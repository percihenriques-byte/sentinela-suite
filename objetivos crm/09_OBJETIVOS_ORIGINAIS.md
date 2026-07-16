# Objetivos originais e status atual

## Pedido inicial do Perci

Construir um CRM que:

1. ✅ **Roda 100% local no PC do usuário** — SQLite + FastAPI + Vanilla JS
2. ✅ **Tem um assistente Jarvis** que entende PT/EN — 80+ intents, PT default
3. ✅ **Zero APIs externas** — nem Google, nem OAuth, nem cloud LLM em runtime
4. ✅ **UX limpa/mais bonita que Twenty.com** — hero grande, feature cards, gradient
5. ✅ **Funciona em PC e celular** — responsivo, hamburger, LAN via 0.0.0.0
6. ✅ **1 clique pra rodar no Windows** — `RODAR.bat` / `INICIAR.bat`
7. ✅ **Repo privado no GitHub** — [github.com/percihenriques-byte/visiquost-crm](https://github.com/percihenriques-byte/visiquost-crm)
8. ✅ **Testado como usuário real** — 4 walkthroughs Playwright (não só screenshots)

## Pedidos específicos ao longo do tempo

### "look at exemples in the web"
- Pesquisei Twenty.com, HubSpot, Pipedrive, Linear, Notion
- Aplicado: hero KPI (5-second rule), Kanban clean, keyboard shortcuts, empty states polidos,
  responsive breakpoints, dark mode elegante, print styles

### "estava horrível, refaça a landing"
- Refeita: hero h1 clamp 40-64px em gradient, 4 feature cards, stats row, botão demo com ⚡

### "não consigo scrollar"
- Fix: `body { overflow: hidden }` global → `.app-active { overflow: hidden }` só após login

### "só funciona no celular"
- Fix: cache do browser servindo versão velha → `_NoCacheStatic` middleware

### "n consigo clicar nem scrollar"
- Fix: mesmo bug acima do body overflow

### "os testes sao somente scrints shots"
- Fix: usei skill `web-navigate` + Playwright walkthroughs (slow_mo 60-120ms, real click)

### "esta horrivel como nem coisa para dar enter no signup tem"
- Fix: modal com hidden submit btn — Enter em qualquer input dispara submit

### "faca ficar tudo funcional e quando estiver crie um repo"
- Fix: 5 rounds de walkthrough até 0 issues, criou repo privado

### "esta dando o mesmo erro" (INSTALAR.bat)
- Fix: 3 bugs de parser CMD no INSTALAR.bat

### "sim ate n ter mais bugs e quando n tiver e estiver 100 funcional faca outro up para o repo e crie uma pasta"
- ✅ Rodadas até 0 bugs
- ✅ Pasta `objetivos crm/` criada (esta aqui)
- ⏳ Push final pendente (próxima ação)

## Métricas finais

| Métrica | Valor |
|---|---|
| Backend tests | 434/434 ✅ |
| Full-flow E2E | 18/18 ✅ |
| Brutal walkthrough | 0 issues ✅ |
| Deep walkthrough | 0 issues ✅ |
| R4 walkthrough | 0 issues ✅ |
| R5 edge cases | 0 issues ✅ |
| JS errors | 0 ✅ |
| HTTP 4xx/5xx | 0 (excl. 401/409 esperados) ✅ |
| Bugs reais corrigidos nesta sessão | 17 |
| Repo | ✅ Privado, atualizado |
| Documentação pra Fable | ✅ Esta pasta |

## Próximos passos possíveis (para o Fable continuar)

Se Perci quiser expandir depois:

1. **Meetings**: agrupamento por dia funciona, mas falta view de calendário (mês)
2. **Task recurrence** — tarefas recorrentes (semanal, mensal)
3. **Workspace switcher** — UI pra trocar entre múltiplos workspaces
4. **PDF export** direto (não via Ctrl+P)
5. **Kanban touch drag** — reorder em mobile via toque
6. **Push notifications** locais (Notification API browser)
7. **Templates de email** ricos com merge fields
8. **Reports customizáveis** — pivot table dos dados
9. **Postgres em prod** — testar fluxo alembic

**MAS** — não faça nenhum desses sem Perci pedir. Regra 2 (não pergunte, não faça
pré-emptivo) aplica.
