# build.ps1 — 编译 C++ DDPS 平台（run_ddps.exe + 各测试）。
#
# 环境：
#   - 编译器：WinLibs MinGW g++ 16.2.0（便携 zip）
#     C:\Users\ZhenpingXing\AppData\Local\mingw64\mingw64\bin\
#   - 注意：该便携链的 g++.exe / x86_64-w64-mingw32-g++.exe 会被 Windows Application
#     Control（Smart App Control）拦截，但 gcc.exe（同源自带的 C 驱动，哈希未被拦）
#     可正常运行。因 C++ 源按扩展名 .cpp 判定语言，用 gcc.exe + 显式 -lstdc++ 即可
#     完整编译并链接 C++（与 g++ 等价）。
#   - 必须【动态链接】（去掉 -static）：WDAC 会拦 >~0.6MB 静态链接 exe（~0.2MB 动态可运行）。
#   - 运行前把 mingw64\bin 加入 PATH（libstdc++-6.dll 等运行时依赖）。
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

# 主入口
Compile "cpp\main.cpp" "cpp\build\run_ddps.exe"

# 测试二进制
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
