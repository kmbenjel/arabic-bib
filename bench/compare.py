"""Head-to-head: arabic-bib against PyArabic, CAMeL Tools, Maha and Tashaphyne on the same inputs.

Each library runs in its own virtual environment (bench/compare.sh makes them):

    python bench/compare.py --lib camel > bench/results/camel.json     # inside the camel venv
    python bench/compare.py --report bench/results/*.json > bench/RESULTS.md

What is measured, for every library with its own documented normaliser:
  1. spelling pairs that should fold to one search key (hamza seats, ta marbuta, presentation forms, Persian letters …);
  2. author-name matching on tests/cases/author_pairs.tsv: the others have no author matcher, so two baselines a
     developer would write with them are run: «equal after normalising» and «the shorter's words are all in the
     longer» (a cataloguer's quick rule); arabic-bib runs match_authors;
  3. the bibliographic tasks of the README table (death years, number words, edition statements, Hijri dates),
     each attempted with the library's closest public function, outputs recorded as they come.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FOLD_PAIRS = [
    ("الإمام", "الامام", "hamza on alef"),
    ("القرآن", "القران", "madda"),
    ("ٱلرحمن", "الرحمن", "alef wasla"),
    ("مكتبة", "مكتبه", "ta marbuta"),
    ("مصطفى", "مصطفي", "alef maqsura"),
    ("مسؤول", "مسوول", "hamza on waw"),
    ("رئيس", "رييس", "hamza on ya"),
    ("مُحَمَّدٌ", "محمد", "diacritics"),
    ("كتــاب", "كتاب", "tatweel"),
    ("ﺟﻬﺎﺩ", "جهاد", "presentation forms (PDF text)"),
    ("ﻻ", "لا", "lam-alef ligature"),
    ("یوسف", "يوسف", "Persian ya"),
    ("کتاب", "كتاب", "Persian kaf"),
    ("١٤٢٠", "1420", "Arabic-Indic digits"),
    ("‏الرسالة‎", "الرسالة", "bidi marks"),
]

TASKS = [
    ("death", "ابن تيمية (ت 728 هـ)"),
    ("death", "المتوفى سنة ثمان وعشرين وسبعمائة"),
    ("death", "الذهبي (673 - 748 هـ)"),
    ("number", "ثمان وعشرين وسبعمائة"),
    ("ordinal", "الحادية عشرة"),
    ("edition", "الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م"),
    ("hijri", "728-11-20"),
    ("author", "شيخ الإسلام تقي الدين أبو العباس أحمد بن عبد الحليم بن تيمية الحراني"),
    ("wasl", "الإستغفار والإجتهاد"),
    ("filename", 'ديوان المتنبي: شرح "العكبري"?'),
]


def load_pairs() -> list[tuple[str, str, str]]:
    rows = []
    for line in (ROOT / "tests/cases/author_pairs.tsv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        a, b, v = line.split("\t")[:3]
        rows.append((a, b, v))
    return rows


# --------------------------------------------------------------------------------------------------- adapters
def adapter(lib: str):  # type: ignore[no-untyped-def]
    """→ (version, normalise(str) -> str, tasks: dict[name, fn(str) -> object])."""
    from importlib.metadata import version

    if lib == "ours":
        import arabic_bib as ab

        def edition(t: str) -> object:
            e = ab.parse_edition(t)
            return {"number": e.number, "publisher": e.publisher, "city": e.city, "hijri": e.hijri,
                    "gregorian": e.gregorian}

        def author(t: str) -> object:
            a = ab.parse_author(t)
            return {k: v for k, v in a.as_dict().items() if v}

        def hijri(t: str) -> object:
            return "-".join(map(str, ab.hijri_to_gregorian(*map(int, t.split("-")))))

        tasks = {
            "death": lambda t: (lambda d: d.label() if d else None)(ab.parse_death(t)),
            "number": ab.cardinal_value,
            "ordinal": ab.ordinal_value,
            "edition": edition,
            "hijri": hijri,
            "author": author,
            "wasl": ab.fix_wasl,
            "filename": ab.safe_filename,
        }
        return version("arabic-bib"), ab.search_key, tasks, ab

    if lib == "pyarabic":
        import pyarabic.araby as a

        def norm(s: str) -> str:
            # the documented helpers that fold for search; normalize_hamza with method="tasheel" (ؤ → و, ئ → ي),
            # not its default («uniform»), which turns every hamza seat into «ء» and splits more than it joins
            s = a.normalize_ligature(s)
            s = a.strip_tashkeel(a.strip_tatweel(s))
            s = a.normalize_hamza(s, method="tasheel")
            s = a.normalize_alef(s)
            s = a.normalize_teh(s)
            return " ".join(s.split())

        import pyarabic.number as pn

        return version("pyarabic"), norm, {"number": pn.text2number}, None

    if lib == "camel":
        from camel_tools.utils.dediac import dediac_ar
        from camel_tools.utils.normalize import (
            normalize_alef_ar,
            normalize_alef_maksura_ar,
            normalize_teh_marbuta_ar,
            normalize_unicode,
        )

        def norm(s: str) -> str:
            s = normalize_unicode(s)
            s = dediac_ar(s)
            s = normalize_alef_ar(normalize_alef_maksura_ar(normalize_teh_marbuta_ar(s)))
            return " ".join(s.split())

        return version("camel-tools"), norm, {}, None

    if lib == "maha":
        from maha.cleaners.functions import arabic_numbers_to_english, normalize, remove_all_harakat, remove_tatweel
        from maha.parsers.functions import parse_dimension

        def norm(s: str) -> str:
            s = remove_tatweel(remove_all_harakat(normalize(s, all=True)))
            return " ".join(arabic_numbers_to_english(s).split())

        def dims(t: str, **kw: bool) -> object:
            try:
                return [str(d.value) for d in parse_dimension(t, **kw)]
            except Exception as e:  # noqa: BLE001
                return f"error: {type(e).__name__}"

        tasks = {
            "number": lambda t: dims(t, numeral=True),
            "ordinal": lambda t: dims(t, ordinal=True),
            "death": lambda t: dims(t, time=True),
        }
        return version("mahad"), norm, tasks, None

    if lib == "tashaphyne":
        from tashaphyne.normalize import normalize_searchtext

        return version("tashaphyne"), lambda s: " ".join(normalize_searchtext(s).split()), {}, None

    raise SystemExit(f"unknown lib {lib}")


def tokens_in(a: str, b: str) -> bool:
    ta, tb = set(a.split()), set(b.split())
    s, l = (ta, tb) if len(ta) <= len(tb) else (tb, ta)  # noqa: E741
    return bool(s) and s <= l


def score(pred: list[str], gold: list[str]) -> dict[str, object]:
    n = len(gold)
    acc = sum(p == g for p, g in zip(pred, gold)) / n
    false_merge = sum(p == "same" and g == "different" for p, g in zip(pred, gold))
    same_gold = sum(g == "same" for g in gold)
    recall = sum(p == "same" and g == "same" for p, g in zip(pred, gold)) / same_gold
    said_same = sum(p == "same" for p in pred)
    precision = sum(p == "same" and g == "same" for p, g in zip(pred, gold)) / said_same if said_same else 0.0
    return {"accuracy": round(acc, 3), "same_precision": round(precision, 3), "same_recall": round(recall, 3),
            "false_merges": false_merge, "n": n}


def run_lib(lib: str) -> dict[str, object]:
    ver, norm, tasks, ab = adapter(lib)
    folds = []
    for a, b, what in FOLD_PAIRS:
        try:
            na, nb = norm(a), norm(b)
            folds.append({"pair": [a, b], "what": what, "out": [na, nb], "ok": na == nb})
        except Exception as e:  # noqa: BLE001
            folds.append({"pair": [a, b], "what": what, "out": [f"error: {e}", ""], "ok": False})
    pairs = load_pairs()
    gold = [v for _, _, v in pairs]
    t0 = time.perf_counter()
    eq = ["same" if norm(a) == norm(b) else "different" for a, b, _ in pairs]
    tok = ["same" if tokens_in(norm(a), norm(b)) else "different" for a, b, _ in pairs]
    dt = time.perf_counter() - t0
    out: dict[str, object] = {
        "lib": lib, "version": ver, "folds": folds, "fold_ok": sum(f["ok"] for f in folds),
        "match_equal": score(eq, gold), "match_tokens": score(tok, gold), "baseline_seconds": round(dt, 4),
    }
    if ab is not None:
        t0 = time.perf_counter()
        ours = [ab.match_authors(a, b).verdict for a, b, _ in pairs]
        out["match_ours"] = score(ours, gold)
        out["match_seconds"] = round(time.perf_counter() - t0, 4)
        out["misses"] = [[a, b, g, p] for (a, b, g), p in zip(pairs, ours) if g != p]
    res = {}
    for name, text in TASKS:
        fn = tasks.get(name)
        if fn is None:
            res[f"{name}: {text}"] = None
            continue
        try:
            res[f"{name}: {text}"] = fn(text)
        except Exception as e:  # noqa: BLE001
            res[f"{name}: {text}"] = f"error: {type(e).__name__}"
    out["tasks"] = res
    # import time: median of five fresh interpreters
    mod = {"ours": "arabic_bib", "pyarabic": "pyarabic.araby", "camel": "camel_tools.utils.normalize",
           "maha": "maha.cleaners.functions", "tashaphyne": "tashaphyne.normalize"}[lib]
    ts = []
    for _ in range(5):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-W", "ignore", "-c", f"import {mod}"], check=True)
        ts.append(time.perf_counter() - t0)
    out["import_seconds"] = round(statistics.median(ts), 3)
    return out


# ----------------------------------------------------------------------------------------------------- report
NAMES = {"ours": "arabic-bib", "pyarabic": "PyArabic", "camel": "CAMeL Tools", "maha": "Maha", "tashaphyne": "Tashaphyne"}


def report(files: list[str], sizes: dict[str, dict[str, object]]) -> str:
    rs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    order = ["ours", "pyarabic", "camel", "maha", "tashaphyne"]
    rs.sort(key=lambda r: order.index(r["lib"]))
    L = []
    L.append("# Head-to-head results\n")
    L.append("Made by `bench/compare.sh` on a Linux VM (Python 3.12). Every number below comes from a run.\n")
    L.append("## Versions, install size, dependencies, import time\n")
    L.append("| library | version | installed size | dependencies installed | import time |")
    L.append("|---|---|---|---|---|")
    for r in rs:
        s = sizes.get(r["lib"], {})
        L.append(f"| {NAMES[r['lib']]} | {r['version']} | {s.get('mb', '?')} MB | {s.get('pkgs', '?')} | {r['import_seconds']} s |")
    L.append("\n## 1. Spelling variants folded to one search key\n")
    head = "| variant | " + " | ".join(NAMES[r["lib"]] for r in rs) + " |"
    L.append(head)
    L.append("|---" * (len(rs) + 1) + "|")
    for i, (a, b, what) in enumerate(FOLD_PAIRS):
        cells = ["✓" if r["folds"][i]["ok"] else "✗" for r in rs]
        L.append(f"| {what}: «{a}» = «{b}» | " + " | ".join(cells) + " |")
    L.append("| **total** | " + " | ".join(f"**{r['fold_ok']}/{len(FOLD_PAIRS)}**" for r in rs) + " |")
    n = rs[0]["match_equal"]["n"]
    L.append(f"\n## 2. Author-name matching ({n} labelled pairs, `tests/cases/author_pairs.tsv`)\n")
    L.append("Labels: same / different / unknown, the decision a careful cataloguer makes from the two strings alone. "
             "A false merge is «same» said of two different people.\n")
    L.append("| method | accuracy | precision of «same» | recall of «same» | false merges |")
    L.append("|---|---|---|---|---|")
    for r in rs:
        if "match_ours" in r:
            m = r["match_ours"]
            L.append(f"| **arabic-bib `match_authors`** | **{m['accuracy']:.0%}** | **{m['same_precision']:.0%}** | "
                     f"**{m['same_recall']:.0%}** | **{m['false_merges']}** |")
    for r in rs:
        for key, label in (("match_equal", "equal after normalising"), ("match_tokens", "words of one ⊂ the other")):
            m = r[key]
            L.append(f"| {NAMES[r['lib']]} + {label} | {m['accuracy']:.0%} | {m['same_precision']:.0%} | "
                     f"{m['same_recall']:.0%} | {m['false_merges']} |")
    L.append("\n## 3. Bibliographic tasks (closest public function of each library)\n")
    L.append("| input | " + " | ".join(NAMES[r["lib"]] for r in rs) + " |")
    L.append("|---" * (len(rs) + 1) + "|")
    for k in rs[0]["tasks"]:
        cells = []
        for r in rs:
            v = r["tasks"].get(k)
            cells.append("—" if v is None else f"`{json.dumps(v, ensure_ascii=False)}`".replace("|", "\\|"))
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L.append("\n«—» = the library has no function for this task; `[]` = it has one and found nothing.\n")
    ours = next((r for r in rs if r["lib"] == "ours"), None)
    if ours and ours.get("misses"):
        L.append("## arabic-bib's misses on the pair set\n")
        L.append("| a | b | label | arabic-bib |")
        L.append("|---|---|---|---|")
        for a, b, g, p in ours["misses"]:
            L.append(f"| {a} | {b} | {g} | {p} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib")
    ap.add_argument("--report", nargs="*")
    ap.add_argument("--sizes", help="JSON {lib: {mb, pkgs}} from compare.sh")
    a = ap.parse_args()
    if a.lib:
        print(json.dumps(run_lib(a.lib), ensure_ascii=False, indent=1))
    elif a.report:
        sizes = json.loads(Path(a.sizes).read_text(encoding="utf-8")) if a.sizes else {}
        sys.stdout.write(report(a.report, sizes))


if __name__ == "__main__":
    main()
