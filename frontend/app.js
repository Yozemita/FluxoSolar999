"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const state = {products: [], creatives: [], schedules: [], agents: [], runs: []};
const brl = new Intl.NumberFormat("pt-BR", {style: "currency", currency: "BRL"});
const num = new Intl.NumberFormat("pt-BR");
let noticeTimer;
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notice(message, error = false) {
  clearTimeout(noticeTimer);
  $("#notice").textContent = message;
  $("#notice").className = error ? "notice error" : "notice";
  $("#notice").hidden = false;
  noticeTimer = setTimeout(() => { $("#notice").hidden = true; }, 7000);
}
function loginView() {
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
  $("#login-form").elements.password.value = "";
}
async function api(path, data, method = "POST") {
  const response = await fetch(path, {method: data === undefined ? "GET" : method, credentials: "same-origin",
    headers: data === undefined ? {} : {"Content-Type": "application/json", "X-FluxoSolar-CSRF": "1"},
    body: data === undefined ? undefined : JSON.stringify(data)});
  let result;
  try { result = await response.json(); } catch { throw new Error("O servidor não retornou uma resposta válida."); }
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/auth/login") loginView();
    const detail = result.detail;
    throw new Error(Array.isArray(detail) ? detail.map(x => `${x.loc.slice(1).join(".")}: ${x.msg}`).join("; ") : detail || "Não foi possível concluir a operação.");
  }
  return result;
}
async function busy(button, task) {
  button.disabled = true;
  try { await task(); } catch (e) { notice(e.message, true); }
  finally { button.disabled = false; }
}
function optionSelect(select, rows, label) {
  const current = select.value;
  select.replaceChildren();
  if (!rows.length) {
    const option = new Option("Cadastre um item primeiro", "");
    select.add(option);
  }
  rows.forEach(row => select.add(new Option(label(row), String(row.id))));
  if (rows.some(r => String(r.id) === current)) select.value = current;
}
function showView(id) {
  $$(".view").forEach(view => { view.hidden = view.id !== id; });
  $$(".nav-item").forEach(button => {
    button.classList.toggle("active", button.dataset.view === id);
    if (button.dataset.view === id) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  window.scrollTo({top: 0, behavior: "smooth"});
}
$$('[data-view]').forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));

function renderDashboard(data, status) {
  const summary = $("#summary"); summary.replaceChildren();
  [["Produtos cadastrados", num.format(data.products), "Seu catálogo persistido"],
   ["Rascunhos criativos", num.format(data.creatives), "Ideias em preparação"],
   ["Comissão informada", brl.format(data.totals.commission), "Relatórios importados"],
   ["Resultado de mídia", brl.format(data.profit), "Comissão menos gasto informado"]].forEach(([label, value, note]) => {
    const card = el("article", undefined, "metric-card");
    card.append(el("small", label), el("div", value, "metric-number"), el("small", note)); summary.append(card);
  });
  const table = $("#ranking"); table.replaceChildren();
  data.ranking.forEach(row => {
    const tr = el("tr"), name = el("td", row.product.title);
    name.append(el("small", `${row.product.merchant} · ${row.product.external_code}`)); tr.append(name);
    [num.format(row.metrics.views), num.format(row.metrics.clicks), num.format(row.metrics.conversions), brl.format(row.profit),
     ({collect_data: "Coletar mais dados", prioritize: "Priorizar para revisão", review: "Revisar resultado"})[row.recommendation]].forEach(value => tr.append(el("td", value)));
    table.append(tr);
  });
  $("#ranking-note").textContent = `${data.note} O ranking exige ao menos 100 views, 20 cliques e 3 conversões; os limites são heurísticos.`;
  $("#connection").textContent = status.database === "postgresql" ? "● PostgreSQL conectado" : "● Modo local conectado";
  const integrations = $("#integrations"); integrations.replaceChildren();
  [["Banco", status.database === "postgresql" ? "PostgreSQL" : "SQLite · desenvolvimento"],
   ["Redis", ({ready: "Conexão verificada", unavailable: "Conexão indisponível", not_configured: "Não configurado"})[status.redis]],
   ["Mídia S3", status.s3 === "not_configured" ? "Não configurada" : "Configurada · envio a validar"],
   ["Publicação social", "Não conectada"]].forEach(([label, value]) => {
    const box = el("div", label, "integration"); box.append(el("small", value)); integrations.append(box);
  });
}
function renderProducts() {
  const list = $("#product-list"); list.replaceChildren();
  state.products.forEach(product => {
    const card = el("article", undefined, "product-card");
    const link = el("a", "Abrir link oficial ↗");
    link.href = product.affiliate_url; link.target = "_blank"; link.rel = "sponsored noopener noreferrer";
    const edit = el("button", "Editar produto", "quiet"); edit.type = "button";
    edit.addEventListener("click", () => {
      const form = $("#product-form");
      ["id", "merchant", "external_code", "title", "affiliate_url"].forEach(key => { form.elements[key].value = product[key]; });
      form.scrollIntoView({behavior: "smooth"}); form.elements.title.focus();
    });
    card.append(el("span", product.merchant, "badge"), el("h3", product.title), el("div", product.external_code, "code"), link, edit);
    list.append(card);
  });
  if (!state.products.length) list.append(el("p", "Seu catálogo está vazio. Cadastre o primeiro produto acima.", "empty"));
  $$(".product-select").forEach(select => optionSelect(select, state.products, p => `${p.title} · ${p.external_code}`));
}
function field(label, name, value, textarea = false) {
  const wrapper = el("label", label);
  const input = el(textarea ? "textarea" : "input"); input.name = name; input.value = value || ""; input.required = true;
  input.maxLength = ({title: 200, caption: 5000, prompt: 10000})[name];
  wrapper.append(input); return wrapper;
}
function renderCreatives() {
  const list = $("#creative-list"); list.replaceChildren();
  state.creatives.forEach(creative => {
    const form = el("form", undefined, "panel creative-editor");
    const product = state.products.find(p => p.id === creative.product_id);
    const meta = el("p", `Rascunho #${creative.id} · ${product?.external_code || "Produto"} · Template, sem geração de mídia`, "footnote full");
    form.append(el("h3", product?.title || creative.title), meta, field("Título", "title", creative.title), field("Legenda", "caption", creative.caption, true));
    const prompt = field("Prompt para produção", "prompt", creative.prompt, true); prompt.classList.add("full"); form.append(prompt);
    const uploadLabel = el("label", "Anexar mídia autorizada · S3, até 25 MB");
    const file = el("input"); file.type = "file"; file.accept = "image/jpeg,image/png,image/webp,video/mp4"; uploadLabel.append(file);
    const mediaStatus = el("p", creative.media_key ? "Mídia anexada ao rascunho" : "Sem mídia anexada", "footnote");
    const upload = el("button", "Enviar mídia", "quiet"); upload.type = "button";
    upload.addEventListener("click", () => busy(upload, async () => {
      const media = file.files[0];
      if (!media) throw new Error("Selecione uma imagem ou vídeo primeiro.");
      if (media.size > 25 * 1024 * 1024) throw new Error("O limite de envio é 25 MB.");
      const signed = await api("/api/media/uploads", {content_type: media.type});
      const body = new FormData(); Object.entries(signed.upload.fields).forEach(([k, v]) => body.append(k, v)); body.append("file", media);
      const result = await fetch(signed.upload.url, {method: "POST", body, credentials: "omit"});
      if (!result.ok) throw new Error("O armazenamento recusou o envio. Confira as permissões e CORS do bucket.");
      creative.media_key = signed.key;
      await saveCreative(form, creative);
      mediaStatus.textContent = "Mídia anexada ao rascunho"; notice("Mídia enviada e rascunho salvo.");
    }));
    const uploadBox = el("div"); uploadBox.append(uploadLabel, upload, mediaStatus); form.append(uploadBox);
    const save = el("button", "Salvar rascunho", "primary"); save.type = "submit"; form.append(save);
    form.addEventListener("submit", event => { event.preventDefault(); busy(save, async () => {
      await saveCreative(form, creative); notice("Rascunho atualizado.");
    }); });
    list.append(form);
  });
  if (!state.creatives.length) list.append(el("p", "Selecione um produto e crie seu primeiro rascunho.", "empty"));
  optionSelect($("#creative-select"), state.creatives, c => `#${c.id} · ${c.title}`);
}
async function saveCreative(form, creative) {
  const values = Object.fromEntries(new FormData(form)); values.media_key = creative.media_key;
  const result = await api(`/api/creatives/${creative.id}`, values, "PUT");
  Object.assign(creative, result);
}
function renderSchedules() {
  const list = $("#schedule-list"); list.replaceChildren();
  state.schedules.forEach(row => {
    const creative = state.creatives.find(c => c.id === row.creative_id);
    const card = el("div", undefined, "schedule-row");
    const instant = row.scheduled_for.endsWith("Z") || /[+-]\d\d:\d\d$/.test(row.scheduled_for) ? row.scheduled_for : `${row.scheduled_for}Z`;
    card.append(el("span", creative?.title || `Criativo #${row.creative_id}`), el("span", `${row.channel} · ${new Date(instant).toLocaleString("pt-BR")}`), el("span", "Planejado · publicação manual", "muted"));
    list.append(card);
  });
  if (!state.schedules.length) list.append(el("p", "Nenhuma publicação planejada.", "empty"));
}
const descriptions = {Scout: "Identifica produtos com dados suficientes para uma nova análise.", Creative: "Cria uma legenda e um prompt por template para o produto escolhido.", Catalog: "Consulta o catálogo salvo e seus vínculos de produto.", Scheduler: "Consulta a agenda interna, sem publicar nos canais.", Analytics: "Consolida as métricas e o resultado de mídia informado.", Winner: "Aplica o ranking heurístico às métricas importadas.", Compliance: "Confere identificação de publicidade nas legendas."};
function renderAgents() {
  const list = $("#agent-list"); list.replaceChildren();
  state.agents.forEach(name => {
    const card = el("article", undefined, "product-card"), button = el("button", "Executar agora ↗", "primary");
    button.addEventListener("click", () => busy(button, async () => {
      const product = Number($("#agent-product").value);
      if (name === "Creative" && !product) throw new Error("Cadastre e selecione um produto primeiro.");
      await api(`/api/agents/${name}/run`, name === "Creative" ? {product_id: product} : {});
      await loadData(); notice(`${name}: execução concluída e registrada.`);
    }));
    card.append(el("h3", name), el("p", descriptions[name], "muted"), button); list.append(card);
  });
  const history = $("#agent-history"); history.replaceChildren();
  state.runs.forEach(run => {
    const details = el("details", undefined, "run-record");
    details.append(el("summary", `#${run.id} · ${run.agent} · Concluído — ver resultado`), el("pre", JSON.stringify(run.result, null, 2)));
    history.append(details);
  });
  if (!state.runs.length) history.append(el("p", "As execuções aparecerão aqui.", "empty"));
}
async function loadData() {
  const [products, creatives, schedules, agents, runs, data, status] = await Promise.all([
    api("/api/products"), api("/api/creatives"), api("/api/schedules"), api("/api/agents"), api("/api/agent-runs"), api("/api/dashboard"), api("/api/status")]);
  Object.assign(state, {products, creatives, schedules, agents: agents.agents, runs});
  renderDashboard(data, status); renderProducts(); renderCreatives(); renderSchedules(); renderAgents();
}
async function openApp() {
  const user = await api("/api/auth/me");
  await loadData();
  $("#owner-label").textContent = user.username;
  $("#login-view").hidden = true; $("#app-view").hidden = false;
}
$("#login-form").addEventListener("submit", async event => {
  event.preventDefault(); const form = event.currentTarget, button = form.querySelector("button"); button.disabled = true; $("#login-error").textContent = "";
  try { await api("/api/auth/login", Object.fromEntries(new FormData(form))); form.elements.password.value = ""; await openApp(); }
  catch (e) { $("#login-error").textContent = e.message; }
  finally { button.disabled = false; }
});
$("#logout").addEventListener("click", event => busy(event.currentTarget, async () => { await api("/api/auth/logout", {}); loginView(); }));
$("#logout-top").addEventListener("click", event => busy(event.currentTarget, async () => { await api("/api/auth/logout", {}); loginView(); }));
$("#refresh").addEventListener("click", event => busy(event.currentTarget, async () => { await loadData(); notice("Dados atualizados."); }));
$("#product-form").addEventListener("submit", event => {
  event.preventDefault(); const form = event.currentTarget;
  busy(form.querySelector('[type="submit"]'), async () => {
    const data = Object.fromEntries(new FormData(form)), id = data.id; delete data.id;
    const existing = state.products.find(p => String(p.id) === id); data.storefront_url = existing?.storefront_url || null;
    await api(id ? `/api/products/${id}` : "/api/products", data, id ? "PUT" : "POST");
    form.reset(); form.elements.id.value = ""; await loadData(); notice("Produto salvo.");
  });
});
$("#cancel-product").addEventListener("click", () => { $("#product-form").reset(); $("#product-form").elements.id.value = ""; });
$("#creative-form").addEventListener("submit", event => {
  event.preventDefault(); const form = event.currentTarget;
  busy(form.querySelector("button"), async () => { await api("/api/creatives", {product_id: Number(form.elements.product_id.value)}); await loadData(); notice("Rascunho criado por template."); });
});
function newEventId() { $("#metrics-form").elements.event_id.value = crypto.randomUUID(); }
newEventId();
$("#metrics-form").addEventListener("submit", event => {
  event.preventDefault(); const form = event.currentTarget;
  busy(form.querySelector("button"), async () => {
    const values = Object.fromEntries(new FormData(form));
    Object.keys(values).forEach(key => { if (key !== "event_id") values[key] = Number(values[key]); });
    const result = await api("/api/metrics", values);
    form.reset(); newEventId(); await loadData(); notice(result.duplicate ? "Esse lote já estava importado. Nenhum valor foi duplicado." : "Lote importado.");
  });
});
$("#schedule-form").addEventListener("submit", event => {
  event.preventDefault(); const form = event.currentTarget;
  busy(form.querySelector("button"), async () => {
    await api("/api/schedules", {creative_id: Number(form.elements.creative_id.value), channel: form.elements.channel.value, scheduled_for: new Date(form.elements.scheduled_for.value).toISOString()});
    form.reset(); await loadData(); notice("Adicionado ao planejamento. A publicação externa é manual.");
  });
});
openApp().catch(e => { loginView(); if (!e.message.includes("login")) $("#login-error").textContent = e.message; });
