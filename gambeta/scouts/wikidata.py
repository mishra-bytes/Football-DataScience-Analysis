"""Wikidata adapter: the player identity crosswalk, and individual honours.

Pulls every association footballer born in the era this project covers, together
with a Latin-script label, date of birth, and an FBref player ID where one
exists. Players holding multiple citizenships return one row per citizenship, so
`parse_bindings` deduplicates on QID.

**Occupation is the anchor, not the FBref ID.** The obvious query — "everyone
carrying P5750" — was measured against the real data and threw away 56% of the
candidates: 114,084 people carry an FBref ID, 261,725 footballers of the right
age exist, and Modrić, Puyol, Handanović and Weidenfeller are all in the second
group. Since :func:`gambeta.whois.resolve` joins on ``(name, birth year)`` and
has never once used ``fbref_id``, requiring the property bought nothing and cost
half the pool. It is kept as an optional column for provenance.

**The label service is asked for Latin scripts only.** With ``language "en"``
alone it silently returns the bare QID for anyone lacking an English label —
328 crosswalk rows were literally named ``Q483837``, which is Luka Modrić. A
Cyrillic or Greek label is no more useful than that, since it cannot be folded
onto FBref's Latin spelling, so the fallback chain lists Latin-script languages
and nothing else.

One query per birth year, because a single unrestricted query times out: the
service caps at 60 s and the whole population needs roughly 40 s per year.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

log = logging.getLogger("gambeta")

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "gambeta/0.1 (football analytics research)"
COLUMNS = ["qid", "fbref_id", "label", "birth_year"]

BIRTH_YEARS = range(1965, 2006)
"""Nobody younger than 15 or older than 45 plays a Big-5 season in 2000-2025."""

_LANGS = (
    "en,es,de,fr,it,pt,nl,ca,gl,eu,hr,sl,pl,cs,sk,tr,da,sv,nb,nn,fi,"
    "ro,hu,sq,bs,id,af,et,lv,lt,is,mt,cy,ga,vi"
)

_YEAR = "__YEAR__"

_MONTHS = "__MONTHS__"

QUERY = f"""
SELECT ?p ?pLabel ?fbref ?dob WHERE {{
  ?p wdt:P106 wd:Q937857 ; wdt:P569 ?dob .
  OPTIONAL {{ ?p wdt:P5750 ?fbref }}
  FILTER(YEAR(?dob) = {_YEAR}{_MONTHS})
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{_LANGS}". }}
}}
"""

HALVES: tuple[tuple[int, int], ...] = ((1, 6), (7, 12))
"""Birth-month ranges used to halve a year that will not come back whole."""

_BARE_QID = re.compile(r"^Q\d+$")
_ATTEMPTS = 3
_BACKOFF = 5.0


def query_for(year: int, months: tuple[int, int] | None = None) -> str:
    """Return the SPARQL query for footballers born in ``year``.

    ``months`` narrows it to a range of birth months, halving the payload for a
    cohort too large to come back inside the service's time limit.
    """
    clause = (
        "" if months is None else f" && MONTH(?dob) >= {months[0]} && MONTH(?dob) <= {months[1]}"
    )
    return QUERY.replace(_YEAR, str(year)).replace(_MONTHS, clause)


def parse_bindings(bindings: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert SPARQL JSON bindings into the crosswalk frame.

    Rows whose label came back as a bare QID are dropped: that is the label
    service reporting a failed lookup, not a name, and such a row can never
    match a player.

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
    df = df[~df["label"].str.fullmatch(_BARE_QID, na=False)]
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce").astype("Int64")
    return df.drop_duplicates(subset="qid").reset_index(drop=True)


def ask(query: str, what: str) -> list[dict[str, Any]]:
    """Run one SPARQL query, retried. The query service returns 502 and 504 freely.

    **Every retry varies the query text, and that is load-bearing.** When the
    service times out mid-stream it does not fail: it has already sent
    ``200 OK``, so it appends a Java stack trace to the half-written JSON body
    and caches the result. ``raise_for_status`` sees a success, the parse fails
    at the exact same byte on every attempt, and an identical retry replays the
    identical corruption from cache. Measured on birth year 1990: three attempts
    all died at char 2,767,040 of a 2.77 MB body, while the same query with a
    comment appended returned 4.30 MB and 9,893 clean rows. A comment changes
    the cache key and nothing else.

    An exhausted query yields an empty list rather than raising: one missing
    birth-year cohort costs a few matches, whereas aborting costs the whole
    half-hour fetch. The caller is expected to notice and say so.
    """
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            response = requests.get(
                ENDPOINT,
                params={
                    "query": query if attempt == 1 else f"{query}\n# attempt {attempt}\n",
                    "format": "json",
                },
                headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
                timeout=300,
            )
            response.raise_for_status()
            # strict=False, not response.json(): the payload contains raw
            # control characters inside player labels, which the strict decoder
            # rejects outright — one bad byte would discard the whole page.
            payload = json.loads(response.text, strict=False)
            bindings: list[dict[str, Any]] = payload["results"]["bindings"]
            return bindings
        except (requests.RequestException, ValueError, KeyError) as exc:
            log.warning("wikidata %s attempt %d/%d: %s", what, attempt, _ATTEMPTS, exc)
            if attempt == _ATTEMPTS:
                return []
            time.sleep(_BACKOFF * attempt)
    return []


AWARDS: dict[str, str] = {
    "Q166177": "Ballon d'Or",
    "Q2291862": "FIFA Ballon d'Or",
    "Q182529": "FIFA World Player of the Year",
    "Q28156245": "The Best FIFA Men's Player",
    "Q260117": "UEFA Men's Player of the Year",
}
"""The awards that between them cover 2000-2025 without a gap.

France Football's Ballon d'Or and FIFA's world player award merged for 2010-2015
and split again afterwards, so no single award spans the window. Taking all five
is not double counting — it is the contemporaneous consensus, and where two
bodies disagreed in the same year that disagreement is itself evidence.
"""

AWARDS_QUERY = """
SELECT ?p ?award ?when WHERE {
  VALUES ?award { __AWARDS__ }
  ?p p:P166 ?statement ; wdt:P21 wd:Q6581097 .
  ?statement ps:P166 ?award .
  OPTIONAL { ?statement pq:P585 ?when }
}
"""
"""Winners of the tracked awards, restricted to men's football.

The P21 filter matches the project's declared scope — the Big 5 men's domestic
leagues — and without it the check misreports itself. Wikidata attaches several
of these award items to women's winners too, so Birgit Prinz, Carli Lloyd and
Aitana Bonmatí arrived counted as "winners our data is missing" when their
absence is correct and by design.
"""


def parse_awards(bindings: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert award-winner bindings into the honours frame.

    Returns
    -------
    pd.DataFrame
        Columns ``qid, award, year``; one row per person per award per year.
        Conforms to :data:`gambeta.laws.AWARDS`.
    """
    rows = [
        {
            "qid": b["p"]["value"].rsplit("/", 1)[-1],
            "award": AWARDS.get(
                b["award"]["value"].rsplit("/", 1)[-1], b["award"]["value"].rsplit("/", 1)[-1]
            ),
            # An unbound OPTIONAL usually omits the key, but a null has been
            # seen too; this is a trust boundary, so handle both.
            "year": (b.get("when") or {}).get("value", "")[:4] or None,
        }
        for b in bindings
    ]
    df = pd.DataFrame(rows, columns=["qid", "award", "year"])
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df.drop_duplicates().reset_index(drop=True)


class AwardsScout:
    """Fetch individual honours — the only outside opinion in the project."""

    name = "wikidata-awards"

    def fetch(self) -> pd.DataFrame:
        """One query for all five awards; a few thousand rows."""
        values = " ".join(f"wd:{qid}" for qid in AWARDS)
        out = parse_awards(ask(AWARDS_QUERY.replace("__AWARDS__", values), "awards"))
        log.warning("awards: %d honours across %d people", len(out), out["qid"].nunique())
        return out


def query_fingerprint() -> str:
    """Short hash of the query text, used as part of the cache key.

    Change what you ask for and every cached page stops matching, which is the
    behaviour you want: a cached answer to a different question is a wrong
    answer, not a saving.
    """
    return hashlib.sha1(QUERY.encode()).hexdigest()[:8]


class WikidataScout:
    """Fetch the footballer identity crosswalk from Wikidata.

    **One birth year per file on disk, exactly as the FBref scout caches one
    HTML page per league-season-table.** Without it the fetch was all or
    nothing: 41 requests and roughly 35 minutes, repeated in full whenever a
    single cohort failed or the run was interrupted. Two of 41 years came back
    empty on one run and repairing them cost another complete pass.

    The cache key includes a fingerprint of the query, so editing the question
    invalidates the answers rather than silently mixing them.
    """

    name = "wikidata"

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir

    def _cached(self, year: int) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"crosswalk_{query_fingerprint()}_{year}.parquet"

    def _page(self, year: int) -> list[dict[str, Any]]:
        """One birth year, split in half if it will not come back whole.

        Cache-busting rescues a year whose cached response was corrupt, but not
        one whose result set genuinely takes longer than the service allows: the
        biggest cohorts run 36-41 s against a 60 s cap, so under load they tip
        over however many times they are asked. Halving by birth month puts each
        request comfortably inside the limit.

        This is not hypothetical. 1985 was lost on two consecutive full runs, and
        1985 is when Cristiano Ronaldo and Luka Modrić were born — so the cost of
        skipping the fallback was the second name in our own ranking going
        unresolved.
        """
        whole = ask(query_for(year), str(year))
        if whole:
            return whole

        log.warning("wikidata %d: retrying in halves", year)
        split: list[dict[str, Any]] = []
        for months in HALVES:
            split.extend(ask(query_for(year, months), f"{year} months {months[0]}-{months[1]}"))
        return split

    def year(self, year: int) -> pd.DataFrame:
        """One birth year, read from disk when it is already there.

        A cached year costs no request, so a repair run fetches only the cohorts
        that actually failed and an interrupted run resumes where it stopped.
        Nothing is written for an empty result: that is a failure to retry next
        time, not an answer to remember.
        """
        path = self._cached(year)
        if path is not None and path.exists():
            cached: pd.DataFrame = pd.read_parquet(path)
            log.info("wikidata %d: %d people (cached)", year, len(cached))
            return cached

        page = parse_bindings(self._page(year))
        log.info("wikidata %d: %d people", year, len(page))
        if path is not None and len(page):
            path.parent.mkdir(parents=True, exist_ok=True)
            page.to_parquet(path, index=False)
        return page

    def fetch(self) -> pd.DataFrame:
        """One request per uncached birth year, roughly 260,000 footballers.

        A year that fails every retry is logged and skipped rather than aborting
        the run: a crosswalk missing one cohort still resolves everyone else, and
        the players it would have matched are reported as unresolved downstream.
        """
        parts: list[pd.DataFrame] = []
        empty: list[int] = []
        for year in BIRTH_YEARS:
            page = self.year(year)
            if len(page):
                parts.append(page)
            else:
                empty.append(year)

        if not parts:
            raise RuntimeError("wikidata returned nothing for any birth year")

        # A birth year that came back empty is a hole in the crosswalk, and every
        # player born in it will be reported unresolved for a reason that has
        # nothing to do with the player. Silence here would look exactly like a
        # genuine identity failure, so it is said out loud.
        if empty:
            log.warning(
                "wikidata: NO DATA for birth years %s - players born then cannot resolve",
                ", ".join(str(y) for y in empty),
            )

        out = pd.concat(parts, ignore_index=True).drop_duplicates(subset="qid")
        log.warning("wikidata crosswalk: %d people across %d years", len(out), len(parts))
        return out.reset_index(drop=True)
