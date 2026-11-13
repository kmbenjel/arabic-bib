from __future__ import annotations

from importlib.metadata import entry_points

from arabic_bib.integrations import pocketshelf_profile


def test_pocketshelf_profile() -> None:
    d = pocketshelf_profile("03 - الرسالة - الشافعي - ت أحمد شاكر - مكتبة الحلبي القاهرة")
    assert d == {"title": "الرسالة", "lang": "ar", "author": "الشافعي", "editor": "أحمد شاكر",
                 "publisher": "مكتبة الحلبي", "place": "القاهرة", "volume": "03"}
    d = pocketshelf_profile("الأم - الشافعي - المطبعة الأميرية بولاق 1321 هـ", is_folder=True)
    assert d and d["year"] == 1903 and "volume" not in d
    d = pocketshelf_profile("رسالة - ابن تيمية (ت 728 هـ) - مخطوط")
    assert d and d["author_death"] == 728 and d["author_calendar"] == "ah" and d["edition"] == "مخطوط"
    assert pocketshelf_profile("scan0001") is None
    assert pocketshelf_profile("Les Misérables - Victor Hugo") == {"title": "Les Misérables", "author": "Victor Hugo"}


def test_entry_point_is_declared() -> None:
    eps = entry_points(group="pocketshelf.profiles")
    assert any(e.name == "warraq" and e.value == "arabic_bib.integrations:pocketshelf_profile" for e in eps)
