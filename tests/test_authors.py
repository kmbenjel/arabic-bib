from __future__ import annotations

import pytest
from tables import load, lst

from arabic_bib import parse_author

ROWS = load("authors.tsv")


@pytest.mark.parametrize("row", ROWS, ids=[r[0][:40] for r in ROWS])
def test_parse_author(row: list[str]) -> None:
    name, ism, kunya, nasab, laqab, nisba, shuhra, death = row[:8]
    a = parse_author(name)
    got = (a.ism, a.kunya, a.nasab, a.laqab, a.nisba, a.shuhra, a.death)
    want = (ism, kunya, lst(nasab), lst(laqab), lst(nisba), shuhra, int(death) if death else None)
    assert got == want
