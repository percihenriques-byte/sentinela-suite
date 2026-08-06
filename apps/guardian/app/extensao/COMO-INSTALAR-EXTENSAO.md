# 🧩 Extensão do Sentinela — filtro por IA + supervisão

A extensão é a **segunda camada** do Sentinela. Enquanto o DNS força o modo seguro do
Google/YouTube, a extensão:

- **bloqueia na hora** buscas de temas que o modo seguro não cobre (apostas, autolesão,
  violência, "burlar filtro"...), usando a **IA local** (sem internet);
- **analisa o TEXTO da página** que a criança está vendo (não só a busca) e bloqueia a
  página se o conteúdo for impróprio;
- **analisa as IMAGENS** da página e borra as suspeitas (heurístico local; dá para plugar
  um modelo treinado — veja `modelo/COMO-ADICIONAR-MODELO.md`);
- **registra o que a criança busca/vê** para o responsável revisar (supervisão);
- deixa você **escolher os temas**, adicionar **palavras próprias** e **ligar/desligar a
  análise de imagens**.

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
2. Descobre o **ID** da extensão e gera um `update.xml`.
3. Sobe um **servidor local** (`127.0.0.1:48610`) que serve o `update.xml` e o `.crx`
   — registrado como tarefa no boot, roda escondido, **sem internet**. Isso faz o
   force-install funcionar em **qualquer versão** de navegador.
4. Grava a política oficial do Windows **`ExtensionInstallForcelist`** para **Edge e
   Chrome** — a mesma que as escolas usam.

Depois, feche e reabra o navegador: a extensão aparece como **"Instalada pela sua
organização"** e o botão de desativar/remover **some**. Confira em `edge://policy` ou
`chrome://policy`. Para reverter: `Travar-Extensao.ps1 -Destravar` (remove a política e o
servidor).

## Cobertura de navegação sem recarregar (SPA)

A extensão roda em **todo** o domínio do YouTube e **reavalia a busca a cada mudança de
URL** — via os eventos `popstate`, `hashchange`, `yt-navigate-finish` e um verificador
periódico. Assim, mesmo quando o YouTube (ou o DuckDuckGo) troca os resultados **sem
recarregar a página**, o Sentinela reclassifica e bloqueia na hora. O DNS continua
garantindo o modo seguro por baixo, como terceira rede de proteção.
