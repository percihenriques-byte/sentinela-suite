<#
    Travar-Extensao.ps1
    ------------------------------------------------------------------
    Trava a extensao do Sentinela para que a crianca NAO consiga
    desativa-la (nem em chrome://extensions). Usa a politica oficial
    do Windows "ExtensionInstallForcelist" (a mesma das escolas), para
    Microsoft Edge e Google Chrome.

    Como funciona:
      1. Empacota a extensao em um .crx assinado (chave .pem estavel).
      2. Descobre o ID da extensao (derivado da chave).
      3. Gera um update.xml local apontando para o .crx.
      4. Grava a politica de "instalacao forcada" no registro (HKLM).

    Extensoes forcadas por politica aparecem como "Instalada pela sua
    organizacao" e NAO podem ser removidas ou desativadas pelo usuario.

    Uso:
        .\Travar-Extensao.ps1              # trava (auto-eleva admin)
        .\Travar-Extensao.ps1 -Destravar   # remove a trava
        .\Travar-Extensao.ps1 -Simular     # testa sem tocar em nada real
    ------------------------------------------------------------------
#>
param([switch]$Destravar, [switch]$Simular)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Crx.ps1')

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

# eleva para admin (HKLM) quando for de verdade
if (-not $Simular) {
    $ident = [Security.Principal.WindowsIdentity]::GetCurrent()
    $princ = New-Object Security.Principal.WindowsPrincipal($ident)
    if (-not $princ.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $argsList = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`"")
        if ($Destravar) { $argsList += '-Destravar' }
        Start-Process powershell.exe -Verb RunAs -ArgumentList $argsList
        exit
    }
}

# ramos de registro (reais ou de teste, em simulacao)
if ($Simular) {
    $roots = @(
        @{ Nome='Edge';   Path='HKCU:\Software\SentinelaTeste\Microsoft\Edge' },
        @{ Nome='Chrome'; Path='HKCU:\Software\SentinelaTeste\Google\Chrome' }
    )
} else {
    $roots = @(
        @{ Nome='Edge';   Path='HKLM:\SOFTWARE\Policies\Microsoft\Edge' },
        @{ Nome='Chrome'; Path='HKLM:\SOFTWARE\Policies\Google\Chrome' }
    )
}

function Get-ForceKey { param($root) return (Join-Path $root.Path 'ExtensionInstallForcelist') }

function Add-ForceListEntry {
    param([string]$ForceKey, [string]$Entrada)
    if (-not (Test-Path $ForceKey)) { New-Item -Path $ForceKey -Force | Out-Null }
    $idPart = $Entrada.Split(';')[0]
    $existente = $null; $max = 0
    foreach ($p in (Get-Item $ForceKey).Property) {
        $v = (Get-ItemProperty -Path $ForceKey -Name $p).$p
        if ($v -like "$idPart;*") { $existente = $p }
        if ($p -match '^\d+$' -and [int]$p -gt $max) { $max = [int]$p }
    }
    $nome = if ($existente) { $existente } else { [string]($max + 1) }
    New-ItemProperty -Path $ForceKey -Name $nome -Value $Entrada -PropertyType String -Force | Out-Null
    return $nome
}

function Remove-ForceListEntry {
    param([string]$ForceKey, [string]$Id)
    if (-not (Test-Path $ForceKey)) { return 0 }
    $n = 0
    foreach ($p in (Get-Item $ForceKey).Property) {
        $v = (Get-ItemProperty -Path $ForceKey -Name $p).$p
        if ($v -like "$Id;*") { Remove-ItemProperty -Path $ForceKey -Name $p -Force; $n++ }
    }
    return $n
}

# ------------------------------------------------------------------
$paths = Initialize-SentinelaStore
$extDir = Join-Path $paths.Base 'ext'
$idFile = Join-Path $extDir 'extension-id.txt'

if ($Destravar) {
    Write-Host ''
    Write-Host '  Removendo a trava da extensao...' -ForegroundColor Yellow
    $id = if (Test-Path $idFile) { (Get-Content $idFile -Raw).Trim() } else { $null }
    if (-not $id) { Write-Host '  Nenhum ID salvo; nada a remover.' -ForegroundColor DarkGray; return }
    foreach ($r in $roots) {
        $rem = Remove-ForceListEntry -ForceKey (Get-ForceKey $r) -Id $id
        Write-Host ("  {0}: removidas {1} entrada(s)." -f $r.Nome, $rem)
    }
    if (-not $Simular) {
        # para e remove o servidor local
        Unregister-ScheduledTask -TaskName 'Sentinela-Servidor' -Confirm:$false -ErrorAction SilentlyContinue
        Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*Sentinela-Servidor*' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    Write-SentinelaLog "Trava da extensao REMOVIDA (id $id)." 'ACAO'
    Write-Host '  Pronto. Reinicie o navegador.' -ForegroundColor Green
    return
}

Write-Host ''
Write-Host '  Travando a extensao do Sentinela...' -ForegroundColor Cyan

# 1) empacota
$fonteExt = Join-Path $PSScriptRoot 'extensao'
Write-Host '  [1/5] Empacotando a extensao (.crx)...'
$crx = Invoke-EmpacotarExtensao -PastaExtensao $fonteExt -PastaSaida $extDir
Write-Host ('        crx: ' + $crx) -ForegroundColor DarkGray

# 2) ID
Write-Host '  [2/5] Calculando o ID da extensao...'
$id = Get-CrxExtensionId -CrxPath $crx
$id | Set-Content -Path $idFile -Encoding ASCII
Write-Host ('        ID: ' + $id) -ForegroundColor Green

# 3) update.xml + servidor local (http 127.0.0.1)
Write-Host '  [3/5] Gerando update.xml (servidor local)...'
$PORTA = 48610
$codebase  = "http://127.0.0.1:$PORTA/sentinela.crx"
$updateUrl = "http://127.0.0.1:$PORTA/update.xml"
$updateXml = Join-Path $extDir 'update.xml'
(New-UpdateXml -ExtensionId $id -Codebase $codebase) | Set-Content -Path $updateXml -Encoding UTF8

# 4) servidor local (serve update.xml + .crx por 127.0.0.1; force-install em qualquer navegador)
Write-Host '  [4/5] Registrando o servidor local (127.0.0.1)...'
$servidor = Join-Path $PSScriptRoot 'Sentinela-Servidor.ps1'
if ($Simular) {
    Write-Host '        (simulacao) servidor NAO registrado.' -ForegroundColor DarkGray
} else {
    $act = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Porta {1}' -f $servidor, $PORTA)
    $trg = New-ScheduledTaskTrigger -AtStartup
    $prn = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName 'Sentinela-Servidor' -Action $act -Trigger $trg -Principal $prn -Settings $set `
        -Description 'Sentinela: serve a extensao localmente (127.0.0.1) para o force-install.' -Force | Out-Null
    Start-ScheduledTask -TaskName 'Sentinela-Servidor'
    Write-Host '        servidor local ativo e no boot.' -ForegroundColor Green
}

# 5) politica
Write-Host '  [5/5] Aplicando a politica de instalacao forcada...'
$entrada = "$id;$updateUrl"
foreach ($r in $roots) {
    $nome = Add-ForceListEntry -ForceKey (Get-ForceKey $r) -Entrada $entrada
    Write-Host ("        {0}: ForceList[{1}] = {2}" -f $r.Nome, $nome, $id) -ForegroundColor DarkGray
}
Write-SentinelaLog "Extensao TRAVADA por politica (id $id)." 'ACAO'

Write-Host ''
Write-Host '  ============================================' -ForegroundColor Green
Write-Host '     Extensao travada!' -ForegroundColor Green
Write-Host '  ============================================' -ForegroundColor Green
Write-Host ''
if ($Simular) {
    Write-Host '  (simulacao) politica gravada em HKCU\Software\SentinelaTeste (teste).' -ForegroundColor Yellow
} else {
    Write-Host '  Feche e reabra o Edge/Chrome. A extensao vai aparecer como' -ForegroundColor White
    Write-Host '  "Instalada pela sua organizacao" e NAO podera ser desativada.' -ForegroundColor White
    Write-Host '  Confira em: edge://policy  ou  chrome://policy' -ForegroundColor DarkGray
}
Write-Host ''
