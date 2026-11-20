import { useState, type FormEvent } from 'react'
import { ArrowIcon, LockIcon, MailIcon, MedicalIcon, VisibilityIcon } from '../../components/Icons'
import { DEMO_ADMIN, auth } from '../../lib/localBackend'
import { Link } from '../../components/Link'
import { navigate } from '../../lib/router'
import { AuthLayout } from './AuthLayout'

export function LoginPage({ redirect }: { redirect: string | null }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await auth.login(email, password)
      navigate(redirect ?? '/feed', { replace: true })
    } catch (caught) {
      setError((caught as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="mb-6">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-200/30 bg-cyan-200/5 text-accent">
          <MedicalIcon />
        </div>
        <p className="mb-2 text-xs font-bold tracking-[0.2em] text-accent">ACESSO À PLATAFORMA</p>
        <h2 className="text-3xl font-semibold tracking-tight">Bem-vindo de volta.</h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Entre na sua conta para acompanhar as atualizações das suas especialidades.
        </p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit} noValidate>
        <div>
          <label htmlFor="email" className="mb-2 block text-xs font-semibold text-slate-200">
            E-mail
          </label>
          <div className="field-shell text-slate-400">
            <MailIcon />
            <input
              id="email"
              type="email"
              placeholder="seu.email@exemplo.com"
              autoComplete="email"
              inputMode="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
        </div>

        <div>
          <label htmlFor="password" className="mb-2 block text-xs font-semibold text-slate-200">
            Senha
          </label>
          <div className="field-shell text-slate-400">
            <LockIcon />
            <input
              id="password"
              type={isPasswordVisible ? 'text' : 'password'}
              placeholder="Digite sua senha"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              type="button"
              className="password-toggle"
              aria-label={isPasswordVisible ? 'Ocultar senha' : 'Mostrar senha'}
              aria-pressed={isPasswordVisible}
              onClick={() => setIsPasswordVisible((visible) => !visible)}
            >
              <VisibilityIcon visible={isPasswordVisible} />
            </button>
          </div>
        </div>

        {error && (
          <p role="alert" className="text-sm text-rose-300">
            {error}
          </p>
        )}

        <button type="submit" className="auth-button mt-2" disabled={submitting || !email || !password}>
          {submitting ? 'ENTRANDO…' : 'ENTRAR NA PLATAFORMA'}
          <ArrowIcon size={19} />
        </button>
      </form>

      <p className="mt-5 text-center text-sm text-slate-400">
        Ainda não tem conta?{' '}
        <Link to="/cadastro" className="font-semibold text-accent hover:underline">
          Criar conta
        </Link>
      </p>

      <div className="my-6 h-px bg-white/10" />

      <p className="text-xs leading-5 text-slate-500">
        <strong className="font-semibold text-slate-400">Demonstração:</strong> as contas ficam salvas só
        neste navegador até o backend de usuários existir. Acesso administrativo:{' '}
        <code className="text-slate-300">{DEMO_ADMIN.email}</code> /{' '}
        <code className="text-slate-300">{DEMO_ADMIN.password}</code>
      </p>
    </AuthLayout>
  )
}
