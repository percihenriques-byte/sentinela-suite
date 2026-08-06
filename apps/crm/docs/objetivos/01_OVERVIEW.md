# VisiQuost — Overview

## O que é

CRM (Customer Relationship Management) desktop-local para pequenas empresas e freelancers
brasileiros que **não querem** enviar dados de clientes/negócios para a nuvem.

Rodando em `localhost:8000`, com hamburger + hero + kanban + kpis + assistente JARVIS.

## Público-alvo

- **Consultor/freelancer autônomo** que gerencia ~30-300 clientes e não quer pagar mensalidade
  de Hubspot/Pipedrive
- **Pequena empresa** (2-20 pessoas) que precisa de multi-workspace e importar/exportar dados
- **Advogado, contador, corretor** — profissões liberais que lidam com dados sensíveis (LGPD)
  e não podem/querem terceirizar armazenamento

## O que diferencia

| Feature | VisiQuost | Hubspot/Pipedrive | Twenty.com (OSS competitor) |
|---|---|---|---|
| Runs on your PC | ✅ (SQLite) | ❌ (cloud) | ❌ (cloud/self-host) |
| Zero cloud APIs | ✅ | ❌ | ❌ (uses S3, etc.) |
| Native PT/EN | ✅ | ✅ | Parcial |
| Free forever | ✅ | ❌ | ✅ |
| AI Assistant local | ✅ (Jarvis) | Cloud LLM | ❌ |
| Setup < 5min | ✅ (`INICIAR.bat`) | Signup online | Docker-compose |
| Encryption at rest | ✅ (Fernet) | ✅ | ? |
| Import/export JSON | ✅ portable | Parcial | Parcial |

## O que faz (visão do usuário)

### Núcleo CRM
- **Contatos** — nome, email, telefone, empresa, cargo, notas, timeline de atividades
- **Empresas** — domínio, indústria, tamanho, receita anual
- **Oportunidades** — valor, probabilidade, estágio, data prevista de fechamento
- **Leads** — separado de contatos (funil ainda não convertido), com scoring automático
- **Pipelines** — múltiplos, com estágios customizáveis (WIP limits opcionais)
- **Tarefas** — prioridade, due date, marcar como concluída, filtros
- **Reuniões** — agenda, agrupamento por Hoje/Amanhã/Semana/Depois, badge "AGORA"
- **Notas** — anexadas a qualquer entidade, timeline
- **Atividades** — feed append-only (created/updated/deleted, calls, emails, stage_moved…)
- **Tags** — livre, cor-codificadas

### Assistente JARVIS
- **80+ intents** em PT/EN — greeting, pipeline health, briefing, top oportunidades,
  criar contato/empresa/oportunidade/tarefa, mover stage, log call/email, marcar tarefa
  como feita, buscar em tudo, forecast, undo/redo, memory ("me chame de Alex"), etc.
- **Detecção de idioma automática** com default PT-BR
- **Tom configurável** (formal/casual/técnico/conciso)
- **Undo** — desfaz last update OU last create (delete soft)
- **100% local** — motor de intent com regex + fuzzy + slot filling, sem LLM cloud

### UX
- **Kanban visual** com drag-and-drop + keyboard reorder (aria-grabbed)
- **Cmd-K palette** — busca global + comandos rápidos
- **Row navigation** com ↑↓ + Enter
- **Recently viewed** persistido em localStorage
- **Bulk actions** — selecionar múltiplos, exportar CSV, apagar em lote
- **Dark mode** com toggle
- **Print styles** — Ctrl+P vira relatório limpo
- **Responsivo** — mobile hamburger, sidebar deslizante, layout adapta
- **A11y** — role=dialog, aria-modal, focus restore, focus-visible, reduced-motion
- **Landing hero** — h1 gigante gradient, feature cards, stats, botão "⚡ Entrar como demo"

### Automações
- **Lead scoring** — regras com 14 operadores (email_domain, source, engagement…),
  auto-recompute
- **Workflow engine** — triggers em Activity kind + condições, actions (create_task,
  add_note, move_opportunity, set_lead_status), audit trail em WorkflowRun

### Deploy
- `INICIAR.bat` — 1 clique, sobe uvicorn em 0.0.0.0:8000, mostra URL do PC + IP LAN
  para celular acessar via Wi-Fi
- `INSTALAR.bat` — auto-detecta Python (winget instala se falta), cria venv, aplica
  migrations, popula demo, invoca INICIAR
- `RODAR.bat` — atalho: instala se preciso, senão só inicia
