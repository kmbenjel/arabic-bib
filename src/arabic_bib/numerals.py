"""Arabic number words as they appear in bibliographic text.

* ordinals of editions and centuries: «الطبعة الأولى», «الحادية عشرة», «القرن الرابع عشر»;
* cardinal years written in words, as classical biographies give them: «سنة ثمان وعشرين وسبعمائة» → 728.
"""

from __future__ import annotations

import re

from .normalize import search_key

__all__ = ["cardinal_value", "ordinal_value", "ordinal_word", "parse_number"]

_K = search_key

_ORD_M = ["", "الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع", "الثامن", "التاسع", "العاشر"]
_ORD_F = ["", "الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة", "السابعة", "الثامنة", "التاسعة",
          "العاشرة"]
_TENS = ["", "", "العشرون", "الثلاثون", "الأربعون", "الخمسون", "الستون", "السبعون", "الثمانون", "التسعون"]

# every spelling met in print, folded: «الاولي», «الأولى», «أولى», «اولى», «الحادي عشر», «الحاديه عشره» …
_ORD: dict[str, int] = {}


def _add_ord(word: str, n: int) -> None:
    k = _K(word)
    _ORD.setdefault(k, n)
    if k.startswith("ال"):
        _ORD.setdefault(k[2:], n)  # «طبعة أولى», «ط ثانية»


for _n in range(1, 11):
    _add_ord(_ORD_M[_n], _n)
    _add_ord(_ORD_F[_n], _n)
for _n in (1,):
    _add_ord("الحادي", 1)
    _add_ord("الحادية", 1)
for _n in range(11, 20):
    u = _n - 10
    um = "الحادي" if u == 1 else _ORD_M[u]
    uf = "الحادية" if u == 1 else _ORD_F[u]
    _add_ord(f"{um} عشر", _n)
    _add_ord(f"{uf} عشرة", _n)
    _add_ord(f"{uf} عشر", _n)  # a common misprint, still unambiguous
for _t in range(2, 10):
    _add_ord(_TENS[_t], 10 * _t)
    _add_ord(_TENS[_t].replace("ون", "ين"), 10 * _t)  # «في القرن العشرين»
    for u in range(1, 10):
        for um in ({_ORD_M[u], "الحادي"} if u == 1 else {_ORD_M[u]}):
            _add_ord(f"{um} و{_TENS[_t]}", 10 * _t + u)
            _add_ord(f"{um} و{_TENS[_t].replace('ون', 'ين')}", 10 * _t + u)
        for uf in ({_ORD_F[u], "الحادية"} if u == 1 else {_ORD_F[u]}):
            _add_ord(f"{uf} و{_TENS[_t]}", 10 * _t + u)
            _add_ord(f"{uf} و{_TENS[_t].replace('ون', 'ين')}", 10 * _t + u)
_ORD_MAX_WORDS = 3


def ordinal_value(text: str) -> int | None:
    """«الأولى» → 1, «الحادية عشرة» → 11, «الخامسة والعشرون» → 25, «4» / «٤» → 4; else None.

    Accepts the masculine and feminine forms, with or without the article and the hamza.
    """
    k = _K(text)
    if not k:
        return None
    if k.isdigit():
        return int(k)
    return _ORD.get(k)


def ordinal_word(n: int, feminine: bool = False, article: bool = True) -> str:
    """1 → «الأول» (or «الأولى»), 14 → «الرابع عشر», 21 → «الحادي والعشرون»; 1–99."""
    if not 1 <= n <= 99:
        raise ValueError("ordinal_word covers 1–99")
    units = _ORD_F if feminine else _ORD_M
    if n <= 10:
        w = units[n]
    elif n < 20:
        u = n - 10
        first = ("الحادية" if feminine else "الحادي") if u == 1 else units[u]
        w = f"{first} {'عشرة' if feminine else 'عشر'}"
    else:
        t, u = divmod(n, 10)
        if u == 0:
            w = _TENS[t]
        else:
            first = ("الحادية" if feminine else "الحادي") if u == 1 else units[u]
            w = f"{first} و{_TENS[t]}"
    if not article:
        w = " ".join(x[2:] if x.startswith("ال") else (("و" + x[3:]) if x.startswith("وال") else x) for x in w.split())
    return w


# cardinal words of years: units, teens, tens, hundreds, thousands; the counted noun's case does not matter
_UNITS = {
    1: "واحد واحدة إحدى احدى أحد",
    2: "اثنين اثنتين اثنتي اثني ثنتين اثنان اثنتان اثنا اثنتا",
    3: "ثلاث ثلاثة",
    4: "أربع أربعة",
    5: "خمس خمسة",
    6: "ست ستة",
    7: "سبع سبعة",
    8: "ثمان ثماني ثمانية",
    9: "تسع تسعة",
    10: "عشر عشرة",
}
_TENS_C = {20: "عشرين عشرون", 30: "ثلاثين ثلاثون", 40: "أربعين أربعون", 50: "خمسين خمسون", 60: "ستين ستون",
           70: "سبعين سبعون", 80: "ثمانين ثمانون", 90: "تسعين تسعون"}
_HUNDREDS = {100: "مائة مئة مائه مية", 200: "مائتين مئتين مائتان مئتان"}
_THOUSANDS = {1000: "ألف", 2000: "ألفين ألفان"}
_CARD: dict[str, int] = {}
for _v, _ws in (*_UNITS.items(), *_TENS_C.items(), *_HUNDREDS.items(), *_THOUSANDS.items()):
    for _w in _ws.split():
        _CARD[_K(_w)] = _v
for _u in range(3, 10):
    for _w in _UNITS[_u].split():
        for _h in ("مائة", "مئة"):
            _CARD.setdefault(_K(_w + _h), _u * 100)  # «سبعمائة», «ثمانمئة»
            _CARD.setdefault(_K(_w.rstrip("ة") + _h), _u * 100)
_CARD[_K("ثمانمائة")] = 800
_CARD[_K("ثمانمئة")] = 800
_CARD[_K("ثماني مائة")] = 800


def cardinal_value(text: str) -> int | None:
    """A year written in words → its number: «ثمان وعشرين وسبعمائة» → 728, «إحدى عشرة وثلاثمائة» → 311,
    «ست وخمسين وتسعمائة وألف» → 1956, «ثلاث مائة» → 300. Returns None when a word is not a number word."""
    k = _K(text)
    if not k:
        return None
    total, prev = 0, 0
    for w in k.split():
        if w in ("سنه", "عام", "في"):
            continue
        joined = w.startswith("و") and w[1:] in _CARD
        v = _CARD.get(w[1:] if joined else w)
        if v is None:
            return None
        if v == 100 and not joined and 3 <= prev <= 9:  # «ثلاث مائة» in two words
            total += prev * 100 - prev
            prev = 0
            continue
        total += v
        prev = v
    return total or None


_NUMBER_RE = re.compile(r"[0-9٠-٩۰-۹]+")


def parse_number(text: str) -> int | None:
    """Digits, an ordinal or a cardinal in words → int; else None."""
    k = _K(text)
    if not k:
        return None
    m = _NUMBER_RE.fullmatch(k)
    if m:
        return int(k)
    return ordinal_value(k) or cardinal_value(k)
