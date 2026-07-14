/*
  analise-imagem.js — analisador de imagem LOCAL do Sentinela.
  Roda no service worker (background) e, se quiser, num teste isolado.

  Duas camadas:
   1) HEURISTICO (sempre disponivel, sem download): proporcao de pixels
      em tom de pele. Cru — pode errar em fotos normais de pessoas —, por
      isso o limiar e conservador. Serve como 1a linha offline.
   2) MODELO (opcional, preciso): se os arquivos de um modelo NSFW forem
      colocados na pasta modelo/ da extensao, o background pode usa-lo.
      Veja modelo/COMO-ADICIONAR-MODELO.md. Enquanto nao houver modelo,
      usa-se o heuristico.

  Expõe self.SentinelaImg.analisarPixels(data, w, h) -> { flag, skinRatio }
*/
(function (global) {
  // Regra de pele em RGB (Kovac et al.) — rapida e sem dependencias.
  function ehPele(r, g, b) {
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    return r > 95 && g > 40 && b > 20 &&
           (mx - mn) > 15 &&
           Math.abs(r - g) > 15 && r > g && r > b;
  }

  // data = Uint8ClampedArray RGBA. Retorna proporcao de pele e o veredito.
  // Limiar conservador (0.45) + exige imagem com area minima (checada por quem chama).
  function analisarPixels(data, w, h, limiar) {
    limiar = limiar || 0.45;
    var total = 0, pele = 0;
    // amostra 1 a cada N pixels para performance
    var passo = 4 * Math.max(1, Math.floor((w * h) / 40000));
    for (var i = 0; i < data.length; i += passo) {
      var r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3];
      if (a < 125) continue; // ignora transparente
      total++;
      if (ehPele(r, g, b)) pele++;
    }
    var ratio = total > 0 ? (pele / total) : 0;
    return { flag: ratio >= limiar, skinRatio: Math.round(ratio * 100) / 100 };
  }

  global.SentinelaImg = { analisarPixels: analisarPixels, ehPele: ehPele };
})(typeof self !== 'undefined' ? self : this);
