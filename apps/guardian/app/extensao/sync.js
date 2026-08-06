/*
  sync.js — envia o registro de supervisao para o painel local da suite.

  Antes: o responsavel tinha de clicar "Exportar" no popup, salvar um .jsonl e
  importar a mao no app PowerShell. Agora a extensao entrega direto ao servidor
  em 127.0.0.1, e o painel mostra em tempo real.

  Principios:
    - Offline primeiro. O log local (chrome.storage) continua sendo a verdade;
      o envio e um espelho. Se o servidor estiver desligado, nada se perde: a
      fila espera e vai na proxima oportunidade.
    - Nada de internet. So fala com o host configurado, que e loopback.
    - O servidor autentica com um token de ingestao. Sem token, nao envia
      (a rota recusaria de qualquer forma).

  Roda no service worker (tem host_permissions; o content script nao teria).
*/
(function (raiz) {
  'use strict';

  var CHAVE_FILA = 'sentinela_fila';
  var CHAVE_SRV = 'sentinela_servidor';
  var CHAVE_ESTADO = 'sentinela_sync_estado';
  var MAX_FILA = 500;   // mesmo teto do log local
  var LOTE = 100;       // servidor aceita ate 200 por requisicao
  var MAX_RODADAS = 10; // trava de seguranca contra laco infinito

  var PADRAO_SRV = { url: 'http://127.0.0.1:8000', token: '', dispositivo: 'este-pc', ligado: false };

  function ehLoopback(url) {
    try {
      var h = new URL(url).hostname;
      return h === '127.0.0.1' || h === 'localhost' || h === '::1' || h === '[::1]';
    } catch (e) { return false; }
  }

  async function lerServidor() {
    var d = await chrome.storage.local.get({ sentinela_servidor: PADRAO_SRV });
    var cfg = d.sentinela_servidor || {};
    return {
      url: cfg.url || PADRAO_SRV.url,
      token: cfg.token || '',
      dispositivo: cfg.dispositivo || PADRAO_SRV.dispositivo,
      ligado: !!cfg.ligado
    };
  }

  async function salvarServidor(parcial) {
    var atual = await lerServidor();
    var novo = {
      url: parcial.url !== undefined ? String(parcial.url).trim() : atual.url,
      token: parcial.token !== undefined ? String(parcial.token).trim() : atual.token,
      dispositivo: parcial.dispositivo !== undefined ? String(parcial.dispositivo).trim() : atual.dispositivo,
      ligado: parcial.ligado !== undefined ? !!parcial.ligado : atual.ligado
    };
    if (novo.url && !ehLoopback(novo.url)) {
      throw new Error('O painel so pode estar no proprio dispositivo (127.0.0.1).');
    }
    await chrome.storage.local.set({ sentinela_servidor: novo });
    return novo;
  }

  async function lerEstado() {
    var d = await chrome.storage.local.get({ sentinela_sync_estado: {} });
    return d.sentinela_sync_estado || {};
  }

  async function salvarEstado(parcial) {
    var atual = await lerEstado();
    var novo = Object.assign({}, atual, parcial);
    await chrome.storage.local.set({ sentinela_sync_estado: novo });
    return novo;
  }

  async function enfileirar(entrada) {
    if (!entrada || !entrada.busca) return 0;
    var d = await chrome.storage.local.get({ sentinela_fila: [] });
    var fila = d.sentinela_fila || [];
    fila.push(entrada);
    var descartados = 0;
    if (fila.length > MAX_FILA) {
      descartados = fila.length - MAX_FILA;
      fila = fila.slice(descartados);
    }
    await chrome.storage.local.set({ sentinela_fila: fila });
    if (descartados) {
      await salvarEstado({ descartados: ((await lerEstado()).descartados || 0) + descartados });
    }
    return fila.length;
  }

  /* Traduz o formato do log da extensao para o corpo que a API espera. */
  function paraApi(entrada, dispositivo) {
    return {
      busca: String(entrada.busca).slice(0, 500),
      origem: entrada.origem || 'extensao',
      dispositivo: dispositivo || 'este-pc',
      tema: entrada.tema || null,
      confianca: typeof entrada.confianca === 'number' ? entrada.confianca : 0,
      bloqueado: !!entrada.bloqueado,
      sinais: Array.isArray(entrada.sinais) ? entrada.sinais : [],
      ocorrido_em: entrada.hora || null
    };
  }

  /*
    Drena a fila em lotes. Devolve {enviados, restantes, erro}.
    Em erro de rede a fila fica intacta de proposito — melhor repetir um evento
    do que perder um.
  */
  async function enviar() {
    var srv = await lerServidor();
    if (!srv.ligado) return { enviados: 0, restantes: null, erro: 'desligado' };
    if (!srv.token) return { enviados: 0, restantes: null, erro: 'sem-token' };
    if (!ehLoopback(srv.url)) return { enviados: 0, restantes: null, erro: 'url-invalida' };

    var enviados = 0;
    for (var rodada = 0; rodada < MAX_RODADAS; rodada++) {
      var d = await chrome.storage.local.get({ sentinela_fila: [] });
      var fila = d.sentinela_fila || [];
      if (!fila.length) break;

      var lote = fila.slice(0, LOTE);
      var corpo = { eventos: lote.map(function (e) { return paraApi(e, srv.dispositivo); }) };
      var resp;
      try {
        resp = await fetch(srv.url.replace(/\/+$/, '') + '/api/v1/sentinela/eventos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Sentinela-Token': srv.token },
          body: JSON.stringify(corpo)
        });
      } catch (e) {
        await salvarEstado({ ultimoErro: 'offline', ultimoErroEm: new Date().toISOString() });
        return { enviados: enviados, restantes: fila.length, erro: 'offline' };
      }

      if (resp.status === 401) {
        await salvarEstado({ ultimoErro: 'token', ultimoErroEm: new Date().toISOString() });
        return { enviados: enviados, restantes: fila.length, erro: 'token' };
      }
      if (resp.status === 422) {
        // Lote malformado: descarta so ele, senao entope a fila para sempre.
        await chrome.storage.local.set({ sentinela_fila: fila.slice(lote.length) });
        await salvarEstado({ ultimoErro: 'lote-invalido', ultimoErroEm: new Date().toISOString() });
        continue;
      }
      if (!resp.ok) {
        await salvarEstado({ ultimoErro: 'http-' + resp.status, ultimoErroEm: new Date().toISOString() });
        return { enviados: enviados, restantes: fila.length, erro: 'http-' + resp.status };
      }

      await chrome.storage.local.set({ sentinela_fila: fila.slice(lote.length) });
      enviados += lote.length;
    }

    var fim = await chrome.storage.local.get({ sentinela_fila: [] });
    await salvarEstado({ ultimoEnvio: new Date().toISOString(), ultimoErro: null, enviadosTotal: ((await lerEstado()).enviadosTotal || 0) + enviados });
    return { enviados: enviados, restantes: (fim.sentinela_fila || []).length, erro: null };
  }

  async function estado() {
    var srv = await lerServidor();
    var d = await chrome.storage.local.get({ sentinela_fila: [] });
    var st = await lerEstado();
    return {
      configurado: !!(srv.token && srv.ligado),
      ligado: srv.ligado,
      url: srv.url,
      dispositivo: srv.dispositivo,
      temToken: !!srv.token,
      fila: (d.sentinela_fila || []).length,
      ultimoEnvio: st.ultimoEnvio || null,
      ultimoErro: st.ultimoErro || null,
      enviadosTotal: st.enviadosTotal || 0
    };
  }

  raiz.SentinelaSync = {
    lerServidor: lerServidor,
    salvarServidor: salvarServidor,
    enfileirar: enfileirar,
    enviar: enviar,
    estado: estado,
    ehLoopback: ehLoopback,
    paraApi: paraApi,
    MAX_FILA: MAX_FILA,
    LOTE: LOTE
  };
})(typeof self !== 'undefined' ? self : this);
