// Formatos devolvidos pela API FastAPI (src/medguide/api/app.py).

export type Source = {
  id: string
  code: string
  connector_key: string
  base_url: string
  enabled: boolean
  discovery_interval: number
  content_recheck_interval: number
  next_due_at: string
}

export type Guideline = {
  id: string
  source_id: string
  external_key: string
  title: string
  catalog_url: string
  last_seen_at: string
  last_checked_at: string | null
  current_version_id: string | null
}

export type GuidelineVersion = {
  id: string
  guideline_id: string
  observed_version: number
  composite_content_sha256: string
  extracted_text: string
  extractor_version: string
  normalizer_version: string
  detected_at: string
}

export type DocumentRef = {
  reference_key: string
  role: string
  source_url: string
  media_hint?: string | null
}

export type CatalogObservation = {
  id: string
  guideline_id: string
  run_id: string
  fingerprint: string
  observed_at: string
  source_metadata_json: {
    title?: string
    catalog_url?: string
    publication_date?: string | null
    change_date?: string | null
    source_change_note?: string | null
    source_metadata?: { catalog_title?: string; catalog_row?: string }
    document_refs?: DocumentRef[]
  }
}

export type Artifact = {
  id: string
  guideline_id: string
  job_id: string
  reference_key: string
  role: string
  source_url: string
  raw_sha256: string
  content_sha256: string | null
  media_type: string
  fetched_at: string
  size_bytes: number
  extraction_status: string
  pages_json: { page_number: number; text: string }[] | null
  extractor_version: string | null
}

export type CollectionRun = {
  id: string
  source_id: string
  status: string
  started_at: string
  finished_at: string | null
  attempt_count: number
  found_count: number
  queued_count: number
  error_summary: string | null
  connector_version: string
}

export type IngestionJob = {
  id: string
  guideline_id: string
  status: string
  attempt_count: number
  last_error: string | null
  stage: string | null
  result: string | null
  created_at: string
  finished_at: string | null
}

export type Metrics = {
  jobs_by_status: Record<string, number>
  failures_by_stage: { stage: string; count: number }[]
  versions: number
  artifacts: number
  source_successes: { source_id: string; last_success_at: string }[]
}

// Formatos da camada local provisória (src/lib/localBackend.ts). Representam o
// contrato esperado dos endpoints que o backend ainda não implementa.

export type UserRole = 'user' | 'admin'
export type UserProfile = 'medico' | 'estudante' | 'outro'

export type User = {
  id: string
  name: string
  email: string
  profile: UserProfile
  role: UserRole
  specialties: string[]
  createdAt: string
}

export type NotificationKind =
  | 'welcome'
  | 'new_guideline'
  | 'new_version'
  | 'suggestion_received'
  | 'suggestion_approved'
  | 'suggestion_rejected'

export type AppNotification = {
  id: string
  kind: NotificationKind
  title: string
  body: string
  createdAt: string
  read: boolean
  guidelineId?: string
}

export type SuggestionStatus = 'pending' | 'approved' | 'rejected'

export type SourceSuggestion = {
  id: string
  name: string
  url: string
  organization: string
  specialties: string[]
  justification: string
  status: SuggestionStatus
  reviewNote: string | null
  suggestedBy: { id: string; name: string; email: string }
  createdAt: string
  reviewedAt: string | null
}
