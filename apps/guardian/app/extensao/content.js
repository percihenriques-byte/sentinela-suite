/*
  content.js — roda nas páginas de busca. Lê o termo, aplica a IA local,
  bloqueia na hora se for tema impróprio e registra a atividade para o
  responsável. Esconde a página até decidir, para nada impróprio "piscar".
*/
(function () {
  // 1) esconde a página imediatamente
  var hideStyle = document.createElement('style');
  hideStyle.textContent = 'html{visibility:hidden !important}';
  (document.documentElement || document).appendChild(hideStyle);
  function show() { if (hideStyle && hideStyle.parentNode) hideStyle.parentNode.removeChild(hideStyle); }

  function getQuery() {
    try {
      var u = new URL(location.href);
      if (location.hostname.indexOf('youtube') >= 0) return u.searchParams.get('search_query') || '';
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
        if (log.length > 500) log = log.slice(log.length - 500);
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
    show();
  }

  var q = getQuery();
  if (!q) { show(); return; }
  try {
    chrome.storage.local.get({ sentinela_config: {} }, function (d) {
      var res = window.SentinelaIA.classify(q, d.sentinela_config || {});
      registrar({ hora: new Date().toISOString(), busca: q, origem: origem(), tema: res.category, confianca: res.confidence, bloqueado: res.block });
      if (res.block) bloquear(res); else show();
    });
  } catch (e) { show(); }
})();
