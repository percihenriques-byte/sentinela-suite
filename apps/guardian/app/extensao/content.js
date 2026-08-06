/*
  content.js — roda em TODA página. Faz duas coisas:
   1) BUSCA: nas páginas de busca, lê o termo e bloqueia na hora (antes
      de renderizar), inclusive em navegação SPA.
   2) CONTEÚDO: em qualquer página, lê o TEXTO que a criança está vendo e
      a IA local decide se o conteúdo é impróprio (não só a busca).
  Tudo local, sem internet.
*/
(function () {
  'use strict';

  var hideStyle = null;
  var ultimaQuery = null;
  var jaBloqueado = false;

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
      if (location.hostname.indexOf('google') >= 0 && location.pathname.indexOf('/search') !== 0) return '';
      if (location.hostname.indexOf('bing') >= 0 && location.pathname.indexOf('/search') !== 0) return '';
      return u.searchParams.get('q') || '';
    } catch (e) { return ''; }
  }
  function origem() {
    var h = location.hostname;
    if (h.indexOf('youtube') >= 0) return 'youtube';
    if (h.indexOf('bing') >= 0) return 'bing';
    if (h.indexOf('duckduckgo') >= 0) return 'duckduckgo';
    if (h.indexOf('google') >= 0) return 'google';
    return h;
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
    // Espelha no painel local da suite. Quem fala com 127.0.0.1 e o service
    // worker; aqui so avisamos. Falha nao pode atrapalhar o bloqueio.
    try {
      chrome.runtime.sendMessage({ tipo: 'registrarEvento', entrada: entry }, function () {
        void chrome.runtime.lastError; // painel desligado: a fila espera
      });
    } catch (e) { /* silencioso */ }
  }

  function telaBloqueio(cat, sub) {
    jaBloqueado = true;
    document.documentElement.innerHTML =
      '<head><meta charset="utf-8"><title>Bloqueado — Sentinela</title></head>' +
      '<body style="margin:0;font-family:system-ui,Segoe UI,sans-serif;background:#0B1220;color:#E6F6F2;display:flex;min-height:100vh;align-items:center;justify-content:center">' +
      '<div style="max-width:480px;text-align:center;padding:32px">' +
      '<div style="font-size:52px">🛡️</div>' +
      '<h1 style="font-size:24px;margin:12px 0 6px;color:#2DD4BF">Conteúdo bloqueado</h1>' +
      '<p style="color:#90AEB4;font-size:15px;line-height:1.5">' + (sub || '') + '</p>' +
      '<div style="margin-top:14px;font-size:12px;color:#5E7A82">Categoria: <b style="color:#E6F6F2">' + (cat || '—') + '</b>. Responsável: ajuste os temas no painel do Sentinela se isto foi um engano.</div>' +
      '</div></body>';
    mostrar();
  }

  // ---- 1) BUSCA ----
  function verificarBusca() {
    if (jaBloqueado) return;
    var q = getQuery();
    if (!q) { mostrar(); ultimaQuery = null; return; }
    if (q === ultimaQuery) return;
    ultimaQuery = q;
    esconder();
    try {
      chrome.storage.local.get({ sentinela_config: {} }, function (d) {
        var res = window.SentinelaIA.classify(q, d.sentinela_config || {});
        registrar({ hora: new Date().toISOString(), busca: q, origem: origem(), tema: res.category, confianca: res.confidence, bloqueado: res.block });
        if (res.block) telaBloqueio(res.category, 'A busca foi classificada como <b>' + res.category + '</b> (' + Math.round(res.confidence * 100) + '% de confiança).');
        else mostrar();
      });
    } catch (e) { mostrar(); }
  }

  // ---- 2) CONTEÚDO DA PÁGINA ----
  function analisarPagina() {
    if (jaBloqueado) return;
    var texto = '';
    try { texto = document.body ? (document.body.innerText || '') : ''; } catch (e) { return; }
    if (texto.length < 40) return;               // pouco texto: ignora
    if (texto.length > 200000) texto = texto.slice(0, 200000);
    try {
      chrome.storage.local.get({ sentinela_config: {} }, function (d) {
        var res = window.SentinelaIA.classifyPagina(texto, d.sentinela_config || {});
        if (res && res.block) {
          registrar({ hora: new Date().toISOString(), busca: '[página] ' + location.hostname, origem: 'página', tema: res.category, confianca: Math.min(1, res.score / 6), bloqueado: true });
          telaBloqueio(res.category, 'A IA analisou o <b>conteúdo desta página</b> e o classificou como <b>' + res.category + '</b>.');
        }
      });
    } catch (e) { /* silencioso */ }
  }

  // ---- 3) IMAGENS ----
  function borrarImagem(img, ratio) {
    img.style.setProperty('filter', 'blur(30px)', 'important');
    img.style.setProperty('clip-path', 'inset(1px)', 'important');
    img.setAttribute('data-sentinela-oculta', ratio || '');
    img.title = 'Imagem ocultada pelo Sentinela';
  }
  function acaoImg(elImg, res) {
    if (res && res.flag) {
      borrarImagem(elImg, res.skinRatio);
      registrar({ hora: new Date().toISOString(), busca: '[imagem] ' + location.hostname, origem: 'imagem', tema: 'Imagem suspeita', confianca: res.skinRatio || 0, bloqueado: true });
    }
  }
  // tenta analisar a imagem no proprio content script (data:, mesma origem,
  // ou CORS liberado). Retorna undefined se nao der (cross-origin tainted).
  function analisarLocal(img, limiar) {
    try {
      if (!self.SentinelaImg || !img.complete) return undefined;
      var w = img.naturalWidth, h = img.naturalHeight;
      if (!w || !h) return undefined;
      var esc = Math.min(1, 400 / Math.max(w, h));
      var cw = Math.max(1, Math.round(w * esc)), ch = Math.max(1, Math.round(h * esc));
      var cv = document.createElement('canvas'); cv.width = cw; cv.height = ch;
      var ctx = cv.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, cw, ch);
      var data = ctx.getImageData(0, 0, cw, ch).data; // SecurityError se cross-origin tainted
      return self.SentinelaImg.analisarPixels(data, cw, ch, limiar);
    } catch (e) { return undefined; }
  }
  // Só analisa o que a criança realmente VE na tela. Nao marca as ocultas,
  // para reanalisar se virarem visiveis depois (ex.: slide de carrossel).
  function imagemVisivel(img) {
    try {
      var r = img.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) return false;   // colapsada / nao renderizada
      var st = (img.ownerDocument.defaultView || window).getComputedStyle(img);
      if (st.display === 'none' || st.visibility === 'hidden' || st.visibility === 'collapse') return false;
      if (parseFloat(st.opacity || '1') === 0) return false;
      return true;
    } catch (e) { return true; }                        // na duvida, analisa
  }
  function analisarImagens(limiar) {
    var imgs;
    try { imgs = document.images; } catch (e) { return; }
    for (var i = 0; i < imgs.length; i++) {
      var img = imgs[i];
      if (img.__sentinelaImg) continue;
      var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
      if (w < 128 || h < 128) continue;         // ignora icones/thumbs pequenos
      if (img.complete && img.naturalWidth === 0) continue; // quebrada
      if (!imagemVisivel(img)) continue;        // oculta: NAO marca, reavalia depois
      var src = img.currentSrc || img.src;
      if (!src) continue;
      img.__sentinelaImg = true;
      var local = analisarLocal(img, limiar);
      if (local !== undefined) {                 // deu para ler os pixels aqui
        acaoImg(img, local);
        continue;
      }
      // cross-origin: o background busca e analisa
      (function (elImg, elSrc) {
        try {
          chrome.runtime.sendMessage({ tipo: 'analisarImagem', url: elSrc, limiar: limiar }, function (res) {
            if (chrome.runtime.lastError) return;
            acaoImg(elImg, res);
          });
        } catch (e) { /* silencioso */ }
      })(img, src);
    }
  }
  function talvezAnalisarImagens() {
    try {
      chrome.storage.local.get({ sentinela_config: {} }, function (d) {
        var cfg = d.sentinela_config || {};
        if (cfg.analisarImagens === false) return;   // toggle (padrao: ligado)
        var s = cfg.imagemSensibilidade || 'normal';
        var limiar = s === 'conservador' ? 0.40 : (s === 'rigido' ? 0.22 : 0.30);
        analisarImagens(limiar);
      });
    } catch (e) { /* silencioso */ }
  }

  // avaliacao inicial da busca (imediata, antes de renderizar)
  verificarBusca();
  // analise de conteudo apos o texto existir
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', analisarPagina); }
  else { analisarPagina(); }
  window.addEventListener('load', function () { analisarPagina(); talvezAnalisarImagens(); });

  // navegacao SPA (troca sem recarregar)
  window.addEventListener('popstate', function () { verificarBusca(); setTimeout(analisarPagina, 600); });
  window.addEventListener('hashchange', verificarBusca);
  document.addEventListener('yt-navigate-finish', function () { verificarBusca(); setTimeout(analisarPagina, 800); });
  var ultimaUrl = location.href;
  setInterval(function () {
    if (location.href !== ultimaUrl) {
      ultimaUrl = location.href; jaBloqueado = false;
      verificarBusca(); setTimeout(analisarPagina, 700);
    }
  }, 500);
  // re-varre imagens que aparecem depois (scroll/lazy-load), de forma leve
  setInterval(talvezAnalisarImagens, 2500);
})();
