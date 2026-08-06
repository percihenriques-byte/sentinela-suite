/*
  background.js — service worker do Sentinela.
  Analisa imagens da pagina: o content.js manda a URL, o background BUSCA
  a imagem (tem host_permissions, entao consegue ler pixels de outros
  dominios, o que o content script nao consegue por causa do CORS),
  desenha num OffscreenCanvas e roda o analisador local.

  Se houver um modelo treinado na pasta modelo/ (ver
  modelo/COMO-ADICIONAR-MODELO.md), da pra troca-lo aqui no futuro.
  Por enquanto usa o heuristico de tom de pele (analise-imagem.js).
*/
try { importScripts('analise-imagem.js'); } catch (e) { /* sem analisador */ }
// sync.js espelha o registro de supervisao no painel local (127.0.0.1).
// Se falhar de carregar, a extensao continua funcionando offline.
try { importScripts('sync.js'); } catch (e) { /* sem sincronizacao */ }

async function analisarImagemUrl(url, limiar) {
  try {
    if (!url || url.indexOf('http') !== 0) return { flag: false };
    var resp = await fetch(url);
    if (!resp.ok) return { flag: false };
    var blob = await resp.blob();
    if (!blob.type || blob.type.indexOf('image') !== 0) return { flag: false };
    var bmp = await createImageBitmap(blob);
    var w = bmp.width, h = bmp.height;
    if (w < 128 || h < 128) { bmp.close && bmp.close(); return { flag: false, pequena: true }; }
    // limita o tamanho analisado p/ performance
    var esc = Math.min(1, 400 / Math.max(w, h));
    var cw = Math.max(1, Math.round(w * esc)), ch = Math.max(1, Math.round(h * esc));
    var canvas = new OffscreenCanvas(cw, ch);
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(bmp, 0, 0, cw, ch);
    bmp.close && bmp.close();
    var img = ctx.getImageData(0, 0, cw, ch);
    if (!self.SentinelaImg) return { flag: false };
    return self.SentinelaImg.analisarPixels(img.data, cw, ch, limiar);
  } catch (e) {
    return { flag: false, erro: String(e && e.message || e) };
  }
}

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (msg && msg.tipo === 'analisarImagem') {
    analisarImagemUrl(msg.url, msg.limiar).then(function (r) { sendResponse(r); });
    return true; // resposta assincrona
  }

  // O content script observa, mas quem fala com o painel local e o service
  // worker (so ele tem host_permissions). Enfileira e tenta entregar; se o
  // painel estiver desligado, a fila espera.
  if (msg && msg.tipo === 'registrarEvento') {
    if (!self.SentinelaSync) { sendResponse({ ok: false, erro: 'sem-sync' }); return true; }
    self.SentinelaSync.enfileirar(msg.entrada)
      .then(function () { return self.SentinelaSync.enviar(); })
      .then(function (r) { sendResponse({ ok: true, resultado: r }); })
      .catch(function (e) { sendResponse({ ok: false, erro: String(e && e.message || e) }); });
    return true;
  }

  // Popup: estado da conexao, salvar configuracao, forcar sincronizacao.
  if (msg && msg.tipo === 'syncEstado') {
    if (!self.SentinelaSync) { sendResponse({ ok: false, erro: 'sem-sync' }); return true; }
    self.SentinelaSync.estado().then(function (e) { sendResponse({ ok: true, estado: e }); });
    return true;
  }
  if (msg && msg.tipo === 'syncSalvar') {
    if (!self.SentinelaSync) { sendResponse({ ok: false, erro: 'sem-sync' }); return true; }
    self.SentinelaSync.salvarServidor(msg.config || {})
      .then(function () { return self.SentinelaSync.enviar(); })
      .then(function () { return self.SentinelaSync.estado(); })
      .then(function (e) { sendResponse({ ok: true, estado: e }); })
      .catch(function (e) { sendResponse({ ok: false, erro: String(e && e.message || e) }); });
    return true;
  }
  if (msg && msg.tipo === 'syncAgora') {
    if (!self.SentinelaSync) { sendResponse({ ok: false, erro: 'sem-sync' }); return true; }
    self.SentinelaSync.enviar()
      .then(function (r) { return self.SentinelaSync.estado().then(function (e) { return { r: r, e: e }; }); })
      .then(function (x) { sendResponse({ ok: true, resultado: x.r, estado: x.e }); })
      .catch(function (e) { sendResponse({ ok: false, erro: String(e && e.message || e) }); });
    return true;
  }
});
