"""Spelling checks that matter in titles and file names, and safe file names.

**Hamzat al-wasl.** The verbal nouns of the derived patterns VII, VIII and X («انفعال», «افتعال», «استفعال») and a
short list of nouns («اسم», «ابن», «اثنان», «امرأة») begin with a connecting hamza, written as a bare alif:
«الاستغفار», not «الإستغفار». Writing a hamza on it is the most frequent spelling error in Arabic titles, and it
breaks exact search. Pattern IV («إفعال»: إتقان، إنفاق، إنتاج) does take a hamza and is never flagged.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .normalize import NormProfile, normalize_mapped

__all__ = ["WaslError", "fix_wasl", "has_presentation_forms", "safe_filename", "wasl_errors"]

_C = r"[بتثجحخدذرزسشصضطظعغفقكلمنهويءئؤأ]"  # one consonant (a hamza counts)
_PREFIX = r"(?:وال|فال|بال|كال|لل|ال|و|ف|ب|ك|ل)?"
# VII إن C C ا, VIII إ C ت C ا, X إست C C ا; VIII after ص ض (اصط… اضط…) and ز (ازد…); VIII of a root whose first
# radical is و or أ, or ت, د (the ت assimilated: اتّصال، اتّخاذ، ادّعاء, the shadda often left out)
_WASL_STEM = (
    rf"إ(?:ست{_C}{_C}ا|{_C}ت{_C}ا|ن{_C}{_C}ا|[صض]ط{_C}ا|زد{_C}ا"
    r"|ت(?:صال|حاد|فاق|جاه|خاذ|ساع|قاء|هام|كال|زان|ضاح|عاظ|سام|ساق)"
    r"|د(?:عاء|خار)"
    r")"
)
_WASL_RE = re.compile(rf"(?<![\w])({_PREFIX})({_WASL_STEM})")
# nouns with hamzat al-wasl: «اسم», «ابن», «ابنة», «اثنان», «امرأة», «امرؤ», «است»
_NOUNS = {
    "إسم": "اسم", "إسما": "اسما", "إسمه": "اسمه", "إسمها": "اسمها", "إسمي": "اسمي", "إبن": "ابن", "إبنة": "ابنة",
    "إبنه": "ابنه", "إبنها": "ابنها", "إثنان": "اثنان", "إثنين": "اثنين", "إثنا": "اثنا", "إثني": "اثني",
    "إثنتان": "اثنتان", "إثنتين": "اثنتين", "إثنتا": "اثنتا", "إثنتي": "اثنتي", "إمرأة": "امرأة", "إمرأته": "امرأته",
    "إمرؤ": "امرؤ", "إمرئ": "امرئ", "إمرأ": "امرأ",
}
_NOUN_RE = re.compile(
    rf"(?<![\w])({_PREFIX})({'|'.join(sorted(map(re.escape, _NOUNS), key=len, reverse=True))})(?![\w])"
)
# words the pattern would catch that take a hamzat al-qat' (pattern IV of a root whose second radical is ت, etc.)
_EXCEPT = {"إستبرق", "إسترليني", "إستونيا", "إسترالي", "إسترالية", "إستانبول", "إسطنبول", "إسطبل", "إسطوانة",
           "إسطرلاب", "إنتاج", "إتقان", "إتلاف", "إتمام", "إتباع", "إتحاف", "إتيان", "إطلاق", "إطعام",
           "إطلاع", "إطار", "إطراء", "إتاحة", "إتقانه", "إتاوة"}
_PRESENTATION = re.compile("[ﭐ-﷿ﹰ-ﻼ]")
_BARE = NormProfile(name="bare", diacritics=True, nfc=False, collapse_spaces=False, zero_width=False,
                    presentation_forms=False, persian_letters=False)


@dataclass(frozen=True)
class WaslError:
    """A hamza written on a hamzat al-wasl: the span in the text, the word as written, the correct spelling."""

    start: int
    end: int
    word: str
    suggestion: str


def _word_at(text: str, i: int) -> tuple[int, int]:
    j = i
    while j < len(text) and not text[j].isspace() and text[j] not in "-–،,.:؛()[]«»":
        j += 1
    return i, j


def wasl_errors(text: str) -> list[WaslError]:
    """Every word of `text` that writes a hamza on a hamzat al-wasl (diacritics and tatweel are seen through).

    >>> [e.suggestion for e in wasl_errors("كتاب الإستغفار وإسم الله")]
    ['الاستغفار', 'واسم']
    """
    src = unicodedata.normalize("NFC", text or "")
    mp = normalize_mapped(src, _BARE)
    plain = mp.text
    out: list[WaslError] = []
    seen: set[int] = set()
    for rx in (_WASL_RE, _NOUN_RE):
        for m in rx.finditer(plain):
            a, b = _word_at(plain, m.start())
            if a in seen:
                continue
            word = plain[a:b]
            pre = m.group(1) or ""
            stem = word[len(pre) :]
            if any(stem.startswith(x) and len(stem) - len(x) <= 2 for x in _EXCEPT):
                continue
            seen.add(a)
            oa, ob = mp.original_span(a, b)
            hamza = mp.offsets[a + len(pre)]
            orig = src[oa:ob]
            k = hamza - oa
            j = k + 1
            while j < len(orig) and unicodedata.combining(orig[j]):
                j += 1  # a kasra under the hamza goes with it: a wasl alif carries no vowel
            out.append(WaslError(oa, ob, orig, orig[:k] + "ا" + orig[j:]))
    return sorted(out, key=lambda e: e.start)


def fix_wasl(text: str) -> str:
    """`text` with every :func:`wasl_errors` word corrected («الإجتهاد» → «الاجتهاد»)."""
    s = unicodedata.normalize("NFC", text or "")
    for e in reversed(wasl_errors(s)):
        s = s[: e.start] + e.suggestion + s[e.end :]
    return s


def has_presentation_forms(text: str) -> bool:
    """True when the text holds Arabic presentation forms («ﺟﻬﺎﺩ» for «جهاد»), typical of text copied out of a PDF:
    they look right but are not found by search and sort apart."""
    return bool(_PRESENTATION.search(text or ""))


# ------------------------------------------------------------------------------------------------ file names
FORBIDDEN = '\\/:*?"<>|'
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.I)


def safe_filename(
    name: str,
    max_bytes: int = 255,
    *,
    keep_parentheses: bool = True,
    extension: str = "",
) -> str:
    """A name every file system takes (FAT, NTFS, ext4, Android): no ``\\ / : * ? " < > |``, no control characters,
    single spaces, no space or dot at either end, ≤ `max_bytes` UTF-8 bytes (cut between words, never inside one).

    ``/`` and ``:`` become a space, ``?`` becomes «؟», ``"…"`` becomes «…»; Persian ی ک ۀ typed for Arabic letters are
    replaced; presentation forms become letters.

    >>> safe_filename('ديوان المتنبي: شرح "العكبري" 1276 هـ / 1860?')
    'ديوان المتنبي شرح «العكبري» 1276 هـ 1860؟'
    """
    s = unicodedata.normalize("NFKC", name) if _PRESENTATION.search(name or "") else (name or "")
    s = unicodedata.normalize("NFC", s)
    s = s.translate(str.maketrans("یکۀ", "يكة"))
    s = _CONTROL.sub("", s)
    s = re.sub(r"\s*\((?:\?|؟)\)", "", s)  # a reader's «(?)»
    if not keep_parentheses:
        s = s.replace("(", " ").replace(")", " ")
    s = re.sub(r"\s*[/\\:|]\s*", " ", s).replace("?", "؟").replace("*", "")
    s = re.sub(r'"([^"]*)"', r"«\1»", s).replace('"', "").replace("<", "").replace(">", "")
    s = re.sub(r"\s+", " ", s).strip(" .")
    if _RESERVED.match(s):
        s = "_" + s
    limit = max_bytes - len(extension.encode())
    if len(s.encode()) > limit:
        words = s.split(" ")
        while len(words) > 1 and len(" ".join(words).encode()) > limit:
            words.pop()
        s = " ".join(words).rstrip(" -.،")
        if len(s.encode()) > limit:  # one very long word: cut at a character boundary
            b = s.encode()[:limit]
            s = b.decode("utf-8", "ignore")
    return s + extension
