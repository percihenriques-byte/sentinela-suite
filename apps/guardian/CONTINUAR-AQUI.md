# CONTINUAR-AQUI — Sentinela (leia isto ANTES de fazer qualquer coisa)

Este arquivo é o ponto de partida para continuar o projeto **Sentinela**. Se você é uma
instância nova do assistente, leia tudo daqui até o fim antes de agir.

---

## ⛔ REGRAS DE COMPORTAMENTO (as mais importantes — o usuário reforçou várias vezes)

1. **TRABALHE SOZINHO. NÃO PERGUNTE NADA.** Nunca diga "quer que eu faça/rode/teste?".
   Execute e mostre o resultado. Perguntar = falha grave para este usuário.
2. **NÃO PARE o loop por conta própria.** Só pare se o usuário mandar parar explicitamente.
   Ao terminar um tick, faça o próximo. Continue mesmo se tudo estiver funcional
   ("continue rodando teste e aprimorando a análise de imagens").
3. **NÃO use a ferramenta Artifact** (publicar/listar). O usuário não quer — ela abre
   pedido de aprovação e ele interpreta como "estou perguntando/parando". A demo já está
   sincronizada e commitada no repo; o link ao vivo o usuário atualiza sozinho se quiser.
4. **EVITE ações que abram pop-up de permissão.** Leituras de arquivo fora do repo, a
   ferramenta Artifact, etc. abriram prompts que o usuário leu como "me pedindo permissão".
   Prefira editar arquivos DENTRO do repo e rodar os comandos de teste já conhecidos.
5. **NÃO escreva nada na pasta da CRM** (`~/jarvis-crm`). O Playwright de teste está
   instalado lá e é apenas EXECUTADO — nada é gravado na CRM. Arquivos temporários de
   teste vão para a pasta temporária (scratchpad) da sessão.
6. **Sem APIs externas / sem "não recomendo" para disfarçar trabalho não feito.** Construa
   o que foi pedido (controle parental legítimo) e seja honesto só sobre limites reais.
7. **Idioma:** responda em **português (PT-BR)**. Código/comentários podem ser em inglês.
8. **Cadência do loop:** commits incrementais a cada ~5 min, 1 commit por melhoria.

---

## 🎯 O QUE É O PROJETO

Sentinela é um **SafeSearch/controle parental à prova de incógnito** — trabalho do filho do
usuário para a olimpíada **Liga Jovem / SEBRAE**. Precisa ser: bloqueio por **IA local**
(sem internet), **impossível de burlar** (só destrava com trava parental/PIN) e **fácil de
instalar** (acessível a leigos). A IA **vê o que a criança vê** (busca + texto da página +
imagens) e decide se é apropriado.

## 🧱 ARQUITETURA (100% local, sem APIs externas)

1. **Rede:** filtro DNS (CleanBrowsing) + bloqueio no `hosts` (forcesafesearch/restrict
   youtube), travado por PIN; um "Guardião" reaplica se adulterarem.
2. **Extensão de navegador (MV3):** classificador de IA local que analisa busca, texto da
   página e **imagens** (borra as impróprias). Trava via política do navegador + servidor
   local em 127.0.0.1.
3. **Painel PowerShell** para o responsável (status, PIN, supervisão, sensibilidade).

Arquivos-chave:
- `app/Sentinela-Classificador.ps1` — classificador de texto (fonte de verdade).
- `app/extensao/classificador.js` — **espelho JS** do PS (tem de ficar sincronizado).
- `app/extensao/analise-imagem.js` — heurístico de imagem (pele conexa + YCbCr + saturação).
- `app/extensao/content.js` / `background.js` — injeção, análise de página e imagem.
- `app/Testes/Executar-Testes.ps1` (139 testes) · `Medir-Precisao.ps1` (corpus rotulado).
- `app/Testes/img-corpus.html` — teste versionado do heurístico de imagem.
- `demo/index.html` + `demo/sentinela-artifact.html` — demo do pitch (já sincronizadas).

## ✅ ESTADO ATUAL (tudo testado no Chromium via Playwright)

- Texto: **corpus 373 casos / 100%** (0 falso-pos/neg), **suíte 139/139**.
- Cobertura **PT + inglês + espanhol + francês**: adulto, violência, autolesão/suicídio, armas, drogas,
  apostas, **ódio/extremismo**, burlar proteção, + gírias BR (caça-níquel, lança-perfume),
  marcas de site adulto/aposta, **CSAM/aliciamento** (pedofilia, foto íntima), evasões
  (leet/espaço/homóglifo/hífen).
- **SafeSearch se auto-configura em 3 camadas** (Enable-Sentinela): DNS de filtro + hosts +
  **política de navegador** (ForceGoogleSafeSearch, ForceYouTubeRestrict=2, DnsOverHttpsMode=off,
  BuiltInDnsClientEnabled=0) — fecha a brecha do DNS-over-HTTPS. Guardião reaplica; Disable/
  Desinstalar removem. Em simulação as políticas vão para `HKCU:\Software\SentinelaTeste`.
- Cuidado com **substring**: NÃO usar `sex`/`nude`/`naked`/`weed`/`xxx` puros (pegariam
  Sussex, nudez-arte, seaweed, filme xXx). Usar frases (`sex video`, `nude pics`…).
- Imagem: maior região **conexa** de pele + Kovac **R>75 (inclusivo p/ pele escura)** +
  YCbCr + **teto de saturação HSV ≤0.58** (corta madeira) + gate de suavidade + só analisa
  imagens **visíveis** + sensibilidade configurável. img-corpus **20 casos / 0 erros reais**.
- **Limites honestos** (só um modelo treinado resolve): superfícies lisas cor-de-pele
  (areia, pinho, torrada) podem ser borradas; slot para modelo em `app/extensao/modelo/`.

Últimos commits do loop (repo `percihenriques-byte/sentinela`, privado, branch `main`):
`dbd36c2` só-visíveis · `2d0fa1f` ódio · `22ae2da` saturação · `ffa6d22` pele escura ·
`67d73ea` gírias BR · `a84faf7` roupa de banho · `c71925f` inglês · `00b3b68` demo sincronizada ·
`f6065b2` handoff · `a7455a4` marcas+CSAM · `c922de9` evasões hífen · `158220d` SafeSearch 3 camadas ·
`fc545d4` espanhol.

## 🔧 COMO TESTAR (comandos exatos)

Python com Playwright (SÓ EXECUTAR, não gravar na CRM):
`~/jarvis-crm/backend/.venv/Scripts/python.exe`

- Suíte de texto: `powershell -NoProfile -ExecutionPolicy Bypass -File app\Testes\Executar-Testes.ps1`
- Precisão: `powershell ... -File app\Testes\Medir-Precisao.ps1`  → esperar "100%".
- Sondar termos novos: script `probe.ps1` no scratchpad que faz dot-source do classificador
  e chama `Get-ClassificacaoConteudo -Texto ... | .Bloquear` (ver histórico).
- Espelho JS: criar `app/extensao/_jscheck.html` (apagar depois), carregar no Playwright e
  ler `#out`. Comparar block/free com o PS.
- Imagem: gerar PNG por zlib (clamp 0..255!), carregar extensão com
  `launch_persistent_context(udd, headless=False, args=['--headless=new','--load-extension=<ext>','--disable-extensions-except=<ext>'])`,
  setar config via `service_worker.evaluate(chrome.storage.local.set(...))`, e checar
  `getComputedStyle(img).filter` conter `blur`. (Propriedade `__sentinelaImg` NÃO é visível
  do mundo da página — use o blur como sinal.)
- Demo: carregar `demo/index.html`, `#q` + Enter, ler `#result` (contém "bloqu…" se bloqueou).
- Regras PS: **ASCII-only** nos `.ps1` (exceto `gui/Sentinela-Painel.ps1`). PS+JS sempre
  sincronizados. Rodar os testes a CADA mudança.

## ▶️ PRÓXIMOS PASSOS (continuar o loop)

1. Sondar mais **evasões** (leet/espaços/homoglifos), marcas de sites adultos/apostas e
   termos de **aliciamento/grooming** que devem bloquear — fechar sem criar falso-positivo.
2. Mais **stress de imagem** (tons intermediários, fundos variados) sem enfraquecer a
   detecção real de nudez.
3. Manter README/PITCH/`~/sentinela-testlog.md` coerentes. **Não** republicar Artifact.
4. Sempre: manter Medir-Precisao 100% e suíte 139/139; PS+JS+demo sincronizados; commit+push
   incremental por melhoria.

## 📌 Onde está o resto do histórico
- Log de bugs/correções (fora do repo): `~/sentinela-testlog.md`.
- Repo privado: `percihenriques-byte/sentinela` (GitHub), branch `main`.
