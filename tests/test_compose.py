from __future__ import annotations

import pytest
from tables import load, lst

from arabic_bib import Book, NameProfile, compose, explain, parse_name, volume, volumes
from arabic_bib.compose import B, cuts, get_profile, keep_label, name_forms, split_title, title_options

ROWS = load("compose.tsv")


@pytest.mark.parametrize("row", ROWS, ids=[f"{r[3] or 'full'}:{r[0][:30]}" for r in ROWS])
def test_compose_table(row: list[str]) -> None:
    title, author, edition, limit, want, gave = row[:6]
    r = explain(Book.parse(title, author, edition), limit=int(limit) if limit else None)
    assert r.name == want
    assert r.gave_way == lst(gave)
    assert r.fits and B(r.name) <= (int(limit) if limit else get_profile("warraq").limit)


@pytest.mark.parametrize("row", ROWS, ids=[f"{r[3] or 'full'}:{r[0][:30]}" for r in ROWS])
def test_rules_hold(row: list[str]) -> None:
    """Whatever the limit: no brackets, commas, «=», never «ط», never a trailing particle."""
    name = row[4]
    assert not any(c in name for c in "()[],،=")
    assert " ط " not in f" {name} "
    assert not name.endswith((" في", " من", " على", " و", " بن"))


def test_nothing_is_cut_when_it_fits() -> None:
    b = Book.parse("الرسالة", "محمد بن إدريس الشافعي", "تحقيق أحمد محمد شاكر، مكتبة مصطفى البابي الحلبي، القاهرة")
    assert explain(b).gave_way == ()
    assert compose(b) == "الرسالة - محمد بن إدريس الشافعي - ت أحمد محمد شاكر - مكتبة مصطفى البابي الحلبي القاهرة"


def test_profiles() -> None:
    b = Book.parse("الأم (رواية الربيع)", "الشافعي", "دار المعرفة، بيروت")
    assert compose(b) == "الأم رواية الربيع - الشافعي - دار المعرفة بيروت"
    assert compose(b, profile="plain") == "الأم (رواية الربيع) - الشافعي - ط دار المعرفة بيروت"
    assert compose(b, profile="author-first") == "الشافعي - الأم (رواية الربيع) - ط دار المعرفة بيروت"
    custom = NameProfile(name="mine", template="{title}[ ({author})]", max_bytes=100)
    assert compose(b, profile=custom) == "الأم (رواية الربيع) (الشافعي)"
    with pytest.raises(ValueError, match="unknown naming profile"):
        compose(b, profile="nope")


def test_equals_and_kinds() -> None:
    assert compose("الجامع لأحكام القرآن = تفسير القرطبي", "القرطبي") == "الجامع لأحكام القرآن أو تفسير القرطبي"
    assert compose("رسالة في الفقه (مخطوط)", "اليوسي") == "رسالة في الفقه - اليوسي - مخطوط"
    assert compose("الكتاب", "التويجري (1413 هـ)") == "الكتاب - التويجري"
    assert compose("الأم", "الشافعي", year="1321 هـ", publisher="المطبعة الأميرية", city="بولاق") == (
        "الأم - الشافعي - المطبعة الأميرية بولاق 1321 هـ")
    assert compose("الأم", "الشافعي؛ محمد بن إدريس الشافعي") == "الأم - محمد بن إدريس الشافعي"


def test_city_and_year_go_with_their_publisher() -> None:
    b = Book("عنوان طويل جدا جدا", "مؤلف", ("محقق الكتاب",), publisher="دار نشر طويلة الاسم جدا", city="بيروت",
             year="1950")
    r = explain(b, limit=B("عنوان طويل جدا جدا - مؤلف - ت محقق الكتاب - بيروت"))
    assert "بيروت" not in r.name and "1950" not in r.name


def test_several_authors() -> None:
    b = Book("ديوان الشعراء الثلاثة", "أحمد شوقي وحافظ إبراهيم وخليل مطران")
    assert compose(b) == "ديوان الشعراء الثلاثة - أحمد شوقي وحافظ إبراهيم وخليل مطران"


def test_volume_and_volumes() -> None:
    v = volume("03", Book("الجامع لأحكام القرآن", "القرطبي"), "سورة البقرة")
    assert v == "03 - الجامع لأحكام القرآن - القرطبي - سورة البقرة"
    b = Book.parse("الجامع لأحكام القرآن", "القرطبي", "ت أحمد البردوني وإبراهيم أطفيش - دار الكتب المصرية القاهرة")
    vs = volumes(b, [("00", "الواجهة"), ("01", "الفاتحة - البقرة"), ("21", "الفهارس")])
    assert vs[1] == "01 - الجامع لأحكام القرآن - القرطبي - ت أحمد البردوني وإبراهيم أطفيش - دار الكتب المصرية القاهرة"
    assert vs[0].endswith(" - الواجهة") and vs[2].endswith(" - الفهارس")
    assert len({v.split(" - ", 1)[1].removesuffix(" - الواجهة").removesuffix(" - الفهارس") for v in vs}) == 1
    long = Book("ا" * 30 + " " + "ب" * 30 + " في " + "ج" * 40, "مؤلف")
    vs = volumes(long, [("01", ""), ("02", "الفهارس")], profile=NameProfile(name="t", max_bytes=120))
    assert all(len(v.encode()) <= 120 - 4 for v in vs)


@pytest.mark.parametrize(
    "label, kept",
    [("الواجهة", "الواجهة"), ("(المقدمة)", "المقدمة"), ("الفهارس", "الفهارس"), ("الفهارس 2", "الفهارس 2"),
     ("ملحق 1", "ملحق 1"), ("صور المخطوطات", "صور المخطوطات"), ("إحياء الموات - أمهات الأولاد", ""),
     ("سورة البقرة", ""), ("", "")],
)
def test_keep_label(label: str, kept: str) -> None:
    assert keep_label(label) == kept


@pytest.mark.parametrize(
    "title, want",
    [
        ("الاستذكار الجامع لمذاهب فقهاء الأمصار", ["الاستذكار الجامع"]),
        ("بداية المجتهد ونهاية المقتصد", ["بداية المجتهد"]),
        ("القضاء والفتيا", []),
        ("جمع الجوامع في أصول الفقه", ["جمع الجوامع"]),
        ("فتح الباري بشرح صحيح البخاري", ["فتح الباري"]),
        ("مسائل الإمام أحمد في الفقه وأثرها في المذهب", ["مسائل الإمام أحمد"]),
    ],
)
def test_cuts(title: str, want: list[str]) -> None:
    assert cuts(title)[-1:] == want[-1:] if want else cuts(title) == []


def test_title_options_and_split() -> None:
    assert title_options("الأم، رواية الربيع")[:2] == ["الأم، رواية الربيع", "الأم"]
    assert split_title("ديوان ابن خفاجة (شاعر الطبيعة والأندلس)") == ("ديوان ابن خفاجة", [], ["شاعر الطبيعة والأندلس"])
    assert split_title("مسائل ابن رشد (الجد) (مخطوط)") == ("مسائل ابن رشد الجد", ["مخطوط"], [])


def test_name_forms() -> None:
    fs = name_forms("جلال الدين عبد الرحمن بن أبي بكر السيوطي")
    assert fs[0] == "جلال الدين عبد الرحمن بن أبي بكر السيوطي" and "جلال الدين السيوطي" in fs
    assert all(len(f.split()) < 7 for f in fs[1:])
    assert name_forms("ابن تيمية") == ["ابن تيمية"]


PARSE = [
    ("03 - الرسالة - الشافعي - ت أحمد شاكر - مكتبة الحلبي القاهرة.pdf",
     {"volume": "03", "title": "الرسالة", "author": "الشافعي", "role": "ت", "editor": "أحمد شاكر",
      "editors": ["أحمد شاكر"], "publisher": "مكتبة الحلبي", "city": "القاهرة"}),
    ("الأم - الشافعي - دار المعرفة بيروت 1990.pdf",
     {"title": "الأم", "author": "الشافعي", "publisher": "دار المعرفة", "city": "بيروت", "year": 1990}),
    ("شرح الأربعين - ابن رجب - صححه وعلق عليه فلان الفلاني - دار السلام - مخطوط.pdf",
     {"title": "شرح الأربعين", "author": "ابن رجب", "role": "صححه وعلق عليه", "editor": "فلان الفلاني",
      "editors": ["فلان الفلاني"], "publisher": "دار السلام", "kinds": ["مخطوط"]}),
    ("01 - تفسير - الطبري - الفهارس.pdf", {"volume": "01", "title": "تفسير", "author": "الطبري", "label": "الفهارس"}),
    ("رسالة - اليوسي - طبعة حجرية فاس.pdf",
     {"title": "رسالة", "author": "اليوسي", "city": "فاس", "kinds": ["طبعة حجرية"]}),
    ("", {}),
]


@pytest.mark.parametrize("name, want", PARSE)
def test_parse_name(name: str, want: dict[str, object]) -> None:
    assert parse_name(name) == want


@pytest.mark.parametrize("row", ROWS[::3], ids=[r[0][:30] for r in ROWS[::3]])
def test_parse_name_reads_compose_back(row: list[str]) -> None:
    title, author, edition = row[:3]
    b = Book.parse(title, author, edition)
    r = explain(b)
    if r.gave_way:
        pytest.skip("shortened")
    p = parse_name(r.name + ".pdf")
    if b.publisher:
        assert p.get("publisher") == b.publisher
    if b.editors:
        assert p.get("editors", [None])[0] == b.editors[0]
