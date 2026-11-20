import { useEffect } from 'react'
import { AppShell } from './components/AppShell'
import { EmptyState } from './components/ui'
import { useCurrentUser } from './lib/hooks'
import { Link } from './components/Link'
import { matchPath, navigate, useLocation } from './lib/router'
import { AdminPage } from './pages/AdminPage'
import { LoginPage } from './pages/auth/LoginPage'
import { RegisterPage } from './pages/auth/RegisterPage'
import { FeedPage } from './pages/FeedPage'
import { GuidelinePage } from './pages/GuidelinePage'
import { NotificationsPage } from './pages/NotificationsPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { ProfilePage } from './pages/ProfilePage'
import { SuggestSourcePage } from './pages/SuggestSourcePage'

const PUBLIC_PATHS = ['/login', '/cadastro']

function Redirect({ to }: { to: string }) {
  useEffect(() => navigate(to, { replace: true }), [to])
  return null
}

export default function App() {
  const { path, query } = useLocation()
  const user = useCurrentUser()

  if (!user) {
    if (path === '/cadastro') return <RegisterPage />
    // Telas protegidas mostram o login e voltam para o endereço pedido.
    const wanted = PUBLIC_PATHS.includes(path) || path === '/' ? null : window.location.hash.slice(1)
    return <LoginPage redirect={wanted} />
  }

  if (path === '/' || PUBLIC_PATHS.includes(path)) return <Redirect to="/feed" />
  if (path === '/especialidades') return <OnboardingPage user={user} />

  const guideline = matchPath('/diretrizes/:id', path)
  let page
  if (path === '/feed') page = <FeedPage user={user} query={query} />
  else if (guideline) page = <GuidelinePage key={guideline.id} id={guideline.id} user={user} query={query} />
  else if (path === '/notificacoes') page = <NotificationsPage user={user} />
  else if (path === '/perfil') page = <ProfilePage key={user.id} user={user} />
  else if (path === '/sugerir-fonte') page = <SuggestSourcePage user={user} />
  else if (path === '/admin')
    page =
      user.role === 'admin' ? (
        <AdminPage query={query} />
      ) : (
        <EmptyState title="Acesso restrito à administração.">
          Entre com uma conta de administração para gerenciar fontes.
        </EmptyState>
      )
  else
    page = (
      <EmptyState title="Página não encontrada.">
        <Link to="/feed" className="text-accent hover:underline">
          Voltar ao feed
        </Link>
      </EmptyState>
    )

  return (
    <AppShell user={user} path={path}>
      {page}
    </AppShell>
  )
}
