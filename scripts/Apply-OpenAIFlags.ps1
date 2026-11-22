[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envFile = Join-Path $repositoryRoot ".env"
$composeFile = Join-Path $repositoryRoot "compose.yaml"
$flagNames = @(
    "OPENAI_TICKET_CONTEXT_ENABLED",
    "OPENAI_KNOWLEDGE_CONTEXT_ENABLED",
    "WEB_SEARCH_ENABLED"
)

if (-not (Test-Path $envFile -PathType Leaf)) {
    throw "Missing .env file. Create it from .env.example first."
}

$expectedValues = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*(?<name>OPENAI_TICKET_CONTEXT_ENABLED|OPENAI_KNOWLEDGE_CONTEXT_ENABLED|WEB_SEARCH_ENABLED)\s*=\s*(?<value>.*?)\s*$') {
        $name = $Matches.name
        $value = $Matches.value.Trim()
        if ($value.Length -ge 2 -and (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        )) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $value = $value.Trim().ToLowerInvariant()
        if ($expectedValues.ContainsKey($name)) {
            throw ".env contains more than one definition for $name."
        }
        if ($value -notin @("true", "false")) {
            throw "$name must be set to true or false in .env."
        }
        $expectedValues[$name] = $value
    }
}

foreach ($name in $flagNames) {
    if (-not $expectedValues.ContainsKey($name)) {
        throw ".env does not define $name."
    }
}

$previousEnvironment = @{}
foreach ($name in $flagNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, $expectedValues[$name], "Process")
}

try {
    $composePrefix = @(
        "--project-directory", $repositoryRoot,
        "--env-file", $envFile,
        "-f", $composeFile
    )
    $configOutput = & docker compose @composePrefix config --format json
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve the Compose configuration."
    }

    $config = ($configOutput -join [Environment]::NewLine) | ConvertFrom-Json
    $serviceEnvironment = $config.services.'agentic-app'.environment
    foreach ($name in $flagNames) {
        $property = $serviceEnvironment.PSObject.Properties[$name]
        if ($null -eq $property) {
            throw "Compose does not define $name for agentic-app."
        }

        $value = ([string]$property.Value).Trim().ToLowerInvariant()
        if ($value -ne $expectedValues[$name]) {
            throw "Compose resolved $name differently from .env."
        }
    }

    & docker compose @composePrefix up -d --force-recreate --no-deps agentic-app
    if ($LASTEXITCODE -ne 0) {
        throw "Could not recreate the agentic-app container."
    }

    $containerId = (& docker compose @composePrefix ps -q agentic-app).Trim()
    if (-not $containerId) {
        throw "Compose did not return an agentic-app container ID."
    }

    $containerEnvironment = & docker inspect $containerId --format '{{range .Config.Env}}{{println .}}{{end}}'
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the agentic-app container environment."
    }

    $actualValues = @{}
    foreach ($line in $containerEnvironment) {
        if ($line -match '^(?<name>[^=]+)=(?<value>.*)$' -and $flagNames -contains $Matches.name) {
            $actualValues[$Matches.name] = $Matches.value.Trim().ToLowerInvariant()
        }
    }

    foreach ($name in $flagNames) {
        if ($actualValues[$name] -ne $expectedValues[$name]) {
            throw "$name differs between .env and the running container."
        }
    }

    $deadline = [DateTime]::UtcNow.AddMinutes(5)
    do {
        $health = (& docker inspect $containerId --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}').Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Could not check the agentic-app container health."
        }
        if ($health -eq "healthy") {
            break
        }
        if ($health -eq "unhealthy" -or [DateTime]::UtcNow -ge $deadline) {
            throw "agentic-app did not become healthy (status: $health)."
        }
        Start-Sleep -Seconds 2
    } while ($true)

    Write-Output "Applied OpenAI sharing flags to agentic-app:"
    foreach ($name in $flagNames) {
        Write-Output "$name=$($actualValues[$name])"
    }
    Write-Output "Container health=$health"
}
finally {
    foreach ($name in $flagNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], "Process")
    }
}
