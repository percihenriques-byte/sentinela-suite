# ESPEC — Security Intelligence Engine ("Segurança")

Especificação técnica do módulo defensivo de detecção de ameaças e exposição de
dados da Sentinela Suite (Sentinela + VisiQuost). Escrita para a Claude Code
implementar sem precisar tomar decisões arquiteturais importantes: onde este
documento cala, vale o padrão já existente no monorepo.

**Codinome interno:** `secintel`. **Nome na UX:** "Segurança".

---

## 0. Missão e princípio fundamental

O módulo DETECTA, CORRELACIONA, ALERTA e AJUDA A REMEDIAR. Ele **nunca**:
tenta login em conta alguma, quebra senha, explora vulnerabilidade, contorna
autenticação, acessa sistema de terceiros, coleta dado privado sem autorização,
enumera pessoas, ou "revida" um suposto atacante. Todo comportamento ofensivo
está fora de escopo por construção — não existe código de ataque para
configurar errado.

**Tensão resolvida com o produto:** a Suite promete "Zero APIs externas".
O módulo Segurança mantém essa promessa **por padrão**: instala 100% offline e
todas as fontes externas nascem DESLIGADAS. Cada fonte é ligada uma a uma pelo
responsável, numa tela que mostra exatamente *o que sai da máquina* naquela
fonte (§10). Sem consentimento registrado, nenhum byte sai. O copy do README
muda junto com o M4: "Zero APIs externas por padrão; o módulo Segurança
consulta apenas as fontes que você ligar, uma a uma."

---

## 1. Arquitetura geral

Segue a anatomia existente do backend (`apps/crm/backend/app/`):

```
app/
  models/secintel.py               # tabelas (§3)
  schemas/secintel.py              # payloads Pydantic (§5)
  api/routes_secintel.py           # rotas /seguranca (§5)
  services/
    secintel_service.py            # CRUD de ativos, incidentes, achados
    secintel_regras.py             # regras de detecção/correlação (declarativas, §7-8)
    secintel_score.py              # scoring (§9)
    secintel_mascara.py            # masking/redaction central (§12)
    secintel_fontes/               # adapters de fontes externas (§10)
      __init__.py                  # registro + contrato do adapter
      fonte_hibp.py                # Have I Been Pwned (k-anonymity)
      fonte_github.py              # varredura de secrets em repos próprios
      fonte_ct.py                  # Certificate Transparency (crt.sh)
    secintel_secrets.py            # detectores de secret (regex+entropia, §11)
    secintel_scheduler.py          # laços de monitoramento (padrão retencao_scheduler, §6)
  alembic/versions/0006_secintel.py
frontend/assets/app.js             # nova seção "Segurança" (§14)
```

Fluxo de dados (pipeline da Fase 10):

```
coletar → normalizar (sec_evento) → correlacionar (regras) → classificar (score)
   → validar (loop de falso-positivo) → alertar (incidente/achado) → registrar
   (auditoria) → reavaliar (scheduler)
```

Dois planos separados:

* **Plano local (M2):** eventos do próprio app — auth do painel, lockout de
  PIN, token de ingestão, rate-limit, eventos de dispositivo do Sentinela.
  Funciona 100% offline. É a primeira entrega de valor.
* **Plano externo (M4+):** fontes de exposição/vazamento, cada uma atrás de
  consentimento explícito.

---

## 2. Limites de autorização (Fase 1)

Nenhum ativo é inventado; todo ativo é cadastrado pelo responsável e carrega
`nivel_autorizacao`:

| Nível | Significado | Como se obtém |
|---|---|---|
| `verificado` | posse comprovada | ver tabela abaixo |
| `declarado` | posse declarada, não comprovada | cadastro manual |

Verificação de posse por tipo:

| Tipo de ativo | Verificação |
|---|---|
| `email` | o e-mail de login do painel é auto-verificado; demais ficam `declarado` (o app é local e não envia e-mail) |
| `dominio` / `subdominio` | registro DNS TXT `sentinela-verify=<token>` consultado quando a fonte CT/DNS estiver ligada |
| `repo` | o token GitHub read-only do usuário lista o repo como próprio/colaborador → `verificado` |
| `dispositivo` | já pareado pelo token de ingestão do Sentinela → `verificado` |
| `username` / `conta_externa` | sempre `declarado` |

**Regra dura:** fontes externas declaram o nível mínimo que exigem. Consultas
que retornam *conteúdo* (ex.: código de repo) exigem `verificado`. Consultas
agregadas com k-anonymity (ex.: HIBP range) aceitam `declarado`. Ativos de
titular `crianca` são permitidos (é um app de controle parental) mas seguem as
mesmas regras — e NUNCA habilitam busca de pessoas: o módulo não tem, e não
terá, adapter de people-search.

---

## 3. Estrutura de dados (migration `0006_secintel`)

Convenções herdadas: SQLModel, `workspace_id` em tudo, campos sensíveis
cifrados com o Fernet de `core/crypto.py`, timestamps UTC.

```
sec_asset
  id, workspace_id (idx), tipo enum(email,dominio,subdominio,username,repo,
      dispositivo,api_endpoint,conta_externa),
  identificador_cifrado (Fernet), identificador_hash (sha256 hex, idx, dedupe),
  identificador_mascarado (para listagens; gerado por secintel_mascara),
  titular enum(responsavel,crianca,organizacao),
  nivel_autorizacao enum(verificado,declarado), verificado_em nullable,
  fonte_cadastro, ativo bool, criado_em, ultima_verificacao nullable

sec_fonte
  id, nome (unique: hibp, github_secrets, ct, eventos_locais),
  habilitada bool default FALSE, requer_nivel enum,
  descricao_egresso  # texto mostrado na UX: exatamente o que sai da máquina
  consentida_em nullable, consentida_por nullable (user id),
  ultima_consulta nullable, estado enum(ok,erro,rate_limited), erro_msg nullable

sec_evento                       # normalização p/ correlação; retenção 30 dias
  id, workspace_id (idx), origem enum(painel_auth,sentinela_pin,ingestao,
      rate_limit,dispositivo,extensao),
  tipo,                          # ex.: login_falha, login_ok, pin_falha, ...
  ts (idx), ip nullable, usuario nullable, dispositivo_id nullable,
  sessao nullable, endpoint nullable, atributos_json  # minimizado (§12)

sec_achado                       # finding de exposição; retenção 365 dias
  id, workspace_id (idx), asset_id FK, fonte,
  tipo_exposicao enum(email_em_vazamento,senha_comprometida,api_key,token,
      private_key,connection_string,secret_generico,documento_exposto,
      repositorio_com_secret,dado_pessoal_exposto),
  classificacao enum(CONFIRMED,LIKELY,POSSIBLE,FALSE_POSITIVE),
  confianca float 0..1, severidade enum(INFO,LOW,MEDIUM,HIGH,CRITICAL),
  indicador_mascarado,           # NUNCA o valor: §12
  evidencia_resumo,              # texto SEM segredo (arquivo, commit, fonte)
  fingerprint (unique por workspace, dedupe: sha256(fonte|asset|tipo|local)),
  descoberto_em, exposto_em_estimado nullable,
  status enum(novo,validado,falso_positivo,resolvido,mesclado),
  motivo_fp nullable, incidente_id FK nullable, criado_em, atualizado_em

sec_incidente                    # retenção: 180 dias após fechado
  id, workspace_id (idx), titulo, cenario,        # chave do threat model §13
  severidade enum, score int 0..100, confianca float,
  estado enum(detectado,triagem,contido,remediado,recuperado,fechado,
      falso_positivo),
  fingerprint (unique por workspace),   # dedupe: mesmo cenario+chave de correlação
  primeiro_visto, ultimo_visto, ocorrencias int default 1,
  resumo, recomendacoes_json     # lista de ações §11/§13, cada uma com feito bool

sec_incidente_item               # linha do tempo do incidente
  id, incidente_id FK (idx), ref_tipo enum(evento,achado,nota,transicao),
  ref_id nullable, nota nullable, ts

sec_auditoria                    # trilha de auditoria do próprio módulo
  id, workspace_id (idx), user_id, acao,   # ex.: fonte_habilitada, achado_visto,
  detalhe_json, ts                          #     fp_marcado, estado_alterado
```

Índices além dos marcados: `sec_evento(workspace_id, ts)`,
`sec_achado(workspace_id, status, severidade)`,
`sec_incidente(workspace_id, estado)`.

---

## 4. Serviços

* **secintel_service** — CRUD com escopo de workspace; transições de estado de
  incidente validadas (§11); dedupe por fingerprint: achado/incidente que já
  existe é ATUALIZADO (`ultimo_visto`, `ocorrencias += 1`, itens de linha do
  tempo), nunca duplicado.
* **secintel_regras** — regras declarativas (constantes Python testáveis) dos
  níveis EVENTO → INDICADOR → SUSPEITA → INCIDENTE (§7) e sequências de
  correlação (§8).
* **secintel_score** — função pura de scoring (§9); sem I/O.
* **secintel_mascara** — único ponto de masking/redaction (§12); qualquer
  string sensível passa por aqui antes de persistir/exibir/logar.
* **secintel_secrets** — detectores de secret (§11); função pura: recebe texto,
  devolve achados com classificação e valor JÁ mascarado + fingerprint.
* **secintel_fontes/** — um adapter por fonte, contrato único:
  `def consultar(assets: list[AssetCtx]) -> list[AchadoBruto]` + metadados
  (`NOME`, `REQUER_NIVEL`, `DESCRICAO_EGRESSO`, `INTERVALO_MIN_S`). O runner
  garante: fonte desligada nunca é chamada; erro de uma fonte não derruba o
  ciclo (best-effort, padrão dos schedulers existentes).

---

## 5. APIs (`/seguranca`, em `routes_secintel.py`)

Autenticação: `CurrentUser` + workspace, como as demais rotas. **Novidade
deliberada (fecha o débito B6 para este módulo):** todas as rotas exigem o
papel `responsavel` no workspace; visitante/membro comum recebe 403. A leitura
de achados sensíveis grava `sec_auditoria`.

| Rota | Método | Função |
|---|---|---|
| `/seguranca/visao-geral` | GET | score agregado, contadores por severidade, últimos incidentes/achados |
| `/seguranca/ativos` | GET/POST | listar/cadastrar ativos |
| `/seguranca/ativos/{id}` | PATCH/DELETE | editar/arquivar |
| `/seguranca/ativos/{id}/verificar` | POST | dispara verificação de posse (§2) |
| `/seguranca/achados` | GET | filtros: status, severidade, fonte, asset |
| `/seguranca/achados/{id}` | PATCH | marcar `falso_positivo` (motivo obrigatório, auditado) ou `resolvido` |
| `/seguranca/incidentes` | GET | listar por estado |
| `/seguranca/incidentes/{id}` | GET | detalhe + linha do tempo |
| `/seguranca/incidentes/{id}/estado` | PATCH | transição validada (§11) |
| `/seguranca/incidentes/{id}/recomendacoes/{n}` | PATCH | marcar ação como feita |
| `/seguranca/fontes` | GET | fontes, estado, consentimento, `descricao_egresso` |
| `/seguranca/fontes/{nome}` | PATCH | ligar/desligar (auditado; ligar registra consentida_em/por) |
| `/seguranca/varreduras/{tipo}` | POST | varredura manual (`exposicao`, `secrets`, `correlacao`); rate-limited pelo middleware existente |
| `/seguranca/auditoria` | GET | trilha de auditoria do módulo |

Todos os payloads em `schemas/secintel.py`; respostas de listagem paginadas no
padrão existente (`schemas/common.py`).

---

## 6. Workers (`secintel_scheduler.py`)

Mesmo padrão de `retencao_scheduler.py`: laço `asyncio` iniciado no lifespan,
best-effort (exceção é logada e engolida, nunca derruba a API).

| Laço | Intervalo | O que faz | Rede? |
|---|---|---|---|
| correlação | 5 min | roda regras §7-8 sobre `sec_evento` novos; cria/atualiza incidentes | não |
| exposição | 24 h | para cada fonte HABILITADA, chama o adapter respeitando `INTERVALO_MIN_S` e backoff exponencial em `rate_limited` | só fontes ligadas |
| higiene | 24 h | aplica retenções (§12), fecha incidentes `recuperado` há >30d, recalcula recência dos scores | não |

Dedupe em todos os laços via fingerprint (§3). Um "kill-switch": desabilitar a
fonte interrompe o uso já no próximo ciclo (o runner reconsulta `sec_fonte` a
cada execução, não cacheia consentimento).

---

## 7. Detecção de ataques (Fase 4) — plano local

Fontes de evento (todas já existem no app; onde faltar log estruturado,
adicioná-lo é parte do M2):

* `routes_auth` — login falho/ok (ip, usuário, user-agent) ⇒ `painel_auth`
* lockout de PIN do Sentinela (escada já persistida) ⇒ `sentinela_pin`
* token de ingestão inválido em `/sentinela/eventos` ⇒ `ingestao`
* hits do rate-limit do middleware ⇒ `rate_limit`
* eventos de dispositivo/extensão do Sentinela ⇒ `dispositivo`/`extensao`

Escada de gravidade — nunca pular degrau sem evidência (Fase 4):

| Nível | Definição | Exemplo |
|---|---|---|
| EVENTO | fato bruto normalizado | 1 login falho |
| INDICADOR | padrão local anômalo | ≥5 logins falhos do mesmo IP em 10 min |
| SUSPEITA | indicadores compostos | brute-force + login OK subsequente de IP novo |
| INCIDENTE | suspeita com evidência suficiente (§9) | suspeita + troca de credencial/token em ≤30 min |

Regras iniciais (em `secintel_regras.py`, cada uma com testes):

```
R1 brute_force:        ≥5 login_falha mesmo ip 10min           → INDICADOR
R2 spray:              ≥5 login_falha ips distintos mesmo user  → INDICADOR
R3 pin_probing:        ≥3 pin_falha em 15min                    → INDICADOR
R4 ingest_probing:     ≥5 token_invalido em 10min               → INDICADOR
R5 takeover_suspeito:  R1|R2 seguido de login_ok de ip inédito  → SUSPEITA
R6 takeover_provavel:  R5 + (troca de senha|PIN|rotação token)  → INCIDENTE HIGH
R7 sessao_anomala:     sessões simultâneas de ips distintos     → INDICADOR
R8 token_inesperado:   criação de token fora de sessão ativa    → SUSPEITA
```

---

## 8. Motor de correlação (Fase 5)

Nada é analisado isolado. Correlaciona por chaves `ip`, `usuario`,
`dispositivo_id`, `sessao`, `endpoint` em janela deslizante de **24 h** (a
janela de cada regra composta manda; 24 h é o teto de retenção quente).
Sequência conceitual de referência (deve ter teste dedicado):

```
muitas falhas de login + login OK inesperado + mudança de credencial
+ criação de token  ⇒  incidente com score MUITO maior que qualquer parte
```

Implementação: o laço de correlação materializa "indicadores" como achados
internos (fonte `eventos_locais`) e as regras compostas consomem indicadores +
eventos. O incidente resultante referencia todos os itens na linha do tempo
(`sec_incidente_item`), com fingerprint `sha256(cenario|usuario|janela-dia)` —
reincidência atualiza o incidente existente (Fase 10: nunca duplicar).

---

## 9. Scoring de risco (Fase 6)

Função pura em `secintel_score.py`:

```
score = round(100 · P · I · C · R)          # 0..100
  P  probabilidade   0.1 fraca | 0.5 média | 0.9 forte      (da regra/fonte)
  I  impacto do ativo (tabela abaixo, 0..1)
  C  confiança da evidência 0..1 (classificação: CONFIRMED=1.0, LIKELY=0.7,
     POSSIBLE=0.4; para incidentes, média ponderada dos itens)
  R  recência: 2^(-idade_dias/30)  (meia-vida 30 dias, piso 0.25)
correlação: +10 por chave de correlação distinta adicional (teto +30), somado
            após o produto, ainda limitado a 100
```

| Impacto (I) | Ativos |
|---|---|
| 1.0 | credencial/segredo ativo, dispositivo da criança, conta do responsável |
| 0.7 | repo, domínio, API endpoint |
| 0.4 | username, e-mail declarado |

Bandas: `0-9 INFO · 10-29 LOW · 30-54 MEDIUM · 55-79 HIGH · 80-100 CRITICAL`.

**Trava anti-alarmismo:** severidade CRITICAL exige `C ≥ 0.8` E classificação
CONFIRMED; caso contrário rebaixa para HIGH com nota automática na linha do
tempo ("rebaixado por confiança insuficiente").

---

## 10. Fontes de threat intelligence (Fases 2 e 7)

Todas nascem desligadas; ligar exige papel responsável e grava consentimento.
Cada adapter documenta `DESCRICAO_EGRESSO` — o texto exato mostrado na UX.

| Fonte | O que detecta | O que SAI da máquina | Nível exigido |
|---|---|---|---|
| `hibp` | e-mail em vazamento; senha comprometida (só indicação) | e-mail consultado à API oficial; senhas NUNCA: usa range k-anonymity (5 primeiros chars do SHA-1) | `declarado` |
| `github_secrets` | secrets em repos próprios (atual + histórico) | nome dos repos do próprio token; clone raso local para varredura | `verificado` |
| `ct` | subdomínios/certificados inesperados dos domínios próprios | nome do domínio consultado ao crt.sh | `verificado` |
| `eventos_locais` | ataques ao próprio app (§7) | nada — 100% local | — (sempre ligada) |

Sem web scraping, sem fontes pagas embutidas, sem people-search. Novas fontes
só entram cumprindo o contrato do adapter e esta tabela.

Registro de cada descoberta (Fase 7): vira `sec_achado` com todos os campos de
§3 — asset, tipo, fonte, `descoberto_em`, `exposto_em_estimado`, confiança,
severidade, status.

---

## 11. Detecção de secrets no GitHub (Fase 3) e resposta (Fase 9)

**Detectores** (`secintel_secrets.py`) — regex de prefixo conhecido + entropia
Shannon para o genérico:

| Detector | Padrão (resumo) | Classificação base |
|---|---|---|
| AWS key | `AKIA[0-9A-Z]{16}` | CONFIRMED |
| GitHub token | `gh[pousr]_[A-Za-z0-9]{36,}` | CONFIRMED |
| Stripe | `sk_live_[A-Za-z0-9]{20,}` | CONFIRMED |
| Slack | `xox[baprs]-...` | CONFIRMED |
| Private key | `-----BEGIN ... PRIVATE KEY-----` | CONFIRMED |
| JWT | `eyJ...` (3 blocos base64url) | LIKELY |
| Connection string | `scheme://user:pass@host` | LIKELY |
| Genérico | var com nome sugestivo (`secret`, `token`, `senha`...) = valor com entropia ≥ 4.0 e comprimento ≥ 20 | POSSIBLE |

**Loop de falso-positivo (Fase 8)** — antes de virar achado, cada candidato
responde: pertence ao ativo? evidência suficiente? é exemplo/doc (`EXAMPLE`,
`xxx`, `teste`, caminho `docs/`, `*.md`, fixture de teste)? é placeholder? é
chave revogada (verificável só se a fonte correspondente estiver ligada)? Cada
"sim" reduz `confianca` e pode reclassificar até FALSE_POSITIVE — que é
registrado com motivo, não descartado em silêncio, e nunca gera incidente.

**Masking obrigatório:** o relatório mostra `sk_live_••••••••••••9F3A`
(prefixo identificador + 4 finais); o banco guarda só o mascarado + o
fingerprint `sha256(valor)` truncado a 16 hex para dedupe. O valor completo
NÃO é persistido em lugar nenhum — nem no log (§12).

**Resposta a incidente (Fase 9)** — para HIGH/CRITICAL o incidente nasce com
`recomendacoes_json` preenchido pelo cenário (§13), separado em quatro blocos:
DETECÇÃO (o que foi visto), CONTENÇÃO (revogar token, encerrar sessões,
desabilitar conta, isolar dispositivo), REMEDIAÇÃO (rotacionar chave, trocar
senha, remover secret do histórico com aviso de que ele deve ser considerado
comprometido mesmo removido, corrigir config, ativar MFA), RECUPERAÇÃO
(preservar logs, revisar acessos, reverificar o ativo, acompanhar reincidência).
Transições de estado válidas:
`detectado → triagem → contido → remediado → recuperado → fechado`, com
desvio `→ falso_positivo` permitido a partir de detectado/triagem (auditado).

---

## 12. Privacidade e proteção do próprio módulo (Fases 11 e 12)

**Nunca persistir:** senha, token completo, chave privada, conteúdo de
arquivo/mensagem privada, dado pessoal desnecessário. `sec_evento.atributos_json`
é minimizado por allowlist de campos — nunca guarda payload bruto.

**Masking central:** toda string sensível passa por `secintel_mascara` antes de
persistir, exibir ou logar. Teste de propriedade: nenhum valor com formato de
secret aparece completo em NENHUMA resposta de API nem em log (§15).

**Sanitização de logs:** um `logging.Filter` global (registrado em
`core/logging.py`) redige padrões de secret (§11) de qualquer mensagem — o
módulo protege inclusive contra o próprio descuido.

**Retenções** (aplicadas pelo laço de higiene): `sec_evento` 30d ·
`sec_achado` 365d · incidentes 180d após fechados · auditoria 365d. Valores em
`Settings` (`config.py`), com piso documentado.

**Least privilege:** papel `responsavel` para tudo (§5); tokens externos
(GitHub) são read-only, cifrados com Fernet via `external_account` existente, e
usados exclusivamente pelos adapters.

**Auto-auditoria (Fase 12), executável:** um teste dedicado varre respostas
das rotas e logs gerados nos testes procurando padrões de secret completos —
se achar, a suíte falha. Riscos do próprio módulo e mitigação:

| Risco | Mitigação |
|---|---|
| dashboard vazar segredo | masking central + teste de propriedade |
| log com secret | logging.Filter + teste |
| permissão excessiva | papel responsável + auditoria de leitura |
| abuso p/ vigiar terceiros | verificação de posse (§2), sem people-search, fontes com nível mínimo |
| armazenamento inadequado | Fernet nos identificadores, fingerprint em vez de valor |
| API insegura | mesmas guardas do app (JWT, rate-limit, loopback onde couber) |

---

## 13. Modelo de ameaças (Fase 13)

Cada cenário define: detecção → evidência → confiança → alerta → contenção →
remediação → recuperação. As recomendações abaixo alimentam
`recomendacoes_json` (§11).

| Cenário (`cenario`) | Detecção | Contenção → Remediação → Recuperação |
|---|---|---|
| `account_takeover` | R5/R6 (§7) | encerrar sessões → trocar senha + MFA → revisar acessos |
| `credential_leak` | hibp: senha comprometida | forçar troca → MFA → monitorar reincidência |
| `api_key_exposure` | github_secrets / achado manual | revogar chave → rotacionar + remover do repo → auditar uso da chave |
| `session_hijacking` | R7 sessões simultâneas anômalas | encerrar sessões → trocar senha → revisar dispositivos |
| `brute_force` | R1/R2/R3/R4 | rate-limit já ativo; bloquear IP local → revisar senha → acompanhar |
| `phishing_indicator` | ct: certificado/subdomínio símile inesperado | alertar responsável → denunciar domínio → monitorar |
| `malicious_repo_change` | github_secrets: secret NOVO em commit recente | reverter/remover → rotacionar → revisar quem commitou |
| `insider_indicator` | eventos: elevação/exportação fora do padrão | revisar permissões → limitar papel → auditar trilha |
| `compromised_device` | eventos do dispositivo Sentinela fora do padrão (ex.: proteção desativada sem PIN) | isolar/reativar proteção → varredura AV externa (recomendação) → reparear |
| `data_exposure` | documento/dado público indevido (fontes) | remover exposição → avaliar impacto → notificar afetado |

---

## 14. UX (Fase 14)

Integra à SPA existente (`app.js`), dentro da seção **Sentinela** do menu (a
marca de proteção da casa), entrada **"Segurança"**, atalho de teclado `g`
(livre no mapa atual). Paleta, tipografia, tom de voz e PT-BR do Sentinela.
Telas:

1. **Visão geral** — score do workspace (0-100 com banda colorida), contadores
   por severidade, fontes ligadas/desligadas, últimos 5 incidentes.
2. **Ameaças** — incidentes por estado (lista com filtros, padrão das listas
   do app), badge de severidade e confiança.
3. **Exposições** — achados com filtros; ação rápida "marcar falso positivo"
   (pede motivo) e "resolvido".
4. **Incidentes (detalhe)** — linha do tempo, recomendações com checkbox por
   ação (PATCH §5), botão de transição de estado.
5. **Ativos** — cadastro com wizard curto por tipo, selo `verificado`/`declarado`
   e botão "verificar posse".
6. **Fontes** — cada fonte com toggle, `descricao_egresso` SEMPRE visível
   antes de ligar, data/autor do consentimento.

**Todo alerta responde, nesta ordem e com estes rótulos:** O que aconteceu? ·
Quando? · Qual ativo? · Gravidade? · Confiança? · **O que fazer agora?** (CTA
para as recomendações). Sem jargão técnico no primeiro nível; detalhes técnicos
ficam num expansor "ver evidência".

---

## 15. Testes

No padrão da suíte existente (`apps/crm/backend/tests/`, roda no CI job `api`):

* `test_secintel_mascara.py` — masking: propriedade "nenhum valor completo em
  saída alguma"; casos por detector.
* `test_secintel_secrets.py` — **corpus rotulado** de detecção (no espírito do
  corpus do classificador): fixtures com secrets FALSOS de formato real
  (gerados, claramente marcados) + armadilhas de falso positivo (docs,
  exemplos, placeholders, alta entropia legítima como hash de lockfile).
  Meta: 100% no corpus; corpus versionado e crescente.
* `test_secintel_regras.py` — cada regra R1-R8 com sequência sintética que
  dispara e sequência vizinha que NÃO dispara; a sequência de referência da
  Fase 5 elevando o score.
* `test_secintel_score.py` — bandas, trava de CRITICAL, decaimento, teto de
  correlação.
* `test_secintel_api.py` — permissões (membro comum = 403), transições de
  estado inválidas = 422, FP exige motivo, auditoria gravada.
* `test_secintel_consentimento.py` — fonte desligada NUNCA faz chamada: os
  testes usam um transporte de rede que **falha o teste** se qualquer request
  sair sem consentimento registrado.
* `test_secintel_privacidade.py` — a auto-auditoria executável (§12).
* Migration `0006` entra no ciclo up/down/up existente do CI.

---

## 16. Critérios de aceitação

1. Instalação limpa funciona 100% offline; nenhuma chamada externa sem fonte
   habilitada (provado por teste de consentimento).
2. Nenhum segredo completo em banco, API, UX ou log (provado por teste de
   propriedade).
3. Corpus de secrets: 100%; regras R1-R8: todas com teste positivo e negativo.
4. Incidente nunca duplica: reincidência atualiza (`ocorrencias`, `ultimo_visto`).
5. CRITICAL só com CONFIRMED + confiança ≥ 0.8.
6. Membro sem papel `responsavel` não acessa nada de `/seguranca`.
7. Falso positivo exige motivo e fica auditado; não gera incidente.
8. Todo alerta na UX responde às 6 perguntas da Fase 14.
9. Suíte inteira verde no CI (jobs `api` e `migrations`).
10. `Verificar-Tudo.ps1` segue verde sem etapa nova obrigatória (os testes
    entram pelo pytest já existente).

## 17. Plano de implementação incremental

| Marco | Entrega | Aceitação |
|---|---|---|
| M0 | migration 0006, modelos, papel `responsavel`, auditoria base | ciclo up/down/up verde |
| M1 | ativos + verificação de posse + tela Ativos | criar/verificar/arquivar via UX |
| M2 | eventos locais + regras R1-R8 + correlação + incidentes (SEM rede) | sequência da Fase 5 gera 1 incidente HIGH com linha do tempo |
| M3 | scoring + visão geral + telas Ameaças/Incidentes | critérios 5 e 8 |
| M4 | fontes externas opt-in (hibp, github_secrets, ct) + tela Fontes | critérios 1 e 2; corpus de secrets 100% |
| M5 | schedulers de monitoramento contínuo + dedupe + FP loop completo | critérios 4 e 7 |
| M6 | auto-auditoria executável, retenções, docs + ajuste do copy do README | critérios 2 e 9-10 |

Cada marco: teste verde + commit próprio, no fluxo de trabalho já usado no
projeto (uma etapa por vez, com verificação).

---

## 18. Autorrevisão da especificação (Fase 15)

Lacunas encontradas ao revisar e como foram resolvidas no próprio texto:

1. *"Verificação de e-mail exige envio de e-mail, mas o app não tem SMTP"* →
   resolvido com os níveis `verificado`/`declarado` e fontes declarando nível
   mínimo (§2).
2. *"Threat intel contradiz o 'Zero APIs externas'"* → resolvido com opt-in por
   fonte, `descricao_egresso` na UX, teste de consentimento e mudança de copy
   no M6 (§0, §10, §15).
3. *"Como impedir uso do módulo para vigiar terceiros"* → posse verificada,
   nível mínimo por fonte, sem people-search por construção, ativos de criança
   limitados ao contexto parental já existente no produto (§2, §12).
4. *"Incidente duplicado a cada ciclo"* → fingerprint + update-em-vez-de-criar
   em achados E incidentes, com teste (§3, §6, critério 4).
5. *"O próprio módulo pode vazar segredo por log"* → masking central +
   `logging.Filter` + auto-auditoria executável que falha a suíte (§12, §15).
6. *"Score vira alarme falso"* → trava de CRITICAL, rebaixamento com nota,
   escada EVENTO→INCIDENTE sem pular degrau (§7, §9).
7. Reexecutada a revisão após os ajustes: as perguntas da Fase 15 (detecta
   vazamento? credencial exposta? sinais de ataque? reduz FP? protege os
   próprios dados? privacidade? resposta a incidentes? UX consistente?) têm
   todas resposta afirmativa apontando para a seção correspondente. Cenário
   relevante não contemplado: monitoramento de e-mail de phishing recebido —
   fica registrado como evolução futura (exigiria acesso a caixa postal, fora
   do escopo local-first atual).

**Condição de parada atendida:** arquitetura ✓ modelo de ameaças ✓
monitoramento de exposição ✓ secrets ✓ ataques ✓ correlação ✓ risco ✓
incidentes ✓ resposta ✓ privacidade ✓ UX ✓ falsos positivos ✓ limites de
autorização ✓ revisão final sem lacuna crítica ✓
