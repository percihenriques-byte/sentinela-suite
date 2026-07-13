/*
  content.js — roda nas páginas de busca. Lê o termo, aplica a IA local,
  bloqueia na hora se for tema impróprio e registra a atividade.

  Cobre também sites que trocam os resultados SEM recarregar a página
  (SPA, como o YouTube): reavalia a cada mudança de URL.
*/
(function () {
  'use strict';

  var hideStyle = null;
  var ultimaQuery = null;

  // esconde a página enquanto a IA decide (evita o conteúdo "piscar")
  function esconder() {
    if (hideStyle) return;
    hideStyle = document.createElement('style');
    hideStyle.id = '__sentinela_hide';
    hideStyle.textContent = 'html{visibility:hidden !important}';
    (document.documentElement || document).appendChild(hideStyle);
  }
  function mostrar() {
    if (hideStyle && hideStyle.parentNode) { hideStyle.parentNode.removeChild(hideStyle); }
    hideStyle = null;
  }

  function getQuery() {
    try {
      var u = new URL(location.href);
      if (location.hostname.indexOf('youtube') >= 0) {
        if (location.pathname.indexOf('/results') !== 0) return '';
        return u.searchParams.get('search_query') || '';
      }
      if (location.hostname.indexOf('google') >= 0 && location.pathname.indexOf('/search') !== 0) {
        return '';
      }
      return u.searchParams.get('q') || '';
    } catch (e) { return ''; }
  }
  function origem() {
    var h = location.hostname;
    if (h.indexOf('youtube') >= 0) return 'youtube';
    if (h.indexOf('bing') >= 0) return 'bing';
    if (h.indexOf('duckduckgo') >= 0) return 'duckduckgo';
    return 'google';
  }

  function registrar(entry) {
    try {
      chrome.storage.local.get({ sentinela_log: [] }, function (d) {
        var log = d.sentinela_log || [];
        log.push(entry);
        if (log.length > 500) { log = log.slice(log.length - 500); }
        chrome.storage.local.set({ sentinela_log: log });
      });
    } catch (e) { /* silencioso */ }
  }

  function bloquear(res) {
    var conf = Math.round(res.confidence * 100);
    var cat = (res.category || 'conteúdo impróprio');
    document.documentElement.innerHTML =
      '<head><meta charset="utf-8"><title>Bloqueado — Sentinela</title></head>' +
      '<body style="margin:0;font-family:system-ui,Segoe UI,sans-serif;background:#0B1220;color:#E6F6F2;display:flex;min-height:100vh;align-items:center;justify-content:center">' +
      '<div style="max-width:460px;text-align:center;padding:32px">' +
      '<div style="font-size:52px">🛡️</div>' +
      '<h1 style="font-size:24px;margin:12px 0 6px;color:#2DD4BF">Conteúdo bloqueado</h1>' +
      '<p style="color:#90AEB4;font-size:15px;line-height:1.5">O Sentinela barrou esta busca porque foi classificada como <b style="color:#E6F6F2">' + cat + '</b> (' + conf + '% de confiança).</p>' +
      '<div style="margin-top:16px;font-size:12px;color:#5E7A82">Responsável: ajuste os temas no painel do Sentinela se isto foi um engano.</div>' +
      '</div></body>';
    mostrar();
  }

  function verificar() {
    var q = getQuery();
    if (!q) { mostrar(); ultimaQuery = null; return; }
    if (q === ultimaQuery) { return; }   // já tratada nesta navegação
    ultimaQuery = q;
    esconder();
    try {
      chrome.storage.local.get({ sentinela_config: {} }, function (d) {
        var res = window.SentinelaIA.classify(q, d.sentinela_config || {});
        registrar({ hora: new Date().toISOString(), busca: q, origem: origem(), tema: res.category, confianca: res.confidence, bloqueado: res.block });
        if (res.block) { bloquear(res); } else { mostrar(); }
      });
    } catch (e) { mostrar(); }
  }

  // avaliação inicial
  verificar();

  // deteccao de navegacao SPA (troca de resultados sem recarregar)
  window.addEventListener('popstate', verificar);
  window.addEventListener('hashchange', verificar);
  document.addEventListener('yt-navigate-finish', verificar); // YouTube
  document.addEventListener('yt-navigate-start', verificar);
  // verificador periodico (rede de seguranca para qualquer SPA)
  var ultimaUrl = location.href;
  setInterval(function () {
    if (location.href !== ultimaUrl) { ultimaUrl = location.href; verificar(); }
  }, 400);
})();
