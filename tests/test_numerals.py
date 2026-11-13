from __future__ import annotations

import pytest

from arabic_bib import cardinal_value, ordinal_value, ordinal_word
from arabic_bib.numerals import parse_number


@pytest.mark.parametrize("n", range(1, 100))
@pytest.mark.parametrize("feminine", [False, True])
def test_ordinal_round_trip(n: int, feminine: bool) -> None:
    assert ordinal_value(ordinal_word(n, feminine)) == n
    assert ordinal_value(ordinal_word(n, feminine, article=False)) == n


ORD = [
    ("الأولى", 1), ("الاولى", 1), ("الأولي", 1), ("أولى", 1), ("الثانية", 2), ("ثانية", 2), ("الثالثه", 3),
    ("العاشرة", 10), ("الحادية عشرة", 11), ("الحادي عشر", 11), ("الثانية عشرة", 12), ("الخامسة عشر", 15),
    ("العشرون", 20), ("العشرين", 20), ("الحادية والعشرون", 21), ("الخامسة والعشرون", 25), ("الثلاثون", 30),
    ("الرابع عشر", 14), ("الثامن", 8), ("4", 4), ("٤", 4), ("۱۲", 12),
]


@pytest.mark.parametrize("text, n", ORD)
def test_ordinal_spellings(text: str, n: int) -> None:
    assert ordinal_value(text) == n


@pytest.mark.parametrize("text", ["", "جديدة", "منقحة", "الكتاب"])
def test_not_ordinal(text: str) -> None:
    assert ordinal_value(text) is None


CARD = [
    ("ثمان وعشرين وسبعمائة", 728), ("ست وخمسين ومائتين", 256), ("إحدى عشرة وتسعمائة", 911),
    ("أربع ومائتين", 204), ("عشر وثلاثمائة", 310), ("خمس وخمسمائة", 505), ("اثنتين وخمسين وثمانمائة", 852),
    ("ثلاث وأربعين وستمائة", 643), ("تسع وسبعين ومائة", 179), ("خمسين ومائة", 150), ("إحدى وأربعين ومائتين", 241),
    ("ست وخمسين وسبعمائة", 756), ("ثلاث مائة", 300), ("ثلاثمئة", 300), ("مائة", 100), ("مائتين", 200),
    ("ألف", 1000), ("ست وخمسين وتسعمائة وألف", 1956), ("سنة أربع وخمسين ومائتين", 254), ("اثنتي عشرة وستمائة", 612),
    ("سبع عشرة وثمانمئة", 817), ("تسعين وأربعمائة", 490), ("إحدى وثمانين وستمائة", 681), ("خمس وتسعين وخمسمائة", 595),
    ("عشرين ومائتين", 220), ("ثمانين", 80), ("ست", 6),
]


@pytest.mark.parametrize("text, n", CARD)
def test_cardinal(text: str, n: int) -> None:
    assert cardinal_value(text) == n


@pytest.mark.parametrize("text", ["", "الكتاب", "ثمان وكتاب"])
def test_not_cardinal(text: str) -> None:
    assert cardinal_value(text) is None


def test_parse_number() -> None:
    assert parse_number("١٤٢٠") == 1420
    assert parse_number("الثالثة") == 3
    assert parse_number("ثلاث وعشرين") == 23
    assert parse_number("") is None
    with pytest.raises(ValueError):
        ordinal_word(100)
