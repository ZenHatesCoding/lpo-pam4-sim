import numpy as np

def project(X):
    X = np.clip(X, -1, 1)
    ffe_sum = np.sum(np.abs(X[:9]))
    X[:9] = X[:9] / max(ffe_sum, 1e-9)
    return X

# Suppose X is near the default
X = np.array([0.01, -0.01, 0, 0, 0.98, 0, 0, 0, 0])
print("Initial:", X)

# Suppose gradient pushes it towards [0, 0, 0, 0, 1, 0, 0, 0, 0] or away
grad = np.array([0.1, -0.1, 0, 0, 0.5, 0, 0, 0, 0])

X_new = X + 0.1 * grad
print("Before proj:", X_new)
X_new = project(X_new)
print("After proj:", X_new)

# What if X is exactly the default point, and grad wants to move away?
X = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
grad = np.array([0.1, -0.1, 0.05, 0, 0.0, 0, 0, 0, 0])
X_new = X + 0.1 * grad
print("From default, before proj:", X_new)
X_new = project(X_new)
print("From default, after proj:", X_new)
