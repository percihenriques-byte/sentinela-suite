# 🧩 Extensão do Sentinela — filtro por IA + supervisão

A extensão é a **segunda camada** do Sentinela. Enquanto o DNS força o modo seguro do
Google/YouTube, a extensão:

- **bloqueia na hora** buscas de temas que o modo seguro não cobre (apostas, autolesão,
  violência, "burlar filtro"...), usando a **IA local** (sem internet);
- **registra o que a criança busca** para o responsável revisar (supervisão);
- deixa você **escolher os temas** e adicionar **palavras próprias**.

## Instalar (Chrome ou Edge)

1. Abra `chrome://extensions` (ou `edge://extensions`).
2. Ligue o **Modo do desenvolvedor** (canto superior).
3. Clique em **Carregar sem compactação** e escolha a pasta `app/extensao`.
4. Pronto — o ícone 🛡️ aparece na barra. Clique nele para ver a **supervisão** e
   **configurar os temas**.

## Como o responsável usa

- Clique no ícone 🛡️ → aba **Supervisão**: veja todas as buscas, com as bloqueadas em
  destaque, o total e o tema mais barrado. Dá para **exportar** o registro.
- Aba **Configurar temas**: ligue/desligue temas, ative o **modo rígido**, e escreva
  **palavras que você quer bloquear** (uma por linha).

## Tornar a extensão impossível de desativar (recomendado)

Por padrão, uma extensão carregada assim pode ser desligada em `chrome://extensions`.
Para **travar** (a criança não consegue remover nem desativar), dê dois cliques em:

```
app/TRAVAR-EXTENSAO.bat      (clique SIM no aviso de Administrador)
```

O que ele faz, automaticamente (via `Travar-Extensao.ps1`):

1. Empacota a extensão num `.crx` assinado com uma chave estável.
2. Descobre o **ID** da extensão e gera um `update.xml` local.
3. Grava a política oficial do Windows **`ExtensionInstallForcelist`** para **Edge e
   Chrome** — a mesma que as escolas usam.

Depois, feche e reabra o navegador: a extensão aparece como **"Instalada pela sua
organização"** e o botão de desativar/remover **some**. Confira em `edge://policy` ou
`chrome://policy`. Para reverter: `Travar-Extensao.ps1 -Destravar`.

## Limitações honestas

- **Hospedagem local:** o travamento aponta para o `.crx` por `file:///`. Em algumas
  versões recentes do navegador, o force-install exige `http`. Se em `edge://policy` a
  extensão não aparecer como forçada, a solução é servir o `update.xml`/`.crx` por um
  mini-servidor **local** (`127.0.0.1`) — está no roadmap e não usa internet.
- **Navegação sem recarregar (SPA):** rolar resultados do YouTube sem recarregar pode
  escapar de uma verificação pontual. O bloqueio pega a **busca** (quando a página de
  resultados carrega), que é o momento principal. Mesmo assim, o **DNS já garante o modo
  seguro** por baixo.
