"""Normalisation profiles for Arabic bibliographic text.

Two needs pull in opposite directions:

* **search** wants every spelling of a word to meet: «الإمام» = «الامام», «القرآن» = «القران», «مكتبة» = «مكتبه»;
* **display** wants the text exactly as printed, only cleaner: one Unicode form (NFC), no tatweel, one space,
  no space before «،» or «:».

Both are offered here as :class:`NormProfile` values, and :func:`normalize_mapped` keeps the index of every output
character in the original string, so a search hit on the folded form can be highlighted in the printed one.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

__all__ = [
    "DIACRITICS",
    "key_norm",
    "Mapped",
    "NormProfile",
    "PROFILES",
    "normalize",
    "normalize_mapped",
    "search_key",
    "strip_diacritics",
    "to_ascii_digits",
]

#: Arabic combining marks: Quranic annotation signs, harakat, shadda, sukun, dagger alif, small high signs.
DIACRITICS = "[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]"
_DIAC = re.compile(DIACRITICS)
_MARK = re.compile(DIACRITICS)
TATWEEL = "ـ"
_PRESENTATION = re.compile("[ﭐ-﷿ﹰ-﻿]")
_ZERO_WIDTH = "​‍‎‏‪‫‬‭‮⁦⁧⁨⁩﻿"

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PERSIAN = {"ی": "ي", "ې": "ي", "ى": "ى", "ک": "ك", "ڪ": "ك", "ۀ": "ة", "ە": "ه", "ھ": "ه", "ہ": "ه"}
_ALEF = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا"}
_HAMZA_SEAT = {"ؤ": "و", "ئ": "ي"}


def to_ascii_digits(text: str) -> str:
    """Arabic-Indic (٠-٩) and Persian (۰-۹) digits → ASCII digits; nothing else changes."""
    return text.translate(_DIGITS)


def strip_diacritics(text: str) -> str:
    """Remove harakat, shadda, sukun, tanwin, dagger alif and Quranic signs (letters stay as written)."""
    return _DIAC.sub("", text)


@dataclass(frozen=True)
class NormProfile:
    """What a normalisation does. Every switch is independent; the named profiles are in :data:`PROFILES`."""

    name: str = "custom"
    presentation_forms: bool = True  # ﻻ ﺟ → لا ج (text copied out of PDFs)
    persian_letters: bool = True  # ی ک ۀ typed for ي ك ة
    zero_width: bool = True  # drop ZWJ, LRM/RLM, bidi controls, BOM (ZWNJ is kept: Persian needs it)
    tatweel: bool = True  # drop ـ
    diacritics: bool = False  # drop harakat, shadda, sukun …
    alef: bool = False  # أ إ آ ٱ → ا
    ta_marbuta: bool = False  # ة → ه
    alef_maqsura: bool = False  # ى → ي
    hamza_seats: bool = False  # ؤ → و, ئ → ي
    lone_hamza: bool = False  # drop ء
    digits: bool = False  # ٠-٩ → 0-9
    punctuation: str = "keep"  # "keep" | "space" (non letter/digit → space) | "tidy" (Arabic spacing rules)
    casefold: bool = False  # Latin case
    nfc: bool = True  # one Unicode form (combining marks in canonical order)
    collapse_spaces: bool = True

    def but(self, **changes: object) -> NormProfile:
        """A copy with some switches changed: ``PROFILES['search'].but(alef_maqsura=False)``."""
        return replace(self, name=f"{self.name}*", **changes)  # type: ignore[arg-type]


PROFILES: dict[str, NormProfile] = {
    "display": NormProfile(name="display", punctuation="tidy"),
    "search": NormProfile(
        name="search",
        diacritics=True,
        alef=True,
        ta_marbuta=True,
        alef_maqsura=True,
        hamza_seats=True,
        lone_hamza=True,
        digits=True,
        punctuation="space",
        casefold=True,
    ),
}
# «loose»: search + the article and «و» of conjunction are not significant (catalogue titles that begin with «و»
# or drop «ال» meet their twins); a matching key, not a display form
PROFILES["loose"] = replace(PROFILES["search"], name="loose")


@dataclass(frozen=True)
class Mapped:
    """A normalised string that remembers where each of its characters came from."""

    text: str
    original: str
    offsets: tuple[int, ...]  # offsets[i] = index in `original` of the character that produced text[i]

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """The span of `original` that produced ``text[start:end]`` (marks after the last letter included)."""
        if not self.text or start >= end:
            o = self.offsets[start] if start < len(self.offsets) else len(self.original)
            return o, o
        a = self.offsets[start]
        b = self.offsets[end - 1] + 1
        while b < len(self.original) and (_MARK.match(self.original[b]) or self.original[b] == TATWEEL):
            b += 1
        return a, b

    def find(self, needle: str, profile: str | NormProfile = "search") -> list[tuple[int, int]]:
        """Every place `needle` occurs in the normalised text, as spans of the ORIGINAL string."""
        key = normalize(needle, profile)
        if not key:
            return []
        out, i = [], self.text.find(key)
        while i >= 0:
            out.append(self.original_span(i, i + len(key)))
            i = self.text.find(key, i + 1)
        return out


def _profile(p: str | NormProfile) -> NormProfile:
    if isinstance(p, NormProfile):
        return p
    try:
        return PROFILES[p]
    except KeyError:
        raise ValueError(f"unknown normalisation profile {p!r}; choose one of {', '.join(PROFILES)}") from None


def _char(ch: str, p: NormProfile) -> str:
    """One original character → its replacement (possibly empty, possibly several characters)."""
    if p.zero_width and ch in _ZERO_WIDTH:
        return ""
    if p.presentation_forms and _PRESENTATION.match(ch):
        ch = unicodedata.normalize("NFKC", ch)
        if not ch.strip():
            return " "
    out = []
    for c in ch:
        if p.persian_letters and c in _PERSIAN:
            c = _PERSIAN[c]
        if p.tatweel and c == TATWEEL:
            continue
        if p.alef or p.hamza_seats or p.diacritics:
            # a letter that carries a hamza or a madda is a base letter plus a combining mark (أ = ا + U+0654):
            # decomposing first lets the seat rules and the mark rule act on its parts
            if p.alef and c in _ALEF:
                c = "ا"
            elif p.hamza_seats and c in _HAMZA_SEAT:
                c = _HAMZA_SEAT[c]
        if p.diacritics and _MARK.match(c):
            continue
        if p.ta_marbuta and c == "ة":
            c = "ه"
        if p.alef_maqsura and c == "ى":
            c = "ي"
        if p.lone_hamza and c == "ء":
            continue
        if p.digits:
            c = c.translate(_DIGITS)
        if p.casefold:
            c = c.casefold()
        out.append(c)
    s = "".join(out)
    if p.punctuation == "space":
        s = "".join(c if (c.isalnum() or _MARK.match(c)) else " " for c in s)
    return s


_LOOSE_ART = re.compile(r"^(?:و|ف)?(?:ال|لل)(?=\S{2,})")


def _loose_word(w: str) -> str:
    return _LOOSE_ART.sub("", w) if len(w) > 4 else w


def normalize_mapped(text: str | None, profile: str | NormProfile = "search") -> Mapped:
    """Normalise `text` and keep, for every output character, the index of the original character behind it."""
    p = _profile(profile)
    src = text or ""
    chars: list[str] = []
    offs: list[int] = []
    if p.nfc and not p.diacritics:
        # canonical order of marks (shadda + fatha typed in either order) needs NFC over each letter's cluster
        i = 0
        while i < len(src):
            j = i + 1
            while j < len(src) and unicodedata.combining(src[j]):
                j += 1
            cluster = unicodedata.normalize("NFC", "".join(_char(c, p) for c in src[i:j]))
            for c in cluster:
                chars.append(c)
                offs.append(i)
            i = j
    else:
        for i, c in enumerate(src):
            for r in _char(c, p):
                chars.append(r)
                offs.append(i)
    if p.punctuation == "tidy":
        chars, offs = _tidy(chars, offs)
    if p.collapse_spaces:
        c2: list[str] = []
        o2: list[int] = []
        for c, o in zip(chars, offs):
            if c.isspace():
                if c2 and c2[-1] != " ":
                    c2.append(" ")
                    o2.append(o)
                continue
            c2.append(c)
            o2.append(o)
        if c2 and c2[-1] == " ":
            c2.pop()
            o2.pop()
        chars, offs = c2, o2
    if p.name.startswith("loose"):
        words, wo, cur, co = [], [], [], []
        for c, o in zip([*chars, " "], [*offs, len(src)]):
            if c == " ":
                if cur:
                    w = "".join(cur)
                    lw = _loose_word(w)
                    cut = len(w) - len(lw)
                    words.append(lw)
                    wo.append(co[cut:])
                cur, co = [], []
            else:
                cur.append(c)
                co.append(o)
        chars, offs = [], []
        for k, (w, o) in enumerate(zip(words, wo)):
            if k:
                chars.append(" ")
                offs.append(o[0] if o else 0)
            chars.extend(w)
            offs.extend(o)
    return Mapped("".join(chars), src, tuple(offs))


_NO_SPACE_BEFORE = set("،؛:.!؟?,;)]»")
_NO_SPACE_AFTER = set("([«")


def _tidy(chars: list[str], offs: list[int]) -> tuple[list[str], list[int]]:
    """Arabic typographic spacing: no space before «، ؛ : . ! ؟ ) » …», one after them, none inside brackets."""
    out_c: list[str] = []
    out_o: list[int] = []
    n = len(chars)
    for k, (c, o) in enumerate(zip(chars, offs)):
        if c.isspace():
            nxt = next((chars[j] for j in range(k + 1, n) if not chars[j].isspace()), "")
            prv = out_c[-1] if out_c else ""
            if nxt in _NO_SPACE_BEFORE or prv in _NO_SPACE_AFTER:
                continue
            out_c.append(" ")
            out_o.append(o)
            continue
        if out_c and out_c[-1] in "،؛" and not c.isspace():
            out_c.append(" ")
            out_o.append(o)
        out_c.append(c)
        out_o.append(o)
    return out_c, out_o


def normalize(text: str | None, profile: str | NormProfile = "search") -> str:
    """Normalise `text` with a named profile (``"search"``, ``"display"``, ``"loose"``) or a :class:`NormProfile`.

    >>> normalize("الإِمامُ أبو حامدٍ الغزاليّ")
    'الامام ابو حامد الغزالي'
    >>> normalize("مكتبــة  المعارف ،الرباط", "display")
    'مكتبة المعارف، الرباط'
    """
    return normalize_mapped(text, profile).text


def search_key(text: str | None) -> str:
    """The search-normal form: every spelling of a word folds to one key.

    Drops diacritics and tatweel, folds أ إ آ ٱ → ا, ة → ه, ى → ي, ؤ → و, ئ → ي, drops ء, maps presentation forms
    and Persian letters to Arabic ones, digits to ASCII, punctuation to a space; Latin is case-folded.

    >>> search_key("القُرْآن الكريم")
    'القران الكريم'
    """
    return normalize_mapped(text, PROFILES["search"]).text


# ------------------------------------------------------------------------------------------- catalogue keys
_KEY_MARKS = re.compile("[ً-ْٰـ]")
_KEY_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي", "ء": None})
_KEY_OUT = re.compile("[^ء-ي0-9 ]")


def key_norm(text: str | None) -> str:
    """The catalogue-key normalisation shared by the Warraq tools (keys v1, frozen: work ids are hashed from it).

    NFC; drop U+064B–U+0652, U+0670 and tatweel; fold أ إ آ ٱ → ا, ة → ه, ى → ي, ؤ → و, ئ → ي; drop ء; digits →
    ASCII; every character outside U+0621–U+064A, 0–9 and space → a space; single spaces. Unlike
    :func:`search_key`, Latin letters, Persian letters and presentation forms are not kept: the key is for Arabic
    catalogue matching and must never change.

    >>> key_norm("الإمامُ ابن تيميّة (ت 728هـ)")
    'الامام ابن تيميه ت 728ه'
    """
    s = unicodedata.normalize("NFC", text or "")
    s = _KEY_MARKS.sub("", s).translate(_KEY_FOLD).translate(_DIGITS)
    return " ".join(_KEY_OUT.sub(" ", s).split())
