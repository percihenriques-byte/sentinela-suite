<#
    Sentinela-Servidor.ps1
    ------------------------------------------------------------------
    Mini-servidor LOCAL (so 127.0.0.1) que serve o update.xml e o .crx
    da extensao por HTTP. Isso garante o "force-install" em qualquer
    versao de navegador (algumas recusam file:// para instalar).

    - NAO acessa a internet. Escuta apenas em 127.0.0.1 (loopback).
    - Servido a partir de  <base>\ext  (update.xml e sentinela.crx).

    Roda em segundo plano (registrado como tarefa agendada pelo
    Travar-Extensao.ps1). Tambem da para rodar a mao para testar.

    Uso:
        .\Sentinela-Servidor.ps1                 # roda ate ser fechado
        .\Sentinela-Servidor.ps1 -Porta 48610
        .\Sentinela-Servidor.ps1 -Simular        # usa a pasta de teste
    ------------------------------------------------------------------
#>
param([int]$Porta = 48610, [switch]$Simular, [switch]$PermitirShutdown)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

$paths  = Get-SentinelaPaths
$extDir = Join-Path $paths.Base 'ext'

function Send-Arquivo {
    param($Resposta, [string]$Arquivo, [string]$Tipo)
    if (Test-Path $Arquivo) {
        $bytes = [System.IO.File]::ReadAllBytes($Arquivo)
        $Resposta.ContentType = $Tipo
        $Resposta.ContentLength64 = $bytes.Length
        $Resposta.OutputStream.Write($bytes, 0, $bytes.Length)
    } else {
        $Resposta.StatusCode = 404
    }
    $Resposta.OutputStream.Close()
}

$listener = New-Object System.Net.HttpListener
$prefixo = "http://127.0.0.1:$Porta/"
$listener.Prefixes.Add($prefixo)
try {
    $listener.Start()
} catch {
    Write-SentinelaLog ("Servidor: falha ao iniciar em $prefixo - " + $_.Exception.Message) 'ERRO'
    throw
}
Write-SentinelaLog "Servidor local ativo em $prefixo (extensao)" 'INFO'

try {
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()
        $req = $ctx.Request
        $res = $ctx.Response
        # so aceita loopback (defesa extra)
        if (-not $req.IsLocal) { $res.StatusCode = 403; $res.OutputStream.Close(); continue }
        $rota = $req.Url.AbsolutePath.TrimStart('/').ToLowerInvariant()
        switch ($rota) {
            'update.xml'    { Send-Arquivo $res (Join-Path $extDir 'update.xml')    'text/xml' }
            'sentinela.crx' { Send-Arquivo $res (Join-Path $extDir 'sentinela.crx') 'application/x-chrome-extension' }
            'ping'          { $res.ContentType='text/plain'; $b=[Text.Encoding]::ASCII.GetBytes('ok'); $res.OutputStream.Write($b,0,$b.Length); $res.OutputStream.Close() }
            'shutdown'      {
                                if ($PermitirShutdown) {
                                    $res.StatusCode = 200; $res.OutputStream.Close(); $listener.Stop()
                                } else { $res.StatusCode = 404; $res.OutputStream.Close() }
                            }
            default         { $res.StatusCode = 404; $res.OutputStream.Close() }
        }
    }
} finally {
    $listener.Stop()
}
