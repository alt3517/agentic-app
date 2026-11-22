$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python environment not found. Create it with: py -3.12 -m venv .venv"
}

$certFile = if ($env:TLS_CERT_FILE) {
    $env:TLS_CERT_FILE
} else {
    Join-Path $PSScriptRoot "..\dev-certs\localhost.pem"
}
$keyFile = if ($env:TLS_KEY_FILE) {
    $env:TLS_KEY_FILE
} else {
    Join-Path $PSScriptRoot "..\dev-certs\localhost.key"
}
$certFile = [System.IO.Path]::GetFullPath($certFile)
$keyFile = [System.IO.Path]::GetFullPath($keyFile)
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

if (-not $env:MAIN_APP_API_URL) {
    $env:MAIN_APP_API_URL = "https://localhost:7161"
}
if (-not $env:MAIN_APP_CA_FILE) {
    $env:MAIN_APP_CA_FILE = Join-Path $repositoryRoot "dev-certs\localhost.pem"
}

if (-not (Test-Path $certFile)) {
    throw "TLS certificate not found: $certFile. See the repository README."
}
if (-not (Test-Path $keyFile)) {
    throw "TLS private key not found: $keyFile. See the repository README."
}

& $python -m uvicorn main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --ssl-certfile $certFile `
    --ssl-keyfile $keyFile `
    --no-access-log
exit $LASTEXITCODE
