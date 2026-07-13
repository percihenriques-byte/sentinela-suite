/*
  classificador.js — IA local do Sentinela (mesma lógica do módulo
  Sentinela-Classificador.ps1). Roda no navegador, sem internet.
  Expõe window.SentinelaIA.classify(texto, config).
*/
(function (global) {
  function normalizar(s) {
    s = (s || '').toLowerCase();
    s = s.normalize('NFD').replace(/[̀-ͯ]/g, ''); // tira acentos
    var mapa = { '0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','8':'b','9':'g','@':'a','$':'s','+':'t' };
    s = s.replace(/[01345789@$+]/g, function (c) { return mapa[c] || c; });
    s = s.replace(/(.)\1{2,}/g, '$1');                 // encolhe repetições
    return { texto: s, colado: s.replace(/[^a-z0-9]/g, '') };
  }

  // Padrao: true = bloqueia por padrao; false = tema opcional (responsavel ativa)
  var CATS = [
    { nome:'Conteúdo adulto', padrao:true, semReducao:false, termos:{'porno':1,'pornografia':1,'pornografico':1,'xvideos':1,'xnxx':1,'nudes':1,'hentai':1,'putaria':1,'conteudo adulto':1,'sexo explicito':1,'onlyfans':1,'camgirl':1,'sexo':.5,'nudez':.5,'pelada':.5,'pelado':.5,'+18':.5,'nu':.35,'seios':.35}},
    { nome:'Violência', padrao:true, semReducao:false, termos:{'decapitacao':1,'tortura':1,'gore':1,'estupro':1,'espancamento':.5,'violencia':.5,'sangue':.35,'briga':.35,'assassinato':.5,'massacre':.5}},
    { nome:'Autolesão e suicídio', padrao:true, semReducao:true, termos:{'suicidio':1,'como se matar':1,'automutilacao':1,'me cortar':1,'tirar a propria vida':1,'anorexia dicas':1,'pro ana':1}},
    { nome:'Armas', padrao:true, semReducao:true, termos:{'como fazer bomba':1,'fabricar arma':1,'arma caseira':1,'explosivo':.5,'pistola':.35,'rifle':.35,'municao':.35}},
    { nome:'Drogas', padrao:true, semReducao:false, termos:{'como usar drogas':1,'comprar maconha':1,'cocaina':.5,'crack':.5,'maconha':.5,'lsd':.5,'ecstasy':.5,'droga':.35,'entorpecente':.5}},
    { nome:'Apostas', padrao:true, semReducao:true, termos:{'cassino online':1,'aposta esportiva':1,'jogo do bicho':1,'aposta':.5,'bet':.35,'cassino':.5,'tigrinho':1,'jogo do tigrinho':1}},
    { nome:'Burlar proteção', padrao:true, semReducao:true, termos:{'burlar filtro':1,'burlar o filtro':1,'driblar o filtro':1,'desativar safesearch':1,'desbloquear sites':1,'filtro da escola':1,'vpn para escola':1,'como burlar':.5,'proxy anonimo':.5}},
    { nome:'Linguagem imprópria', padrao:true, semReducao:true, termos:{'caralho':.5,'porra':.5,'buceta':1,'piroca':1}},
    { nome:'Namoro e relacionamento', padrao:false, semReducao:true, termos:{'app de namoro':1,'tinder':1,'como beijar':.5,'namorada online':.5,'pegar meninas':.5}},
    { nome:'Redes sociais', padrao:false, semReducao:true, termos:{'tiktok':.5,'instagram':.5,'kwai':.5,'snapchat':.5}}
  ];
  var CTX_SEGURO = ['dever de casa','trabalho escolar','feira de ciencias','aula de ciencias','biologia','saude','medico','doenca','cancer','prevencao','sintomas','aula de'];

  function classify(texto, config) {
    config = config || {};
    var desativados = config.temasDesativados || [];
    var ativados = config.temasAtivados || [];
    var termosExtra = config.termosPersonalizados || [];
    var limiar = config.modoRigido ? 0.5 : 1.0;

    var n = normalizar(texto);
    var reducao = 0;
    for (var i = 0; i < CTX_SEGURO.length; i++) { if (n.texto.indexOf(CTX_SEGURO[i]) !== -1) { reducao = 0.5; break; } }

    var cats = [];
    for (var c = 0; c < CATS.length; c++) {
      var cat = CATS[c];
      if (desativados.indexOf(cat.nome) !== -1) continue;
      if (!cat.padrao && ativados.indexOf(cat.nome) === -1) continue;
      cats.push(cat);
    }
    if (termosExtra.length) {
      var extra = {};
      for (var e = 0; e < termosExtra.length; e++) {
        var t = (termosExtra[e] || '').toString().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
        if (t) extra[t] = 1;
      }
      cats.push({ nome:'Bloqueio do responsável', padrao:true, semReducao:true, termos:extra });
    }

    var melhor = null;
    for (var k = 0; k < cats.length; k++) {
      var ct = cats[k], score = 0, sinais = [];
      for (var termo in ct.termos) {
        var colado = termo.replace(/[^a-z0-9]/g, '');
        if (n.texto.indexOf(termo) !== -1 || (colado.length >= 3 && n.colado.indexOf(colado) !== -1)) {
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

  global.SentinelaIA = { classify: classify, temas: CATS.map(function (c) { return { tema: c.nome, padraoLigado: c.padrao }; }) };
})(this);
