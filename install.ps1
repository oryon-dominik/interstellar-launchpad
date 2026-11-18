# launchpad, stage 0: a fresh Windows machine, Windows PowerShell 5.1, nothing else:
#
#   irm https://raw.githubusercontent.com/oryon-dominik/interstellar-launchpad/trunk/install.ps1 | iex
#
# Installs uv, then runs the launchpad through it; uv brings its own Python.
# Plain ASCII and PowerShell 5.1 syntax: no ternary, no ??, no && - the shell a fresh machine opens.

[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$source = "https://github.com/oryon-dominik/interstellar-launchpad/archive/refs/heads/trunk.zip"
if ($env:LAUNCHPAD_SOURCE) { $source = $env:LAUNCHPAD_SOURCE }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    # In a child shell: the uv installer calls `exit` on failure, which would close this window.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    uvx --refresh-package launchpad --from $source launchpad
}
else {
    Write-Host "uv did not install. See the messages above, then run this command again." -ForegroundColor Red
}
