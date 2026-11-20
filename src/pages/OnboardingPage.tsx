import { useState } from 'react'
import { ArrowIcon } from '../components/Icons'
import { SpecialtyPicker } from '../components/SpecialtyPicker'
import { Backdrop, Brand, Eyebrow, ProvisionalNote } from '../components/ui'
import { useCatalog } from '../lib/hooks'
import { auth } from '../lib/localBackend'
import { navigate } from '../lib/router'
import type { User } from '../lib/types'

export function OnboardingPage({ user }: { user: User }) {
  const [selected, setSelected] = useState<string[]>(user.specialties)
  const catalog = useCatalog()

  async function finish() {
    await auth.updateMe({ specialties: selected })
    navigate('/feed', { replace: true })
  }

  return (
    <main className="relative isolate min-h-screen overflow-x-clip text-white">
      <Backdrop />
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
        <Brand />
        <div className="mt-10 mb-6">
          <Eyebrow>CRIAR CONTA · PASSO 2 DE 2</Eyebrow>
          <h1 className="text-3xl font-semibold tracking-tight">
            Olá, {user.name.split(' ')[0]}. Quais especialidades você quer acompanhar?
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Seu feed e suas notificações vão priorizar as diretrizes destas áreas. Você pode mudar a
            seleção depois, no seu perfil.
          </p>
        </div>

        <SpecialtyPicker value={selected} onChange={setSelected} catalog={catalog.data} />

        {catalog.error && (
          <p className="mt-4 text-sm text-amber-200">
            Não foi possível contar as diretrizes agora ({catalog.error.message}). Você ainda pode
            escolher as especialidades.
          </p>
        )}

        <div className="sticky bottom-0 mt-8 flex flex-col-reverse gap-3 border-t border-white/10 bg-[#03070c]/90 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
          <button type="button" className="btn-ghost" onClick={finish}>
            Pular por enquanto
          </button>
          <div className="flex items-center gap-4">
            <p className="text-sm text-slate-400">
              {selected.length === 0 ? 'Nenhuma selecionada' : `${selected.length} selecionada(s)`}
            </p>
            <button type="button" className="btn-primary" disabled={selected.length === 0} onClick={finish}>
              Ir para o feed
              <ArrowIcon size={18} />
            </button>
          </div>
        </div>

        <ProvisionalNote>
          a classificação das diretrizes por especialidade é feita pelas palavras do título, porque o
          catálogo da CONITEC não informa a especialidade.
        </ProvisionalNote>
      </div>
    </main>
  )
}
