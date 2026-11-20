import type { ReactNode } from 'react'
import { Backdrop, Brand } from '../../components/ui'

const HIGHLIGHTS = [
  ['FONTES', 'Oficiais'],
  ['HISTÓRICO', 'De versões'],
  ['AVISOS', 'Por especialidade'],
]

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="relative isolate min-h-screen overflow-hidden text-white">
      <Backdrop />
      <div className="ambient-glow glow-bottom -z-10" aria-hidden="true" />

      <div className="relative mx-auto flex min-h-screen max-w-360 flex-col px-4 sm:px-8 lg:px-14">
        <header className="flex items-center justify-between border-b border-white/10 py-4 sm:py-5">
          <Brand />
          <div className="hidden items-center gap-2 rounded-full border border-white/10 px-4 py-2 sm:flex">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <span className="text-[10px] tracking-[0.12em] text-slate-300">CONHECIMENTO EM SAÚDE</span>
          </div>
        </header>

        <section className="grid flex-1 grid-cols-1 items-center gap-9 py-8 sm:gap-12 sm:py-10 lg:grid-cols-[1fr_460px] lg:gap-14">
          <div className="max-w-2xl">
            <div className="mb-5 flex items-center gap-3 sm:mb-6">
              <span className="h-px w-10 bg-accent" />
              <p className="text-xs font-bold tracking-[0.2em] text-accent">INFORMAÇÃO CLÍNICA, SEM RUÍDO</p>
            </div>

            <h1 className="display-font max-w-xl text-5xl leading-[0.98] tracking-wide sm:text-6xl lg:text-7xl">
              A MEDICINA
              <br />
              <span className="text-accent">NÃO PARA.</span>
              <br />
              MANTENHA-SE
              <br />
              ATUALIZADO.
            </h1>

            <p className="mt-5 max-w-lg text-sm leading-6 text-slate-300 sm:mt-6 sm:text-base sm:leading-7">
              O MedGuide acompanha diretrizes oficiais, como os PCDT da CONITEC, registra cada versão
              observada e avisa quando algo muda nas suas especialidades. Sem precisar conferir as
              fontes manualmente.
            </p>

            <div className="mt-7 grid max-w-lg grid-cols-3 gap-2 sm:mt-8 sm:gap-3">
              {HIGHLIGHTS.map(([title, subtitle]) => (
                <div key={title} className="border-l-2 border-accent/70 pl-2 sm:pl-3">
                  <p className="text-[10px] font-bold text-white sm:text-xs">{title}</p>
                  <p className="mt-1 text-[10px] text-slate-400 sm:text-xs">{subtitle}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mx-auto w-full max-w-115">
            <div className="login-card rounded-2xl p-6 sm:p-8">{children}</div>
            <p className="mt-5 text-center text-[10px] tracking-wider text-slate-500">MEDGUIDE © 2026</p>
          </div>
        </section>
      </div>
    </main>
  )
}
