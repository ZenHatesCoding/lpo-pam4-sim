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

def viterbi_mlse_pam4(y, pr_taps):
    """
    Viterbi MLSE for PAM4 signal with Partial Response target.
    Supports memory length up to 2.
    pr_taps: [1, a_1] or [1, a_1, a_2]
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
        survivor_paths = np.zeros((4, N), dtype=int)
        
        for n in range(N):
            new_path_metrics = np.full(4, np.inf)
            new_survivor_paths = np.zeros((4, N), dtype=int)
            
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
                new_survivor_paths[next_state, :n] = survivor_paths[best_prev_state, :n]
                new_survivor_paths[next_state, n] = curr_sym
                
            path_metrics = new_path_metrics
            survivor_paths = new_survivor_paths
            
        return survivor_paths[np.argmin(path_metrics)]

    elif memory == 2:
        # 16 states
        path_metrics = np.zeros(16)
        survivor_paths = np.zeros((16, N), dtype=int)
        
        state_to_syms = [(levels[i//4], levels[i%4]) for i in range(16)] # (prev2, prev1)
        
        for n in range(N):
            new_path_metrics = np.full(16, np.inf)
            new_survivor_paths = np.zeros((16, N), dtype=int)
            
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
                new_survivor_paths[next_state, :n] = survivor_paths[best_prev_state, :n]
                new_survivor_paths[next_state, n] = curr_sym
                
            path_metrics = new_path_metrics
            survivor_paths = new_survivor_paths
            
        return survivor_paths[np.argmin(path_metrics)]
    else:
        raise NotImplementedError("MLSE Memory > 2 not implemented")
