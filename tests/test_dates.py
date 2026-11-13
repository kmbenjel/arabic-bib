from __future__ import annotations

import datetime as dt
import random

import pytest
from tables import load

from arabic_bib import (
    century_label,
    century_of,
    gregorian_to_hijri,
    gregorian_year_to_hijri,
    hijri_to_gregorian,
    hijri_year_to_gregorian,
    parse_death,
    strip_dates,
)
from arabic_bib.dates import find_dates

ROWS = load("deaths.tsv")
NONE = [r[0] for r in load("deaths_none.tsv")]


def _i(s: str) -> int | None:
    return int(s) if s else None


@pytest.mark.parametrize("row", ROWS, ids=[r[0] for r in ROWS])
def test_parse_death(row: list[str]) -> None:
    text, h, g, bh, bg, q, c, alive, label = row[:9]
    d = parse_death(text)
    assert d is not None
    assert (d.hijri, d.gregorian, d.birth_hijri, d.birth_gregorian, d.qualifier, d.century, d.alive) == (
        _i(h), _i(g), _i(bh), _i(bg), q, _i(c), bool(alive))
    assert d.label() == label


@pytest.mark.parametrize("text", NONE)
def test_no_death(text: str) -> None:
    assert parse_death(text) is None


def test_assume_gregorian() -> None:
    d = parse_death("ت 1973", assume="gregorian")
    assert d and d.gregorian == 1973 and d.hijri is None


@pytest.mark.parametrize(
    "text, want",
    [
        ("ابن تيمية (ت 728 هـ)", "ابن تيمية"),
        ("الذهبي، ت 748", "الذهبي"),
        ("الذهبي (673 - 748 هـ)", "الذهبي"),
        ("السيوطي المتوفى سنة 911 هـ", "السيوطي"),
        ("طه حسين (1889 - 1973 م)", "طه حسين"),
        ("ابن تيمية", "ابن تيمية"),
        ("محمد بن صالح العثيمين (معاصر)", "محمد بن صالح العثيمين"),
    ],
)
def test_strip_dates(text: str, want: str) -> None:
    assert strip_dates(text) == want


def test_find_dates() -> None:
    ds = find_dates("ابن تيمية (ت 728 هـ) وابن القيم (ت 751 هـ)")
    assert [d.hijri for d in ds] == [728, 751]


# ------------------------------------------------------------------------------------------- the calendar
# anchors: the epoch, and dates cited in reference works (tabular calendar; Julian before 1582-10-15)
ANCHORS = [
    ((1, 1, 1), (622, 7, 16)),
    ((1, 1, 2), (622, 7, 17)),
    ((1400, 1, 1), (1979, 11, 21)),
    ((1420, 1, 1), (1999, 4, 17)),
    ((1445, 1, 1), (2023, 7, 19)),
    ((1000, 1, 1), (1591, 10, 19)),
    ((728, 11, 20), (1328, 9, 26)),
    ((1300, 1, 1), (1882, 11, 12)),
    ((1, 9, 1), (623, 3, 9)),
    ((10, 1, 1), (631, 4, 9)),
    ((500, 1, 1), (1106, 9, 2)),
    ((991, 1, 1), (1583, 1, 25)),
]


@pytest.mark.parametrize("h, g", ANCHORS)
def test_anchor_dates(h: tuple[int, int, int], g: tuple[int, int, int]) -> None:
    assert hijri_to_gregorian(*h) == g
    assert gregorian_to_hijri(*g) == h


def test_round_trip_every_day_for_a_century_range() -> None:
    rng = random.Random(7)
    for _ in range(3000):
        y, m = rng.randint(1, 1600), rng.randint(1, 12)
        d = rng.randint(1, 29)
        assert gregorian_to_hijri(*hijri_to_gregorian(y, m, d)) == (y, m, d)


def test_consecutive_days_are_consecutive() -> None:
    # 1 Muharram 1440 → 30 Dhu al-Hijja 1445, day by day, never a gap or a repeat in the Gregorian dates
    prev = None
    for y in range(1440, 1446):
        for m in range(1, 13):
            for d in range(1, 31):
                try:
                    g = dt.date(*hijri_to_gregorian(y, m, d))
                except ValueError:
                    continue
                if prev:
                    assert (g - prev).days == 1
                prev = g


def _accepts(y: int, m: int, d: int) -> bool:
    try:
        hijri_to_gregorian(y, m, d)
    except ValueError:
        return False
    return True


@pytest.mark.parametrize("cycle", [0, 1, 47])
def test_leap_years_of_the_cycle(cycle: int) -> None:
    years = range(30 * cycle + 1, 30 * cycle + 31)
    leap = [y - 30 * cycle for y in years if _accepts(y, 12, 30)]
    assert leap == [2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29]


def test_month_length_errors() -> None:
    with pytest.raises(ValueError):
        hijri_to_gregorian(1, 12, 30)  # year 1 is not a leap year
    hijri_to_gregorian(2, 12, 30)  # year 2 is
    with pytest.raises(ValueError):
        hijri_to_gregorian(1, 13, 1)
    with pytest.raises(ValueError):
        gregorian_to_hijri(600, 1, 1)
    with pytest.raises(ValueError):
        hijri_to_gregorian(1, 1, 1, calendar="lunar")


def test_proleptic() -> None:
    assert hijri_to_gregorian(728, 11, 20, proleptic=True) == (1328, 10, 4)
    assert gregorian_to_hijri(1328, 10, 4, proleptic=True) == (728, 11, 20)


@pytest.mark.parametrize(
    "h, g",
    [(728, (1327, 1328)), (1400, (1979, 1980)), (1, (622, 623)), (256, (869, 870)), (1420, (1999, 2000))],
)
def test_year_spans(h: int, g: tuple[int, int]) -> None:
    assert hijri_year_to_gregorian(h) == g


@pytest.mark.parametrize("g, h", [(1999, (1419, 1420)), (2000, (1420, 1421)), (1328, (728, 729))])
def test_gregorian_year_spans(g: int, h: tuple[int, int]) -> None:
    assert gregorian_year_to_hijri(g) == h


@pytest.mark.parametrize("y, c", [(1, 1), (100, 1), (101, 2), (700, 7), (701, 8), (728, 8), (1445, 15)])
def test_century_of(y: int, c: int) -> None:
    assert century_of(y) == c


def test_century_label() -> None:
    assert century_label(8) == "القرن الثامن الهجري"
    assert century_label(14, "م") == "القرن الرابع عشر الميلادي"
    assert century_label(11, "") == "القرن الحادي عشر"
    with pytest.raises(ValueError):
        century_of(0)


convertdate = pytest.importorskip("convertdate")


def test_against_convertdate() -> None:
    """The same tabular calendar as convertdate's `islamic` module (an independent implementation)."""
    from convertdate import islamic, julian

    rng = random.Random(11)
    for _ in range(2000):
        y, m, d = rng.randint(1, 1500), rng.randint(1, 12), rng.randint(1, 29)
        g = hijri_to_gregorian(y, m, d)
        jd = islamic.to_jd(y, m, d)
        if g < (1582, 10, 15):
            assert julian.from_jd(jd) == g
        else:
            from convertdate import gregorian

            assert gregorian.from_jd(jd) == g
