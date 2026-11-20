import type { SuggestionStatus } from './types'

type Tone = 'ok' | 'warn' | 'error' | 'muted' | 'info'

export const SUGGESTION_STATUS: Record<SuggestionStatus, { label: string; tone: Tone }> = {
  pending: { label: 'Em análise', tone: 'warn' },
  approved: { label: 'Aprovada', tone: 'ok' },
  rejected: { label: 'Não aprovada', tone: 'error' },
}

const PIPELINE_STATUS: Record<string, { label: string; tone: Tone }> = {
  PENDING: { label: 'Pendente', tone: 'muted' },
  RUNNING: { label: 'Em execução', tone: 'info' },
  PROCESSING: { label: 'Em processamento', tone: 'info' },
  COMPLETED: { label: 'Concluído', tone: 'ok' },
  FAILED: { label: 'Falhou', tone: 'error' },
  NEEDS_REVIEW: { label: 'Para revisão', tone: 'warn' },
}

export function pipelineStatus(status: string) {
  return PIPELINE_STATUS[status] ?? { label: status, tone: 'muted' as Tone }
}
