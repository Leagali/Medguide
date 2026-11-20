import type {
  Artifact,
  CatalogObservation,
  CollectionRun,
  Guideline,
  GuidelineVersion,
  IngestionJob,
  Metrics,
  Source,
} from './types'

// Em desenvolvimento, o Vite encaminha /api para o FastAPI e injeta o token de
// administração lido do .env (vite.config.ts). O token nunca chega ao navegador.

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'Não foi possível conectar à API. Verifique se o backend está em execução.')
  }
  if (!response.ok) {
    // 502/504 vêm do proxy do Vite quando o FastAPI não responde.
    if (response.status === 502 || response.status === 504) {
      throw new ApiError(
        response.status,
        'A API não está respondendo em http://127.0.0.1:8000. Suba o backend com "docker compose up -d" no Ubuntu/WSL e tente novamente.',
      )
    }
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Corpo sem JSON: mantém o statusText.
    }
    if (response.status === 401 || response.status === 503) {
      detail = `${detail}. Confira MEDGUIDE_ADMIN_TOKEN no .env e reinicie o npm run dev.`
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

const MAX_PAGE = 200

async function listAll<T>(path: string): Promise<T[]> {
  const items: T[] = []
  const separator = path.includes('?') ? '&' : '?'
  for (let offset = 0; ; offset += MAX_PAGE) {
    const page = await request<T[]>(`${path}${separator}limit=${MAX_PAGE}&offset=${offset}`)
    items.push(...page)
    if (page.length < MAX_PAGE) return items
  }
}

export const api = {
  sources: () => listAll<Source>('/sources'),
  updateSource: (id: string, patch: Partial<Pick<Source, 'enabled' | 'discovery_interval' | 'content_recheck_interval'>>) =>
    request<Source>(`/sources/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  discover: (id: string) =>
    request<{ run_id: string; published: boolean }>(`/sources/${id}/discover`, { method: 'POST' }),

  guidelines: () => listAll<Guideline>('/guidelines'),
  guideline: (id: string) => request<Guideline>(`/guidelines/${id}`),
  versions: (id: string) => request<GuidelineVersion[]>(`/guidelines/${id}/versions?limit=${MAX_PAGE}`),
  observations: (id: string, limit = 20) =>
    request<CatalogObservation[]>(`/guidelines/${id}/observations?limit=${limit}`),
  artifacts: (id: string) => request<Artifact[]>(`/guidelines/${id}/artifacts?limit=${MAX_PAGE}`),
  rawUrl: (artifactId: string) => `/api/artifacts/${artifactId}/raw`,

  runs: (limit = 20) => request<CollectionRun[]>(`/runs?limit=${limit}`),
  jobs: (status?: string, limit = 50) =>
    request<IngestionJob[]>(`/jobs?limit=${limit}${status ? `&status=${status}` : ''}`),
  retryJob: (id: string) =>
    request<{ job_id: string; published: boolean }>(`/jobs/${id}/retry`, { method: 'POST' }),
  metrics: () => request<Metrics>('/metrics'),
}
