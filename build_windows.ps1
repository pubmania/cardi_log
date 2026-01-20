$ErrorActionPreference = "Stop"

# Kill running instances to release file locks
Write-Host "Stopping any running instances..." -ForegroundColor Cyan
Get-Process -Name "cardi_log", "flutter" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Cleaning up old build..." -ForegroundColor Cyan
if (Test-Path "build") {
    Remove-Item -Path "build" -Recurse -Force
}

Write-Host "Starting Flet Build (this may take a while)..." -ForegroundColor Cyan
$Env:PYTHONIOENCODING='utf-8'

# Run build but allow failure
try {
    flet build windows -v
} catch {
    Write-Host "Build failed as expected (likely due to installation error). Checking for patch..." -ForegroundColor Yellow
}

# Define the patch target
$cmakeInstallPath = "build\flutter\build\windows\x64\cmake_install.cmake"

if (Test-Path $cmakeInstallPath) {
    Write-Host "Patching cmake_install.cmake..." -ForegroundColor Cyan
    $content = Get-Content $cmakeInstallPath -Raw
    
    # Check if we need to patch
    if ($content -match "C:\\windows/system32/vcruntime140.dll") {
        # Determine local paths relative to the build dir
        $localRuntime140 = "$PSScriptRoot/build/flutter/build/windows/x64/python/vcruntime140.dll"
        $localRuntime140_1 = "$PSScriptRoot/build/flutter/build/windows/x64/python/vcruntime140_1.dll"
        
        # Apply replacement
        $content = $content.Replace('"C:\windows/system32/vcruntime140.dll"', "`"$localRuntime140`"")
        $content = $content.Replace('"C:\windows/system32/vcruntime140_1.dll"', "`"$localRuntime140_1`"")
        
        Set-Content $cmakeInstallPath $content
        Write-Host "Patch applied successfully." -ForegroundColor Green
        
        Write-Host "Resuming installation..." -ForegroundColor Cyan
        & "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" -DBUILD_TYPE=Release -P $cmakeInstallPath
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Build completed successfully!" -ForegroundColor Green
            Write-Host "Executable is at: build\flutter\build\windows\x64\runner\Release\cardi_log.exe" -ForegroundColor Green
            exit 0
        } else {
            Write-Host "Installation failed even after patch." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Could not find the problematic string to patch. The build might have failed for another reason." -ForegroundColor Red
    }
} else {
    Write-Host "Build failed early before generating install script." -ForegroundColor Red
    exit 1
}
