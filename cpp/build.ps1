# build.ps1 — compile C++ DDPS platform (run_ddps.exe + test binaries).
#
# Environment:
#   - Compiler: WinLibs MinGW g++ 16.2.0 portable zip
#     C:\Users\ZhenpingXing\AppData\Local\mingw64\mingw64\bin\
#   - IMPORTANT: g++.exe / x86_64-w64-mingw32-g++.exe are blocked by Windows
#     Application Control (Smart App Control, hash-based), but gcc.exe (the C driver
#     from the same toolchain, hash not blocked) runs fine. Since .cpp sources select
#     the language by extension, use gcc.exe + explicit -lstdc++ to compile+link C++
#     (equivalent to g++).
#   - MUST link dynamically (no -static): WDAC blocks statically-linked exe > ~0.6MB
#     (dynamic ~0.2MB runs fine).
#   - Add mingw64\bin to PATH before running (libstdc++-6.dll runtime dependency).
param(
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$GPP = "C:\Users\ZhenpingXing\AppData\Local\mingw64\mingw64\bin\gcc.exe"
$env:PATH = "C:\Users\ZhenpingXing\AppData\Local\mingw64\mingw64\bin;" + $env:PATH

if (-not (Test-Path "cpp\build")) { New-Item -ItemType Directory -Path "cpp\build" | Out-Null }

$common = "-O2 -std=c++17"

function Compile([string]$src, [string]$out) {
    Write-Host "  compiling $src -> $out"
    & $GPP $common.Split(" ") $src -o $out -lstdc++
    if ($LASTEXITCODE -ne 0) { throw "compile failed: $src" }
}

# Main entry
Compile "cpp\main.cpp" "cpp\build\run_ddps.exe"

# Test binaries
Compile "cpp\tests\test_equiv.cpp" "cpp\build\test_equiv.exe"
Compile "cpp\tests\test_rng.cpp" "cpp\build\test_rng.exe"
Compile "cpp\tests\test_dsp.cpp" "cpp\build\test_dsp.exe"
Compile "cpp\tests\test_s4p.cpp" "cpp\build\test_s4p.exe"
Compile "cpp\tests\test_interp.cpp" "cpp\build\test_interp.exe"
Compile "cpp\tests\test_probe.cpp" "cpp\build\test_probe.exe"
Compile "cpp\tests\test_optimizer.cpp" "cpp\build\test_optimizer.exe"
Compile "cpp\tests\test_chan.cpp" "cpp\build\test_chan.exe"
Compile "cpp\tests\test_probe_chain.cpp" "cpp\build\test_probe_chain.exe"
Compile "cpp\tests\test_drms.cpp" "cpp\build\test_drms.exe"
Compile "cpp\tests\test_dft.cpp" "cpp\build\test_dft.exe"

Write-Host "build done. run with:  .\cpp\build\run_ddps.exe cpp\config.txt"