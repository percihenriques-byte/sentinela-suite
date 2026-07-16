# Objetivos CRM — VisiQuost (para Claude Fable)

Olá Fable. Isto é o contexto completo do VisiQuost, um CRM local com assistente JARVIS que
Perci (percihenriques-byte no GitHub) e eu (Claude Opus 4.7) construímos em várias sessões
autônomas.

## Como ler esta pasta

Ordem sugerida:

1. **[00_LEIA_PRIMEIRO.md](00_LEIA_PRIMEIRO.md)** — este arquivo. Panorama e como navegar.
2. **[01_OVERVIEW.md](01_OVERVIEW.md)** — o que o produto é, para quem, o que o diferencia.
3. **[02_ARCHITECTURE.md](02_ARCHITECTURE.md)** — stack, camadas, decisões técnicas.
4. **[03_FEATURES_DONE.md](03_FEATURES_DONE.md)** — lista completa do que já foi construído.
5. **[04_TESTS_PROOF.md](04_TESTS_PROOF.md)** — evidência de que está funcional (434 pytest, 4 walkthroughs Playwright).
6. **[05_HARD_RULES.md](05_HARD_RULES.md)** — as regras inegociáveis do Perci. **LEIA ANTES DE PROPOR MUDANÇAS.**
7. **[06_KNOWN_LIMITATIONS.md](06_KNOWN_LIMITATIONS.md)** — o que ainda não foi feito ou é limitação consciente.
8. **[07_HOW_TO_RUN.md](07_HOW_TO_RUN.md)** — como abrir o projeto na sua máquina em 1 clique.
9. **[08_SESSION_HISTORY.md](08_SESSION_HISTORY.md)** — resumo cronológico dos loops de trabalho.

## Estado atual (2026-07-16)

- **Repo privado**: https://github.com/percihenriques-byte/visiquost-crm
- **Backend**: 434/434 pytest passando · FastAPI + SQLModel + SQLite
- **Frontend**: Vanilla JS SPA · ~5000 linhas · zero dependências CDN
- **Walkthroughs (Playwright, "as user"):** 4 suites (full_flow / brutal / deeper / r4 / r5 edge) — 0 issues, 0 JS errors, 0 HTTP 4xx/5xx
- **Deploy**: 100% local — `INICIAR.bat` (1 clique no Windows). Nada de cloud.

## Missão do produto (em uma frase)

> Um CRM que funciona no PC do usuário, sem cloud, sem OAuth, sem mensalidade, com um
> assistente Jarvis que entende português e inglês e executa 80+ intenções (criar contato,
> agendar reunião, resumir pipeline, mover oportunidade, etc.) 100% offline.

## Se você (Fable) for continuar o trabalho

- **Antes de qualquer mudança**, leia [05_HARD_RULES.md](05_HARD_RULES.md). O Perci se irrita
  quando as regras são quebradas (aconteceu comigo várias vezes).
- Não pergunte "posso fazer X?" — execute e mostre o resultado. Perci reforçou essa regra 5+
  vezes.
- Se algo parecer precisar de API externa (fetch, OAuth, cloud LLM), **PARE e pergunte**.
  Zero APIs externas é a linha vermelha do produto.
- Use `Skill web-navigate` para testar como usuário real (Playwright com slow_mo),
  não só screenshots. Perci já reclamou de screenshot-only tests.
- Cada mudança deve rodar `pytest -q` + o brutal walkthrough antes de comitar.

Boa sorte. — Opus 4.7
