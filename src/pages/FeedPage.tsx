import { useMemo, useState } from 'react'
import { RefreshIcon, SearchIcon } from '../components/Icons'
import { EmptyState, ErrorBox, PageHeader, SpecialtyTag, Spinner, StatusPill } from '../components/ui'
import { formatRelative, normalize, plural } from '../lib/format'
import { useAsync, useCatalog, type CatalogEntry } from '../lib/hooks'
import { notifications, useLocalVersion } from '../lib/localBackend'
import { Link } from '../components/Link'
import { replaceQuery } from '../lib/router'
import { loadSources, sourceLabel } from '../lib/sources'
import { SPECIALTIES, specialtyName } from '../lib/specialties'
import type { User } from '../lib/types'

const PAGE_SIZE = 30

type Scope = 'minhas' | 'todas'
type Status = 'todas' | 'disponiveis' | 'processando' | 'novidades'
type Order = 'recentes' | 'az'

export function FeedPage({ user, query }: { user: User; query: URLSearchParams }) {
  useLocalVersion()
  const catalog = useCatalog()
  const sources = useAsync(() => loadSources(), 'sources')
  const [visible, setVisible] = useState(PAGE_SIZE)

  const hasSpecialties = user.specialties.length > 0
  const scope: Scope = query.get('escopo') === 'todas' || !hasSpecialties ? 'todas' : 'minhas'
  const specialty = query.get('esp') ?? ''
  const search = query.get('q') ?? ''
  const status = (query.get('status') as Status | null) ?? 'todas'
  const order: Order = query.get('ordem') === 'az' ? 'az' : 'recentes'

  const params = { escopo: scope === 'todas' && hasSpecialties ? 'todas' : null, esp: specialty || null, q: search || null, status: status === 'todas' ? null : status, ordem: order === 'az' ? 'az' : null }
  const setParam = (key: keyof typeof params, value: string | null) => {
    setVisible(PAGE_SIZE)
    replaceQuery('/feed', { ...params, [key]: value })
  }

  const userNotifications = notifications.list(user.id)
  const unreadByGuideline = useMemo(() => {
    const ids = new Set<string>()
    userNotifications.forEach((item) => !item.read && item.guidelineId && ids.add(item.guidelineId))
    return ids
  }, [userNotifications])

  const sourceById = useMemo(() => new Map((sources.data ?? []).map((source) => [source.id, source])), [sources.data])

  const inScope = useMemo(
    () =>
      (catalog.data ?? []).filter(
        (entry) => scope === 'todas' || entry.specialties.some((id) => user.specialties.includes(id)),
      ),
    [catalog.data, scope, user.specialties],
  )

  const results = useMemo(() => {
    const term = normalize(search.trim())
    const filtered = inScope.filter((entry) => {
      if (specialty && !entry.specialties.includes(specialty)) return false
      if (term && !normalize(entry.title).includes(term)) return false
      if (status === 'disponiveis' && !entry.current_version_id) return false
      if (status === 'processando' && entry.current_version_id) return false
      if (status === 'novidades' && !unreadByGuideline.has(entry.id)) return false
      return true
    })
    return filtered.sort((a, b) =>
      order === 'az'
        ? a.title.localeCompare(b.title, 'pt-BR')
        : (b.last_checked_at ?? '').localeCompare(a.last_checked_at ?? '') || a.title.localeCompare(b.title, 'pt-BR'),
    )
  }, [inScope, specialty, search, status, order, unreadByGuideline])

  const chipSpecialties = scope === 'minhas' ? SPECIALTIES.filter((item) => user.specialties.includes(item.id)) : SPECIALTIES
  const withText = inScope.filter((entry) => entry.current_version_id).length
  const lastCheck = inScope.reduce<string | null>(
    (latest, entry) => (entry.last_checked_at && (!latest || entry.last_checked_at > latest) ? entry.last_checked_at : latest),
    null,
  )

  return (
    <>
      <PageHeader
        eyebrow="FEED DE DIRETRIZES"
        title={scope === 'minhas' ? 'Suas especialidades' : 'Todas as diretrizes'}
        description={
          hasSpecialties ? (
            <>
              Acompanhando{' '}
              {user.specialties.map(specialtyName).join(', ')}.{' '}
              <Link to="/perfil" className="text-accent hover:underline">
                Alterar
              </Link>
            </>
          ) : (
            <>
              Você ainda não escolheu especialidades.{' '}
              <Link to="/perfil" className="text-accent hover:underline">
                Escolher agora
              </Link>{' '}
              para receber avisos.
            </>
          )
        }
        actions={
          <button type="button" className="btn-secondary" onClick={catalog.reload} disabled={catalog.loading}>
            <RefreshIcon size={16} /> Atualizar
          </button>
        }
      />

      {catalog.data && (
        <dl className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Diretrizes acompanhadas" value={inScope.length.toLocaleString('pt-BR')} />
          <Stat label="Com texto disponível" value={withText.toLocaleString('pt-BR')} />
          <Stat label="Novidades não lidas" value={unreadByGuideline.size.toLocaleString('pt-BR')} accent={unreadByGuideline.size > 0} />
          <Stat label="Última verificação" value={formatRelative(lastCheck)} />
        </dl>
      )}

      <section aria-label="Filtros" className="panel mb-5 space-y-4 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="field-shell min-h-11 flex-1 text-slate-400">
            <SearchIcon size={18} />
            <input
              type="search"
              aria-label="Buscar diretriz pelo título"
              placeholder="Buscar pelo título — ex.: asma, HIV, diabete"
              defaultValue={search}
              onChange={(event) => setParam('q', event.target.value || null)}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {hasSpecialties && (
              <div className="segmented" role="group" aria-label="Escopo">
                <button type="button" aria-pressed={scope === 'minhas'} onClick={() => replaceQuery('/feed', { ...params, escopo: null, esp: null })}>
                  Minhas
                </button>
                <button type="button" aria-pressed={scope === 'todas'} onClick={() => replaceQuery('/feed', { ...params, escopo: 'todas', esp: null })}>
                  Todas
                </button>
              </div>
            )}
            <select className="select" aria-label="Situação" value={status} onChange={(event) => setParam('status', event.target.value === 'todas' ? null : event.target.value)}>
              <option value="todas">Todas as situações</option>
              <option value="novidades">Só novidades</option>
              <option value="disponiveis">Texto disponível</option>
              <option value="processando">Aguardando processamento</option>
            </select>
            <select className="select" aria-label="Ordenação" value={order} onChange={(event) => setParam('ordem', event.target.value === 'az' ? 'az' : null)}>
              <option value="recentes">Verificadas recentemente</option>
              <option value="az">Título (A–Z)</option>
            </select>
          </div>
        </div>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Especialidade">
          <button type="button" className="chip" aria-pressed={!specialty} onClick={() => setParam('esp', null)}>
            Todas
          </button>
          {chipSpecialties.map((item) => (
            <button key={item.id} type="button" className="chip" aria-pressed={specialty === item.id} onClick={() => setParam('esp', specialty === item.id ? null : item.id)}>
              {item.name}
            </button>
          ))}
        </div>
      </section>

      {catalog.loading && !catalog.data && <Spinner label="Carregando diretrizes…" />}
      {catalog.error && <ErrorBox error={catalog.error} onRetry={catalog.reload} />}

      {catalog.data && (
        <>
          <p className="mb-3 text-sm text-slate-400" aria-live="polite">
            {plural(results.length, 'diretriz encontrada', 'diretrizes encontradas')}
          </p>

          {results.length === 0 ? (
            <EmptyState title="Nenhuma diretriz com esses filtros.">
              Tente outra especialidade, limpe a busca ou veja todas as diretrizes.
            </EmptyState>
          ) : (
            <ul className="grid gap-3">
              {results.slice(0, visible).map((entry) => (
                <GuidelineCard
                  key={entry.id}
                  entry={entry}
                  isNew={unreadByGuideline.has(entry.id)}
                  source={sourceLabel(sourceById.get(entry.source_id))}
                  highlight={specialty}
                />
              ))}
            </ul>
          )}

          {results.length > visible && (
            <div className="mt-5 text-center">
              <button type="button" className="btn-secondary" onClick={() => setVisible((value) => value + PAGE_SIZE)}>
                Mostrar mais ({results.length - visible} restantes)
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}

function Stat({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="panel px-4 py-3">
      <dt className="text-[11px] tracking-wide text-slate-400">{label}</dt>
      <dd className={`mt-1 text-xl font-semibold ${accent ? 'text-accent' : ''}`}>{value}</dd>
    </div>
  )
}

function GuidelineCard({
  entry,
  isNew,
  source,
  highlight,
}: {
  entry: CatalogEntry
  isNew: boolean
  source: string
  highlight: string
}) {
  return (
    <li>
      <Link to={`/diretrizes/${entry.id}`} className="card group block p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2 text-[11px] tracking-wide text-slate-400">
          <span className="font-bold text-slate-300">{source}</span>
          <span aria-hidden="true">·</span>
          <span>Verificada {formatRelative(entry.last_checked_at ?? entry.last_seen_at)}</span>
          {isNew && <StatusPill tone="info">Novidade</StatusPill>}
        </div>
        <h2 className="mt-2 text-base font-semibold leading-snug group-hover:text-accent sm:text-lg">{entry.title}</h2>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {entry.specialties
            .slice()
            .sort((a) => (a === highlight ? -1 : 0))
            .map((id) => (
              <SpecialtyTag key={id} id={id} />
            ))}
          <span className="ml-auto">
            {entry.current_version_id ? (
              <StatusPill tone="ok">Texto disponível</StatusPill>
            ) : (
              <StatusPill tone="warn">Aguardando processamento</StatusPill>
            )}
          </span>
        </div>
      </Link>
    </li>
  )
}
