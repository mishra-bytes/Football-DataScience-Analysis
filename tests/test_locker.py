import json
from pathlib import Path

import pandas as pd
import pytest
from pandera.pandas import Column, DataFrameSchema

from gambeta import laws, locker

SCHEMA = DataFrameSchema({"a": Column(int)}, strict=True, coerce=True)


def test_roundtrip_preserves_data(tmp_path: Path) -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})
    p = locker.write(df, tmp_path / "t.parquet", SCHEMA, source="test")
    pd.testing.assert_frame_equal(locker.read(p, SCHEMA), df)


def test_write_emits_manifest(tmp_path: Path) -> None:
    p = locker.write(pd.DataFrame({"a": [1, 2]}), tmp_path / "t.parquet", SCHEMA, source="fbref")
    m = json.loads(locker.manifest_path(p).read_text())
    assert m["rows"] == 2
    assert m["source"] == "fbref"
    assert m["columns"] == ["a"]
    assert "written_at" in m
    assert "soccerdata_version" in m


def test_write_rejects_invalid_frame(tmp_path: Path) -> None:
    with pytest.raises(laws.ValidationError):
        locker.write(pd.DataFrame({"b": [1]}), tmp_path / "t.parquet", SCHEMA, source="test")


def test_rejected_write_leaves_no_file(tmp_path: Path) -> None:
    target = tmp_path / "t.parquet"
    with pytest.raises(laws.ValidationError):
        locker.write(pd.DataFrame({"b": [1]}), target, SCHEMA, source="test")
    assert not target.exists(), "a rejected frame must not leave a partial file behind"


def test_write_creates_parent_directories(tmp_path: Path) -> None:
    p = locker.write(pd.DataFrame({"a": [1]}), tmp_path / "deep" / "x.parquet", SCHEMA, source="t")
    assert p.exists()


def test_extra_metadata_lands_in_manifest(tmp_path: Path) -> None:
    p = locker.write(
        pd.DataFrame({"a": [1]}), tmp_path / "t.parquet", SCHEMA, source="t", extra={"seasons": 25}
    )
    assert json.loads(locker.manifest_path(p).read_text())["seasons"] == 25


def test_read_validates_against_schema(tmp_path: Path) -> None:
    p = tmp_path / "raw.parquet"
    pd.DataFrame({"unexpected": ["x"]}).to_parquet(p, index=False)
    with pytest.raises(laws.ValidationError):
        locker.read(p, SCHEMA)
