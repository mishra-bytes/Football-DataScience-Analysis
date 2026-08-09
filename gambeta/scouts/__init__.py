"""Source adapters. Each scout returns a tidy DataFrame matching a schema in `laws`.

Adding a source means adding one file here and changing nothing else — this
protocol is the project's extension seam.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class Scout(Protocol):
    """A data source adapter."""

    name: str

    def fetch(self) -> pd.DataFrame:
        """Retrieve the source's data as a tidy, schema-conforming frame."""
        ...
