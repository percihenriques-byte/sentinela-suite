<#
    Ativar-Sentinela.ps1
    Liga a protecao. Em modo real precisa de administrador (altera DNS/hosts).
    Uso:
        .\Ativar-Sentinela.ps1                # modo real
        .\Ativar-Sentinela.ps1 -Simular       # nao altera nada real (dev)
#>
param([switch]$Simular)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Pin.ps1')

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

# checa administrador quando for aplicar de verdade
if (-not $Simular -and $env:SENTINELA_SIMULAR -ne '1') {
    $ident = [Security.Principal.WindowsIdentity]::GetCurrent()
    $princ = New-Object Security.Principal.WindowsPrincipal($ident)
    if (-not $princ.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host 'Este comando precisa ser executado como Administrador.' -ForegroundColor Red
        exit 1
    }
}

Enable-Sentinela -Simular:$Simular
Write-Host ''
Write-Host '  Sentinela ATIVADO.' -ForegroundColor Green
Get-SentinelaStatus | Format-List
