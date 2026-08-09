import numpy as np

from gambeta import gpu


def test_xp_is_always_available() -> None:
    assert gpu.xp is not None
    assert hasattr(gpu.xp, "mean")


def test_asnumpy_returns_a_host_array() -> None:
    out = gpu.asnumpy(gpu.xp.asarray([1.0, 2.0, 3.0]))
    assert isinstance(out, np.ndarray)
    assert out.tolist() == [1.0, 2.0, 3.0]


def test_has_gpu_is_a_bool() -> None:
    assert isinstance(gpu.HAS_GPU, bool)


def test_falls_back_to_numpy_when_no_gpu() -> None:
    if not gpu.HAS_GPU:
        assert gpu.xp is np
