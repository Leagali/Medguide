import { useState, type FormEvent } from 'react'
import { ArrowIcon, LockIcon, MailIcon, UserIcon } from '../../components/Icons'
import { auth } from '../../lib/localBackend'
import { Link } from '../../components/Link'
import { navigate } from '../../lib/router'
import type { UserProfile } from '../../lib/types'
import { AuthLayout } from './AuthLayout'

const PROFILES: { value: UserProfile; label: string }[] = [
  { value: 'medico', label: 'Médico(a)' },
  { value: 'estudante', label: 'Estudante' },
  { value: 'outro', label: 'Outro profissional' },
]

const MIN_PASSWORD = 8

export function RegisterPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [profile, setProfile] = useState<UserProfile>('medico')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function validate() {
    if (name.trim().length < 2) return 'Informe seu nome.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return 'Informe um e-mail válido.'
    if (password.length < MIN_PASSWORD) return `A senha precisa ter pelo menos ${MIN_PASSWORD} caracteres.`
    if (password !== confirmation) return 'As senhas não conferem.'
    return null
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problem = validate()
    setError(problem)
    if (problem) return
    setSubmitting(true)
    try {
      await auth.register({ name, email, password, profile })
      navigate('/especialidades', { replace: true })
    } catch (caught) {
      setError((caught as Error).message)
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="mb-6">
        <p className="mb-2 text-xs font-bold tracking-[0.2em] text-accent">CRIAR CONTA · PASSO 1 DE 2</p>
        <h2 className="text-3xl font-semibold tracking-tight">Comece a acompanhar.</h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Depois do cadastro, você escolhe as especialidades que quer acompanhar.
        </p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit} noValidate>
        <div>
          <label htmlFor="name" className="mb-2 block text-xs font-semibold text-slate-200">
            Nome
          </label>
          <div className="field-shell text-slate-400">
            <UserIcon />
            <input
              id="name"
              autoComplete="name"
              placeholder="Como devemos chamar você"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
        </div>

        <div>
          <label htmlFor="email" className="mb-2 block text-xs font-semibold text-slate-200">
            E-mail
          </label>
          <div className="field-shell text-slate-400">
            <MailIcon />
            <input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="seu.email@exemplo.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
        </div>

        <fieldset>
          <legend className="mb-2 block text-xs font-semibold text-slate-200">Perfil</legend>
          <div className="grid grid-cols-3 gap-2">
            {PROFILES.map((option) => (
              <label key={option.value} className="choice">
                <input
                  type="radio"
                  name="profile"
                  value={option.value}
                  checked={profile === option.value}
                  onChange={() => setProfile(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="password" className="mb-2 block text-xs font-semibold text-slate-200">
              Senha
            </label>
            <div className="field-shell text-slate-400">
              <LockIcon />
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                placeholder={`Mín. ${MIN_PASSWORD} caracteres`}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
          </div>
          <div>
            <label htmlFor="confirmation" className="mb-2 block text-xs font-semibold text-slate-200">
              Confirmar senha
            </label>
            <div className="field-shell text-slate-400">
              <LockIcon />
              <input
                id="confirmation"
                type="password"
                autoComplete="new-password"
                placeholder="Repita a senha"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </div>
          </div>
        </div>

        {error && (
          <p role="alert" className="text-sm text-rose-300">
            {error}
          </p>
        )}

        <button type="submit" className="auth-button mt-2" disabled={submitting}>
          {submitting ? 'CRIANDO CONTA…' : 'CONTINUAR'}
          <ArrowIcon size={19} />
        </button>
      </form>

      <p className="mt-5 text-center text-sm text-slate-400">
        Já tem conta?{' '}
        <Link to="/login" className="font-semibold text-accent hover:underline">
          Entrar
        </Link>
      </p>
    </AuthLayout>
  )
}
