from __future__ import annotations

import pytest
from tables import load, lst

from arabic_bib import parse_edition

ROWS = load("editions.tsv")


def _i(s: str) -> int | None:
    return int(s) if s.strip() else None


@pytest.mark.parametrize("row", ROWS, ids=[r[0][:40] for r in ROWS])
def test_parse_edition(row: list[str]) -> None:
    text, number, pub, city, country, h, g, editors, role, contrib, kind = row[:11]
    e = parse_edition(text.replace("\\n", "\n"))
    got = (e.number, e.publisher, e.city, e.country, e.hijri, e.gregorian, e.editors, e.role, e.contributors, e.kind)
    want = (_i(number), pub, city, country, _i(h), _i(g), lst(editors), role, lst(contrib), kind)
    assert got == want


def test_empty() -> None:
    e = parse_edition("")
    assert e.number is None and e.publisher == "" and e.as_dict()["editors"] == []


def test_unknown_piece_is_kept() -> None:
    e = parse_edition("دار الفكر، بيروت، مزيدة بفهارس")
    assert e.publisher == "دار الفكر" and e.rest == ("مزيدة بفهارس",)
