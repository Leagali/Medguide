import { useSyncExternalStore } from 'react'
import { classifyGuideline } from './specialties'
import type {
  AppNotification,
  Guideline,
  NotificationKind,
  SourceSuggestion,
  User,
  UserProfile,
} from './types'

/*
 * CAMADA PROVISÓRIA — substitui endpoints que o backend ainda não tem:
 *
 *   POST /auth/register, POST /auth/login, POST /auth/logout, GET/PATCH /me
 *   GET /me/notifications, POST /me/notifications/{id}/read
 *   POST /source-suggestions, GET /source-suggestions, POST /source-suggestions/{id}/review
 *
 * Tudo fica no localStorage deste navegador: não há segurança real e os dados
 * não são compartilhados entre pessoas. As funções são assíncronas e usam os
 * mesmos formatos do contrato (src/lib/types.ts) para que a troca pela API seja
 * feita só aqui, sem mexer nas telas.
 */

const STORAGE_KEY = 'medguide.local.v1'

export const DEMO_ADMIN = { email: 'admin@medguide.local', password: 'medguide-admin' }

type StoredUser = User & { passwordHash: string; salt: string }

type Snapshot = { versions: Record<string, string | null>; syncedAt: string }

type LocalState = {
  users: StoredUser[]
  sessionUserId: string | null
  notifications: Record<string, AppNotification[]>
  snapshots: Record<string, Snapshot>
  suggestions: SourceSuggestion[]
}

const emptyState = (): LocalState => ({
  users: [],
  sessionUserId: null,
  notifications: {},
  snapshots: {},
  suggestions: [],
})

let memoryState: LocalState | null = null
const listeners = new Set<() => void>()
let version = 0

function load(): LocalState {
  if (memoryState) return memoryState
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    memoryState = raw ? { ...emptyState(), ...(JSON.parse(raw) as LocalState) } : emptyState()
  } catch {
    // Navegação privada ou armazenamento bloqueado: segue só em memória.
    memoryState = emptyState()
  }
  return memoryState
}

function save(update: (state: LocalState) => void) {
  const state = structuredClone(load())
  update(state)
  memoryState = state
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Sem persistência: o estado vale até recarregar a página.
  }
  version++
  listeners.forEach((listener) => listener())
}

window.addEventListener('storage', (event) => {
  if (event.key !== STORAGE_KEY) return
  memoryState = null
  version++
  listeners.forEach((listener) => listener())
})

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Re-renderiza o componente sempre que a camada local mudar. */
export function useLocalVersion() {
  return useSyncExternalStore(subscribe, () => version)
}

export class LocalError extends Error {}

const id = () => crypto.randomUUID()
const now = () => new Date().toISOString()

async function hashPassword(password: string, salt: string) {
  const data = new TextEncoder().encode(`${salt}:${password}`)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

function publicUser({ passwordHash: _hash, salt: _salt, ...user }: StoredUser): User {
  return user
}

function pushNotification(
  state: LocalState,
  userId: string,
  kind: NotificationKind,
  title: string,
  body: string,
  guidelineId?: string,
) {
  const list = state.notifications[userId] ?? []
  list.unshift({ id: id(), kind, title, body, createdAt: now(), read: false, guidelineId })
  state.notifications[userId] = list.slice(0, 200)
}

async function ensureDemoAdmin() {
  if (load().users.some((user) => user.email === DEMO_ADMIN.email)) return
  const salt = id()
  const passwordHash = await hashPassword(DEMO_ADMIN.password, salt)
  save((state) => {
    if (state.users.some((user) => user.email === DEMO_ADMIN.email)) return
    state.users.push({
      id: id(),
      name: 'Administração MedGuide',
      email: DEMO_ADMIN.email,
      profile: 'outro',
      role: 'admin',
      specialties: [],
      createdAt: now(),
      passwordHash,
      salt,
    })
  })
}

// ---------------------------------------------------------------- Autenticação

export const auth = {
  currentUser(): User | null {
    const state = load()
    const user = state.users.find((candidate) => candidate.id === state.sessionUserId)
    return user ? publicUser(user) : null
  },

  async register(input: { name: string; email: string; password: string; profile: UserProfile }) {
    await ensureDemoAdmin()
    const email = input.email.trim().toLowerCase()
    if (load().users.some((user) => user.email === email)) {
      throw new LocalError('Já existe uma conta com este e-mail.')
    }
    const salt = id()
    const passwordHash = await hashPassword(input.password, salt)
    const user: StoredUser = {
      id: id(),
      name: input.name.trim(),
      email,
      profile: input.profile,
      role: 'user',
      specialties: [],
      createdAt: now(),
      passwordHash,
      salt,
    }
    save((state) => {
      state.users.push(user)
      state.sessionUserId = user.id
    })
    return publicUser(user)
  },

  async login(emailInput: string, password: string) {
    await ensureDemoAdmin()
    const email = emailInput.trim().toLowerCase()
    const user = load().users.find((candidate) => candidate.email === email)
    if (!user || (await hashPassword(password, user.salt)) !== user.passwordHash) {
      throw new LocalError('E-mail ou senha incorretos.')
    }
    save((state) => {
      state.sessionUserId = user.id
    })
    return publicUser(user)
  },

  logout() {
    save((state) => {
      state.sessionUserId = null
    })
  },

  async updateMe(patch: Partial<Pick<User, 'name' | 'profile' | 'specialties'>>) {
    const current = auth.currentUser()
    if (!current) throw new LocalError('Sessão expirada.')
    save((state) => {
      const user = state.users.find((candidate) => candidate.id === current.id)
      if (user) Object.assign(user, patch)
    })
    return auth.currentUser()!
  },
}

// --------------------------------------------------------------- Notificações

export const notifications = {
  list(userId: string): AppNotification[] {
    return load().notifications[userId] ?? []
  },

  unreadCount(userId: string) {
    return notifications.list(userId).filter((item) => !item.read).length
  },

  markRead(userId: string, notificationId: string) {
    save((state) => {
      const item = state.notifications[userId]?.find((candidate) => candidate.id === notificationId)
      if (item) item.read = true
    })
  },

  markAllRead(userId: string) {
    save((state) => {
      state.notifications[userId]?.forEach((item) => (item.read = true))
    })
  },

  /**
   * Compara o catálogo atual com o último visto pelo usuário e gera avisos de
   * diretriz nova ou nova versão nas especialidades dele. Quando o backend
   * tiver notificações, essa comparação passa a ser feita no servidor.
   */
  sync(user: User, guidelines: Guideline[]) {
    const previous = load().snapshots[user.id]
    const current: Record<string, string | null> = {}
    guidelines.forEach((guideline) => (current[guideline.id] = guideline.current_version_id))

    const relevant = (guideline: Guideline) =>
      classifyGuideline(guideline.title).some((specialty) => user.specialties.includes(specialty))

    const changes: { guideline: Guideline; kind: 'new_guideline' | 'new_version' }[] = []
    if (previous) {
      for (const guideline of guidelines) {
        if (!relevant(guideline)) continue
        if (!(guideline.id in previous.versions)) {
          changes.push({ guideline, kind: 'new_guideline' })
        } else {
          const before = previous.versions[guideline.id]
          // Primeira extração (null → versão) não é atualização da diretriz.
          if (before && guideline.current_version_id && before !== guideline.current_version_id) {
            changes.push({ guideline, kind: 'new_version' })
          }
        }
      }
    }

    const unchanged =
      previous &&
      changes.length === 0 &&
      Object.keys(current).length === Object.keys(previous.versions).length &&
      Object.entries(current).every(([key, value]) => previous.versions[key] === value)
    if (unchanged) return

    save((state) => {
      if (!previous) {
        const count = guidelines.filter(relevant).length
        pushNotification(
          state,
          user.id,
          'welcome',
          'Acompanhamento iniciado',
          `Você passou a acompanhar ${count} diretrizes das suas especialidades. Avisaremos aqui quando surgir uma diretriz nova ou uma nova versão.`,
        )
      }
      for (const { guideline, kind } of changes) {
        pushNotification(
          state,
          user.id,
          kind,
          kind === 'new_guideline' ? 'Nova diretriz publicada' : 'Nova versão detectada',
          guideline.title,
          guideline.id,
        )
      }
      state.snapshots[user.id] = { versions: current, syncedAt: now() }
    })
  },
}

// ------------------------------------------------------- Sugestões de fontes

export const suggestions = {
  list(): SourceSuggestion[] {
    return load().suggestions
  },

  mine(userId: string) {
    return suggestions.list().filter((item) => item.suggestedBy.id === userId)
  },

  async create(
    user: User,
    input: Pick<SourceSuggestion, 'name' | 'url' | 'organization' | 'specialties' | 'justification'>,
  ) {
    const suggestion: SourceSuggestion = {
      ...input,
      id: id(),
      status: 'pending',
      reviewNote: null,
      suggestedBy: { id: user.id, name: user.name, email: user.email },
      createdAt: now(),
      reviewedAt: null,
    }
    save((state) => {
      state.suggestions.unshift(suggestion)
      state.users
        .filter((candidate) => candidate.role === 'admin')
        .forEach((admin) =>
          pushNotification(
            state,
            admin.id,
            'suggestion_received',
            'Nova fonte sugerida',
            `${user.name} sugeriu “${input.name}”.`,
          ),
        )
    })
    return suggestion
  },

  async review(suggestionId: string, decision: 'approved' | 'rejected', note: string) {
    save((state) => {
      const suggestion = state.suggestions.find((item) => item.id === suggestionId)
      if (!suggestion || suggestion.status !== 'pending') return
      suggestion.status = decision
      suggestion.reviewNote = note.trim() || null
      suggestion.reviewedAt = now()
      pushNotification(
        state,
        suggestion.suggestedBy.id,
        decision === 'approved' ? 'suggestion_approved' : 'suggestion_rejected',
        decision === 'approved' ? 'Sugestão de fonte aprovada' : 'Sugestão de fonte não aprovada',
        decision === 'approved'
          ? `“${suggestion.name}” foi aprovada e entrará na fila de integração.${note.trim() ? ` ${note.trim()}` : ''}`
          : `“${suggestion.name}” não foi aprovada.${note.trim() ? ` Motivo: ${note.trim()}` : ''}`,
      )
    })
  },
}
