import numpy as np
import sys

print(f"Python executable: {sys.executable}")
print(f"Numpy version: {np.__version__}")

a = np.array([1, 2, 3])
b = np.array([4, 5, 6])
c = a + b
print(f"Result of a + b: {c}")
