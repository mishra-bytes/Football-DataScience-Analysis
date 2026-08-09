"""Player identity resolution.

The project's highest-risk component. FBref exposes no player ID at season level
(see ``DEVIATIONS.md`` #1), so identity is built from ``(normalized_name, born)``
and enriched with a Wikidata QID where both name and birth year agree.

The cardinal rule: a player who cannot be matched is **reported**, never
dropped. Silently discarding an unmatched row does not raise an error — it just
quietly deletes a career from the analysis, and no test would ever notice.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

_WHITESPACE = re.compile(r"\s+")
_ID_LENGTH = 12


def normalize(name: str) -> str:
    """Fold accents, collapse whitespace, and lowercase a player name.

    FBref and Wikidata disagree routinely on diacritics — "Fàbregas" against
    "Fabregas" — so both sides are folded to a common form before matching.
    """
    decomposed = unicodedata.normalize("NFKD", str(name))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _WHITESPACE.sub(" ", stripped).strip().lower()


def player_id(name: str, born: float | None) -> str:
    """Return a stable identifier for a player.

    Derived from the normalized name plus birth year, so one person keeps a
    single identifier across clubs and seasons while two people who share a name
    stay separate.

    Parameters
    ----------
    name
        Player name as recorded by the source.
    born
        Birth year, or ``None``/``NaN`` when the source omits it.
    """
    year = "" if born is None or pd.isna(born) else str(int(born))
    digest = hashlib.sha1(f"{normalize(name)}|{year}".encode()).hexdigest()
    return digest[:_ID_LENGTH]


def resolve(raw: pd.DataFrame, crosswalk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach ``player_id`` and, where possible, a Wikidata ``qid``.

    Parameters
    ----------
    raw
        Frame with at least ``player`` and ``born`` columns.
    crosswalk
        Wikidata crosswalk conforming to :data:`gambeta.laws.CROSSWALK`.

    Returns
    -------
    labelled : pd.DataFrame
        ``raw`` plus ``player_id`` and ``qid``, where ``qid`` is null when no
        confident match exists. Always the same length as ``raw``.
    unresolved : pd.DataFrame
        One row per distinct unmatched player, for reporting.
    """
    df = raw.copy()
    df["player_id"] = [
        player_id(name, born) for name, born in zip(df["player"], df["born"], strict=True)
    ]
    df["_key"] = df["player"].map(normalize)
    df["_year"] = pd.to_numeric(df["born"], errors="coerce").astype("Int64")

    lookup = crosswalk.copy()
    lookup["_key"] = lookup["label"].map(normalize)
    lookup["_year"] = lookup["birth_year"].astype("Int64")
    # Keep one QID per (name, year) so the merge can never fan out the left side.
    lookup = lookup.drop_duplicates(subset=["_key", "_year"])[["_key", "_year", "qid"]]

    merged = df.merge(lookup, on=["_key", "_year"], how="left")

    unresolved = (
        merged.loc[merged["qid"].isna(), ["player", "born", "player_id"]]
        .drop_duplicates(subset="player_id")
        .reset_index(drop=True)
    )
    return merged.drop(columns=["_key", "_year"]), unresolved
