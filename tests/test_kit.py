import dataclasses
from pathlib import Path

import pytest

from gambeta import kit


def test_seasons_span_25_years() -> None:
    assert len(kit.SEASONS) == 25
    assert kit.SEASONS[0] == "0001"
    assert kit.SEASONS[-1] == "2425"


def test_load_builds_paths_under_root(tmp_path: Path) -> None:
    cfg = kit.load(tmp_path)
    assert cfg.raw == tmp_path / "vault" / "raw"
    assert cfg.clean == tmp_path / "vault" / "clean"
    assert cfg.derive == tmp_path / "vault" / "derive"
    assert cfg.league == "ENG-Premier League"
    assert cfg.seed == 20260810


def test_config_is_frozen(tmp_path: Path) -> None:
    cfg = kit.load(tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.seed = 1  # type: ignore[misc]
