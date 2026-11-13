"""The labelled author-pair set: accuracy is measured, not asserted pair by pair (see bench/)."""

from __future__ import annotations

import pytest
from tables import load

from arabic_bib import AuthorMatch, author_similarity, match_authors, parse_author, same_author, same_person, same_publisher
from arabic_bib.authors import publisher_family

PAIRS = load("author_pairs.tsv")


def test_accuracy_floor() -> None:
    ok = sum(match_authors(a, b).verdict == v for a, b, v, *_ in PAIRS)
    assert len(PAIRS) >= 170
    assert ok / len(PAIRS) >= 0.95


def test_no_false_merge_of_different_people() -> None:
    """«same» on a pair labelled «different» is the costly error: at most one in the set."""
    bad = [(a, b) for a, b, v, *_ in PAIRS if v == "different" and match_authors(a, b).verdict == "same"]
    assert len(bad) <= 1, bad


@pytest.mark.parametrize("row", PAIRS, ids=[f"{r[0]}~{r[1]}"[:50] for r in PAIRS])
def test_symmetric(row: list[str]) -> None:
    a, b = row[:2]
    assert match_authors(a, b).verdict == match_authors(b, a).verdict


def test_api_shapes() -> None:
    m = match_authors("ابن تيمية", "أحمد بن عبد الحليم بن تيمية الحراني")
    assert isinstance(m, AuthorMatch) and m and m.reasons
    assert same_author("ابن تيمية", parse_author("أحمد بن عبد الحليم بن تيمية"))
    assert 0.75 <= author_similarity("الذهبي", "محمد بن أحمد الذهبي") <= 1
    assert match_authors("", "ابن تيمية").verdict == "unknown"
    assert match_authors("ابن تيمية", "ابن تيمية").verdict == "same"
    assert match_authors("محمد", "محمد").verdict == "unknown"


def test_common_extends_per_catalogue() -> None:
    assert match_authors("الذهبي", "محمد بن أحمد الذهبي").verdict == "same"
    assert match_authors("الذهبي", "محمد بن أحمد الذهبي", common=["الذهبي"]).verdict == "unknown"


def test_inverted_catalogue_forms() -> None:
    assert same_author("عبد الله بن المقفع", '"إبن المقفع، عبد الله"')
    assert same_author("عبد الرحمن بن محمد بن خلدون الحضرمي", "ابن خلدون، عبد الرحمن بن محمد")


@pytest.mark.parametrize(
    "a, b, same",
    [
        ("محمد محيي الدين عبد الحميد", "الشيخ محمد محيى الدين عبد الحميد", True),
        ("أحمد محمد شاكر", "أحمد شاكر", True),
        ("محمود محمد شاكر", "أحمد محمد شاكر", True),  # the rule: two shared words; brothers need a third part
        ("عبد السلام هارون", "عبد السلام محمد هارون", True),
        ("شعيب الأرنؤوط", "عبد القادر الأرنؤوط", False),
        ("بشار عواد معروف", "د. بشار عواد", True),
        ("", "فلان", False),
    ],
)
def test_same_person(a: str, b: str, same: bool) -> None:
    assert same_person(a, b) is same


@pytest.mark.parametrize(
    "a, b, same",
    [
        ("دار الكتب العلمية - بيروت", "دار الكتب العلمية", True),
        ("دار الفكر", "دار الفكر العربي", False),
        ("دار الفكر", "دار الفكر المعاصر", False),
        ("مؤسسة الرسالة", "مؤسسة الرسالة ناشرون", True),
        ("مكتبة الحلبي", "مطبعة مصطفى البابي الحلبي", True),
        ("المطبعة الأميرية ببولاق", "المطبعة الكبرى الأميرية", True),
        ("دار إحياء الكتب العربية عيسى البابي الحلبي", "مطبعة مصطفى البابي الحلبي", False),
        ("دار المعرفة", "دار المعارف", False),
        ("دار", "دار", True),
    ],
)
def test_same_publisher(a: str, b: str, same: bool) -> None:
    assert same_publisher(a, b) is same


def test_publisher_family() -> None:
    assert publisher_family("مطبعة دائرة المعارف العثمانية بحيدر آباد") == "dairat-al-maarif"
    assert publisher_family("دار الشروق") == ""
