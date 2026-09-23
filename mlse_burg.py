import numpy as np

def burg_ar(x, order):
    """
    Burg algorithm for AR parameter estimation.
    Used for determining the Partial Response target.
    """
    N = len(x)
    ef = x.copy()
    eb = x.copy()
    a = np.zeros(order + 1)
    a[0] = 1.0
    
    E = np.sum(x**2) / N
    
    for m in range(1, order + 1):
        num = -2.0 * np.sum(ef[m:N] * eb[m-1:N-1])
        den = np.sum(ef[m:N]**2) + np.sum(eb[m-1:N-1]**2)
        k = num / den
        
        a_prev = a.copy()
        for i in range(1, m + 1):
            if i == m:
                a[i] = k
            else:
                a[i] = a_prev[i] + k * a_prev[m - i]
                
        ef_new = np.zeros(N)
        eb_new = np.zeros(N)
        ef_new[m:N] = ef[m:N] + k * eb[m-1:N-1]
        eb_new[m:N] = eb[m-1:N-1] + k * ef[m:N]
        ef = ef_new
        eb = eb_new
        
        E = E * (1 - k**2)
        
    return a[1:] # returns [a_1, ..., a_p]


def _viterbi_mlse_pam4_ref(y, pr_taps):
    """原始标量实现（参考分支，禁止改动）。

    与 _viterbi_mlse_pam4_fast 逐位等价；仅在 fast=False 回退时使用。
    """
    L = len(pr_taps)
    memory = L - 1
    levels = np.array([-3.0, -1.0, 1.0, 3.0])
    N = len(y)
    
    if memory == 0:
        # Simple slicer
        decisions = np.zeros(N)
        for i in range(N):
            decisions[i] = levels[np.argmin(np.abs(levels - y[i]))]
        return decisions
        
    elif memory == 1:
        # 4 states
        path_metrics = np.zeros(4)
        pointers = np.zeros((4, N), dtype=int)
        
        for n in range(N):
            new_path_metrics = np.full(4, np.inf)
            
            for next_state, curr_sym in enumerate(levels):
                min_metric = np.inf
                best_prev_state = 0
                
                for prev_state, prev_sym in enumerate(levels):
                    expected = pr_taps[0] * curr_sym + pr_taps[1] * prev_sym
                    branch_metric = (y[n] - expected)**2
                    metric = path_metrics[prev_state] + branch_metric
                    
                    if metric < min_metric:
                        min_metric = metric
                        best_prev_state = prev_state
                        
                new_path_metrics[next_state] = min_metric
                pointers[next_state, n] = best_prev_state
                
            path_metrics = new_path_metrics
            
        # Traceback
        decisions = np.zeros(N)
        curr_state = np.argmin(path_metrics)
        for n in range(N - 1, -1, -1):
            decisions[n] = levels[curr_state]
            curr_state = pointers[curr_state, n]
            
        return decisions

    elif memory == 2:
        # 16 states
        path_metrics = np.zeros(16)
        pointers = np.zeros((16, N), dtype=int)
        
        state_to_syms = [(levels[i//4], levels[i%4]) for i in range(16)] # (prev2, prev1)
        
        for n in range(N):
            new_path_metrics = np.full(16, np.inf)
            
            for next_state in range(16):
                prev1_new, curr_sym = state_to_syms[next_state]
                min_metric = np.inf
                best_prev_state = 0
                
                for prev2_old_idx, prev2_old in enumerate(levels):
                    prev1_old = prev1_new
                    prev1_old_idx = np.where(levels == prev1_old)[0][0]
                    prev_state = prev2_old_idx * 4 + prev1_old_idx
                    
                    expected = pr_taps[0] * curr_sym + pr_taps[1] * prev1_new + pr_taps[2] * prev2_old
                    branch_metric = (y[n] - expected)**2
                    metric = path_metrics[prev_state] + branch_metric
                    
                    if metric < min_metric:
                        min_metric = metric
                        best_prev_state = prev_state
                        
                new_path_metrics[next_state] = min_metric
                pointers[next_state, n] = best_prev_state
                
            path_metrics = new_path_metrics
            
        # Traceback
        decisions = np.zeros(N)
        curr_state = np.argmin(path_metrics)
        for n in range(N - 1, -1, -1):
            _, curr_sym = state_to_syms[curr_state]
            decisions[n] = curr_sym
            curr_state = pointers[curr_state, n]
            
        return decisions
    else:
        raise NotImplementedError("MLSE Memory > 2 not implemented")


def _viterbi_mlse_pam4_fast(y, pr_taps):
    """向量化等价实现（与 _viterbi_mlse_pam4_ref 逐位一致）。

    memory=0/1 用 NumPy 向量化 ACS；memory=2 沿用原始标量实现（当前配置未使用，
    因此不向量化，避免在未使用路径上引入差异）。
    """
    L = len(pr_taps)
    memory = L - 1
    levels = np.array([-3.0, -1.0, 1.0, 3.0])
    y = np.asarray(y, dtype=float)
    N = len(y)

    if memory == 0:
        # 向量化切片器：与原始 for 循环逐位一致（argmin 取第一个最小，平手同左）
        idx = np.argmin(np.abs(levels[:, None] - y[None, :]), axis=0)
        return levels[idx]

    if memory == 1:
        # 4 状态。ACS 向量化：expected[next_state, prev_state] 一次性算 4×4 分支度量，
        # 对每个 next_state 沿 prev 轴取 min/argmin，与原始三重循环逐位一致。
        pr0 = pr_taps[0]
        pr1 = pr_taps[1]
        expected = pr0 * levels[:, None] + pr1 * levels[None, :]
        path_metrics = np.zeros(4)
        pointers = np.zeros((4, N), dtype=int)

        for n in range(N):
            sq = (y[n] - expected) ** 2
            metric = path_metrics[None, :] + sq
            pointers[:, n] = np.argmin(metric, axis=1)
            path_metrics = metric.min(axis=1)

        # Traceback（与原始实现一致）
        decisions = np.zeros(N)
        curr_state = int(np.argmin(path_metrics))
        for n in range(N - 1, -1, -1):
            decisions[n] = levels[curr_state]
            curr_state = pointers[curr_state, n]

        return decisions

    # memory == 2：当前配置未使用；沿用原始标量实现保证一致。
    return _viterbi_mlse_pam4_ref(y, pr_taps)


def viterbi_mlse_pam4(y, pr_taps, fast=True):
    """Viterbi MLSE for PAM4 signal with Partial Response target.

    Supports memory length up to 2.
    pr_taps: [1, a_1] or [1, a_1, a_2]

    fast=True（默认）使用向量化等价实现；fast=False 回退到原始标量参考实现。
    两条分支输出逐位一致，仅计算路径不同。
    """
    if fast:
        return _viterbi_mlse_pam4_fast(y, pr_taps)
    return _viterbi_mlse_pam4_ref(y, pr_taps)
