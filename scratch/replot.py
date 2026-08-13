import re
import matplotlib.pyplot as plt
import os
import sys

log_file = r'C:\Users\ZhenpingXing\.gemini\antigravity\brain\82b33c7b-843b-4b40-ad39-b15bf13d7f45\.system_generated\tasks\task-635.log'

with open(log_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

combinations = {}
current_combo = None
current_mlse_history = []
n_stage1 = 20

for line in lines:
    m = re.search(r'Running Combo: ([^\s]+)', line)
    if m:
        if current_combo:
            combinations[current_combo] = current_mlse_history
        current_combo = m.group(1)
        current_mlse_history = []
        continue
    
    m_default = re.search(r'Default -> FFE BER: .* \| MLSE BER: ([\d\.e\-\+]+)', line)
    if m_default:
        current_mlse_history.append(float(m_default.group(1)))
        continue
        
    m_stage1 = re.search(r'Stage 1 \[.*\] \| Best MLSE: .* \| Cur FFE: .* \| Cur MLSE: ([\d\.e\-\+]+)', line)
    if m_stage1:
        current_mlse_history.append(float(m_stage1.group(1)))
        continue
        
    m_stage2_surr = re.search(r'Stage 2 \[.*\] \| Best MLSE: .* \| PsLogBER: .* \| Cur MLSE: ([\d\.e\-\+]+)', line)
    if m_stage2_surr:
        current_mlse_history.append(float(m_stage2_surr.group(1)))
        continue
        
    m_stage2_base = re.search(r'Stage 2 \[.*\] \| Best MLSE: .* \| Cur FFE: .* \| Cur MLSE: ([\d\.e\-\+]+)', line)
    if m_stage2_base:
        current_mlse_history.append(float(m_stage2_base.group(1)))
        continue

if current_combo:
    combinations[current_combo] = current_mlse_history
    
base_combos = {}
for key, hist in combinations.items():
    if key.endswith('_Baseline'):
        base = key.replace('_Baseline', '')
        if base not in base_combos:
            base_combos[base] = {}
        base_combos[base]['Baseline'] = hist
    elif key.endswith('_Surrogate'):
        base = key.replace('_Surrogate', '')
        if base not in base_combos:
            base_combos[base] = {}
        base_combos[base]['Surrogate'] = hist

n_combos = len(base_combos)
fig, axes = plt.subplots(n_combos, 1, figsize=(12, 4 * n_combos), sharex=True)
if n_combos == 1:
    axes = [axes]

for ax, (base, modes) in zip(axes, base_combos.items()):
    if 'Baseline' in modes:
        ax.semilogy(modes['Baseline'], label='RX MLSE Feedback (Baseline)', color='blue', linestyle='-', marker='o', markersize=4)
    if 'Surrogate' in modes:
        ax.semilogy(modes['Surrogate'], label='TX GPR+UCB Surrogate (Proposed)', color='red', linestyle='--', marker='x', markersize=4)
        
    ax.axvline(x=n_stage1, color='black', linestyle=':', label='Stage 1 / Stage 2 Boundary')
    ax.set_title(f"Optimization Combination: {base} (SNR=26.0 dB)")
    ax.set_ylabel("MLSE BER")
    ax.grid(True, which="both", ls="--", alpha=0.6)
    ax.legend()
    
axes[-1].set_xlabel("Evaluation Step")
plt.tight_layout()
plot_path = r"c:\DSPPlayground\eLPO_antigravity\result\latest_comparison\two_stage\two_stage_convergence.png"
plt.savefig(plot_path)
plt.close()
print("Plot successfully regenerated!")
