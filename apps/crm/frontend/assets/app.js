// Sentinela — frontend em JS puro. Uma casca so: o modulo de protecao
// (Sentinela) e o CRM (VisiQuost) vivem na mesma SPA e no mesmo servidor.
// Talks to the FastAPI at /api/v1/*. Persists auth in localStorage.
// Zero framework, zero build step — matches the "works offline" ethos.

const API = "/api/v1";
const TOKEN_KEY = "visiquost.token";
const CONV_KEY = "visiquost.conversation";
const LANG_KEY = "visiquost.lang";
const THEME_KEY = "visiquost.theme";
const KANBAN_KEY = "visiquost.kanban";

// ==================== i18n ====================
const DICT = {
  en: {
    // auth
    auth_signin: "Sign in", auth_create: "Create workspace",
    auth_email: "Email", auth_password: "Password",
    auth_fullname: "Full name", auth_ws: "Workspace name",
    auth_login_tab: "Login", auth_register_tab: "Sign up",
    auth_demo: "Demo login:",
    // hero
    hero_tag: "AI-powered CRM — works offline",
    hero_1: "Multi-workspace, encryption at rest",
    hero_2: "Jarvis: assistant that runs without any external API",
    hero_3: "Kanban, automations, lead scoring, forecast",
    hero_4: "Full workspace import/export",
    // new hero (redesign)
    hero_h1_line1: "Your family protected.",
    hero_h1_line2: "Your work organized.",
    hero_h1_line3: "Zero cloud.",
    hero_lead: "Sentinela filters what your child sees with local AI, and the CRM keeps your clients in order. One app, on your machine — no OAuth, no subscription, no data leaves it.",
    hero_fc_filtro_t: "A filter that can't be switched off", hero_fc_filtro_d: "DNS + hosts + browser policy. Incognito has nothing to turn off, and a Guardian reapplies it if tampered with.",
    hero_fc_painel_t: "Parent dashboard", hero_fc_painel_d: "What was searched, what the AI blocked and why. PIN lock, encrypted log, retention you choose.",
    hero_fc_jarvis_t: "Local Jarvis", hero_fc_jarvis_d: "80+ intents in PT/EN. Creates contacts, schedules meetings, summarizes pipeline — all on your PC.",
    hero_fc_crm_t: "Full CRM", hero_fc_crm_d: "Kanban, forecast, lead scoring, encryption at rest, portable import/export and automatic backup.",
    nav_section_crm: "CRM",
    hero_stats_tests: "tests passing", hero_stats_apis: "external APIs", hero_stats_setup: "full setup",
    auth_welcome: "Welcome", auth_welcome_sub: "Sign in or create a new workspace in 30 seconds.",
    auth_demo_btn_t: "Sign in as demo", auth_demo_btn_d: "No signup · sample data ready",
    auth_badge_local: "100% LOCAL",
    // sidebar
    nav_dashboard: "Dashboard", nav_contacts: "Contacts", nav_companies: "Companies",
    nav_opportunities: "Opportunities", nav_leads: "Leads", nav_kanban: "Pipeline",
    nav_tasks: "Tasks", nav_meetings: "Meetings", nav_automations: "Automations", nav_integrations: "Integrations",
    cmdk_hint: "🔍 Search everything…",
    menu_seed: "🌱 Seed demo", menu_export: "📤 Export",
    menu_import: "📥 Import", menu_theme: "🌓 Theme", menu_logout: "↩ Log out",
    menu_lang: "🌐 Language",
    // pages
    p_greeting_morning: "Good morning", p_greeting_afternoon: "Good afternoon", p_greeting_evening: "Good evening",
    p_overdue: "⏰ Overdue tasks", p_upcoming: "📅 Upcoming meetings (48h)", p_this_week: "📊 This week",
    p_kpi_contacts: "Contacts", p_kpi_companies: "Companies", p_kpi_leads: "Leads",
    p_kpi_opps: "Opportunities", p_kpi_tasks: "Open tasks",
    p_wk_closing: "Opportunities closing", p_wk_weighted: "Weighted pipeline",
    p_wk_tasks: "Tasks due", p_wk_meetings: "Meetings",
    add_contact: "+ New contact", add_company: "+ New company", add_opp: "+ New opportunity",
    add_lead: "+ New lead", add_task: "+ New task", add_meeting: "+ New meeting",
    add_workflow: "+ Workflow", add_rule: "+ Rule",
    import_csv: "📄 Import CSV", scoring_rules: "⚙️ Scoring rules", recalc: "🔄 Recalculate all",
    search_contacts: "🔍 Search contacts…", search_companies: "🔍 Search companies…",
    tbl_name: "Name", tbl_email: "Email", tbl_phone: "Phone", tbl_job: "Job", tbl_domain: "Domain",
    tbl_industry: "Industry", tbl_stage: "Stage", tbl_amount: "Amount", tbl_status: "Status",
    tbl_company: "Company", tbl_source: "Source", tbl_score: "Score",
    tbl_field: "Field", tbl_op: "Op", tbl_value: "Value", tbl_delta: "Δ", tbl_active: "Active",
    kanban_hint: "Drag a card to change stage · right-click a column header to set the WIP limit",
    auto_desc: "Workflows fire automatically when an Activity matches their trigger. Steps run synchronously in order. Loop guard prevents recursion.",
    inte_desc: "Connect external accounts. Tokens are encrypted at rest (Fernet). Live OAuth flows land later — for now paste an access token you already obtained.",
    inte_provider: "Provider", inte_label: "Account label (email / handle)",
    inte_access: "Access token", inte_refresh: "Refresh token (optional)",
    inte_connect: "Connect", inte_disconnect: "Disconnect", inte_empty: "Nothing connected yet.",
    task_all: "All", task_open: "Open", task_overdue: "Overdue", task_done: "Done",
    task_mark_done: "Done", task_due: "due",
    workflow_none: "No workflows yet. Click \"+ Workflow\" to create one.",
    workflow_disable: "Disable", workflow_enable: "Enable", workflow_delete: "Delete", workflow_runs: "Runs",
    workflow_no_runs: "No runs yet.", workflow_recent: "Recent runs",
    // jarvis
    jarvis_welcome_title: "Hi! I'm Jarvis.",
    jarvis_welcome_body: "Ask for anything: summarize pipeline, create task, find contact, forecast, meetings, mark task done…",
    jarvis_placeholder: "Ask Jarvis…",
    quick_week: "📊 Week", quick_pipeline: "💰 Pipeline",
    quick_overdue: "⏰ Overdue", quick_forecast: "🔮 Forecast", quick_help: "❓ Help",
    // drawer
    drawer_notes: "Notes", drawer_activity: "Timeline",
    drawer_add_note: "Add a note…", drawer_no_notes: "No notes yet.", drawer_no_activity: "No activity yet.",
    // modal
    modal_cancel: "Cancel", modal_save: "Save", modal_close: "Close",
    // toasts
    t_saved: "Saved", t_deleted: "Deleted", t_created: "Created",
    t_seeded: "Sample data added", t_seed_skipped: "Workspace already has data",
    t_exported: "Exported", t_imported: "Imported",
    t_export_failed: "Export failed", t_import_failed: "Import failed",
    t_connect_failed: "Connect failed", t_seed_failed: "Seed failed",
    t_error: "Error",
    // confirms
    c_seed: "Populate this workspace with sample data? (Skipped if it already has data.)",
    c_import: (name) => `Import ${name} into the current workspace? If the workspace has data, IDs will be regenerated.`,
    c_delete_rule: (n) => `Delete rule "${n}"?`,
    c_delete_workflow: (n) => `Delete workflow "${n}"?`,
    c_disconnect: (p) => `Disconnect ${p}?`,
    // misc
    empty_here: "Nothing here.",
    loading: "Loading pipeline…",
    no_pipeline: "No pipeline yet.",
    total: "total", wip: "WIP",
    expand: "expand", collapse: "collapse",
    session_expired: "Session expired — please sign in again",
    wip_prompt: (s) => `WIP limit for "${s}" (blank to clear):`,
    field_ph_email: "you@company.com",
    field_ph_password: "at least 8 characters",
    field_ph_ws: "My Company",
    session_hero_name: "Sentinela",
  },
  pt: {
    auth_signin: "Entrar", auth_create: "Criar workspace",
    auth_email: "Email", auth_password: "Senha",
    auth_fullname: "Nome completo", auth_ws: "Nome do workspace",
    auth_login_tab: "Entrar", auth_register_tab: "Criar conta",
    auth_demo: "Login demo:",
    hero_tag: "CRM com IA — funciona offline",
    hero_1: "Multi-workspace, criptografia em repouso",
    hero_h1_line1: "Sua família protegida.",
    hero_h1_line2: "Seu trabalho organizado.",
    hero_h1_line3: "Zero nuvem.",
    hero_lead: "O Sentinela filtra o que a criança vê com IA local, e o CRM cuida dos seus clientes. Um app só, no seu computador — sem OAuth, sem mensalidade, sem enviar dados pra ninguém.",
    hero_fc_filtro_t: "Filtro que não desliga", hero_fc_filtro_d: "DNS + hosts + política do navegador. A aba anônima não tem o que desligar, e um Guardião reaplica se adulterarem.",
    hero_fc_painel_t: "Painel do responsável", hero_fc_painel_d: "O que foi buscado, o que a IA barrou e por quê. Trava por PIN, registro cifrado, retenção que você define.",
    hero_fc_jarvis_t: "Jarvis local", hero_fc_jarvis_d: "80+ intents em PT/EN. Cria contato, agenda reunião, resume o pipeline — tudo no seu PC.",
    hero_fc_crm_t: "CRM completo", hero_fc_crm_d: "Kanban, forecast, lead scoring, criptografia em repouso, import/export portátil e backup automático.",
    nav_section_crm: "CRM",
    hero_stats_tests: "testes passando", hero_stats_apis: "APIs externas", hero_stats_setup: "setup completo",
    auth_welcome: "Bem-vindo", auth_welcome_sub: "Entre com sua conta ou crie um workspace novo em 30 segundos.",
    auth_demo_btn_t: "Entrar como demo", auth_demo_btn_d: "Sem cadastro · dados de exemplo já carregados",
    auth_badge_local: "100% LOCAL",
    hero_2: "Jarvis: assistente que roda sem nenhuma API externa",
    hero_3: "Kanban, automações, lead scoring, forecast",
    hero_4: "Import/export completo do workspace",
    nav_dashboard: "Painel", nav_contacts: "Contatos", nav_companies: "Empresas",
    nav_opportunities: "Oportunidades", nav_leads: "Leads", nav_kanban: "Pipeline",
    nav_tasks: "Tarefas", nav_meetings: "Reuniões", nav_automations: "Automações", nav_integrations: "Integrações",
    cmdk_hint: "🔍 Buscar em tudo…",
    menu_seed: "🌱 Popular demo", menu_export: "📤 Exportar",
    menu_import: "📥 Importar", menu_theme: "🌓 Tema", menu_logout: "↩ Sair",
    menu_lang: "🌐 Idioma",
    p_greeting_morning: "Bom dia", p_greeting_afternoon: "Boa tarde", p_greeting_evening: "Boa noite",
    p_overdue: "⏰ Tarefas atrasadas", p_upcoming: "📅 Próximas reuniões (48h)", p_this_week: "📊 Esta semana",
    p_kpi_contacts: "Contatos", p_kpi_companies: "Empresas", p_kpi_leads: "Leads",
    p_kpi_opps: "Oportunidades", p_kpi_tasks: "Tarefas abertas",
    p_wk_closing: "Oportunidades fechando", p_wk_weighted: "Pipeline ponderado",
    p_wk_tasks: "Tarefas com prazo", p_wk_meetings: "Reuniões",
    add_contact: "+ Novo contato", add_company: "+ Nova empresa", add_opp: "+ Nova oportunidade",
    add_lead: "+ Novo lead", add_task: "+ Nova tarefa", add_meeting: "+ Nova reunião",
    add_workflow: "+ Fluxo", add_rule: "+ Regra",
    import_csv: "📄 Importar CSV", scoring_rules: "⚙️ Regras de pontuação", recalc: "🔄 Recalcular todos",
    search_contacts: "🔍 Buscar contatos…", search_companies: "🔍 Buscar empresas…",
    tbl_name: "Nome", tbl_email: "Email", tbl_phone: "Telefone", tbl_job: "Cargo", tbl_domain: "Domínio",
    tbl_industry: "Indústria", tbl_stage: "Estágio", tbl_amount: "Valor", tbl_status: "Status",
    tbl_company: "Empresa", tbl_source: "Fonte", tbl_score: "Score",
    tbl_field: "Campo", tbl_op: "Op", tbl_value: "Valor", tbl_delta: "Δ", tbl_active: "Ativa",
    kanban_hint: "Arraste um card para mudar o estágio · clique com o botão direito no cabeçalho da coluna para definir limite WIP",
    auto_desc: "Fluxos disparam automaticamente quando uma Atividade bate com o trigger. Passos executam em ordem síncrona. Loop-guard previne recursão.",
    inte_desc: "Conecte contas externas. Tokens são criptografados em repouso (Fernet). Fluxos OAuth ao vivo virão depois — por enquanto cole um token que você já obteve.",
    inte_provider: "Provedor", inte_label: "Etiqueta da conta (email / handle)",
    inte_access: "Access token", inte_refresh: "Refresh token (opcional)",
    inte_connect: "Conectar", inte_disconnect: "Desconectar", inte_empty: "Nada conectado ainda.",
    task_all: "Todas", task_open: "Abertas", task_overdue: "Atrasadas", task_done: "Concluídas",
    task_mark_done: "Concluir", task_due: "prazo",
    workflow_none: "Sem fluxos ainda. Clique \"+ Fluxo\" para criar.",
    workflow_disable: "Desabilitar", workflow_enable: "Habilitar", workflow_delete: "Apagar", workflow_runs: "Execuções",
    workflow_no_runs: "Sem execuções ainda.", workflow_recent: "Execuções recentes",
    jarvis_welcome_title: "Olá! Sou o Jarvis.",
    jarvis_welcome_body: "Peça qualquer coisa: resumir pipeline, criar tarefa, buscar contato, forecast, reuniões, marcar tarefa como concluída…",
    jarvis_placeholder: "Pergunte ao Jarvis…",
    quick_week: "📊 Semana", quick_pipeline: "💰 Pipeline",
    quick_overdue: "⏰ Atrasos", quick_forecast: "🔮 Forecast", quick_help: "❓ Ajuda",
    drawer_notes: "Notas", drawer_activity: "Linha do tempo",
    drawer_add_note: "Adicionar uma nota…", drawer_no_notes: "Sem notas ainda.", drawer_no_activity: "Sem atividade ainda.",
    modal_cancel: "Cancelar", modal_save: "Salvar", modal_close: "Fechar",
    t_saved: "Salvo", t_deleted: "Apagado", t_created: "Criado",
    t_seeded: "Dados de exemplo adicionados", t_seed_skipped: "Workspace já tem dados",
    t_exported: "Exportado", t_imported: "Importado",
    t_export_failed: "Falha ao exportar", t_import_failed: "Falha ao importar",
    t_connect_failed: "Falha ao conectar", t_seed_failed: "Falha ao popular",
    t_error: "Erro",
    c_seed: "Popular este workspace com dados de exemplo? (Pulado se já tiver dados.)",
    c_import: (name) => `Importar ${name} para o workspace atual? Se já tem dados, os IDs serão regenerados.`,
    c_delete_rule: (n) => `Apagar a regra "${n}"?`,
    c_delete_workflow: (n) => `Apagar o fluxo "${n}"?`,
    c_disconnect: (p) => `Desconectar ${p}?`,
    empty_here: "Nada aqui.",
    loading: "Carregando pipeline…",
    no_pipeline: "Sem pipeline ainda.",
    total: "total", wip: "WIP",
    expand: "expandir", collapse: "recolher",
    session_expired: "Sessão expirada — por favor entre de novo",
    wip_prompt: (s) => `Limite WIP para "${s}" (vazio para limpar):`,
    field_ph_email: "voce@empresa.com",
    field_ph_password: "mínimo 8 caracteres",
    field_ph_ws: "Minha Empresa",
    session_hero_name: "Sentinela",
  }
};

function detectLang() {
  const saved = localStorage.getItem(LANG_KEY);
  if (saved && DICT[saved]) return saved;
  const nav = (navigator.language || "en").toLowerCase();
  return nav.startsWith("pt") ? "pt" : "en";
}

// Ultima secao aberta. Primeira execucao cai no Sentinela: e o que da a cara
// do app. Depois disso, quem usa o CRM todo dia continua caindo no CRM.
const PAGE_KEY = "sentinela.page";

const state = {
  token: localStorage.getItem(TOKEN_KEY) || null,
  user: null,
  workspace: null,
  conversation_id: localStorage.getItem(CONV_KEY) || null,
  page: localStorage.getItem(PAGE_KEY) || "sentinela",
  lang: detectLang(),
  theme: localStorage.getItem(THEME_KEY) || "dark",
  taskFilter: "all",
  contactSearch: "",
  companySearch: "",
};

function t(key, ...args) {
  const val = DICT[state.lang]?.[key] ?? DICT.en[key] ?? key;
  return typeof val === "function" ? val(...args) : val;
}

function applyLang() {
  document.documentElement.lang = state.lang === "pt" ? "pt-BR" : "en";
  // Apply text to statically-labeled elements via data-i18n
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (DICT[state.lang]?.[key] !== undefined) el.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => {
    const key = el.dataset.i18nPh;
    if (DICT[state.lang]?.[key] !== undefined) el.setAttribute("placeholder", t(key));
  });
}

function applyTheme() {
  // Enable smooth cross-fade for the duration of the swap only.
  const html = document.documentElement;
  html.classList.add("theme-switching");
  html.setAttribute("data-theme", state.theme);
  localStorage.setItem(THEME_KEY, state.theme);
  setTimeout(() => html.classList.remove("theme-switching"), 220);
}

// ---------- HTTP ----------
// Top-of-page network progress bar — Vercel/GitHub style. Counts in-flight
// requests; slides in when >0, fades out on drain. Zero-cost when idle.
let _apiInflight = 0;
function _apiStart() {
  _apiInflight++;
  let bar = document.getElementById("vq-progress-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "vq-progress-bar";
    document.body.appendChild(bar);
  }
  bar.classList.add("active");
}
function _apiEnd() {
  _apiInflight = Math.max(0, _apiInflight - 1);
  if (_apiInflight === 0) {
    const bar = document.getElementById("vq-progress-bar");
    if (bar) { bar.classList.remove("active"); bar.classList.add("finish"); setTimeout(() => bar.classList.remove("finish"), 400); }
  }
}

async function api(path, { method = "GET", body, headers = {} } = {}) {
  const opts = { method, headers: { "Content-Type": "application/json", ...headers } };
  if (state.token) opts.headers["Authorization"] = `Bearer ${state.token}`;
  if (body) opts.body = JSON.stringify(body);
  _apiStart();
  let resp;
  try {
    resp = await fetch(`${API}${path}`, opts);
  } catch (netErr) {
    _apiEnd();
    // Network failure — usually server down
    const err = new Error(state.lang === "pt"
      ? "Servidor offline. Verifique se o Sentinela está rodando."
      : "Server offline. Check if Sentinela is running.");
    err.status = 0;
    throw err;
  }
  if (resp.status === 204) return null;
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    if (resp.status === 401 && state.token && !path.startsWith("/auth/")) {
      clearToken();
      state.user = null;
      show("auth");
      const err = new Error(t("session_expired"));
      err.status = 401;
      throw err;
    }
    // Friendly messages per status
    const FRIENDLY = {
      400: state.lang === "pt" ? "Dados inválidos" : "Invalid data",
      403: state.lang === "pt" ? "Sem permissão" : "Not allowed",
      404: state.lang === "pt" ? "Não encontrado" : "Not found",
      409: state.lang === "pt" ? "Conflito (já existe?)" : "Conflict (already exists?)",
      413: state.lang === "pt" ? "Arquivo muito grande" : "File too large",
      429: state.lang === "pt" ? "Muitas requisições. Espere um pouco." : "Too many requests. Slow down.",
      500: state.lang === "pt" ? "Erro interno. Veja o log do servidor." : "Server error. Check the log.",
      503: state.lang === "pt" ? "Serviço indisponível" : "Service unavailable",
    };
    const detail = data?.detail || FRIENDLY[resp.status] || `HTTP ${resp.status}`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = resp.status;
    err.data = data;
    _apiEnd();
    throw err;
  }
  _apiEnd();
  return data;
}

// ==================== TOASTS ====================
function toast(msg, kind = "info", ms = 3200) {
  const host = document.getElementById("toast-host");
  if (!host) { console.log("[toast]", msg); return; }
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, ms);
}

// Undo toast with 5s window — dispatched after a soft-delete
function toastUndo(label, kind, itemId) {
  const host = document.getElementById("toast-host");
  if (!host) return;
  const el = document.createElement("div");
  el.className = "toast";
  el.style.borderLeftColor = "var(--warn)";
  const undoLabel = state.lang === "pt" ? "Desfazer" : "Undo";
  el.innerHTML = `<span></span>&nbsp;&nbsp;<button class="linkish" style="font-weight:600;">${undoLabel}</button>`;
  el.querySelector("span").textContent = label;
  const btn = el.querySelector("button");
  btn.addEventListener("click", async () => {
    try {
      await api(`/restore/${kind}/${itemId}`, { method: "POST" });
      toast(state.lang === "pt" ? "↩ Restaurado" : "↩ Restored", "success", 1800);
      routes[state.page]?.();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      el.remove();
    }
  });
  host.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 5000);
}

// ---------- Auth ----------
function saveToken(tok) { state.token = tok; localStorage.setItem(TOKEN_KEY, tok); }
function clearToken() { state.token = null; localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(CONV_KEY); state.conversation_id = null; }

async function tryRestoreSession() {
  if (!state.token) return false;
  try {
    state.user = await api("/auth/me");
    try {
      const wss = await api("/workspaces");
      state.workspace = wss?.[0] || null;
    } catch {}
    return true;
  } catch {
    clearToken();
    return false;
  }
}

function applyAuthI18n() {
  // Elementos com data-i18n="key" recebem t(key) direto — cobre hero, badge,
  // welcome, feature cards, stats, demo button. Extensivel: basta anotar
  // o elemento com o atributo.
  document.querySelectorAll(".auth-view [data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    const txt = t(key);
    if (txt) el.textContent = txt;
  });
  // Tabs (nao tem data-i18n pra permitir switch classes)
  const q = (sel, txt) => { const el = document.querySelector(sel); if (el) el.textContent = txt; };
  q('.tab[data-tab="login"]', t("auth_login_tab"));
  q('.tab[data-tab="register"]', t("auth_register_tab"));
  // Form labels — text node antes do <input>
  document.querySelectorAll("#login-form label, #register-form label").forEach(label => {
    const inp = label.querySelector("input");
    if (!inp) return;
    const nameMap = { email: "auth_email", password: "auth_password", full_name: "auth_fullname", workspace_name: "auth_ws" };
    const key = nameMap[inp.name];
    if (key && label.firstChild?.nodeType === Node.TEXT_NODE) {
      label.firstChild.textContent = t(key) + " ";
    }
  });
  const loginBtn = document.querySelector("#login-form button[type='submit']");
  if (loginBtn) loginBtn.textContent = t("auth_signin") + " →";
  const regBtn = document.querySelector("#register-form button[type='submit']");
  if (regBtn) regBtn.textContent = t("auth_create") + " →";
}

function bindAuth() {
  const langSel = document.getElementById("auth-lang-select");
  if (langSel) {
    langSel.value = state.lang;
    langSel.addEventListener("change", () => {
      state.lang = langSel.value;
      localStorage.setItem(LANG_KEY, state.lang);
      applyAuthI18n();
    });
    applyAuthI18n();
  }
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach(tabBtn => tabBtn.addEventListener("click", () => {
    tabs.forEach(x => x.classList.remove("active"));
    tabBtn.classList.add("active");
    const which = tabBtn.dataset.tab;
    document.getElementById("login-form").classList.toggle("hidden", which !== "login");
    document.getElementById("register-form").classList.toggle("hidden", which !== "register");
  }));

  document.getElementById("login-form").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const tok = await api("/auth/login", { method: "POST", body: Object.fromEntries(fd) });
      saveToken(tok.access_token);
      state.user = await api("/auth/me");
      try { const wss = await api("/workspaces"); state.workspace = wss?.[0] || null; } catch {}
      await enterApp();
    } catch (err) { document.getElementById("auth-error").textContent = err.message; }
  });

  // "Entrar como demo" — 1-click login with demo credentials
  document.getElementById("auth-demo-btn")?.addEventListener("click", async () => {
    const errEl = document.getElementById("auth-error");
    errEl.textContent = "";
    try {
      const tok = await api("/auth/login", { method: "POST", body: { email: "demo@visiquost.app", password: "demo1234" } });
      saveToken(tok.access_token);
      state.user = await api("/auth/me");
      try { const wss = await api("/workspaces"); state.workspace = wss?.[0] || null; } catch {}
      await enterApp();
    } catch (err) {
      errEl.textContent = (state.lang === "pt")
        ? `Conta demo indisponivel (${err.message}). Ela so existe em ambiente de desenvolvimento — crie sua conta na aba "Criar conta".`
        : `Demo account unavailable (${err.message}). It only exists in development — create your account under "Sign up".`;
    }
  });

  // Instalacao nova nao tem usuario nenhum: a tela abre em "Criar conta" e o
  // botao de demo some (a conta demo tem senha fixa e so existe em dev).
  // Sem isso o responsavel caia numa tela de login sem ter o que digitar.
  (async () => {
    try {
      const est = await api("/auth/estado-inicial");
      const btnDemo = document.getElementById("auth-demo-btn");
      if (btnDemo && !est.demo_disponivel) btnDemo.classList.add("hidden");
      if (!est.tem_usuarios) {
        document.querySelector('.tab[data-tab="register"]')?.click();
        const sub = document.querySelector(".auth-sub");
        if (sub) {
          sub.textContent = state.lang === "pt"
            ? "Primeiro acesso: crie a conta do responsável. Ela é a única chave deste computador — nada é enviado para fora."
            : "First run: create the parent account. It is the only key to this machine — nothing is sent anywhere.";
        }
      }
    } catch { /* servidor ainda subindo: a tela padrao serve */ }
  })();

  document.getElementById("register-form").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const tok = await api("/auth/register", { method: "POST", body: Object.fromEntries(fd) });
      saveToken(tok.access_token);
      state.user = await api("/auth/me");
      try { const wss = await api("/workspaces"); state.workspace = wss?.[0] || null; } catch {}
      await enterApp();
    } catch (err) { document.getElementById("auth-error").textContent = err.message; }
  });

  document.getElementById("logout-btn")?.addEventListener("click", () => {
    clearToken();
    state.user = null;
    show("auth");
  });
}

function show(view) {
  document.querySelectorAll("[data-view]").forEach(el => {
    if (el.dataset.view === view || el.id === "app") el.classList.remove("hidden");
    else el.classList.add("hidden");
  });
  // Lock viewport para app (sidebars fixas, main scrolla).
  // Auth/loading scrollam natural para caber em telas pequenas.
  document.body.classList.toggle("app-active", view === "app");
}

// ==================== INBOX ====================
const INBOX_READ_KEY = "visiquost.inbox.readCursor";  // ISO timestamp of latest read
function _getReadCursor() { return localStorage.getItem(INBOX_READ_KEY) || "1970-01-01T00:00:00Z"; }
function _setReadCursor(ts) { localStorage.setItem(INBOX_READ_KEY, ts); }

async function refreshInboxBadge() {
  try {
    const page = await api("/activities?limit=50");
    const cursor = new Date(_getReadCursor());
    const unread = (page.items || []).filter(a => new Date(a.occurred_at) > cursor).length;
    const badge = document.getElementById("inbox-badge");
    if (!badge) return;
    if (unread > 0) {
      badge.textContent = unread > 99 ? "99+" : unread;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  } catch {}
}

async function openInbox() {
  const inbox = document.getElementById("inbox");
  const list = document.getElementById("inbox-list");
  if (!inbox || !list) return;
  inbox.classList.remove("hidden");
  list.innerHTML = `<li class="empty">${t("loading") || "…"}</li>`;
  try {
    const page = await api("/activities?limit=50");
    const cursor = new Date(_getReadCursor());
    const items = page.items || [];
    if (!items.length) {
      const isPT = (state.lang || "pt") === "pt";
      list.innerHTML = `<li class="empty">
        <div class="empty-ico">📥</div>
        <div class="empty-title">${isPT ? "Caixa vazia" : "Inbox empty"}</div>
        <div class="empty-hint">${isPT ? "Atividades novas aparecem aqui — criações, edições, deleções." : "New activity shows here — creates, edits, deletes."}</div>
      </li>`;
      return;
    }
    list.innerHTML = "";
    const ICON = {
      created: "➕", updated: "✏️", deleted: "🗑️",
      call: "📞", email: "✉️", won: "🏆", lost: "💔",
    };
    for (const a of items) {
      const li = document.createElement("li");
      const unread = new Date(a.occurred_at) > cursor;
      li.className = unread ? "unread" : "";
      const when = new Date(a.occurred_at);
      li.innerHTML = `
        <div style="display:flex;align-items:flex-start;gap:10px;">
          <span style="font-size:1.15em;">${ICON[a.kind] || "•"}</span>
          <div style="flex:1;min-width:0;">
            <div><strong>${escapeHtml(a.kind)}</strong> ${escapeHtml(a.subject_type || "")}${a.summary ? " — " + escapeHtml(a.summary) : ""}</div>
            <div class="inbox-when" title="${when.toLocaleString()}">${timeAgo(when)}</div>
          </div>
        </div>
      `;
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li class="error">${t("t_error")}: ${err.message}</li>`;
  }
}

function bindInbox() {
  document.getElementById("open-inbox")?.addEventListener("click", openInbox);
  document.getElementById("inbox-close")?.addEventListener("click", () => {
    document.getElementById("inbox")?.classList.add("hidden");
  });
  document.getElementById("inbox-mark-read")?.addEventListener("click", () => {
    _setReadCursor(new Date().toISOString());
    refreshInboxBadge();
    openInbox();  // re-render without unread highlights
  });
  // Poll every 60s
  setInterval(refreshInboxBadge, 60_000);
  refreshInboxBadge();
}

// ==================== DASHBOARD WINDOW FILTER ====================
state.dashboardWindow = 30;
function bindDashboardWindow() {
  document.querySelectorAll("#dashboard-window .chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("#dashboard-window .chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.dashboardWindow = parseInt(chip.dataset.window, 10);
      loadDashboard();
    });
  });
  document.getElementById("dashboard-refresh")?.addEventListener("click", () => {
    const btn = document.getElementById("dashboard-refresh");
    if (btn) { btn.style.animation = "spin 600ms linear"; setTimeout(() => btn.style.animation = "", 600); }
    loadDashboard();
    refreshInboxBadge();
  });
}

// ==================== TABLE SORT (client-side) ====================
// Attach click handlers to <th> in a table — reads its data-key attr and
// sorts the rendered <tbody> rows on that key. Toggles asc/desc.
function _applySort(table, colIdx, dir) {
  const ths = table.querySelectorAll("thead th");
  ths.forEach(x => {
    delete x.dataset.sortDir;
    const ind = x.querySelector(".sort-ind");
    if (ind) ind.remove();
  });
  const th = ths[colIdx];
  if (!th) return;
  th.dataset.sortDir = dir;
  const ind = document.createElement("span");
  ind.className = "sort-ind";
  ind.textContent = dir === "asc" ? " ↑" : " ↓";
  th.appendChild(ind);
  const rows = [...table.querySelectorAll("tbody tr")];
  rows.sort((a, b) => {
    const av = (a.children[colIdx]?.textContent || "").trim().toLowerCase();
    const bv = (b.children[colIdx]?.textContent || "").trim().toLowerCase();
    const num = parseFloat(av) - parseFloat(bv);
    if (!isNaN(num) && av && bv) return dir === "asc" ? num : -num;
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
  const tbody = table.querySelector("tbody");
  rows.forEach(r => tbody.appendChild(r));
}

function makeTableSortable(tableId, colKeys) {
  const table = document.getElementById(tableId);
  if (!table) return;
  // Restore last sort from localStorage
  const SORT_KEY = `visiquost.sort.${tableId}`;
  try {
    const saved = JSON.parse(localStorage.getItem(SORT_KEY) || "null");
    if (saved && saved.col != null) _applySort(table, saved.col, saved.dir);
  } catch {}
  const ths = table.querySelectorAll("thead th");
  ths.forEach((th, i) => {
    const key = colKeys[i];
    if (!key) return;
    th.style.cursor = "pointer";
    th.title = state.lang === "pt" ? "Clique para ordenar" : "Click to sort";
    th.addEventListener("click", () => {
      const dir = th.dataset.sortDir === "asc" ? "desc" : "asc";
      _applySort(table, i, dir);
      localStorage.setItem(SORT_KEY, JSON.stringify({ col: i, dir }));
    });
  });
}

// ==================== BULK SELECT (contacts + companies) ====================
const selectedContacts = new Set();
const selectedCompanies = new Set();

function updateCompaniesBulkToolbar() {
  const tb = document.getElementById("companies-bulk-toolbar");
  if (!tb) return;
  const c = document.getElementById("companies-bulk-count");
  if (c) c.textContent = selectedCompanies.size;
  tb.classList.toggle("hidden", selectedCompanies.size === 0);
}

function bindCompaniesBulk() {
  document.getElementById("companies-bulk-clear")?.addEventListener("click", () => {
    selectedCompanies.clear();
    document.querySelectorAll(".company-select").forEach(cb => cb.checked = false);
    const all = document.getElementById("companies-select-all"); if (all) all.checked = false;
    updateCompaniesBulkToolbar();
  });
  document.getElementById("companies-bulk-delete")?.addEventListener("click", async () => {
    if (!selectedCompanies.size) return;
    if (!confirm(state.lang === "pt" ? `Apagar ${selectedCompanies.size} empresas?` : `Delete ${selectedCompanies.size} companies?`)) return;
    for (const id of selectedCompanies) {
      try { await api(`/companies/${id}`, { method: "DELETE" }); } catch {}
    }
    toast(state.lang === "pt" ? `🗑 ${selectedCompanies.size} apagadas` : `🗑 ${selectedCompanies.size} deleted`, "success");
    selectedCompanies.clear();
    updateCompaniesBulkToolbar();
    await loadCompanies();
  });
  document.getElementById("companies-bulk-export")?.addEventListener("click", async () => {
    if (!selectedCompanies.size) return;
    try {
      const full = await api("/companies?limit=200");
      const wanted = new Set([...selectedCompanies]);
      const rows = (full.items || []).filter(c => wanted.has(c.id)).map(c => ({
        name: c.name || "", domain: c.domain || "", industry: c.industry || "", website: c.website || "",
      }));
      downloadCsv(`companies-selection-${new Date().toISOString().slice(0,10)}.csv`, rows);
      toast(state.lang === "pt" ? `⬇ ${rows.length} exportadas` : `⬇ ${rows.length} exported`, "success");
    } catch (err) { toast(err.message, "error"); }
  });
}
function updateBulkToolbar() {
  const tb = document.getElementById("contacts-bulk-toolbar");
  if (!tb) return;
  const c = document.getElementById("contacts-bulk-count");
  if (c) c.textContent = selectedContacts.size;
  tb.classList.toggle("hidden", selectedContacts.size === 0);
}
function bindContactBulk() {
  const all = document.getElementById("contacts-select-all");
  if (all) {
    all.addEventListener("change", () => {
      document.querySelectorAll(".contact-select").forEach(cb => {
        cb.checked = all.checked;
        if (all.checked) selectedContacts.add(cb.dataset.id);
        else selectedContacts.delete(cb.dataset.id);
      });
      updateBulkToolbar();
    });
  }
  document.getElementById("contacts-bulk-clear")?.addEventListener("click", () => {
    selectedContacts.clear();
    document.querySelectorAll(".contact-select").forEach(cb => cb.checked = false);
    const all2 = document.getElementById("contacts-select-all"); if (all2) all2.checked = false;
    updateBulkToolbar();
  });
  document.getElementById("contacts-bulk-delete")?.addEventListener("click", async () => {
    if (!selectedContacts.size) return;
    if (!confirm(state.lang === "pt" ? `Apagar ${selectedContacts.size} contatos?` : `Delete ${selectedContacts.size} contacts?`)) return;
    try {
      const r = await api("/contacts/bulk-delete", { method: "POST", body: { ids: [...selectedContacts] } });
      toast(state.lang === "pt" ? `🗑 ${r.deleted} apagados` : `🗑 ${r.deleted} deleted`, "success");
      selectedContacts.clear();
      updateBulkToolbar();
      await loadContacts();
    } catch (err) { toast(err.message, "error"); }
  });
  document.getElementById("contacts-bulk-export")?.addEventListener("click", async () => {
    if (!selectedContacts.size) return;
    try {
      // Pull full page (up to 500) then filter to selection — server has no bulk-fetch endpoint
      const full = await api("/contacts?limit=200");
      const wanted = new Set([...selectedContacts]);
      const rows = (full.items || []).filter(c => wanted.has(c.id)).map(c => ({
        first_name: c.first_name || "", last_name: c.last_name || "",
        email: c.email || "", phone: c.phone || "", job_title: c.job_title || "",
      }));
      downloadCsv(`contacts-selection-${new Date().toISOString().slice(0,10)}.csv`, rows);
      toast(state.lang === "pt" ? `⬇ ${rows.length} exportados` : `⬇ ${rows.length} exported`, "success");
    } catch (err) { toast(err.message, "error"); }
  });
}

async function enterApp() {
  show("app");
  const email = state.user?.email || "";
  const emailEl = document.getElementById("user-email"); if (emailEl) emailEl.textContent = email;
  const wsEl = document.getElementById("workspace-name");
  if (wsEl) {
    // Small green pulse dot + workspace name + "Local" tag reinforces the
    // 100%-local promise. Uses innerHTML because we're composing markup.
    const name = escapeHtml(state.workspace?.name || "");
    wsEl.innerHTML = `<span class="local-dot" title="Rodando 100% local"></span>${name}<span class="local-tag" title="Zero cloud, tudo na sua máquina">local</span>`;
  }
  const avEl = document.getElementById("user-avatar");
  if (avEl) avEl.textContent = (state.user?.full_name || email || "?").trim()[0]?.toUpperCase() || "?";
  const greetEl = document.getElementById("dashboard-greeting");
  if (greetEl) {
    const h = new Date().getHours();
    const greet = h < 12 ? t("p_greeting_morning") : h < 18 ? t("p_greeting_afternoon") : t("p_greeting_evening");
    const name = state.user?.full_name || email.split("@")[0] || "";
    // JARVIS-style: crisp, situationally aware. No emoji noise.
    greetEl.textContent = `${greet}, ${name}. Jarvis à disposição.`;
  }
  bindNav();
  bindJarvis();
  bindCreateButtons();
  bindIoButtons();
  bindDrawer();
  bindCmdK();
  bindOverlayClose();
  bindShortcuts();
  bindHelpModal();
  bindInbox();
  bindDashboardWindow();
  bindContactBulk();
  bindCompaniesBulk();
  bindContactSavedViews();
  bindJarvisHero();
  bindConversationsList();
  bindThemeToggle();
  bindLanguageToggle();
  bindTaskFilters();
  applyStaticI18n();
  // loadDashboard tambem popula badges do menu, pegada em disco e preferencias
  // do workspace — roda sempre, independente da secao aberta.
  await loadDashboard();
  if (state.page !== "dashboard") gotoPage(state.page);
}

function applyStaticI18n() {
  const map = {
    "dashboard": "nav_dashboard", "contacts": "nav_contacts", "companies": "nav_companies",
    "opportunities": "nav_opportunities", "leads": "nav_leads", "kanban": "nav_kanban",
    "tasks": "nav_tasks", "meetings": "nav_meetings", "automations": "nav_automations", "integrations": "nav_integrations",
  };
  document.querySelectorAll(".nav-item").forEach(btn => {
    const page = btn.dataset.page;
    if (map[page]) {
      const ico = btn.querySelector(".ico")?.outerHTML || "";
      btn.innerHTML = `${ico}${t(map[page])}`;
    }
  });

  // Sidebar buttons
  const seed = document.getElementById("seed-demo-btn"); if (seed) seed.textContent = t("menu_seed");
  const exp = document.getElementById("export-btn"); if (exp) exp.textContent = t("menu_export");
  const imp = document.querySelector('label[for="import-file"], .menu-btn input[type="file"]')?.parentElement;
  if (imp) imp.childNodes[0].textContent = t("menu_import") + " ";
  const themeBtn = document.getElementById("theme-toggle"); if (themeBtn) themeBtn.textContent = t("menu_theme");
  const logout = document.getElementById("logout-btn"); if (logout) logout.textContent = t("menu_logout");

  // cmdk hint
  const cmdk = document.getElementById("open-cmdk");
  if (cmdk) cmdk.querySelector("span").textContent = t("cmdk_hint");

  // Quick buttons
  const qmap = {
    "resumo da semana": "quick_week", "week summary": "quick_week",
    "pipeline": "quick_pipeline", "tarefas atrasadas": "quick_overdue",
    "overdue tasks": "quick_overdue", "forecast": "quick_forecast", "help": "quick_help",
  };
  document.querySelectorAll(".qbtn").forEach(b => {
    const key = qmap[b.dataset.quick];
    if (key) b.textContent = t(key);
  });

  // Jarvis input placeholder
  const ji = document.getElementById("jarvis-input");
  if (ji) ji.setAttribute("placeholder", t("jarvis_placeholder"));

  // Welcome
  const welc = document.querySelector(".jarvis-welcome");
  if (welc) {
    welc.querySelector(".welcome-text strong").textContent = t("jarvis_welcome_title");
    welc.querySelector(".welcome-text p").textContent = t("jarvis_welcome_body");
  }

  // Task filter chips
  const tmap = { all: "task_all", open: "task_open", overdue: "task_overdue", done: "task_done" };
  document.querySelectorAll("[data-task-filter]").forEach(c => {
    c.textContent = t(tmap[c.dataset.taskFilter] || "task_all");
  });

  // Page headers
  const headings = {
    "page-dashboard": "nav_dashboard", "page-contacts": "nav_contacts",
    "page-companies": "nav_companies", "page-opportunities": "nav_opportunities",
    "page-leads": "nav_leads", "page-kanban": "nav_kanban", "page-tasks": "nav_tasks",
    "page-meetings": "nav_meetings", "page-automations": "nav_automations", "page-integrations": "nav_integrations",
  };
  for (const [id, key] of Object.entries(headings)) {
    const h = document.querySelector(`#${id} h2`);
    if (h) h.textContent = t(key);
  }

  // Add buttons
  const addMap = {
    "add-contact-btn": "add_contact", "add-company-btn": "add_company",
    "add-opportunity-btn": "add_opp", "add-lead-btn": "add_lead",
    "add-task-btn": "add_task", "add-meeting-btn": "add_meeting",
    "add-workflow-btn": "add_workflow", "add-rule-btn": "add_rule",
    "toggle-rules-btn": "scoring_rules", "recalc-btn": "recalc",
  };
  for (const [id, key] of Object.entries(addMap)) {
    const b = document.getElementById(id);
    if (b) b.textContent = t(key);
  }

  const cs = document.getElementById("contact-search"); if (cs) cs.setAttribute("placeholder", t("search_contacts"));
  const cos = document.getElementById("company-search"); if (cos) cos.setAttribute("placeholder", t("search_companies"));

  const dn = document.querySelector(".drawer-section:nth-of-type(1) h4"); if (dn) dn.textContent = t("drawer_notes");
  const da = document.querySelector(".drawer-section:nth-of-type(2) h4"); if (da) da.textContent = t("drawer_activity");
  const dni = document.getElementById("drawer-note-input"); if (dni) dni.setAttribute("placeholder", t("drawer_add_note"));

  const mc = document.getElementById("modal-cancel"); if (mc) mc.textContent = t("modal_cancel");
  const ms = document.getElementById("modal-save"); if (ms) ms.textContent = t("modal_save");
}

function bindIoButtons() {
  document.getElementById("seed-demo-btn")?.addEventListener("click", async () => {
    if (!confirm(t("c_seed"))) return;
    try {
      const r = await api("/workspaces/current/seed-demo", { method: "POST" });
      if (r.status === "skipped") { toast(t("t_seed_skipped"), "warn"); return; }
      toast(t("t_seeded"), "success");
      routes[state.page]?.();
    } catch (err) { toast(`${t("t_seed_failed")}: ${err.message}`, "error"); }
  });

  document.getElementById("export-btn")?.addEventListener("click", async () => {
    try {
      const resp = await fetch(`${API}/workspaces/current/export`, {
        headers: { Authorization: `Bearer ${state.token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `visiquost-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast(t("t_exported"), "success");
    } catch (err) { toast(`${t("t_export_failed")}: ${err.message}`, "error"); }
  });

  document.getElementById("export-md-btn")?.addEventListener("click", async () => {
    try {
      const resp = await fetch(`${API}/jarvis/workspace-summary.md`, {
        headers: { Authorization: `Bearer ${state.token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `visiquost-summary-${new Date().toISOString().slice(0, 10)}.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast(t("t_exported"), "success");
    } catch (err) { toast(`${t("t_export_failed")}: ${err.message}`, "error"); }
  });

  document.getElementById("import-file")?.addEventListener("change", async ev => {
    const file = ev.target.files?.[0];
    if (!file) return;
    if (!confirm(t("c_import", file.name))) { ev.target.value = ""; return; }
    try {
      const text = await file.text();
      const envelope = JSON.parse(text);
      const res = await api("/workspaces/current/import", { method: "POST", body: envelope });
      toast(`${t("t_imported")}: ${JSON.stringify(res.counts)}`, "success");
      routes[state.page]?.();
    } catch (err) { toast(`${t("t_import_failed")}: ${err.message}`, "error"); }
    finally { ev.target.value = ""; }
  });
}

function bindThemeToggle() {
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    applyTheme();
    toast(state.theme === "dark" ? "🌙 Dark" : "☀️ Light", "info", 1500);
  });
}

function bindLanguageToggle() {
  // We hijack Ctrl+Shift+L and a small on-hover selector via right-clicking the theme button? Simpler: add a small button in the sidebar footer.
  // Actually add an inline "toggle EN/PT" button next to the theme.
  const themeBtn = document.getElementById("theme-toggle");
  if (themeBtn && !document.getElementById("lang-toggle")) {
    const langBtn = document.createElement("button");
    langBtn.id = "lang-toggle";
    langBtn.className = "menu-btn";
    langBtn.textContent = `${t("menu_lang")} — ${state.lang.toUpperCase()}`;
    langBtn.addEventListener("click", () => {
      state.lang = state.lang === "en" ? "pt" : "en";
      localStorage.setItem(LANG_KEY, state.lang);
      langBtn.textContent = `${t("menu_lang")} — ${state.lang.toUpperCase()}`;
      applyStaticI18n();
      applyLang();
      routes[state.page]?.();
      toast(state.lang === "pt" ? "Idioma: Português (BR)" : "Language: English", "info", 1500);
    });
    themeBtn.parentElement.insertBefore(langBtn, themeBtn);
  }
}

function bindNav() {
  document.querySelectorAll(".nav-item[data-page]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach(x => x.classList.remove("active"));
      btn.classList.add("active");
      state.page = btn.dataset.page;
      try { localStorage.setItem(PAGE_KEY, state.page); } catch { /* modo privado */ }
      document.querySelectorAll(".page").forEach(p => p.classList.add("hidden"));
      document.getElementById(`page-${state.page}`).classList.remove("hidden");
      routes[state.page]?.();
      // Auto-close mobile sidebar after nav
      document.body.classList.remove("sidebar-open");
    });
  });
  document.getElementById("nav-more-toggle")?.addEventListener("click", () => {
    const wrap = document.getElementById("nav-more");
    const btn = document.getElementById("nav-more-toggle");
    wrap.classList.toggle("hidden");
    btn.classList.toggle("open");
  });
  document.getElementById("hamburger")?.addEventListener("click", () => {
    document.body.classList.toggle("sidebar-open");
  });
  document.getElementById("sidebar-scrim")?.addEventListener("click", () => {
    document.body.classList.remove("sidebar-open");
  });
}

const routes = {
  dashboard: loadDashboard,
  contacts: loadContacts,
  companies: loadCompanies,
  opportunities: loadOpportunities,
  leads: loadLeads,
  kanban: loadKanban,
  tasks: loadTasks,
  meetings: loadMeetings,
  automations: loadAutomations,
  integrations: loadIntegrations,
  device: loadDevice,
  jarvis: loadJarvisHero,
  sentinela: loadSentinela,
};

async function loadConversationsList() {
  const list = document.getElementById("jarvis-convos-list");
  if (!list) return;
  try {
    const page = await api("/jarvis/conversations?limit=30");
    let items = page.items || [];
    // Bring favorites to the top
    const starred = new Set(JSON.parse(localStorage.getItem("visiquost.convo.starred") || "[]"));
    items = items.slice().sort((a, b) => (starred.has(b.id) ? 1 : 0) - (starred.has(a.id) ? 1 : 0));
    list.innerHTML = "";
    for (const c of items) {
      const li = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = c.title || (state.lang === "pt" ? "Sem título" : "Untitled");
      label.title = new Date(c.updated_at || c.created_at).toLocaleString();
      li.appendChild(label);
      if (c.id === state.conversation_id) li.classList.add("active");
      li.addEventListener("click", async e => {
        if (e.target.closest(".convo-del")) return;
        if (e.target.classList.contains("convo-rename-input")) return;
        state.conversation_id = c.id;
        localStorage.setItem(CONV_KEY, c.id);
        document.getElementById("jarvis-hero-log").innerHTML = "";
        await loadJarvisHero();
        loadConversationsList();
      });
      // Double-click to rename
      label.addEventListener("dblclick", ev => {
        ev.stopPropagation();
        const input = document.createElement("input");
        input.type = "text";
        input.value = label.textContent;
        input.className = "convo-rename-input";
        label.replaceWith(input);
        input.focus(); input.select();
        const finish = async (save) => {
          if (save && input.value.trim() && input.value.trim() !== c.title) {
            try {
              await api(`/jarvis/conversations/${c.id}`, { method: "PATCH", body: { title: input.value.trim() } });
              toast(state.lang === "pt" ? "Renomeada" : "Renamed", "success", 1200);
            } catch (err) { toast(err.message, "error"); }
          }
          loadConversationsList();
        };
        input.addEventListener("keydown", e => {
          if (e.key === "Enter") { e.preventDefault(); finish(true); }
          else if (e.key === "Escape") { e.preventDefault(); finish(false); }
        });
        input.addEventListener("blur", () => finish(true));
      });
      // Favorite star (localStorage)
      const starKey = "visiquost.convo.starred";
      const starred = JSON.parse(localStorage.getItem(starKey) || "[]");
      const isStar = starred.includes(c.id);
      const star = document.createElement("button");
      star.className = "convo-star" + (isStar ? " starred" : "");
      star.innerHTML = isStar ? "★" : "☆";
      star.title = state.lang === "pt" ? "Favoritar" : "Star";
      star.addEventListener("click", e => {
        e.stopPropagation();
        const cur = JSON.parse(localStorage.getItem(starKey) || "[]");
        const next = cur.includes(c.id) ? cur.filter(x => x !== c.id) : [c.id, ...cur];
        localStorage.setItem(starKey, JSON.stringify(next));
        loadConversationsList();
      });
      li.appendChild(star);

      // Export .md
      const exp = document.createElement("button");
      exp.className = "convo-export";
      exp.textContent = "⬇";
      exp.title = state.lang === "pt" ? "Exportar .md" : "Export .md";
      exp.addEventListener("click", async e => {
        e.stopPropagation();
        try {
          const resp = await fetch(`${API}/jarvis/conversations/${c.id}/export.md`, {
            headers: { Authorization: `Bearer ${state.token}` },
          });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `${(c.title || "conversa").replace(/[^\w\-]+/g, "_")}.md`;
          a.click();
          URL.revokeObjectURL(url);
          toast(state.lang === "pt" ? "Exportada" : "Exported", "success", 1500);
        } catch (err) { toast(err.message, "error"); }
      });
      li.appendChild(exp);

      const del = document.createElement("button");
      del.className = "convo-del";
      del.textContent = "×";
      del.title = state.lang === "pt" ? "Apagar conversa" : "Delete conversation";
      del.addEventListener("click", async e => {
        e.stopPropagation();
        if (!confirm(state.lang === "pt" ? "Apagar esta conversa?" : "Delete this conversation?")) return;
        try {
          await api(`/jarvis/conversations/${c.id}`, { method: "DELETE" });
          if (c.id === state.conversation_id) {
            state.conversation_id = null;
            localStorage.removeItem(CONV_KEY);
            document.getElementById("jarvis-new-convo")?.click();
          }
          loadConversationsList();
          toast(state.lang === "pt" ? "🗑 Apagada" : "🗑 Deleted", "success", 1500);
        } catch (err) { toast(err.message, "error"); }
      });
      li.appendChild(del);
      list.appendChild(li);
    }
    if (!items.length) {
      list.innerHTML = `<li class="empty">${state.lang === "pt" ? "Sem conversas ainda" : "No conversations yet"}</li>`;
    }
  } catch {}
}

async function searchMessages(q) {
  const list = document.getElementById("jarvis-convos-list");
  if (!list) return;
  if (!q.trim()) { loadConversationsList(); return; }
  try {
    const r = await api(`/jarvis/messages/search?q=${encodeURIComponent(q)}&limit=20`);
    list.innerHTML = "";
    if (!r.hits.length) {
      list.innerHTML = `<li class="empty">${state.lang === "pt" ? "Nada encontrado" : "No matches"}</li>`;
      return;
    }
    for (const hit of r.hits) {
      const li = document.createElement("li");
      li.innerHTML = `<div style="font-weight:500;font-size:0.85em;">${escapeHtml(hit.conversation_title)}</div>
                      <div class="subtle" style="font-size:0.75em;">${escapeHtml(hit.snippet)}</div>`;
      li.addEventListener("click", async () => {
        state.conversation_id = hit.conversation_id;
        localStorage.setItem(CONV_KEY, hit.conversation_id);
        document.getElementById("jarvis-hero-log").innerHTML = "";
        document.getElementById("jarvis-convo-search").value = "";
        await loadJarvisHero();
        loadConversationsList();
      });
      list.appendChild(li);
    }
  } catch {}
}

function bindConversationsList() {
  document.getElementById("jarvis-convo-search")?.addEventListener("input", debounce(e => searchMessages(e.target.value), 300));
  document.getElementById("jarvis-new-convo")?.addEventListener("click", async () => {
    // "Start fresh" = clear conversation_id + log; next message creates a new one
    state.conversation_id = null;
    localStorage.removeItem(CONV_KEY);
    const log = document.getElementById("jarvis-hero-log");
    if (log) {
      log.innerHTML = `
        <div class="jarvis-hero-welcome">
          <div class="hero-mark">✨</div>
          <h2>${state.lang === "pt" ? "Nova conversa" : "New conversation"}</h2>
          <p class="subtle">${state.lang === "pt" ? "Comece do zero." : "Start fresh."}</p>
        </div>
      `;
    }
    document.getElementById("jarvis-hero-input")?.focus();
    loadConversationsList();
  });
}

function refreshContextChip() {
  const chip = document.getElementById("jarvis-context-chip");
  const label = document.getElementById("context-chip-label");
  if (!chip || !label) return;
  const ctx = state.lastEntityContext;
  const active = ctx && ctx.expires > Date.now();
  if (!active) {
    chip.classList.add("hidden");
    return;
  }
  chip.classList.remove("hidden");
  const KIND_LABEL_PT = { contact: "Contato", company: "Empresa", opportunity: "Oportunidade", lead: "Lead" };
  const KIND_LABEL_EN = { contact: "Contact", company: "Company", opportunity: "Opportunity", lead: "Lead" };
  const map = state.lang === "pt" ? KIND_LABEL_PT : KIND_LABEL_EN;
  label.textContent = `${map[ctx.type] || ctx.type}: ${ctx.name}`;
}

async function loadJarvisHero() {
  const log = document.getElementById("jarvis-hero-log");
  if (!log) return;
  refreshContextChip();
  loadConversationsList();
  // Only load history on first visit (or if empty)
  const hasMessages = log.querySelector(".jarvis-msg");
  if (state.conversation_id && !hasMessages) {
    try {
      const history = await api(`/jarvis/conversations/${state.conversation_id}/messages`);
      const welcome = log.querySelector(".jarvis-hero-welcome");
      if (history && history.length > 0 && welcome) welcome.remove();
      for (const m of history || []) {
        if (m.role === "user" || m.role === "assistant") {
          appendHeroMessage(m.role, m.content, m.fallback, m.tool_calls, m.intent);
        }
      }
    } catch {}
  }
  setTimeout(() => document.getElementById("jarvis-hero-input")?.focus(), 100);
}

// Very light markdown → HTML. Only for assistant messages so we don't leak
// user input into inline HTML.
function renderLightMarkdown(text) {
  let html = escapeHtml(text);
  // Bold **x**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Inline code `x`
  html = html.replace(/`([^`\n]+?)`/g, "<code>$1</code>");
  // Headers: line starting with ## or #
  html = html.replace(/^##\s+(.+)$/gm, "<div class='md-h3'>$1</div>");
  html = html.replace(/^#\s+(.+)$/gm, "<div class='md-h2'>$1</div>");
  // Bullet lines: `  • foo` or `* foo` or `- foo`
  const lines = html.split("\n");
  const out = [];
  let inList = false;
  for (const line of lines) {
    const m = line.match(/^\s*[•*\-]\s+(.+)$/);
    if (m) {
      if (!inList) { out.push("<ul class='md-list'>"); inList = true; }
      out.push(`<li>${m[1]}</li>`);
    } else {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(line);
    }
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function appendHeroMessage(role, text, fallback, toolCalls, intent) {
  const log = document.getElementById("jarvis-hero-log");
  if (!log) return;
  const welcome = log.querySelector(".jarvis-hero-welcome");
  if (welcome && role === "user") welcome.remove();
  const wrap = document.createElement("div");
  wrap.className = "jarvis-hero-turn";
  const msg = document.createElement("div");
  msg.className = `jarvis-msg ${role}${fallback ? " fallback" : ""}`;
  if (role === "assistant") {
    msg.innerHTML = renderLightMarkdown(text);
    // Copy button
    const copy = document.createElement("button");
    copy.className = "msg-copy";
    copy.textContent = "📋";
    copy.title = state.lang === "pt" ? "Copiar" : "Copy";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(text);
        toast(state.lang === "pt" ? "Copiado" : "Copied", "success", 1200);
      } catch { toast("Clipboard unavailable", "error"); }
    });
    msg.appendChild(copy);
  } else {
    msg.textContent = text;
  }
  wrap.appendChild(msg);
  // If it's an agent_plan reply, render its steps as visual checklist cards
  if (role === "assistant" && intent === "agent_plan" && Array.isArray(toolCalls)) {
    const stepsByIdx = {};
    for (const tc of toolCalls) {
      const idx = tc.step_index;
      if (!idx) continue;
      stepsByIdx[idx] = stepsByIdx[idx] || { intent: tc.step_intent, tools: [] };
      stepsByIdx[idx].tools.push(tc.name);
    }
    const idxs = Object.keys(stepsByIdx).sort((a, b) => parseInt(a) - parseInt(b));
    if (idxs.length) {
      const plan = document.createElement("div");
      plan.className = "plan-card";
      const label = state.lang === "pt" ? "Plano executado" : "Plan executed";
      plan.innerHTML = `<div class="plan-header">📋 ${label}</div>` +
        idxs.map(i => {
          const s = stepsByIdx[i];
          const okMark = s.intent ? "✓" : "⚠";
          const okCls = s.intent ? "ok" : "warn";
          return `<div class="plan-step ${okCls}">
            <span class="plan-step-mark">${okMark}</span>
            <div class="plan-step-body">
              <div class="plan-step-title">Passo ${i}${s.intent ? " · " + escapeHtml(s.intent) : ""}</div>
              ${s.tools.length ? `<div class="plan-step-tools">${s.tools.map(t => `<code>${escapeHtml(t)}</code>`).join(" ")}</div>` : ""}
            </div>
          </div>`;
        }).join("");
      wrap.appendChild(plan);
    }
  }
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

// Contextual suggestions after each reply
const SUGGESTIONS = {
  agent_plan: ["resumo da semana", "top 5 oportunidades", "tarefas atrasadas"],
  weekly_digest: ["planeje minha semana", "top oportunidades", "leads parados"],
  summarize_pipeline: ["revenue by stage", "top 5 oportunidades", "oportunidades fechando este mês"],
  top_opportunities: ["planeje minha semana", "revenue by stage", "leads parados"],
  plan_week: ["top 5 oportunidades", "weekly digest", "tarefas atrasadas"],
  overdue_tasks: ["planeje minha semana", "week summary"],
  create_task: ["planeje minha semana", "top 5 oportunidades"],
  schedule_meeting: ["minha agenda", "planeje minha semana"],
  read_calendar: ["planeje minha semana", "agende reunião", "reuniões hoje"],
  scan_work_dir: ["importe contatos", "leia arquivo notes.txt"],
  auto_import_contacts: ["meus arquivos"],
  greeting: ["planeje minha semana", "resumo da semana", "top 5 oportunidades"],
  help: ["resumo da semana", "top 5 oportunidades", "planeje minha semana"],
  __default: ["resumo da semana", "planeje minha semana", "top oportunidades"],
};
function renderSuggestions(intent) {
  const wrap = document.getElementById("jarvis-suggestions");
  if (!wrap) return;
  const list = SUGGESTIONS[intent] || SUGGESTIONS.__default;
  wrap.innerHTML = list.map(s =>
    `<button class="qbtn" data-suggest="${escapeHtml(s)}">${escapeHtml(s)}</button>`
  ).join("");
}

// Voice input via Web Speech API
function initVoice(onFinalText) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = document.getElementById("jarvis-mic");
  if (!SR || !mic) return null;
  mic.classList.remove("hidden");
  const rec = new SR();
  rec.lang = state.lang === "pt" ? "pt-BR" : "en-US";
  rec.continuous = false;
  rec.interimResults = false;
  let listening = false;
  mic.addEventListener("click", () => {
    if (listening) { rec.stop(); return; }
    try { rec.start(); listening = true; mic.classList.add("recording"); }
    catch (e) { toast(e.message, "error"); }
  });
  rec.onresult = ev => {
    const text = ev.results[0]?.[0]?.transcript;
    if (text) onFinalText(text);
  };
  rec.onend = () => { listening = false; mic.classList.remove("recording"); };
  rec.onerror = ev => { listening = false; mic.classList.remove("recording"); toast("Voz: " + ev.error, "warn", 1800); };
  return rec;
}

function bindJarvisHero() {
  const form = document.getElementById("jarvis-hero-form");
  const input = document.getElementById("jarvis-hero-input");
  const log = document.getElementById("jarvis-hero-log");
  if (!form || !input || !log) return;

  // Suggestion click delegation
  const sug = document.getElementById("jarvis-suggestions");
  sug?.addEventListener("click", e => {
    const b = e.target.closest("[data-suggest]");
    if (b) { input.value = b.dataset.suggest; form.dispatchEvent(new Event("submit")); }
  });

  // Voice input
  initVoice(text => { input.value = text; form.dispatchEvent(new Event("submit")); });

  // Input history (↑/↓)
  const HISTORY_KEY = "visiquost.chat.history";
  let history = [];
  try { history = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); } catch { history = []; }
  let histPos = -1;
  input.addEventListener("keydown", e => {
    if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !e.shiftKey && !e.ctrlKey) {
      // Only navigate history if input is empty or matches current history entry
      if (input.value && histPos < 0) return;
      if (e.key === "ArrowUp") {
        if (histPos + 1 < history.length) { histPos++; input.value = history[histPos] || ""; e.preventDefault(); }
      } else {
        if (histPos > 0) { histPos--; input.value = history[histPos] || ""; e.preventDefault(); }
        else { histPos = -1; input.value = ""; }
      }
    }
  });
  form.addEventListener("submit", () => {
    const msg = input.value.trim();
    if (msg && msg !== history[0]) { history.unshift(msg); history = history.slice(0, 50); localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); }
    histPos = -1;
  });

  // Drag-drop upload
  const layout = document.querySelector(".jarvis-hero-layout") || form.parentElement;
  if (layout) {
    let dragCounter = 0;
    layout.addEventListener("dragenter", ev => {
      ev.preventDefault();
      if (ev.dataTransfer?.types?.includes("Files")) {
        dragCounter++;
        layout.classList.add("drop-target");
      }
    });
    layout.addEventListener("dragover", ev => { ev.preventDefault(); });
    layout.addEventListener("dragleave", () => {
      dragCounter = Math.max(0, dragCounter - 1);
      if (dragCounter === 0) layout.classList.remove("drop-target");
    });
    // Paste image from clipboard (screenshots)
    input.addEventListener("paste", async ev => {
      const items = [...(ev.clipboardData?.items || [])];
      const image = items.find(it => it.type.startsWith("image/"));
      if (!image) return;
      ev.preventDefault();
      const file = image.getAsFile();
      if (!file) return;
      const ext = (file.type.split("/")[1] || "png").split(";")[0];
      const named = new File([file], `screenshot-${Date.now()}.${ext}`, { type: file.type });
      try {
        const fd = new FormData();
        fd.append("file", named);
        const resp = await fetch(`${API}/files/upload`, {
          method: "POST", headers: { Authorization: `Bearer ${state.token}` }, body: fd,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const j = await resp.json();
        appendHeroMessage("assistant", state.lang === "pt"
          ? `📎 Colado: \`${j.name}\` (${(j.size / 1024).toFixed(1)} KB)`
          : `📎 Pasted: \`${j.name}\` (${(j.size / 1024).toFixed(1)} KB)`,
          false, null, "file_upload");
      } catch (err) { toast(err.message, "error"); }
    });

    layout.addEventListener("drop", async ev => {
      ev.preventDefault();
      dragCounter = 0;
      layout.classList.remove("drop-target");
      const files = [...(ev.dataTransfer?.files || [])];
      if (!files.length) return;
      for (const f of files) {
        try {
          const fd = new FormData();
          fd.append("file", f);
          const resp = await fetch(`${API}/files/upload`, {
            method: "POST",
            headers: { Authorization: `Bearer ${state.token}` },
            body: fd,
          });
          if (!resp.ok) { toast(`❌ ${f.name}: HTTP ${resp.status}`, "error"); continue; }
          const j = await resp.json();
          appendHeroMessage("assistant", state.lang === "pt"
            ? `📎 Recebi \`${j.name}\` (${(j.size / 1024).toFixed(1)} KB). ${j.importable ? "Diga \"importe contatos\" para importar." : "Diga \"leia arquivo " + j.name + "\" para ler."}`
            : `📎 Received \`${j.name}\` (${(j.size / 1024).toFixed(1)} KB). ${j.importable ? "Say \"import contacts\" to import." : "Say \"read file " + j.name + "\" to read."}`,
            false, null, "file_upload");
          toast(`📎 ${j.name}`, "success", 1500);
        } catch (err) { toast(err.message, "error"); }
      }
    });
  }

  // Slash-command interceptor — client-side only
  const handleSlashCommand = (msg) => {
    const cmd = msg.trim().toLowerCase();
    if (cmd === "/help" || cmd === "/?") {
      document.getElementById("help-modal")?.classList.remove("hidden");
      input.value = "";
      return true;
    }
    if (cmd === "/new") {
      document.getElementById("jarvis-new-convo")?.click();
      return true;
    }
    if (cmd === "/clear") {
      log.innerHTML = "";
      input.value = "";
      return true;
    }
    if (cmd.startsWith("/lang ")) {
      const lang = cmd.split(" ")[1];
      if (lang === "pt" || lang === "en") {
        state.lang = lang;
        localStorage.setItem(LANG_KEY, lang);
        applyStaticI18n(); applyLang();
        toast(lang === "pt" ? "Idioma: PT-BR" : "Language: EN", "info", 1500);
      }
      input.value = "";
      return true;
    }
    return false;
  };

  const showTyping = () => {
    const t = document.createElement("div");
    t.className = "jarvis-typing";
    t.id = "jarvis-typing-indicator";
    t.innerHTML = `<span></span><span></span><span></span>`;
    log.appendChild(t);
    log.scrollTop = log.scrollHeight;
  };
  const hideTyping = () => document.getElementById("jarvis-typing-indicator")?.remove();

  let currentAbort = null;

  // Apply implicit entity context: if user says "ele/ela/dele/dela/este/esta/it/them"
  // and we have a fresh entity, expand it inline
  const applyContext = (msg) => {
    const ctx = state.lastEntityContext;
    if (!ctx || ctx.expires < Date.now()) return msg;
    if (/\b(ele|ela|dele|dela|este|esta|esse|essa|isso|it|them|him|her|this\s+one|this\s+contact|this\s+company|essa\s+empresa|esse\s+contato|essa\s+oportunidade)\b/i.test(msg)) {
      return `sobre ${ctx.name}: ${msg}`;
    }
    return msg;
  };

  const sendMsg = async (message) => {
    if (handleSlashCommand(message)) return;
    const original = message;
    const expanded = applyContext(message);
    appendHeroMessage("user", original + (expanded !== original ? ` ‎(→ ${expanded})` : ""));
    input.value = "";
    input.style.height = "auto";
    showTyping();
    // Toggle send → stop
    const sendBtn = form.querySelector("button[type='submit']");
    if (sendBtn) { sendBtn.textContent = "■"; sendBtn.title = "Parar geração"; sendBtn.dataset.mode = "stop"; }
    currentAbort = new AbortController();
    try {
      const body = state.conversation_id ? { message: expanded, conversation_id: state.conversation_id } : { message: expanded };
      const resp = await api("/jarvis/chat", { method: "POST", body });
      if (resp.conversation_id) {
        state.conversation_id = resp.conversation_id;
        localStorage.setItem(CONV_KEY, resp.conversation_id);
      }
      hideTyping();
      appendHeroMessage("assistant", resp.reply, resp.fallback, resp.tool_calls, resp.intent);
      renderSuggestions(resp.intent);
      loadConversationsList();
    } catch (err) {
      hideTyping();
      const aborted = err.name === "AbortError" || err.message?.includes("aborted");
      if (aborted) {
        appendHeroMessage("assistant", state.lang === "pt" ? "(parado)" : "(stopped)", true);
      } else {
        appendHeroMessage("assistant", `${t("t_error")}: ${err.message}`, true);
      }
    } finally {
      if (sendBtn) { sendBtn.textContent = "➤"; sendBtn.title = "Enviar"; sendBtn.dataset.mode = "send"; }
      currentAbort = null;
    }
  };

  form.addEventListener("submit", e => {
    e.preventDefault();
    const btn = form.querySelector("button[type='submit']");
    if (btn?.dataset.mode === "stop" && currentAbort) {
      currentAbort.abort();
      return;
    }
    const message = input.value.trim();
    if (message) sendMsg(message);
  });

  // Context chip clear button
  document.getElementById("context-chip-clear")?.addEventListener("click", () => {
    state.lastEntityContext = null;
    refreshContextChip();
  });
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });
  // Auto-resize textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(200, input.scrollHeight) + "px";
  });
  // Wire quick-example buttons inside the welcome card
  log.addEventListener("click", e => {
    const q = e.target.closest?.(".hero-examples .qbtn");
    if (q) sendMsg(q.dataset.quick);
  });
}

async function openFilePreview(filename) {
  try {
    const r = await api(`/jarvis/read-file?filename=${encodeURIComponent(filename)}`);
    if (r.error) { toast(r.message || r.error, "error"); return; }
    // Show in the existing generic modal
    const modal = document.getElementById("modal");
    document.getElementById("modal-title").textContent = `📄 ${r.name}`;
    const form = document.getElementById("modal-form");
    form.innerHTML = "";
    const pre = document.createElement("pre");
    pre.style.cssText = "max-height:60vh;overflow:auto;white-space:pre-wrap;background:var(--bg-2);padding:12px;border-radius:6px;font-size:0.85em;font-family:var(--font-mono);";
    pre.textContent = r.text + (r.truncated ? "\n\n…(truncado)" : "");
    form.appendChild(pre);
    // Hide save button, only cancel/close
    document.getElementById("modal-save").style.display = "none";
    const restore = () => { document.getElementById("modal-save").style.display = ""; };
    document.getElementById("modal-cancel").onclick = () => { modal.classList.add("hidden"); restore(); };
    document.getElementById("modal-x").onclick = () => { modal.classList.add("hidden"); restore(); };
    modal.classList.remove("hidden");
  } catch (err) { toast(err.message, "error"); }
}

async function loadDevice() {
  const wrap = document.getElementById("device-tools-list");
  if (!wrap) return;
  // Bind refresh button once
  const rb = document.getElementById("device-refresh");
  if (rb && !rb.dataset.wired) {
    rb.dataset.wired = "1";
    rb.addEventListener("click", () => {
      rb.style.animation = "spin 600ms linear";
      setTimeout(() => rb.style.animation = "", 600);
      loadDevice();
    });
  }
  wrap.innerHTML = `<p class="subtle">${t("loading") || "…"}</p>`;
  try {
    const [s, scan] = await Promise.all([
      api("/jarvis/device-status"),
      api("/jarvis/scan-work-dir").catch(() => null),
    ]);
    wrap.innerHTML = "";
    const STATUS_MAP = {
      ready: { icon: "✅", cls: "ok", label: state.lang === "pt" ? "Pronto" : "Ready" },
      not_connected: { icon: "🔌", cls: "warn", label: state.lang === "pt" ? "Não conectado" : "Not connected" },
      not_configured: { icon: "⚙️", cls: "warn", label: state.lang === "pt" ? "Não configurado" : "Not configured" },
      missing_deps: { icon: "⚠️", cls: "danger", label: state.lang === "pt" ? "Dependência faltando" : "Missing dependency" },
      coming_soon: { icon: "🚧", cls: "", label: state.lang === "pt" ? "Em breve" : "Coming soon" },
    };
    // Show scan of work dir first — the "drop files here" hint
    if (scan?.status === "ok") {
      const scanCard = document.createElement("div");
      scanCard.className = "card";
      scanCard.style.gridColumn = "1 / -1";
      const counts = scan.counts || {};
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      // File list with click-to-preview
      const allFiles = [];
      for (const cat of Object.keys(scan.categories || {})) {
        for (const f of scan.categories[cat] || []) allFiles.push({ ...f, cat });
      }
      const hasContacts = (counts.contacts || 0) > 0;
      const pathHint = state.lang === "pt"
        ? `Solte arquivos em <code>${escapeHtml(scan.root)}</code> — VisiQuost lê automaticamente. Suportado: .ics (agenda), .csv (contatos), .vcf (vCard).`
        : `Drop files in <code>${escapeHtml(scan.root)}</code> — VisiQuost reads them automatically. Supported: .ics (calendar), .csv (contacts), .vcf (vCard).`;
      const labels = state.lang === "pt"
        ? { calendars: "📅 Agendas", contacts: "👥 Contatos", docs: "📄 Docs", spreadsheets: "📊 Planilhas", images: "🖼️ Imagens" }
        : { calendars: "📅 Calendars", contacts: "👥 Contacts", docs: "📄 Docs", spreadsheets: "📊 Sheets", images: "🖼️ Images" };
      const chips = Object.entries(counts).filter(([, n]) => n > 0).map(([cat, n]) =>
        `<span class="chip" style="pointer-events:none;">${labels[cat] || cat}: ${n}</span>`
      ).join(" ");
      const importBtn = hasContacts
        ? `<button id="auto-import-btn" class="btn-primary" style="margin-top:12px;">📥 ${state.lang === "pt" ? "Importar contatos detectados" : "Import detected contacts"}</button>`
        : "";
      // File list — click to preview
      const fileList = allFiles.length
        ? `<ul class="device-files">${allFiles.slice(0, 40).map(f =>
            `<li class="device-file-item" data-name="${escapeHtml(f.name)}">
              <span class="device-file-name">${escapeHtml(f.name)}</span>
              <span class="subtle">${(f.size / 1024).toFixed(1)} KB</span>
            </li>`).join("")}${allFiles.length > 40 ? `<li class="subtle">…+${allFiles.length - 40}</li>` : ""}</ul>`
        : "";
      scanCard.innerHTML = `
        <div class="card-header">
          <h3>📂 ${state.lang === "pt" ? "Minha pasta VisiQuost" : "My VisiQuost folder"}</h3>
          <span class="subtle">${total} ${state.lang === "pt" ? "arquivos" : "files"}</span>
        </div>
        <p style="margin-top:0;">${pathHint}</p>
        ${chips ? `<div class="flex-row" style="margin-top:8px;flex-wrap:wrap;">${chips}</div>` : ""}
        ${importBtn}
        ${fileList}
      `;
      wrap.appendChild(scanCard);
      // Wire file preview
      scanCard.querySelectorAll(".device-file-item").forEach(li => {
        li.addEventListener("click", () => openFilePreview(li.dataset.name));
      });
      // Wire the import button (preview → confirm)
      if (hasContacts) {
        setTimeout(() => {
          document.getElementById("auto-import-btn")?.addEventListener("click", async () => {
            try {
              const preview = await api("/jarvis/auto-import-contacts", { method: "POST" });
              const would = preview.would_import || 0;
              if (!would) { toast(state.lang === "pt" ? "Nenhum novo contato" : "No new contacts", "warn"); return; }
              const msg = state.lang === "pt"
                ? `Encontrei ${would} contatos novos. Importar tudo?`
                : `Found ${would} new contacts. Import all?`;
              if (!confirm(msg)) return;
              const done = await api("/jarvis/auto-import-contacts?confirm=true", { method: "POST" });
              toast(`✅ ${done.created} ${state.lang === "pt" ? "contatos importados" : "contacts imported"}`, "success");
              await loadDevice();
            } catch (err) { toast(err.message, "error"); }
          });
        }, 0);
      }
    }
    for (const tool of (s.tools || [])) {
      const st = STATUS_MAP[tool.status] || { icon: "❔", cls: "", label: tool.status };
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
          <div>
            <strong style="font-size:1.02em;">${st.icon} ${escapeHtml(tool.label)}</strong>
            <div class="subtle" style="margin-top:4px;">${escapeHtml(tool.note || "")}</div>
          </div>
          <span class="status-pill ${st.cls}">${escapeHtml(st.label)}</span>
        </div>
      `;
      wrap.appendChild(card);
    }
  } catch (err) {
    wrap.innerHTML = `<p class="error">${t("t_error")}: ${escapeHtml(err.message)}</p>`;
  }
}

// ==================== ONBOARDING ====================
const ONB_KEY = "visiquost.onboarding";
function shouldShowOnboarding(counts) {
  if (localStorage.getItem(ONB_KEY) === "dismissed") return false;
  const total = (counts?.contacts || 0) + (counts?.companies || 0) + (counts?.leads || 0) + (counts?.opportunities || 0);
  return total === 0;
}
function renderOnboarding(counts) {
  const card = document.getElementById("onboarding-card");
  if (!card) return;
  if (!shouldShowOnboarding(counts)) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  const done = JSON.parse(localStorage.getItem(ONB_KEY + ".steps") || "{}");
  ["1", "2", "3"].forEach(n => {
    const li = document.getElementById("onb-" + n);
    if (li) li.classList.toggle("done", !!done[n]);
  });
  const mark = (n) => {
    done[n] = true;
    localStorage.setItem(ONB_KEY + ".steps", JSON.stringify(done));
    document.getElementById("onb-" + n)?.classList.add("done");
  };
  document.getElementById("onb-1-btn")?.addEventListener("click", () => {
    mark("1");
    document.getElementById("seed-demo-btn")?.click();
  });
  document.getElementById("onb-2-btn")?.addEventListener("click", () => {
    mark("2");
    document.getElementById("jarvis-input")?.focus();
  });
  document.getElementById("onb-3-btn")?.addEventListener("click", () => {
    mark("3");
    // Open the device page — where the user drops .ics/.csv/.vcf files
    // (Zero external APIs — local files only, per project rule.)
    document.querySelector('.nav-item[data-page="device"]')?.click();
  });
  document.getElementById("onb-dismiss")?.addEventListener("click", () => {
    localStorage.setItem(ONB_KEY, "dismissed");
    card.classList.add("hidden");
  });
}

// ==================== DASHBOARD ====================
function renderNavBadges(counts) {
  const map = {
    contacts: counts.contacts, companies: counts.companies,
    leads: counts.leads, opportunities: counts.opportunities,
    tasks: counts.tasks_open,
  };
  document.querySelectorAll(".nav-item[data-page]").forEach(btn => {
    const page = btn.dataset.page;
    const n = map[page];
    // Remove any existing badge
    btn.querySelector(".nav-badge")?.remove();
    if (n && n > 0) {
      const span = document.createElement("span");
      span.className = "nav-badge";
      span.textContent = n > 999 ? "999+" : n;
      btn.appendChild(span);
    }
  });
}

// On-device footprint widget — signature reminder of local-first values.
// Called after login and on dashboard refresh. Silently no-ops on error.
function _fmtBytes(n) {
  if (!n || n < 1024) return `${n || 0} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}
async function updateLocalFootprint() {
  try {
    const data = await api("/jarvis/local-footprint");
    const sizeEl = document.getElementById("lf-size");
    const rowsEl = document.getElementById("lf-rows");
    if (sizeEl) sizeEl.textContent = _fmtBytes(data.db_bytes);
    if (rowsEl) rowsEl.textContent = (data.total_rows ?? 0).toLocaleString("pt-BR");
  } catch (_) { /* silent — widget just stays "—" */ }
}

async function loadDashboard() {
  try {
    const ctx = await api("/jarvis/context");
    renderNudges(ctx.nudges || []);
    renderRecentlyViewed();
    renderOnboarding(ctx.counts || {});
    renderNavBadges(ctx.counts || {});
    updateLocalFootprint();  // fire-and-forget
    // Cache workspace preferences (tone, preferred_name, language) for UI reuse.
    state.workspacePref = ctx.preferences || {};
    const kpis = document.getElementById("kpis");
    kpis.innerHTML = "";
    // Hero KPI — pipeline value (5-second rule): the number that matters most on landing.
    const opps = ctx.open_opportunities || [];
    const heroTotal = opps.reduce((s, o) => s + (o.amount || 0), 0);
    const isPT = (state.lang || "pt") === "pt";
    const heroLabel = isPT ? "Pipeline aberto" : "Open pipeline";
    const heroCount = opps.length;
    const heroCurrency = opps[0]?.currency || (isPT ? "BRL" : "USD");
    const symbol = heroCurrency === "BRL" ? "R$" : "$";
    const heroValue = heroTotal >= 1000000
      ? `${symbol} ${(heroTotal / 1_000_000).toLocaleString(isPT ? "pt-BR" : "en-US", { maximumFractionDigits: 1 })}M`
      : `${symbol} ${heroTotal.toLocaleString(isPT ? "pt-BR" : "en-US", { maximumFractionDigits: 0 })}`;
    const heroEl = document.createElement("div");
    heroEl.className = "kpi kpi-hero";
    heroEl.dataset.kind = "pipeline";
    heroEl.innerHTML = `<div class="label">${heroLabel}</div>
      <div class="value" style="font-size:1.6em;font-weight:700;">${heroValue}</div>
      <div class="subtle" style="font-size:0.78em;margin-top:2px;">${heroCount} ${isPT ? "oportunidades" : "opportunities"}</div>`;
    kpis.appendChild(heroEl);

    const cards = [
      [t("p_kpi_contacts"), ctx.counts.contacts ?? 0, "revenue"],
      [t("p_kpi_companies"), ctx.counts.companies ?? 0, "pipeline"],
      [t("p_kpi_leads"), ctx.counts.leads ?? 0, "won"],
      [t("p_kpi_opps"), ctx.counts.opportunities ?? 0, "pipeline"],
      [t("p_kpi_tasks"), ctx.counts.tasks_open ?? 0, "risk"],
    ];
    for (const [label, value, kind] of cards) {
      const el = document.createElement("div");
      el.className = "kpi";
      el.dataset.kind = kind;
      el.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
      kpis.appendChild(el);
    }

    const [today, week, byStage, activities, trend, monthly] = await Promise.all([
      silentJarvisCall("what's on today"),
      silentJarvisCall("this week"),
      silentJarvisCall("revenue by stage"),
      api("/activities?limit=15").catch(() => null),
      api(`/jarvis/wins-losses-trend?days=${state.dashboardWindow || 30}`).catch(() => null),
      api("/jarvis/monthly-forecast?months=6").catch(() => null),
    ]);
    // Render dashboard sub-cards FIRST — before charts that might throw.
    // renderList handles empty gracefully via friendly empty state.
    try {
      const tr = today?.tool_calls?.[0]?.result || {};
      const isPT = (state.lang || "pt") === "pt";
      renderList("overdue-tasks",
        (tr.overdue_tasks || []).map(x => `${x.title} (${t("task_due")} ${x.due_at || ""})`),
        { icon: "✅", good: true,
          title: isPT ? "Nada atrasado" : "Nothing overdue",
          hint: isPT ? "Bom trabalho — sem tarefas em atraso." : "Nice work — no overdue tasks." });
      renderList("upcoming-meetings",
        (tr.meetings_today || []).map(x => `${x.title} @ ${x.starts_at}`),
        { icon: "📅",
          title: isPT ? "Nenhuma reunião marcada" : "No upcoming meetings",
          hint: isPT ? "Diga \"agende reunião com <contato> amanhã 15h\"." : "Say \"schedule meeting with <name> tomorrow 3pm\"." });
      const oc = document.getElementById("overdue-count");
      if (oc) oc.textContent = (tr.overdue_tasks || []).length ? `${(tr.overdue_tasks || []).length}` : "";
    } catch (e) { console.warn("dashboard sub-cards render failed", e); }
    renderPipelineChart(byStage);
    renderWinsLossesChart(trend);
    renderMonthlyForecast(monthly);
    renderWinRateGauge(trend);
    renderActivityFeed(activities);
    const wk = week?.tool_calls?.[0]?.result;
    const wkEl = document.getElementById("week-summary");
    if (wkEl) {
      const fmt = n => n.toLocaleString(undefined, { maximumFractionDigits: 2 });
      const totalActivity = wk
        ? (wk.opportunities_closing || []).length + (wk.tasks_due || []).length + (wk.meetings || []).length
        : 0;
      const isPT = (state.lang || "pt") === "pt";
      if (!wk || totalActivity === 0) {
        wkEl.innerHTML = `<div class="empty" style="padding:24px 12px;text-align:center">
          <div class="empty-ico" style="font-size:1.8em;opacity:0.6;margin-bottom:4px;">📊</div>
          <div class="empty-title" style="color:var(--fg-2);font-weight:500;">
            ${isPT ? "Semana tranquila" : "Quiet week"}
          </div>
          <div class="empty-hint" style="color:var(--fg-4);font-size:0.85em;margin-top:4px;">
            ${isPT ? "Nada agendado — hora de prospectar." : "Nothing scheduled — time to prospect."}
          </div>
        </div>`;
      } else {
        wkEl.innerHTML = `
          <div>${t("p_wk_closing")}: <strong>${(wk.opportunities_closing || []).length}</strong></div>
          <div>${t("p_wk_weighted")}: <strong>${fmt(wk.weighted_pipeline || 0)}</strong></div>
          <div>${t("p_wk_tasks")}: <strong>${(wk.tasks_due || []).length}</strong></div>
          <div>${t("p_wk_meetings")}: <strong>${(wk.meetings || []).length}</strong></div>
        `;
      }
    }
  } catch (err) { console.error(err); }
}

async function silentJarvisCall(message) {
  try {
    const body = state.conversation_id ? { message, conversation_id: state.conversation_id } : { message };
    return await api("/jarvis/chat", { method: "POST", body });
  } catch { return null; }
}

function renderNudges(nudges) {
  const el = document.getElementById("jarvis-nudges");
  if (!el) return;
  el.innerHTML = "";
  for (const n of nudges) {
    const chip = document.createElement("button");
    chip.className = `jarvis-nudge ${n.level === "warn" ? "warn" : ""}`;
    chip.textContent = n.message;
    chip.title = n.suggested_prompt ? `Ask: "${n.suggested_prompt}"` : "";
    chip.addEventListener("click", () => {
      const input = document.getElementById("jarvis-input");
      if (n.suggested_prompt) {
        input.value = n.suggested_prompt;
        document.getElementById("jarvis-form").dispatchEvent(new Event("submit"));
      }
    });
    el.appendChild(chip);
  }
}

// Recently-viewed section: renders as a horizontal chip strip near nudges.
// Zero cost when empty. Notion/Linear pattern for quick re-access.
function renderRecentlyViewed() {
  const nudgesHost = document.getElementById("jarvis-nudges");
  if (!nudgesHost) return;
  // Reuse the nudges container's parent — insert a strip right after nudges.
  let strip = document.getElementById("recent-viewed");
  const items = readRecent();
  if (!items.length) { if (strip) strip.remove(); return; }
  if (!strip) {
    strip = document.createElement("div");
    strip.id = "recent-viewed";
    strip.className = "recent-viewed";
    nudgesHost.parentNode.insertBefore(strip, nudgesHost.nextSibling);
  }
  const isPT = (state.lang || "pt") === "pt";
  const label = isPT ? "Vistos recentemente" : "Recently viewed";
  strip.innerHTML = `<span class="recent-label">${label}:</span>` + items.slice(0, 6).map(r => {
    const av = avatarChip(r.name, {size: 20, sat: 55, light: 44});
    return `<button class="recent-chip" data-type="${r.type}" data-id="${r.id}" title="${escapeHtml(r.name)}">${av}<span>${escapeHtml(r.name)}</span></button>`;
  }).join("");
  strip.querySelectorAll(".recent-chip").forEach(btn => {
    btn.addEventListener("click", () => openDrawer(btn.dataset.type, btn.dataset.id));
  });
}

function renderActivityFeed(page) {
  const ul = document.getElementById("activity-feed");
  if (!ul) return;
  // Wire CSV export once
  const btn = document.getElementById("activity-export-csv");
  if (btn && !btn.dataset.wired) {
    btn.dataset.wired = "1";
    btn.addEventListener("click", async () => {
      try {
        const full = await api("/activities?limit=200");
        downloadCsv(`activity-${new Date().toISOString().slice(0,10)}.csv`,
          (full.items || []).map(a => ({
            occurred_at: a.occurred_at,
            kind: a.kind,
            subject_type: a.subject_type || "",
            subject_id: a.subject_id || "",
            summary: a.summary || "",
          })));
      } catch (err) { toast(err.message, "error"); }
    });
  }
  const cnt = document.getElementById("activity-count");
  const items = page?.items || [];
  if (cnt) cnt.textContent = items.length ? `${items.length}` : "";
  ul.innerHTML = "";
  if (!items.length) {
    const isPT = (state.lang || "pt") === "pt";
    ul.innerHTML = `<li class="empty">
      <div class="empty-ico">📜</div>
      <div class="empty-title">${isPT ? "Sem atividade recente" : "No recent activity"}</div>
      <div class="empty-hint">${isPT ? "Ações criadas/editadas/apagadas aparecem aqui." : "Created/edited/deleted actions show up here."}</div>
    </li>`;
    return;
  }
  const isPT = (state.lang || "pt") === "pt";
  const KIND_META = {
    created:     { icon: "➕", cls: "act-good", pt: "Criado",     en: "Created" },
    updated:     { icon: "✏️", cls: "act-info", pt: "Atualizado", en: "Updated" },
    deleted:     { icon: "🗑️", cls: "act-warn", pt: "Removido",   en: "Deleted" },
    call:        { icon: "📞", cls: "act-info", pt: "Ligação",    en: "Call" },
    email:       { icon: "✉️", cls: "act-info", pt: "Email",       en: "Email" },
    sms:         { icon: "💬", cls: "act-info", pt: "SMS",         en: "SMS" },
    whatsapp:    { icon: "💬", cls: "act-info", pt: "WhatsApp",    en: "WhatsApp" },
    chat:        { icon: "💬", cls: "act-info", pt: "Chat",        en: "Chat" },
    stage_moved: { icon: "↔️", cls: "act-info", pt: "Mudou etapa", en: "Stage moved" },
    won:         { icon: "🏆", cls: "act-good", pt: "Ganho",       en: "Won" },
    lost:        { icon: "💔", cls: "act-warn", pt: "Perdido",     en: "Lost" },
  };
  const SUBJ_LABEL = {
    contact:     { pt: "contato",     en: "contact" },
    company:     { pt: "empresa",     en: "company" },
    opportunity: { pt: "oportunidade", en: "opportunity" },
    lead:        { pt: "lead",        en: "lead" },
    task:        { pt: "tarefa",      en: "task" },
    meeting:     { pt: "reunião",     en: "meeting" },
    note:        { pt: "nota",        en: "note" },
  };
  const parseTs = s => {
    if (!s) return new Date();
    const iso = /[zZ]|[+\-]\d\d:?\d\d$/.test(s) ? s : s + "Z";
    return new Date(iso);
  };
  for (const a of items) {
    const when = parseTs(a.occurred_at);
    const ago = timeAgo(when);
    const meta = KIND_META[a.kind] || { icon: "•", cls: "act-info", pt: a.kind, en: a.kind };
    const kindLabel = isPT ? meta.pt : meta.en;
    const subjLabel = a.subject_type ? (SUBJ_LABEL[a.subject_type]?.[isPT ? "pt" : "en"] || a.subject_type) : "";
    const li = document.createElement("li");
    li.className = "activity-item";
    const summaryHtml = a.summary ? ` <span class="activity-summary">— ${escapeHtml(a.summary)}</span>` : "";
    li.innerHTML = `
      <div class="activity-row">
        <span class="activity-icon ${meta.cls}" aria-hidden="true">${meta.icon}</span>
        <div class="activity-body">
          <div class="activity-line">
            <strong>${escapeHtml(kindLabel)}</strong>${subjLabel ? ` <span class="activity-subj">${escapeHtml(subjLabel)}</span>` : ""}${summaryHtml}
          </div>
          <div class="activity-when" title="${when.toLocaleString()}">${ago}</div>
        </div>
      </div>
    `;
    ul.appendChild(li);
  }
}

function timeAgo(date) {
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 60) return state.lang === "pt" ? "agora" : "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return state.lang === "pt" ? `há ${m} min` : `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return state.lang === "pt" ? `há ${h}h` : `${h}h ago`;
  const d = Math.floor(h / 24);
  return state.lang === "pt" ? `há ${d}d` : `${d}d ago`;
}

function renderMonthlyForecast(data) {
  const existing = document.getElementById("mf-chart");
  if (existing) existing.remove();
  if (!data || !data.buckets?.length) return;
  const buckets = data.buckets;
  const rawMax = Math.max(...buckets.map(b => b.total));
  const isPT = (state.lang || "pt") === "pt";
  const kpiRow = document.getElementById("kpis");
  if (!kpiRow) return;
  // Empty state — no forecast data in any bucket
  if (rawMax === 0) {
    const wrap = document.createElement("div");
    wrap.id = "mf-chart";
    wrap.className = "card";
    wrap.style.marginBottom = "20px";
    wrap.innerHTML = `
      <div class="card-header">
        <h3>🔮 ${isPT ? "Forecast mensal" : "Monthly forecast"}</h3>
      </div>
      <div class="empty" style="padding:32px 12px;text-align:center;">
        <div class="empty-ico" style="font-size:1.8em;opacity:0.6;margin-bottom:6px;">🔮</div>
        <div class="empty-title" style="color:var(--fg-2);font-weight:500;">
          ${isPT ? "Sem forecast pra mostrar" : "No forecast to show"}
        </div>
        <div class="empty-hint" style="color:var(--fg-4);font-size:0.85em;margin-top:4px;">
          ${isPT ? "Adicione data de fechamento nas oportunidades abertas." : "Add expected close dates to open opportunities."}
        </div>
      </div>
    `;
    const wl = document.getElementById("wl-chart");
    const pipe = document.getElementById("pipeline-chart");
    (wl || pipe || kpiRow).after(wrap);
    return;
  }
  const max = rawMax;
  const barW = 100 / buckets.length;
  const totalWeighted = buckets.reduce((s, b) => s + b.weighted, 0);
  const bars = buckets.map((b, i) => {
    const total_h = Math.round((b.total / max) * 45);
    const weight_h = Math.round((b.weighted / max) * 45);
    const x = i * barW;
    const label = b.month.split("-")[1];  // just month number
    return `
      <g transform="translate(${x}, 0)">
        <rect x="${barW * 0.15}" y="${50 - total_h}" width="${barW * 0.7}" height="${total_h}"
              fill="var(--bg-3)" opacity="0.4"><title>${b.month}: total $ ${b.total.toLocaleString()}</title></rect>
        <rect x="${barW * 0.15}" y="${50 - weight_h}" width="${barW * 0.7}" height="${weight_h}"
              fill="url(#mfGrad)"><title>${b.month}: weighted $ ${b.weighted.toLocaleString()}</title></rect>
        <text x="${barW / 2}" y="56" font-size="3.6" text-anchor="middle" fill="var(--fg-2)">${label}</text>
      </g>
    `;
  }).join("");
  const wrap = document.createElement("div");
  wrap.id = "mf-chart";
  wrap.className = "card";
  wrap.style.marginBottom = "20px";
  wrap.innerHTML = `
    <div class="card-header">
      <h3>🔮 ${state.lang === "pt" ? "Forecast mensal" : "Monthly forecast"}</h3>
      <span class="subtle">${state.lang === "pt" ? "Total ponderado:" : "Weighted total:"} <strong>$ ${totalWeighted.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong></span>
    </div>
    <svg viewBox="0 0 100 60" preserveAspectRatio="none" style="width:100%;height:160px;display:block;">
      <defs><linearGradient id="mfGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2dd4bf"/><stop offset="1" stop-color="#0ea5a0"/></linearGradient></defs>
      ${bars}
    </svg>
  `;
  // Insert after wl-chart or pipe-chart or kpiRow
  const wl = document.getElementById("wl-chart");
  const pipe = document.getElementById("pipeline-chart");
  (wl || pipe || kpiRow).after(wrap);
}

function renderWinRateGauge(trend) {
  const existing = document.getElementById("wr-gauge");
  if (existing) existing.remove();
  if (!trend?.totals) return;
  const won = trend.totals.won || 0;
  const lost = trend.totals.lost || 0;
  const total = won + lost;
  if (!total) return;
  const winRate = Math.round((won / total) * 100);
  // Semi-circle gauge: 180° arc, needle at winRate%
  const angle = -180 + (winRate / 100) * 180;
  const rad = angle * Math.PI / 180;
  const cx = 50, cy = 50, r = 40;
  const needleX = cx + r * Math.cos(rad);
  const needleY = cy + r * Math.sin(rad);
  const color = winRate >= 60 ? "var(--ok)" : winRate >= 30 ? "var(--warn)" : "var(--danger)";

  const kpiRow = document.getElementById("kpis");
  if (!kpiRow) return;
  const wrap = document.createElement("div");
  wrap.id = "wr-gauge";
  wrap.className = "card";
  wrap.style.cssText = "margin-bottom:20px;text-align:center;";
  wrap.innerHTML = `
    <div class="card-header">
      <h3>🎯 ${state.lang === "pt" ? "Taxa de vitória" : "Win rate"}</h3>
      <span class="subtle">${won} / ${total} ${state.lang === "pt" ? "deals fechados" : "closed deals"}</span>
    </div>
    <svg viewBox="0 0 100 60" style="width:100%;max-width:280px;height:140px;display:block;margin:0 auto;">
      <path d="M 10 50 A 40 40 0 0 1 90 50" stroke="var(--bg-3)" stroke-width="8" fill="none" />
      <path d="M 10 50 A 40 40 0 0 1 90 50" stroke="${color}" stroke-width="8" fill="none"
            stroke-dasharray="${125.6 * winRate / 100} 125.6" />
      <text x="50" y="42" text-anchor="middle" font-size="14" font-weight="700" fill="var(--fg)">${winRate}%</text>
    </svg>
  `;
  const wl = document.getElementById("wl-chart");
  const mf = document.getElementById("mf-chart");
  (mf || wl || kpiRow).after(wrap);
}

function renderWinsLossesChart(trend) {
  const existing = document.getElementById("wl-chart");
  if (existing) existing.remove();
  if (!trend || !trend.series?.length) return;
  const kpiRow = document.getElementById("kpis");
  if (!kpiRow) return;
  const series = trend.series;
  const max = Math.max(...series.map(x => Math.max(x.won, x.lost)));
  const isPT = (state.lang || "pt") === "pt";
  // Empty state — trend has no wins/losses in the window
  if (max === 0) {
    const wrap = document.createElement("div");
    wrap.id = "wl-chart";
    wrap.className = "card";
    wrap.style.marginBottom = "20px";
    wrap.innerHTML = `
      <div class="card-header">
        <h3>📈 ${isPT ? "Vitórias vs Perdas (30d)" : "Wins vs Losses (30d)"}</h3>
      </div>
      <div class="empty" style="padding:32px 12px;text-align:center;">
        <div class="empty-ico" style="font-size:1.8em;opacity:0.6;margin-bottom:6px;">📈</div>
        <div class="empty-title" style="color:var(--fg-2);font-weight:500;">
          ${isPT ? "Sem oportunidades fechadas nos últimos 30 dias" : "No closed deals in the last 30 days"}
        </div>
        <div class="empty-hint" style="color:var(--fg-4);font-size:0.85em;margin-top:4px;">
          ${isPT ? "Feche um deal com \"ganhei &lt;nome&gt;\" pra começar a série." : "Close a deal with \"won &lt;name&gt;\" to start the series."}
        </div>
      </div>
    `;
    const pipe = document.getElementById("pipeline-chart");
    (pipe || kpiRow).after(wrap);
    return;
  }
  const w = 100 / series.length;
  const bars = series.map((it, i) => {
    const wh = Math.round((it.won / max) * 45);
    const lh = Math.round((it.lost / max) * 45);
    const x = i * w;
    return `
      <g transform="translate(${x}, 0)">
        <rect x="${w * 0.1}" y="${50 - wh}" width="${w * 0.35}" height="${wh}" fill="var(--ok)"><title>${it.date} · ${it.won} wins</title></rect>
        <rect x="${w * 0.55}" y="${50 - lh}" width="${w * 0.35}" height="${lh}" fill="var(--danger)"><title>${it.date} · ${it.lost} losses</title></rect>
      </g>
    `;
  }).join("");
  const wrap = document.createElement("div");
  wrap.id = "wl-chart";
  wrap.className = "card";
  wrap.style.marginBottom = "20px";
  wrap.innerHTML = `
    <div class="card-header">
      <h3>📈 ${state.lang === "pt" ? "Wins vs Losses (30d)" : "Wins vs Losses (30d)"}</h3>
      <span class="subtle">
        <span style="color:var(--ok);">● ${trend.totals.won} wins</span>
        &nbsp;·&nbsp;
        <span style="color:var(--danger);">● ${trend.totals.lost} losses</span>
      </span>
    </div>
    <svg viewBox="0 0 100 55" preserveAspectRatio="none" style="width:100%;height:120px;display:block;">${bars}</svg>
  `;
  // Insert after pipeline-chart if it exists, else after kpiRow
  const pipe = document.getElementById("pipeline-chart");
  (pipe || kpiRow).after(wrap);
}

function renderPipelineChart(byStageResp) {
  // Injects a mini SVG bar chart under the KPI row, showing open $ per stage.
  // Parses the plain-text reply. Cheap but works.
  const existing = document.getElementById("pipeline-chart");
  if (existing) existing.remove();
  const reply = byStageResp?.reply || "";
  // Lines like "  • Prospecting: 3 × $ 45,000"
  const lines = reply.split("\n").filter(l => /[•\-*]\s+\S/.test(l));
  const items = [];
  for (const line of lines) {
    const m = line.match(/[•\-*]\s+(.+?):\s*(\d+)\s*[×x]\s*\$?\s*([\d,\.]+)/);
    if (!m) continue;
    const amt = parseFloat(m[3].replace(/,/g, "")) || 0;
    items.push({ stage: m[1].trim(), count: parseInt(m[2], 10), amount: amt });
  }
  if (!items.length) return;
  const max = Math.max(...items.map(x => x.amount), 1);
  const kpiRow = document.getElementById("kpis");
  if (!kpiRow) return;
  const wrap = document.createElement("div");
  wrap.id = "pipeline-chart";
  wrap.className = "card";
  wrap.style.marginBottom = "20px";
  const barW = 100 / items.length;
  // SVG only draws the bars + count labels. Stage labels render as HTML below —
  // avoids preserveAspectRatio="none" horizontal stretching that mangled text.
  const bars = items.map((it, i) => {
    const h = Math.max(4, Math.round((it.amount / max) * 90));
    const x = i * barW;
    return `
      <g transform="translate(${x}, 0)">
        <rect x="${barW * 0.15}" y="${95 - h}" width="${barW * 0.7}" height="${h}"
              fill="url(#chartGrad)" rx="2">
          <title>${it.stage}: ${it.count} × $${it.amount.toLocaleString()}</title>
        </rect>
        <text x="${barW / 2}" y="${95 - h - 3}" font-size="3.4" text-anchor="middle" fill="var(--fg-3)">${it.count}</text>
      </g>
    `;
  }).join("");
  const stageLabels = items.map(it => {
    const local = localizeStage(it.stage);
    const short = local.length > 14 ? local.slice(0, 13) + "…" : local;
    return `<div class="pipe-chart-label" title="${escapeHtml(local)}">${escapeHtml(short)}</div>`;
  }).join("");
  wrap.innerHTML = `
    <div class="card-header"><h3>💼 ${state.lang === "pt" ? "Valor aberto por estágio" : "Open value by stage"}</h3></div>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style="width:100%;height:160px;display:block;">
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2dd4bf"/>
          <stop offset="1" stop-color="#0ea5a0"/>
        </linearGradient>
      </defs>
      ${bars}
    </svg>
    <div class="pipe-chart-labels">${stageLabels}</div>
  `;
  kpiRow.after(wrap);
}

// ---------- CSV export ----------
function toCsvCell(v) {
  if (v == null) return "";
  const s = String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}
function downloadCsv(filename, rows) {
  if (!rows.length) { toast(t("empty_here"), "warn"); return; }
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(","), ...rows.map(r => headers.map(h => toCsvCell(r[h])).join(","))];
  const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  toast(`${t("t_exported")}: ${filename}`, "success");
}

function renderList(id, items, emptyState) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  if (!items.length) {
    if (emptyState && typeof emptyState === "object") {
      const { icon = "·", title = t("empty_here"), hint = "", good = false } = emptyState;
      el.innerHTML = `<li class="empty${good ? " good" : ""}">
        <div class="empty-ico">${icon}</div>
        <div class="empty-title">${title}</div>
        ${hint ? `<div class="empty-hint">${hint}</div>` : ""}
      </li>`;
    } else {
      el.innerHTML = `<li class="empty">${t("empty_here")}</li>`;
    }
    return;
  }
  for (const line of items) {
    const li = document.createElement("li");
    li.textContent = line;
    el.appendChild(li);
  }
}

function bigEmptyCTA(colspan, icon, title, sub, btnLabel, btnAction) {
  const btnId = `cta-${Math.random().toString(36).slice(2, 8)}`;
  setTimeout(() => document.getElementById(btnId)?.addEventListener("click", btnAction), 0);
  return `<tr><td colspan="${colspan}" style="text-align:center;padding:40px 20px;">
    <div style="font-size:3em;margin-bottom:8px;">${icon}</div>
    <div style="font-weight:600;font-size:1.05em;margin-bottom:4px;">${escapeHtml(title)}</div>
    <div class="subtle" style="margin-bottom:16px;">${escapeHtml(sub)}</div>
    <button id="${btnId}" class="btn-primary">${escapeHtml(btnLabel)}</button>
  </td></tr>`;
}

// ==================== SAVED VIEWS ====================
const SAVED_VIEWS_KEY = "visiquost.contact.views";
function getSavedViews() {
  try { return JSON.parse(localStorage.getItem(SAVED_VIEWS_KEY) || "[]"); }
  catch { return []; }
}
function setSavedViews(v) { localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(v)); }

function renderContactSavedViews() {
  const wrap = document.getElementById("contact-saved-views");
  if (!wrap) return;
  const views = getSavedViews();
  wrap.innerHTML = "";
  for (const v of views) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = v.name;
    chip.title = `Buscar: "${v.q}"`;
    chip.addEventListener("click", () => {
      const inp = document.getElementById("contact-search");
      if (inp) { inp.value = v.q; loadContacts(); }
    });
    chip.addEventListener("contextmenu", ev => {
      ev.preventDefault();
      if (confirm(state.lang === "pt" ? `Remover "${v.name}"?` : `Remove "${v.name}"?`)) {
        const remaining = getSavedViews().filter(x => x.name !== v.name);
        setSavedViews(remaining);
        renderContactSavedViews();
      }
    });
    wrap.appendChild(chip);
  }
}

function bindContactSavedViews() {
  const saveBtn = document.getElementById("contact-save-view");
  if (!saveBtn) return;
  saveBtn.addEventListener("click", () => {
    const q = document.getElementById("contact-search")?.value.trim() || "";
    if (!q) { toast(state.lang === "pt" ? "Digite uma busca antes" : "Type a search first", "warn"); return; }
    const name = prompt(state.lang === "pt" ? "Nome da visão:" : "View name:", q.slice(0, 20));
    if (!name) return;
    const views = getSavedViews();
    if (!views.some(v => v.name === name)) views.push({ name, q });
    setSavedViews(views);
    renderContactSavedViews();
    toast(state.lang === "pt" ? "💾 Visão salva" : "💾 View saved", "success");
  });
  renderContactSavedViews();
}

// ==================== CRM PAGES ====================
state.contactsPage = { limit: 50, offset: 0 };
state.companiesPage = { limit: 50, offset: 0 };
state.oppsPage = { limit: 50, offset: 0 };
state.leadsPage = { limit: 50, offset: 0 };

function renderPagination(hostId, total, pageState, onChange) {
  const wrap = document.getElementById(hostId);
  if (!wrap) return;
  const { limit, offset } = pageState;
  const showing = Math.min(offset + limit, total);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;
  wrap.innerHTML = `
    <span class="pagination-count">${offset + 1}-${showing} ${state.lang === "pt" ? "de" : "of"} ${total}</span>
    <button class="chip ${limit === 25 ? "active" : ""}" data-limit="25">25</button>
    <button class="chip ${limit === 50 ? "active" : ""}" data-limit="50">50</button>
    <button class="chip ${limit === 100 ? "active" : ""}" data-limit="100">100</button>
    <button class="chip" data-nav="prev" ${hasPrev ? "" : "disabled"}>‹</button>
    <button class="chip" data-nav="next" ${hasNext ? "" : "disabled"}>›</button>
  `;
  wrap.querySelectorAll("[data-limit]").forEach(b => b.addEventListener("click", () => {
    pageState.limit = parseInt(b.dataset.limit, 10);
    pageState.offset = 0;
    onChange();
  }));
  wrap.querySelector("[data-nav='prev']")?.addEventListener("click", () => {
    if (offset > 0) { pageState.offset = Math.max(0, offset - limit); onChange(); }
  });
  wrap.querySelector("[data-nav='next']")?.addEventListener("click", () => {
    if (offset + limit < total) { pageState.offset = offset + limit; onChange(); }
  });
}

async function loadContacts() {
  const q = document.getElementById("contact-search")?.value.trim() || "";
  if (q !== state.contactSearch) state.contactsPage.offset = 0;
  state.contactSearch = q;
  const { limit, offset } = state.contactsPage;
  const params = new URLSearchParams({ limit, offset });
  if (q) params.set("q", q);
  // Skeleton rows while data loads — better perceived latency
  showTableSkeleton("#contacts-table tbody", 5, ["cb", 60, 80, 40, 60]);
  const page = await api(`/contacts?${params}`);
  const tbody = document.querySelector("#contacts-table tbody");
  tbody.innerHTML = "";
  const head = document.querySelector("#contacts-table thead tr");
  if (head) head.innerHTML = `<th style="width:30px;"><input type="checkbox" id="contacts-select-all"/></th><th>${t("tbl_name")}</th><th>${t("tbl_email")}</th><th>${t("tbl_phone")}</th><th>${t("tbl_job")}</th>`;
  if (!page.items.length) {
    const isPT = (state.lang || "pt") === "pt";
    if (q) tbody.innerHTML = `<tr><td colspan="5">
      <div class="empty" style="padding:32px 12px;">
        <div class="empty-ico">🔍</div>
        <div class="empty-title">${isPT ? `Nenhum contato bate com "${escapeHtml(q)}"` : `No contact matches "${escapeHtml(q)}"`}</div>
        <div class="empty-hint">${isPT ? "Tente outro nome ou parte do email." : "Try a different name or email fragment."}</div>
      </div>
    </td></tr>`;
    else tbody.innerHTML = bigEmptyCTA(5, "👥",
      isPT ? "Nenhum contato ainda" : "No contacts yet",
      isPT ? "Adicione seu primeiro contato ou importe um CSV." : "Add your first contact or import a CSV.",
      isPT ? "+ Criar meu primeiro contato" : "+ Create my first contact",
      () => document.getElementById("add-contact-btn")?.click());
    return;
  }
  for (const c of page.items) {
    const tr = document.createElement("tr");
    tr.className = "row-clickable";
    const checked = selectedContacts.has(c.id) ? "checked" : "";
    // Row quick actions — email / call icons that appear on hover
    const cleanPhone = (c.phone || "").replace(/[^\d+]/g, "");
    const quicks = [];
    if (c.email) quicks.push(`<a href="mailto:${escapeHtml(c.email)}" class="row-qa" onclick="event.stopPropagation()" title="Email">✉️</a>`);
    if (cleanPhone) quicks.push(`<a href="tel:${escapeHtml(cleanPhone)}" class="row-qa" onclick="event.stopPropagation()" title="Ligar">📞</a>`);
    const qaHtml = quicks.length ? `<span class="row-qa-wrap">${quicks.join("")}</span>` : "";
    // Avatar with initials — colored by hash of name for identity + scannability
    const fullName = ((c.first_name || "") + " " + (c.last_name || "")).trim();
    const avatarHtml = avatarChip(fullName || c.email);
    tr.innerHTML = `<td onclick="event.stopPropagation()"><input type="checkbox" class="contact-select" data-id="${c.id}" ${checked}/></td>
                    <td>${avatarHtml}${escapeHtml(fullName)}${newBadge(c.created_at)}${qaHtml}</td>
                    <td>${escapeHtml(c.email || "")}</td>
                    <td>${escapeHtml(c.phone || "")}</td>
                    <td>${escapeHtml(c.job_title || "")}</td>`;
    tr.addEventListener("click", () => openDrawer("contact", c.id));
    tbody.appendChild(tr);
  }
  // Rebind checkboxes
  document.querySelectorAll(".contact-select").forEach(cb => {
    cb.addEventListener("change", () => {
      if (cb.checked) selectedContacts.add(cb.dataset.id);
      else selectedContacts.delete(cb.dataset.id);
      updateBulkToolbar();
    });
  });
  // Rebind select-all (recreated in header)
  const all = document.getElementById("contacts-select-all");
  if (all) all.addEventListener("change", () => {
    document.querySelectorAll(".contact-select").forEach(cb => {
      cb.checked = all.checked;
      if (all.checked) selectedContacts.add(cb.dataset.id);
      else selectedContacts.delete(cb.dataset.id);
    });
    updateBulkToolbar();
  });
  updateBulkToolbar();
  makeTableSortable("contacts-table", [null, "name", "email", "phone", "job_title"]);
  renderPagination("contacts-pagination", page.total, state.contactsPage, loadContacts);
}

async function loadCompanies() {
  const q = document.getElementById("company-search")?.value.trim() || "";
  if (q !== state.companySearch) state.companiesPage.offset = 0;
  state.companySearch = q;
  const { limit, offset } = state.companiesPage;
  const params = new URLSearchParams({ limit, offset });
  if (q) params.set("q", q);
  showTableSkeleton("#companies-table tbody", 5, ["cb", 60, 80, 60]);
  const page = await api(`/companies?${params}`);
  const tbody = document.querySelector("#companies-table tbody");
  tbody.innerHTML = "";
  const head = document.querySelector("#companies-table thead tr");
  if (head) head.innerHTML = `<th style="width:30px;"><input type="checkbox" id="companies-select-all"/></th><th>${t("tbl_name")}</th><th>${t("tbl_domain")}</th><th>${t("tbl_industry")}</th>`;
  if (!page.items.length) {
    const isPT = (state.lang || "pt") === "pt";
    if (q) tbody.innerHTML = `<tr><td colspan="3">
      <div class="empty" style="padding:32px 12px;">
        <div class="empty-ico">🔍</div>
        <div class="empty-title">${isPT ? `Nenhuma empresa bate com "${escapeHtml(q)}"` : `No company matches "${escapeHtml(q)}"`}</div>
        <div class="empty-hint">${isPT ? "Tente outro nome ou domínio." : "Try a different name or domain."}</div>
      </div>
    </td></tr>`;
    else tbody.innerHTML = bigEmptyCTA(3, "🏢",
      isPT ? "Nenhuma empresa ainda" : "No companies yet",
      isPT ? "Adicione a primeira empresa para vincular a contatos e oportunidades." : "Add your first company to link with contacts and opportunities.",
      isPT ? "+ Criar minha primeira empresa" : "+ Create my first company",
      () => document.getElementById("add-company-btn")?.click());
    return;
  }
  for (const c of page.items) {
    const tr = document.createElement("tr");
    tr.className = "row-clickable";
    const checked = selectedCompanies.has(c.id) ? "checked" : "";
    tr.innerHTML = `<td onclick="event.stopPropagation()"><input type="checkbox" class="company-select" data-id="${c.id}" ${checked}/></td>
                    <td>${avatarChip(c.name)}${escapeHtml(c.name)}${newBadge(c.created_at)}</td><td>${escapeHtml(c.domain || "")}</td><td>${escapeHtml(c.industry || "")}</td>`;
    tr.addEventListener("click", () => openDrawer("company", c.id));
    tbody.appendChild(tr);
  }
  document.querySelectorAll(".company-select").forEach(cb => {
    cb.addEventListener("change", () => {
      if (cb.checked) selectedCompanies.add(cb.dataset.id); else selectedCompanies.delete(cb.dataset.id);
      updateCompaniesBulkToolbar();
    });
  });
  const allCo = document.getElementById("companies-select-all");
  if (allCo) allCo.addEventListener("change", () => {
    document.querySelectorAll(".company-select").forEach(cb => {
      cb.checked = allCo.checked;
      if (allCo.checked) selectedCompanies.add(cb.dataset.id); else selectedCompanies.delete(cb.dataset.id);
    });
    updateCompaniesBulkToolbar();
  });
  updateCompaniesBulkToolbar();
  makeTableSortable("companies-table", [null, "name", "domain", "industry"]);
  renderPagination("companies-pagination", page.total, state.companiesPage, loadCompanies);
}

async function loadOpportunities() {
  const { limit, offset } = state.oppsPage;
  showTableSkeleton("#opportunities-table tbody", 5, [60, 40, 40, 40]);
  const [page, pipelines] = await Promise.all([api(`/opportunities?limit=${limit}&offset=${offset}`), api("/pipelines")]);
  const stageById = {};
  for (const p of pipelines) for (const s of p.stages) stageById[s.id] = localizeStage(s.name);
  const tbody = document.querySelector("#opportunities-table tbody");
  tbody.innerHTML = "";
  const head = document.querySelector("#opportunities-table thead tr");
  if (head) head.innerHTML = `<th>${t("tbl_name")}</th><th>${t("tbl_stage")}</th><th>${t("tbl_amount")}</th><th>${t("tbl_status")}</th>`;
  if (!page.items.length) {
    tbody.innerHTML = bigEmptyCTA(4, "💰",
      state.lang === "pt" ? "Nenhuma oportunidade ainda" : "No opportunities yet",
      state.lang === "pt" ? "Registre a primeira negociação para ver o pipeline em ação." : "Register your first deal to see the pipeline in action.",
      state.lang === "pt" ? "+ Criar minha primeira oportunidade" : "+ Create my first opportunity",
      () => document.getElementById("add-opportunity-btn")?.click());
    return;
  }
  for (const o of page.items) {
    const tr = document.createElement("tr");
    tr.className = "row-clickable";
    tr.innerHTML = `<td>${avatarChip(o.name)}${escapeHtml(o.name)}${newBadge(o.created_at)}</td>
                    <td>${escapeHtml(stageById[o.stage_id] || "")}</td>
                    <td>${escapeHtml(fmtMoney(o.amount, o.currency))}</td>
                    <td><span class="status-pill ${o.status}">${escapeHtml(o.status)}</span></td>`;
    tr.addEventListener("click", () => openDrawer("opportunity", o.id));
    tbody.appendChild(tr);
  }
  makeTableSortable("opportunities-table", ["name", "stage", "amount", "status"]);
  renderPagination("opps-pagination", page.total, state.oppsPage, loadOpportunities);
}

// Keyboard-only kanban reorder.
// - Enter → open drawer
// - Space → pick up / drop (toggles aria-grabbed + .kanban-card-grabbed)
// - ArrowLeft / ArrowRight → move to previous / next stage column when grabbed
// Only one card can be grabbed at a time; blur cancels the pickup.
let _kanbanGrabbedCard = null;
function handleKanbanCardKey(ev, oppId, stageId) {
  if (ev.key === "Enter") { ev.preventDefault(); openDrawer("opportunity", oppId); return; }
  if (ev.key === " ") {
    ev.preventDefault();
    const card = ev.currentTarget;
    if (_kanbanGrabbedCard === card) {
      _kanbanGrabbedCard = null;
      card.setAttribute("aria-grabbed", "false");
      card.classList.remove("kanban-card-grabbed");
      toast(state.lang === "pt" ? "Solto" : "Dropped", "info", 900);
    } else {
      if (_kanbanGrabbedCard) {
        _kanbanGrabbedCard.setAttribute("aria-grabbed", "false");
        _kanbanGrabbedCard.classList.remove("kanban-card-grabbed");
      }
      _kanbanGrabbedCard = card;
      card.setAttribute("aria-grabbed", "true");
      card.classList.add("kanban-card-grabbed");
      toast(state.lang === "pt" ? "← → para mover, espaço para soltar" : "← → to move, space to drop", "info", 1400);
    }
    return;
  }
  if ((ev.key === "ArrowLeft" || ev.key === "ArrowRight") && _kanbanGrabbedCard === ev.currentTarget) {
    ev.preventDefault();
    const cols = Array.from(document.querySelectorAll(".kanban-col[data-stage-id]"));
    const curIdx = cols.findIndex(c => c.dataset.stageId === stageId);
    if (curIdx < 0) return;
    const nextIdx = ev.key === "ArrowRight" ? Math.min(cols.length - 1, curIdx + 1) : Math.max(0, curIdx - 1);
    if (nextIdx === curIdx) return;
    const newStageId = cols[nextIdx].dataset.stageId;
    _kanbanGrabbedCard = null;
    api(`/opportunities/${oppId}`, { method: "PATCH", body: { stage_id: newStageId } })
      .then(() => loadKanban().then(() => {
        // Re-focus the moved card
        setTimeout(() => document.querySelector(`.kanban-card[data-opp-id="${oppId}"]`)?.focus(), 60);
      }))
      .catch(err => toast(err.message, "error"));
  }
}

const kanbanPrefs = (() => {
  try { return JSON.parse(localStorage.getItem(KANBAN_KEY) || "{}"); } catch { return {}; }
})();
function saveKanbanPrefs() { localStorage.setItem(KANBAN_KEY, JSON.stringify(kanbanPrefs)); }

async function loadIntegrations() {
  const wrap = document.getElementById("integrations-list");
  const page = await api("/integrations");
  wrap.innerHTML = "";
  if (!page.items.length) {
    wrap.innerHTML = `<p class="subtle">${t("inte_empty")}</p>`;
  } else {
    for (const acc of page.items) {
      const div = document.createElement("div");
      div.className = "workflow-card";
      const expires = acc.expires_at ? new Date(acc.expires_at).toLocaleString() : "—";
      div.innerHTML = `
        <div class="wf-header">
          <div><strong>${escapeHtml(acc.provider)}</strong> <span class="subtle">${escapeHtml(acc.account_label || "")}</span></div>
          <button class="linkish" data-act="disconnect">${t("inte_disconnect")}</button>
        </div>
        <div class="subtle">Scopes: ${escapeHtml(acc.scopes || "—")} · Expires: ${expires} · ${acc.is_active ? "active" : "disabled"}</div>
      `;
      div.querySelector('[data-act="disconnect"]').addEventListener("click", async () => {
        if (!confirm(t("c_disconnect", acc.provider))) return;
        await api(`/integrations/${acc.id}`, { method: "DELETE" });
        toast(t("t_deleted"), "success");
        await loadIntegrations();
      });
      wrap.appendChild(div);
    }
  }
  const form = document.getElementById("connect-form");
  if (form && !form.dataset.wired) {
    form.dataset.wired = "1";
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      try {
        await api("/integrations/connect", { method: "POST", body: data });
        form.reset();
        toast(t("t_created"), "success");
        await loadIntegrations();
      } catch (err) { toast(`${t("t_connect_failed")}: ${err.message}`, "error"); }
    });
  }
}

async function loadWorkflowTemplates() {
  const sel = document.getElementById("workflow-template-select");
  if (!sel || sel.dataset.loaded) return;
  sel.dataset.loaded = "1";
  try {
    const r = await api("/workflows/templates");
    for (const t of r.templates) {
      const opt = document.createElement("option");
      opt.value = t.key;
      opt.textContent = t.name;
      opt.title = t.description || "";
      sel.appendChild(opt);
    }
    sel.addEventListener("change", async () => {
      const key = sel.value;
      if (!key) return;
      const tName = sel.options[sel.selectedIndex].textContent;
      if (!confirm(state.lang === "pt" ? `Instalar automação "${tName}"?` : `Install workflow "${tName}"?`)) {
        sel.value = "";
        return;
      }
      try {
        await api(`/workflows/from-template/${key}`, { method: "POST" });
        toast(state.lang === "pt" ? "✅ Automação instalada" : "✅ Workflow installed", "success");
        sel.value = "";
        await loadAutomations();
      } catch (err) { toast(err.message, "error"); }
    });
  } catch {}
}

async function loadAutomations() {
  await loadWorkflowTemplates();
  const page = await api("/workflows");
  const wrap = document.getElementById("workflows-list");
  wrap.innerHTML = "";
  if (!page.items.length) {
    wrap.innerHTML = `<p class="subtle">${t("workflow_none")}</p>`;
    return;
  }
  for (const wf of page.items) {
    const card = document.createElement("div");
    card.className = "workflow-card";
    const stepsSummary = (wf.steps || []).map(s => s.kind).join(" → ") || "(no steps)";
    let trigger = "";
    try { trigger = JSON.stringify(JSON.parse(wf.trigger_json), null, 2); } catch { trigger = wf.trigger_json; }
    card.innerHTML = `
      <div class="wf-header">
        <div><strong>${escapeHtml(wf.name)}</strong> <span class="subtle">${wf.is_active ? "active" : "disabled"} · ${wf.run_count} runs</span></div>
        <div class="flex-row">
          <button class="linkish" data-act="toggle">${wf.is_active ? t("workflow_disable") : t("workflow_enable")}</button>
          <button class="linkish" data-act="delete">${t("workflow_delete")}</button>
          <button class="linkish" data-act="runs">${t("workflow_runs")}</button>
        </div>
      </div>
      <div class="subtle">Steps: ${escapeHtml(stepsSummary)}</div>
      <pre>${escapeHtml(trigger)}</pre>
      <div class="wf-runs hidden"></div>
    `;
    card.querySelector('[data-act="toggle"]').addEventListener("click", async () => {
      await api(`/workflows/${wf.id}`, { method: "PATCH", body: { is_active: !wf.is_active } });
      await loadAutomations();
    });
    card.querySelector('[data-act="delete"]').addEventListener("click", async () => {
      if (!confirm(t("c_delete_workflow", wf.name))) return;
      await api(`/workflows/${wf.id}`, { method: "DELETE" });
      toast(t("t_deleted"), "success");
      await loadAutomations();
    });
    card.querySelector('[data-act="runs"]').addEventListener("click", async () => {
      const runsEl = card.querySelector(".wf-runs");
      runsEl.classList.toggle("hidden");
      if (runsEl.classList.contains("hidden")) return;
      const runs = await api(`/workflows/${wf.id}/runs`);
      if (!runs.length) { runsEl.innerHTML = `<p class='subtle'>${t("workflow_no_runs")}</p>`; return; }
      runsEl.innerHTML = `<h4>${t("workflow_recent")}</h4>` + runs.map(r =>
        `<div class="subtle">${r.started_at} · ${r.status}${r.error ? " · " + escapeHtml(r.error) : ""}</div>`
      ).join("");
    });
    wrap.appendChild(card);
  }
}

async function loadLeads() {
  const { limit, offset } = state.leadsPage;
  showTableSkeleton("#leads-table tbody", 5, [60, 60, 40, 40, 40]);
  const page = await api(`/leads?limit=${limit}&offset=${offset}`);
  const tbody = document.querySelector("#leads-table tbody");
  tbody.innerHTML = "";
  const head = document.querySelector("#leads-table thead tr");
  if (head) head.innerHTML = `<th>${t("tbl_name")}</th><th>${t("tbl_company")}</th><th>${t("tbl_source")}</th><th>${t("tbl_status")}</th><th>${t("tbl_score")}</th>`;
  if (!page.items.length) {
    tbody.innerHTML = bigEmptyCTA(5, "🎯",
      state.lang === "pt" ? "Nenhum lead ainda" : "No leads yet",
      state.lang === "pt" ? "Leads são possíveis clientes ainda não qualificados. Adicione o primeiro." : "Leads are prospects not yet qualified. Add your first.",
      state.lang === "pt" ? "+ Criar meu primeiro lead" : "+ Create my first lead",
      () => document.getElementById("add-lead-btn")?.click());
    return;
  }
  for (const l of page.items) {
    const tr = document.createElement("tr");
    tr.className = "row-clickable";
    const statusClass = l.status || "new";
    tr.innerHTML = `
      <td>${avatarChip(((l.first_name || "") + " " + (l.last_name || "")).trim() || l.email)}${escapeHtml((l.first_name || "") + " " + (l.last_name || ""))}${newBadge(l.created_at)}</td>
      <td>${escapeHtml(l.company_name || "")}</td>
      <td>${escapeHtml(l.source || "")}</td>
      <td><span class="status-pill ${statusClass}">${escapeHtml(l.status)}</span></td>
      <td>${l.score}</td>
    `;
    tr.addEventListener("click", () => openDrawer("lead", l.id));
    tbody.appendChild(tr);
  }
  renderPagination("leads-pagination", page.total, state.leadsPage, loadLeads);
  await loadRules();
}

async function loadRules() {
  const wrap = document.getElementById("lead-rules-section");
  if (!wrap || wrap.classList.contains("hidden")) return;
  const page = await api("/lead-scoring/rules");
  const tbody = document.querySelector("#rules-table tbody");
  tbody.innerHTML = "";
  for (const r of page.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.name)}</td>
      <td>${escapeHtml(r.field)}</td>
      <td>${escapeHtml(r.op)}</td>
      <td>${escapeHtml(r.value || "")}</td>
      <td>${r.score_delta > 0 ? "+" + r.score_delta : r.score_delta}</td>
      <td>${r.is_active ? "✓" : "—"}</td>
      <td><button class="icon-btn">🗑</button></td>
    `;
    tr.querySelector("button").addEventListener("click", async () => {
      if (!confirm(t("c_delete_rule", r.name))) return;
      await api(`/lead-scoring/rules/${r.id}`, { method: "DELETE" });
      toast(t("t_deleted"), "success");
      await loadRules();
    });
    tbody.appendChild(tr);
  }
}

async function loadPipelineTemplates() {
  const sel = document.getElementById("pipeline-template-select");
  if (!sel || sel.dataset.loaded) return;
  sel.dataset.loaded = "1";
  try {
    const r = await api("/pipelines/templates");
    for (const t of r.templates) {
      const opt = document.createElement("option");
      opt.value = t.key;
      opt.textContent = `${t.name} (${t.stages.length} estágios)`;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", async () => {
      const key = sel.value;
      if (!key) return;
      const tName = sel.options[sel.selectedIndex].textContent;
      if (!confirm(state.lang === "pt" ? `Instalar template "${tName}"?` : `Install template "${tName}"?`)) {
        sel.value = "";
        return;
      }
      try {
        await api(`/pipelines/from-template/${key}`, { method: "POST" });
        toast(state.lang === "pt" ? "✅ Template instalado" : "✅ Template installed", "success");
        sel.value = "";
        await loadKanban();
      } catch (err) { toast(err.message, "error"); }
    });
  } catch {}
}

// Palette used to auto-color kanban stages by index
// Rampa categorica ancorada no teal do Sentinela: progride do frio (inicio do
// funil) ao quente (fechamento), mantendo contraste entre estagios vizinhos.
const STAGE_PALETTE = ["#0ea5a0", "#2dd4bf", "#7ff5e6", "#38bdf8", "#818cf8", "#f6b73c", "#fb923c", "#ff6b6b", "#e879f9"];

async function loadKanban() {
  await loadPipelineTemplates();
  const board = document.getElementById("kanban-board");
  board.innerHTML = `<div class="subtle">${t("loading")}</div>`;
  const [pipelines, opps] = await Promise.all([
    api("/pipelines"),
    api("/opportunities?limit=200"),
  ]);
  const pipeline = pipelines.find(p => p.is_default) || pipelines[0];
  if (!pipeline) {
    const isPT = (state.lang || "pt") === "pt";
    board.innerHTML = `<div class="empty" style="padding:48px 24px;text-align:center;grid-column:1/-1;">
      <div class="empty-ico" style="font-size:2.4em;opacity:0.6;margin-bottom:12px;">📋</div>
      <div class="empty-title" style="color:var(--fg-2);font-weight:600;font-size:1.1em;">
        ${isPT ? "Sem pipeline ainda" : "No pipeline yet"}
      </div>
      <div class="empty-hint" style="color:var(--fg-4);font-size:0.9em;margin-top:6px;max-width:400px;margin-left:auto;margin-right:auto;">
        ${isPT ? "Crie uma oportunidade e o pipeline padrão será instalado automaticamente. Diga ao Jarvis: \"nova oportunidade: Big Deal 50k\"." : "Create an opportunity and the default pipeline installs automatically. Tell Jarvis: \"new opportunity: Big Deal 50k\"."}
      </div>
    </div>`;
    return;
  }
  const stages = pipeline.stages.slice().sort((a, b) => a.order_index - b.order_index);
  const byStage = {};
  for (const s of stages) byStage[s.id] = [];
  for (const o of opps.items || []) if (byStage[o.stage_id]) byStage[o.stage_id].push(o);

  board.innerHTML = "";
  for (let sidx = 0; sidx < stages.length; sidx++) {
    const stage = stages[sidx];
    const col = document.createElement("div");
    col.className = "kanban-col";
    col.dataset.stageId = stage.id;
    // Auto-color per stage. Won stays green, lost stays red.
    const stageColor = stage.is_won ? "var(--ok)" : stage.is_lost ? "var(--danger)" : STAGE_PALETTE[sidx % STAGE_PALETTE.length];
    col.style.borderTop = `3px solid ${stageColor}`;
    const cards = byStage[stage.id] || [];
    const totalAmt = cards.reduce((sum, c) => sum + (c.amount || 0), 0);
    const wipLimit = kanbanPrefs.wip?.[stage.id];
    const collapsed = kanbanPrefs.collapsed?.[stage.id] ?? (stage.is_won || stage.is_lost);
    if (collapsed) col.classList.add("collapsed");
    const overLimit = wipLimit != null && cards.length > wipLimit;
    col.innerHTML = `
      <h4>
        <span>${escapeHtml(localizeStage(stage.name))}</span>
        <span class="subtle ${overLimit ? "wip-limit-hit" : ""}">${cards.length}${wipLimit != null ? "/" + wipLimit : ""}</span>
      </h4>
      <div class="kanban-total">${totalAmt.toLocaleString()} ${t("total")} ${wipLimit != null ? "· " + t("wip") + " " + wipLimit : ""}</div>
      <div class="kanban-cards" data-stage-id="${stage.id}"></div>
      <button class="expand-toggle" title="Toggle collapsed">${collapsed ? t("expand") : t("collapse")}</button>
    `;
    const cardsEl = col.querySelector(".kanban-cards");
    for (const opp of cards) {
      const card = document.createElement("div");
      card.className = "kanban-card";
      card.draggable = true;
      card.dataset.oppId = opp.id;
      card.dataset.stageId = stage.id;
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-grabbed", "false");
      const ariaLabel = state.lang === "pt"
        ? `Oportunidade ${opp.name}, etapa ${stage.name}. Espaço para mover, setas para trocar de etapa, Enter para abrir.`
        : `Opportunity ${opp.name}, stage ${stage.name}. Space to grab, arrows to change stage, Enter to open.`;
      card.setAttribute("aria-label", ariaLabel);
      const prob = opp.probability != null ? Math.round(opp.probability) : null;
      const closingDate = opp.expected_close_date ? new Date(opp.expected_close_date).toLocaleDateString() : "";
      const probBar = prob != null ? `<div class="opp-prob"><div class="opp-prob-fill" style="width:${prob}%"></div></div>` : "";
      card.innerHTML = `
        <div class="name" style="display:flex;align-items:center;gap:8px;">${avatarChip(opp.name, {size: 22})}<span>${escapeHtml(opp.name)}</span></div>
        <div class="amount">${escapeHtml(fmtMoney(opp.amount, opp.currency))}${prob != null ? ` · ${prob}%` : ""}</div>
        ${probBar}
        ${closingDate ? `<div class="opp-close subtle">${state.lang === "pt" ? "Fecha" : "Close"} ${closingDate}</div>` : ""}
      `;
      card.title = `${opp.name}
${opp.currency} ${(opp.amount || 0).toLocaleString()}${prob != null ? ` · ${prob}% probability` : ""}${closingDate ? `
Expected close: ${closingDate}` : ""}`;
      card.addEventListener("dragstart", ev => {
        ev.dataTransfer.setData("text/opp-id", opp.id);
        ev.dataTransfer.effectAllowed = "move";
      });
      card.addEventListener("click", () => openDrawer("opportunity", opp.id));
      card.addEventListener("keydown", ev => handleKanbanCardKey(ev, opp.id, stage.id));
      cardsEl.appendChild(card);
    }
    col.addEventListener("dragover", ev => { ev.preventDefault(); col.classList.add("drag-over"); });
    col.addEventListener("dragleave", () => col.classList.remove("drag-over"));
    col.addEventListener("drop", async ev => {
      ev.preventDefault();
      col.classList.remove("drag-over");
      const oppId = ev.dataTransfer.getData("text/opp-id");
      if (!oppId) return;
      try {
        await api(`/opportunities/${oppId}`, { method: "PATCH", body: { stage_id: stage.id } });
        await loadKanban();
      } catch (err) { toast(err.message, "error"); }
    });
    col.querySelector(".expand-toggle").addEventListener("click", ev => {
      ev.stopPropagation();
      kanbanPrefs.collapsed = kanbanPrefs.collapsed || {};
      kanbanPrefs.collapsed[stage.id] = !col.classList.contains("collapsed");
      saveKanbanPrefs();
      loadKanban();
    });
    col.querySelector("h4").addEventListener("contextmenu", ev => {
      ev.preventDefault();
      const current = kanbanPrefs.wip?.[stage.id] ?? "";
      const val = prompt(t("wip_prompt", stage.name), current);
      if (val === null) return;
      kanbanPrefs.wip = kanbanPrefs.wip || {};
      if (val === "") delete kanbanPrefs.wip[stage.id];
      else kanbanPrefs.wip[stage.id] = Math.max(0, parseInt(val, 10) || 0);
      saveKanbanPrefs();
      loadKanban();
    });
    board.appendChild(col);
  }
  updateKanbanScrollHints();
}

// Sync the .can-scroll-left/right classes on the wrapper based on scroll pos.
// Called after render + on scroll + on resize.
function updateKanbanScrollHints() {
  const board = document.getElementById("kanban-board");
  const wrap = board?.closest(".kanban-scroll-wrap");
  if (!board || !wrap) return;
  const canLeft = board.scrollLeft > 4;
  const canRight = board.scrollLeft + board.clientWidth < board.scrollWidth - 4;
  wrap.classList.toggle("can-scroll-left", canLeft);
  wrap.classList.toggle("can-scroll-right", canRight);
}

function bindTaskFilters() {
  document.querySelectorAll("[data-task-filter]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("[data-task-filter]").forEach(x => x.classList.remove("active"));
      chip.classList.add("active");
      state.taskFilter = chip.dataset.taskFilter;
      loadTasks();
    });
  });
}

async function loadTasks() {
  const ul = document.getElementById("task-list");
  if (!ul) return;
  const isPT = (state.lang || "pt") === "pt";
  ul.innerHTML = Array.from({length: 3}).map(() =>
    `<li class="task-item skeleton-item"><div class="skeleton skeleton-line w-60" style="height:12px;"></div></li>`
  ).join("");
  const page = await api("/tasks?limit=200");
  ul.innerHTML = "";
  const now = new Date();
  let items = page.items;
  if (state.taskFilter === "open") items = items.filter(x => x.status !== "done");
  if (state.taskFilter === "done") items = items.filter(x => x.status === "done");
  if (state.taskFilter === "overdue") items = items.filter(x => x.status !== "done" && x.due_at && new Date(x.due_at) < now);
  if (!items.length) {
    const filter = state.taskFilter;
    const specifics = {
      open:    { pt: ["Nenhuma tarefa aberta", "🎉 Tudo em dia. Aproveita pra prospectar."],
                 en: ["No open tasks", "🎉 All caught up. Time to prospect."] },
      done:    { pt: ["Nenhuma concluída ainda", "Complete uma tarefa pra ver aqui."],
                 en: ["Nothing completed yet", "Complete a task to see it here."] },
      overdue: { pt: ["Nada atrasado", "✅ Bom trabalho."],
                 en: ["Nothing overdue", "✅ Nice."] },
      _all:    { pt: ["Nenhuma tarefa ainda", 'Clique em "Nova tarefa" acima ou diga "crie tarefa: <título>".'],
                 en: ["No tasks yet", 'Click "New task" above or say "create task: <title>".'] },
    };
    const key = specifics[filter] ? filter : "_all";
    const [title, hint] = isPT ? specifics[key].pt : specifics[key].en;
    ul.innerHTML = `<li class="empty">
      <div class="empty-ico">✓</div>
      <div class="empty-title">${title}</div>
      <div class="empty-hint">${hint}</div>
    </li>`;
    return;
  }
  // Parse due dates with UTC coercion (same fix as newBadge/meetings)
  const parseDue = s => {
    if (!s) return null;
    const iso = /[zZ]|[+\-]\d\d:?\d\d$/.test(s) ? s : s + "Z";
    const t = Date.parse(iso);
    return Number.isFinite(t) ? new Date(t) : null;
  };
  // Sort: overdue first (nearest overdue on top), then upcoming ascending, no-date last, done at bottom
  items = items.map(x => ({ ...x, _due: parseDue(x.due_at) }));
  items.sort((a, b) => {
    if ((a.status === "done") !== (b.status === "done")) return a.status === "done" ? 1 : -1;
    if (!a._due && !b._due) return 0;
    if (!a._due) return 1;
    if (!b._due) return -1;
    return a._due - b._due;
  });
  const startOfDay = d => { const x = new Date(d); x.setHours(0,0,0,0); return x; };
  const today = startOfDay(now);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  const endOfWeek = new Date(today); endOfWeek.setDate(endOfWeek.getDate() + 7);
  const bucketOf = tk => {
    if (tk.status === "done") return isPT ? "Concluídas" : "Done";
    if (!tk._due) return isPT ? "Sem prazo" : "No due date";
    if (tk._due < now) return isPT ? "Atrasadas" : "Overdue";
    const d = startOfDay(tk._due);
    if (+d === +today) return isPT ? "Hoje" : "Today";
    if (+d === +tomorrow) return isPT ? "Amanhã" : "Tomorrow";
    if (d < endOfWeek) return isPT ? "Esta semana" : "This week";
    return isPT ? "Depois" : "Later";
  };
  const priorityIcon = p => ({ urgent: "🔥", high: "⬆", normal: "•", low: "⬇" }[p || "normal"] || "•");
  const buckets = new Map();
  for (const tk of items) {
    const k = bucketOf(tk);
    if (!buckets.has(k)) buckets.set(k, []);
    buckets.get(k).push(tk);
  }
  for (const [bucket, list] of buckets) {
    const header = document.createElement("li");
    header.className = "task-bucket-header";
    const isOverdue = bucket === (isPT ? "Atrasadas" : "Overdue");
    header.innerHTML = `<span${isOverdue ? ' style="color:var(--danger)"' : ''}>${escapeHtml(bucket)}</span><span class="task-count">${list.length}</span>`;
    ul.appendChild(header);
    for (const tk of list) {
      const li = document.createElement("li");
      li.className = "task-item" + (tk.status === "done" ? " task-done" : "");
      const overdue = tk._due && tk.status !== "done" && tk._due < now;
      const dueStr = tk._due ? tk._due.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
      li.innerHTML = `
        <div class="task-row">
          <button class="task-check" aria-label="${isPT ? 'Concluir' : 'Complete'}" ${tk.status === "done" ? 'disabled' : ''}>${tk.status === "done" ? "✓" : ""}</button>
          <span class="task-prio task-prio-${tk.priority || 'normal'}" title="${escapeHtml(tk.priority || 'normal')}">${priorityIcon(tk.priority)}</span>
          <div class="task-body">
            <div class="task-title">${escapeHtml(tk.title)}${newBadge(tk.created_at)}</div>
            ${dueStr ? `<div class="task-meta${overdue ? ' task-overdue' : ''}">${t("task_due")} ${escapeHtml(dueStr)}</div>` : ""}
          </div>
        </div>
      `;
      if (tk.status !== "done") {
        li.querySelector(".task-check").addEventListener("click", async ev => {
          ev.stopPropagation();
          await api(`/tasks/${tk.id}`, { method: "PATCH", body: { status: "done" } });
          toast(t("t_saved"), "success");
          await loadTasks();
        });
      }
      ul.appendChild(li);
    }
  }
}

async function loadMeetings() {
  const ul = document.getElementById("meetings-list");
  if (!ul) return;
  const isPT = (state.lang || "pt") === "pt";
  // Skeleton
  ul.innerHTML = Array.from({length: 3}).map(() =>
    `<li class="meeting-item skeleton-item"><div class="skeleton skeleton-line w-60" style="height:12px;"></div><div class="skeleton skeleton-line w-40" style="height:10px;margin-top:6px;"></div></li>`
  ).join("");
  const page = await api("/meetings?limit=100");
  ul.innerHTML = "";
  if (!page.items.length) {
    ul.innerHTML = `<li class="empty">
      <div class="empty-ico">📅</div>
      <div class="empty-title">${isPT ? "Nenhuma reunião ainda" : "No meetings yet"}</div>
      <div class="empty-hint">${isPT ? 'Clique em "Nova reunião" acima ou diga "agende reunião com &lt;contato&gt; amanhã 15h".' : 'Click "New meeting" above or say "schedule meeting with &lt;name&gt; tomorrow 3pm".'}</div>
    </li>`;
    return;
  }
  // Sort: nearest-future first (upcoming ascending), then past descending.
  const now = new Date();
  const items = [...page.items].map(m => {
    const iso = m.starts_at ? (/[zZ]|[+\-]\d\d:?\d\d$/.test(m.starts_at) ? m.starts_at : m.starts_at + "Z") : null;
    return { ...m, _dt: iso ? new Date(iso) : null };
  });
  items.sort((a, b) => {
    if (!a._dt) return 1; if (!b._dt) return -1;
    const aFuture = a._dt >= now, bFuture = b._dt >= now;
    if (aFuture !== bFuture) return aFuture ? -1 : 1;
    return aFuture ? (a._dt - b._dt) : (b._dt - a._dt);
  });
  // Group by day bucket
  const startOfDay = d => { const x = new Date(d); x.setHours(0,0,0,0); return x; };
  const today = startOfDay(now);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  const endOfWeek = new Date(today); endOfWeek.setDate(endOfWeek.getDate() + 7);
  const bucketOf = dt => {
    if (!dt) return isPT ? "Sem data" : "No date";
    const d = startOfDay(dt);
    if (d < today) return isPT ? "Passado" : "Past";
    if (+d === +today) return isPT ? "Hoje" : "Today";
    if (+d === +tomorrow) return isPT ? "Amanhã" : "Tomorrow";
    if (d < endOfWeek) return isPT ? "Esta semana" : "This week";
    return isPT ? "Depois" : "Later";
  };
  const buckets = new Map();
  for (const m of items) {
    const k = bucketOf(m._dt);
    if (!buckets.has(k)) buckets.set(k, []);
    buckets.get(k).push(m);
  }
  const fmtTime = dt => dt ? dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
  const fmtDate = dt => dt ? dt.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" }) : "";
  for (const [bucket, list] of buckets) {
    const header = document.createElement("li");
    header.className = "meeting-bucket-header";
    header.innerHTML = `<span>${escapeHtml(bucket)}</span><span class="meeting-count">${list.length}</span>`;
    ul.appendChild(header);
    for (const m of list) {
      const li = document.createElement("li");
      li.className = "meeting-item";
      const isFuture = m._dt && m._dt >= now;
      // "Happening now" = started within last 90min and hasn't reached end (default 60min)
      const ms = m._dt ? (now - m._dt) : null;
      const isNow = ms !== null && ms >= 0 && ms < 5400000;
      if (isNow) li.classList.add("meeting-now");
      const dateBits = [fmtDate(m._dt), fmtTime(m._dt)].filter(Boolean).join(" · ");
      const badge = isNow ? `<span class="status-pill open" title="${isPT ? "Acontecendo agora" : "Happening now"}">● ${isPT ? "AGORA" : "NOW"}</span>`
                   : isFuture ? `<span class="status-pill open">▶︎</span>`
                              : `<span class="status-pill done">✓</span>`;
      li.innerHTML = `
        <div class="meeting-row">
          <div class="meeting-icon">📅</div>
          <div class="meeting-body">
            <strong>${escapeHtml(m.title)}</strong>
            <div class="subtle">${escapeHtml(dateBits)}${m.location ? " · " + escapeHtml(m.location) : ""}</div>
          </div>
          ${badge}
        </div>
      `;
      ul.appendChild(li);
    }
  }
}

// ==================== CREATE + MODAL ====================
function bindCreateButtons() {
  document.getElementById("add-contact-btn")?.addEventListener("click", () =>
    openModal(t("add_contact"), [
      { name: "first_name", label: t("tbl_name") + " *", required: true },
      { name: "last_name", label: "Last name / Sobrenome" },
      { name: "email", label: t("tbl_email"), type: "email" },
      { name: "phone", label: t("tbl_phone") },
      { name: "job_title", label: t("tbl_job") },
    ], async data => { await api("/contacts", { method: "POST", body: data }); toast(t("t_created"), "success"); await loadContacts(); })
  );
  document.getElementById("add-company-btn")?.addEventListener("click", () =>
    openModal(t("add_company"), [
      { name: "name", label: t("tbl_name") + " *", required: true },
      { name: "domain", label: t("tbl_domain") },
      { name: "industry", label: t("tbl_industry") },
      { name: "website", label: "Website" },
    ], async data => { await api("/companies", { method: "POST", body: data }); toast(t("t_created"), "success"); await loadCompanies(); })
  );
  document.getElementById("add-opportunity-btn")?.addEventListener("click", () =>
    openModal(t("add_opp"), [
      { name: "name", label: t("tbl_name") + " *", required: true },
      { name: "amount", label: t("tbl_amount"), type: "number" },
      { name: "currency", label: "Currency", value: "USD" },
    ], async data => { await api("/opportunities", { method: "POST", body: { ...data, amount: parseFloat(data.amount || 0) } }); toast(t("t_created"), "success"); await loadOpportunities(); })
  );
  document.getElementById("add-task-btn")?.addEventListener("click", () =>
    openModal(t("add_task"), [
      { name: "title", label: "Title / Título *", required: true },
      { name: "priority", label: "Priority (low/normal/high/urgent)", value: "normal" },
      { name: "due_at", label: "Due at (ISO datetime, optional)", type: "datetime-local" },
    ], async data => {
      if (data.due_at) data.due_at = new Date(data.due_at).toISOString();
      await api("/tasks", { method: "POST", body: data });
      toast(t("t_created"), "success");
      await loadTasks();
    })
  );
  document.getElementById("add-lead-btn")?.addEventListener("click", () =>
    openModal(t("add_lead"), [
      { name: "first_name", label: t("tbl_name") + " *", required: true },
      { name: "last_name", label: "Last name / Sobrenome" },
      { name: "email", label: t("tbl_email"), type: "email" },
      { name: "company_name", label: t("tbl_company") },
      { name: "source", label: t("tbl_source") },
    ], async data => { await api("/leads", { method: "POST", body: data }); toast(t("t_created"), "success"); await loadLeads(); })
  );
  document.getElementById("add-meeting-btn")?.addEventListener("click", () =>
    openModal(t("add_meeting"), [
      { name: "title", label: "Title / Título *", required: true },
      { name: "starts_at", label: "Start (ISO)", type: "datetime-local", required: true },
      { name: "ends_at", label: "End (ISO)", type: "datetime-local", required: true },
      { name: "location", label: "Location / Local" },
    ], async data => {
      data.starts_at = new Date(data.starts_at).toISOString();
      data.ends_at = new Date(data.ends_at).toISOString();
      await api("/meetings", { method: "POST", body: data });
      toast(t("t_created"), "success");
      await loadMeetings();
    })
  );
  document.getElementById("toggle-rules-btn")?.addEventListener("click", () => {
    const s = document.getElementById("lead-rules-section");
    s.classList.toggle("hidden");
    if (!s.classList.contains("hidden")) loadRules();
  });
  document.getElementById("add-rule-btn")?.addEventListener("click", () =>
    openModal(t("add_rule"), [
      { name: "name", label: t("tbl_name") + " *", required: true },
      { name: "field", label: "Field (source, email_domain, company_name, score, status)", required: true },
      { name: "op", label: "Op (iequals, icontains, regex, gt, in, is_present, ...)", required: true },
      { name: "value", label: t("tbl_value") + " (blank for is_present/is_absent)" },
      { name: "score_delta", label: "Score delta (integer)", type: "number", value: "0" },
    ], async data => {
      data.score_delta = parseInt(data.score_delta || "0", 10);
      await api("/lead-scoring/rules", { method: "POST", body: data });
      toast(t("t_created"), "success");
      await loadRules();
    })
  );
  document.getElementById("add-workflow-btn")?.addEventListener("click", () => openWorkflowEditor());

  document.getElementById("recalc-btn")?.addEventListener("click", async () => {
    const r = await api("/lead-scoring/recalculate", { method: "POST" });
    toast(`${t("t_saved")}: ${r.leads_updated}/${r.leads_scanned}`, "success");
    await loadLeads();
  });

  document.getElementById("contact-search")?.addEventListener("input", debounce(loadContacts, 250));
  document.getElementById("company-search")?.addEventListener("input", debounce(loadCompanies, 250));

  // Paginacao completa — server limita 200/req; junta ate' 5000.
  async function fetchAllPages(path) {
    const LIMIT = 200, MAX = 5000;
    const items = [];
    let offset = 0;
    while (offset < MAX) {
      const sep = path.includes("?") ? "&" : "?";
      const p = await api(`${path}${sep}limit=${LIMIT}&offset=${offset}`);
      const batch = p.items || [];
      items.push(...batch);
      if (batch.length < LIMIT) break;
      offset += LIMIT;
    }
    return items;
  }

  document.getElementById("export-contacts-csv")?.addEventListener("click", async () => {
    const items = await fetchAllPages("/contacts");
    downloadCsv(`contacts-${new Date().toISOString().slice(0,10)}.csv`,
      items.map(c => ({
        first_name: c.first_name || "", last_name: c.last_name || "",
        email: c.email || "", phone: c.phone || "", job_title: c.job_title || "",
        department: c.department || "", created_at: c.created_at || "",
      })));
  });
  document.getElementById("export-companies-csv")?.addEventListener("click", async () => {
    const items = await fetchAllPages("/companies");
    downloadCsv(`companies-${new Date().toISOString().slice(0,10)}.csv`,
      items.map(c => ({
        name: c.name, domain: c.domain || "", industry: c.industry || "",
        size: c.size || "", website: c.website || "", phone: c.phone || "",
        annual_revenue: c.annual_revenue || "", created_at: c.created_at || "",
      })));
  });
  document.getElementById("export-opps-csv")?.addEventListener("click", async () => {
    const [items, pipelines] = await Promise.all([fetchAllPages("/opportunities"), api("/pipelines")]);
    const stageById = {};
    for (const p of pipelines) for (const s of p.stages) stageById[s.id] = s.name;
    downloadCsv(`opportunities-${new Date().toISOString().slice(0,10)}.csv`,
      items.map(o => ({
        name: o.name, stage: stageById[o.stage_id] || "",
        amount: o.amount || 0, currency: o.currency, status: o.status,
        probability: o.probability, expected_close_date: o.expected_close_date || "",
        closed_at: o.closed_at || "", created_at: o.created_at || "",
      })));
  });

  document.getElementById("import-contacts-csv")?.addEventListener("change", async ev => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const status = document.getElementById("csv-status");
    status.textContent = "Parsing CSV…";
    try {
      const text = await file.text();
      const rows = parseCsv(text);
      if (!rows.length) throw new Error("empty file");
      const [header, ...body] = rows;
      const normalize = h => h.trim().toLowerCase().replace(/\s+/g, "_");
      const columns = header.map(normalize);
      const items = body.filter(r => r.some(c => (c || "").trim())).map(r => {
        const o = {};
        columns.forEach((k, i) => { if (r[i] !== undefined && r[i] !== "") o[k] = r[i]; });
        if (o.name && !o.first_name) {
          const parts = o.name.trim().split(/\s+/);
          o.first_name = parts.shift();
          if (parts.length) o.last_name = parts.join(" ");
          delete o.name;
        }
        return o;
      });
      if (!items.length) throw new Error("no data rows");
      status.textContent = `Uploading ${items.length} contacts…`;
      const r = await api("/contacts/bulk", { method: "POST", body: { items } });
      status.textContent = `Imported ${r.created} contact(s). ${r.failed ? r.failed + " failed." : ""}`;
      if (r.errors?.length) console.warn("csv import errors:", r.errors);
      toast(`${t("t_imported")} ${r.created}`, "success");
      await loadContacts();
    } catch (err) {
      status.textContent = "Import failed: " + err.message;
      toast(`${t("t_import_failed")}: ${err.message}`, "error");
    } finally {
      ev.target.value = "";
    }
  });
}

function parseCsv(text) {
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  const rows = [];
  let field = "", row = [], inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else field += c;
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
      else if (c === "\r") { /* skip */ }
      else field += c;
    }
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function openWorkflowEditor() {
  const modal = document.getElementById("modal");
  document.getElementById("modal-title").textContent = t("add_workflow");
  const form = document.getElementById("modal-form");
  const triggerExample = JSON.stringify({
    kind: "created", subject_type: "lead",
    conditions: [{ field: "subject.score", op: "gte", value: "50" }],
  }, null, 2);
  const stepsExample = JSON.stringify([
    { kind: "create_task", payload: { title: "Follow up with {{subject_id}}", due_in_days: 2, priority: "high" } },
  ], null, 2);
  form.innerHTML = `
    <label>${t("tbl_name")} *<input name="name" required /></label>
    <label>Description<input name="description" /></label>
    <label>Trigger JSON<textarea name="trigger" style="min-height:120px;font-family:monospace">${escapeHtml(triggerExample)}</textarea>
      <span class="json-error" data-target="trigger" style="color:var(--danger);font-size:0.8em;"></span></label>
    <label>Steps JSON (array)<textarea name="steps" style="min-height:120px;font-family:monospace">${escapeHtml(stepsExample)}</textarea>
      <span class="json-error" data-target="steps" style="color:var(--danger);font-size:0.8em;"></span></label>
  `;
  // Live JSON validation
  const validate = (ta) => {
    const err = form.querySelector(`.json-error[data-target="${ta.name}"]`);
    if (!ta.value.trim()) { err.textContent = ""; return true; }
    try { JSON.parse(ta.value); err.textContent = "✅ JSON válido"; err.style.color = "var(--ok)"; return true; }
    catch (e) { err.textContent = `⚠ ${e.message}`; err.style.color = "var(--danger)"; return false; }
  };
  form.querySelectorAll("textarea[name='trigger'], textarea[name='steps']").forEach(ta => {
    ta.addEventListener("input", debounce(() => validate(ta), 200));
    validate(ta);  // initial
  });
  const close = () => modal.classList.add("hidden");
  document.getElementById("modal-cancel").onclick = close;
  document.getElementById("modal-x").onclick = close;
  document.getElementById("modal-save").onclick = async () => {
    const data = Object.fromEntries(new FormData(form));
    try {
      const payload = {
        name: data.name,
        description: data.description || null,
        trigger: JSON.parse(data.trigger),
        steps: JSON.parse(data.steps),
      };
      await api("/workflows", { method: "POST", body: payload });
      close();
      toast(t("t_created"), "success");
      await loadAutomations();
    } catch (err) { toast(err.message, "error"); }
  };
  modal.classList.remove("hidden");
}

function openModal(title, fields, onSave) {
  const modal = document.getElementById("modal");
  document.getElementById("modal-title").textContent = title;
  // Modais especializados (ex.: "Conectar dispositivo") trocam o rotulo do
  // botao. Restaurar aqui cobre tambem quem fechou com Esc, que nao passa
  // pelos botoes de cancelar/fechar.
  document.getElementById("modal-save").textContent = "Salvar";
  const form = document.getElementById("modal-form");
  form.innerHTML = "";
  for (const f of fields) {
    const wrap = document.createElement("label");
    wrap.innerHTML = `${f.label}<input name="${f.name}" ${f.type ? `type="${f.type}"` : ""} ${f.required ? "required" : ""} value="${f.value || ""}" />`;
    form.appendChild(wrap);
  }
  // Hidden submit button — sem ele, Enter num input nao dispara form.onsubmit
  // (o botao Salvar visivel esta fora do <form>).
  const hidden = document.createElement("button");
  hidden.type = "submit"; hidden.style.display = "none"; hidden.setAttribute("aria-hidden", "true");
  form.appendChild(hidden);
  // Remember focus to restore on close (a11y)
  const returnFocus = document.activeElement;
  const close = () => {
    modal.classList.add("hidden");
    if (returnFocus && typeof returnFocus.focus === "function" && document.contains(returnFocus)) {
      try { returnFocus.focus(); } catch {}
    }
  };
  const submit = async () => {
    const data = Object.fromEntries(new FormData(form));
    for (const k of Object.keys(data)) if (data[k] === "") delete data[k];
    try { await onSave(data); close(); }
    catch (err) { toast(err.message, "error"); }
  };
  document.getElementById("modal-cancel").onclick = close;
  document.getElementById("modal-x").onclick = close;
  document.getElementById("modal-save").onclick = submit;
  // Enter within any input submits the form (natural expectation)
  form.onsubmit = ev => { ev.preventDefault(); submit(); };
  modal.classList.remove("hidden");
  setTimeout(() => form.querySelector("input")?.focus(), 50);
}

// ==================== DRAWER ====================
const DRAWER_ENDPOINT = {
  contact: id => `/contacts/${id}`,
  company: id => `/companies/${id}`,
  opportunity: id => `/opportunities/${id}`,
  lead: id => `/leads/${id}`,
};
const DRAWER_LABELS_PT = { contact: "Contato", company: "Empresa", opportunity: "Oportunidade", lead: "Lead" };
const DRAWER_LABELS_EN = { contact: "Contact", company: "Company", opportunity: "Opportunity", lead: "Lead" };
const DRAWER_LABELS = new Proxy({}, { get: (_, k) => ((state.lang || "pt") === "pt" ? DRAWER_LABELS_PT : DRAWER_LABELS_EN)[k] });
const DRAWER_NOTE_KEY = { contact: "related_contact_id", company: "related_company_id", opportunity: "related_opportunity_id", lead: "related_lead_id" };
let drawerCurrent = null;

// Track last-opened entity for implicit context in Jarvis chat
state.lastEntityContext = null;  // { type, id, name, expires }

// Recently-viewed entities — kept in localStorage, surfaced on dashboard.
const RECENT_KEY = "visiquost.recent";
function pushRecent(type, id, name) {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]")
      .filter(r => !(r.type === type && r.id === id));
    list.unshift({ type, id, name: name || "?", at: Date.now() });
    localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 8)));
  } catch (_) { /* ignore */ }
}
function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (_) { return []; }
}

async function openDrawer(type, id) {
  drawerCurrent = { type, id };
  const drawer = document.getElementById("drawer");
  drawer.classList.remove("hidden");
  // Remember what had focus so we can restore it on close (a11y)
  drawer._returnFocus = document.activeElement;
  // Focus the close button so keyboard users can immediately Esc/Tab-out
  setTimeout(() => document.getElementById("drawer-close")?.focus(), 60);
  document.getElementById("drawer-title").textContent = `${DRAWER_LABELS[type]}`;
  // Skeleton lines while entity loads (cleaner than a "…" placeholder).
  document.getElementById("drawer-body").innerHTML =
    '<div class="skeleton skeleton-line w-60"></div>' +
    '<div class="skeleton skeleton-line w-80"></div>' +
    '<div class="skeleton skeleton-line w-40"></div>' +
    '<div class="skeleton skeleton-line w-full"></div>';
  document.getElementById("drawer-notes").innerHTML = "";
  document.getElementById("drawer-activity").innerHTML = "";
  try {
    const entity = await api(DRAWER_ENDPOINT[type](id));
    renderDrawerBody(type, entity);
    // Cache entity as context for the Jarvis chat (5-min TTL)
    const name = entity.name || `${entity.first_name || ""} ${entity.last_name || ""}`.trim() || type;
    state.lastEntityContext = { type, id, name, expires: Date.now() + 5 * 60 * 1000 };
    refreshContextChip();
    pushRecent(type, id, name);
    await Promise.all([loadDrawerNotes(type, id), loadDrawerActivity(type, id)]);
  } catch (err) { document.getElementById("drawer-body").textContent = `${t("t_error")}: ${err.message}`; }
}

const DRAWER_EDITABLE = {
  contact: new Set(["first_name", "last_name", "email", "phone", "mobile", "job_title", "department"]),
  company: new Set(["name", "domain", "industry", "size", "website", "phone", "annual_revenue"]),
  opportunity: new Set(["name", "amount", "currency", "probability", "expected_close_date"]),
  lead: new Set(["first_name", "last_name", "email", "phone", "company_name", "source"]),
};

function renderQuickActions(type, entity) {
  if (type !== "contact") return "";
  const email = entity.email || "";
  const phone = (entity.phone || entity.mobile || "").replace(/[^\d+]/g, "");
  const acts = [];
  if (email) acts.push(`<a href="mailto:${escapeHtml(email)}" class="qa-btn" title="Email">✉️ Email</a>`);
  if (phone) acts.push(`<a href="tel:${escapeHtml(phone)}" class="qa-btn" title="Ligar">📞 Ligar</a>`);
  if (phone) acts.push(`<a href="https://wa.me/${escapeHtml(phone.replace(/^\+/, ""))}" target="_blank" class="qa-btn" title="WhatsApp">💬 WhatsApp</a>`);
  if (email) acts.push(`<button class="qa-btn" data-templates="${entity.id}" title="Template de email">📝 Template</button>`);
  acts.push(`<button class="qa-btn" data-vcard="${entity.id}" title="Baixar vCard">💳 vCard</button>`);
  acts.push(`<button class="qa-btn" data-add-task="${entity.id}" title="Criar tarefa vinculada">+ Tarefa</button>`);
  acts.push(`<button class="qa-btn" data-link-company="${entity.id}" title="Vincular empresa">🏢 Empresa</button>`);
  return `<div class="quick-actions">${acts.join("")}</div>`;
}

function renderDrawerBody(type, e) {
  const body = document.getElementById("drawer-body");
  const fields = {
    contact: ["first_name", "last_name", "email", "phone", "mobile", "job_title", "department"],
    company: ["name", "domain", "industry", "size", "website", "phone", "annual_revenue"],
    opportunity: ["name", "status", "amount", "currency", "probability", "expected_close_date", "closed_at"],
    lead: ["first_name", "last_name", "email", "phone", "company_name", "source", "status", "score"],
  }[type];
  const editable = DRAWER_EDITABLE[type] || new Set();
  const dl = document.createElement("dl");
  for (const f of fields) {
    const v = e[f];
    if (v === null || v === undefined || v === "") continue;
    const dt = document.createElement("dt");
    dt.textContent = f.replace(/_/g, " ");
    const dd = document.createElement("dd");
    dd.textContent = String(v);
    if (editable.has(f)) {
      dd.classList.add("editable");
      dd.title = state.lang === "pt" ? "Clique para editar" : "Click to edit";
      dd.addEventListener("click", () => startInlineEdit(type, e.id, f, dd));
    }
    dl.appendChild(dt);
    dl.appendChild(dd);
  }
  body.innerHTML = "";
  // Big avatar + name at top of drawer for identity confirmation
  const displayName = e.name || `${e.first_name || ""} ${e.last_name || ""}`.trim() || e.email || "?";
  const hdr = document.createElement("div");
  hdr.className = "drawer-entity-hdr";
  hdr.style.cssText = "display:flex;align-items:center;gap:12px;padding:0 0 12px 0;";
  hdr.innerHTML = `${avatarChip(displayName, {size: 44, sat: 60, light: 45})}
    <div>
      <div style="font-size:1.15em;font-weight:600;color:var(--fg);">${escapeHtml(displayName)}</div>
      <div class="subtle" style="font-size:0.82em;">${escapeHtml(e.email || e.domain || e.company_name || type)}</div>
    </div>`;
  body.appendChild(hdr);
  const qa = renderQuickActions(type, e);
  if (qa) {
    const div = document.createElement("div");
    div.innerHTML = qa;
    body.appendChild(div);
  }
  body.appendChild(dl);
  // Wire template picker
  body.querySelectorAll("[data-templates]").forEach(btn => {
    btn.addEventListener("click", async () => openTemplatePicker(btn.dataset.templates, e.email));
  });
  // Wire add-task (contact-linked)
  body.querySelectorAll("[data-add-task]").forEach(btn => {
    btn.addEventListener("click", () => {
      openModal(state.lang === "pt" ? "+ Nova tarefa vinculada" : "+ New linked task", [
        { name: "title", label: state.lang === "pt" ? "Título *" : "Title *", required: true, value: `Follow-up com ${e.first_name || ""}`.trim() },
        { name: "priority", label: "Priority (low/normal/high/urgent)", value: "normal" },
        { name: "due_at", label: "Due at", type: "datetime-local" },
      ], async data => {
        if (data.due_at) data.due_at = new Date(data.due_at).toISOString();
        data.related_contact_id = btn.dataset.addTask;
        await api("/tasks", { method: "POST", body: data });
        toast(t("t_created"), "success");
      });
    });
  });
  // Wire link-company picker
  body.querySelectorAll("[data-link-company]").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        const page = await api("/companies?limit=100");
        const items = page.items || [];
        if (!items.length) { toast(state.lang === "pt" ? "Sem empresas cadastradas" : "No companies yet", "warn"); return; }
        const chosen = prompt(
          (state.lang === "pt" ? "Escolha a empresa:\n" : "Choose company:\n") +
          items.map((c, i) => `${i + 1}. ${c.name}`).join("\n"),
          "1"
        );
        if (!chosen) return;
        const idx = parseInt(chosen, 10) - 1;
        if (idx < 0 || idx >= items.length) return;
        await api(`/contacts/${btn.dataset.linkCompany}`, {
          method: "PATCH", body: { company_id: items[idx].id },
        });
        toast(state.lang === "pt" ? `✓ Vinculado a ${items[idx].name}` : `✓ Linked to ${items[idx].name}`, "success");
        await openDrawer("contact", btn.dataset.linkCompany);
      } catch (err) { toast(err.message, "error"); }
    });
  });
  // Wire vCard download
  body.querySelectorAll("[data-vcard]").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        const resp = await fetch(`${API}/contacts/${btn.dataset.vcard}/vcard`, {
          headers: { Authorization: `Bearer ${state.token}` },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${(e.first_name || "contact").replace(/\s+/g, "_")}.vcf`;
        a.click();
        URL.revokeObjectURL(url);
        toast(state.lang === "pt" ? "vCard salvo" : "vCard saved", "success", 1500);
      } catch (err) { toast(err.message, "error"); }
    });
  });
}

async function openTemplatePicker(contactId, email) {
  try {
    const list = await api("/email-templates");
    const items = list.templates || [];
    if (!items.length) return;
    const chosen = prompt(
      (state.lang === "pt" ? "Escolha o template:\n" : "Choose a template:\n") +
      items.map((t, i) => `${i + 1}. ${t.name}`).join("\n"),
      "1"
    );
    if (!chosen) return;
    const idx = parseInt(chosen, 10) - 1;
    if (idx < 0 || idx >= items.length) return;
    const key = items[idx].key;
    const r = await api(`/email-templates/${key}/render?contact_id=${contactId}`);
    const subject = encodeURIComponent(r.rendered.subject);
    const body = encodeURIComponent(r.rendered.body);
    window.location.href = `mailto:${encodeURIComponent(email)}?subject=${subject}&body=${body}`;
  } catch (err) { toast(err.message, "error"); }
}

function startInlineEdit(type, id, field, dd) {
  if (dd.querySelector("input")) return;  // already editing
  const current = dd.textContent;
  const input = document.createElement("input");
  input.value = current;
  input.className = "inline-edit-input";
  dd.textContent = "";
  dd.appendChild(input);
  input.focus();
  input.select();

  const finish = async (save) => {
    if (!save) { dd.textContent = current; return; }
    const nv = input.value.trim();
    if (nv === current) { dd.textContent = current; return; }
    const path = { contact: "contacts", company: "companies", opportunity: "opportunities", lead: "leads" }[type];
    if (!path) { dd.textContent = current; return; }
    try {
      let value = nv;
      if (["amount", "probability", "annual_revenue"].includes(field)) value = parseFloat(nv) || 0;
      if (field === "score") value = parseInt(nv, 10) || 0;
      await api(`/${path}/${id}`, { method: "PATCH", body: { [field]: value } });
      dd.textContent = nv;
      toast(t("t_saved"), "success", 1500);
    } catch (err) {
      dd.textContent = current;
      toast(err.message, "error");
    }
  };
  input.addEventListener("keydown", ev => {
    if (ev.key === "Enter") { ev.preventDefault(); finish(true); }
    else if (ev.key === "Escape") { ev.preventDefault(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
}

async function loadDrawerNotes(type, id) {
  const key = DRAWER_NOTE_KEY[type];
  const paramName = key === "related_contact_id" ? "contact_id" : key === "related_company_id" ? "company_id" : key === "related_opportunity_id" ? "opportunity_id" : "lead_id";
  const page = await api(`/notes?${paramName}=${id}&limit=20`);
  const ul = document.getElementById("drawer-notes");
  ul.innerHTML = "";
  if (!page.items.length) {
    const isPT = (state.lang || "pt") === "pt";
    ul.innerHTML = `<li class="empty" style="padding:16px 8px;text-align:center;">
      <div style="font-size:1.6em;opacity:0.55;margin-bottom:4px;">📝</div>
      <div style="color:var(--fg-3);font-size:0.86em;">${isPT ? "Sem notas ainda." : "No notes yet."}</div>
      <div style="color:var(--fg-4);font-size:0.75em;margin-top:2px;">${isPT ? "Use o campo acima para adicionar contexto." : "Use the field above to add context."}</div>
    </li>`;
    return;
  }
  for (const n of page.items) {
    const li = document.createElement("li");
    li.textContent = n.body;
    ul.appendChild(li);
  }
}

let drawerActivityFilter = "all";
async function loadDrawerActivity(type, id) {
  const page = await api(`/activities?subject_type=${type}&subject_id=${id}&limit=50`);
  const ul = document.getElementById("drawer-activity");
  ul.innerHTML = "";
  const items = drawerActivityFilter === "all"
    ? page.items
    : page.items.filter(a => a.kind === drawerActivityFilter);
  if (!items.length) {
    const isPT = (state.lang || "pt") === "pt";
    ul.innerHTML = `<li class="empty" style="padding:16px 8px;text-align:center;">
      <div style="font-size:1.6em;opacity:0.55;margin-bottom:4px;">📊</div>
      <div style="color:var(--fg-3);font-size:0.86em;">${isPT ? "Sem atividade ainda." : "No activity yet."}</div>
    </li>`;
    return;
  }
  for (const a of items) {
    const li = document.createElement("li");
    const when = new Date(a.occurred_at).toLocaleString();
    li.innerHTML = `<span class="subtle">${when}</span> · ${escapeHtml(a.kind)}${a.summary ? " — " + escapeHtml(a.summary) : ""}`;
    ul.appendChild(li);
  }
}

function bindDrawer() {
  document.getElementById("drawer-close")?.addEventListener("click", closeDrawer);
  // Timeline kind filter chips
  document.querySelectorAll("[data-kind-filter]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("[data-kind-filter]").forEach(x => x.classList.remove("active"));
      chip.classList.add("active");
      drawerActivityFilter = chip.dataset.kindFilter;
      if (drawerCurrent) loadDrawerActivity(drawerCurrent.type, drawerCurrent.id);
    });
  });
  document.getElementById("drawer-ask-jarvis")?.addEventListener("click", () => {
    if (!drawerCurrent) return;
    // Compose a context-question and route through Jarvis
    const KIND_LABEL = { contact: "contato", company: "empresa", opportunity: "oportunidade", lead: "lead" };
    const KIND_LABEL_EN = { contact: "contact", company: "company", opportunity: "opportunity", lead: "lead" };
    const label = (state.lang === "pt" ? KIND_LABEL : KIND_LABEL_EN)[drawerCurrent.type] || drawerCurrent.type;
    const titleEl = document.getElementById("drawer-title");
    const bodyText = document.getElementById("drawer-body")?.textContent || "";
    const nameMatch = bodyText.match(/first name\s*(\S+.*?)(?:\n|last name|email|$)/i);
    const name = nameMatch ? nameMatch[1].trim() :
                 titleEl?.textContent?.split(" ")[0] || label;
    // Move focus to the Jarvis chat and pre-fill the input
    const input = document.getElementById("jarvis-input");
    if (!input) return;
    const prompt = state.lang === "pt"
      ? `contexto sobre este ${label}: resuma últimas atividades e sugira próximo passo`
      : `context on this ${label}: summarize recent activity and suggest a next step`;
    input.value = prompt;
    // Open FAB if mobile
    document.body.classList.add("jarvis-open");
    setTimeout(() => {
      input.focus();
      input.select();
    }, 250);
  });
  document.getElementById("drawer-note-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    if (!drawerCurrent) return;
    const input = document.getElementById("drawer-note-input");
    const body = input.value.trim();
    if (!body) return;
    const key = DRAWER_NOTE_KEY[drawerCurrent.type];
    await api("/notes", { method: "POST", body: { body, [key]: drawerCurrent.id } });
    input.value = "";
    await loadDrawerNotes(drawerCurrent.type, drawerCurrent.id);
    await loadDrawerActivity(drawerCurrent.type, drawerCurrent.id);
  });
}

function closeDrawer() {
  const drawer = document.getElementById("drawer");
  drawer.classList.add("hidden");
  // Restore focus to whatever triggered the drawer (a11y)
  const ret = drawer._returnFocus;
  drawer._returnFocus = null;
  if (ret && typeof ret.focus === "function" && document.contains(ret)) {
    try { ret.focus(); } catch {}
  }
  drawerCurrent = null;
}

// ==================== JARVIS ====================
function bindJarvis() {
  document.getElementById("jarvis-fab")?.addEventListener("click", () => {
    document.body.classList.add("jarvis-open");
    setTimeout(() => document.getElementById("jarvis-input")?.focus(), 220);
  });
  document.getElementById("jarvis-close-mobile")?.addEventListener("click", () => {
    document.body.classList.remove("jarvis-open");
  });
  // Desktop collapse/reopen — remembers preference via localStorage.
  const setCollapsed = (collapsed) => {
    document.body.classList.toggle("jarvis-collapsed", collapsed);
    try { localStorage.setItem("jarvis_collapsed", collapsed ? "1" : "0"); } catch {}
  };
  if (localStorage.getItem("jarvis_collapsed") === "1") setCollapsed(true);
  document.getElementById("jarvis-collapse")?.addEventListener("click", () => setCollapsed(true));
  document.getElementById("jarvis-reopen")?.addEventListener("click", () => {
    setCollapsed(false);
    setTimeout(() => document.getElementById("jarvis-input")?.focus(), 220);
  });

  // Kanban scroll hints: fade edges + arrow buttons appear/hide with scroll position.
  const kanbanBoard = document.getElementById("kanban-board");
  if (kanbanBoard) {
    kanbanBoard.addEventListener("scroll", updateKanbanScrollHints, { passive: true });
    window.addEventListener("resize", updateKanbanScrollHints);
    const scrollBy = (dx) => kanbanBoard.scrollBy({ left: dx, behavior: "smooth" });
    document.getElementById("kanban-scroll-right")?.addEventListener("click", () => scrollBy(300));
    document.getElementById("kanban-scroll-left")?.addEventListener("click", () => scrollBy(-300));
  }

  const form = document.getElementById("jarvis-form");
  const jarvisInput = document.getElementById("jarvis-input");
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const message = jarvisInput.value.trim();
    if (!message) return;
    appendJarvis("user", message);
    jarvisInput.value = "";
    await jarvisSay(message);
  });
  // Also submit on Ctrl/Cmd+Enter for muscle-memory with other AI apps
  jarvisInput?.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  document.querySelectorAll(".qbtn").forEach(b => {
    b.addEventListener("click", async () => {
      const msg = b.dataset.quick;
      appendJarvis("user", msg);
      await jarvisSay(msg);
    });
  });
}

async function jarvisSay(message) {
  try {
    const body = state.conversation_id ? { message, conversation_id: state.conversation_id } : { message };
    const resp = await api("/jarvis/chat", { method: "POST", body });
    if (resp.conversation_id) {
      state.conversation_id = resp.conversation_id;
      localStorage.setItem(CONV_KEY, resp.conversation_id);
    }
    // Mode chip: primarily "local" (we never call cloud), append user's
    // tone preference if set for at-a-glance state confirmation.
    const modeEl = document.getElementById("jarvis-mode");
    if (modeEl) {
      const tonePref = state.workspacePref?.tone || null;
      const base = resp.fallback ? "local·hint" : "local";
      modeEl.textContent = tonePref ? `${base}·${tonePref}` : base;
    }
    appendJarvis("assistant", resp.reply, resp.fallback);
    // Refresh views on state-changing intents
    if (["create_task", "create_note", "mark_task_done", "move_opportunity_stage", "reschedule_meeting",
         "delete_task", "delete_contact", "delete_company", "delete_opportunity", "delete_lead",
         "mark_opportunity", "schedule_meeting", "enrich_company"].includes(resp.intent)) {
      routes[state.page]?.();
      if (state.page === "dashboard") await loadDashboard();
    }
    // Offer undo when a delete happened
    const deleteIntents = { delete_task: "task", delete_contact: "contact", delete_company: "company",
                             delete_opportunity: "opportunity", delete_lead: "lead" };
    const kind = deleteIntents[resp.intent];
    if (kind && Array.isArray(resp.tool_calls)) {
      const tc = resp.tool_calls.find(x => x?.result?.id);
      if (tc) {
        const label = state.lang === "pt" ? `🗑 ${kind} apagado(a)` : `🗑 ${kind} deleted`;
        toastUndo(label, kind, tc.result.id);
      }
    }
    return resp;
  } catch (err) {
    appendJarvis("assistant", `${t("t_error")}: ${err.message}`, true);
  }
}

function appendJarvis(role, text, fallback = false) {
  const log = document.getElementById("jarvis-log");
  // Remove welcome banner on first user message
  const welcome = log.querySelector(".jarvis-welcome");
  if (welcome && role === "user") welcome.remove();
  const msg = document.createElement("div");
  msg.className = `jarvis-msg ${role}${fallback ? " fallback" : ""}`;
  // Minimal safe markdown for assistant messages: inline `code` and **bold**.
  // Users' own messages stay plain text to avoid injection surprise.
  if (role === "assistant") {
    const escaped = escapeHtml(text);
    const rendered = escaped
      .replace(/`([^`\n]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    msg.innerHTML = rendered;
  } else {
    msg.textContent = text;
  }
  log.appendChild(msg);
  log.scrollTop = log.scrollHeight;
}

// ==================== COMMAND PALETTE (⌘K) ====================
// Backdrop click to close overlays — standard SaaS behavior (Notion/Linear/Twenty)
function bindOverlayClose() {
  // modal: click outside .modal-inner closes it
  const modal = document.getElementById("modal");
  if (modal) modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
  // cmdk: click outside .cmdk-inner closes it
  const cmdk = document.getElementById("cmdk");
  if (cmdk) cmdk.addEventListener("click", (e) => {
    if (e.target === cmdk) cmdk.classList.add("hidden");
  });
  // help modal: same pattern
  const kb = document.getElementById("kb-help");
  if (kb) kb.addEventListener("click", (e) => {
    if (e.target === kb) kb.classList.add("hidden");
  });
}

function bindCmdK() {
  const overlay = document.getElementById("cmdk");
  const input = document.getElementById("cmdk-input");
  const results = document.getElementById("cmdk-results");
  let items = [];
  let activeIdx = 0;

  const commands = [
    { kind: "cmd", label: "Ir para Painel · Go to Dashboard", action: () => gotoPage("dashboard") },
    { kind: "cmd", label: "Ir para Contatos · Contacts", action: () => gotoPage("contacts") },
    { kind: "cmd", label: "Ir para Empresas · Companies", action: () => gotoPage("companies") },
    { kind: "cmd", label: "Ir para Oportunidades · Opportunities", action: () => gotoPage("opportunities") },
    { kind: "cmd", label: "Ir para Leads", action: () => gotoPage("leads") },
    { kind: "cmd", label: "Ir para Pipeline / Kanban", action: () => gotoPage("kanban") },
    { kind: "cmd", label: "Ir para Tarefas · Tasks", action: () => gotoPage("tasks") },
    { kind: "cmd", label: "Ir para Reuniões · Meetings", action: () => gotoPage("meetings") },
    { kind: "cmd", label: "Ir para Automações · Automations", action: () => gotoPage("automations") },
    { kind: "cmd", label: "Ir para Integrações · Integrations", action: () => gotoPage("integrations") },
    { kind: "cmd", label: "🌓 Alternar tema · Toggle theme", action: () => { state.theme = state.theme === "dark" ? "light" : "dark"; applyTheme(); } },
    { kind: "cmd", label: "🌐 Alternar idioma · Switch language", action: () => { state.lang = state.lang === "en" ? "pt" : "en"; localStorage.setItem(LANG_KEY, state.lang); applyStaticI18n(); applyLang(); routes[state.page]?.(); } },
    { kind: "cmd", label: "+ Novo contato · New contact", action: () => document.getElementById("add-contact-btn")?.click() },
    { kind: "cmd", label: "+ Nova empresa · New company", action: () => document.getElementById("add-company-btn")?.click() },
    { kind: "cmd", label: "+ Nova oportunidade · New opportunity", action: () => document.getElementById("add-opportunity-btn")?.click() },
    { kind: "cmd", label: "+ Nova tarefa · New task", action: () => document.getElementById("add-task-btn")?.click() },
    { kind: "cmd", label: "+ Novo lead · New lead", action: () => document.getElementById("add-lead-btn")?.click() },
  ];

  function open() {
    overlay.classList.remove("hidden");
    input.value = "";
    input.focus();
    render("");
  }
  function close() { overlay.classList.add("hidden"); }

  async function render(q) {
    activeIdx = 0;
    items = [];
    const filteredCmds = commands.filter(c => !q || c.label.toLowerCase().includes(q.toLowerCase()));
    items.push(...filteredCmds);
    // Add "Ask Jarvis: <q>" as top action when user typed something.
    // Lets them chat directly from anywhere without leaving current page.
    if (q && q.trim().length >= 2) {
      const isPT = (state.lang || "pt") === "pt";
      items.unshift({
        kind: "cmd",
        label: (isPT ? "💬 Perguntar ao Jarvis: " : "💬 Ask Jarvis: ") + q,
        action: () => {
          close();
          const el = document.getElementById("jarvis-input");
          if (el) { el.value = q; el.dispatchEvent(new Event("input")); el.focus();
            document.getElementById("jarvis-form")?.dispatchEvent(new Event("submit", { cancelable: true })); }
        },
      });
    }
    // Contextual entity actions — if there's a live drawer context or a recent
    // entity, offer targeted Jarvis commands (analyze / delete / add note) at
    // the top. This is the "current selection" concept from Notion/Linear.
    const lec = state.lastEntityContext;
    if (!q && lec && lec.expires > Date.now()) {
      const isPT = (state.lang || "pt") === "pt";
      const ctxLabel = `${lec.name} (${lec.type})`;
      items.unshift({
        kind: "cmd",
        label: (isPT ? "🔍 Analisar " : "🔍 Analyze ") + ctxLabel,
        action: () => {
          close();
          const el = document.getElementById("jarvis-input");
          const verb = { contact: "contato", company: "empresa", opportunity: "", lead: "lead" }[lec.type] || "";
          const cmd = lec.type === "opportunity"
            ? `analisa ${lec.name}`
            : `analisa ${verb} ${lec.name}`;
          if (el) { el.value = cmd; document.getElementById("jarvis-form")?.dispatchEvent(new Event("submit", { cancelable: true })); }
        },
      });
    }
    if (q.length >= 2) {
      try {
        const [search, msgs] = await Promise.all([
          api(`/jarvis/search-everywhere?q=${encodeURIComponent(q)}&limit=6`),
          api(`/jarvis/messages/search?q=${encodeURIComponent(q)}&limit=5`).catch(() => null),
        ]);
        for (const c of (search?.contacts || [])) items.push({ kind: "contact", label: `${c.first_name} ${c.last_name || ""}`.trim(), sub: c.email, action: () => { close(); openDrawer("contact", c.id); } });
        for (const co of (search?.companies || [])) items.push({ kind: "company", label: co.name, sub: co.domain, action: () => { close(); openDrawer("company", co.id); } });
        for (const o of (search?.opportunities || [])) items.push({ kind: "opportunity", label: o.name, sub: `${o.currency} ${o.amount}`, action: () => { close(); openDrawer("opportunity", o.id); } });
        for (const l of (search?.leads || [])) items.push({ kind: "lead", label: `${l.first_name} ${l.last_name || ""}`.trim(), sub: l.company_name || "", action: () => { close(); openDrawer("lead", l.id); } });
        for (const m of (msgs?.hits || [])) items.push({
          kind: "message", label: m.conversation_title, sub: m.snippet,
          action: () => { close(); state.conversation_id = m.conversation_id; localStorage.setItem(CONV_KEY, m.conversation_id); gotoPage("jarvis"); document.getElementById("jarvis-hero-log").innerHTML=""; loadJarvisHero(); },
        });
      } catch {}
    }
    results.innerHTML = "";
    if (!items.length) {
      const isPT = (state.lang || "pt") === "pt";
      results.innerHTML = `<div class="cmdk-item empty" style="text-align:center;padding:24px;">
        <div style="font-size:1.8em;opacity:0.6;margin-bottom:6px;">🔍</div>
        <div style="color:var(--fg-2);font-weight:500;">${isPT ? "Nada encontrado" : "Nothing found"}</div>
        <div style="color:var(--fg-4);font-size:0.85em;margin-top:4px;">${isPT ? "Tente outro termo ou digite um comando." : "Try a different term or type a command."}</div>
      </div>`;
      return;
    }
    let lastKind = null;
    items.forEach((it, i) => {
      if (it.kind !== lastKind) {
        const grp = document.createElement("div");
        grp.className = "cmdk-group";
        grp.textContent = { cmd: "Comandos / Commands", contact: "Contatos / Contacts", company: "Empresas / Companies", opportunity: "Oportunidades", lead: "Leads", message: "Mensagens do Jarvis" }[it.kind] || it.kind;
        results.appendChild(grp);
        lastKind = it.kind;
      }
      const row = document.createElement("div");
      row.className = "cmdk-item" + (i === activeIdx ? " active" : "");
      row.innerHTML = `<span>${escapeHtml(it.label)}</span>${it.sub ? `<span class="kind">${escapeHtml(it.sub)}</span>` : `<span class="kind">${it.kind}</span>`}`;
      row.addEventListener("click", () => { it.action?.(); close(); });
      results.appendChild(row);
    });
  }

  input.addEventListener("input", debounce(e => render(e.target.value), 180));
  input.addEventListener("keydown", e => {
    if (e.key === "Escape") { close(); return; }
    const rows = results.querySelectorAll(".cmdk-item:not(.cmdk-group):not(.empty)");
    if (!rows.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(activeIdx + 1, rows.length - 1); updateActive(rows); }
    if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(activeIdx - 1, 0); updateActive(rows); }
    if (e.key === "Enter") { e.preventDefault(); items[activeIdx]?.action?.(); close(); }
  });
  overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
  document.getElementById("open-cmdk")?.addEventListener("click", open);

  function updateActive(rows) {
    rows.forEach((r, i) => r.classList.toggle("active", i === activeIdx));
    rows[activeIdx]?.scrollIntoView({ block: "nearest" });
  }

  window.__openCmdK = open;
}

function gotoPage(page) {
  const btn = document.querySelector(`.nav-item[data-page="${page}"]`);
  btn?.click();
}

// ==================== KEYBOARD SHORTCUTS ====================
// Linear/Gmail-style "g <letter>" chords for fast navigation.
const G_CHORDS = {
  d: "dashboard", c: "contacts", e: "companies", o: "opportunities",
  l: "leads", k: "kanban", t: "tasks", m: "meetings",
  a: "automations", i: "integrations", v: "device", s: "sentinela",
};
let gArmed = false;
let gTimeout = null;

function bindHelpModal() {
  const help = document.getElementById("help-modal");
  if (!help) return;
  document.getElementById("help-close")?.addEventListener("click", () => help.classList.add("hidden"));
  help.addEventListener("click", e => { if (e.target === help) help.classList.add("hidden"); });
}

function bindShortcuts() {
  document.addEventListener("keydown", e => {
    const inField = e.target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);

    // Cmd/Ctrl + K → cmdk
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      window.__openCmdK?.();
      return;
    }
    // Esc closes help / drawer / modal / cmdk / mobile sidebar
    if (e.key === "Escape") {
      const help = document.getElementById("help-modal");
      if (help && !help.classList.contains("hidden")) { help.classList.add("hidden"); return; }
      const cmdk = document.getElementById("cmdk");
      if (!cmdk.classList.contains("hidden")) { cmdk.classList.add("hidden"); return; }
      const modal = document.getElementById("modal");
      if (!modal.classList.contains("hidden")) { modal.classList.add("hidden"); return; }
      const drawer = document.getElementById("drawer");
      if (!drawer.classList.contains("hidden")) { closeDrawer(); return; }
      document.body.classList.remove("sidebar-open");
      gArmed = false;
    }
    // Cmd/Ctrl + / → focus Jarvis
    if ((e.ctrlKey || e.metaKey) && e.key === "/") {
      e.preventDefault();
      document.getElementById("jarvis-input")?.focus();
      return;
    }
    // "?" → open keyboard help modal
    if (!inField && e.key === "?" && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      document.getElementById("help-modal")?.classList.remove("hidden");
      return;
    }
    if (inField) return;

    // ArrowDown/ArrowUp — row navigation in visible data tables.
    // Enter opens the highlighted row's drawer. Skipped when an overlay is up.
    if (["ArrowDown", "ArrowUp", "Enter"].includes(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      const drawer = document.getElementById("drawer");
      const modal = document.getElementById("modal");
      if ((drawer && !drawer.classList.contains("hidden")) || (modal && !modal.classList.contains("hidden"))) return;
      const rows = Array.from(document.querySelectorAll(".page:not(.hidden) table.table tbody tr.row-clickable"));
      if (!rows.length) return;
      let idx = rows.findIndex(r => r.classList.contains("row-focus"));
      if (e.key === "Enter") {
        if (idx >= 0) { e.preventDefault(); rows[idx].click(); }
        return;
      }
      e.preventDefault();
      if (idx < 0) idx = (e.key === "ArrowUp") ? rows.length - 1 : 0;
      else {
        rows[idx].classList.remove("row-focus");
        idx = (e.key === "ArrowDown") ? Math.min(rows.length - 1, idx + 1) : Math.max(0, idx - 1);
      }
      rows[idx].classList.add("row-focus");
      rows[idx].scrollIntoView({ block: "nearest", behavior: "smooth" });
      return;
    }

    // g-chord: press 'g' then a letter to navigate
    if (e.key.toLowerCase() === "g" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      gArmed = true;
      clearTimeout(gTimeout);
      gTimeout = setTimeout(() => { gArmed = false; }, 1200);
      return;
    }
    if (gArmed) {
      const target = G_CHORDS[e.key.toLowerCase()];
      gArmed = false;
      clearTimeout(gTimeout);
      if (target) {
        e.preventDefault();
        gotoPage(target);
        toast(`→ ${target}`, "info", 800);
      }
      return;
    }
    // "c" alone → new contact quick-add (Gmail-like)
    if (e.key === "c" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      document.getElementById("add-contact-btn")?.click();
    }
    // ";" alone → open email template picker if contact drawer is open
    if (e.key === ";" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      if (drawerCurrent?.type === "contact") {
        e.preventDefault();
        const btn = document.querySelector("[data-templates]");
        btn?.click();
      }
    }
    // "f" alone → focus mode (hide sidebar + jarvis panel)
    if (e.key === "f" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      document.body.classList.toggle("focus-mode");
      toast(document.body.classList.contains("focus-mode")
        ? (state.lang === "pt" ? "🎯 Modo foco" : "🎯 Focus mode")
        : (state.lang === "pt" ? "Voltando" : "Restored"), "info", 1200);
    }
    // "." alone → jump to Jarvis + open last conversation
    if (e.key === "." && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      gotoPage("jarvis");
      document.getElementById("jarvis-hero-input")?.focus();
    }
    // "j" alone → open Jarvis (FAB on mobile, focus on desktop)
    if (e.key === "j" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      const fab = document.getElementById("jarvis-fab");
      if (fab && window.getComputedStyle(fab).display !== "none") {
        fab.click();
      } else {
        document.getElementById("jarvis-input")?.focus();
      }
    }
    // "n" alone → new note in current drawer if open
    if (e.key === "n" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
      if (drawerCurrent) document.getElementById("drawer-note-input")?.focus();
    }
    // "/" alone → focus contact search when on contacts page
    if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
      const active = document.querySelector(".nav-item.active")?.dataset.page;
      const el = active === "companies" ? document.getElementById("company-search")
              : active === "contacts" ? document.getElementById("contact-search")
              : null;
      if (el) { e.preventDefault(); el.focus(); }
    }
  });
}

// ==================== UTILS ====================
// Locale-aware money formatting. Falls back to bare toLocaleString on error.
function fmtMoney(amount, currency = "USD") {
  try {
    const locale = state.lang === "pt" ? "pt-BR" : "en-US";
    return new Intl.NumberFormat(locale, {
      style: "currency", currency,
      maximumFractionDigits: 0,
    }).format(amount || 0);
  } catch {
    return `${currency} ${(amount || 0).toLocaleString()}`;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Skeleton table rows — pass width tokens (numbers 0-100 or "cb" for checkbox).
// Only fires when tbody is empty (first load) — doesn't clobber existing rows.
function showTableSkeleton(selector, rowCount, widths) {
  const tbody = document.querySelector(selector);
  if (!tbody || tbody.children.length) return;
  const cellFor = w => w === "cb"
    ? `<td><span class="skeleton" style="width:16px;height:16px;display:inline-block;border-radius:3px;"></span></td>`
    : `<td><div class="skeleton skeleton-line w-${w >= 80 ? 80 : w >= 60 ? 60 : 40}"></div></td>`;
  tbody.innerHTML = Array.from({length: rowCount}).map(() =>
    "<tr>" + widths.map(cellFor).join("") + "</tr>"
  ).join("");
}

// Hash-color avatar chip — stable color per name, initials from first two words.
// Used in contacts/companies/leads tables for at-a-glance identity.
function avatarChip(name, opts = {}) {
  const source = (name || "?").trim() || "?";
  const parts = source.split(/\s+/).slice(0, 2);
  const initials = parts.map(s => s[0] || "").join("").toUpperCase() || "?";
  const hash = [...source].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) | 0, 0);
  const hue = Math.abs(hash) % 360;
  const size = opts.size || 26;
  const light = opts.light || 42;
  const sat = opts.sat || 55;
  return `<span class="row-avatar" style="background:hsl(${hue},${sat}%,${light}%);width:${size}px;height:${size}px;">${escapeHtml(initials)}</span>`;
}
function debounce(fn, ms) {
  let tt;
  return (...args) => { clearTimeout(tt); tt = setTimeout(() => fn(...args), ms); };
}

// Traduz nomes de estágios padrão em inglês quando locale é PT.
// Só troca strings conhecidas — nomes custom do usuário ficam intactos.
const _STAGE_PT = {
  "Prospecting": "Prospecção",
  "Qualification": "Qualificação",
  "Proposal": "Proposta",
  "Negotiation": "Negociação",
  "Won": "Ganho",
  "Lost": "Perdido",
  "Closed Won": "Ganho",
  "Closed Lost": "Perdido",
};
function localizeStage(name) {
  if ((state.lang || "pt") !== "pt") return name;
  return _STAGE_PT[name] || name;
}

// Return "NEW" badge HTML if entity was created within the last 24h.
// Empty string if older or missing — safe to concat into row templates.
function newBadge(createdAt) {
  if (!createdAt) return "";
  const iso = /[zZ]|[+\-]\d\d:?\d\d$/.test(createdAt) ? createdAt : createdAt + "Z";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const ageMs = Date.now() - t;
  if (ageMs < -60000 || ageMs > 86400000) return "";
  const label = (state.lang || "pt") === "pt" ? "NOVO" : "NEW";
  return `<span class="new-badge" title="${(state.lang || "pt") === "pt" ? "Criado nas últimas 24h" : "Created in the last 24h"}">${label}</span>`;
}

// ==================== BOOT ====================
(async function main() {
  applyTheme();
  applyLang();
  bindAuth();
  const restored = await tryRestoreSession();
  if (restored) await enterApp();
  else show("auth");
})();

// ==================== MODULO SENTINELA ====================
// Painel do responsavel. Le a API local (/sentinela/*): eventos observados
// pela extensao, resumo por tema e a configuracao da protecao.
// Nada aqui fala com a internet — a mesma promessa do resto da suite.

const SN_PAGINA = 50;
const snState = { offset: 0, soBloqueadas: false, carregando: false, fim: false };

function snHora(iso) {
  try {
    const d = new Date(iso);
    const hoje = new Date();
    const mesmoDia = d.toDateString() === hoje.toDateString();
    const hh = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return mesmoDia ? hh : `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${hh}`;
  } catch { return ""; }
}

function snEventoHtml(ev) {
  const conf = Math.round((ev.confianca || 0) * 100);
  const status = ev.bloqueado
    ? `<span class="sn-tema">🛡️ bloqueada${ev.tema ? ` · ${escapeHtml(ev.tema)}` : ""}${conf ? ` · ${conf}%` : ""}</span>`
    : `<span style="color:var(--ok)">✔ liberada</span>`;
  return `<div class="sn-ev ${ev.bloqueado ? "bloq" : ""}">
    <div class="sn-ico">${ev.bloqueado ? "🛡️" : "🔎"}</div>
    <div class="sn-txt">
      <div class="sn-q">${escapeHtml(ev.busca || "")}</div>
      <div class="sn-meta">${status}
        <span>${escapeHtml(ev.origem || "")}</span>
        <span>${escapeHtml(ev.dispositivo || "")}</span>
        <span class="sn-hora">${snHora(ev.ocorrido_em)}</span>
      </div>
    </div>
  </div>`;
}

async function snCarregarEventos({ append = false } = {}) {
  const lista = document.getElementById("sn-lista");
  const mais = document.getElementById("sn-mais");
  if (!lista || snState.carregando) return;
  snState.carregando = true;
  if (!append) { snState.offset = 0; snState.fim = false; lista.innerHTML = `<p class="sn-vazio">…</p>`; }
  try {
    const qs = new URLSearchParams({ limite: SN_PAGINA, offset: snState.offset });
    if (snState.soBloqueadas) qs.set("somente_bloqueados", "true");
    const data = await api(`/sentinela/eventos?${qs}`);
    const html = (data.items || []).map(snEventoHtml).join("");
    if (!append) lista.innerHTML = "";
    if (!html && !append) {
      lista.innerHTML = `<p class="sn-vazio">Nada registrado ainda.<br>Conecte um dispositivo para começar a acompanhar.</p>`;
    } else {
      lista.insertAdjacentHTML("beforeend", html);
    }
    snState.offset += (data.items || []).length;
    snState.fim = snState.offset >= (data.total || 0);
    mais?.classList.toggle("hidden", snState.fim);
  } catch (err) {
    lista.innerHTML = `<p class="sn-vazio">Não consegui ler o registro: ${escapeHtml(err.message)}</p>`;
  } finally {
    snState.carregando = false;
  }
}

async function snCarregarResumo() {
  const kpis = document.getElementById("sn-kpis");
  const temas = document.getElementById("sn-temas");
  if (!kpis) return;
  try {
    const r = await api("/sentinela/resumo?dias=7");
    const hoje = (r.por_dia || []).slice(-1)[0] || { total: 0, bloqueados: 0 };
    kpis.innerHTML = `
      <div class="kpi" data-kind="risk"><div class="label">BLOQUEADAS</div><div class="value">${r.bloqueados || 0}</div><div class="subtle">${hoje.bloqueados || 0} hoje</div></div>
      <div class="kpi" data-kind="pipeline"><div class="label">OBSERVADAS</div><div class="value">${r.total || 0}</div><div class="subtle">${hoje.total || 0} hoje</div></div>
      <div class="kpi"><div class="label">DISPOSITIVOS</div><div class="value">${(r.dispositivos || []).length}</div><div class="subtle">${escapeHtml((r.dispositivos || []).join(", ") || "nenhum conectado")}</div></div>
      <div class="kpi"><div class="label">ÚLTIMO SINAL</div><div class="value" style="font-size:1.3em">${r.ultimo_evento ? snHora(r.ultimo_evento) : "—"}</div><div class="subtle">${r.ultimo_evento ? "registro chegando" : "sem atividade"}</div></div>`;

    const lista = r.temas || [];
    const topo = (lista[0] && lista[0].vezes) || 1;
    temas.innerHTML = lista.length
      ? lista.slice(0, 8).map(t => `<div class="sn-tema-row"><span>${escapeHtml(t.tema)}</span><b>${t.vezes}</b>
          <div class="sn-tema-bar"><i style="width:${Math.round((t.vezes / topo) * 100)}%"></i></div></div>`).join("")
      : `<p class="sn-vazio">Nenhum bloqueio ainda. 🎉</p>`;
  } catch (err) {
    kpis.innerHTML = `<p class="sn-vazio">Não consegui ler o resumo: ${escapeHtml(err.message)}</p>`;
  }
}

async function snCarregarConfig() {
  try {
    const cfg = await api("/sentinela/config");
    document.getElementById("sn-ativo").checked = !!cfg.ativo;
    document.getElementById("sn-sens").value = cfg.sensibilidade || "media";
    document.getElementById("sn-ret").value = cfg.retencao_dias == null ? 90 : cfg.retencao_dias;
    // "Guardar para sempre" tem de ser escolha visivel, nao efeito colateral de
    // um zero: sao buscas cifradas de uma crianca acumulando sem prazo.
    const avisoRet = document.getElementById("sn-ret-aviso");
    if (avisoRet) {
      const paraSempre = Number(cfg.retencao_dias) === 0;
      avisoRet.textContent = paraSempre
        ? "guardando para sempre — a purga automática está desligada"
        : "dias (0 = para sempre)";
      avisoRet.style.color = paraSempre ? "var(--warn)" : "";
    }
    const estado = document.getElementById("sn-pin-estado");
    const btn = document.getElementById("sn-pin-btn");
    estado.textContent = cfg.pin_definido ? "definido — só ele desarma a proteção" : "sem PIN — qualquer um pode desarmar";
    estado.style.color = cfg.pin_definido ? "" : "var(--warn)";
    btn.textContent = cfg.pin_definido ? "Trocar" : "Definir";
    btn.dataset.definido = cfg.pin_definido ? "1" : "";
    return cfg;
  } catch { return null; }
}

// Mostra o token para colar no popup da extensao. Fica atras de um clique de
// proposito: e credencial, nao deve ficar exposta na tela o tempo todo.
async function snConectarDispositivo() {
  let cfg;
  try { cfg = await api("/sentinela/config"); }
  catch (err) { toast(err.message, "error"); return; }

  const modal = document.getElementById("modal");
  document.getElementById("modal-title").textContent = "Conectar dispositivo";
  const form = document.getElementById("modal-form");
  form.innerHTML = `
    <p class="subtle" style="margin-bottom:8px">No navegador da criança, abra a extensão <b>Sentinela</b>,
    vá na aba <b>Painel</b>, ligue "Enviar para o painel" e cole o token abaixo.</p>
    <div class="sn-token" id="sn-token-val">${escapeHtml(cfg.token_ingestao)}</div>
    <p class="subtle">Endereço do painel: <code>${escapeHtml(location.origin)}</code></p>
    <p class="subtle" style="margin-top:8px">Se o token vazar, gere outro — os dispositivos antigos param de enviar até serem reconectados.</p>`;
  const close = () => modal.classList.add("hidden");
  document.getElementById("modal-cancel").onclick = close;
  document.getElementById("modal-x").onclick = close;
  const salvar = document.getElementById("modal-save");
  salvar.textContent = "Gerar novo token";
  salvar.onclick = async () => {
    try {
      const novo = await api("/sentinela/token/rotacionar", { method: "POST" });
      document.getElementById("sn-token-val").textContent = novo.token_ingestao;
      toast("Token novo gerado. Reconecte os dispositivos.", "info");
    } catch (err) { toast(err.message, "error"); }
  };
  form.onsubmit = ev => ev.preventDefault();
  modal.classList.remove("hidden");
}

function snDefinirPin() {
  const jaTem = !!document.getElementById("sn-pin-btn").dataset.definido;
  const campos = jaTem
    ? [{ label: "PIN atual", name: "pin_atual", type: "password", required: true },
       { label: "PIN novo (4 a 12 dígitos)", name: "pin", type: "password", required: true }]
    : [{ label: "PIN (4 a 12 dígitos)", name: "pin", type: "password", required: true }];
  openModal(jaTem ? "Trocar PIN do responsável" : "Definir PIN do responsável", campos, async data => {
    await api("/sentinela/config/pin", { method: "POST", body: data });
    toast("PIN salvo.", "success");
    snCarregarConfig();
  });
}

let snWired = false;
let snPinPedido = false;
async function loadSentinela() {
  if (!snWired) {
    snWired = true;
    document.getElementById("sn-refresh")?.addEventListener("click", () => loadSentinela());
    document.getElementById("sn-conectar")?.addEventListener("click", snConectarDispositivo);
    document.getElementById("sn-pin-btn")?.addEventListener("click", snDefinirPin);
    document.getElementById("sn-mais")?.addEventListener("click", () => snCarregarEventos({ append: true }));
    document.getElementById("sn-so-bloq")?.addEventListener("change", ev => {
      snState.soBloqueadas = ev.target.checked;
      snCarregarEventos();
    });
    // Config salva sozinha ao mudar — sem botao "Salvar" para esquecer de clicar.
    const salvar = async campos => {
      try { await api("/sentinela/config", { method: "PATCH", body: campos }); toast("Salvo.", "success", 1400); }
      catch (err) { toast(err.message, "error"); snCarregarConfig(); }
    };
    document.getElementById("sn-ativo")?.addEventListener("change", e => salvar({ ativo: e.target.checked }));
    document.getElementById("sn-sens")?.addEventListener("change", e => salvar({ sensibilidade: e.target.value }));
    document.getElementById("sn-ret")?.addEventListener("change", e => {
      const n = parseInt(e.target.value, 10);
      if (Number.isNaN(n) || n < 0) { snCarregarConfig(); return; }
      salvar({ retencao_dias: n }).then(snCarregarConfig);
    });
  }
  const [, , cfg] = await Promise.all([snCarregarResumo(), snCarregarEventos(), snCarregarConfig()]);

  // Sem PIN, a trava parental nao existe: qualquer um desarma a proteção. Na
  // primeira visita da sessão o app pede o PIN em vez de só avisar em cinza —
  // um aviso que ninguém lê não protege ninguém.
  if (cfg && !cfg.pin_definido && !snPinPedido) {
    snPinPedido = true;
    setTimeout(snDefinirPin, 400);
  }
}
