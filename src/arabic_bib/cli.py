"""The ``arabic-bib`` command line."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .audit import CHECKS, audit_tree
from .authors import match_authors, parse_author
from .compose import PROFILES as NAME_PROFILES
from .compose import Book, explain
from .dates import (
    century_label,
    gregorian_to_hijri,
    gregorian_year_to_hijri,
    hijri_to_gregorian,
    hijri_year_to_gregorian,
    parse_death,
)
from .edition import parse_edition
from .normalize import PROFILES as NORM_PROFILES
from .normalize import normalize
from .spelling import fix_wasl, safe_filename, wasl_errors

EPILOG = """examples:
  arabic-bib demo
  arabic-bib audit ~/Books --profile warraq --plan fixes.tsv
  arabic-bib compose -t "الرسالة" -a "الشافعي" -e "تحقيق أحمد شاكر، مكتبة الحلبي، القاهرة"
  arabic-bib author "شيخ الإسلام أحمد بن عبد الحليم بن تيمية الحراني (ت 728 هـ)"
  arabic-bib match "ابن تيمية" "أحمد بن عبد الحليم بن تيمية الحراني"
  arabic-bib date "المتوفى سنة ثمان وعشرين وسبعمائة"
  arabic-bib hijri 728            arabic-bib gregorian 1999
  arabic-bib edition "الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م"
  arabic-bib normalize --profile search "الإمامُ أبو حامدٍ الغزاليّ"
  arabic-bib wasl "الإجتهاد والإستنباط"
"""


class _C:
    """ANSI colours, only on a terminal and only without NO_COLOR."""

    on = (sys.stdout.isatty() or bool(os.environ.get("FORCE_COLOR"))) and not os.environ.get("NO_COLOR")

    @classmethod
    def w(cls, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if cls.on else s

    @classmethod
    def red(cls, s: str) -> str:
        return cls.w("31", s)

    @classmethod
    def yellow(cls, s: str) -> str:
        return cls.w("33", s)

    @classmethod
    def green(cls, s: str) -> str:
        return cls.w("32", s)

    @classmethod
    def dim(cls, s: str) -> str:
        return cls.w("2", s)

    @classmethod
    def bold(cls, s: str) -> str:
        return cls.w("1", s)


def _out(obj: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return
    if isinstance(obj, dict):
        width = max((len(str(k)) for k in obj), default=0)
        for k, v in obj.items():
            if v in (None, "", [], ()):
                continue
            if isinstance(v, (list, tuple)):
                v = " | ".join(map(str, v))
            print(f"{_C.dim(str(k).ljust(width))}  {v}")
    else:
        print(obj)


def _texts(args: argparse.Namespace) -> list[str]:
    if args.text:
        return [" ".join(args.text)]
    if sys.stdin.isatty():
        raise SystemExit("give a text, or pipe lines on stdin")
    return [line.rstrip("\n") for line in sys.stdin]


# --------------------------------------------------------------------------------------------------- commands
def cmd_normalize(a: argparse.Namespace) -> int:
    for t in _texts(a):
        print(normalize(t, a.profile))
    return 0


def cmd_compose(a: argparse.Namespace) -> int:
    kw: dict[str, object] = {}
    if a.year:
        kw["year"] = a.year
    if a.kind:
        kw["kinds"] = tuple(a.kind)
    book = Book.parse(a.title, a.author or "", a.edition or "", **kw)
    r = explain(book, a.profile, limit=a.limit)
    ext = NAME_PROFILES[a.profile].extension if a.profile in NAME_PROFILES else ""
    if a.json:
        _out({"name": r.name, "file": r.name + ext, "bytes": r.bytes, "fits": r.fits, "gave_way": list(r.gave_way)},
             True)
    else:
        print(r.name + (ext if a.ext else ""))
        if a.explain:
            print(_C.dim(f"{r.bytes} bytes; gave way: {', '.join(r.gave_way) or 'nothing'}"), file=sys.stderr)
    return 0


def cmd_audit(a: argparse.Namespace) -> int:
    root = Path(a.dir)
    try:
        found = list(audit_tree(root, a.profile))
    except NotADirectoryError as e:
        print(f"arabic-bib audit: {e}", file=sys.stderr)
        return 2
    if a.only:
        found = [(i, f) for i, f in found if i.code in a.only]
    if a.format == "json":
        print(json.dumps([{**i.__dict__, "fix": f} for i, f in found], ensure_ascii=False, indent=2))
    elif a.format == "tsv":
        w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
        w.writerow(["code", "severity", "path", "detail", "fix"])
        for i, f in found:
            w.writerow([i.code, i.severity, i.path, i.detail, f])
    else:
        by_path: dict[str, list[tuple[object, str]]] = {}
        for i, f in found:
            by_path.setdefault(i.path, []).append((i, f))
        for path, items in by_path.items():
            print(_C.bold(path))
            fix = next((f for _, f in items if f), "")
            for i, _ in items:
                mark = _C.red("✗") if i.severity == "error" else _C.yellow("!")
                det = f" {_C.dim(i.detail)}" if i.detail else ""
                print(f"  {mark} {i.code:<19}{det}")
            if fix:
                print(f"  {_C.green('→')} {fix}")
        n = Counter(i.severity for i, _ in found)
        names = len({i.path for i, _ in found})
        total = sum(1 for _ in root.rglob("*") if not any(p.startswith(".") for p in _.relative_to(root).parts))
        summary = f"{total} names checked, {names} with issues: {n['error']} errors, {n['warning']} warnings"
        print(_C.bold(summary) if found else _C.green(summary))
        if found:
            codes = Counter(i.code for i, _ in found)
            print(_C.dim("  " + ", ".join(f"{c} {k}" for k, c in codes.most_common())))
    if a.plan:
        rows = {}
        for i, f in found:
            if f and i.path not in rows:
                parent = str(Path(i.path).parent)
                to = f if parent == "." else f"{parent}/{f}"
                rows[i.path] = (i.path, to, i.code)
        with open(a.plan, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(["from", "to", "reason"])
            # deepest paths first, so that a folder is renamed after its files
            for r in sorted(rows.values(), key=lambda r: -r[0].count("/")):
                w.writerow([*r[:2], f"arabic-bib audit: {r[2]}"])
        print(_C.dim(f"plan: {len(rows)} renames → {a.plan}"), file=sys.stderr)
    return 1 if any(i.severity == "error" for i, _ in found) and a.strict else 0


def cmd_author(a: argparse.Namespace) -> int:
    texts = _texts(a)
    for t in texts:
        p = parse_author(t)
        d = p.as_dict()
        d["forms"] = p.forms()
        _out(d, a.json)
        if not a.json and len(texts) > 1:
            print()
    return 0


def cmd_match(a: argparse.Namespace) -> int:
    m = match_authors(a.a, a.b)
    if a.json:
        _out({"verdict": m.verdict, "score": m.score, "reasons": list(m.reasons)}, True)
    else:
        col = {"same": _C.green, "different": _C.red}.get(m.verdict, _C.yellow)
        print(f"{col(m.verdict)}  {m.score:.2f}  {_C.dim(' '.join(m.reasons))}")
    return 0 if m.verdict == "same" else 1


def cmd_date(a: argparse.Namespace) -> int:
    for t in _texts(a):
        d = parse_death(t)
        if not d:
            print(_C.yellow("no date found"), file=sys.stderr)
            continue
        out = {k: v for k, v in d.__dict__.items() if k not in ("text", "span")}
        out["label"] = d.label()
        if d.hijri:
            out["gregorian_years"] = "–".join(map(str, sorted(set(hijri_year_to_gregorian(d.hijri)))))
        if d.century:
            out["century_label"] = century_label(d.century)
        _out(out, a.json)
    return 0


def _ymd(s: str) -> tuple[int, ...]:
    from .normalize import to_ascii_digits

    parts = [int(x) for x in to_ascii_digits(s).replace("/", "-").split("-") if x]
    if not 1 <= len(parts) <= 3:
        raise SystemExit(f"a date is Y, Y-M or Y-M-D, not {s!r}")
    return tuple(parts)


def cmd_hijri(a: argparse.Namespace) -> int:
    p = _ymd(a.date)
    if len(p) == 1:
        g = hijri_year_to_gregorian(p[0])
        print(f"{p[0]} هـ = {g[0]}{'–' + str(g[1]) if g[1] != g[0] else ''} م")
    else:
        y, m, d = (*p, 1)[:3] if len(p) == 2 else p
        g = hijri_to_gregorian(y, m, d, proleptic=a.proleptic, calendar=a.calendar)
        print(f"{y}-{m:02d}-{d:02d} هـ = {g[0]}-{g[1]:02d}-{g[2]:02d} م")
    return 0


def cmd_gregorian(a: argparse.Namespace) -> int:
    p = _ymd(a.date)
    if len(p) == 1:
        h = gregorian_year_to_hijri(p[0])
        print(f"{p[0]} م = {h[0]}{'–' + str(h[1]) if h[1] != h[0] else ''} هـ")
    else:
        y, m, d = (*p, 1)[:3] if len(p) == 2 else p
        h = gregorian_to_hijri(y, m, d, proleptic=a.proleptic, calendar=a.calendar)
        print(f"{y}-{m:02d}-{d:02d} م = {h[0]}-{h[1]:02d}-{h[2]:02d} هـ")
    return 0


def cmd_edition(a: argparse.Namespace) -> int:
    for t in _texts(a):
        _out(parse_edition(t.replace("\\n", "\n")).as_dict(), a.json)
    return 0


def cmd_wasl(a: argparse.Namespace) -> int:
    bad = 0
    for t in _texts(a):
        errs = wasl_errors(t)
        bad += len(errs)
        if a.fix:
            print(fix_wasl(t))
        else:
            for e in errs:
                print(f"{e.word} → {_C.green(e.suggestion)}")
    return 1 if bad and not a.fix else 0


def cmd_safe(a: argparse.Namespace) -> int:
    for t in _texts(a):
        print(safe_filename(t, a.max_bytes))
    return 0


def cmd_profiles(a: argparse.Namespace) -> int:
    if a.planfs:
        from .audit import planfs_profile

        print(json.dumps(planfs_profile(a.planfs), ensure_ascii=False, indent=2))
        return 0
    print(_C.bold("naming profiles (compose, audit):"))
    for p in NAME_PROFILES.values():
        print(f"  {p.name:<13} {p.max_bytes} bytes  {p.description}")
    print(_C.bold("normalisation profiles (normalize):"))
    for n in NORM_PROFILES:
        print(f"  {n}")
    print(_C.bold("audit checks:"))
    for code, (sev, msg) in CHECKS.items():
        print(f"  {code:<19} {sev:<8} {msg}")
    return 0


DEMO_NAMES = [
    "الإعتصام (ط دار ابن عفان).pdf",
    "تفسير الطبري = جامع البيان - ت شاكر، دار المعارف.pdf",
    "ﺟﻬﺎﺩ النفس - ابن أبي الدنيا.pdf",
    "كتاب  الأم - الشافعي .pdf",
    "ديوان المتنبي: شرح العكبري?.pdf",
    "12_3456.pdf",
    "الموطأ - مالك بن أنس - ت محمد فؤاد عبد الباقي - دار إحياء التراث العربي بيروت.pdf",
    "مقدمة ابن خلدون/01 - مقدمة ابن خلدون - ت عبد الله الدرويش - دار يعرب دمشق.pdf",
    "مقدمة ابن خلدون/01 - مقدمة ابن خلدون - ت عبد الله الدرويش - دار يعرب دمشق - نسخة ثانية.pdf",
    "الرسالة - الشافعي/الرسالة - الشافعي - ت أحمد شاكر.pdf",
]


def cmd_demo(a: argparse.Namespace) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="arabic-bib-demo-"))
    try:
        for n in DEMO_NAMES:
            p = tmp / "كتب" / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"%PDF-1.4\n%%EOF\n")
        print(_C.bold("1. audit: a folder of badly named books (profile warraq)"))
        print(_C.dim(f"   $ arabic-bib audit {tmp / 'كتب'}"))
        ns = argparse.Namespace(dir=str(tmp / "كتب"), profile="warraq", format="text", plan=None, only=None,
                                strict=False)
        cmd_audit(ns)
        print()
        print(_C.bold("2. compose: a name from its parts; nothing is cut when it fits"))
        b = Book.parse("الرسالة", "الشافعي", "تحقيق: أحمد محمد شاكر، مكتبة مصطفى البابي الحلبي، القاهرة، 1358 هـ")
        print("  ", explain(b).name + ".pdf")
        long = Book.parse(
            "جمع الجوامع في أصول الفقه وقواعده الكلية ويليه همع الهوامع في شرح جمع الجوامع في علم العربية",
            "جلال الدين عبد الرحمن بن أبي بكر السيوطي",
            "ت عبد الحميد هنداوي - دار الكتب العلمية بيروت",
        )
        r = explain(long, limit=110)
        print("  ", r.name, _C.dim(f"({r.bytes} bytes; gave way: {', '.join(r.gave_way)})"))
        print()
        print(_C.bold("3. authors: parts, and two forms of one person"))
        p = parse_author("شيخ الإسلام تقي الدين أبو العباس أحمد بن عبد الحليم بن تيمية الحراني (ت 728 هـ)")
        for k, v in p.as_dict().items():
            if v:
                print(f"   {k:<8} {' | '.join(v) if isinstance(v, list) else v}")
        for x, y in (("ابن تيمية", "أحمد بن عبد الحليم بن تيمية الحراني"),
                     ("ابن حجر العسقلاني", "ابن حجر الهيتمي"),
                     ("محمد", "محمد بن إسماعيل البخاري")):
            m = match_authors(x, y)
            col = {"same": _C.green, "different": _C.red}.get(m.verdict, _C.yellow)
            print(f"   {x}  ~  {y}  → {col(m.verdict)}")
        print()
        print(_C.bold("4. dates and editions"))
        for t in ("ت 728 هـ", "المتوفى سنة ثمان وعشرين وسبعمائة", "(661 - 728 هـ)", "القرن الثامن الهجري"):
            d = parse_death(t)
            assert d
            print(f"   {t:<34} → {d.label()}")
        e = parse_edition("الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م")
        print(f"   edition {e.number} · {e.publisher} · {e.city} · {e.hijri} هـ / {e.gregorian} م")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


# ------------------------------------------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="arabic-bib",
        description="Arabic bibliographic text: normalise, compose and audit book names, parse authors, death "
        "years, Hijri dates and edition statements.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--version", action="version", version=f"arabic-bib {__version__}")
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND")

    def add(name: str, fn, help_: str) -> argparse.ArgumentParser:  # type: ignore[no-untyped-def]
        p = sub.add_parser(name, help=help_, description=help_)
        p.set_defaults(fn=fn)
        return p

    p = add("demo", cmd_demo, "show what the tool does on built-in examples (no files needed)")
    p = add("audit", cmd_audit, "check every file and folder name under DIR against a naming profile")
    p.add_argument("dir")
    p.add_argument("--profile", default="warraq", choices=sorted(NAME_PROFILES))
    p.add_argument("--format", default="text", choices=("text", "tsv", "json"))
    p.add_argument("--plan", metavar="FILE", help="write the proposed renames as a from/to/reason TSV plan")
    p.add_argument("--only", nargs="+", metavar="CODE", help="only these checks (see `arabic-bib profiles`)")
    p.add_argument("--strict", action="store_true", help="exit 1 when an error is found (for CI)")

    p = add("compose", cmd_compose, "build a book's file name from its title, author and imprint")
    p.add_argument("-t", "--title", required=True)
    p.add_argument("-a", "--author")
    p.add_argument("-e", "--edition", help="editor and imprint as printed: «تحقيق فلان، دار كذا، بيروت»")
    p.add_argument("-y", "--year")
    p.add_argument("-k", "--kind", action="append", help="«مخطوط», «رسالة ماجستير» … (repeatable)")
    p.add_argument("--profile", default="warraq", choices=sorted(NAME_PROFILES))
    p.add_argument("--limit", type=int, help="bytes for the name without its extension")
    p.add_argument("--ext", action="store_true", help="print the extension too")
    p.add_argument("--explain", action="store_true", help="say what gave way (on stderr)")
    p.add_argument("--json", action="store_true")

    for name, fn, h in (
        ("author", cmd_author, "split an author's name into ism, nasab, kunya, laqab, nisba, shuhra, death"),
        ("date", cmd_date, "find a death date: «ت 728 هـ», «المتوفى سنة …», «القرن الثامن»"),
        ("edition", cmd_edition, "read an edition statement into number, publisher, city, years, editors"),
    ):
        p = add(name, fn, h)
        p.add_argument("text", nargs="*")
        p.add_argument("--json", action="store_true")

    p = add("match", cmd_match, "do two name forms name the same person? (exit 0 when same)")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--json", action="store_true")

    for name, fn, h in (
        ("hijri", cmd_hijri, "Hijri → Gregorian: a year (728) or a date (728-11-20)"),
        ("gregorian", cmd_gregorian, "Gregorian → Hijri: a year (1999) or a date (1328-09-26)"),
    ):
        p = add(name, fn, h)
        p.add_argument("date")
        p.add_argument("--proleptic", action="store_true", help="proleptic Gregorian before 1582 (default: Julian)")
        p.add_argument("--calendar", default="tabular", choices=("tabular", "umalqura"))

    p = add("normalize", cmd_normalize, "normalise text (search, display, loose); reads stdin lines")
    p.add_argument("text", nargs="*")
    p.add_argument("--profile", default="search", choices=sorted(NORM_PROFILES))

    p = add("wasl", cmd_wasl, "find (or --fix) hamzas written on a hamzat al-wasl")
    p.add_argument("text", nargs="*")
    p.add_argument("--fix", action="store_true")

    p = add("safe", cmd_safe, "make a name safe for every file system")
    p.add_argument("text", nargs="*")
    p.add_argument("--max-bytes", type=int, default=255)

    p = add("profiles", cmd_profiles, "list naming and normalisation profiles and the audit checks")
    p.add_argument("--planfs", metavar="PROFILE", help="print a naming profile as planfs profile JSON")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    try:
        return int(args.fn(args) or 0)
    except ValueError as e:
        print(f"arabic-bib {args.cmd}: {e}", file=sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
