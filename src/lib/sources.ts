import { api } from './api'
import type { Source } from './types'

const LABELS: Record<string, { name: string; organization: string }> = {
  conitec_pcdt: { name: 'PCDT', organization: 'CONITEC' },
}

export function sourceLabel(source: Pick<Source, 'code'> | undefined) {
  if (!source) return 'Fonte oficial'
  const known = LABELS[source.code]
  return known ? `${known.organization} · ${known.name}` : source.code
}

let sourcesPromise: Promise<Source[]> | null = null

export function loadSources(force = false) {
  if (!sourcesPromise || force) {
    sourcesPromise = api.sources()
    sourcesPromise.catch(() => {
      sourcesPromise = null
    })
  }
  return sourcesPromise
}
