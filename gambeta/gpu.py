"""Array-namespace dispatch. Ten lines, deliberately.

``xp`` is CuPy when a CUDA GPU is usable and NumPy otherwise. There is no
abstraction layer and no strategy pattern: numeric code takes an array
namespace and works either way, so CI runs GPU-less and so does anyone
without an NVIDIA card.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np

try:  # pragma: no cover - depends on hardware
    import cupy as _cupy

    _cupy.zeros(1)  # fail fast if the driver or device is unusable
    xp: ModuleType = _cupy
    HAS_GPU = True
except Exception:  # pragma: no cover - the common path, and the CI path
    xp = np
    HAS_GPU = False


def asnumpy(a: Any) -> np.ndarray:
    """Bring an array back to host memory, whichever namespace produced it."""
    return np.asarray(xp.asnumpy(a)) if HAS_GPU else np.asarray(a)
