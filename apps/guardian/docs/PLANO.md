# Roteiro de construção — Sentinela

Sessão contínua (~1h). Objetivo: sair do protótipo para um **produto final** com duas
entregas — demo web para o pitch + app Windows real que aplica a proteção.

## Entrega 1 — Demo web (pitch)
- [x] Corrigir encoding e refinar o protótipo original
- [x] Classificador por categorias (espelha o app real)
- [x] Chamada para ação apontando o app real
- [ ] Publicar como Artifact para link compartilhável

## Entrega 2 — App Windows real (o produto)
- [ ] Núcleo `Sentinela-Core.ps1`: aplicar/remover DNS de filtro + entradas hosts (com modo simulação seguro)
- [ ] Sistema de PIN (hash SHA-256, sem guardar o PIN em texto)
- [ ] Config em `%ProgramData%\Sentinela` com status
- [ ] Guardião (tarefa agendada) que reaplica a config se adulterada
- [ ] `Instalar-Sentinela.ps1` — instalador com elevação de admin, 1 clique
- [ ] `Desativar` protegido por PIN + desinstalador
- [ ] Painel do responsável (GUI Windows Forms simples)
- [ ] Harness de teste em modo simulação (NÃO alterar o DNS real da máquina de dev)

## Entrega 3 — Documentação
- [ ] Guia de instalação para leigos (passo a passo com prints em texto)
- [ ] Material de apresentação (problema, solução, mercado, diferencial)

## Decisões técnicas
- **DNS de filtro:** CleanBrowsing Family (`185.228.168.168` / `185.228.169.168`) —
  gratuito, força SafeSearch e bloqueia categorias adultas. Alternativa: OpenDNS FamilyShield.
- **hosts (reforço):** mapear domínios de busca para os hosts `forcesafesearch`/`restrict`.
- **Por que PowerShell:** já vem no Windows → instalação acessível, sem runtime extra.
- **Segurança honesta:** trava o caminho fácil (aba anônima, trocar navegador, mexer nas
  configs). Não pretende deter um adulto com VPN/outro SO.
