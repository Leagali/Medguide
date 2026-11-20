import { useState } from 'react'
import { BellIcon, CheckIcon, HistoryIcon, PlusIcon, ShieldIcon } from '../components/Icons'
import { EmptyState, PageHeader, ProvisionalNote } from '../components/ui'
import { formatDateTime, formatRelative } from '../lib/format'
import { notifications, useLocalVersion } from '../lib/localBackend'
import { navigate } from '../lib/router'
import type { AppNotification, User } from '../lib/types'

const ICONS: Record<AppNotification['kind'], typeof BellIcon> = {
  welcome: BellIcon,
  new_guideline: PlusIcon,
  new_version: HistoryIcon,
  suggestion_received: ShieldIcon,
  suggestion_approved: CheckIcon,
  suggestion_rejected: ShieldIcon,
}

export function NotificationsPage({ user }: { user: User }) {
  useLocalVersion()
  const [onlyUnread, setOnlyUnread] = useState(false)
  const all = notifications.list(user.id)
  const unread = all.filter((item) => !item.read).length
  const items = onlyUnread ? all.filter((item) => !item.read) : all

  function open(item: AppNotification) {
    notifications.markRead(user.id, item.id)
    if (item.guidelineId) navigate(`/diretrizes/${item.guidelineId}`)
    else if (item.kind === 'suggestion_received') navigate('/admin?aba=sugestoes')
    else if (item.kind.startsWith('suggestion_')) navigate('/sugerir-fonte')
  }

  return (
    <>
      <PageHeader
        eyebrow="NOTIFICAÇÕES"
        title="Avisos e atualizações"
        description="Você é avisado quando surge uma diretriz nova ou uma nova versão nas suas especialidades, e quando uma sugestão de fonte é analisada."
        actions={
          <>
            <div className="segmented" role="group" aria-label="Filtro">
              <button type="button" aria-pressed={!onlyUnread} onClick={() => setOnlyUnread(false)}>
                Todas
              </button>
              <button type="button" aria-pressed={onlyUnread} onClick={() => setOnlyUnread(true)}>
                Não lidas ({unread})
              </button>
            </div>
            <button type="button" className="btn-secondary" disabled={unread === 0} onClick={() => notifications.markAllRead(user.id)}>
              <CheckIcon size={16} /> Marcar todas como lidas
            </button>
          </>
        }
      />

      {items.length === 0 ? (
        <EmptyState title={onlyUnread ? 'Nenhum aviso não lido.' : 'Nenhum aviso ainda.'}>
          {user.specialties.length === 0
            ? 'Escolha especialidades no seu perfil para receber avisos sobre elas.'
            : 'Quando uma diretriz das suas especialidades mudar, o aviso aparece aqui.'}
        </EmptyState>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => {
            const Icon = ICONS[item.kind]
            const clickable = Boolean(item.guidelineId) || item.kind.startsWith('suggestion_')
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => (clickable ? open(item) : notifications.markRead(user.id, item.id))}
                  className={`notification ${item.read ? '' : 'is-unread'}`}
                >
                  <span className="icon" aria-hidden="true">
                    <Icon size={18} />
                  </span>
                  <span className="min-w-0 flex-1 text-left">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold">{item.title}</span>
                      <time className="text-xs text-slate-400" dateTime={item.createdAt} title={formatDateTime(item.createdAt)}>
                        {formatRelative(item.createdAt)}
                      </time>
                    </span>
                    <span className="mt-0.5 block text-sm leading-6 text-slate-300">{item.body}</span>
                  </span>
                  {!item.read && <span className="dot" aria-label="Não lida" />}
                </button>
              </li>
            )
          })}
        </ul>
      )}

      <ProvisionalNote>
        os avisos são calculados neste navegador, comparando o catálogo atual com o último que você viu.
        Com o serviço de notificações no backend, eles passarão a chegar também por e-mail e em qualquer
        dispositivo.
      </ProvisionalNote>
    </>
  )
}
