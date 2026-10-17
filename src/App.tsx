
import { useState } from 'react'

function MedicalIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M10 3H18V10H25V18H18V25H10V18H3V10H10V3Z"
        stroke="currentColor"
        strokeWidth="1.8"
      />
    </svg>
  )
}

function MailIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="3"
        y="5"
        width="18"
        height="14"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M4 7L12 13L20 7"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function LockIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="4"
        y="10"
        width="16"
        height="11"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M8 10V7a4 4 0 0 1 8 0v3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M5 12H19M12 5L19 12L12 19"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function VisibilityIcon({ visible }: { visible: boolean }) {
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle
        cx="12"
        cy="12"
        r="2.5"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      {!visible && (
        <path
          d="m4 4 16 16"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      )}
    </svg>
  )
}

export default function App() {
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-[#03070c] text-white">
      {/* Elementos decorativos do fundo */}
      <div
        aria-hidden="true"
        className="background-grid absolute inset-0"
      />
      <div
        aria-hidden="true"
        className="ambient-glow glow-left"
      />
      <div
        aria-hidden="true"
        className="ambient-glow glow-right"
      />
      <div
        aria-hidden="true"
        className="ambient-glow glow-bottom"
      />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-360 flex-col px-5 sm:px-8 lg:px-14">
        {/* Cabeçalho */}
        <header className="flex items-center justify-between border-b border-white/10 py-4 sm:py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-200/40 bg-cyan-200/5 text-[#a6faff]">
              <MedicalIcon />
            </div>

            <div>
              <p className="display-font text-2xl tracking-wider">
                MED<span className="text-[#a6faff]">GUIDE</span>
              </p>
              <p className="text-[9px] tracking-[0.2em] text-slate-400">
                MEDICAL GUIDELINES
              </p>
            </div>
          </div>

          <div className="hidden items-center gap-2 rounded-full border border-white/10 px-4 py-2 sm:flex">
            <span className="h-2 w-2 rounded-full bg-[#a6faff]" />
            <span className="text-[10px] tracking-[0.12em] text-slate-300">
              CONHECIMENTO EM SAÚDE
            </span>
          </div>
        </header>

        {/* Conteúdo principal */}
        <section className="grid flex-1 grid-cols-1 items-center gap-9 py-8 sm:gap-12 sm:py-10 lg:grid-cols-[1fr_460px] lg:gap-14 lg:py-10">
          {/* Apresentação do projeto */}
          <div className="max-w-2xl">
            <div className="mb-5 flex items-center gap-3 sm:mb-6">
              <span className="h-px w-10 bg-[#a6faff]" />
              <p className="text-xs font-bold tracking-[0.2em] text-[#a6faff]">
                INFORMAÇÃO CLÍNICA, SEM RUÍDO
              </p>
            </div>

            <h1 className="display-font max-w-xl text-5xl leading-[0.98] tracking-wide sm:text-6xl lg:text-7xl">
              A MEDICINA
              <br />
              <span className="text-[#a6faff]">
                NÃO PARA.
              </span>
              <br />
              MANTENHA-SE
              <br />
              ATUALIZADO.
            </h1>

            <p className="mt-5 max-w-lg text-sm leading-6 text-slate-300 sm:mt-6 sm:text-base sm:leading-7">
              Acompanhe diretrizes médicas, identifique
              atualizações relevantes e mantenha as
              informações de suas especialidades organizadas
              em um só lugar.
            </p>

            <div className="mt-7 grid max-w-lg grid-cols-3 gap-2 sm:mt-8 sm:gap-3">
              <div className="border-l-2 border-[#a6faff]/70 pl-2 sm:pl-3">
                <p className="text-[10px] font-bold text-white sm:text-xs">
                  FONTES
                </p>
                <p className="mt-1 text-[10px] text-slate-400 sm:text-xs">
                  Confiáveis
                </p>
              </div>

              <div className="border-l-2 border-[#a6faff]/70 pl-2 sm:pl-3">
                <p className="text-[10px] font-bold text-white sm:text-xs">
                  HISTÓRICO
                </p>
                <p className="mt-1 text-[10px] text-slate-400 sm:text-xs">
                  De versões
                </p>
              </div>

              <div className="border-l-2 border-[#a6faff]/70 pl-2 sm:pl-3">
                <p className="text-[10px] font-bold text-white sm:text-xs">
                  ATUALIZAÇÕES
                </p>
                <p className="mt-1 text-[10px] text-slate-400 sm:text-xs">
                  Organizadas
                </p>
              </div>
            </div>

            <div className="mt-8 hidden items-center gap-3 text-xs text-slate-500 lg:flex">
              <span className="h-px w-14 bg-slate-700" />
              TECNOLOGIA A SERVIÇO DO CONHECIMENTO MÉDICO
            </div>
          </div>

          {/* Cartão de login */}
          <div className="mx-auto w-full max-w-115">
            <div className="login-card rounded-2xl p-6 sm:p-8">
              <div className="mb-6">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-200/30 bg-cyan-200/5 text-[#a6faff]">
                  <MedicalIcon />
                </div>

                <p className="mb-2 text-xs font-bold tracking-[0.2em] text-[#a6faff]">
                  ACESSO À PLATAFORMA
                </p>

                <h2 className="text-3xl font-semibold tracking-tight">
                  Bem-vindo de volta.
                </h2>

                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Entre na sua conta para acompanhar
                  as atualizações das suas especialidades.
                </p>
              </div>

              {/* Formulário somente visual */}
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="email"
                    className="mb-2 block text-xs font-semibold text-slate-200"
                  >
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
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="password"
                    className="mb-2 block text-xs font-semibold text-slate-200"
                  >
                    Senha
                  </label>

                  <div className="field-shell text-slate-400">
                    <LockIcon />
                    <input
                      id="password"
                      type={isPasswordVisible ? 'text' : 'password'}
                      placeholder="Digite sua senha"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      aria-label={
                        isPasswordVisible ? 'Ocultar senha' : 'Mostrar senha'
                      }
                      aria-pressed={isPasswordVisible}
                      onClick={() => setIsPasswordVisible((visible) => !visible)}
                    >
                      <VisibilityIcon visible={isPasswordVisible} />
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  className="auth-button mt-2"
                >
                  ENTRAR NA PLATAFORMA
                  <ArrowIcon />
                </button>
              </div>

              <div className="my-7 h-px bg-white/10" />

              <p className="text-center text-xs leading-5 text-slate-400">
                Plataforma de acompanhamento de diretrizes
                médicas para estudantes e profissionais de saúde.
              </p>
            </div>

            <p className="mt-5 text-center text-[10px] tracking-wider text-slate-500">
              MEDGUIDE © 2026
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
