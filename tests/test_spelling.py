from __future__ import annotations

import pytest
from tables import load

from arabic_bib import fix_wasl, safe_filename, wasl_errors
from arabic_bib.spelling import has_presentation_forms

ROWS = load("wasl.tsv")


@pytest.mark.parametrize("text, fixed", ROWS, ids=[r[0] for r in ROWS])
def test_fix_wasl(text: str, fixed: str) -> None:
    assert fix_wasl(text) == fixed
    assert bool(wasl_errors(text)) == (text != fixed)


def test_error_spans() -> None:
    t = "كتاب الإستغفار وإسم الله"
    es = wasl_errors(t)
    assert [(t[e.start:e.end], e.suggestion) for e in es] == [("الإستغفار", "الاستغفار"), ("وإسم", "واسم")]


SAFE = [
    ('ديوان المتنبي: شرح "العكبري" 1276 هـ / 1860?', "ديوان المتنبي شرح «العكبري» 1276 هـ 1860؟"),
    ("a/b\\c|d", "a b c d"),
    ("  نقطة. ", "نقطة"),
    ("..مخفي", "مخفي"),
    ("نجمة*", "نجمة"),
    ("<وسم>", "وسم"),
    ("ﺟﻬﺎﺩ", "جهاد"),
    ("یوسف", "يوسف"),
    ("سؤال (؟)", "سؤال"),
    ("CON", "_CON"),
    ("nul.txt", "_nul.txt"),
    ("tab\there", "tabhere"),
    ("ok", "ok"),
]


@pytest.mark.parametrize("name, want", SAFE)
def test_safe_filename(name: str, want: str) -> None:
    assert safe_filename(name) == want


def test_safe_filename_bytes() -> None:
    long = " ".join(["كلمة"] * 60)
    s = safe_filename(long, 100)
    assert len(s.encode()) <= 100 and not s.endswith(" ") and s.split()[-1] == "كلمة"
    s = safe_filename(long, 100, extension=".pdf")
    assert s.endswith(".pdf") and len(s.encode()) <= 100
    one = "ا" * 200
    assert len(safe_filename(one, 101).encode()) <= 101
    assert safe_filename("(أ)", keep_parentheses=False) == "أ"


def test_presentation_forms() -> None:
    assert has_presentation_forms("ﺟﻬﺎﺩ") and not has_presentation_forms("جهاد")
