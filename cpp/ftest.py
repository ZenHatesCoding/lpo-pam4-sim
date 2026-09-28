# ftest.py — 与 test_dft.exe 配对：写入输入，比对 FFT/irfft 与 numpy。
import numpy as np
import sys

N = int(sys.argv[1])
rng = np.random.RandomState(0)
x = rng.normal(0, 1, N)
x.astype('<f8').tofile('cpp/build/dft_in.bin')

# 读 C++ 输出（若存在），否则先只写输入
import os
if not (os.path.exists('cpp/build/dft_out.bin') and os.path.exists('cpp/build/dft_y.bin')):
    print(f'wrote dft_in.bin N={N}')
    sys.exit(0)

c = np.frombuffer(open('cpp/build/dft_out.bin', 'rb').read(), dtype='<f8')
Xc = c[0::2] + 1j * c[1::2]
y = np.fromfile('cpp/build/dft_y.bin', dtype='<f8')
Xn = np.fft.rfft(x)
yn = np.fft.irfft(Xn, n=N)
print(f'N={N} rfft relerr {np.max(np.abs(Xc - Xn)) / np.max(np.abs(Xn)):.3e}')
print(f'N={N} irfft relerr {np.max(np.abs(y - yn)) / np.max(np.abs(yn)):.3e}')
print(f'X[3] cpp {Xc[3]}')
print(f'X[3] np  {Xn[3]}')