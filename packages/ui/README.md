# packages/ui — Design System Sentinela

Fonte **única** da identidade visual da suite. Quem quiser mudar cor, fonte,
raio ou sombra mexe **aqui** — em nenhum outro arquivo.

## Arquivo

- `sentinela-tokens.css` — variáveis CSS (`:root` + tema claro).

## Como é consumido

| App | Como carrega |
|---|---|
| CRM (`apps/crm/frontend`) | `<link rel="stylesheet" href="/ui/sentinela-tokens.css">` — o backend monta `packages/ui` em `/ui` (ver `apps/crm/backend/app/main.py`) |
| Painel do responsável | mesma folha, mesma rota |

`apps/crm/frontend/assets/app.css` **não define paleta**: só consome as
variáveis. Isso é o que permite trocar toda a identidade em um lugar só.

## Origem dos valores

Extraídos de `apps/guardian/demo/index.html`, a UX oficial do Sentinela:

| Token | Valor | Papel |
|---|---|---|
| `--sn-ink` | `#0b1220` | fundo mais profundo |
| `--sn-panel` | `#0d1a26` | cartão / painel |
| `--sn-well` | `#08131c` | campo / poço |
| `--sn-line` | `#1e3a44` | borda padrão |
| `--sn-teal` | `#2dd4bf` | ação primária |
| `--sn-mint` | `#7ff5e6` | hover / realce |
| `--sn-coral` | `#ff6b6b` | perigo / bloqueio |
| `--sn-amber` | `#f6b73c` | alerta / incógnito |

Os nomes genéricos (`--bg`, `--primary`, `--danger`…) continuam existindo como
apelidos, apontando para os tokens da marca. Foi assim que o re-skin do CRM
inteiro saiu sem alterar uma linha de layout.

## Fontes

As fontes oficiais são **Sora** (títulos) e **DM Sans** (texto). A suite roda
offline (regra: zero APIs externas), então **não há `@import` de CDN**: a pilha
usa a fonte se ela estiver instalada e cai para a nativa do sistema
(Segoe UI no Windows) se não estiver. A página pública de pitch
(`apps/guardian/demo/index.html`) é auto-contida e continua carregando as
fontes do Google — é a única superfície que faz isso, e por ser um site
público, não o app local.

## Exceção conhecida

`apps/guardian/demo/index.html` mantém a paleta inline em vez de importar esta
folha, porque precisa ser **um arquivo só** (é publicada avulsa como página de
pitch). Ao mudar um token aqui, confira se a demo precisa acompanhar.
