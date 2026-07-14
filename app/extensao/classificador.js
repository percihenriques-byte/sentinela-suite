/*
  classificador.js — IA local do Sentinela (mesma lógica do módulo
  Sentinela-Classificador.ps1). Roda no navegador, sem internet.
  Expõe window.SentinelaIA.classify(texto, config).
*/
(function (global) {
  function normalizar(s) {
    s = (s || '').toLowerCase();
    // homoglifos cirilicos -> latinos (evasao "p\u043ern\u043e")
    var homo = {'\u0430':'a','\u043e':'o','\u0435':'e','\u0440':'p','\u0441':'c','\u0445':'x','\u0443':'y','\u0456':'i','\u0455':'s','\u0458':'j'};
    s = s.replace(/[\u0430\u043e\u0435\u0440\u0441\u0445\u0443\u0456\u0455\u0458]/g, function (c) { return homo[c] || c; });
    // NFKD resolve full-width (\uff53\uff45\uff58\uff4f) e ligaduras; depois remove acentos
    s = s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    var raw = s.replace(/(.)\1{2,}/g, '$1');
    var mapa = { '0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','8':'b','9':'g','@':'a','$':'s','+':'t' };
    var leet = s.replace(/[01345789@$+]/g, function (c) { return mapa[c] || c; }).replace(/(.)\1{2,}/g, '$1');
    return { texto: leet, colado: leet.replace(/[^a-z0-9]/g, ''), textoRaw: raw, coladoRaw: raw.replace(/[^a-z0-9]/g, '') };
  }

  // Padrao: true = bloqueia por padrao; false = tema opcional (responsavel ativa)
  var CATS = [
    { nome:'Conteúdo adulto', padrao:true, semReducao:false, termos:{'porno':1,'pornografia':1,'pornografico':1,'xvideos':1,'xnxx':1,'nudes':1,'hentai':1,'putaria':1,'conteudo adulto':1,'sexo explicito':1,'onlyfans':1,'camgirl':1,'sexo':1,'transar':1,'nudez':1,'nudez infantil':1,'pornografia infantil':1,'zoofilia':1,'masturbacao':1,'punheta':1,'siririca':1,'pelada':.5,'pelado':.5,'+18':.5}},
    { nome:'Violência', padrao:true, semReducao:false, termos:{'decapitacao':1,'tortura':1,'gore':1,'estupro':1,'espancamento':.5,'violencia extrema':1,'videos de violencia':1,'briga de rua':1,'violencia':.5,'sangue':.35,'briga':.35,'assassinato':.5,'massacre':.5}},
    { nome:'Autolesão e suicídio', padrao:true, semReducao:true, termos:{'suicidio':1,'como se matar':1,'me matar':1,'quero morrer':1,'vontade de morrer':1,'automutilacao':1,'me cortar':1,'tirar a propria vida':1,'tirar minha vida':1,'anorexia dicas':1,'pro ana':1}},
    { nome:'Armas', padrao:true, semReducao:true, termos:{'como fazer bomba':1,'fabricar arma':1,'arma caseira':1,'explosivo':.5,'pistola':.35,'rifle':.35,'municao':.35}},
    { nome:'Drogas', padrao:true, semReducao:false, termos:{'como usar drogas':1,'comprar maconha':1,'cocaina':.5,'crack':.5,'maconha':.5,'lsd':.5,'ecstasy':.5,'droga':.35,'entorpecente':.5}},
    { nome:'Apostas', padrao:true, semReducao:true, termos:{'cassino online':1,'aposta esportiva':1,'jogo do bicho':1,'aposta':.5,'cassino':.5,'tigrinho':1,'jogo do tigrinho':1,'bet365':1,'betano':1,'sportingbet':1,'blaze aposta':1}},
    { nome:'Burlar proteção', padrao:true, semReducao:true, termos:{'burlar filtro':1,'burlar o filtro':1,'driblar o filtro':1,'desativar safesearch':1,'desbloquear sites':1,'filtro da escola':1,'vpn para escola':1,'como burlar':.5,'proxy anonimo':.5}},
    { nome:'Linguagem imprópria', padrao:true, semReducao:true, termos:{'caralho':.5,'porra':.5,'buceta':1,'piroca':1}},
    { nome:'Namoro e relacionamento', padrao:false, semReducao:true, termos:{'app de namoro':1,'tinder':1,'como beijar':.5,'namorada online':.5,'pegar meninas':.5}},
    { nome:'Redes sociais', padrao:false, semReducao:true, termos:{'tiktok':.5,'instagram':.5,'kwai':.5,'snapchat':.5}}
  ];
  var CTX_SEGURO = ['dever de casa','trabalho escolar','feira de ciencias','aula de ciencias','biologia','saude','medico','doenca','cancer','prevencao','sintomas','aula de'];

  function nrmNome(s) { return (s || '').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim(); }

  function classify(texto, config) {
    config = config || {};
    // nomes de tema comparados sem acento/caixa (BUG-11)
    var desativados = (config.temasDesativados || []).map(nrmNome);
    var ativados = (config.temasAtivados || []).map(nrmNome);
    var termosExtra = config.termosPersonalizados || [];
    var limiar = config.modoRigido ? 0.5 : 1.0;

    var n = normalizar(texto);
    var reducao = 0;
    for (var i = 0; i < CTX_SEGURO.length; i++) { if (n.texto.indexOf(CTX_SEGURO[i]) !== -1) { reducao = 0.5; break; } }

    var cats = [];
    for (var c = 0; c < CATS.length; c++) {
      var cat = CATS[c];
      var cn = nrmNome(cat.nome);
      if (desativados.indexOf(cn) !== -1) continue;
      if (!cat.padrao && ativados.indexOf(cn) === -1) continue;
      cats.push(cat);
    }
    if (termosExtra.length) {
      var extra = {};
      for (var e = 0; e < termosExtra.length; e++) {
        var t = (termosExtra[e] || '').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        if (t) extra[t] = 1;
      }
      cats.push({ nome:'Bloqueio do responsável', padrao:true, semReducao:true, termos:extra });
    }

    var melhor = null;
    for (var k = 0; k < cats.length; k++) {
      var ct = cats[k], score = 0, sinais = [];
      for (var termo in ct.termos) {
        var colado = termo.replace(/[^a-z0-9]/g, '');
        var achou = n.texto.indexOf(termo) !== -1 || n.textoRaw.indexOf(termo) !== -1;
        if (!achou && colado.length >= 3) { achou = n.colado.indexOf(colado) !== -1 || n.coladoRaw.indexOf(colado) !== -1; }
        if (achou) {
          score += ct.termos[termo]; sinais.push(termo);
        }
      }
      if (score > 0) {
        var red = ct.semReducao ? 0 : reducao;
        var sf = Math.max(0, score - red);
        if (!melhor || sf > melhor.score) melhor = { category: ct.nome, score: sf, signals: sinais };
      }
    }
    if (!melhor) return { block: false, category: null, confidence: 0, signals: [] };
    return {
      block: melhor.score >= limiar,
      category: melhor.category,
      confidence: Math.min(1, melhor.score / (limiar * 1.5)),
      signals: melhor.signals
    };
  }

  function contarOcorrencias(hay, needle) {
    if (!needle) return 0;
    var n = 0, i = 0;
    while ((i = hay.indexOf(needle, i)) >= 0) { n++; i += needle.length; }
    return n;
  }

  // Analisa o CONTEUDO de uma pagina inteira (o que a crianca VE), contando
  // ocorrencias, com limiar mais alto p/ nao bloquear mencao incidental.
  function classifyPagina(texto, config, limiar) {
    config = config || {}; limiar = limiar || 3.0;
    if (!texto || !texto.trim()) return { block: false, category: null, score: 0, signals: [] };
    var n = normalizar(texto);
    var desativados = (config.temasDesativados || []).map(nrmNome);
    var ativados = (config.temasAtivados || []).map(nrmNome);
    var termosExtra = config.termosPersonalizados || [];
    var cats = [];
    for (var c = 0; c < CATS.length; c++) {
      var cat = CATS[c], cn = nrmNome(cat.nome);
      if (desativados.indexOf(cn) !== -1) continue;
      if (!cat.padrao && ativados.indexOf(cn) === -1) continue;
      cats.push(cat);
    }
    if (termosExtra.length) {
      var extra = {};
      for (var e = 0; e < termosExtra.length; e++) {
        var t = (termosExtra[e] || '').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        if (t) extra[t] = 1;
      }
      cats.push({ nome: 'Bloqueio do responsável', padrao: true, semReducao: true, termos: extra });
    }
    var melhor = null;
    for (var k = 0; k < cats.length; k++) {
      var ct = cats[k], score = 0, sinais = [];
      for (var termo in ct.termos) {
        var occ = contarOcorrencias(n.texto, termo);
        if (occ === 0) occ = contarOcorrencias(n.textoRaw, termo);
        if (occ > 0) { score += ct.termos[termo] * Math.min(occ, 3); sinais.push(occ + 'x' + termo); }
      }
      if (score > 0 && (!melhor || score > melhor.score)) melhor = { category: ct.nome, score: score, signals: sinais };
    }
    if (!melhor) return { block: false, category: null, score: 0, signals: [] };
    return { block: melhor.score >= limiar, category: melhor.category, score: Math.round(melhor.score * 10) / 10, signals: melhor.signals };
  }

  global.SentinelaIA = { classify: classify, classifyPagina: classifyPagina, temas: CATS.map(function (c) { return { tema: c.nome, padraoLigado: c.padrao }; }) };
})(this);
