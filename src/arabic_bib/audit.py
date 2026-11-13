"""Audit file and folder names against a naming profile, and propose fixes.

``audit_name`` checks one name; ``audit_tree`` walks a directory and adds the checks that need siblings (a folder
that holds one file, a volume number used twice, indexes numbered 99). Every issue that can be fixed mechanically
carries the fixed name, so ``arabic-bib audit --plan fixes.tsv`` writes a rename plan (``from<TAB>to<TAB>reason``)
that a tool such as `planfs` can preview and apply.
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .compose import NameProfile, get_profile
from .spelling import FORBIDDEN, fix_wasl, has_presentation_forms, safe_filename, wasl_errors

__all__ = ["CHECKS", "Issue", "audit_name", "audit_tree", "fix_name"]


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str = ""
    severity: str = "error"  # error | warning
    detail: str = ""


#: every check: code → (severity, what it means)
CHECKS: dict[str, tuple[str, str]] = {
    "too-long": ("error", "name longer than the profile allows (UTF-8 bytes)"),
    "forbidden-char": ("error", 'a character some file systems refuse: \\ / : * ? " < > | or a control character'),
    "spacing": ("error", "double space, or a space or dot at an end"),
    "invisible": ("error", "an invisible character (bidi control, zero-width joiner, BOM)"),
    "parentheses": ("error", "parentheses (the profile writes parts with « - »)"),
    "comma": ("error", "a comma (the profile writes none)"),
    "equals": ("error", "«=» between titles (the profile writes «أو»)"),
    "ta-prefix": ("error", "«ط» before a publisher or an edition number (the profile writes the publisher alone)"),
    "hamzat-wasl": ("error", "a hamza written on a hamzat al-wasl («الإستغفار» for «الاستغفار»)"),
    "presentation-forms": ("error", "Arabic presentation forms («ﺟﻬﺎﺩ» for «جهاد»): invisible to search"),
    "persian-letters": ("warning", "Persian letters ی ک typed in Arabic text"),
    "tatweel": ("warning", "tatweel «ـ» (kashida) in a name"),
    "not-nfc": ("warning", "not in Unicode NFC (marks in another order): the same name may exist twice"),
    "forbidden-word": ("warning", "an uploader's word or a duplicate marker («تحميل», «_alt», «نسخة ثانية»)"),
    "extension": ("warning", "an extension the profile does not expect"),
    "raw-name": ("warning", "a raw download name («12_3456.pdf», «trm01.pdf»): nothing tells what the book is"),
    "one-file-folder": ("warning", "a folder that holds one file (a single book is a plain file)"),
    "volume-twice": ("error", "two volumes with the same number"),
    "numbered-99": ("warning", "indexes numbered 99 (they take the number after the last volume)"),
}

_INVISIBLE = re.compile("[​‍‎‏‪-‮⁦-⁩﻿]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_TA = re.compile(r"(?:^|[\s(\-])ط\.?\s?(?=[0-9٠-٩]|دار|مكتبة|مؤسسة|مطبعة|المطبعة|المكتبة|الدار)")
_RAW = re.compile(r"^(\d+_[^/]*|[A-Za-z][A-Za-z_-]*?\d{1,3}[a-z]?)\.[A-Za-z0-9]{2,4}$", re.I)
_FRONT = re.compile(r"المقدمة|الواجهة|الفهارس|ملحق|صور المخطوط|مقدمة|تقديم")
_ARABIC = re.compile(r"[؀-ۿ]")


def _split_ext(name: str, is_dir: bool) -> tuple[str, str]:
    if is_dir:
        return name, ""
    stem, ext = os.path.splitext(name)
    if not stem or len(ext) > 6 or " " in ext:
        return name, ""
    return stem, ext


def fix_name(name: str, profile: str | NameProfile = "warraq", *, is_dir: bool = False) -> str:
    """The name with every mechanical fix of the profile applied (characters, spacing, brackets, commas, «=», «ط»,
    hamzat al-wasl, presentation forms, Persian letters, tatweel, NFC). Words are never reordered or dropped."""
    prof = get_profile(profile)
    stem, ext = _split_ext(name, is_dir)
    s = unicodedata.normalize("NFKC", stem) if has_presentation_forms(stem) else stem
    s = unicodedata.normalize("NFC", _INVISIBLE.sub("", s)).replace("ـ", "")
    if _ARABIC.search(s):
        s = s.translate(str.maketrans("یک", "يك"))
    if prof.check_wasl:
        s = fix_wasl(s)
    if not prof.equals:
        s = re.sub(r"\s*=\s*", " أو ", s)
    if not prof.ta_prefix:
        s = re.sub(r"(^|[\s(\-])ط\.?\s?(?=[0-9٠-٩])", r"\1الطبعة ", s)
        s = re.sub(r"(^|[\s(\-])ط\.?\s(?=دار|مكتبة|مؤسسة|مطبعة|المطبعة|المكتبة|الدار)", r"\1", s)
        s = re.sub(r"\(\s+", "(", s)
    if not prof.parentheses:
        # an edition in brackets at the end becomes a part of its own: «X (ت Y - Z)» → «X - ت Y - Z»
        s = re.sub(r"\s*\(((?:ت|ط|تحقيق|ترجمة|دار|مكتبة|مؤسسة|مطبعة|المطبعة)\s[^()]*)\)\s*$", r" - \1", s)
        s = re.sub(r"\s*\(([^()]*)\)\s*", lambda m: f" {m.group(1).strip()} ", s).replace("(", " ").replace(")", " ")
    if not prof.commas:
        s = re.sub(r"\s*[،,]\s*(?=دار|مكتبة|مؤسسة|مطبعة|المطبعة|المكتبة|الدار|منشورات)", " - ", s)
        s = re.sub(r"\s*[،,]\s*", " ", s)
    s = re.sub(r"(?:\s+-){2,}\s+", " - ", s)
    s = safe_filename(s, max_bytes=prof.max_bytes, keep_parentheses=prof.parentheses, extension=ext.lower() if
                      prof.allowed_extensions else ext)
    return s


def audit_name(
    name: str, profile: str | NameProfile = "warraq", *, is_dir: bool = False, path: str = ""
) -> list[Issue]:
    """Every rule of the profile that `name` (one path component) breaks.

    >>> [i.code for i in audit_name("الإعتصام (ط دار ابن عفان).pdf")]
    ['parentheses', 'ta-prefix', 'hamzat-wasl']
    """
    prof = get_profile(profile)
    out: list[Issue] = []
    p = path or name

    def add(code: str, detail: str = "") -> None:
        sev, msg = CHECKS[code]
        out.append(Issue(code, msg, p, sev, detail))

    stem, ext = _split_ext(name, is_dir)
    n = len(name.encode())
    if n > prof.max_bytes:
        add("too-long", f"{n} > {prof.max_bytes} bytes")
    bad = sorted({c for c in name if c in FORBIDDEN} | {c for c in name if _CONTROL.match(c)})
    if bad:
        add("forbidden-char", " ".join(repr(c) for c in bad))
    if "  " in name or name != name.strip() or stem.endswith((" ", ".")) or name.startswith("."):
        add("spacing")
    if _INVISIBLE.search(name):
        add("invisible", " ".join(f"U+{ord(c):04X}" for c in sorted(set(_INVISIBLE.findall(name)))))
    if not prof.parentheses and ("(" in name or ")" in name):
        add("parentheses")
    if not prof.commas and re.search(r"[،,]", name):
        add("comma")
    if not prof.equals and "=" in name:
        add("equals")
    if not prof.ta_prefix and _TA.search(stem):
        add("ta-prefix")
    if prof.check_wasl:
        errs = wasl_errors(stem)
        if errs:
            add("hamzat-wasl", ", ".join(f"{e.word} → {e.suggestion}" for e in errs))
    if has_presentation_forms(name):
        add("presentation-forms")
    if _ARABIC.search(name) and re.search("[یک]", name):
        add("persian-letters")
    if "ـ" in name:
        add("tatweel")
    if not unicodedata.is_normalized("NFC", name):
        add("not-nfc")
    low = name.lower()
    words = [w for w in prof.forbidden_words if w.lower() in low]
    if words:
        add("forbidden-word", ", ".join(words))
    if not is_dir and prof.allowed_extensions and ext.lower() not in prof.allowed_extensions:
        add("extension", ext or "(none)")
    if not is_dir and prof.allowed_extensions and _RAW.match(name):
        add("raw-name")
    return out


def audit_tree(
    root: str | os.PathLike[str],
    profile: str | NameProfile = "warraq",
    *,
    skip_hidden: bool = True,
) -> Iterator[tuple[Issue, str]]:
    """Walk `root` and yield (issue, fixed name or "") for every file and folder name; paths are relative to `root`."""
    prof = get_profile(profile)
    base = Path(root)
    if not base.is_dir():
        raise NotADirectoryError(f"{root}: not a directory")
    for dirpath, dirnames, filenames in os.walk(base):
        if skip_hidden:
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            filenames = [f for f in filenames if not f.startswith(".")]
        rel = Path(dirpath).relative_to(base)
        for d in dirnames:
            r = str(rel / d) if str(rel) != "." else d
            for i in audit_name(d, prof, is_dir=True, path=r):
                yield i, _fix_or_empty(d, prof, True)
        files = sorted(filenames)
        for f in files:
            r = str(rel / f) if str(rel) != "." else f
            for i in audit_name(f, prof, path=r):
                yield i, _fix_or_empty(f, prof, False)
        if str(rel) == ".":
            continue
        if prof.one_file_folder and len(files) == 1 and not dirnames:
            sev, msg = CHECKS["one-file-folder"]
            yield Issue("one-file-folder", msg, str(rel), sev, files[0]), ""
        by: dict[str, list[str]] = defaultdict(list)
        for f in files:
            m = re.match(r"^(\d+) - ", f)
            if m and m.group(1).strip("0") and not _FRONT.search(os.path.splitext(f)[0].rsplit(" - ", 1)[-1]):
                by[m.group(1)].append(f)
            if prof.numbered_99 and re.search(r"(^| )99 - ", f):
                sev, msg = CHECKS["numbered-99"]
                yield Issue("numbered-99", msg, str(rel / f), sev), ""
        for nn, fs in sorted(by.items()):
            if len(fs) > 1:
                sev, msg = CHECKS["volume-twice"]
                for f in fs:
                    yield Issue("volume-twice", msg, str(rel / f), sev, nn), ""


def _fix_or_empty(name: str, prof: NameProfile, is_dir: bool) -> str:
    f = fix_name(name, prof, is_dir=is_dir)
    return f if f != name else ""
