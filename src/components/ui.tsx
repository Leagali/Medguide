import type { ReactNode } from 'react'
import { MedicalIcon } from './Icons'
import { specialtyName } from '../lib/specialties'

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex items-center justify-center rounded-xl border border-cyan-200/40 bg-cyan-200/5 text-accent ${
          compact ? 'h-9 w-9' : 'h-11 w-11'
        }`}
      >
        <MedicalIcon size={compact ? 22 : 28} />
      </div>
      <div>
        <p className={`display-font tracking-wider ${compact ? 'text-xl' : 'text-2xl'}`}>
          MED<span className="text-accent">GUIDE</span>
        </p>
        {!compact && <p className="text-[9px] tracking-[0.2em] text-slate-400">MEDICAL GUIDELINES</p>}
      </div>
    </div>
  )
}

export function Backdrop() {
  return (
    <>
      <div aria-hidden="true" className="background-grid pointer-events-none fixed inset-0 -z-10" />
      <div aria-hidden="true" className="ambient-glow glow-left -z-10" />
      <div aria-hidden="true" className="ambient-glow glow-right -z-10" />
    </>
  )
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <span className="h-px w-8 bg-accent" />
      <p className="text-[11px] font-bold tracking-[0.2em] text-accent">{children}</p>
    </div>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function SpecialtyTag({ id }: { id: string }) {
  return <span className="tag">{specialtyName(id)}</span>
}

export function StatusPill({ tone, children }: { tone: 'ok' | 'warn' | 'error' | 'muted' | 'info'; children: ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>
}

export function Spinner({ label = 'Carregando…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 py-10 text-sm text-slate-400">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-rose-400/30 bg-rose-400/5 p-4 text-sm text-rose-100">
      <p className="font-semibold">Não foi possível carregar os dados.</p>
      <p className="mt-1 text-rose-200/80">{error.message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary mt-3" onClick={onRetry}>
          Tentar novamente
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="panel px-6 py-10 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-400">{children}</div>}
    </div>
  )
}

export function ProvisionalNote({ children }: { children: ReactNode }) {
  return (
    <p className="mt-6 rounded-lg border border-amber-300/20 bg-amber-300/5 px-3 py-2 text-xs leading-5 text-amber-100/80">
      <strong className="font-semibold text-amber-100">Provisório:</strong> {children}
    </p>
  )
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string
  htmlFor: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block text-xs font-semibold text-slate-200">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}
