<#
    Instalar-Sentinela.ps1
    ------------------------------------------------------------------
    Instalador de 1 clique. O que faz:
      1. Pede acesso de Administrador (se auto-eleva).
      2. Copia os arquivos para  %ProgramData%\Sentinela\app
      3. Pede ao responsavel para criar um PIN.
      4. Registra o "Guardiao" como tarefa agendada (roda a cada 1 min
         e na inicializacao, como SYSTEM) para reaplicar a protecao.
      5. Liga a protecao.
      6. Cria atalhos no Menu Iniciar (Painel e Status).

    Uso normal:  duplo clique no INSTALAR.bat
    Uso dev...:  .\Instalar-Sentinela.ps1 -Simular   (nao altera nada real)
    ------------------------------------------------------------------
#>
param([switch]$Simular)

$ErrorActionPreference = 'Stop'
$TASK_NAME = 'Sentinela-Guardiao'

# ---- auto-elevacao (so em modo real) --------------------------------
if (-not $Simular) {
    $ident = [Security.Principal.WindowsIdentity]::GetCurrent()
    $princ = New-Object Security.Principal.WindowsPrincipal($ident)
    if (-not $princ.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host 'Solicitando permissao de Administrador...' -ForegroundColor Yellow
        Start-Process powershell.exe -Verb RunAs -ArgumentList @(
            '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`""
        )
        exit
    }
}

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

# ---- destino --------------------------------------------------------
$baseData = if ($Simular) { Join-Path $env:TEMP 'SentinelaSim' } else { Join-Path $env:ProgramData 'Sentinela' }
$destApp  = Join-Path $baseData 'app'

Write-Host ''
Write-Host '  ============================================' -ForegroundColor Cyan
Write-Host '     SENTINELA - Instalacao' -ForegroundColor Cyan
Write-Host '     busca segura a prova de incognito' -ForegroundColor DarkCyan
Write-Host '  ============================================' -ForegroundColor Cyan
Write-Host ''

# ---- 1. copiar arquivos --------------------------------------------
Write-Host '  [1/5] Copiando arquivos...' -ForegroundColor White
New-Item -ItemType Directory -Path $destApp -Force | Out-Null
$fonte = $PSScriptRoot
Get-ChildItem -Path $fonte -Recurse -Include '*.ps1' | ForEach-Object {
    $rel = $_.FullName.Substring($fonte.Length).TrimStart('\')
    $tgt = Join-Path $destApp $rel
    New-Item -ItemType Directory -Path (Split-Path $tgt -Parent) -Force | Out-Null
    Copy-Item $_.FullName $tgt -Force
}
Write-Host '        arquivos copiados para ' -NoNewline; Write-Host $destApp -ForegroundColor DarkGray

# ---- carregar modulos do destino -----------------------------------
. (Join-Path $destApp 'Sentinela-Core.ps1')
. (Join-Path $destApp 'Sentinela-Pin.ps1')

# ---- 2. definir PIN -------------------------------------------------
Write-Host ''
Write-Host '  [2/5] Crie o PIN do responsavel (4 a 8 digitos).' -ForegroundColor White
Write-Host '        Guarde bem: sem ele nao e possivel desligar o Sentinela.' -ForegroundColor DarkGray
if ($Simular) {
    Set-SentinelaPin -Pin '2026'
    Write-Host '        (simulacao) PIN definido como 2026' -ForegroundColor DarkGray
} else {
    while ($true) {
        $p1 = Read-Host -AsSecureString '        Novo PIN'
        $p2 = Read-Host -AsSecureString '        Repita o PIN'
        $b1 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($p1)
        $b2 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($p2)
        try {
            $s1 = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b1)
            $s2 = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b2)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b1)
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b2)
        }
        if ($s1 -ne $s2) { Write-Host '        Os PINs nao conferem. Tente de novo.' -ForegroundColor Red; continue }
        try { Set-SentinelaPin -Pin $s1; break }
        catch { Write-Host ('        ' + $_.Exception.Message) -ForegroundColor Red }
    }
    Write-Host '        PIN definido com sucesso.' -ForegroundColor Green
}

# ---- 3. registrar o guardiao (tarefa agendada) ----------------------
Write-Host ''
Write-Host '  [3/5] Registrando o Guardiao (protecao anti-adulteracao)...' -ForegroundColor White
$guardiao = Join-Path $destApp 'Sentinela-Guardiao.ps1'
if ($Simular) {
    Write-Host '        (simulacao) tarefa agendada NAO registrada.' -ForegroundColor DarkGray
} else {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $guardiao)
    $trigger1 = New-ScheduledTaskTrigger -AtStartup
    $trigger2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 9999)
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $TASK_NAME -Action $action -Trigger @($trigger1,$trigger2) `
        -Principal $principal -Settings $settings -Description 'Sentinela: reaplica a protecao de busca segura.' -Force | Out-Null
    Write-Host '        Guardiao registrado (roda a cada 1 min e na inicializacao).' -ForegroundColor Green
}

# ---- 4. ligar a protecao -------------------------------------------
Write-Host ''
Write-Host '  [4/5] Ligando a protecao...' -ForegroundColor White
Enable-Sentinela -Simular:$Simular
Write-Host '        Protecao ATIVA.' -ForegroundColor Green

# ---- 5. atalhos -----------------------------------------------------
Write-Host ''
Write-Host '  [5/5] Criando atalhos no Menu Iniciar...' -ForegroundColor White
if ($Simular) {
    Write-Host '        (simulacao) atalhos NAO criados.' -ForegroundColor DarkGray
} else {
    try {
        $startMenu = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\Sentinela'
        New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
        $ws = New-Object -ComObject WScript.Shell
        $sc = $ws.CreateShortcut((Join-Path $startMenu 'Painel do Sentinela.lnk'))
        $sc.TargetPath = 'powershell.exe'
        $sc.Arguments = ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $destApp 'gui\Sentinela-Painel.ps1'))
        $sc.IconLocation = 'shell32.dll,48'
        $sc.Save()
        Write-Host '        Atalho "Painel do Sentinela" criado.' -ForegroundColor Green
    } catch {
        Write-Host ('        Aviso: nao foi possivel criar atalho: ' + $_.Exception.Message) -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host '  ============================================' -ForegroundColor Green
Write-Host '     Sentinela instalado e ATIVO!' -ForegroundColor Green
Write-Host '  ============================================' -ForegroundColor Green
Write-Host ''
Get-SentinelaStatus | Format-List
if (-not $Simular) {
    Write-Host '  Dica: teste abrir o Google numa aba anonima e buscar algo -' -ForegroundColor DarkGray
    Write-Host '        o modo seguro estara ligado e nao podera ser desativado.' -ForegroundColor DarkGray
    Write-Host ''
    Read-Host '  Pressione ENTER para fechar'
}
