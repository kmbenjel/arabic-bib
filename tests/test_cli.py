from __future__ import annotations

import json
from pathlib import Path

import pytest

from arabic_bib.cli import main


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    code = main(list(args))
    return code, capsys.readouterr().out


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys)
    assert code == 0 and "examples:" in out


def test_demo(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "demo")
    assert code == 0
    for s in ("hamzat-wasl", "الاعتصام - دار ابن عفان.pdf", "same", "different", "ت 728 هـ"):
        assert s in out


def test_audit_formats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "الإعتصام (ط دار ابن عفان).pdf").write_bytes(b"x")
    (tmp_path / "الأم - الشافعي.pdf").write_bytes(b"x")
    code, out = run(capsys, "audit", str(tmp_path))
    assert code == 0 and "2 names checked, 1 with issues" in out
    code, out = run(capsys, "audit", str(tmp_path), "--strict")
    assert code == 1
    code, out = run(capsys, "audit", str(tmp_path), "--format", "json")
    data = json.loads(out)
    assert {d["code"] for d in data} == {"parentheses", "ta-prefix", "hamzat-wasl"}
    code, out = run(capsys, "audit", str(tmp_path), "--format", "tsv", "--only", "hamzat-wasl")
    assert out.splitlines()[0].startswith("code\t") and len(out.splitlines()) == 2
    plan = tmp_path / "plan.tsv"
    run(capsys, "audit", str(tmp_path), "--plan", str(plan))
    rows = plan.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "from\tto\treason" and rows[1].split("\t")[1] == "الاعتصام - دار ابن عفان.pdf"
    assert main(["audit", str(tmp_path / "none")]) == 2


def test_compose(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "compose", "-t", "الرسالة", "-a", "الشافعي", "-e", "تحقيق أحمد شاكر، مكتبة الحلبي، القاهرة", "--ext")
    assert out.strip() == "الرسالة - الشافعي - ت أحمد شاكر - مكتبة الحلبي القاهرة.pdf"
    code, out = run(capsys, "compose", "-t", "الأم", "-a", "الشافعي", "-y", "1321 هـ", "-k", "طبعة حجرية", "--json")
    d = json.loads(out)
    assert d["name"] == "الأم - الشافعي - 1321 هـ - طبعة حجرية" and d["fits"]
    code, out = run(capsys, "compose", "-t", "جمع الجوامع في أصول الفقه", "-a", "السيوطي", "--limit", "40", "--explain")
    assert out.strip() == "جمع الجوامع - السيوطي"


def test_author_match_date_edition(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "author", "--json", "أحمد بن عبد الحليم بن تيمية الحراني (ت 728 هـ)")
    d = json.loads(out)
    assert d["ism"] == "أحمد" and d["death"] == 728
    code, out = run(capsys, "author", "ابن تيمية")
    assert "shuhra" in out
    assert main(["match", "ابن تيمية", "أحمد بن عبد الحليم بن تيمية"]) == 0
    assert main(["match", "ابن حجر العسقلاني", "ابن حجر الهيتمي"]) == 1
    capsys.readouterr()
    code, out = run(capsys, "match", "--json", "ابن كثير", "ابن تيمية")
    assert json.loads(out)["verdict"] == "different"
    code, out = run(capsys, "date", "--json", "المتوفى سنة ثمان وعشرين وسبعمائة")
    d = json.loads(out)
    assert d["hijri"] == 728 and d["gregorian_years"] == "1327–1328" and d["century_label"] == "القرن الثامن الهجري"
    code, out = run(capsys, "date", "لا تاريخ هنا")
    assert out == ""
    code, out = run(capsys, "edition", "--json", "الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م")
    assert json.loads(out)["publisher"] == "دار الكتب العلمية"
    code, out = run(capsys, "edition", "الناشر: دار الفكر\\nالطبعة: الثانية")
    assert "دار الفكر" in out


def test_calendar(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "hijri", "728")[1].strip() == "728 هـ = 1327–1328 م"
    assert run(capsys, "hijri", "728-11-20")[1].strip() == "728-11-20 هـ = 1328-09-26 م"
    assert run(capsys, "hijri", "٧٢٨-١١-٢٠", "--proleptic")[1].strip() == "728-11-20 هـ = 1328-10-04 م"
    assert run(capsys, "gregorian", "1999")[1].strip() == "1999 م = 1419–1420 هـ"
    assert run(capsys, "gregorian", "1979-11-21")[1].strip() == "1979-11-21 م = 1400-01-01 هـ"
    assert run(capsys, "hijri", "1400-1")[1].strip() == "1400-01-01 هـ = 1979-11-21 م"
    assert main(["hijri", "1-12-30"]) == 2
    with pytest.raises(SystemExit):
        main(["hijri", "1-2-3-4"])


def test_text_tools(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(capsys, "normalize", "الإمامُ", "أبو", "حامدٍ")[1].strip() == "الامام ابو حامد"
    assert run(capsys, "normalize", "--profile", "display", "مكتبــة  المعارف")[1].strip() == "مكتبة المعارف"
    code, out = run(capsys, "wasl", "الإجتهاد والإستنباط")
    assert code == 1 and "الاجتهاد" in out and "الاستنباط" in out
    code, out = run(capsys, "wasl", "--fix", "الإجتهاد")
    assert code == 0 and out.strip() == "الاجتهاد"
    assert run(capsys, "safe", "ديوان: المتنبي?")[1].strip() == "ديوان المتنبي؟"
    code, out = run(capsys, "profiles")
    assert "warraq" in out and "hamzat-wasl" in out
    code, out = run(capsys, "profiles", "--planfs", "warraq")
    assert json.loads(out)["max_name"] == 240

    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("الإمام\nالقرآن\n"))
    assert run(capsys, "normalize")[1].splitlines() == ["الامام", "القران"]
