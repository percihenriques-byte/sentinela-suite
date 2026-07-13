<#
    Sentinela-Pin.ps1
    ------------------------------------------------------------------
    Trava por PIN do responsavel. O PIN NUNCA e guardado em texto:
    guardamos apenas um hash SHA-256 com "sal" aleatorio. Sem o PIN
    correto, nao e possivel desativar o Sentinela.

    Requer Sentinela-Core.ps1 dot-sourceado antes (usa Get-SentinelaPaths).
    ------------------------------------------------------------------
#>

function Get-SentinelaPinHash {
    param([Parameter(Mandatory)][string]$Pin, [Parameter(Mandatory)][string]$Salt)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Salt + ':' + $Pin)
        $hash  = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash) -replace '-', '').ToLower()
    } finally {
        $sha.Dispose()
    }
}

function New-SentinelaSalt {
    $bytes = New-Object 'System.Byte[]' 16
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
}

function Get-SentinelaConfig {
    $p = Get-SentinelaPaths
    if (Test-Path $p.Config) {
        try { return Get-Content $p.Config -Raw | ConvertFrom-Json } catch { }
    }
    return $null
}

function Save-SentinelaConfig {
    param([Parameter(Mandatory)]$Config)
    $p = Initialize-SentinelaStore
    $Config | ConvertTo-Json -Depth 5 | Set-Content -Path $p.Config -Encoding UTF8
}

function Test-SentinelaPinConfigured {
    $cfg = Get-SentinelaConfig
    return ($null -ne $cfg -and $cfg.PSObject.Properties.Name -contains 'pinHash' -and $cfg.pinHash)
}

function Set-SentinelaPin {
    param([Parameter(Mandatory)][string]$Pin)
    if ($Pin -notmatch '^\d{4,8}$') {
        throw 'O PIN deve ter de 4 a 8 digitos numericos.'
    }
    $salt = New-SentinelaSalt
    $hash = Get-SentinelaPinHash -Pin $Pin -Salt $salt

    $cfg = Get-SentinelaConfig
    if ($null -eq $cfg) { $cfg = [pscustomobject]@{} }
    $cfg | Add-Member -NotePropertyName pinSalt   -NotePropertyValue $salt -Force
    $cfg | Add-Member -NotePropertyName pinHash   -NotePropertyValue $hash -Force
    $cfg | Add-Member -NotePropertyName criadoEm  -NotePropertyValue (Get-Date).ToString('o') -Force
    Save-SentinelaConfig -Config $cfg
    Write-SentinelaLog 'PIN do responsavel definido/atualizado.' 'ACAO'
}

function Test-SentinelaPin {
    param([Parameter(Mandatory)][string]$Pin)
    $cfg = Get-SentinelaConfig
    if ($null -eq $cfg -or -not (Test-SentinelaPinConfigured)) { return $false }
    $tentativa = Get-SentinelaPinHash -Pin $Pin -Salt $cfg.pinSalt
    $ok = ($tentativa -eq $cfg.pinHash)
    if ($ok) {
        Write-SentinelaLog 'PIN correto — acesso do responsavel liberado.' 'INFO'
    } else {
        Write-SentinelaLog 'PIN incorreto — tentativa de desativar registrada.' 'WARN'
    }
    return $ok
}

<#
  Pede o PIN no console de forma segura (nao ecoa na tela) e retorna
  $true se conferir. Usado pelos scripts de linha de comando.
#>
function Request-SentinelaPin {
    param([string]$Prompt = 'Digite o PIN do responsavel', [int]$MaxTentativas = 3)
    if (-not (Test-SentinelaPinConfigured)) {
        Write-Host 'Nenhum PIN configurado. Configure com Set-SentinelaPin.' -ForegroundColor Yellow
        return $false
    }
    for ($i = 1; $i -le $MaxTentativas; $i++) {
        $sec = Read-Host -AsSecureString "$Prompt ($i/$MaxTentativas)"
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        try {
            $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        if (Test-SentinelaPin -Pin $plain) { return $true }
        Write-Host 'PIN incorreto.' -ForegroundColor Red
    }
    return $false
}
