import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useCatalog } from '../lib/hooks'
import { auth, notifications, useLocalVersion } from '../lib/localBackend'
import { Link } from './Link'
import { navigate } from '../lib/router'
import type { User } from '../lib/types'
import { BellIcon, FeedIcon, LogoutIcon, PlusIcon, ShieldIcon, UserIcon } from './Icons'
import { Backdrop, Brand } from './ui'

type NavItem = { to: string; label: string; icon: ReactNode; match: string; badge?: number }

export function AppShell({ user, path, children }: { user: User; path: string; children: ReactNode }) {
  useLocalVersion()
  const catalog = useCatalog()
  const unread = notifications.unreadCount(user.id)

  // Compara o catálogo com o último visto pelo usuário e gera avisos.
  useEffect(() => {
    if (catalog.data) notifications.sync(user, catalog.data)
  }, [catalog.data, user])

  const items: NavItem[] = [
    { to: '/feed', label: 'Feed', icon: <FeedIcon size={18} />, match: '/feed' },
    { to: '/notificacoes', label: 'Notificações', icon: <BellIcon size={18} />, match: '/notificacoes', badge: unread },
    { to: '/sugerir-fonte', label: 'Sugerir fonte', icon: <PlusIcon size={18} />, match: '/sugerir-fonte' },
  ]
  if (user.role === 'admin') {
    items.push({ to: '/admin', label: 'Administração', icon: <ShieldIcon size={18} />, match: '/admin' })
  }

  return (
    <div className="relative isolate min-h-screen overflow-x-clip text-white">
      <Backdrop />
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#03070c]/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-8">
          <Link to="/feed" aria-label="MedGuide — início">
            <Brand compact />
          </Link>

          <nav aria-label="Principal" className="ml-6 hidden items-center gap-1 md:flex">
            {items.map((item) => (
              <NavLink key={item.to} item={item} active={path.startsWith(item.match)} />
            ))}
          </nav>

          <div className="ml-auto">
            <UserMenu user={user} />
          </div>
        </div>

        <nav aria-label="Principal" className="flex gap-1 overflow-x-auto px-3 pb-2 md:hidden">
          {items.map((item) => (
            <NavLink key={item.to} item={item} active={path.startsWith(item.match)} />
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-8 sm:py-10">{children}</main>

      <footer className="mx-auto max-w-7xl px-4 pb-8 text-[11px] leading-5 text-slate-500 sm:px-8">
        O MedGuide reproduz o conteúdo das fontes oficiais e não substitui o documento publicado. Confira
        sempre o original antes de uma decisão clínica.
      </footer>
    </div>
  )
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link to={item.to} className={`nav-link ${active ? 'is-active' : ''}`} aria-current={active ? 'page' : undefined}>
      {item.icon}
      <span className="whitespace-nowrap">{item.label}</span>
      {item.badge ? (
        <span className="badge" aria-label={`${item.badge} não lidas`}>
          {item.badge > 99 ? '99+' : item.badge}
        </span>
      ) : null}
    </Link>
  )
}

function UserMenu({ user }: { user: User }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !ref.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const initials = user.name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="flex items-center gap-2 rounded-full border border-white/10 py-1 pr-3 pl-1 hover:border-accent/40"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/15 text-xs font-bold text-accent">
          {initials || <UserIcon size={14} />}
        </span>
        <span className="hidden max-w-36 truncate text-sm sm:block">{user.name}</span>
      </button>

      {open && (
        <div role="menu" className="menu absolute right-0 mt-2 w-64">
          <div className="border-b border-white/10 px-4 py-3">
            <p className="truncate text-sm font-semibold">{user.name}</p>
            <p className="truncate text-xs text-slate-400">{user.email}</p>
            {user.role === 'admin' && <p className="mt-1 text-[10px] font-bold tracking-wider text-accent">ADMINISTRADOR</p>}
          </div>
          <Link to="/perfil" role="menuitem" className="menu-item" onClick={() => setOpen(false)}>
            <UserIcon size={16} /> Perfil e especialidades
          </Link>
          <button
            type="button"
            role="menuitem"
            className="menu-item w-full"
            onClick={() => {
              auth.logout()
              navigate('/login', { replace: true })
            }}
          >
            <LogoutIcon size={16} /> Sair
          </button>
        </div>
      )}
    </div>
  )
}
