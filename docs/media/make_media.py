"""Make the README and docs media by running the tool (run on a build machine, not a laptop):

    python docs/media/make_media.py            # → docs/media/audit.svg, demo.svg, examples.md
    python docs/media/make_media.py --card     # + card.webp (needs google-chrome and Pillow)

audit.svg is a terminal recording: the real output of ``arabic-bib audit`` on a folder of badly named books, played
back line by line (CSS animation, so it plays on GitHub). The font is Kawkab Mono (SIL OFL), embedded.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from arabic_bib.cli import DEMO_NAMES  # noqa: E402

FONT = Path(os.environ.get("KAWKAB", str(HERE / "fonts" / "kawkab-mono-regular.woff2")))
COLORS = {"31": "#f7768e", "32": "#9ece6a", "33": "#e0af68", "2": "#7a819e", "1": None}
BG, FG, TITLE = "#1a1b26", "#c0caf5", "#24283b"
ANSI = re.compile(r"\x1b\[(\d+)m(.*?)\x1b\[0m")


def run(args: list[str], cwd: Path) -> list[str]:
    env = {**os.environ, "FORCE_COLOR": "1", "PYTHONPATH": str(ROOT / "src")}
    out = subprocess.run([sys.executable, "-m", "arabic_bib", *args], cwd=cwd, env=env, capture_output=True,
                         text=True, check=False)
    return out.stdout.rstrip("\n").splitlines()


def spans(line: str) -> list[tuple[str, str | None, bool]]:
    """ANSI line → [(text, colour, bold)]."""
    out, pos = [], 0
    for m in ANSI.finditer(line):
        if m.start() > pos:
            out.append((line[pos : m.start()], None, False))
        out.append((m.group(2), COLORS.get(m.group(1)), m.group(1) == "1"))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], None, False))
    return out

_AR_RUN = re.compile(
    "[\u0600-\u06ff\ufb50-\ufdff\ufe70-\ufeff][^A-Za-z\u2192\u21e5]*?"
    "(?=\\s*$|\\s{2,}|\\s[\u2192\u21e5]\\s|\\.[A-Za-z0-9]{2,4}(?:\\s|$)|\\s+-?-?[A-Za-z])"
)


def isolate(text: str) -> str:
    """Each Arabic file name or phrase becomes a right-to-left island (U+2067 … U+2069) inside the left-to-right
    terminal line, so «الإعتصام.pdf» reads as in a bidi-aware terminal and arrows keep their direction."""
    return _AR_RUN.sub(lambda m: "\u2067" + m.group(0) + "\u2069", text)


def visible(line: str) -> int:
    return len(re.sub("\x1b\\[\\d+m", "", line))



def svg(lines: list[str], title: str, *, animate: bool, width: int = 0, step: float = 0.22) -> str:
    lh, pad, top = 22, 22, 46
    width = width or int(max(visible(x) for x in lines) * 8.75 + 2 * pad)
    height = top + pad + lh * len(lines) + pad
    font = ""
    if FONT.exists():
        b64 = base64.b64encode(FONT.read_bytes()).decode()
        font = f"@font-face{{font-family:'Kawkab Mono';src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
    css = [font, f"text{{font-family:'Kawkab Mono','DejaVu Sans Mono',monospace;font-size:14.5px;fill:{FG};"
           "white-space:pre}", ".b{font-weight:700}"]
    if animate:
        css.append("@keyframes in{from{opacity:0}to{opacity:1}} .l{opacity:0;animation:in .01s forwards}")
        css.append("@keyframes type{from{width:0}to{width:100%}}")
    rows = []
    for i, line in enumerate(lines):
        y = top + pad + lh * (i + 1) - 6
        parts = []
        for text, col, bold in spans(line):
            t = html.escape(isolate(text), quote=False)
            attrs = (f' fill="{col}"' if col else "") + (' class="b"' if bold else "")
            parts.append(f"<tspan{attrs}>{t}</tspan>")
        delay = f' style="animation-delay:{0.6 + i * step:.2f}s"' if animate else ""
        cls = ' class="l"' if animate else ""
        rows.append(f'<text x="{pad}" y="{y}" xml:space="preserve"{cls}{delay}>{"".join(parts)}</text>')
    dots = "".join(f'<circle cx="{22 + 20 * k}" cy="18" r="6" fill="{c}"/>'
                   for k, c in enumerate(("#f7768e", "#e0af68", "#9ece6a")))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"<style>{''.join(css)}</style>"
        f'<rect width="{width}" height="{height}" rx="10" fill="{BG}"/>'
        f'<rect width="{width}" height="36" rx="10" fill="{TITLE}"/><rect y="26" width="{width}" height="10" fill="{TITLE}"/>'
        f'{dots}<text x="{width // 2}" y="23" text-anchor="middle" style="font-size:13px;fill:#7a819e">'
        f"{html.escape(title)}</text>{''.join(rows)}</svg>\n"
    )


def demo_tree(base: Path) -> Path:
    root = base / "كتب"
    for n in DEMO_NAMES:
        p = root / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return root


EXAMPLES = [
    ("author", "شيخ الإسلام تقي الدين أبو العباس أحمد بن عبد الحليم بن تيمية الحراني (ت 728 هـ)"),
    ("author", "ابن خلدون، عبد الرحمن بن محمد"),
    ("match", "ابن تيمية", "أحمد بن عبد الحليم بن تيمية الحراني"),
    ("match", "ابن حجر العسقلاني", "ابن حجر الهيتمي"),
    ("match", "محمد", "محمد بن إسماعيل البخاري"),
    ("date", "المتوفى سنة ثمان وعشرين وسبعمائة"),
    ("date", "الذهبي (673 - 748 هـ)"),
    ("date", "من علماء القرن الحادي عشر"),
    ("hijri", "728-11-20"),
    ("edition", "تحقيق: شعيب الأرنؤوط - مؤسسة الرسالة، بيروت، ط 2، 1405هـ/1985م"),
    ("compose", "-t", "تفسير الطبري = جامع البيان عن تأويل آي القرآن", "-a", "الطبري", "-e",
     "تحقيق محمود محمد شاكر، مكتبة ابن تيمية، القاهرة"),
    ("wasl", "--fix", "الإجتهاد والإستنباط"),
    ("normalize", "الإِمامُ أبو حامدٍ الغزاليّ"),
]


def examples_md(cwd: Path) -> str:
    """The README table: input → parsed output, each row produced by the CLI."""
    rows = ["| command | input | output |", "|---|---|---|"]
    for ex in EXAMPLES:
        cmd, args = ex[0], list(ex[1:])
        js = cmd in ("author", "date", "edition")
        out = run([cmd, *(["--json"] if js else []), *args], cwd)
        if js:
            d = json.loads("\n".join(out))
            d = {k: v for k, v in d.items() if v not in (None, "", [], False) and k not in ("span",)}
            if cmd == "date":
                d = {k: d[k] for k in ("hijri", "gregorian_years", "birth_hijri", "century", "label") if k in d}
            if cmd == "edition":
                d = {k: v for k, v in d.items() if k != "places"}
            text = "<br>".join(f"**{k}** {' · '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in d.items())
        else:
            text = "<br>".join(html.escape(re.sub(r"\x1b\[\d+m", "", x)) for x in out)
        shown = " ".join(a for a in args if not a.startswith("-"))
        if cmd == "compose":
            shown = " · ".join(a for a in args if not a.startswith("-"))
        if cmd == "match":
            shown = f"{args[0]} ~ {args[1]}"
        rows.append(f"| `{cmd}` | {shown} | {text} |")
    return "\n".join(rows) + "\n"


def card(svg_path: Path) -> None:
    """A still of the recording (every line shown) → card.png (1200×750) → card.webp."""
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise SystemExit("--card needs google-chrome or chromium")
    page = svg_path.with_name("_card.html")
    body = svg_path.read_text(encoding="utf-8")
    page.write_text(
        "<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#0f1018;width:1200px;height:750px;"
        "display:flex;align-items:center;justify-content:center;overflow:hidden}svg{width:1160px;height:710px}</style>"
        + body, encoding="utf-8")
    png = svg_path.with_name("card.png")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1200,750",
                    f"--screenshot={png}", page.as_uri()], check=True, capture_output=True)
    page.unlink()
    from PIL import Image

    im = Image.open(png).convert("RGB")
    im.save(svg_path.with_name("card.webp"), "WEBP", quality=82, method=6)
    png.unlink()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", action="store_true")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        demo_tree(base)
        out = run(["audit", "كتب", "--plan", "fixes.tsv"], base)
        lines = ["\x1b[32m$\x1b[0m arabic-bib audit كتب --plan fixes.tsv", *out, ""]
        plan = (base / "fixes.tsv").read_text(encoding="utf-8").splitlines()
        lines += ["\x1b[32m$\x1b[0m head -3 fixes.tsv", *[x.replace("\t", "  ⇥  ") for x in plan[:3]]]
        (HERE / "audit.svg").write_text(svg(lines, "arabic-bib audit", animate=True), encoding="utf-8")
        cut = next(i for i, x in enumerate(lines) if "names checked" in x)
        still = lines[:13] + ["  \x1b[2m…\x1b[0m"] + lines[cut : cut + 1]
        (HERE / "audit-still.svg").write_text(svg(still, "arabic-bib audit", animate=False), encoding="utf-8")
        demo = run(["demo"], base)
        start = next(i for i, x in enumerate(demo) if "2. compose" in x)
        lines = ["\x1b[32m$\x1b[0m arabic-bib demo", *demo[start:]]
        (HERE / "demo.svg").write_text(svg(lines, "arabic-bib demo", animate=True, step=0.12), encoding="utf-8")
        (HERE / "examples.md").write_text(examples_md(base), encoding="utf-8")
    if a.card:
        card(HERE / "audit-still.svg")
    for f in sorted(HERE.glob("*.*")):
        if f.suffix in (".svg", ".png", ".webp", ".md"):
            print(f"{f.name:<18} {f.stat().st_size // 1024:>5} KB")


if __name__ == "__main__":
    main()
