import { useState, type FormEvent } from 'react'
import { SpecialtyPicker } from '../components/SpecialtyPicker'
import { Field, PageHeader } from '../components/ui'
import { formatDate } from '../lib/format'
import { useCatalog } from '../lib/hooks'
import { auth } from '../lib/localBackend'
import type { User, UserProfile } from '../lib/types'

export function ProfilePage({ user }: { user: User }) {
  const catalog = useCatalog()
  const [name, setName] = useState(user.name)
  const [profile, setProfile] = useState<UserProfile>(user.profile)
  const [specialties, setSpecialties] = useState(user.specialties)
  const [saved, setSaved] = useState(false)

  const dirty =
    name.trim() !== user.name ||
    profile !== user.profile ||
    specialties.length !== user.specialties.length ||
    specialties.some((id) => !user.specialties.includes(id))

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (name.trim().length < 2) return
    await auth.updateMe({ name: name.trim(), profile, specialties })
    setSaved(true)
    window.setTimeout(() => setSaved(false), 2500)
  }

  return (
    <form onSubmit={handleSubmit}>
      <PageHeader
        eyebrow="PERFIL"
        title="Sua conta"
        description={`${user.email} · conta criada em ${formatDate(user.createdAt)}`}
        actions={
          <>
            {saved && (
              <span role="status" className="self-center text-sm text-emerald-300">
                Alterações salvas.
              </span>
            )}
            <button type="submit" className="btn-primary" disabled={!dirty || name.trim().length < 2}>
              Salvar alterações
            </button>
          </>
        }
      />

      <section className="panel mb-6 grid gap-4 p-4 sm:grid-cols-2 sm:p-6">
        <Field label="Nome" htmlFor="profile-name">
          <input id="profile-name" className="input" value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" />
        </Field>
        <Field label="Perfil" htmlFor="profile-kind">
          <select id="profile-kind" className="select w-full" value={profile} onChange={(event) => setProfile(event.target.value as UserProfile)}>
            <option value="medico">Médico(a)</option>
            <option value="estudante">Estudante</option>
            <option value="outro">Outro profissional</option>
          </select>
        </Field>
      </section>

      <section>
        <h2 className="text-lg font-semibold">Especialidades acompanhadas</h2>
        <p className="mt-1 mb-4 text-sm text-slate-400">
          Definem o que aparece em “Minhas” no feed e quais diretrizes geram avisos.
        </p>
        <SpecialtyPicker value={specialties} onChange={setSpecialties} catalog={catalog.data} />
      </section>
    </form>
  )
}
