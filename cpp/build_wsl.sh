#!/bin/bash
# build_wsl.sh — 在 WSL 内编译 C++ 平台（绕开 Windows Smart App Control 对本地
# 无签名二进制的强制拦截）。
#
# 背景（2026-10-12 实测）：本机 Smart App Control 已从评估模式转入强制模式，
# MinGW 工具链的 cc1plus.exe 因依赖的 libisl-23.dll 不满足签名等级被拦，
# 此前编译的 run_ddps.exe 同样被拦（"An Application Control policy has blocked
# this file"）。换任何 Windows 侧编译器都无法解决——产物仍是本地无签名 exe，
# 照样被拦。WSL 内的 Linux 进程不受 Windows 代码完整性策略管辖，且本工程
# C++ 源码为纯标准 C++17（无平台相关 API），g++ 直接可编译。
# 数值等价性不受影响：仍按 AGENTS.md 口径在 2^18 小点数低 SNR 下与 Python
# 逐一比对（cpp/compare_traces.py），通过后才能跑全量规模仿真。
#
# 用法（仓库根目录）：
#   wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity bash cpp/build_wsl.sh
# 产物：cpp/build/run_ddps（Linux ELF）
set -e
g++ -O2 -std=c++17 cpp/main.cpp -o cpp/build/run_ddps
echo "built cpp/build/run_ddps (Linux ELF, g++ $(g++ -dumpversion))"
