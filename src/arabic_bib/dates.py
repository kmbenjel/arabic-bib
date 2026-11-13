"""Death years, centuries and the Hijri calendar.

Conversion uses the **tabular (arithmetic) Islamic calendar**, the convention of reference works and of most
software (the "Kuwaiti algorithm"): 30-year cycles with leap years 2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29, epoch
1 Muharram 1 AH = Friday 16 July 622 (Julian). A real month began with the sighting of the new moon, so a historical
date may differ from the tabular one by a day or two; for 1343–1500 AH, Saudi Arabia's Umm al-Qura calendar is
available through the optional ``hijridate`` package (``calendar="umalqura"``).

Gregorian dates before 15 October 1582 are given in the Julian calendar, as historians do (``proleptic=True``
gives the proleptic Gregorian instead).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import to_ascii_digits
from .numerals import cardinal_value, ordinal_value, ordinal_word

__all__ = [
    "Death",
    "century_label",
    "century_of",
    "find_dates",
    "gregorian_to_hijri",
    "gregorian_year_to_hijri",
    "hijri_to_gregorian",
    "hijri_year_to_gregorian",
    "parse_century",
    "parse_death",
    "strip_dates",
]

# ---------------------------------------------------------------------------------------------- calendar arithmetic
_EPOCH = 1948440  # JDN of 1 Muharram 1 AH (16 July 622 Julian)
_GREGORIAN_START = 2299161  # JDN of 15 October 1582


def _islamic_to_jdn(y: int, m: int, d: int) -> int:
    return d + (59 * (m - 1) + 1) // 2 + (y - 1) * 354 + (3 + 11 * y) // 30 + _EPOCH - 1


def _month_length(y: int, m: int) -> int:
    if m % 2 == 1:
        return 30
    if m == 12 and (14 + 11 * y) % 30 < 11:
        return 30
    return 29


def _jdn_to_islamic(j: int) -> tuple[int, int, int]:
    y = (30 * (j - _EPOCH) + 10646) // 10631
    while _islamic_to_jdn(y + 1, 1, 1) <= j:
        y += 1
    while _islamic_to_jdn(y, 1, 1) > j:
        y -= 1
    m = 1
    while m < 12 and _islamic_to_jdn(y, m + 1, 1) <= j:
        m += 1
    return y, m, j - _islamic_to_jdn(y, m, 1) + 1


def _gregorian_to_jdn(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    yy, mm = y + 4800 - a, m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def _julian_to_jdn(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    yy, mm = y + 4800 - a, m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - 32083


def _jdn_to_gregorian(j: int) -> tuple[int, int, int]:
    a = j + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return 100 * b + d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1


def _jdn_to_julian(j: int) -> tuple[int, int, int]:
    c = j + 32082
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1


def _check_hijri(y: int, m: int, d: int) -> None:
    if y < 1 or not 1 <= m <= 12:
        raise ValueError(f"no Hijri date {y}-{m}-{d}: the year starts at 1 and months run 1–12")
    if not 1 <= d <= _month_length(y, m):
        raise ValueError(f"Hijri month {y}-{m} has {_month_length(y, m)} days in the tabular calendar, not {d}")


def _umalqura():  # pragma: no cover - optional dependency
    try:
        import hijridate  # type: ignore[import-not-found]
    except ImportError:
        raise ImportError(
            "calendar='umalqura' needs the optional package hijridate: pip install 'arabic-bib[umalqura]'"
        ) from None
    return hijridate


def hijri_to_gregorian(
    year: int, month: int = 1, day: int = 1, *, proleptic: bool = False, calendar: str = "tabular"
) -> tuple[int, int, int]:
    """A Hijri date → (year, month, day) in the Julian calendar before 1582-10-15, Gregorian after.

    >>> hijri_to_gregorian(1, 1, 1)
    (622, 7, 16)
    >>> hijri_to_gregorian(1400, 1, 1)
    (1979, 11, 21)
    """
    if calendar == "umalqura":  # pragma: no cover - optional dependency
        g = _umalqura().Hijri(year, month, day).to_gregorian()
        return g.year, g.month, g.day
    if calendar != "tabular":
        raise ValueError("calendar is 'tabular' or 'umalqura'")
    _check_hijri(year, month, day)
    j = _islamic_to_jdn(year, month, day)
    return _jdn_to_gregorian(j) if proleptic or j >= _GREGORIAN_START else _jdn_to_julian(j)


def gregorian_to_hijri(
    year: int, month: int = 1, day: int = 1, *, proleptic: bool = False, calendar: str = "tabular"
) -> tuple[int, int, int]:
    """A Gregorian date (Julian before 1582-10-15 unless `proleptic`) → the tabular Hijri (year, month, day).

    >>> gregorian_to_hijri(1328, 9, 26)
    (728, 11, 20)
    """
    if calendar == "umalqura":  # pragma: no cover - optional dependency
        h = _umalqura().Gregorian(year, month, day).to_hijri()
        return h.year, h.month, h.day
    if calendar != "tabular":
        raise ValueError("calendar is 'tabular' or 'umalqura'")
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError(f"no date {year}-{month}-{day}")
    j = _gregorian_to_jdn(year, month, day)
    if not proleptic and j < _GREGORIAN_START:
        j = _julian_to_jdn(year, month, day)
    if j < _EPOCH:
        raise ValueError(f"{year}-{month}-{day} is before the Hijri era (16 July 622)")
    return _jdn_to_islamic(j)


def hijri_year_to_gregorian(year: int) -> tuple[int, int]:
    """The Gregorian years a Hijri year overlaps: 728 → (1327, 1328), 1400 → (1979, 1980)."""
    a = hijri_to_gregorian(year, 1, 1)[0]
    b = hijri_to_gregorian(year, 12, _month_length(year, 12))[0]
    return a, b


def gregorian_year_to_hijri(year: int) -> tuple[int, int]:
    """The Hijri years a Gregorian year overlaps: 1999 → (1419, 1420); 1 Jan and 31 Dec may fall in a third."""
    a = gregorian_to_hijri(year, 1, 1)[0]
    b = gregorian_to_hijri(year, 12, 31)[0]
    return a, b


def century_of(year: int) -> int:
    """728 → 8 (the 8th century: 701–800); 700 → 7."""
    if year < 1:
        raise ValueError("years start at 1")
    return (year - 1) // 100 + 1


def century_label(c: int, era: str = "هـ") -> str:
    """8 → «القرن الثامن الهجري»; ``era="م"`` → «القرن الرابع عشر الميلادي»; era="" → «القرن الثامن»."""
    adj = {"هـ": " الهجري", "م": " الميلادي", "": ""}[era]
    return f"القرن {ordinal_word(c)}{adj}"


# ------------------------------------------------------------------------------------------------------- parsing
_D = r"[0-9٠-٩۰-۹]{1,4}"
_AH = r"(?:\s*(?:هـ|ه|ھ|هج|هجرية|للهجرة|من الهجرة)(?![ء-ي]))"
_CE = r"(?:\s*(?:م|ميلادية|للميلاد)(?![ء-ي]))"
_QUAL = {
    "بعد": "after", "قبل": "before", "نحو": "circa", "حوالي": "circa", "حوالى": "circa", "في حدود": "circa",
    "قرابة": "circa", "تقريبا": "circa", "تقريبًا": "circa", "بضع": "circa", "سنة نيف": "circa",
}
_QUAL_RE = r"(?:بعد|قبل|نحو|حوالي|حوالى|في حدود|قرابة)"
_DIED = (
    r"(?:المتوفى|المتوفي|المتوفّى|المتوفَّى|المتوفاة|توفي|توفّي|تُوفِّي|توفى|توفيت|وفاته|الوفاة|مات|ت\.?|ت:|ت\s*-)"
)

_DEATH_RE = re.compile(
    rf"(?P<died>(?<![ء-ي]){_DIED})?\s*:?\s*(?:في\s+)?(?:سنة|عام)?\s*(?P<q>{_QUAL_RE})?\s*(?:سنة|عام)?\s*"
    rf"(?P<y1>{_D})(?P<ah1>{_AH})?(?P<ce1>{_CE})?"
    rf"(?:\s*(?P<sep>[-–—/]|إلى|الى)\s*(?P<q2>{_QUAL_RE})?\s*(?P<y2>{_D})(?P<ah2>{_AH})?(?P<ce2>{_CE})?)?"
)
_CENTURY_RE = re.compile(
    r"(?:من\s+(?:علماء|أعلام|رجال)\s+)?(?<![ء-ي])(?:القرن|ق\.?)\s*(?P<n>[0-9٠-٩۰-۹]{1,2}|[ء-ي]+(?:\s+(?:عشر|و[ء-ي]+))?)"
    r"\s*(?P<era>الهجري|للهجرة|هـ|ه|الميلادي|م)?"
)
_WORD_YEAR_RE = re.compile(
    rf"(?P<died>(?<![ء-ي]){_DIED})?\s*(?:في\s+)?(?<![ء-ي])(?:سنة|عام)\s+(?P<q>{_QUAL_RE}\s+)?(?P<w>(?:[ء-ي]+\s*){{1,6}})"
)
_ALIVE_RE = re.compile(r"(?<![ء-ي])(?:معاصر|معاصرة|حفظه الله|حفظها الله)(?![ء-ي])|\(\s*(?:حي|حية|معاصر)\s*\)")


@dataclass(frozen=True)
class Death:
    """A person's dates as a catalogue gives them. Years are integers; `qualifier` says how sure they are."""

    hijri: int | None = None
    gregorian: int | None = None
    birth_hijri: int | None = None
    birth_gregorian: int | None = None
    qualifier: str = ""  # "" | "after" | "before" | "circa"
    century: int | None = None  # Hijri century (from the year, or given alone: «القرن الثامن»)
    alive: bool = False  # «معاصر», «حفظه الله»
    span: tuple[int, int] = (0, 0)  # where the dates were found in the text
    text: str = field(default="", compare=False)

    @property
    def year(self) -> int | None:
        """The Hijri death year, or None (alias of `hijri`)."""
        return self.hijri

    def label(self) -> str:
        """«ت 728 هـ», «ت بعد 666 هـ», «ق 8 هـ», «معاصر»."""
        if self.alive:
            return "معاصر"
        q = {"after": "بعد ", "before": "قبل ", "circa": "نحو "}.get(self.qualifier, "")
        if self.hijri:
            return f"ت {q}{self.hijri} هـ"
        if self.gregorian:
            return f"ت {q}{self.gregorian} م"
        if self.century:
            return f"ق {self.century} هـ"
        return ""


def _int(s: str | None) -> int | None:
    return int(to_ascii_digits(s)) if s else None


def parse_death(text: str | None, *, assume: str = "hijri") -> Death | None:
    """Find a person's death date in a catalogue string.

    Understands «ت 728 هـ», «(ت. 728هـ)», «المتوفى سنة 728 هـ», «توفي سنة ثمان وعشرين وسبعمائة», «(661 - 728 هـ)»,
    «728 هـ / 1328 م», «ت بعد 666 هـ», «نحو 450 هـ», «القرن الثامن الهجري», «ق 8 هـ», «معاصر».
    A bare number counts only when a death word, an era sign («هـ», «م») or brackets mark it. `assume` decides the
    era of a death year that carries no era sign: ``"hijri"`` (the convention of Arabic catalogues) or ``"gregorian"``.

    >>> parse_death("ابن تيمية (ت 728 هـ)").hijri
    728
    >>> parse_death("الذهبي (673 - 748 هـ)").birth_hijri
    673
    """
    if not text:
        return None
    s = text
    if _ALIVE_RE.search(s):
        m = _ALIVE_RE.search(s)
        assert m
        return Death(alive=True, span=m.span(), text=s)
    cen = parse_century(s)
    for m in _DEATH_RE.finditer(s):
        if cen and cen[1][0] <= m.start("y1") < cen[1][1]:
            continue  # «ق 8 هـ» is a century, not the year 8
        y1, y2 = _int(m["y1"]), _int(m["y2"])
        marked = m["died"] or m["ah1"] or m["ce1"] or m["ah2"] or m["ce2"] or m["q"]
        bracketed = m.start() > 0 and s[: m.start()].rstrip().endswith(("(", "["))
        if not (marked or bracketed):
            continue
        if y1 is None or y1 == 0:
            continue
        q = _QUAL.get(m["q"] or "", "") or _QUAL.get(m["q2"] or "", "")
        sep = m["sep"]
        ce_first = bool(m["ce1"])
        if y2 is not None and sep == "/":
            # «728 هـ / 1328 م» — one year in two calendars (or «1328 م / 728 هـ»)
            if ce_first and not m["ce2"]:
                h, g = y2, y1
            else:
                h, g = y1, y2
            return Death(hijri=h, gregorian=g, qualifier=q, century=century_of(h), span=m.span(), text=s)
        if y2 is not None:
            # «661 - 728 هـ»: birth – death, the era given once at the end (or at each year)
            g_era = bool(m["ce2"] or (m["ce1"] and not m["ah2"]))
            if y2 < y1:  # «728 - 1328 م»? not a life span: treat as hijri / gregorian
                return Death(hijri=y1, gregorian=y2, qualifier=q, century=century_of(y1), span=m.span(), text=s)
            if g_era:
                return Death(gregorian=y2, birth_gregorian=y1, qualifier=q, span=m.span(), text=s)
            return Death(
                hijri=y2, birth_hijri=y1, qualifier=q, century=century_of(y2), span=m.span(), text=s
            )
        if m["ce1"] or (assume == "gregorian" and not m["ah1"]):
            return Death(gregorian=y1, qualifier=q, span=m.span(), text=s)
        return Death(hijri=y1, qualifier=q, century=century_of(y1), span=m.span(), text=s)
    for m in _WORD_YEAR_RE.finditer(s):
        words = m["w"].split()
        # the longest run of number words from the start
        for n in range(len(words), 0, -1):
            v = cardinal_value(" ".join(words[:n]))
            if v:
                end = m.start("w") + len(" ".join(words[:n]))
                q = _QUAL.get((m["q"] or "").strip(), "")
                return Death(hijri=v, qualifier=q, century=century_of(v), span=(m.start(), end), text=s)
    if cen:
        return Death(century=cen[0], span=cen[1], text=s)
    return None


def parse_century(text: str) -> tuple[int, tuple[int, int]] | None:
    """«القرن الثامن الهجري» → (8, span); «ق 8 هـ» → (8, span); «من علماء القرن الحادي عشر» → (11, span)."""
    for m in _CENTURY_RE.finditer(text or ""):
        n = m["n"]
        v = _int(n) if n[0].isdigit() or n[0] in "٠١٢٣٤٥٦٧٨٩" else ordinal_value(n)
        if v is None and " " in n:  # «الثامن و…» picked a following word
            v = ordinal_value(n.split()[0])
        if v and 1 <= v <= 16:
            return v, m.span()
    return None


_BRACKET_DATES = re.compile(r"\s*[\(\[][^()\[\]]*?[0-9٠-٩][^()\[\]]*?[\)\]]")


def strip_dates(text: str) -> str:
    """A name without its dates: «ابن تيمية (ت 728 هـ)» → «ابن تيمية», «الذهبي، ت 748» → «الذهبي»."""
    s = text or ""
    d = parse_death(s)
    while d and (d.hijri or d.gregorian or d.century or d.alive):
        a, b = d.span
        # widen to brackets and separators around the dates
        while a > 0 and s[a - 1] in " ،,-–(:[":
            a -= 1
        while b < len(s) and s[b] in " )].،,":
            b += 1
        s2 = (s[:a] + " " + s[b:]).strip()
        if s2 == s:
            break
        s = s2
        d = parse_death(s)
    s = re.sub(r"\(\s*\)|\[\s*\]", "", s)
    return re.sub(r"\s+", " ", s).strip(" ،,-")


def find_dates(text: str) -> list[Death]:
    """Every dated span in a text (a list of authors, a catalogue line), left to right."""
    out, pos, s = [], 0, text or ""
    while pos < len(s):
        d = parse_death(s[pos:])
        if not d or d.span == (0, 0) and not (d.hijri or d.gregorian or d.century):
            break
        a, b = d.span
        out.append(Death(**{**d.__dict__, "span": (a + pos, b + pos), "text": s}))
        pos += max(b, 1)
    return out
