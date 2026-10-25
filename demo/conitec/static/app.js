/* Interface descartável exclusiva para o vídeo. Nenhum resultado é simulado. */
"use strict";
const $ = (id) => document.getElementById(id);
const number = (value) => new Intl.NumberFormat("pt-BR").format(value);
const labels = {PENDING:"Pendente",PROCESSING:"Em processamento",COMPLETED:"Concluído",FAILED:"Falha",NEEDS_REVIEW:"Para revisão"};
let snapshot = null, selectedId = null, detail = null, filter = "all", pageIndex = 0, documentIndex = 0;
let readingMode = "pages", refreshBusy = false, ticket = 0, sampleId = null, sampleRunning = false, fontSize = 16;

function date(value) {
  if (!value) return "Não informado";
  const aware = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + "Z";
  return new Date(aware).toLocaleString("pt-BR", {dateStyle:"short", timeStyle:"short"});
}
function text(id, value) { $(id).textContent = value; }
function node(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== undefined) element.textContent = value;
  return element;
}
function toast(message) {
  text("toast", message); $("toast").hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => $("toast").hidden = true, 6500);
}
async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options, headers:{"X-MedGuide-Demo":"1","Content-Type":"application/json",...options.headers},
    cache:"no-store",
  });
  let payload;
  try { payload = await response.json(); } catch { throw new Error("Resposta indisponível. Confira os serviços locais."); }
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Não foi possível concluir a operação.");
  return payload;
}
function error(message) { text("errorBanner", message); $("errorBanner").hidden = false; }
function normalized(value) { return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }

function renderList() {
  if (!snapshot) return;
  const query = normalized($("search").value);
  const visible = snapshot.guidelines.filter(item => {
    if (!normalized(item.title).includes(query)) return false;
    if (filter === "text") return Boolean(item.current_version_id);
    if (filter === "pending") return ["PENDING","PROCESSING"].includes(item.job?.status);
    if (filter === "review") return ["FAILED","NEEDS_REVIEW"].includes(item.job?.status);
    return true;
  });
  text("listCount", `${number(visible.length)} de ${number(snapshot.guidelines.length)} diretrizes`);
  const list = $("guidelineList"); list.replaceChildren();
  if (!visible.length) { list.append(node("div", "empty-list", "Nenhuma diretriz corresponde a esta busca.")); return; }
  visible.forEach(item => {
    const button = node("button", "guideline-item" + (item.id === selectedId ? " selected" : ""));
    button.type = "button"; button.setAttribute("aria-pressed", String(item.id === selectedId));
    button.append(node("span", "file-icon", "▤"));
    const content = node("span", "row-content"); content.append(node("strong", "", item.title));
    const pending = ["PENDING","PROCESSING"].includes(item.job?.status);
    const review = ["FAILED","NEEDS_REVIEW"].includes(item.job?.status);
    const caption = pending ? labels[item.job.status] : review ? "Último job requer conferência" : item.current_version_id ? "Texto disponível" : "Aguardando extração";
    const subtitle = node("span", "row-subtitle " + (pending ? "pending" : review ? "review" : item.current_version_id ? "available" : ""));
    subtitle.append(node("span", "small-dot"), document.createTextNode(caption)); content.append(subtitle); button.append(content);
    button.addEventListener("click", () => loadGuideline(item.id)); list.append(button);
  });
}

async function refresh(reloadReader = false) {
  if (refreshBusy) return;
  refreshBusy = true; $("refreshButton").disabled = true;
  try {
    const previous = snapshot;
    snapshot = await request("/demo-api/state");
    $("errorBanner").hidden = true;
    $("connection").className = "connection online"; $("connection").replaceChildren(node("span", "small-dot"), document.createTextNode("Acervo conectado"));
    const c = snapshot.counts;
    text("totalCount", number(c.guidelines)); text("textCount", number(c.with_text));
    text("pendingCount", number(c.pending)); text("reviewCount", number(c.review));
    $("discoverButton").disabled = !snapshot.source.enabled;
    $("discoverButton").title = snapshot.source.enabled ? "Solicitar descoberta na fonte real" : "Fonte desabilitada. Habilite pela CLI antes de verificar.";
    text("updatedAt", `Painel atualizado em ${date(snapshot.checked_at)}`);
    const run = snapshot.latest_run;
    text("runBadge", run ? (labels[run.status] || run.status) : "Sem execução");
    $("runBadge").className = "badge " + (!run ? "neutral" : run.status === "COMPLETED" ? "teal" : run.status === "FAILED" ? "red" : "blue");
    text("runTitle", !run ? "Nenhuma descoberta registrada" : run.status === "COMPLETED" ? "Última verificação do catálogo concluída" : run.status === "FAILED" ? "A última verificação requer atenção" : "Verificação do catálogo em andamento");
    text("runDescription", !run ? "Use Verificar CONITEC para solicitar uma execução." : run.status === "COMPLETED" ? `${number(run.found_count)} itens encontrados · ${number(run.queued_count)} novos jobs · ${date(run.finished_at)}` : run.status === "FAILED" ? (run.error_summary || "Confira os logs do worker de descoberta.") : `Solicitada em ${date(run.started_at)}. Downloads e extração seguem nos workers.`);
    renderList();
    if (!selectedId && snapshot.guidelines.length) {
      const first = snapshot.guidelines.find(g => g.external_key.startsWith("acidentes-escorpionicos") && g.current_version_id) || snapshot.guidelines.find(g => g.current_version_id) || snapshot.guidelines[0];
      await loadGuideline(first.id);
    } else if (selectedId && detail?.scope === "archive") {
      const before = previous?.guidelines.find(g => g.id === selectedId);
      const after = snapshot.guidelines.find(g => g.id === selectedId);
      if (reloadReader || (before?.current_version_id !== after?.current_version_id && detail.version?.id === before?.current_version_id)) {
        await loadGuideline(selectedId, reloadReader ? detail.version?.id : null);
      }
    }
  } catch (exc) {
    error(exc.message);
    $("connection").className = "connection offline";
    $("connection").replaceChildren(node("span", "small-dot"), document.createTextNode(snapshot ? "Leitura desatualizada" : "Acervo indisponível"));
    $("discoverButton").disabled = true;
    if (!snapshot) text("runDescription", "Inicie o backend com docker compose up -d. O ensaio temporário também precisa do Redis.");
  } finally { refreshBusy = false; $("refreshButton").disabled = false; }
}

async function loadGuideline(id, versionId = null) {
  const currentTicket = ++ticket;
  selectedId = id; renderList();
  $("readerLoading").hidden = false; $("readerEmpty").hidden = true; $("readerContent").hidden = true;
  try {
    const value = await request(`/demo-api/guidelines/${encodeURIComponent(id)}` + (versionId ? `?version_id=${encodeURIComponent(versionId)}` : ""));
    if (currentTicket !== ticket) return;
    detail = value; documentIndex = 0; pageIndex = 0; readingMode = "pages";
    renderReader();
    text("sampleDescription", `PDF principal de “${value.guideline.title}”. O ensaio é temporário e não altera o acervo.`);
  } catch (exc) { if (currentTicket === ticket) { error(exc.message); $("readerEmpty").hidden = false; } }
  finally { if (currentTicket === ticket) $("readerLoading").hidden = true; }
}

function currentDocument() { return detail?.documents[documentIndex] || null; }
function currentPage() { return currentDocument()?.pages_json?.[pageIndex] || null; }
function pdfURL() {
  const doc = currentDocument();
  if (!doc || doc.media_type !== "application/pdf") return null;
  if (detail.scope === "temporary") return `/demo-api/sample/${encodeURIComponent(detail.sample_id)}/pdf`;
  return `/demo-api/guidelines/${encodeURIComponent(detail.guideline.id)}/pdf/${encodeURIComponent(doc.id)}?version_id=${encodeURIComponent(detail.version.id)}`;
}
function renderReader() {
  if (!detail) return;
  $("readerEmpty").hidden = true; $("readerContent").hidden = false;
  const temporary = detail.scope === "temporary", version = detail.version;
  text("scopeBadge", temporary ? "ENSAIO TEMPORÁRIO" : "ACERVO REAL");
  $("scopeBadge").className = "badge " + (temporary ? "amber" : "teal");
  $("temporaryNote").hidden = !temporary; $("backToArchive").hidden = !temporary;
  text("readerTitle", detail.guideline.title);
  text("characterCount", version ? `${number([...version.extracted_text].length)} caracteres` : "Sem texto extraído");
  text("versionDate", version ? `Detectado em ${date(version.detected_at)}` : "Aguardando processamento");
  text("pageCount", detail.documents.length ? `${number(detail.documents.reduce((n, d) => n + (d.pages_json?.length || 0), 0))} páginas` : "Sem páginas disponíveis");
  const select = $("versionSelect"); select.replaceChildren();
  detail.versions.forEach(v => {
    const option = node("option", "", `Observada ${v.observed_version}${v.id === detail.guideline.current_version_id ? " · corrente" : ""}`);
    option.value = v.id; option.selected = v.id === version?.id; select.append(option);
  });
  $("versionLabel").hidden = temporary || !detail.versions.length;
  const documents = $("documentSelect"); documents.replaceChildren();
  detail.documents.forEach((doc, index) => {
    const option = node("option", "", doc.role === "main" ? "Documento principal" : `Anexo · ${doc.reference_key}`);
    option.value = String(index); documents.append(option);
  });
  $("documentLabel").hidden = detail.documents.length < 2;
  $("downloadButton").disabled = !version;
  $("pagesTab").disabled = !detail.documents.length;
  if (!detail.documents.length) readingMode = "full";
  renderText();
}
function renderText() {
  const doc = currentDocument(), page = currentPage(), full = readingMode === "full";
  $("pagesTab").classList.toggle("active", !full); $("fullTab").classList.toggle("active", full);
  $("pagesTab").setAttribute("aria-pressed", String(!full)); $("fullTab").setAttribute("aria-pressed", String(full));
  $("pagination").hidden = full || !doc?.pages_json?.length;
  $("pageInput").value = String(pageIndex + 1); $("pageInput").max = String(doc?.pages_json?.length || 1);
  text("pageTotal", `de ${number(doc?.pages_json?.length || 0)}`);
  $("previousPage").disabled = pageIndex === 0; $("nextPage").disabled = pageIndex + 1 >= (doc?.pages_json?.length || 0);
  text("pageCaption", full ? "TEXTO COMPLETO DA VERSÃO OBSERVADA" : `PÁGINA ${page?.page_number || "—"} · TEXTO EXTRAÍDO DO ORIGINAL`);
  text("pageText", full ? (detail.version?.extracted_text || "Ainda não há uma versão textual. Aguarde a conclusão dos jobs de ingestão.") : (page?.text?.trim() || "Esta página não contém texto extraível. Consulte o PDF original."));
  $("readingArea").scrollTop = 0; $("pdfButton").disabled = !pdfURL(); $("copyButton").disabled = !detail.version;
  const url = doc?.source_url;
  $("sourceLink").removeAttribute("href"); text("sourceLink", url || "Não disponível");
  if (url) { try { if (new URL(url).protocol === "https:") $("sourceLink").href = url; } catch { /* Preserve only text. */ } }
  text("fetchedAt", date(doc?.fetched_at)); text("rawHash", doc?.raw_sha256 || "Não disponível"); text("textHash", doc?.content_sha256 || "Não disponível");
}

async function startSample() {
  if (sampleRunning) return;
  sampleRunning = true; $("sampleButton").disabled = true; $("sampleResultButton").hidden = true;
  $("sampleProgress").hidden = false; $("sampleBusy").hidden = false;
  $("sampleEvents").replaceChildren(); text("sampleSummary", ""); text("sampleStage", "Iniciando ensaio temporário…");
  try {
    const selected = snapshot?.guidelines.find(g => g.id === selectedId);
    const started = await request("/demo-api/sample", {method:"POST", body:JSON.stringify({external_key:selected?.external_key || null})});
    sampleId = started.id;
    await pollSample();
  } catch (exc) { finishSample(); text("sampleStage", "Ensaio não iniciado"); text("sampleSummary", exc.message); }
}
function finishSample() { sampleRunning = false; $("sampleButton").disabled = false; $("sampleBusy").hidden = true; }
async function pollSample() {
  try {
    const state = await request(`/demo-api/sample/${encodeURIComponent(sampleId)}`);
    const stages = {DISCOVERY:"Consultando a CONITEC",FETCH:"Recuperando o PDF oficial",PERSIST:"Preservando dados temporários",EXTRACT:"Extraindo texto por página",NORMALIZE:"Conferindo o conteúdo extraído",COMPLETED:"Extração temporária concluída",FAILED:"O ensaio não concluiu"};
    text("sampleStage", stages[state.stage] || "Em processamento");
    const events = $("sampleEvents"); events.replaceChildren();
    (state.events || []).forEach(event => events.append(node("li", "", `${date(event.at)} · ${event.message}`)));
    if (state.status === "COMPLETED") {
      finishSample(); text("sampleSummary", `${state.title} · ${number(state.pages)} páginas · ${number(state.characters)} caracteres · reexecução ${state.duplicate_delivery === "IGNORED" ? "ignorada" : state.duplicate_delivery}`);
      $("sampleResultButton").hidden = false;
    } else if (state.status === "FAILED") { finishSample(); text("sampleSummary", state.error || "Confira a disponibilidade da fonte e tente novamente."); }
    else { setTimeout(pollSample, 1000); }
  } catch (exc) { finishSample(); text("sampleStage", "Acompanhamento indisponível"); text("sampleSummary", exc.message + " O processo pode continuar no servidor."); }
}

$("refreshButton").addEventListener("click", () => refresh(true));
$("discoverButton").addEventListener("click", async () => {
  $("discoverButton").disabled = true;
  try {
    const result = await request("/demo-api/discover", {method:"POST"});
    toast(result.published ? "Verificação solicitada. Acompanhe o catálogo e os processamentos reais." : "Solicitação salva no banco. Publicação pendente para reconciliação.");
    await refresh();
  } catch (exc) { error(exc.message); }
  finally { $("discoverButton").disabled = !snapshot?.source.enabled; }
});
$("search").addEventListener("input", renderList);
document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
  filter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach(b => { b.classList.toggle("active", b === button); b.setAttribute("aria-pressed", String(b === button)); });
  renderList();
}));
$("versionSelect").addEventListener("change", () => loadGuideline(selectedId, $("versionSelect").value));
$("documentSelect").addEventListener("change", () => { documentIndex = Number($("documentSelect").value); pageIndex = 0; renderText(); });
$("pagesTab").addEventListener("click", () => { readingMode = "pages"; renderText(); });
$("fullTab").addEventListener("click", () => { readingMode = "full"; renderText(); });
$("previousPage").addEventListener("click", () => { if (pageIndex > 0) { pageIndex--; renderText(); } });
$("nextPage").addEventListener("click", () => { if (pageIndex + 1 < currentDocument().pages_json.length) { pageIndex++; renderText(); } });
$("pageInput").addEventListener("change", () => { pageIndex = Math.max(0, Math.min(Math.trunc(Number($("pageInput").value) || 1) - 1, currentDocument().pages_json.length - 1)); renderText(); });
$("pdfButton").addEventListener("click", () => { const url = pdfURL(); if (url) window.open(url + (url.includes("?") ? "&" : "?") + "view=1#page=" + (pageIndex + 1), "_blank", "noopener"); });
$("downloadButton").addEventListener("click", () => {
  if (!detail?.version) return;
  const url = URL.createObjectURL(new Blob([detail.version.extracted_text], {type:"text/plain;charset=utf-8"}));
  const link = document.createElement("a"); link.href = url; link.download = `${detail.scope === "temporary" ? "ensaio-temporario" : "medguide"}-versao-${detail.version.observed_version}.txt`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
});
$("copyButton").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("pageText").textContent); toast("Texto copiado."); } catch { toast("O navegador não permitiu copiar. Use Baixar texto."); } });
$("smallerFont").addEventListener("click", () => { fontSize = Math.max(13, fontSize - 1); document.documentElement.style.setProperty("--font-size", fontSize + "px"); });
$("largerFont").addEventListener("click", () => { fontSize = Math.min(23, fontSize + 1); document.documentElement.style.setProperty("--font-size", fontSize + "px"); });
$("sampleButton").addEventListener("click", startSample);
$("sampleResultButton").addEventListener("click", async () => {
  try { ++ticket; detail = await request(`/demo-api/sample/${encodeURIComponent(sampleId)}/result`); detail.sample_id = sampleId; pageIndex = 0; documentIndex = 0; readingMode = "pages"; $("readerLoading").hidden = true; renderReader(); $("reader").scrollIntoView({behavior:"smooth", block:"start"}); }
  catch (exc) { error(exc.message); }
});
$("backToArchive").addEventListener("click", () => { if (selectedId) loadGuideline(selectedId); else toast("Conecte o acervo para selecionar uma diretriz."); });
$("archiveNav").addEventListener("click", () => { if (selectedId && detail?.scope === "temporary") loadGuideline(selectedId); $("search").focus(); });
$("aboutButton").addEventListener("click", () => $("aboutDialog").showModal());
$("closeAbout").addEventListener("click", () => $("aboutDialog").close());
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 5000);
