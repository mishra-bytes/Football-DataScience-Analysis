"""Parquet read/write with schema validation and provenance manifests.

The Parquet store is the seam of the project: ingestion writes it, and every
downstream consumer reads it. Nothing past this module touches the network,
so a broken scraper breaks ingestion rather than analysis.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa


def manifest_path(path: Path) -> Path:
    """Return the sidecar manifest path for a Parquet file."""
    return path.with_suffix(".manifest.json")


def write(
    df: pd.DataFrame,
    path: Path,
    schema: pa.DataFrameSchema,
    source: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Validate ``df``, write it to ``path``, and emit a provenance manifest.

    Validation happens before any file is created, so a rejected frame never
    leaves a partial artifact behind. A partial scrape must always be
    distinguishable from a complete one. That is the manifest's real job.

    Parameters
    ----------
    df
        Frame to persist.
    path
        Destination ``.parquet`` path. Parent directories are created.
    schema
        Schema the frame must satisfy.
    source
        Provenance label, e.g. ``"fbref"``.
    extra
        Additional key-value pairs to record in the manifest.

    Returns
    -------
    Path
        The path written.

    Raises
    ------
    gambeta.laws.ValidationError
        If ``df`` does not satisfy ``schema``. No file is written.
    """
    validated = schema.validate(df)

    import soccerdata

    path.parent.mkdir(parents=True, exist_ok=True)
    validated.to_parquet(path, index=False)

    manifest = {
        "source": source,
        "written_at": datetime.now(UTC).isoformat(),
        "rows": int(len(validated)),
        "columns": list(validated.columns),
        "soccerdata_version": soccerdata.__version__,
        **(extra or {}),
    }
    manifest_path(path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def read(path: Path, schema: pa.DataFrameSchema) -> pd.DataFrame:
    """Read a Parquet file and validate it against ``schema``."""
    validated: pd.DataFrame = schema.validate(pd.read_parquet(path))
    return validated
