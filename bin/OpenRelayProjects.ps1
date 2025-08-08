Param(
  [string]  $Distro        = 'Ubuntu-24.04',
  [string]  $Base          = '/home/paul/code/deposition/apps/relay',
  [string[]]$Projects      = @('devops','cli','atlas','mcp','agent'),

  # toggles
  [switch]  $RestartDistro = $false,  # restart ONLY this distro (safe + non-hanging)
  [switch]  $KillTmux      = $true,   # kill stale tmux sessions once
  [switch]  $PrimeKeychain = $false   # prompt for SSH passphrase here in PS once
)

function Restart-Distro {
  param([string]$Distro, [int]$TimeoutSec = 60)

  $orig = Get-Location
  $leftUNC = $false
  if ($orig.Provider.Name -eq 'FileSystem' -and $orig.Path -like "\\wsl$\$Distro*") {
    Write-Host "[Restart] Detected current path under \\wsl`\$$Distro; moving to $($env:USERPROFILE) to avoid handle deadlock..." -ForegroundColor Yellow
    Push-Location $env:USERPROFILE
    $leftUNC = $true
  } else {
    Write-Host "[Restart] Current path: $($orig.Path)"
  }

  try {
    Write-Host "[Restart] Sending 'wsl --terminate $Distro' (non-blocking)..." -ForegroundColor Yellow
    $term = Start-Process -FilePath wsl.exe -ArgumentList @('--terminate', $Distro) -PassThru -WindowStyle Hidden
    Write-Host "[Restart] Terminate PID: $($term.Id). Not waiting for exit to avoid UNC hangs."

    # Optional: wait briefly until state shows Stopped
    $stopDeadline = (Get-Date).AddSeconds(15)
    $stopped = $false
    do {
      try {
        $out = & wsl.exe -l -v 2>$null | Out-String
        if ($out -match ("`n" + [regex]::Escape($Distro) + ".*Stopped")) {
          $stopped = $true
          Write-Host "[Restart] '$Distro' state: Stopped."
          break
        }
      } catch {}
      Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $stopDeadline)
    if (-not $stopped) { Write-Host "[Restart] Proceeding without explicit 'Stopped' confirmation." -ForegroundColor DarkYellow }

    Write-Host "[Restart] Warming '$Distro'..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $ready = $false
    do {
      $probe = Start-Process -FilePath wsl.exe `
        -ArgumentList @('-d', $Distro, '--', 'bash','-lc','echo ready') `
        -PassThru -WindowStyle Hidden -Wait
      if ($probe.ExitCode -eq 0) {
        $ready = $true
        Write-Host "[Restart] '$Distro' responded to probe." -ForegroundColor Green
      } else {
        Start-Sleep -Milliseconds 500
      }
    } while (-not $ready -and (Get-Date) -lt $deadline)

    if (-not $ready) {
      throw "[Restart] Distro '$Distro' did not become ready within $TimeoutSec seconds."
    }
  }
  finally {
    if ($leftUNC) {
      Pop-Location
      Write-Host "[Restart] Returned to original path."
    }
  }
}

if ($RestartDistro) {
  Restart-Distro -Distro $Distro
}

if ($KillTmux) {
  Write-Host "[Init] Killing tmux server in '$Distro' (safe if not running)..." -ForegroundColor Yellow
  wsl -d $Distro -- bash -lc 'tmux kill-server >/dev/null 2>&1 || true'
  Write-Host "[Init] tmux server kill requested."
}

if ($PrimeKeychain) {
  Write-Host "[Init] Priming keychain (you will be prompted here)..." -ForegroundColor Yellow
  wsl -d $Distro -- bash -lc 'keychain --quiet --agents ssh --quick id_ed25519'
  Write-Host "[Init] Keychain primed."
}

function Open-OneTab([string]$proj, [switch]$First) {
  $bashCmd       = "PROJ='$proj' DIR='$Base/$proj' exec /home/paul/.dotfiles/bin/byobu-cd-attach"
  $quotedBashCmd = "'$bashCmd'"

  $args = @()
  if ($First) { $args += 'new-tab' } else { $args += @('-w','0','new-tab') }
  $args += @('-p', $Distro, '--title', $proj, '--', 'bash', '-ilc', $quotedBashCmd)

  Write-Host "[Launch] Opening tab for '$proj' → $Base/$proj" -ForegroundColor Cyan
  Start-Process wt.exe -ArgumentList $args
}

# First tab creates the window
Open-OneTab $Projects[0] -First
Start-Sleep -Milliseconds 300

# Remaining tabs in the same window
foreach ($p in $Projects[1..($Projects.Count-1)]) {
  Open-OneTab $p
  Start-Sleep -Milliseconds 150
}

Write-Host "[Done] Launched $($Projects.Count) tabs for distro '$Distro'." -ForegroundColor Green
