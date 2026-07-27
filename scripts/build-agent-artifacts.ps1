$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$agentDir = Join-Path $rootDir "agent"
$outDir = Join-Path $agentDir "bin"
$cacheDir = Join-Path $rootDir ".cache\go-build"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

foreach ($arch in @("amd64", "arm64")) {
    Write-Host "Building linux-$arch agent"
    Push-Location $agentDir
    try {
        $env:GOOS = "linux"
        $env:GOARCH = $arch
        $env:GOCACHE = $cacheDir
        go build -o (Join-Path $outDir "vulnflanker-agent-linux-$arch") ./cmd/vulnflanker-agent
    }
    finally {
        Pop-Location
        Remove-Item Env:\GOOS -ErrorAction SilentlyContinue
        Remove-Item Env:\GOARCH -ErrorAction SilentlyContinue
        Remove-Item Env:\GOCACHE -ErrorAction SilentlyContinue
    }
}

Write-Host "Agent artifacts written to $outDir"
