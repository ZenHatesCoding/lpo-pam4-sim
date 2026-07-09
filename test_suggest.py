import numpy as np
from bo_optimizer import BayesianOptimizer

bounds = np.zeros((10, 2))
bounds[:9, 0] = -1.0
bounds[:9, 1] = 1.0
bounds[9, 0] = -20.0
bounds[9, 1] = 0.0

bo = BayesianOptimizer(bounds, noise_var=1e-3)

# Fake training data
X_data = []
y_data = []
X_data.append(np.array([0,0,0,0,1,0,0,0,0,-12]))
y_data.append(0.069)
for _ in range(10):
    x = np.random.uniform(-1, 1, 10)
    x[9] = np.random.uniform(-20, 0)
    x[:9] /= np.sum(np.abs(x[:9]))
    X_data.append(x)
    y_data.append(0.3)

bo.fit(X_data, y_data)
next_taps = bo.suggest_next(n_coarse=20, n_fine_steps=50, patience=15, lr=0.1)

print("Next taps suggested by BO:")
print(next_taps)
print("Is it default point?", np.allclose(next_taps[:9], np.array([0,0,0,0,1,0,0,0,0])))
