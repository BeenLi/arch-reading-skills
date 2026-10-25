#!/usr/bin/env python3
"""Look up a venue's CCF rank (A / B / C).

The table in ``ccf_ranks.json`` comes from CCFrank4dblp (MIT, WenyanLiu) and
follows the 2022 CCF recommended list. It is keyed by CCF's own abbreviation;
a conference and a journal sharing one abbreviation (WWW) keep the
conference's rank.

A venue string is first normalised by ``venue_label.short_venue`` so that
"2024 ACM/IEEE 51st Annual International Symposium on Computer Architecture
(ISCA)" and "ISCA" both find ISCA. Workshops (``-W``) and companion volumes
(``-C``) are not ranked, nor are venues CCF does not list (arXiv, MLSys,
IEEE Micro, ...).
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from venue_label import _clean, short_venue  # noqa: E402

# venue_label 的缩写 → CCF 表里的写法（会议改名或写法不同）
_ALIASES = {
    "ATC": "ACM SIGOPS ATC",  # USENIX ATC 并入 ACM SIGOPS 后 CCF 用新名
    "PVLDB": "VLDB",
    "Hot Chips": "HOT CHIPS",
}


@lru_cache(maxsize=1)
def _ranks() -> dict[str, str]:
    data = json.loads((_SCRIPTS_DIR / "ccf_ranks.json").read_text(encoding="utf-8"))
    return data["ranks"]


@lru_cache(maxsize=1)
def _ranks_upper() -> dict[str, str]:
    return {abbr.upper(): rank for abbr, rank in _ranks().items()}


def ccf_rank(venue: str | None) -> str | None:
    """"A", "B", "C", or None when the venue is unknown, unranked, a workshop or a companion."""
    if not venue:
        return None
    label = short_venue(venue)
    if label and label.endswith(("-W", "-C")):
        return None
    key = label or _clean(venue)
    key = _ALIASES.get(key, key)
    return _ranks().get(key) or _ranks_upper().get(key.upper())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("venue", help="venue string, e.g. 'ISCA' or a full Zotero venue name")
    args = parser.parse_args(argv)
    rank = ccf_rank(args.venue)
    if rank is None:
        return 1
    print(rank)
    return 0


if __name__ == "__main__":
    sys.exit(main())
