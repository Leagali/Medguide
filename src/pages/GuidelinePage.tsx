import { Fragment, useEffect, useMemo, useState } from 'react'
import { BackIcon, DownloadIcon, ExternalIcon, SearchIcon } from '../components/Icons'
import { EmptyState, ErrorBox, SpecialtyTag, Spinner, StatusPill } from '../components/ui'
import { api } from '../lib/api'
import { foldSameLength, formatBytes, formatDate, formatDateTime, normalize, plural, shortHash } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { notifications } from '../lib/localBackend'
import { replaceQuery } from '../lib/router'
import { loadSources, sourceLabel } from '../lib/sources'
import { classifyGuideline } from '../lib/specialties'
import { compareVersions, splitPages } from '../lib/text'
import type { Artifact, CatalogObservation, GuidelineVersion, User } from '../lib/types'

type Tab = 'texto' | 'versoes' | 'rastreabilidade'

export function GuidelinePage({ id, user, query }: { id: string; user: User; query: URLSearchParams }) {
  const detail = useAsync(
    () =>
      Promise.all([api.guideline(id), api.versions(id), api.observations(id), api.artifacts(id), loadSources()]),
    `guideline:${id}`,
  )

  // Abrir a diretriz conta como leitura dos avisos sobre ela.
  useEffect(() => {
    notifications
      .list(user.id)
      .filter((item) => item.guidelineId === id && !item.read)
      .forEach((item) => notifications.markRead(user.id, item.id))
  }, [id, user.id])

  const tab: Tab = query.get('aba') === 'versoes' ? 'versoes' : query.get('aba') === 'rastreabilidade' ? 'rastreabilidade' : 'texto'
  const versionParam = query.get('versao')
  const setQuery = (next: Record<string, string | null>) =>
    replaceQuery(`/diretrizes/${id}`, { aba: tab === 'texto' ? null : tab, versao: versionParam, ...next })

  if (detail.loading && !detail.data) return <Spinner label="Carregando diretriz…" />
  if (detail.error) {
    return (
      <>
        <BackLink />
        <ErrorBox error={detail.error} onRetry={detail.reload} />
      </>
    )
  }
  if (!detail.data) return null

  const [guideline, versions, observations, artifacts, sources] = detail.data
  const specialties = classifyGuideline(guideline.title)
  const latest = observations[0]
  const metadata = latest?.source_metadata_json
  const current = versions.find((version) => version.id === guideline.current_version_id) ?? versions[0]
  const selected = versions.find((version) => version.id === versionParam) ?? current
  const mainRef = metadata?.document_refs?.find((ref) => ref.role === 'main') ?? metadata?.document_refs?.[0]
  const mainArtifact = artifacts.find((artifact) => artifact.role === 'main') ?? artifacts[0]
  const source = sources.find((item) => item.id === guideline.source_id)

  return (
    <>
      <BackLink />

      <header className="mb-6">
        <div className="flex flex-wrap items-center gap-2 text-xs tracking-wide text-slate-400">
          <span className="font-bold text-slate-300">{sourceLabel(source)}</span>
          {current ? (
            <StatusPill tone="ok">Versão observada {current.observed_version}</StatusPill>
          ) : (
            <StatusPill tone="warn">Aguardando processamento</StatusPill>
          )}
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-balance sm:text-4xl">{guideline.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          {specialties.map((specialty) => (
            <SpecialtyTag key={specialty} id={specialty} />
          ))}
        </div>

        <dl className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Meta label="Publicação oficial" value={formatDate(metadata?.publication_date)} />
          <Meta label="Alteração informada" value={formatDate(metadata?.change_date)} />
          <Meta label="Versão detectada em" value={formatDateTime(current?.detected_at)} />
          <Meta label="Última verificação" value={formatDateTime(guideline.last_checked_at)} />
        </dl>

        {metadata?.source_metadata?.catalog_row && (
          <p className="mt-4 rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3 text-sm leading-6 text-slate-300">
            <span className="mr-2 text-[11px] font-bold tracking-wider text-slate-400">NO CATÁLOGO</span>
            {metadata.source_metadata.catalog_row}
          </p>
        )}
        {metadata?.source_change_note && (
          <p className="mt-3 text-sm text-slate-300">
            <strong>Nota da fonte:</strong> {metadata.source_change_note}
          </p>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          {mainRef && (
            <a className="btn-primary" href={mainRef.source_url} target="_blank" rel="noreferrer">
              <ExternalIcon size={16} /> Documento oficial
            </a>
          )}
          {mainArtifact && (
            <a className="btn-secondary" href={api.rawUrl(mainArtifact.id)} download={downloadName(guideline.title, mainArtifact)}>
              <DownloadIcon size={16} /> Original arquivado ({formatBytes(mainArtifact.size_bytes)})
            </a>
          )}
          <a className="btn-secondary" href={guideline.catalog_url} target="_blank" rel="noreferrer">
            <ExternalIcon size={16} /> Página do catálogo
          </a>
        </div>
      </header>

      <div role="tablist" aria-label="Seções da diretriz" className="tabs mb-5">
        {(
          [
            ['texto', 'Texto'],
            ['versoes', `Histórico de versões (${versions.length})`],
            ['rastreabilidade', 'Rastreabilidade'],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => setQuery({ aba: value === 'texto' ? null : value })}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'texto' &&
        (selected ? (
          <TextReader version={selected} isCurrent={selected.id === current?.id} onShowCurrent={() => setQuery({ versao: null })} />
        ) : (
          <EmptyState title="O texto ainda não foi extraído.">
            A diretriz já foi encontrada no catálogo e está na fila de processamento. Volte em alguns minutos.
          </EmptyState>
        ))}

      {tab === 'versoes' && (
        <VersionHistory
          versions={versions}
          currentId={current?.id}
          onRead={(versionId) => setQuery({ aba: null, versao: versionId === current?.id ? null : versionId })}
        />
      )}

      {tab === 'rastreabilidade' && <Traceability observations={observations} artifacts={artifacts} title={guideline.title} />}
    </>
  )
}

function BackLink() {
  return (
    <button type="button" onClick={() => history.back()} className="mb-5 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-accent">
      <BackIcon size={16} /> Voltar
    </button>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel px-4 py-3">
      <dt className="text-[11px] tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}

function downloadName(title: string, artifact: Artifact) {
  const slug = normalize(title).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80)
  const extension = artifact.media_type === 'application/pdf' ? 'pdf' : artifact.media_type.includes('html') ? 'html' : 'bin'
  return `${slug || artifact.id}.${extension}`
}

// ------------------------------------------------------------------- Texto

function TextReader({
  version,
  isCurrent,
  onShowCurrent,
}: {
  version: GuidelineVersion
  isCurrent: boolean
  onShowCurrent: () => void
}) {
  const [term, setTerm] = useState('')
  const pages = useMemo(() => splitPages(version.extracted_text), [version.extracted_text])
  const normalizedTerm = normalize(term.trim())
  const matches = useMemo(
    () => (normalizedTerm.length >= 2 ? pages.filter((page) => normalize(page.text).includes(normalizedTerm)) : pages),
    [pages, normalizedTerm],
  )
  const multipleRefs = new Set(pages.map((page) => page.reference)).size > 1

  return (
    <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
      <aside className="lg:sticky lg:top-24 lg:self-start">
        <div className="field-shell min-h-11 text-slate-400">
          <SearchIcon size={18} />
          <input type="search" aria-label="Buscar no texto" placeholder="Buscar no texto" value={term} onChange={(event) => setTerm(event.target.value)} />
        </div>
        <p className="mt-2 text-xs text-slate-400" aria-live="polite">
          {normalizedTerm.length >= 2
            ? `${plural(matches.length, 'página', 'páginas')} com “${term.trim()}”`
            : plural(pages.length, 'página', 'páginas')}
        </p>
        <nav aria-label="Páginas" className="mt-3 hidden max-h-[60vh] flex-wrap gap-1 overflow-y-auto lg:flex">
          {matches.map((page) => (
            <a key={`${page.reference}-${page.page}`} href={`#p-${page.reference}-${page.page}`} onClick={(event) => {
              event.preventDefault()
              document.getElementById(`p-${page.reference}-${page.page}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }} className="page-chip">
              {multipleRefs ? `${page.reference}·` : ''}
              {page.page || '—'}
            </a>
          ))}
        </nav>
      </aside>

      <div className="min-w-0">
        {!isCurrent && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-300/25 bg-amber-300/5 px-4 py-3 text-sm text-amber-100">
            <span>
              Você está lendo a versão observada {version.observed_version}, que não é a atual.
            </span>
            <button type="button" className="btn-secondary" onClick={onShowCurrent}>
              Ver versão atual
            </button>
          </div>
        )}
        <p className="mb-4 text-xs leading-5 text-slate-500">
          Texto extraído automaticamente do documento oficial ({version.extractor_version}). Tabelas e
          figuras podem perder a formatação; confira o original para doses e esquemas.
        </p>
        {matches.length === 0 ? (
          <EmptyState title="Nenhuma página contém esse termo." />
        ) : (
          <div className="space-y-4">
            {matches.map((page) => (
              <section
                key={`${page.reference}-${page.page}`}
                id={`p-${page.reference}-${page.page}`}
                className="panel scroll-mt-28 p-4 sm:p-6"
                aria-label={`Página ${page.page}`}
              >
                <p className="mb-3 text-[11px] font-bold tracking-wider text-slate-500">
                  {multipleRefs && `${page.reference.toUpperCase()} · `}PÁGINA {page.page || '—'}
                </p>
                <div className="reader-text">
                  <Highlighted text={page.text} term={normalizedTerm.length >= 2 ? term.trim() : ''} />
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Highlighted({ text, term }: { text: string; term: string }) {
  if (!term) return <>{text}</>
  // Busca sem acento, com posições equivalentes às do texto original.
  const plain = foldSameLength(text)
  const needle = foldSameLength(term)
  const parts: { text: string; hit: boolean }[] = []
  let cursor = 0
  for (let index = plain.indexOf(needle); index !== -1; index = plain.indexOf(needle, index + needle.length)) {
    if (index > cursor) parts.push({ text: text.slice(cursor, index), hit: false })
    parts.push({ text: text.slice(index, index + needle.length), hit: true })
    cursor = index + needle.length
  }
  parts.push({ text: text.slice(cursor), hit: false })
  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>{part.hit ? <mark>{part.text}</mark> : part.text}</Fragment>
      ))}
    </>
  )
}

// ---------------------------------------------------------------- Versões

function VersionHistory({
  versions,
  currentId,
  onRead,
}: {
  versions: GuidelineVersion[]
  currentId: string | undefined
  onRead: (versionId: string) => void
}) {
  const [compareFrom, setCompareFrom] = useState(versions[1]?.id ?? '')
  const [compareTo, setCompareTo] = useState(versions[0]?.id ?? '')

  if (versions.length === 0) {
    return <EmptyState title="Nenhuma versão registrada ainda." />
  }

  const older = versions.find((version) => version.id === compareFrom)
  const newer = versions.find((version) => version.id === compareTo)

  return (
    <div className="space-y-6">
      <p className="text-sm leading-6 text-slate-400">
        Cada vez que o conteúdo do documento oficial muda, o MedGuide registra uma nova versão observada,
        preservando as anteriores. A numeração é a sequência detectada pelo coletor, não a edição oficial.
      </p>

      <ol className="timeline">
        {versions.map((version) => (
          <li key={version.id}>
            <div className="panel p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold">Versão observada {version.observed_version}</p>
                {version.id === currentId && <StatusPill tone="ok">Atual</StatusPill>}
                <span className="text-sm text-slate-400">· detectada em {formatDateTime(version.detected_at)}</span>
                <button type="button" className="btn-secondary ml-auto" onClick={() => onRead(version.id)}>
                  Ler esta versão
                </button>
              </div>
              <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs text-slate-400 sm:grid-cols-3">
                <div>
                  <dt className="inline">Hash do conteúdo: </dt>
                  <dd className="inline font-mono text-slate-300" title={version.composite_content_sha256}>
                    {shortHash(version.composite_content_sha256)}
                  </dd>
                </div>
                <div>
                  <dt className="inline">Extração: </dt>
                  <dd className="inline text-slate-300">{version.extractor_version}</dd>
                </div>
                <div>
                  <dt className="inline">Tamanho: </dt>
                  <dd className="inline text-slate-300">{version.extracted_text.length.toLocaleString('pt-BR')} caracteres</dd>
                </div>
              </dl>
            </div>
          </li>
        ))}
      </ol>

      <section className="panel p-4 sm:p-5">
        <h2 className="font-semibold">Comparar versões</h2>
        {versions.length < 2 ? (
          <p className="mt-2 text-sm text-slate-400">
            Só existe uma versão observada até agora. A comparação aparece quando o documento oficial mudar.
          </p>
        ) : (
          <>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <select className="select" aria-label="Versão anterior" value={compareFrom} onChange={(event) => setCompareFrom(event.target.value)}>
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>Versão {version.observed_version}</option>
                ))}
              </select>
              <span className="text-slate-400">→</span>
              <select className="select" aria-label="Versão posterior" value={compareTo} onChange={(event) => setCompareTo(event.target.value)}>
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>Versão {version.observed_version}</option>
                ))}
              </select>
            </div>
            {older && newer && older.id !== newer.id && <VersionDiff older={older} newer={newer} />}
          </>
        )}
      </section>
    </div>
  )
}

const DIFF_LIMIT = 150

function VersionDiff({ older, newer }: { older: GuidelineVersion; newer: GuidelineVersion }) {
  const diff = useMemo(() => compareVersions(older.extracted_text, newer.extracted_text), [older, newer])
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      {(
        [
          ['Trechos novos', diff.added, 'diff-added'],
          ['Trechos removidos', diff.removed, 'diff-removed'],
        ] as const
      ).map(([label, lines, tone]) => (
        <div key={label}>
          <p className="mb-2 text-sm font-semibold">
            {label} <span className="font-normal text-slate-400">({lines.length.toLocaleString('pt-BR')} linhas)</span>
          </p>
          <div className={`diff ${tone}`}>
            {lines.length === 0 ? (
              <p className="text-slate-400">Nenhum.</p>
            ) : (
              lines.slice(0, DIFF_LIMIT).map((line, index) => <p key={index}>{line}</p>)
            )}
            {lines.length > DIFF_LIMIT && <p className="text-slate-400">… e mais {lines.length - DIFF_LIMIT} linhas.</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

// --------------------------------------------------------- Rastreabilidade

function Traceability({
  observations,
  artifacts,
  title,
}: {
  observations: CatalogObservation[]
  artifacts: Artifact[]
  title: string
}) {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-1 font-semibold">Originais arquivados</h2>
        <p className="mb-3 text-sm text-slate-400">
          Cada documento baixado fica guardado com seu hash SHA-256, permitindo provar exatamente o que foi lido.
        </p>
        {artifacts.length === 0 ? (
          <EmptyState title="Nenhum original baixado ainda." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Papel</th>
                  <th>Baixado em</th>
                  <th>Tipo</th>
                  <th>Tamanho</th>
                  <th>Páginas</th>
                  <th>SHA-256</th>
                  <th>Extração</th>
                  <th><span className="sr-only">Ações</span></th>
                </tr>
              </thead>
              <tbody>
                {artifacts.map((artifact) => (
                  <tr key={artifact.id}>
                    <td>{artifact.role === 'main' ? 'Principal' : artifact.role}</td>
                    <td>{formatDateTime(artifact.fetched_at)}</td>
                    <td>{artifact.media_type.replace('application/', '')}</td>
                    <td>{formatBytes(artifact.size_bytes)}</td>
                    <td>{artifact.pages_json?.length ?? '—'}</td>
                    <td className="font-mono" title={artifact.raw_sha256}>{shortHash(artifact.raw_sha256)}</td>
                    <td>
                      <StatusPill tone={artifact.extraction_status === 'EXTRACTED' ? 'ok' : 'warn'}>
                        {artifact.extraction_status === 'EXTRACTED' ? 'Extraído' : artifact.extraction_status}
                      </StatusPill>
                    </td>
                    <td className="whitespace-nowrap">
                      <a className="text-accent hover:underline" href={api.rawUrl(artifact.id)} download={downloadName(title, artifact)}>
                        Baixar
                      </a>
                      {' · '}
                      <a className="text-accent hover:underline" href={artifact.source_url} target="_blank" rel="noreferrer">
                        Origem
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Observações no catálogo</h2>
        <p className="mb-3 text-sm text-slate-400">
          Cada vez que o coletor visita o catálogo oficial, registra o que viu, mesmo sem mudanças.
        </p>
        {observations.length === 0 ? (
          <EmptyState title="Nenhuma observação registrada." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Observado em</th>
                  <th>Publicação</th>
                  <th>Alteração</th>
                  <th>Documentos</th>
                  <th>Impressão digital</th>
                  <th>Coleta</th>
                </tr>
              </thead>
              <tbody>
                {observations.map((observation) => (
                  <tr key={observation.id}>
                    <td>{formatDateTime(observation.observed_at)}</td>
                    <td>{formatDate(observation.source_metadata_json.publication_date)}</td>
                    <td>{formatDate(observation.source_metadata_json.change_date)}</td>
                    <td>{observation.source_metadata_json.document_refs?.length ?? 0}</td>
                    <td className="font-mono" title={observation.fingerprint}>{shortHash(observation.fingerprint)}</td>
                    <td className="font-mono" title={observation.run_id}>{observation.run_id.slice(0, 8)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
