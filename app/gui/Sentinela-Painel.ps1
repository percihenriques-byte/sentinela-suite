<#
    Sentinela-Painel.ps1
    ------------------------------------------------------------------
    Painel do Responsavel (janela grafica). Permite, sem usar terminal:
      - ver o estado da protecao (ativa/desligada, DNS, hosts, PIN)
      - ligar a protecao
      - desligar (exige o PIN)
      - definir/trocar o PIN
      - ver o registro de tentativas (log)

    Em modo real, se abrir sem ser Administrador, o painel se auto-eleva
    (as acoes de ligar/desligar mexem em DNS/hosts e exigem admin).

    Parametros de teste:
      -Simular   : nao altera nada real
      -NoShow    : constroi a janela e sai (usado nos testes automatizados)
    ------------------------------------------------------------------
#>
param([switch]$Simular, [switch]$NoShow)

# ---- auto-elevacao (modo real) -------------------------------------
if (-not $Simular -and -not $NoShow) {
    $ident = [Security.Principal.WindowsIdentity]::GetCurrent()
    $princ = New-Object Security.Principal.WindowsPrincipal($ident)
    if (-not $princ.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Start-Process powershell.exe -Verb RunAs -ArgumentList @(
            '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',"`"$PSCommandPath`""
        )
        exit
    }
}

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# localiza os modulos (pasta pai do gui\)
$appDir = Split-Path $PSScriptRoot -Parent
. (Join-Path $appDir 'Sentinela-Core.ps1')
. (Join-Path $appDir 'Sentinela-Pin.ps1')

# ---- paleta ---------------------------------------------------------
$C_BG    = [System.Drawing.Color]::FromArgb(11,18,32)
$C_PANEL = [System.Drawing.Color]::FromArgb(13,26,38)
$C_TEAL  = [System.Drawing.Color]::FromArgb(45,212,191)
$C_TEALD = [System.Drawing.Color]::FromArgb(14,165,160)
$C_TXT   = [System.Drawing.Color]::FromArgb(230,246,242)
$C_MUTE  = [System.Drawing.Color]::FromArgb(144,174,180)
$C_RED   = [System.Drawing.Color]::FromArgb(255,107,107)
$C_LINE  = [System.Drawing.Color]::FromArgb(30,58,68)

function New-Font { param([single]$Size, [int]$Style = 0) New-Object System.Drawing.Font('Segoe UI', $Size, [System.Drawing.FontStyle]$Style) }

# ---- dialogo de PIN -------------------------------------------------
function Show-PinDialog {
    param([string]$Titulo = 'Digite o PIN', [string]$Msg = 'PIN do responsavel:')
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Titulo; $f.Size = New-Object System.Drawing.Size(340, 190)
    $f.StartPosition = 'CenterParent'; $f.FormBorderStyle = 'FixedDialog'
    $f.MaximizeBox = $false; $f.MinimizeBox = $false; $f.BackColor = $C_PANEL

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = $Msg; $lbl.ForeColor = $C_TXT; $lbl.Font = New-Font 10
    $lbl.Location = '20,20'; $lbl.Size = '300,24'; $f.Controls.Add($lbl)

    $tb = New-Object System.Windows.Forms.TextBox
    $tb.UseSystemPasswordChar = $true; $tb.Font = New-Font 14
    $tb.Location = '20,48'; $tb.Size = '295,28'; $tb.MaxLength = 8
    $f.Controls.Add($tb)

    $ok = New-Object System.Windows.Forms.Button
    $ok.Text = 'OK'; $ok.DialogResult = 'OK'; $ok.Location = '150,100'; $ok.Size = '80,34'
    $ok.BackColor = $C_TEAL; $ok.ForeColor = $C_BG; $ok.FlatStyle = 'Flat'; $ok.Font = New-Font 10 1
    $f.Controls.Add($ok); $f.AcceptButton = $ok

    $ca = New-Object System.Windows.Forms.Button
    $ca.Text = 'Cancelar'; $ca.DialogResult = 'Cancel'; $ca.Location = '235,100'; $ca.Size = '80,34'
    $ca.BackColor = $C_PANEL; $ca.ForeColor = $C_MUTE; $ca.FlatStyle = 'Flat'
    $f.Controls.Add($ca); $f.CancelButton = $ca

    $f.Add_Shown({ $tb.Focus() }) | Out-Null
    $r = $f.ShowDialog()
    $val = $tb.Text; $f.Dispose()
    if ($r -eq 'OK') { return $val } else { return $null }
}

# ---- formulario principal ------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Sentinela — Painel do Responsável'
$form.Size = New-Object System.Drawing.Size(560, 640)
$form.StartPosition = 'CenterScreen'
$form.BackColor = $C_BG
$form.Font = New-Font 9.5
$form.FormBorderStyle = 'FixedSingle'
$form.MaximizeBox = $false

# cabecalho
$hdr = New-Object System.Windows.Forms.Label
$hdr.Text = '🛡  Sentinela'
$hdr.ForeColor = $C_TEAL; $hdr.Font = New-Font 20 1
$hdr.Location = '24,18'; $hdr.Size = '400,40'; $form.Controls.Add($hdr)

$sub = New-Object System.Windows.Forms.Label
$sub.Text = 'Busca segura à prova de incógnito — Painel do Responsável'
$sub.ForeColor = $C_MUTE; $sub.Font = New-Font 9
$sub.Location = '26,58'; $sub.Size = '500,20'; $form.Controls.Add($sub)

# cartao de status
$card = New-Object System.Windows.Forms.Panel
$card.BackColor = $C_PANEL; $card.Location = '24,92'; $card.Size = '505,120'
$form.Controls.Add($card)

$stLbl = New-Object System.Windows.Forms.Label
$stLbl.Font = New-Font 17 1; $stLbl.Location = '20,16'; $stLbl.Size = '465,32'
$card.Controls.Add($stLbl)

$stInfo = New-Object System.Windows.Forms.Label
$stInfo.ForeColor = $C_MUTE; $stInfo.Font = New-Font 9.5
$stInfo.Location = '22,54'; $stInfo.Size = '465,56'
$card.Controls.Add($stInfo)

# botoes
$btnAtivar = New-Object System.Windows.Forms.Button
$btnAtivar.Text = 'Ligar proteção'; $btnAtivar.Location = '24,228'; $btnAtivar.Size = '160,44'
$btnAtivar.BackColor = $C_TEAL; $btnAtivar.ForeColor = $C_BG; $btnAtivar.FlatStyle = 'Flat'; $btnAtivar.Font = New-Font 10 1
$form.Controls.Add($btnAtivar)

$btnDesligar = New-Object System.Windows.Forms.Button
$btnDesligar.Text = 'Desligar (PIN)'; $btnDesligar.Location = '194,228'; $btnDesligar.Size = '160,44'
$btnDesligar.BackColor = $C_PANEL; $btnDesligar.ForeColor = $C_RED; $btnDesligar.FlatStyle = 'Flat'; $btnDesligar.Font = New-Font 10 1
$btnDesligar.FlatAppearance.BorderColor = $C_RED
$form.Controls.Add($btnDesligar)

$btnPin = New-Object System.Windows.Forms.Button
$btnPin.Text = 'Definir / trocar PIN'; $btnPin.Location = '364,228'; $btnPin.Size = '165,44'
$btnPin.BackColor = $C_PANEL; $btnPin.ForeColor = $C_TXT; $btnPin.FlatStyle = 'Flat'; $btnPin.Font = New-Font 10
$btnPin.FlatAppearance.BorderColor = $C_LINE
$form.Controls.Add($btnPin)

# log
$logLbl = New-Object System.Windows.Forms.Label
$logLbl.Text = 'Registro de atividades'; $logLbl.ForeColor = $C_TEAL; $logLbl.Font = New-Font 10 1
$logLbl.Location = '24,292'; $logLbl.Size = '300,22'; $form.Controls.Add($logLbl)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true; $logBox.ReadOnly = $true; $logBox.ScrollBars = 'Vertical'
$logBox.BackColor = [System.Drawing.Color]::FromArgb(8,19,28); $logBox.ForeColor = $C_MUTE
$logBox.Font = New-Object System.Drawing.Font('Consolas', 8.5)
$logBox.Location = '24,318'; $logBox.Size = '505,225'; $logBox.BorderStyle = 'FixedSingle'
$form.Controls.Add($logBox)

$btnAtualizar = New-Object System.Windows.Forms.Button
$btnAtualizar.Text = 'Atualizar'; $btnAtualizar.Location = '24,552'; $btnAtualizar.Size = '120,34'
$btnAtualizar.BackColor = $C_PANEL; $btnAtualizar.ForeColor = $C_TXT; $btnAtualizar.FlatStyle = 'Flat'
$btnAtualizar.FlatAppearance.BorderColor = $C_LINE
$form.Controls.Add($btnAtualizar)

$footer = New-Object System.Windows.Forms.Label
$footer.Text = 'Desafio Liga Jovem · SEBRAE'
$footer.ForeColor = [System.Drawing.Color]::FromArgb(94,122,130); $footer.Font = New-Font 8
$footer.Location = '330,562'; $footer.Size = '200,20'; $footer.TextAlign = 'MiddleRight'
$form.Controls.Add($footer)

# ---- logica de atualizacao -----------------------------------------
function Update-Ui {
    $s = Get-SentinelaStatus
    if ($s.Ativo) {
        $stLbl.Text = '● PROTEÇÃO ATIVA'; $stLbl.ForeColor = $C_TEAL
        $btnAtivar.Enabled = $false; $btnDesligar.Enabled = $true
    } else {
        $stLbl.Text = '○ PROTEÇÃO DESLIGADA'; $stLbl.ForeColor = $C_RED
        $btnAtivar.Enabled = $true; $btnDesligar.Enabled = $false
    }
    $pinTxt = if (Test-SentinelaPinConfigured) { 'definido' } else { 'NÃO definido' }
    $dns = if ($s.DnsAplicado) { 'aplicado' } else { 'ausente' }
    $hosts = if ($s.HostsAplicado) { 'aplicado' } else { 'ausente' }
    $extra = if ($s.Simulacao) { '   [modo simulação]' } else { '' }
    $stInfo.Text = "DNS de filtro: $dns      Bloco hosts: $hosts`nPIN do responsável: $pinTxt$extra"

    $p = Get-SentinelaPaths
    if (Test-Path $p.Log) {
        $linhas = Get-Content $p.Log -Tail 60
        $logBox.Text = ($linhas -join "`r`n")
        $logBox.SelectionStart = $logBox.Text.Length
        $logBox.ScrollToCaret()
    } else {
        $logBox.Text = '(sem registros ainda)'
    }
}

# ---- eventos --------------------------------------------------------
$btnAtivar.Add_Click({
    Enable-Sentinela -Simular:$Simular
    [System.Windows.Forms.MessageBox]::Show('Proteção ligada.','Sentinela','OK','Information') | Out-Null
    Update-Ui
})

$btnDesligar.Add_Click({
    if (-not (Test-SentinelaPinConfigured)) {
        [System.Windows.Forms.MessageBox]::Show('Defina um PIN primeiro.','Sentinela','OK','Warning') | Out-Null
        return
    }
    $pin = Show-PinDialog -Titulo 'Desligar o Sentinela' -Msg 'Digite o PIN do responsável para desligar:'
    if ($null -eq $pin) { return }
    if (Test-SentinelaPin -Pin $pin) {
        Disable-Sentinela -Simular:$Simular
        [System.Windows.Forms.MessageBox]::Show('Proteção desligada pelo responsável.','Sentinela','OK','Information') | Out-Null
    } else {
        [System.Windows.Forms.MessageBox]::Show('PIN incorreto. A tentativa foi registrada.','Sentinela','OK','Error') | Out-Null
    }
    Update-Ui
})

$btnPin.Add_Click({
    if (Test-SentinelaPinConfigured) {
        $atual = Show-PinDialog -Titulo 'Trocar PIN' -Msg 'Digite o PIN atual:'
        if ($null -eq $atual) { return }
        if (-not (Test-SentinelaPin -Pin $atual)) {
            [System.Windows.Forms.MessageBox]::Show('PIN atual incorreto.','Sentinela','OK','Error') | Out-Null
            return
        }
    }
    $novo = Show-PinDialog -Titulo 'Novo PIN' -Msg 'Novo PIN (4 a 8 dígitos):'
    if ($null -eq $novo) { return }
    $rep = Show-PinDialog -Titulo 'Confirmar PIN' -Msg 'Repita o novo PIN:'
    if ($novo -ne $rep) {
        [System.Windows.Forms.MessageBox]::Show('Os PINs não conferem.','Sentinela','OK','Warning') | Out-Null
        return
    }
    try {
        Set-SentinelaPin -Pin $novo
        [System.Windows.Forms.MessageBox]::Show('PIN salvo com sucesso.','Sentinela','OK','Information') | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Sentinela','OK','Error') | Out-Null
    }
    Update-Ui
})

$btnAtualizar.Add_Click({ Update-Ui })

Update-Ui
if ($NoShow) {
    Write-Host 'Painel construido com sucesso (NoShow).' -ForegroundColor Green
    $form.Dispose()
    return
}
[System.Windows.Forms.Application]::EnableVisualStyles()
$form.ShowDialog() | Out-Null
$form.Dispose()
