from __future__ import annotations

import unicodedata

import pytest
from tables import load

from arabic_bib import NormProfile, normalize, normalize_mapped, search_key, strip_diacritics, to_ascii_digits
from arabic_bib.normalize import PROFILES

ROWS = load("normalize.tsv")


@pytest.mark.parametrize("text, profile, want", ROWS, ids=[f"{r[1]}:{r[0]}" for r in ROWS])
def test_profiles(text: str, profile: str, want: str) -> None:
    assert normalize(text, profile) == want


def test_search_key_is_search_profile() -> None:
    for text, _, _ in ROWS:
        assert search_key(text) == normalize(text, "search")


def test_display_puts_marks_in_canonical_order() -> None:
    a = "مَّ"  # meem + fatha + shadda
    b = "مَّ"  # meem + shadda + fatha
    assert normalize(a, "display") == normalize(b, "display") == unicodedata.normalize("NFC", a)


def test_mapped_offsets_point_into_the_original() -> None:
    src = "قالَ الإمامُ أبو حامدٍ الغزاليّ: «الإحياء»"
    m = normalize_mapped(src)
    assert m.text == "قال الامام ابو حامد الغزالي الاحيا"
    assert len(m.offsets) == len(m.text)
    for i, ch in enumerate(m.text):
        if ch != " ":
            o = m.original[m.offsets[i]]
            assert search_key(o) in (ch, "")  or ch in search_key(unicodedata.normalize("NFD", o))
    spans = m.find("الغزالي")
    assert [src[a:b] for a, b in spans] == ["الغزاليّ"]
    assert [src[a:b] for a, b in m.find("ابو حامد")] == ["أبو حامدٍ"]
    assert m.find("") == []


def test_mapped_presentation_ligature() -> None:
    m = normalize_mapped("ﻻ")
    assert m.text == "لا" and m.offsets == (0, 0)
    assert m.original_span(0, 2) == (0, 1)


def test_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unknown normalisation profile"):
        normalize("x", "nope")


def test_custom_profile() -> None:
    p = PROFILES["search"].but(alef_maqsura=False)
    assert normalize("موسى", p) == "موسى"
    assert normalize("موسى", NormProfile(tatweel=False)) == "موسى"


def test_helpers() -> None:
    assert to_ascii_digits("١٤٢٠ / ۱۹۹۹") == "1420 / 1999"
    assert strip_diacritics("مُحَمَّدٌ") == "محمد"
    assert normalize(None) == ""
    assert normalize_mapped("").original_span(0, 0) == (0, 0)
