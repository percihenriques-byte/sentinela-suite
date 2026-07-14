# ✅ Teste manual da extensão (5 minutos)

Este guia confirma, num navegador **com janela** (Edge ou Chrome), que a extensão do
Sentinela carrega e funciona. Todos os testes usam conteúdo **seguro** — você não precisa
visitar nenhum site impróprio.

> Marque cada item. No fim, me diga o que passou (✅) e o que não passou (❌), e se
> apareceu algum erro. Com isso eu ajusto o que precisar.

---

## Passo 0 — Instalar a extensão (uma vez)

1. Abra `edge://extensions` (ou `chrome://extensions`).
2. Ligue o **Modo do desenvolvedor** (canto da tela).
3. Clique em **Carregar sem compactação** e escolha a pasta `app/extensao`.
4. A extensão **Sentinela — Filtro e Supervisão** deve aparecer, **sem erros**.
   - [ ] Apareceu e está **ativada**
   - [ ] Não há um botão vermelho de **"Erros"** (se houver, clique e me mande o texto)
5. Clique em **Detalhes** da extensão e ligue **"Permitir acesso a URLs de arquivo"**
   (isso é só para o Teste 2 com o arquivo local).
   - [ ] Liguei "acesso a URLs de arquivo"

---

## Teste 1 — Bloqueio de BUSCA (30 s)

1. Abra o Google (ou Bing) numa aba normal.
2. Busque: **`jogo do tigrinho`** (é seguro — é um teste de "apostas").
3. **Esperado:** a página vira a tela **"Conteúdo bloqueado pelo Sentinela"**, categoria
   *Apostas*.
   - [ ] Bloqueou ✅
4. Agora abra uma **aba anônima** e repita a busca.
   - [ ] Bloqueou também no anônimo ✅

## Teste 2 — Bloqueio de CONTEÚDO da página (30 s)

1. Abra o arquivo **`docs/teste/pagina-teste.html`** no navegador (arraste-o para uma aba).
   É uma página inofensiva que só **fala** de apostas.
2. **Esperado:** a página é **bloqueada** assim que abre (tela do Sentinela).
   - [ ] Bloqueou a página pelo **conteúdo de texto** ✅

## Teste 3 — Supervisão (30 s)

1. Clique no ícone 🛡️ da extensão (barra do navegador) → aba **Supervisão**.
2. **Esperado:** você vê os testes acima **registrados** (a busca do tigrinho e a página),
   em destaque como bloqueadas, com data/hora.
   - [ ] Os registros aparecem ✅

## Teste 4 — Configuração (30 s)

1. No popup → aba **Configurar temas**.
2. **Desligue** o tema *Apostas* e clique **Salvar**.
3. Busque **`jogo do tigrinho`** de novo.
   - [ ] Agora **NÃO** bloqueia (você desligou o tema) ✅
4. **Religue** o tema *Apostas* e salve (para voltar ao normal).
   - [ ] Religuei ✅

## Teste 5 — Imagens (opcional, ~1 min)

A análise de imagem é um **heurístico** (borra imagens com muita "pele"). É a parte mais
difícil de testar com segurança e a que mais pode errar.
1. No popup → **Configurar temas** → confirme que **"Analisar imagens"** está ligado.
2. Abra uma página **comum** com fotos grandes de pessoas (ex.: um portal de notícias).
3. **Observe:** algumas fotos podem ficar **borradas** (é o heurístico agindo). Se borrar
   **muita** coisa normal, me avise — a gente baixa o modelo treinado (mais preciso) ou
   ajusta o limiar.
   - [ ] Testei imagens (anote se borrou demais, de menos, ou ok)

---

## Se algo não funcionar

- **A extensão não carrega / dá erro:** em `edge://extensions`, clique em **"Erros"** na
  extensão e me mande o texto.
- **Não bloqueia nada:** confirme que a extensão está **ativada**; recarregue a página
  (F5). Para o Teste 2, confirme o "acesso a URLs de arquivo" (Passo 0.5).
- **Ver o console:** aperte **F12** → aba **Console** na página que testou, e me mande
  qualquer linha em vermelho.

## O que me reportar
1. Passo 0 (carregou sem erro?) — ✅/❌
2. Teste 1 (busca) — ✅/❌
3. Teste 2 (conteúdo da página) — ✅/❌
4. Teste 3 (supervisão) — ✅/❌
5. Teste 4 (config) — ✅/❌
6. Teste 5 (imagens) — borrou demais / de menos / ok
7. Qualquer mensagem de erro que apareceu.
