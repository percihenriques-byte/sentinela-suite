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
Para **travar** (a criança não consegue remover), o Windows tem uma política oficial —
`ExtensionInstallForcelist`. O instalador do Sentinela pode aplicá-la numa versão
publicada da extensão (quando ela estiver na Chrome Web Store). É o mesmo mecanismo que
escolas usam. *(No roadmap: publicar a extensão e ligar o force-install pelo instalador.)*

## Limitação honesta

Sites que trocam os resultados **sem recarregar a página** (rolar o YouTube, por exemplo)
podem escapar de uma verificação pontual. O bloqueio pega a **busca** (quando a página de
resultados carrega), que é o momento principal. A cobertura de navegação interna (SPA)
está no roadmap. Mesmo assim, o **DNS já garante o modo seguro** por baixo.
