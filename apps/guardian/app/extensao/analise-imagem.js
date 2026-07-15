/*
  analise-imagem.js — analisador de imagem LOCAL do Sentinela.
  Roda no service worker (background) e, se quiser, num teste isolado.

  Heuristico (sem download): deteccao de pele em RGB + YCbCr e, o mais
  importante, a MAIOR REGIAO CONECTADA de pele (um corpo tende a ser um
  grande bloco continuo de pele, enquanto texturas/colagens/cenarios cor
  de pele ficam espalhados). Isso reduz muito o falso-positivo em fotos
  normais (rostos pequenos, mosaicos, thumbnails).

  Comportamento por design (verificado no navegador):
   - Foto vestida comum (so rosto/maos = pouca pele) NAO e borrada.
   - Roupa de banho / muita pele exposta E borrada (lado seguro do filtro);
     quem quiser afrouxar usa a sensibilidade 'conservador' no painel.
   - Duas figuras separadas de tamanho medio podem nao atingir o limiar
     (usa a MAIOR regiao conexa, nao a soma) - troca consciente p/ evitar
     falso-positivo de pele espalhada.

  Limite honesto (teto de cor): superficies lisas genuinamente cor-de-pele
  (areia, pinho/madeira clara, torrada/tan) podem ser borradas por engano —
  a cor delas e a mesma da pele. Erra para o lado SEGURO (borrar demais) e
  detecta todo tom de pele, do claro ao muito escuro. Para separar isso de
  verdade, plugar um modelo treinado (modelo/COMO-ADICIONAR-MODELO.md).

  Expõe self.SentinelaImg.analisarPixels(data, w, h) -> { flag, skinRatio, blobRatio }
*/
(function (global) {
  // Pele: combina regra RGB (Kovac) com faixa YCbCr (mais robusta).
  function ehPele(r, g, b) {
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    // R>75 (nao 95) para NAO perder pele escura/muito escura — protecao tem de
    // valer para todo tom de pele. O teto de saturacao abaixo barra os marrons
    // saturados que essa faixa mais ampla poderia deixar entrar.
    var rgb = r > 75 && g > 40 && b > 20 && (mx - mn) > 15 &&
              Math.abs(r - g) > 15 && r > g && r > b;
    if (!rgb) return false;
    // Saturacao (HSV): pele humana (clara a escura) fica ~0.2-0.55; marrom de
    // madeira/couro/laranja passa de ~0.6. O teto corta esses falsos-positivos
    // SEM excluir tons de pele reais (nao enfraquece a protecao em pele escura).
    var sat = mx > 0 ? (mx - mn) / mx : 0;
    if (sat > 0.58) return false;
    // YCbCr: pele costuma ter Cb ~[77,135], Cr ~[133,180]
    var cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b;
    var cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b;
    return cb >= 77 && cb <= 135 && cr >= 133 && cr <= 180;
  }

  // data = Uint8ClampedArray RGBA (w x h).
  // flag = a MAIOR regiao conexa de pele cobre >= limiarBlob da imagem.
  function analisarPixels(data, w, h, limiarBlob) {
    limiarBlob = limiarBlob || 0.30;
    var n = w * h;
    if (n === 0) return { flag: false, skinRatio: 0, blobRatio: 0 };

    // 1) mascara de pele
    var mask = new Uint8Array(n);
    var totalPele = 0;
    for (var i = 0; i < n; i++) {
      var p = i * 4;
      if (data[p + 3] >= 125 && ehPele(data[p], data[p + 1], data[p + 2])) { mask[i] = 1; totalPele++; }
    }

    // 2) maior componente conexo (4-conectividade, DFS iterativo)
    var visit = new Uint8Array(n);
    var maior = 0;
    var stack = new Int32Array(n);
    for (var s = 0; s < n; s++) {
      if (!mask[s] || visit[s]) continue;
      var top = 0, count = 0;
      stack[top++] = s; visit[s] = 1;
      while (top > 0) {
        var c = stack[--top]; count++;
        var x = c % w, y = (c / w) | 0;
        var l = c - 1, r = c + 1, u = c - w, d = c + w;
        if (x > 0 && mask[l] && !visit[l]) { visit[l] = 1; stack[top++] = l; }
        if (x < w - 1 && mask[r] && !visit[r]) { visit[r] = 1; stack[top++] = r; }
        if (y > 0 && mask[u] && !visit[u]) { visit[u] = 1; stack[top++] = u; }
        if (y < h - 1 && mask[d] && !visit[d]) { visit[d] = 1; stack[top++] = d; }
      }
      if (count > maior) maior = count;
    }

    // 3) suavidade: gradiente medio de luminancia entre pixels de pele vizinhos.
    //    Pele/superficies reais sao suaves (~5-25); so RUIDO extremo passa de ~50.
    //    Serve para nao "borrar" imagens de ruido/corrompidas cor-de-pele.
    var somaGrad = 0, contGrad = 0;
    for (var y2 = 0; y2 < h; y2++) {
      var base = y2 * w;
      for (var x2 = 0; x2 < w - 1; x2++) {
        var idx = base + x2;
        if (mask[idx] && mask[idx + 1]) {
          var a = idx * 4, b = (idx + 1) * 4;
          var l1 = 0.299 * data[a] + 0.587 * data[a + 1] + 0.114 * data[a + 2];
          var l2 = 0.299 * data[b] + 0.587 * data[b + 1] + 0.114 * data[b + 2];
          somaGrad += Math.abs(l1 - l2); contGrad++;
        }
      }
    }
    var suavidade = contGrad > 0 ? somaGrad / contGrad : 0;
    var muitoRuidoso = suavidade > 50;

    var blobRatio = maior / n;
    var skinRatio = totalPele / n;
    return {
      flag: (blobRatio >= limiarBlob) && !muitoRuidoso,
      skinRatio: Math.round(skinRatio * 100) / 100,
      blobRatio: Math.round(blobRatio * 100) / 100,
      suavidade: Math.round(suavidade)
    };
  }

  global.SentinelaImg = { analisarPixels: analisarPixels, ehPele: ehPele };
})(typeof self !== 'undefined' ? self : this);
