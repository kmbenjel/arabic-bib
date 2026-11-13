from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest
from tables import load, lst

from arabic_bib import audit_name, audit_tree, fix_name
from arabic_bib.audit import CHECKS, planfs_profile

ROWS = load("audit.tsv")


@pytest.mark.parametrize("row", ROWS, ids=[r[0][:40] for r in ROWS])
def test_audit_name(row: list[str]) -> None:
    name, codes, fix = row[:3]
    assert tuple(i.code for i in audit_name(name)) == lst(codes)
    if fix:
        assert fix_name(name) == fix
        assert not [i for i in audit_name(fix) if i.code not in ("forbidden-word", "raw-name", "extension")]


def test_every_issue_is_documented() -> None:
    for row in ROWS:
        for i in audit_name(row[0]):
            assert i.code in CHECKS and i.severity == CHECKS[i.code][0]


def test_plain_profile_is_lenient() -> None:
    assert audit_name("الأم (رواية الربيع)، ط 2 = نسخة.pdf", "plain") == []
    assert [i.code for i in audit_name("a:b.pdf", "plain")] == ["forbidden-char"]


def test_nfd_name_is_flagged() -> None:
    nfd = unicodedata.normalize("NFD", "القرآن.pdf")
    assert nfd != "القرآن.pdf"
    assert "not-nfc" in [i.code for i in audit_name(nfd)]


def _tree(root: Path, names: list[str]) -> None:
    for n in names:
        p = root / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4\n%%EOF\n")


def test_audit_tree(tmp_path: Path) -> None:
    _tree(tmp_path, [
        "الفقه/الأم - الشافعي.pdf",
        "الفقه/المغني - ابن قدامة/01 - المغني - ابن قدامة.pdf",
        "الفقه/المغني - ابن قدامة/01 - المغني - ابن قدامة - نسخة.pdf",
        "الفقه/المغني - ابن قدامة/00 - المغني - ابن قدامة - المقدمة.pdf",
        "الفقه/المغني - ابن قدامة/00 - المغني - ابن قدامة - الواجهة.pdf",
        "الفقه/المغني - ابن قدامة/99 - المغني - ابن قدامة - الفهارس.pdf",
        "الحديث/الموطأ - مالك/الموطأ - مالك.pdf",
        "الحديث/الإعتصام.pdf",
        ".git/config.pdf",
    ])
    found = list(audit_tree(tmp_path))
    by = {(i.code, i.path) for i, _ in found}
    assert ("volume-twice", os.path.join("الفقه", "المغني - ابن قدامة", "01 - المغني - ابن قدامة.pdf")) in by
    assert ("numbered-99", os.path.join("الفقه", "المغني - ابن قدامة", "99 - المغني - ابن قدامة - الفهارس.pdf")) in by
    assert ("one-file-folder", os.path.join("الحديث", "الموطأ - مالك")) in by
    assert ("hamzat-wasl", os.path.join("الحديث", "الإعتصام.pdf")) in by
    assert not [p for _, p in by if ".git" in p]
    assert not [p for c, p in by if c == "volume-twice" and " - 00 " in p]
    fixes = {i.path: f for i, f in found if f}
    assert fixes[os.path.join("الحديث", "الإعتصام.pdf")] == "الاعتصام.pdf"


def test_nfc_twins(tmp_path: Path) -> None:
    a = "القرآن.pdf"
    b = unicodedata.normalize("NFD", a)
    (tmp_path / a).write_bytes(b"x")
    try:
        (tmp_path / b).write_bytes(b"x")
    except OSError:  # pragma: no cover - a file system that normalises names
        pytest.skip("file system normalises names")
    if len(os.listdir(tmp_path)) < 2:  # pragma: no cover
        pytest.skip("file system normalises names")
    assert "nfc-twin" in [i.code for i, _ in audit_tree(tmp_path)]


def test_not_a_dir(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        list(audit_tree(tmp_path / "none"))


def test_planfs_profile() -> None:
    p = planfs_profile("warraq")
    assert p["max_name"] == 240 and p["name_unit"] == "bytes"
    assert all(c in p["forbidden_chars"] for c in "()[],،=:")
    import re

    ta = re.compile(p["forbidden_patterns"][0][0])  # type: ignore[index]
    assert ta.search("الأم - ط الحلبي") and ta.search("الأم ط2") and not ta.search("بسط القول")
    assert "(" not in planfs_profile("plain")["forbidden_chars"]
