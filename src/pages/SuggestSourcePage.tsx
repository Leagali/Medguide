import { useState, type FormEvent } from 'react'
import { EmptyState, Field, PageHeader, ProvisionalNote, SpecialtyTag, StatusPill } from '../components/ui'
import { formatDate } from '../lib/format'
import { SUGGESTION_STATUS } from '../lib/labels'
import { suggestions, useLocalVersion } from '../lib/localBackend'
import { SPECIALTIES } from '../lib/specialties'
import type { User } from '../lib/types'

const emptyForm = { name: '', url: '', organization: '', justification: '', specialties: [] as string[] }

export function SuggestSourcePage({ user }: { user: User }) {
  useLocalVersion()
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const mine = suggestions.mine(user.id)

  function update<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((previous) => ({ ...previous, [key]: value }))
    setSent(false)
  }

  function validate() {
    if (form.name.trim().length < 3) return 'Informe o nome da fonte.'
    try {
      const url = new URL(form.url.trim())
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error()
    } catch {
      return 'Informe um endereço válido, começando com https://.'
    }
    if (form.organization.trim().length < 2) return 'Informe a instituição responsável.'
    if (form.justification.trim().length < 20) return 'Explique em pelo menos 20 caracteres por que a fonte é relevante.'
    return null
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problem = validate()
    setError(problem)
    if (problem) return
    await suggestions.create(user, {
      name: form.name.trim(),
      url: form.url.trim(),
      organization: form.organization.trim(),
      justification: form.justification.trim(),
      specialties: form.specialties,
    })
    setForm(emptyForm)
    setSent(true)
  }

  return (
    <>
      <PageHeader
        eyebrow="SUGERIR FONTE"
        title="Conhece outra fonte oficial?"
        description="Sugira sociedades médicas, ministérios ou agências que publicam diretrizes. A equipe de administração analisa cada sugestão antes de integrar a fonte ao monitoramento."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <form className="panel space-y-4 p-4 sm:p-6" onSubmit={handleSubmit} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nome da fonte" htmlFor="s-name">
              <input id="s-name" className="input" placeholder="Ex.: Diretrizes da SBC" value={form.name} onChange={(event) => update('name', event.target.value)} />
            </Field>
            <Field label="Instituição responsável" htmlFor="s-org">
              <input id="s-org" className="input" placeholder="Ex.: Sociedade Brasileira de Cardiologia" value={form.organization} onChange={(event) => update('organization', event.target.value)} />
            </Field>
          </div>
          <Field label="Endereço da página com as diretrizes" htmlFor="s-url">
            <input id="s-url" className="input" type="url" inputMode="url" placeholder="https://" value={form.url} onChange={(event) => update('url', event.target.value)} />
          </Field>
          <Field label="Por que essa fonte é relevante?" htmlFor="s-why" hint="Ex.: é a referência usada na residência, publica atualizações anuais…">
            <textarea id="s-why" className="input min-h-28" value={form.justification} onChange={(event) => update('justification', event.target.value)} />
          </Field>
          <fieldset>
            <legend className="mb-2 text-xs font-semibold text-slate-200">Especialidades relacionadas (opcional)</legend>
            <div className="flex flex-wrap gap-2">
              {SPECIALTIES.map((specialty) => {
                const selected = form.specialties.includes(specialty.id)
                return (
                  <button
                    key={specialty.id}
                    type="button"
                    className="chip"
                    aria-pressed={selected}
                    onClick={() =>
                      update('specialties', selected ? form.specialties.filter((id) => id !== specialty.id) : [...form.specialties, specialty.id])
                    }
                  >
                    {specialty.name}
                  </button>
                )
              })}
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="text-sm text-rose-300">
              {error}
            </p>
          )}
          {sent && (
            <p role="status" className="text-sm text-emerald-300">
              Sugestão enviada. Você será avisado quando ela for analisada.
            </p>
          )}

          <button type="submit" className="btn-primary">
            Enviar sugestão
          </button>
        </form>

        <aside>
          <h2 className="mb-3 font-semibold">Suas sugestões</h2>
          {mine.length === 0 ? (
            <EmptyState title="Nenhuma sugestão enviada." />
          ) : (
            <ul className="space-y-2">
              {mine.map((item) => (
                <li key={item.id} className="panel p-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold">{item.name}</p>
                    <StatusPill tone={SUGGESTION_STATUS[item.status].tone}>{SUGGESTION_STATUS[item.status].label}</StatusPill>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    {item.organization} · enviada em {formatDate(item.createdAt)}
                  </p>
                  {item.specialties.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.specialties.map((id) => (
                        <SpecialtyTag key={id} id={id} />
                      ))}
                    </div>
                  )}
                  {item.reviewNote && <p className="mt-2 text-sm text-slate-300">“{item.reviewNote}”</p>}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      <ProvisionalNote>
        as sugestões ficam salvas neste navegador. Para testar a aprovação, entre com a conta de
        administração neste mesmo navegador.
      </ProvisionalNote>
    </>
  )
}
