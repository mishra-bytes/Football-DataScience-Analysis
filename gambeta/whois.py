"""Player identity resolution.

The project's highest-risk component. FBref exposes no player ID at season level
(see ``DEVIATIONS.md`` #1), so identity is built from ``(normalized_name, born)``
and enriched with a Wikidata QID where both name and birth year agree.

The cardinal rule: a player who cannot be matched is **reported**, never
dropped. Silently discarding an unmatched row does not raise an error. It just
quietly deletes a career from the analysis, and no test would ever notice.

**Matching runs in tiers.** Measured on the real data, 90% of unmatched players
had a name that was absent from the crosswalk under its exact spelling and
present under another: an extra surname (``Iván Kaviedes`` against ``Iván
Kaviedes Toaquiza``), a missing one (``Yakubu Aiyegbeni`` against ``Yakubu``), or
a shortened forename (``Matt Upson`` against ``Matthew Upson``). The exact join
runs first; whatever it leaves over is offered to the looser tiers.

Every tier is bound by the same two rules, and they are what make loosening the
name safe:

1. **The birth year never relaxes.** It is the only independent evidence in the
   record, so a tier may weaken the name and nothing else.
2. **Ambiguity is a non-match.** If a tier finds two candidates it returns
   nothing. A wrong QID is worse than a missing one, because a missing one is
   reported and a wrong one is not.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict

import pandas as pd

_WHITESPACE = re.compile(r"\s+")
# Apostrophes and full stops vanish; hyphens and slashes become spaces. The
# distinction is not cosmetic: FBref's "M'Boma" is Wikidata's "Mboma", so the
# apostrophe must close up, while "Jean-Pierre" is "Jean Pierre", so the hyphen
# must open out. Collapsing both the same way loses one of the two.
_CLOSING = re.compile(r"['’ʼ.]")
_OPENING = re.compile(r"[^a-z0-9 ]")
_ID_LENGTH = 12


def normalize(name: str) -> str:
    """Fold accents and punctuation, collapse whitespace, and lowercase a name.

    FBref and Wikidata disagree routinely on diacritics ("Fàbregas" against
    "Fabregas") and on punctuation ("M'Boma" against "Mboma"), so both sides
    are folded to a common form before matching.
    """
    decomposed = unicodedata.normalize("NFKD", str(name))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return _WHITESPACE.sub(" ", _OPENING.sub(" ", _CLOSING.sub("", stripped))).strip()


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


def _sole(candidates: set[str]) -> str | None:
    """The one candidate, or nothing. Two candidates is not a match."""
    return next(iter(candidates)) if len(candidates) == 1 else None


def _fallback_match(key: str, year: int, index: _Index) -> str | None:
    """Try each loose tier in turn against one (name, birth year) pair."""
    tokens = frozenset(key.split())
    if not tokens:
        return None

    # Tier 1: one name is contained in the other, in either direction.
    contained = {
        qid for cand, qid in index.tokens_by_year[year] if tokens <= cand or cand <= tokens
    }
    if (hit := _sole(contained)) is not None:
        return hit

    # Tier 2: same surname, same year, forename agreeing on its first letter.
    parts = key.split()
    initialled = {
        qid
        for first, qid in index.surname_by_year[parts[-1], year]
        if first and first[0] == parts[0][0]
    }
    return _sole(initialled)


class _Index:
    """Crosswalk lookups the loose tiers need, built once per resolve() call."""

    def __init__(self, lookup: pd.DataFrame) -> None:
        self.tokens_by_year: dict[int, list[tuple[frozenset[str], str]]] = defaultdict(list)
        self.surname_by_year: dict[tuple[str, int], list[tuple[str, str]]] = defaultdict(list)
        for key, year, qid in lookup.itertuples(index=False):
            if pd.isna(year) or not key:
                continue
            parts = key.split()
            self.tokens_by_year[int(year)].append((frozenset(parts), qid))
            self.surname_by_year[parts[-1], int(year)].append((parts[0], qid))


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
    lookup = lookup[["_key", "_year", "qid"]]
    # Keep one QID per (name, year) so the exact merge can never fan out the
    # left side. The loose tiers read the undeduplicated frame instead, because
    # a name with two owners in one birth year is exactly what they must refuse.
    exact = lookup.drop_duplicates(subset=["_key", "_year"])

    merged = df.merge(exact, on=["_key", "_year"], how="left")

    # Only the pairs the exact join missed reach the loose tiers, and each
    # distinct pair is decided once however many seasons it spans.
    missed = merged.loc[merged["qid"].isna(), ["_key", "_year"]].drop_duplicates()
    if len(missed):
        index = _Index(lookup)
        found = {
            (key, int(year)): _fallback_match(key, int(year), index)
            for key, year in missed.itertuples(index=False)
            if pd.notna(year)
        }
        recovered = pd.Series(
            [
                found.get((key, int(year))) if pd.notna(year) else None
                for key, year in zip(merged["_key"], merged["_year"], strict=True)
            ],
            index=merged.index,
            dtype="object",
        )
        merged["qid"] = merged["qid"].fillna(recovered)

    unresolved = (
        merged.loc[merged["qid"].isna(), ["player", "born", "player_id"]]
        .drop_duplicates(subset="player_id")
        .reset_index(drop=True)
    )
    return merged.drop(columns=["_key", "_year"]), unresolved
