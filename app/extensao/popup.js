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

  renderLog();
  renderConfig();
})();
