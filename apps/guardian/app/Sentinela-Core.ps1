<#
    Sentinela-Core.ps1
    ------------------------------------------------------------------
    Nucleo do Sentinela: aplica e remove a protecao de busca segura na
    camada de rede do Windows (DNS de filtro + arquivo hosts).

    Este arquivo so define funcoes (dot-source). Nao faz nada sozinho.
    Os scripts de acao (Ativar / Desativar / Guardiao / Instalar) usam
    estas funcoes.

    MODO SIMULACAO (seguro para desenvolvimento):
      Defina  $env:SENTINELA_SIMULAR = "1"  antes de dot-sourcear, ou
      passe  -Simular  nas funcoes que alteram o sistema. Nesse modo,
      nada real e alterado: o DNS nao muda e o hosts usado e um arquivo
      de teste em %ProgramData%\Sentinela\sandbox\hosts.
    ------------------------------------------------------------------
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------
# Constantes de configuracao
# ---------------------------------------------------------------------

# DNS de filtro familiar (CleanBrowsing Family). Gratuito. Forca o
# SafeSearch do Google/Bing/YouTube e bloqueia categorias adultas.
$script:SENTINELA_DNS = @('185.228.168.168', '185.228.169.168')

# IPs oficiais de "modo seguro forcado" (usados no arquivo hosts como
# reforco, caso alguem troque o DNS manualmente).
#   forcesafesearch.google.com   -> 216.239.38.120
#   restrict.youtube.com (Estrito) -> 216.239.38.120
$script:SAFE_IP = '216.239.38.120'

# Dominios de busca/video que serao apontados para o modo seguro.
$script:SAFE_HOSTS = @(
    'www.google.com','google.com','www.google.com.br','google.com.br',
    'www.bing.com','bing.com',
    'www.youtube.com','youtube.com','m.youtube.com',
    'youtubei.googleapis.com','youtube.googleapis.com','www.youtube-nocookie.com',
    'duckduckgo.com','www.duckduckgo.com'
)

$script:HOSTS_BEGIN = '# >>> SENTINELA (nao edite esta secao) >>>'
$script:HOSTS_END   = '# <<< SENTINELA <<<'

# Politicas de navegador que AUTO-CONFIGURAM o SafeSearch de forma robusta.
# O hosts/DNS sozinho pode ser furado pelo DNS-over-HTTPS (DoH) do navegador;
# estas politicas forcam o SafeSearch no proprio navegador e desligam o DoH,
# fazendo o filtro voltar a valer. Aplicadas em HKLM (real) ou num ramo de
# teste em HKCU (simulacao). Valem para Edge e Chrome (base Chromium).
$script:SAFE_POLICIES = @(
    @{ Nome='ForceGoogleSafeSearch';   Tipo='DWord';  Valor=1 },      # Google sempre em SafeSearch
    @{ Nome='ForceYouTubeRestrict';    Tipo='DWord';  Valor=2 },      # YouTube em modo restrito ESTRITO
    @{ Nome='DnsOverHttpsMode';        Tipo='String'; Valor='off' },  # sem DoH: o hosts/DNS de filtro volta a valer
    @{ Nome='BuiltInDnsClientEnabled'; Tipo='DWord';  Valor=0 }       # usa o resolvedor do SO (respeita o hosts)
)

# ---------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------
function Get-SentinelaPaths {
    $simular = ($env:SENTINELA_SIMULAR -eq '1')
    $baseData = if ($simular) {
        Join-Path $env:TEMP 'SentinelaSim'
    } else {
        Join-Path $env:ProgramData 'Sentinela'
    }
    $sandboxHosts = Join-Path $baseData 'sandbox\hosts'
    $realHosts    = Join-Path $env:WinDir 'System32\drivers\etc\hosts'

    [pscustomobject]@{
        Simular       = $simular
        Base          = $baseData
        Config        = Join-Path $baseData 'config.json'
        State         = Join-Path $baseData 'state.json'
        Log           = Join-Path $baseData 'sentinela.log'
        HostsBackup   = Join-Path $baseData 'hosts.backup'
        HostsFile     = if ($simular) { $sandboxHosts } else { $realHosts }
        SandboxHosts  = $sandboxHosts
    }
}

function Initialize-SentinelaStore {
    $p = Get-SentinelaPaths
    if (-not (Test-Path $p.Base)) { New-Item -ItemType Directory -Path $p.Base -Force | Out-Null }
    if ($p.Simular) {
        $sandDir = Split-Path $p.SandboxHosts -Parent
        if (-not (Test-Path $sandDir)) { New-Item -ItemType Directory -Path $sandDir -Force | Out-Null }
        if (-not (Test-Path $p.SandboxHosts)) {
            "# hosts de teste do Sentinela (modo simulacao)`n127.0.0.1 localhost`n" |
                Set-Content -Path $p.SandboxHosts -Encoding ASCII
        }
    }
    return $p
}

# ---------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------
function Write-SentinelaLog {
    param([string]$Message, [ValidateSet('INFO','WARN','ERRO','ACAO')][string]$Level = 'INFO')
    $p = Get-SentinelaPaths
    if (-not (Test-Path $p.Base)) { New-Item -ItemType Directory -Path $p.Base -Force | Out-Null }
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    "$ts [$Level] $Message" | Add-Content -Path $p.Log -Encoding UTF8
}

# ---------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------
function Get-SentinelaState {
    $p = Get-SentinelaPaths
    if (Test-Path $p.State) {
        try { return Get-Content $p.State -Raw | ConvertFrom-Json } catch { }
    }
    return [pscustomobject]@{ ativo = $false; desde = $null }
}

function Set-SentinelaState {
    param([bool]$Ativo)
    $p = Initialize-SentinelaStore
    $obj = [pscustomobject]@{
        ativo = $Ativo
        desde = (Get-Date).ToString('o')
    }
    $obj | ConvertTo-Json | Set-Content -Path $p.State -Encoding UTF8
}

# ---------------------------------------------------------------------
# Arquivo hosts
# ---------------------------------------------------------------------
function Get-SentinelaHostsBlock {
    $lines = @($script:HOSTS_BEGIN)
    foreach ($h in $script:SAFE_HOSTS) {
        $lines += ('{0} {1}' -f $script:SAFE_IP, $h)
    }
    $lines += $script:HOSTS_END
    return ($lines -join "`r`n")
}

function Remove-HostsBlockText {
    param([string]$Content)
    if (-not $Content) { return '' }
    # remove qualquer bloco existente entre os marcadores
    $pattern = [regex]::Escape($script:HOSTS_BEGIN) + '.*?' + [regex]::Escape($script:HOSTS_END)
    $clean = [regex]::Replace($Content, $pattern, '', 'Singleline')
    return ($clean.TrimEnd() )
}

function Set-SentinelaHosts {
    param([switch]$Simular)
    $p = Initialize-SentinelaStore
    $hostsFile = $p.HostsFile
    $current = if (Test-Path $hostsFile) { Get-Content $hostsFile -Raw } else { '' }
    $clean = Remove-HostsBlockText -Content $current

    # backup uma vez, do hosts LIMPO (sem bloco SENTINELA), para ser um
    # ponto de restauracao fiel mesmo se ja havia bloco de execucao anterior.
    if (-not (Test-Path $p.HostsBackup)) {
        $clean | Set-Content -Path $p.HostsBackup -Encoding ASCII
    }
    $block = Get-SentinelaHostsBlock
    $new = ($clean.TrimEnd() + "`r`n`r`n" + $block + "`r`n")
    $new | Set-Content -Path $hostsFile -Encoding ASCII
    Write-SentinelaLog "Bloco hosts aplicado ($($script:SAFE_HOSTS.Count) dominios) em $hostsFile" 'ACAO'
}

function Clear-SentinelaHosts {
    $p = Get-SentinelaPaths
    $hostsFile = $p.HostsFile
    if (-not (Test-Path $hostsFile)) { return }
    $current = Get-Content $hostsFile -Raw
    $clean = Remove-HostsBlockText -Content $current
    ($clean.TrimEnd() + "`r`n") | Set-Content -Path $hostsFile -Encoding ASCII
    Write-SentinelaLog "Bloco hosts removido de $hostsFile" 'ACAO'
}

function Test-SentinelaHostsApplied {
    # Valida o CONTEUDO, nao so o marcador: se qualquer linha esperada
    # (IP + dominio) faltar, considera NAO aplicado -> o guardiao reaplica.
    # Isso impede burlar mantendo o marcador e apagando os IPs.
    $p = Get-SentinelaPaths
    if (-not (Test-Path $p.HostsFile)) { return $false }
    $c = Get-Content $p.HostsFile -Raw
    if (-not $c) { return $false }
    if (-not $c.Contains($script:HOSTS_BEGIN)) { return $false }
    foreach ($h in $script:SAFE_HOSTS) {
        $linha = ('{0} {1}' -f $script:SAFE_IP, $h)
        if (-not $c.Contains($linha)) { return $false }
    }
    return $true
}

# ---------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------
function Get-SentinelaAdapters {
    # adaptadores ativos com endereco IP (nao virtuais/loopback)
    try {
        return Get-NetAdapter -Physical -ErrorAction Stop |
            Where-Object { $_.Status -eq 'Up' }
    } catch {
        # fallback para maquinas sem o modulo NetAdapter
        return @()
    }
}

function Set-SentinelaDns {
    param([switch]$Simular)
    if ($Simular -or (Get-SentinelaPaths).Simular) {
        Write-SentinelaLog "[SIMULACAO] DNS de filtro NAO aplicado (dev). Aplicaria: $($script:SENTINELA_DNS -join ', ')" 'ACAO'
        return
    }
    $adapters = Get-SentinelaAdapters
    foreach ($a in $adapters) {
        try {
            Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses $script:SENTINELA_DNS -ErrorAction Stop
            Write-SentinelaLog "DNS de filtro aplicado em '$($a.Name)' (ifIndex $($a.ifIndex))" 'ACAO'
        } catch {
            Write-SentinelaLog "Falha ao aplicar DNS em '$($a.Name)': $($_.Exception.Message)" 'ERRO'
        }
    }
    Clear-DnsClientCache -ErrorAction SilentlyContinue
}

function Restore-SentinelaDns {
    param([switch]$Simular)
    if ($Simular -or (Get-SentinelaPaths).Simular) {
        Write-SentinelaLog "[SIMULACAO] DNS NAO restaurado (dev)." 'ACAO'
        return
    }
    $adapters = Get-SentinelaAdapters
    foreach ($a in $adapters) {
        try {
            # volta para DNS automatico (DHCP)
            Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses -ErrorAction Stop
            Write-SentinelaLog "DNS restaurado (automatico) em '$($a.Name)'" 'ACAO'
        } catch {
            Write-SentinelaLog "Falha ao restaurar DNS em '$($a.Name)': $($_.Exception.Message)" 'ERRO'
        }
    }
    Clear-DnsClientCache -ErrorAction SilentlyContinue
}

function Test-SentinelaDnsApplied {
    if ((Get-SentinelaPaths).Simular) { return $true }
    $adapters = Get-SentinelaAdapters
    foreach ($a in $adapters) {
        try {
            $servers = (Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction Stop).ServerAddresses
            foreach ($dns in $script:SENTINELA_DNS) {
                if ($servers -notcontains $dns) { return $false }
            }
        } catch { return $false }
    }
    return ($adapters.Count -gt 0)
}

# ---------------------------------------------------------------------
# SafeSearch por politica de navegador (Edge + Chrome) - auto-configura
# ---------------------------------------------------------------------
function Get-SentinelaPolicyRoots {
    # Em simulacao grava num ramo de teste em HKCU (sem admin, reversivel).
    if ((Get-SentinelaPaths).Simular) {
        return @(
            @{ Nome='Edge';   Path='HKCU:\Software\SentinelaTeste\Microsoft\Edge' },
            @{ Nome='Chrome'; Path='HKCU:\Software\SentinelaTeste\Google\Chrome' }
        )
    }
    return @(
        @{ Nome='Edge';   Path='HKLM:\SOFTWARE\Policies\Microsoft\Edge' },
        @{ Nome='Chrome'; Path='HKLM:\SOFTWARE\Policies\Google\Chrome' }
    )
}

function Set-SentinelaSafeSearch {
    param([switch]$Simular)
    foreach ($r in (Get-SentinelaPolicyRoots)) {
        if (-not (Test-Path $r.Path)) { New-Item -Path $r.Path -Force | Out-Null }
        foreach ($pol in $script:SAFE_POLICIES) {
            New-ItemProperty -Path $r.Path -Name $pol.Nome -Value $pol.Valor -PropertyType $pol.Tipo -Force | Out-Null
        }
    }
    Write-SentinelaLog 'Politicas de SafeSearch de navegador aplicadas (Google/YouTube estrito, DoH off).' 'ACAO'
}

function Clear-SentinelaSafeSearch {
    foreach ($r in (Get-SentinelaPolicyRoots)) {
        if (-not (Test-Path $r.Path)) { continue }
        foreach ($pol in $script:SAFE_POLICIES) {
            Remove-ItemProperty -Path $r.Path -Name $pol.Nome -ErrorAction SilentlyContinue
        }
    }
    Write-SentinelaLog 'Politicas de SafeSearch de navegador removidas.' 'ACAO'
}

function Test-SentinelaSafeSearchApplied {
    $roots = Get-SentinelaPolicyRoots
    if ($roots.Count -eq 0) { return $false }
    foreach ($r in $roots) {
        if (-not (Test-Path $r.Path)) { return $false }
        foreach ($pol in $script:SAFE_POLICIES) {
            $prop = Get-ItemProperty -Path $r.Path -Name $pol.Nome -ErrorAction SilentlyContinue
            if ($null -eq $prop) { return $false }
            if ($prop.$($pol.Nome) -ne $pol.Valor) { return $false }
        }
    }
    return $true
}

# ---------------------------------------------------------------------
# Acoes de alto nivel
# ---------------------------------------------------------------------
function Enable-Sentinela {
    param([switch]$Simular)
    Initialize-SentinelaStore | Out-Null
    Set-SentinelaHosts      -Simular:$Simular
    Set-SentinelaDns        -Simular:$Simular
    Set-SentinelaSafeSearch -Simular:$Simular
    Set-SentinelaState -Ativo $true
    Write-SentinelaLog 'Sentinela ATIVADO.' 'ACAO'
}

function Disable-Sentinela {
    param([switch]$Simular)
    Clear-SentinelaHosts
    Restore-SentinelaDns   -Simular:$Simular
    Clear-SentinelaSafeSearch
    Set-SentinelaState -Ativo $false
    Write-SentinelaLog 'Sentinela DESATIVADO.' 'ACAO'
}

function Get-SentinelaStatus {
    $state = Get-SentinelaState
    [pscustomobject]@{
        Ativo            = [bool]$state.ativo
        DnsAplicado      = Test-SentinelaDnsApplied
        HostsAplicado    = Test-SentinelaHostsApplied
        SafeSearchAplicado = Test-SentinelaSafeSearchApplied
        Desde            = $state.desde
        Simulacao        = (Get-SentinelaPaths).Simular
    }
}
