"""Catalogue keys v1 are frozen: work ids in turath-catalog and turath-match are hashed from them.

The reference below is the recipe written out independently; arabic-bib must agree with it byte for byte."""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pytest

from arabic_bib import author_key, key_norm, title_key

AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TITLES = re.compile(r"^(?:(?:الإمام|الامام|الحافظ|الشيخ|العلامة|العلامه|شيخ الإسلام|شيخ الاسلام|القاضي|الأستاذ|الدكتور|د)\.?\s+)+")


def ref_norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub("[ً-ْٰـ]", "", s)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ؤ", "و"), ("ئ", "ي"), ("ء", "")):
        s = s.replace(a, b)
    s = s.translate(AR)
    s = re.sub("[^ء-ي0-9 ]", " ", s)
    return " ".join(s.split())


def ref_title_key(t: str) -> str:
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t or "")
    t = re.split(r"\s+-\s+|\s+ط\s|\s+ت\s", " " + t + " ")[0]
    w = ref_norm(t).split()
    if w and w[0] == "كتاب" and len(w) > 1:
        w = w[1:]
    return " ".join(w)


def ref_author_key(a: str) -> str:
    a = re.split(r"[؛;]", a or "")[0].strip()
    return ref_norm(TITLES.sub("", a))


TITLES_IN = [
    "كتاب الأمّ (ط. دار المعرفة) - الشافعي", "الجامع لأحكام القرآن = تفسير القرطبي", "كتاب", "كتاب سيبويه",
    "مجموع الفتاوى ط مجمع الملك فهد", "الرسالة ت أحمد شاكر", "القُرْآنُ الكَرِيمُ", "ﺟﻬﺎﺩ النفس", "Les Misérables",
    "شرح العقيدة الطحاوية [نسخة]", "سؤالات الآجري لأبي داود", "إحياء علوم الدين ٤", "تاريخ بغداد ـ الخطيب",
    "مسائل الإمام أحمد رواية ابنه عبد الله", "الفوائد/ابن القيم", "الإبانة عن أصول الديانة", "مِئَة وأربعون",
    "", "   ", "رؤى وأفكار", "الكامل في التاريخ: ابن الأثير", "مُسْنَد الإمام أحمد بن حنبل - ت شعيب الأرنؤوط",
]
AUTHORS_IN = [
    "الإمام الشاشي؛ إسحاق بن إبراهيم", "شيخ الإسلام ابن تيمية", "الحافظ الشيخ ابن حجر", "د. محمد عمارة",
    "الدكتور طه حسين", "القاضي عياض", "ابن تيمية (ت 728 هـ)", "العلامة ابن عثيمين; محمد بن صالح",
    "الأستاذ محمود شاكر", "الإمامُ مالك", "أبو الفداء إسماعيل بن كثير", "محمد بن یوسف", "", "الشيخ",
    "شيخ الاسلام تقي الدين", "د.أحمد", "ابن قيّم الجوزيّة",
]


@pytest.mark.parametrize("t", TITLES_IN)
def test_title_key_v1(t: str) -> None:
    assert title_key(t) == ref_title_key(t)


@pytest.mark.parametrize("a", AUTHORS_IN)
def test_author_key_v1(a: str) -> None:
    assert author_key(a) == ref_author_key(a)


@pytest.mark.parametrize("s", TITLES_IN + AUTHORS_IN)
def test_key_norm_v1(s: str) -> None:
    assert key_norm(s) == ref_norm(s)


def test_work_id_is_stable() -> None:
    wid = "w_" + hashlib.sha1(unicodedata.normalize("NFC", f"{title_key('كتاب الأمّ')}|{author_key('الإمام الشافعي')}").encode()).hexdigest()[:10]
    assert wid == "w_" + hashlib.sha1("الام|الشافعي".encode()).hexdigest()[:10]
