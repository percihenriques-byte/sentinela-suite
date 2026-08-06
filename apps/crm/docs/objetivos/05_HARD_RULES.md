# Regras Inegociáveis do Perci

Leia isso ANTES de propor qualquer mudança. Cada regra foi reforçada múltiplas vezes.
Quebrar essas regras causou irritação real (documentado no memory system).

## 1. ⛔ ZERO APIs EXTERNAS

Reforçado **3+ vezes** com irritação crescente:

> "não faz nada de OAuth Google/LinkedIn/Anthropic, DuckDuckGo, browse_url. Só HTTP local
> (127.0.0.1). Integração é via arquivos (.ics/.csv/.vcf) na pasta de trabalho."

- ❌ Nenhum `fetch()` pra domínio externo
- ❌ Nenhum OAuth, JWT de terceiro, SSO
- ❌ Nenhum cloud LLM em runtime (Anthropic Claude, OpenAI, etc.)
- ❌ Nenhum Google Fonts, CDN, Google Maps, analytics
- ❌ Nenhum browse_url no Jarvis
- ✅ Integração com dispositivo: **arquivos** que o usuário coloca na pasta workdir
  (`.ics` calendário, `.csv` contatos, `.vcf` vcard)

Se você acha que uma feature precisa de API externa, **PARE** e pergunte antes.

## 2. ⚙️ Trabalhe sozinho — não pergunte

Reforçado **5+ vezes**:

> "sempre pergunta ao invés de fazer, eu quero que vc faça"
> "para de me perguntar toda vez"
> "eu queria que fizesse sem me perguntar"

- ✅ Execute e mostre o resultado
- ❌ Nunca "quer que eu…?"
- ❌ Nunca "posso rodar…?"
- ❌ Nunca "gostaria que eu…?"

Se genuinamente ambíguo, faça a escolha mais provável, execute, mostre o diff e o resultado.
Se estiver errado, o Perci corrige e você reverte. Isso incomoda muito menos que perguntar.

## 3. 🔥 Não use Manus

> "do not use manus anymore"

Perci teve conta bloqueada pelo Manus, migrou pra Claude. Não referencie Manus como
concorrente, não invoque `Skill manus`, não sugira Manus como comparação.

## 4. 🇧🇷 Locale PT-BR

O usuário fala português brasileiro. Responda sempre em PT-BR (inglês OK só em código +
comentários). Se ele escrever em inglês, você pode responder em inglês, mas na dúvida = PT.

O produto também é BR-first: default language do backend é PT, default de detect_lang é PT.

## 5. 🧪 Teste como usuário real

> "os testes sao somente scrints shots porque eu instalei uma skill para vc navegar como um
> usuario e testa o app em si"

- ❌ Screenshots isolados como "prova"
- ✅ Playwright walkthrough com slow_mo, click de verdade, captura JS + HTTP
- ✅ Rodar múltiplos rounds até 0 issues
- ✅ Depois rodar backend `pytest -q`

Screenshots são complemento — a prova é o walkthrough passar.

## 6. 🚫 Não redirecionar pra browser externo

> "isso esta me redirecionando para o brave quando nao era para me redirecionar no total"

- ❌ `start "" URL` nos `.bat` que abre navegador padrão
- ✅ Terminal mostra URL, usuário copia se quiser
- ❌ Não usar pywebview a menos que ele peça explicitamente
- ✅ Server em `0.0.0.0` (não `127.0.0.1`) pra celular acessar via LAN Wi-Fi

## 7. 💻 Windows-first (mas Linux não quebrar)

Perci roda em Windows 11. Path com espaço (`C:\Users\PERCI HENRIQUES\`) é comum.

- ✅ `.bat` usa `%~dp0` como âncora absoluta (nunca paths relativos)
- ✅ Escapar aspas com cuidado — `cmd /k "cd ... && ..."` é frágil
- ✅ Usar arquivos auxiliares `.cmd` em vez de comandos gigantes escapados
- ✅ Testar `INSTALAR.bat` de CWD errado (Perci clica de qualquer lugar)

## 8. 📱 Funciona no celular também

> "eu ter falado que era para ser um app que funciona para pc e celular"

- ✅ UI responsiva (viewport 390x844 testado)
- ✅ Server em `0.0.0.0:8000` — celular acessa via IP LAN
- ✅ Mobile hamburger + sidebar deslizante
- ✅ Touch targets ≥ 44px
- ✅ Skeleton loading pra latência de Wi-Fi

## 9. 🔒 Repo privado

> "tem que ser privado o repo no git"

Sempre `gh repo create --private`. Nunca commit de `.env`, `.db`, tokens, credenciais.

## 10. 🎯 UX de "produto de dinheiro", não dev-demo

> "esta horrivel como nem coisa para dar enter no signup tem"
> "serio como vc fez isso 4 horas e vc me entrega uma merda dessa"

Cada tela precisa ter:
- Hero grande (h1 clamp 40-64px)
- Feature cards com hover
- Stats/números destacados
- Botões primary com gradient
- Micro-interações (skeleton, animações, hover states)
- Empty states polidos (não texto seco)
- Dark mode elegante

Landing genérica com texto pequeno perdido no vazio = INACEITÁVEL.

## 11. 🎨 Não introduzir emojis a menos que solicitado

Emojis já usados no código de UI (✅ ⚡ 🚀 📅 …) — OK manter/usar.
Não adicionar emojis em novo código a menos que Perci peça.
Não usar emojis em respostas ao usuário no chat.

## 12. 📝 Não criar docs .md a menos que pedido

Este `docs/objetivos/` é a exceção: **ele pediu explicitamente**. Fora disso, não criar
`README extras`, `CONTRIBUTING.md`, `CHANGELOG.md`, etc.
