<#
    Sentinela-Crx.ps1
    ------------------------------------------------------------------
    Ajuda a empacotar a extensao e a descobrir o ID dela.

    O travamento da extensao (force-install) exige:
      - um .crx assinado (o navegador gera, com uma chave .pem estavel);
      - o ID da extensao, derivado da chave publica.

    Este arquivo tem as funcoes de baixo nivel (parse do CRX3 e calculo
    do ID). O Travar-Extensao.ps1 usa tudo isso.
    ------------------------------------------------------------------
#>

# le um varint (protobuf) a partir de $Pos (por referencia)
function Read-Varint {
    param([byte[]]$Bytes, [ref]$Pos)
    $shift = 0; [uint64]$res = 0
    while ($true) {
        $x = $Bytes[$Pos.Value]; $Pos.Value++
        $res = $res -bor ([uint64]($x -band 0x7F) -shl $shift)
        if (($x -band 0x80) -eq 0) { break }
        $shift += 7
    }
    return $res
}

# mapeia um hash SHA-256 para o ID de extensao (16 bytes -> 32 chars a-p)
function ConvertTo-CrxIdFromHash {
    param([byte[]]$Hash)
    $hex = ($Hash[0..15] | ForEach-Object { '{0:x2}' -f $_ }) -join ''
    return (-join ($hex.ToCharArray() | ForEach-Object { [char]([int][char]'a' + [Convert]::ToInt32($_, 16)) }))
}

# extrai a chave publica (SubjectPublicKeyInfo DER) do cabecalho CRX3
function Get-CrxPublicKey {
    param([Parameter(Mandatory)][string]$CrxPath)
    $bytes = [System.IO.File]::ReadAllBytes($CrxPath)
    if ($bytes.Length -lt 16) { throw "CRX invalido/curto demais: $CrxPath" }
    $magic = [System.Text.Encoding]::ASCII.GetString($bytes[0..3])
    if ($magic -ne 'Cr24') { throw "Arquivo nao e um CRX valido: $CrxPath" }
    $hlen = [BitConverter]::ToUInt32($bytes, 8)
    if ($hlen -le 0 -or (12 + $hlen) -gt $bytes.Length) {
        throw "CRX corrompido: cabecalho ($hlen bytes) maior que o arquivo ($($bytes.Length) bytes)."
    }
    $hdr = New-Object 'byte[]' $hlen
    [Array]::Copy($bytes, 12, $hdr, 0, $hlen)

    $pos = 0; $pubkey = $null
    while ($pos -lt $hdr.Length) {
        $tag = [int](Read-Varint $hdr ([ref]$pos)); $field = $tag -shr 3; $wt = $tag -band 7
        if ($wt -eq 2) {
            $len = [int](Read-Varint $hdr ([ref]$pos))
            $data = New-Object 'byte[]' $len; [Array]::Copy($hdr, $pos, $data, 0, $len); $pos += $len
            if ($field -eq 2 -and -not $pubkey) {
                $p2 = 0
                $t2 = [int](Read-Varint $data ([ref]$p2)); $f2 = $t2 -shr 3; $w2 = $t2 -band 7
                if ($f2 -eq 1 -and $w2 -eq 2) {
                    $l2 = [int](Read-Varint $data ([ref]$p2))
                    $pubkey = New-Object 'byte[]' $l2; [Array]::Copy($data, $p2, $pubkey, 0, $l2)
                }
            }
        } elseif ($wt -eq 0) {
            [void](Read-Varint $hdr ([ref]$pos))
        } else { break }
    }
    if (-not $pubkey) { throw "Nao foi possivel ler a chave publica do CRX." }
    return $pubkey
}

# ID completo da extensao a partir do .crx
function Get-CrxExtensionId {
    param([Parameter(Mandatory)][string]$CrxPath)
    $pub = Get-CrxPublicKey -CrxPath $CrxPath
    $sha = [System.Security.Cryptography.SHA256]::Create().ComputeHash($pub)
    return (ConvertTo-CrxIdFromHash -Hash $sha)
}

# localiza um navegador para empacotar (Edge preferido, depois Chrome)
function Get-NavegadorParaEmpacotar {
    $cands = @(
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    )
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
    return $null
}

# empacota a pasta da extensao em .crx (gera/reusa a chave .pem para ID estavel)
# retorna o caminho do .crx
function Invoke-EmpacotarExtensao {
    param(
        [Parameter(Mandatory)][string]$PastaExtensao,
        [Parameter(Mandatory)][string]$PastaSaida,
        [string]$Navegador
    )
    if (-not $Navegador) { $Navegador = Get-NavegadorParaEmpacotar }
    if (-not $Navegador) { throw "Nenhum navegador (Edge/Chrome) encontrado para empacotar a extensao." }
    if (-not (Test-Path $PastaSaida)) { New-Item -ItemType Directory -Path $PastaSaida -Force | Out-Null }

    $src = Join-Path $PastaSaida 'src'
    if (Test-Path $src) { Remove-Item $src -Recurse -Force }
    Copy-Item $PastaExtensao $src -Recurse

    $pemEstavel = Join-Path $PastaSaida 'sentinela.pem'
    $crxGerado  = Join-Path $PastaSaida 'src.crx'
    $pemGerado  = Join-Path $PastaSaida 'src.pem'
    Remove-Item $crxGerado, $pemGerado -Force -ErrorAction SilentlyContinue

    if (Test-Path $pemEstavel) {
        & $Navegador "--pack-extension=$src" "--pack-extension-key=$pemEstavel" 2>$null | Out-Null
    } else {
        & $Navegador "--pack-extension=$src" 2>$null | Out-Null
    }
    # espera o arquivo aparecer
    $tentativas = 0
    while (-not (Test-Path $crxGerado) -and $tentativas -lt 20) { Start-Sleep -Milliseconds 300; $tentativas++ }
    if (-not (Test-Path $crxGerado)) { throw "O navegador nao gerou o .crx (tempo esgotado)." }

    if ((Test-Path $pemGerado) -and -not (Test-Path $pemEstavel)) { Move-Item $pemGerado $pemEstavel -Force }

    $crxFinal = Join-Path $PastaSaida 'sentinela.crx'
    Move-Item $crxGerado $crxFinal -Force
    return $crxFinal
}

# gera o update.xml (manifesto Omaha). Use -Codebase para uma URL http
# local (recomendado) ou -CrxPath para um caminho file:// (fallback).
function New-UpdateXml {
    param(
        [Parameter(Mandatory)][string]$ExtensionId,
        [string]$CrxPath,
        [string]$Codebase,
        [string]$Versao = '1.0.0'
    )
    if (-not $Codebase) {
        if (-not $CrxPath) { throw 'Informe -Codebase (URL) ou -CrxPath (arquivo).' }
        $Codebase = 'file:///' + ($CrxPath -replace '\\', '/')
    }
    # escapa para atributo XML (BUG-14): & < > ' "
    $esc = { param($s) ([string]$s).Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;').Replace("'",'&apos;').Replace('"','&quot;') }
    $eId  = & $esc $ExtensionId
    $eCb  = & $esc $Codebase
    $eVer = & $esc $Versao
    return @"
<?xml version='1.0' encoding='UTF-8'?>
<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>
  <app appid='$eId'>
    <updatecheck codebase='$eCb' version='$eVer' />
  </app>
</gupdate>
"@
}
