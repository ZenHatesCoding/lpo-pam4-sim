"""tests/test_viterbi_equiv.py — MLSE fast/ref 逐位一致常驻回归。

验证 viterbi_mlse_pam4 的向量化分支（fast=True）与原始标量参考实现
（fast=False）在 memory 0/1/2 下逐位一致；入口函数两个开关均可用。
电平为归一化 PAM4（满量程 ±1）。

用法：python tests/test_viterbi_equiv.py
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mlse_burg as M


def test_equiv_mem0():
    rng = np.random.RandomState(0)
    for N in (1, 5, 1000):
        y = rng.randn(N) * 3.0
        pr = [1.0]
        a = M._viterbi_mlse_pam4_ref(y, pr)
        b = M._viterbi_mlse_pam4_fast(y, pr)
        assert np.array_equal(a, b), f"mem0 mismatch N={N}"
        assert np.array_equal(M.viterbi_mlse_pam4(y, pr), b)
        assert np.array_equal(M.viterbi_mlse_pam4(y, pr, fast=False), a)


def test_equiv_mem1():
    rng = np.random.RandomState(1)
    for N in (1, 5, 50, 2000):
        y = rng.randn(N) * 3.0
        pr = [1.0, 0.4]
        a = M._viterbi_mlse_pam4_ref(y, pr)
        b = M._viterbi_mlse_pam4_fast(y, pr)
        assert np.array_equal(a, b), f"mem1 mismatch N={N}"
        assert np.array_equal(M.viterbi_mlse_pam4(y, pr), b)
        assert np.array_equal(M.viterbi_mlse_pam4(y, pr, fast=False), a)


def test_equiv_mem2():
    rng = np.random.RandomState(2)
    for N in (1, 50, 200):
        y = rng.randn(N) * 3.0
        pr = [1.0, 0.3, 0.1]
        a = M._viterbi_mlse_pam4_ref(y, pr)
        b = M._viterbi_mlse_pam4_fast(y, pr)
        assert np.array_equal(a, b), f"mem2 mismatch N={N}"


if __name__ == "__main__":
    test_equiv_mem0()
    test_equiv_mem1()
    test_equiv_mem2()
    print("EQUIVALENCE TESTS PASSED (mem 0/1/2)")
