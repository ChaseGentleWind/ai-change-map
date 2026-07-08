param(
    [string]$NgrokPath = "",
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5174
)

$ErrorActionPreference = "Stop"

function Quote-PathForPowerShell {
    param([string]$Path)
    return "'" + ($Path -replace "'", "''") + "'"
}

function Resolve-NgrokPath {
    param([string]$ProvidedPath)

    if ($ProvidedPath -and (Test-Path -LiteralPath $ProvidedPath)) {
        return (Resolve-Path -LiteralPath $ProvidedPath).Path
    }

    if ($env:NGROK_EXE -and (Test-Path -LiteralPath $env:NGROK_EXE)) {
        return (Resolve-Path -LiteralPath $env:NGROK_EXE).Path
    }

    $localNgrok = Join-Path $PSScriptRoot "ngrok.exe"
    if (Test-Path -LiteralPath $localNgrok) {
        return (Resolve-Path -LiteralPath $localNgrok).Path
    }

    $pathNgrok = Get-Command "ngrok.exe" -ErrorAction SilentlyContinue
    if ($pathNgrok) {
        return $pathNgrok.Source
    }

    throw "ngrok.exe was not found. Put ngrok.exe in the project root, set NGROK_EXE, or pass -NgrokPath."
}

function Start-ManagedProcess {
    param(
        [string]$Name,
        [string]$Command,
        [string]$LogName
    )

    $runtimeDir = Join-Path $PSScriptRoot ".runtime"
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

    $stdout = Join-Path $runtimeDir "$LogName.out.log"
    $stderr = Join-Path $runtimeDir "$LogName.err.log"
    $pidFile = Join-Path $runtimeDir "$LogName.pid"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))

    $process = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII
    Write-Host "$Name started, PID: $($process.Id)"
    Write-Host "  stdout: $stdout"
    Write-Host "  stderr: $stderr"
    return $process
}

function Get-NgrokPublicUrl {
    param(
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
            $tunnel = $response.tunnels |
                Where-Object { $_.proto -eq "https" -or $_.public_url -like "https://*" } |
                Select-Object -First 1
            if (-not $tunnel) {
                $tunnel = $response.tunnels | Select-Object -First 1
            }
            if ($tunnel.public_url) {
                return $tunnel.public_url
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    return ""
}

$rootDir = $PSScriptRoot
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$ngrokExe = Resolve-NgrokPath -ProvidedPath $NgrokPath

if (-not (Test-Path -LiteralPath $backendDir)) {
    throw "backend directory was not found: $backendDir"
}
if (-not (Test-Path -LiteralPath $frontendDir)) {
    throw "frontend directory was not found: $frontendDir"
}

$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $backendPython)) {
    $pythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found. Install Python or create backend\.venv first."
    }
    $backendPython = $pythonCommand.Source
}

$npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    $npmCommand = Get-Command "npm.exe" -ErrorAction SilentlyContinue
}
if (-not $npmCommand) {
    throw "npm was not found. Install Node.js first."
}

$backendEnv = Join-Path $backendDir ".env"
if (-not (Test-Path -LiteralPath $backendEnv)) {
    $envExample = Join-Path $backendDir ".env.example"
    if (Test-Path -LiteralPath $envExample) {
        Copy-Item -LiteralPath $envExample -Destination $backendEnv
        Write-Warning "Created backend\.env from backend\.env.example."
    }
    throw "backend\.env is missing or was just created. Fill API keys and JWT_SECRET_KEY, then rerun this script."
}

$backendCommand = @"
`$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $(Quote-PathForPowerShell $backendDir)
& $(Quote-PathForPowerShell $backendPython) -m uvicorn main:app --host 0.0.0.0 --port $BackendPort --reload
"@

$frontendCommand = @"
`$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $(Quote-PathForPowerShell $frontendDir)
if (-not (Test-Path -LiteralPath "node_modules")) {
    & $(Quote-PathForPowerShell $npmCommand.Source) install
}
& $(Quote-PathForPowerShell $npmCommand.Source) run dev -- --host 0.0.0.0 --port $FrontendPort
"@

$ngrokCommand = @"
`$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $(Quote-PathForPowerShell $rootDir)
& $(Quote-PathForPowerShell $ngrokExe) http $FrontendPort
"@

Write-Host "Project: $rootDir"
Write-Host "Backend port: $BackendPort"
Write-Host "Frontend port: $FrontendPort"
Write-Host "ngrok: $ngrokExe"
Write-Host ""

Start-ManagedProcess -Name "Backend FastAPI" -Command $backendCommand -LogName "backend" | Out-Null
Start-Sleep -Seconds 2
Start-ManagedProcess -Name "Frontend Vite" -Command $frontendCommand -LogName "frontend" | Out-Null
Start-Sleep -Seconds 3
Start-ManagedProcess -Name "ngrok" -Command $ngrokCommand -LogName "ngrok" | Out-Null

Write-Host ""
Write-Host "Startup commands have been sent."
Write-Host "Local frontend: http://localhost:$FrontendPort"
Write-Host "Local backend: http://localhost:$BackendPort"
Write-Host "Waiting for ngrok public URL..."
$publicUrl = Get-NgrokPublicUrl -TimeoutSeconds 30
if ($publicUrl) {
    Write-Host ""
    Write-Host "ngrok public URL: $publicUrl"
    try {
        Set-Clipboard -Value $publicUrl
        Write-Host "The ngrok URL has been copied to clipboard."
    } catch {
        Write-Host "Could not copy URL to clipboard."
    }
} else {
    Write-Host "Could not read ngrok URL automatically."
    Write-Host "Open http://127.0.0.1:4040 or check .\.runtime\ngrok.out.log."
}
Write-Host "To stop everything, double-click stop-all.bat."
