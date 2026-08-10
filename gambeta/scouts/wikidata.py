"""Wikidata adapter: the player identity crosswalk.

Pulls every person carrying an FBref player ID (P5750) together with their label
and date of birth (P569). Players holding multiple citizenships return one row
per citizenship, so `parse_bindings` deduplicates on QID.

This is CC0 data and a single request — the cheapest risk reduction in the
project, given FBref exposes no player ID of its own.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import requests

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "gambeta/0.1 (football analytics research)"
COLUMNS = ["qid", "fbref_id", "label", "birth_year"]

QUERY = """
SELECT ?p ?pLabel ?fbref ?dob WHERE {
  ?p wdt:P5750 ?fbref .
  OPTIONAL { ?p wdt:P569 ?dob . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def parse_bindings(bindings: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert SPARQL JSON bindings into the crosswalk frame.

    Parameters
    ----------
    bindings
        The ``results.bindings`` list from a SPARQL JSON response.

    Returns
    -------
    pd.DataFrame
        Columns ``qid, fbref_id, label, birth_year``; one row per person.
        Conforms to :data:`gambeta.laws.CROSSWALK`.
    """
    rows = [
        {
            "qid": b["p"]["value"].rsplit("/", 1)[-1],
            "fbref_id": b.get("fbref", {}).get("value"),
            "label": b.get("pLabel", {}).get("value", ""),
            "birth_year": b["dob"]["value"][:4] if "dob" in b else None,
        }
        for b in bindings
    ]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce").astype("Int64")
    return df.drop_duplicates(subset="qid").reset_index(drop=True)


class WikidataScout:
    """Fetch the FBref-ID identity crosswalk from Wikidata."""

    name = "wikidata"

    def fetch(self) -> pd.DataFrame:
        """One SPARQL request returning roughly 30,000 footballers."""
        response = requests.get(
            ENDPOINT,
            params={"query": QUERY, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=600,
        )
        response.raise_for_status()
        # strict=False, not response.json(): the ~20 MB payload contains raw
        # control characters inside player labels, which the strict decoder
        # rejects outright — one bad byte would discard 114,000 usable rows.
        payload = json.loads(response.text, strict=False)
        bindings: list[dict[str, Any]] = payload["results"]["bindings"]
        return parse_bindings(bindings)
