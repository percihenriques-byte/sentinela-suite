/* popup.js — supervisão (o que o filho buscou) e configuração de temas. */
(function () {
  function $(id) { return document.getElementById(id); }
  function esc(s) { return (s || '').replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function hora(iso) { try { var d = new Date(iso); return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR').slice(0,5); } catch (e) { return ''; } }

  // abas
  document.querySelectorAll('.tab').forEach(function (t) {
    t.addEventListener('click', function () {
      document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('active'); });
      document.querySelectorAll('.view').forEach(function (x) { x.classList.remove('active'); });
      t.classList.add('active');
      $('view-' + t.dataset.view).classList.add('active');
    });
  });

  // ---- supervisão ----
  function renderLog() {
    chrome.storage.local.get({ sentinela_log: [] }, function (d) {
      var log = (d.sentinela_log || []).slice().reverse();
      var total = log.length;
      var bloq = log.filter(function (x) { return x.bloqueado; });
      $('st-total').textContent = total;
      $('st-bloq').textContent = bloq.length;
      var contagem = {};
      bloq.forEach(function (x) { if (x.tema) contagem[x.tema] = (contagem[x.tema] || 0) + 1; });
      var top = Object.keys(contagem).sort(function (a, b) { return contagem[b] - contagem[a]; })[0];
      $('st-tema').textContent = top || '—';
      $('st-tema').style.fontSize = top ? '12px' : '20px';

      var lista = $('lista');
      if (!total) { lista.innerHTML = '<div class="empty">Nenhuma busca registrada ainda.<br>Quando a criança pesquisar, aparece aqui.</div>'; return; }
      lista.innerHTML = log.slice(0, 100).map(function (x) {
        var conf = Math.round((x.confianca || 0) * 100);
        var status = x.bloqueado
          ? '<span class="bad">🛡️ bloqueada · ' + esc(x.tema || '') + ' · ' + conf + '%</span>'
          : '<span class="ok">✔ liberada</span>';
        return '<div class="item ' + (x.bloqueado ? 'b' : '') + '"><div class="q">' + esc(x.busca) + '</div>' +
          '<div class="m">' + status + '<span>' + esc(x.origem || '') + '</span><span>' + hora(x.hora) + '</span></div></div>';
      }).join('');
    });
  }

  $('btn-export').addEventListener('click', function () {
    chrome.storage.local.get({ sentinela_log: [] }, function (d) {
      var linhas = (d.sentinela_log || []).map(function (x) { return JSON.stringify(x); }).join('\n');
      var blob = new Blob([linhas], { type: 'application/x-ndjson' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a'); a.href = url; a.download = 'supervisao-sentinela.jsonl'; a.click();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    });
  });
  $('btn-limpar').addEventListener('click', function () {
    if (confirm('Limpar todo o registro de supervisão?')) {
      chrome.storage.local.set({ sentinela_log: [] }, renderLog);
    }
  });

  // ---- configuração ----
  function renderConfig() {
    chrome.storage.local.get({ sentinela_config: {} }, function (d) {
      var cfg = d.sentinela_config || {};
      var desativados = cfg.temasDesativados || [];
      var ativados = cfg.temasAtivados || [];
      var temasDiv = $('temas');
      temasDiv.innerHTML = window.SentinelaIA.temas.map(function (t) {
        var ligado = t.padraoLigado ? (desativados.indexOf(t.tema) === -1) : (ativados.indexOf(t.tema) !== -1);
        var opc = t.padraoLigado ? '' : '<span class="opc">opcional</span>';
        return '<div class="row"><label for="t_' + esc(t.tema) + '">' + esc(t.tema) + opc + '</label>' +
          '<input type="checkbox" id="t_' + esc(t.tema) + '" data-tema="' + esc(t.tema) + '" data-padrao="' + t.padraoLigado + '" ' + (ligado ? 'checked' : '') + '></div>';
      }).join('');
      $('rigido').checked = !!cfg.modoRigido;
      $('imagens').checked = (cfg.analisarImagens !== false); // padrao: ligado
      $('imgsens').value = cfg.imagemSensibilidade || 'normal';
      $('termos').value = (cfg.termosPersonalizados || []).join('\n');
    });
  }

  $('btn-salvar').addEventListener('click', function () {
    var desativados = [], ativados = [];
    document.querySelectorAll('#temas input[type=checkbox]').forEach(function (chk) {
      var tema = chk.dataset.tema, padrao = chk.dataset.padrao === 'true';
      if (padrao && !chk.checked) desativados.push(tema);
      if (!padrao && chk.checked) ativados.push(tema);
    });
    var termos = $('termos').value.split('\n').map(function (s) { return s.trim(); }).filter(function (s) { return s.length; });
    var cfg = { temasDesativados: desativados, temasAtivados: ativados, modoRigido: $('rigido').checked, analisarImagens: $('imagens').checked, imagemSensibilidade: $('imgsens').value, termosPersonalizados: termos };
    chrome.storage.local.set({ sentinela_config: cfg }, function () {
      $('salvo').textContent = '✔ Configurações salvas.';
      setTimeout(function () { $('salvo').textContent = ''; }, 2000);
    });
  });

  // ---- painel local (sincronizacao) ----
  // Toda conversa com o servidor passa pelo service worker: so ele tem
  // host_permissions. O popup so pede e mostra.
  function msg(tipo, extra, cb) {
    try {
      chrome.runtime.sendMessage(Object.assign({ tipo: tipo }, extra || {}), function (r) {
        if (chrome.runtime.lastError) { cb({ ok: false, erro: 'sem-resposta' }); return; }
        cb(r || { ok: false, erro: 'sem-resposta' });
      });
    } catch (e) { cb({ ok: false, erro: String(e && e.message || e) }); }
  }

  var TEXTO_ERRO = {
    'token': 'Token recusado pelo painel. Copie de novo em Sentinela → Conectar dispositivo.',
    'offline': 'Painel não respondeu. Ele está aberto no seu PC?',
    'sem-token': 'Falta colar o token do painel.',
    'desligado': 'Envio desligado.',
    'url-invalida': 'O endereço precisa ser 127.0.0.1 ou localhost.',
    'lote-invalido': 'Um lote foi recusado pelo painel e descartado.'
  };

  function renderConn(est) {
    var el = $('conn-estado');
    if (!est) { el.className = 'conn off'; el.textContent = 'Não foi possível falar com a extensão.'; return; }
    $('pnl-ligado').checked = !!est.ligado;
    $('pnl-url').value = est.url || 'http://127.0.0.1:8000';
    $('pnl-disp').value = est.dispositivo || 'este-pc';

    var pend = est.fila ? ' · ' + est.fila + ' na fila' : '';
    if (!est.ligado) { el.className = 'conn'; el.textContent = 'Desligado — o registro fica só aqui na extensão.' + pend; return; }
    if (!est.temToken) { el.className = 'conn off'; el.textContent = 'Falta o token do painel.' + pend; return; }
    if (est.ultimoErro) {
      el.className = 'conn off';
      el.textContent = (TEXTO_ERRO[est.ultimoErro] || ('Erro: ' + est.ultimoErro)) + pend;
      return;
    }
    el.className = 'conn on';
    el.textContent = 'Conectado ao painel' + (est.ultimoEnvio ? ' · último envio ' + hora(est.ultimoEnvio) : '') + pend;
  }

  function carregarConn() { msg('syncEstado', null, function (r) { renderConn(r && r.ok ? r.estado : null); }); }

  $('pnl-salvar').addEventListener('click', function () {
    $('pnl-msg').textContent = 'Conectando…';
    msg('syncSalvar', {
      config: {
        url: $('pnl-url').value,
        token: $('pnl-token').value,
        dispositivo: $('pnl-disp').value,
        ligado: $('pnl-ligado').checked
      }
    }, function (r) {
      if (!r.ok) { $('pnl-msg').style.color = 'var(--red)'; $('pnl-msg').textContent = r.erro || 'Não deu certo.'; return; }
      $('pnl-msg').style.color = 'var(--teal)';
      $('pnl-msg').textContent = '✔ Salvo.';
      $('pnl-token').value = '';  // nao deixa credencial na tela
      renderConn(r.estado);
      setTimeout(function () { $('pnl-msg').textContent = ''; }, 2500);
    });
  });

  $('pnl-sync').addEventListener('click', function () {
    $('pnl-msg').style.color = 'var(--muted2)';
    $('pnl-msg').textContent = 'Enviando…';
    msg('syncAgora', null, function (r) {
      if (!r.ok) { $('pnl-msg').style.color = 'var(--red)'; $('pnl-msg').textContent = r.erro || 'Não deu certo.'; return; }
      var n = (r.resultado && r.resultado.enviados) || 0;
      $('pnl-msg').style.color = n ? 'var(--teal)' : 'var(--muted2)';
      $('pnl-msg').textContent = n ? ('✔ ' + n + ' enviado(s).') : 'Nada novo para enviar.';
      renderConn(r.estado);
      setTimeout(function () { $('pnl-msg').textContent = ''; }, 2500);
    });
  });

  renderLog();
  renderConfig();
  carregarConn();
})();
