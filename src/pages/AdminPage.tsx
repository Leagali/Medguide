import { useState } from 'react'
import { CheckIcon, CloseIcon, ExternalIcon, RefreshIcon } from '../components/Icons'
import { EmptyState, ErrorBox, PageHeader, ProvisionalNote, SpecialtyTag, Spinner, StatusPill } from '../components/ui'
import { api } from '../lib/api'
import { formatDate, formatDateTime, formatInterval, formatRelative } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { SUGGESTION_STATUS, pipelineStatus } from '../lib/labels'
import { suggestions, useLocalVersion } from '../lib/localBackend'
import { replaceQuery } from '../lib/router'
import { loadSources, sourceLabel } from '../lib/sources'
import type { Source, SourceSuggestion } from '../lib/types'

type Tab = 'fontes' | 'sugestoes' | 'coletas'

export function AdminPage({ query }: { query: URLSearchParams }) {
  useLocalVersion()
  const tab: Tab = query.get('aba') === 'sugestoes' ? 'sugestoes' : query.get('aba') === 'coletas' ? 'coletas' : 'fontes'
  const pending = suggestions.list().filter((item) => item.status === 'pending').length

  return (
    <>
      <PageHeader
        eyebrow="ADMINISTRAÇÃO"
        title="Fontes e coletas"
        description="Gerencie as fontes monitoradas, acompanhe o processamento dos documentos e analise as fontes sugeridas pelos usuários."
      />

      <div role="tablist" aria-label="Seções da administração" className="tabs mb-6">
        {(
          [
            ['fontes', 'Fontes monitoradas'],
            ['sugestoes', `Sugestões${pending ? ` (${pending})` : ''}`],
            ['coletas', 'Coletas e jobs'],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => replaceQuery('/admin', { aba: value === 'fontes' ? null : value })}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'fontes' && <SourcesTab />}
      {tab === 'sugestoes' && <SuggestionsTab />}
      {tab === 'coletas' && <RunsTab />}
    </>
  )
}

// ------------------------------------------------------------------ Fontes

function SourcesTab() {
  const [refresh, setRefresh] = useState(0)
  const data = useAsync(() => Promise.all([loadSources(refresh > 0), api.metrics()]), `admin-sources:${refresh}`)
  const reload = () => setRefresh((value) => value + 1)

  if (data.loading && !data.data) return <Spinner />
  if (data.error) return <ErrorBox error={data.error} onRetry={reload} />
  if (!data.data) return null
  const [sources, metrics] = data.data
  const jobs = metrics.jobs_by_status
  const totalJobs = Object.values(jobs).reduce((sum, count) => sum + count, 0)

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Metric label="Versões registradas" value={metrics.versions} />
        <Metric label="Originais arquivados" value={metrics.artifacts} />
        <Metric label="Jobs concluídos" value={jobs.COMPLETED ?? 0} total={totalJobs} />
        <Metric label="Na fila / processando" value={(jobs.PENDING ?? 0) + (jobs.PROCESSING ?? 0)} />
        <Metric label="Falhas / revisão" value={(jobs.FAILED ?? 0) + (jobs.NEEDS_REVIEW ?? 0)} alert />
      </dl>

      {sources.length === 0 ? (
        <EmptyState title="Nenhuma fonte cadastrada." />
      ) : (
        sources.map((source) => (
          <SourceCard
            key={source.id}
            source={source}
            lastSuccess={metrics.source_successes.find((item) => item.source_id === source.id)?.last_success_at}
            onChanged={reload}
          />
        ))
      )}
    </div>
  )
}

function Metric({ label, value, total, alert = false }: { label: string; value: number; total?: number; alert?: boolean }) {
  return (
    <div className="panel px-4 py-3">
      <dt className="text-[11px] tracking-wide text-slate-400">{label}</dt>
      <dd className={`mt-1 text-xl font-semibold ${alert && value > 0 ? 'text-rose-300' : ''}`}>
        {value.toLocaleString('pt-BR')}
        {total !== undefined && <span className="text-sm font-normal text-slate-400"> / {total.toLocaleString('pt-BR')}</span>}
      </dd>
    </div>
  )
}

function SourceCard({ source, lastSuccess, onChanged }: { source: Source; lastSuccess?: string; onChanged: () => void }) {
  const [discoveryHours, setDiscoveryHours] = useState(String(source.discovery_interval / 3600))
  const [recheckDays, setRecheckDays] = useState(String(source.content_recheck_interval / 86400))
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  async function run(label: string, action: () => Promise<unknown>, success: string) {
    setBusy(label)
    setMessage(null)
    try {
      await action()
      setMessage({ tone: 'ok', text: success })
      onChanged()
    } catch (error) {
      setMessage({ tone: 'error', text: (error as Error).message })
    } finally {
      setBusy(null)
    }
  }

  const discoverySeconds = Math.round(Number(discoveryHours) * 3600)
  const recheckSeconds = Math.round(Number(recheckDays) * 86400)
  const intervalsValid = discoverySeconds >= 60 && recheckSeconds >= 60
  const intervalsChanged = discoverySeconds !== source.discovery_interval || recheckSeconds !== source.content_recheck_interval

  return (
    <section className="panel p-4 sm:p-6" aria-labelledby={`source-${source.id}`}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id={`source-${source.id}`} className="text-lg font-semibold">
              {sourceLabel(source)}
            </h2>
            <StatusPill tone={source.enabled ? 'ok' : 'muted'}>{source.enabled ? 'Ativa' : 'Pausada'}</StatusPill>
          </div>
          <a href={source.base_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex max-w-full items-center gap-1 text-xs break-all text-slate-400 hover:text-accent">
            {source.base_url} <ExternalIcon size={12} />
          </a>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={busy !== null}
            onClick={() =>
              run('toggle', () => api.updateSource(source.id, { enabled: !source.enabled }), source.enabled ? 'Fonte pausada.' : 'Fonte reativada.')
            }
          >
            {source.enabled ? 'Pausar' : 'Reativar'}
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={busy !== null || !source.enabled}
            onClick={() =>
              run('discover', () => api.discover(source.id), 'Descoberta solicitada. Acompanhe em “Coletas e jobs”.')
            }
          >
            <RefreshIcon size={16} /> {busy === 'discover' ? 'Solicitando…' : 'Descobrir agora'}
          </button>
        </div>
      </div>

      <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs text-slate-400">Conector</dt>
          <dd className="font-mono text-slate-200">{source.connector_key}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Próxima descoberta</dt>
          <dd>{source.enabled ? `${formatDateTime(source.next_due_at)} (${formatRelative(source.next_due_at)})` : '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Última descoberta concluída</dt>
          <dd>{lastSuccess ? `${formatDateTime(lastSuccess)} (${formatRelative(lastSuccess)})` : 'Nunca'}</dd>
        </div>
      </dl>

      <form
        className="mt-5 flex flex-wrap items-end gap-3 border-t border-white/10 pt-5"
        onSubmit={(event) => {
          event.preventDefault()
          run(
            'intervals',
            () => api.updateSource(source.id, { discovery_interval: discoverySeconds, content_recheck_interval: recheckSeconds }),
            'Intervalos atualizados.',
          )
        }}
      >
        <label className="text-xs text-slate-400">
          Descobrir a cada (horas)
          <input className="input mt-1 w-36" type="number" min={0.1} step="any" value={discoveryHours} onChange={(event) => setDiscoveryHours(event.target.value)} />
        </label>
        <label className="text-xs text-slate-400">
          Reverificar conteúdo a cada (dias)
          <input className="input mt-1 w-36" type="number" min={0.01} step="any" value={recheckDays} onChange={(event) => setRecheckDays(event.target.value)} />
        </label>
        <button type="submit" className="btn-secondary" disabled={busy !== null || !intervalsValid || !intervalsChanged}>
          Salvar intervalos
        </button>
        <p className="w-full text-xs text-slate-500">
          Atual: descoberta a cada {formatInterval(source.discovery_interval)}, reverificação a cada{' '}
          {formatInterval(source.content_recheck_interval)}.
        </p>
      </form>

      {message && (
        <p role="status" className={`mt-3 text-sm ${message.tone === 'ok' ? 'text-emerald-300' : 'text-rose-300'}`}>
          {message.text}
        </p>
      )}
    </section>
  )
}

// --------------------------------------------------------------- Sugestões

function SuggestionsTab() {
  const all = suggestions.list()
  const pending = all.filter((item) => item.status === 'pending')
  const reviewed = all.filter((item) => item.status !== 'pending')

  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 font-semibold">Aguardando análise ({pending.length})</h2>
        {pending.length === 0 ? (
          <EmptyState title="Nenhuma sugestão pendente.">
            As sugestões enviadas pelos usuários em “Sugerir fonte” aparecem aqui.
          </EmptyState>
        ) : (
          <ul className="space-y-3">
            {pending.map((item) => (
              <PendingSuggestion key={item.id} suggestion={item} />
            ))}
          </ul>
        )}
      </section>

      {reviewed.length > 0 && (
        <section>
          <h2 className="mb-3 font-semibold">Já analisadas</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fonte</th>
                  <th>Sugerida por</th>
                  <th>Decisão</th>
                  <th>Analisada em</th>
                  <th>Observação</th>
                </tr>
              </thead>
              <tbody>
                {reviewed.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <a href={item.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                        {item.name}
                      </a>
                    </td>
                    <td>{item.suggestedBy.name}</td>
                    <td>
                      <StatusPill tone={SUGGESTION_STATUS[item.status].tone}>{SUGGESTION_STATUS[item.status].label}</StatusPill>
                    </td>
                    <td>{formatDate(item.reviewedAt)}</td>
                    <td className="max-w-xs">{item.reviewNote ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <ProvisionalNote>
        aprovar registra a decisão e avisa quem sugeriu. Para a fonte entrar no monitoramento, ainda é
        preciso desenvolver e homologar um conector para ela no backend; a API só aceita fontes com
        conector homologado.
      </ProvisionalNote>
    </div>
  )
}

function PendingSuggestion({ suggestion }: { suggestion: SourceSuggestion }) {
  const [note, setNote] = useState('')
  const [deciding, setDeciding] = useState<'approved' | 'rejected' | null>(null)

  return (
    <li className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-lg font-semibold">{suggestion.name}</p>
          <p className="text-sm text-slate-400">{suggestion.organization}</p>
        </div>
        <p className="text-xs text-slate-400">
          {suggestion.suggestedBy.name} · {formatRelative(suggestion.createdAt)}
        </p>
      </div>
      <a href={suggestion.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex max-w-full items-center gap-1 text-sm break-all text-accent hover:underline">
        {suggestion.url} <ExternalIcon size={12} />
      </a>
      <p className="mt-3 text-sm leading-6 text-slate-300">{suggestion.justification}</p>
      {suggestion.specialties.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {suggestion.specialties.map((id) => (
            <SpecialtyTag key={id} id={id} />
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-col gap-2 border-t border-white/10 pt-4 sm:flex-row sm:items-center">
        <input
          className="input flex-1"
          aria-label={`Observação para ${suggestion.name}`}
          placeholder="Observação para quem sugeriu (obrigatória ao recusar)"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-danger"
            disabled={deciding !== null || note.trim().length < 3}
            title={note.trim().length < 3 ? 'Explique o motivo da recusa' : undefined}
            onClick={async () => {
              setDeciding('rejected')
              await suggestions.review(suggestion.id, 'rejected', note)
            }}
          >
            <CloseIcon size={16} /> Recusar
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={deciding !== null}
            onClick={async () => {
              setDeciding('approved')
              await suggestions.review(suggestion.id, 'approved', note)
            }}
          >
            <CheckIcon size={16} /> Aprovar
          </button>
        </div>
      </div>
    </li>
  )
}

// ----------------------------------------------------------------- Coletas

function RunsTab() {
  const [refresh, setRefresh] = useState(0)
  const data = useAsync(
    () => Promise.all([api.runs(15), api.jobs('FAILED', 50), api.jobs('NEEDS_REVIEW', 50), api.jobs(undefined, 15), loadSources()]),
    `admin-runs:${refresh}`,
  )
  const [retrying, setRetrying] = useState<string | null>(null)
  const [retryError, setRetryError] = useState<string | null>(null)
  const reload = () => setRefresh((value) => value + 1)

  if (data.loading && !data.data) return <Spinner />
  if (data.error) return <ErrorBox error={data.error} onRetry={reload} />
  if (!data.data) return null
  const [runs, failed, review, recent, sources] = data.data
  const attention = [...failed, ...review]
  const sourceById = new Map(sources.map((source) => [source.id, source]))

  return (
    <div className="space-y-8">
      <div className="flex justify-end">
        <button type="button" className="btn-secondary" onClick={reload} disabled={data.loading}>
          <RefreshIcon size={16} /> Atualizar
        </button>
      </div>

      <section>
        <h2 className="mb-3 font-semibold">Jobs que precisam de atenção ({attention.length})</h2>
        {retryError && <p role="alert" className="mb-3 text-sm text-rose-300">{retryError}</p>}
        {attention.length === 0 ? (
          <EmptyState title="Nenhum job com falha ou em revisão." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Situação</th>
                  <th>Etapa</th>
                  <th>Tentativas</th>
                  <th>Erro</th>
                  <th>Criado em</th>
                  <th><span className="sr-only">Ações</span></th>
                </tr>
              </thead>
              <tbody>
                {attention.map((job) => (
                  <tr key={job.id}>
                    <td><StatusPill tone={pipelineStatus(job.status).tone}>{pipelineStatus(job.status).label}</StatusPill></td>
                    <td>{job.stage ?? '—'}</td>
                    <td>{job.attempt_count}</td>
                    <td className="max-w-sm text-xs">{job.last_error ?? job.result ?? '—'}</td>
                    <td>{formatDateTime(job.created_at)}</td>
                    <td className="whitespace-nowrap">
                      <a className="text-accent hover:underline" href={`#/diretrizes/${job.guideline_id}`}>Diretriz</a>
                      {' · '}
                      <button
                        type="button"
                        className="text-accent hover:underline disabled:opacity-50"
                        disabled={retrying !== null}
                        onClick={async () => {
                          setRetrying(job.id)
                          setRetryError(null)
                          try {
                            await api.retryJob(job.id)
                            reload()
                          } catch (error) {
                            setRetryError((error as Error).message)
                          } finally {
                            setRetrying(null)
                          }
                        }}
                      >
                        {retrying === job.id ? 'Reenviando…' : 'Tentar de novo'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-semibold">Descobertas recentes</h2>
        {runs.length === 0 ? (
          <EmptyState title="Nenhuma descoberta executada." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Início</th>
                  <th>Fonte</th>
                  <th>Situação</th>
                  <th>Encontradas</th>
                  <th>Jobs criados</th>
                  <th>Duração</th>
                  <th>Erro</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>{formatDateTime(run.started_at)}</td>
                    <td>{sourceLabel(sourceById.get(run.source_id))}</td>
                    <td><StatusPill tone={pipelineStatus(run.status).tone}>{pipelineStatus(run.status).label}</StatusPill></td>
                    <td>{run.found_count}</td>
                    <td>{run.queued_count}</td>
                    <td>{run.finished_at ? duration(run.started_at, run.finished_at) : '—'}</td>
                    <td className="max-w-xs text-xs">{run.error_summary ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-semibold">Últimos jobs de ingestão</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Criado em</th>
                <th>Situação</th>
                <th>Resultado</th>
                <th>Tentativas</th>
                <th>Concluído em</th>
                <th><span className="sr-only">Diretriz</span></th>
              </tr>
            </thead>
            <tbody>
              {recent.map((job) => (
                <tr key={job.id}>
                  <td>{formatDateTime(job.created_at)}</td>
                  <td><StatusPill tone={pipelineStatus(job.status).tone}>{pipelineStatus(job.status).label}</StatusPill></td>
                  <td className="font-mono text-xs">{job.result ?? '—'}</td>
                  <td>{job.attempt_count}</td>
                  <td>{formatDateTime(job.finished_at)}</td>
                  <td><a className="text-accent hover:underline" href={`#/diretrizes/${job.guideline_id}`}>Diretriz</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function duration(start: string, end: string) {
  const seconds = Math.max(0, (new Date(end).getTime() - new Date(start).getTime()) / 1000)
  if (seconds < 60) return `${Math.round(seconds)} s`
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}
