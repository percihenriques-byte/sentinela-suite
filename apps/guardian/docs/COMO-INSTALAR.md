# 📥 Como instalar o Sentinela (passo a passo)

Guia para qualquer pessoa, sem conhecimento técnico. Leva menos de 2 minutos.

> **O que você vai precisar:** um computador com Windows 10 ou 11 e a senha de
> administrador (a mesma que o Windows pede quando você instala um programa novo).

---

## Passo 1 — Baixe a pasta do Sentinela

Copie a pasta `sentinela` para o computador da criança (pode ser no Desktop, por
exemplo). Dentro dela existe a subpasta `app`.

## Passo 2 — Abra a pasta `app` e dê dois cliques em **INSTALAR.bat**

![duplo clique no INSTALAR.bat]

Vai abrir uma telinha preta escrito *"Iniciando o instalador do Sentinela..."*.

## Passo 3 — Clique em **SIM** quando o Windows perguntar

O Windows vai mostrar uma janela azul perguntando se você permite que o programa
faça alterações no computador. **Isso é normal e necessário** — é o que permite o
Sentinela proteger a rede toda, e não só um navegador.

> 👉 Clique em **SIM**. (Se aparecer "Usuário/Senha", digite a senha de administrador.)

## Passo 4 — Crie o PIN do responsável

O instalador vai pedir para você digitar um **PIN de 4 a 8 números** (duas vezes,
para confirmar). Esse é o **seu** número secreto.

> ⚠️ **Guarde bem o PIN.** É só com ele que dá para desligar o Sentinela depois.
> A criança **não** deve saber esse número.

## Passo 5 — Pronto! 🎉

O instalador mostra **"Sentinela instalado e ATIVO!"**. A partir de agora:

- O Google, o Bing e o YouTube só funcionam no **modo seguro**.
- Isso vale em **qualquer navegador** (Chrome, Edge, Firefox...).
- Vale **até no modo anônimo/incógnito**.
- Se a criança tentar mexer nas configurações para desligar, o **Guardião** religa
  sozinho em até 1 minuto.

---

## Como testar se está funcionando

1. Abra o Google em uma **aba anônima**.
2. Tente buscar algo impróprio.
3. Você vai ver a mensagem do Google dizendo que o **SafeSearch está ativado pelo
   administrador da rede** e não pode ser desligado. ✅

## Como ver o painel (para o responsável)

No Menu Iniciar, procure por **"Painel do Sentinela"**. Lá você consegue:

- ver se a proteção está ligada;
- ligar/desligar (o desligar pede o PIN);
- trocar o PIN;
- ver o registro de tentativas.

## Como desligar de vez (só o responsável)

Na pasta `app`, dê dois cliques em **Desinstalar-Sentinela.ps1** (ou use o botão
Desligar no painel). Vai pedir o **PIN**. Sem ele, nada é alterado.

---

## Dúvidas comuns

**"A internet parou de funcionar."**
Não para — só a busca vai para o modo seguro. Se algum site específico não abrir,
abra o Painel e confira o status; em último caso, desligue com o PIN e nos avise.

**"Esqueci o PIN."**
Por segurança, não existe "PIN mestre". Se você tem acesso de administrador do
Windows, é possível remover manualmente (apagar a pasta `C:\ProgramData\Sentinela`
e a tarefa agendada `Sentinela-Guardiao` como administrador). Numa versão futura
haverá recuperação por e-mail do responsável.

**"Funciona em celular?"**
Esta versão é para Windows. A mesma ideia (DNS de filtro) funciona em celular
configurando o DNS da rede Wi-Fi — está no roteiro do projeto.

---

## Para quem é técnico

O `INSTALAR.bat` chama `Instalar-Sentinela.ps1`, que:
1. se auto-eleva a administrador;
2. copia os scripts para `C:\ProgramData\Sentinela\app`;
3. grava o hash do PIN (SHA-256 + salt) em `config.json`;
4. registra a tarefa agendada `Sentinela-Guardiao` (SYSTEM, a cada 1 min + no boot);
5. aplica o DNS de filtro (CleanBrowsing Family) e o bloco `hosts` de modo seguro;
6. cria o atalho do Painel no Menu Iniciar.

Para experimentar **sem alterar nada** na máquina, rode em modo simulação:

```powershell
.\Instalar-Sentinela.ps1 -Simular
.\app\Testes\Executar-Testes.ps1
```
