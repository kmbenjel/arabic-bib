"""Edition statements → fields.

Imprint lines come in every order and with every separator::

    الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م
    تحقيق: شعيب الأرنؤوط - مؤسسة الرسالة، بيروت، ط 2، 1405هـ/1985م
    دار ابن حزم - بيروت - لبنان - ط1 - 2003
    الناشر: دار الفكر - دمشق\nالطبعة: الثانية، 1418 هـ

:func:`parse_edition` reads each piece by what it is (an edition number, a role and its names, a publisher, a
place, a year) rather than by its position.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import search_key, to_ascii_digits
from .numerals import ordinal_value

__all__ = ["CITIES", "Edition", "parse_edition"]

K = search_key

#: Places of publication met on Arabic imprints, city → country (both as printed).
CITIES: dict[str, str] = {
    "بيروت": "لبنان", "صيدا": "لبنان", "طرابلس": "", "جونية": "لبنان", "القاهرة": "مصر", "مصر": "مصر",
    "الإسكندرية": "مصر", "بولاق": "مصر", "طنطا": "مصر", "المنصورة": "مصر", "الجيزة": "مصر", "دمشق": "سوريا",
    "حلب": "سوريا", "حمص": "سوريا", "حماة": "سوريا", "الرياض": "السعودية", "جدة": "السعودية",
    "مكة المكرمة": "السعودية", "مكة": "السعودية", "المدينة المنورة": "السعودية", "الدمام": "السعودية",
    "الطائف": "السعودية", "الكويت": "الكويت", "الدوحة": "قطر", "أبوظبي": "الإمارات", "أبو ظبي": "الإمارات",
    "دبي": "الإمارات", "الشارقة": "الإمارات", "المنامة": "البحرين", "مسقط": "عمان", "صنعاء": "اليمن",
    "عدن": "اليمن", "تريم": "اليمن", "بغداد": "العراق", "الموصل": "العراق", "النجف": "العراق", "البصرة": "العراق",
    "عمان": "الأردن", "عمّان": "الأردن", "القدس": "فلسطين", "غزة": "فلسطين", "تونس": "تونس", "القيروان": "تونس",
    "الجزائر": "الجزائر", "وهران": "الجزائر", "قسنطينة": "الجزائر", "تلمسان": "الجزائر", "الرباط": "المغرب",
    "الدار البيضاء": "المغرب", "فاس": "المغرب", "مراكش": "المغرب", "طنجة": "المغرب", "تطوان": "المغرب",
    "المحمدية": "المغرب", "نواكشوط": "موريتانيا", "الخرطوم": "السودان", "طرابلس الغرب": "ليبيا",
    "بنغازي": "ليبيا", "إستانبول": "تركيا", "إسطنبول": "تركيا", "استانبول": "تركيا", "اسطنبول": "تركيا",
    "حيدر آباد": "الهند", "حيدرآباد": "الهند", "حيدر آباد الدكن": "الهند", "بومباي": "الهند", "دلهي": "الهند",
    "لكنو": "الهند", "كراتشي": "باكستان", "لاهور": "باكستان", "طهران": "إيران", "قم": "إيران",
    "ليدن": "هولندا", "لندن": "بريطانيا", "باريس": "فرنسا", "برلين": "ألمانيا", "فيسبادن": "ألمانيا",
    "ليبزغ": "ألمانيا", "ليبسك": "ألمانيا", "ليبزيغ": "ألمانيا", "مدريد": "إسبانيا", "روما": "إيطاليا",
    "كوالالمبور": "ماليزيا", "جاكرتا": "إندونيسيا",
}
COUNTRIES = frozenset(K(c) for c in set(CITIES.values()) | {"لبنان", "مصر", "سوريا", "سورية", "السعودية",
                                                           "المملكة العربية السعودية", "الأردن", "المغرب",
                                                           "المملكة المغربية", "تونس", "الجزائر", "اليمن",
                                                           "العراق", "الكويت", "قطر", "ليبيا", "السودان"} if c)
_CITY_KEYS = {K(c): c for c in CITIES}

_ROLE = (
    r"(?:دراسة وتحقيق|تحقيق وتعليق|تحقيق وشرح|تحقيق ودراسة|تحقيق وتخريج|حققه وعلق عليه|حققه وخرج أحاديثه|"
    r"حققه وضبطه|حققه|تحقيق|تح|ت\.?|المحقق|محقق|ضبطه وصححه|ضبطه|ضبط|اعتنى به|اعتنى بها|عني به|عنى به|"
    r"عني بنشره|صححه|تصحيح|شرح|شرحه|ترجمة|ترجمه|نقله إلى العربية|تعريب|عربه|تقديم|قدم له|قدم لها|مقدمة|"
    r"إشراف|بإشراف|جمع وترتيب|جمع وإعداد|جمعه|جمع|إعداد|أعده|رتبه|ترتيب|تخريج|خرج أحاديثه|مراجعة|راجعه|"
    r"علق عليه|تعليق|قرأه وشرحه|قرأه وعلق عليه|تنسيق)"
)
_ROLE_RE = re.compile(rf"^(?P<role>{_ROLE}(?:\s+و{_ROLE})*)\s*[:：]?\s*(?P<names>.+)$")
_TAHQIQ = re.compile(r"حقق|تحقيق|^تح$|^ت\.?$|محقق|ضبط|اعتنى|عني|صحح|تصحيح")
_PUBLISHER = re.compile(
    r"^(?:الناشر\s*[:：]?\s*)?(?:دار|مكتبة|المكتبة|مكتبه|مؤسسة|مطبعة|المطبعة|مطابع|المكتب|وزارة|مجمع|المجمع|"
    r"جامعة|مركز|الهيئة|المجلس|عالم|إدارة|الأمانة|بيت|شركة|منشورات|معهد|الجمعية|جمعية|الدار|نشر|طبع|"
    r"المطبعة|دائرة|مجلس|مكتب|مؤسسه|المؤسسة)\b"
)
_EDNO = re.compile(
    r"(?:^|\s)(?:الطبعة|طبعة|ط)\s*\.?\s*[:：]?\s*(?P<n>[0-9٠-٩]+|[ء-ي]+(?:\s+(?:عشرة|عشر|و[ء-ي]+))?)"
)
_YEAR = re.compile(
    r"(?<![0-9٠-٩])(?P<y>[0-9٠-٩]{3,4})\s*(?P<era>هـ|ه|هجرية|م|ميلادية)?(?![0-9٠-٩])(?![ء-ي])"
)
_KIND = re.compile(r"طبعة حجرية|طبعة مصورة|مصورة عن[^،\-]*|نسخة مصورة|طبعة جديدة|طبعة منقحة|طبعة مزيدة ومنقحة")
_SPLIT = re.compile(r"\s*[،,؛;\n]\s*|\s+[-–—]\s+|\s*\|\s*")
_LABEL = re.compile(r"^(?P<label>الناشر|الطبعة|المحقق|تحقيق|المؤلف|سنة النشر|سنة الطبع|مكان النشر|بلد النشر|عدد الأجزاء|"
                    r"عدد الصفحات)\s*[:：]\s*(?P<v>.*)$")


@dataclass(frozen=True)
class Edition:
    """The fields of an imprint, as printed (only whitespace is tidied)."""

    raw: str
    number: int | None = None  # 1 for «الطبعة الأولى»
    number_text: str = ""  # «الأولى»
    publisher: str = ""
    city: str = ""
    places: tuple[str, ...] = ()  # every city and country, in order
    country: str = ""
    hijri: int | None = None
    gregorian: int | None = None
    editors: tuple[str, ...] = ()
    role: str = ""  # the editor's role as printed: «تحقيق», «حققه وعلق عليه», «ت»
    contributors: tuple[str, ...] = ()  # the other roles, as printed: «قدم له فلان»
    kind: str = ""  # «طبعة حجرية», «مصورة عن طبعة بولاق» …
    rest: tuple[str, ...] = field(default=(), compare=False)  # pieces read as none of the above

    def as_dict(self) -> dict[str, object]:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items() if k not in ("raw",)}


def _names(s: str) -> list[str]:
    """«محمد أحمد ومحمود شاكر» → two names; «عبد الله بن عبد المحسن التركي» stays one."""
    parts = [x.strip() for x in re.split(r"\s*[،؛]\s*|\s+و(?=(?:محمد|أحمد|عبد|علي|صالح|عمر|عثمان|إبراهيم|يوسف|حسن|"
                                         r"حسين|مصطفى|خالد|سعيد|محمود|د\.|الدكتور|الشيخ)\b)", s) if x.strip()]
    return parts


def _year(m: re.Match[str]) -> tuple[str, int]:
    y = int(to_ascii_digits(m["y"]))
    era = m["era"] or ""
    if era.startswith("ه"):
        return "h", y
    if era.startswith("م"):
        return "g", y
    if y >= 1500:
        return "g", y
    if 1100 <= y <= 1499:
        return "h", y
    return "", y


def parse_edition(text: str | None) -> Edition:
    """Read an imprint line (or a catalogue card of «الناشر: …» lines) into fields.

    >>> e = parse_edition("الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م")
    >>> e.number, e.publisher, e.city, e.country, e.hijri, e.gregorian
    (1, 'دار الكتب العلمية', 'بيروت', 'لبنان', 1420, 1999)
    """
    raw = text or ""
    s = re.sub(r"[ \t]+", " ", raw).strip()
    number, number_text, kind = None, "", ""
    hijri = greg = None
    editors: list[str] = []
    role = ""
    contributors: list[str] = []
    publisher = ""
    places: list[str] = []
    rest: list[str] = []

    m = _KIND.search(s)
    if m:
        kind = m.group(0).strip()
        s = (s[: m.start()] + " " + s[m.end() :]).strip()
    # years: «1405هـ/1985م», «1420 هـ - 1999 م»
    for ym in list(_YEAR.finditer(s)):
        era, y = _year(ym)
        before = s[max(0, ym.start() - 8) : ym.start()]
        if re.search(r"(?:ط|الطبعة|طبعة)\s*\.?\s*[:：]?\s*$", before):
            continue  # «ط 2» is not a year
        if era == "h" and hijri is None:
            hijri = y
        elif era == "g" and greg is None:
            greg = y
        else:
            continue
    s = _YEAR.sub(lambda ym: " " if _year(ym)[0] else ym.group(0), s)
    s = re.sub(r"\s*/\s*(?=\s|$)|(?<=\s)/\s*", " ", s)
    m = _EDNO.search(s)
    if m:
        v = ordinal_value(m["n"])
        if v is None and " " in m["n"]:
            v = ordinal_value(m["n"].split()[0])
        if v is not None:
            number, number_text = v, m["n"].strip()
            if ordinal_value(m["n"]) is None:
                number_text = m["n"].split()[0]
            cut = m.start("n") + len(number_text)
            s = (s[: m.start()] + " " + s[cut:]).strip()

    pieces = [p.strip(" .:-–") for p in _SPLIT.split(s)]
    for p in pieces:
        if not p:
            continue
        lm = _LABEL.match(p)
        if lm:
            lab, p = lm["label"], lm["v"].strip()
            if not p:
                continue
            if lab in ("المحقق", "تحقيق"):
                role = role or ("تحقيق" if lab == "تحقيق" else "تحقيق")
                editors += _names(p)
                continue
            if lab == "الناشر":
                publisher = publisher or p
                continue
            if lab in ("مكان النشر", "بلد النشر"):
                places.append(p)
                continue
            if lab in ("عدد الأجزاء", "عدد الصفحات", "المؤلف", "الطبعة", "سنة النشر", "سنة الطبع"):
                continue
        rm = _ROLE_RE.match(p)
        if rm and not _PUBLISHER.match(p):
            r, names = rm["role"].strip(), rm["names"].strip()
            if _TAHQIQ.search(r) and not editors:
                role, editors = r, _names(names)
            else:
                contributors.append(f"{r} {names}")
            continue
        k = K(p)
        if k in _CITY_KEYS or k in COUNTRIES:
            places.append(p)
            continue
        if _PUBLISHER.match(p) or (not publisher and re.match(r"^(?:ال)?[ء-ي]+\s+(?:للنشر|للطباعة)", p)):
            # «دار الكتب العلمية بيروت»: a place at the end of the publisher's piece
            w = p.split()
            tail: list[str] = []
            while len(w) > 2:
                two = K(" ".join(w[-2:]))
                if two in _CITY_KEYS:
                    tail[:0] = w[-2:]
                    w = w[:-2]
                elif K(w[-1]) in _CITY_KEYS or K(w[-1]) in COUNTRIES or K(w[-1]).removeprefix("ب") in _CITY_KEYS:
                    tail.insert(0, w[-1])
                    w = w[:-1]
                else:
                    break
            pub = re.sub(r"^الناشر\s*[:：]?\s*", "", " ".join(w))
            if publisher:
                publisher = f"{publisher} و{pub}" if pub not in publisher else publisher
            else:
                publisher = pub
            if tail:
                places.append(" ".join(tail))
            continue
        if re.fullmatch(r"[\s0-9٠-٩]*", p):
            continue
        rest.append(p)
    city = next((x for x in places if K(x) in _CITY_KEYS or K(x).removeprefix("ب") in _CITY_KEYS), "")
    if city and K(city) not in _CITY_KEYS:
        city = city[1:]  # «ببولاق» as printed in `places`; the city is «بولاق»
    country = next((x for x in places if K(x) in COUNTRIES), "")
    if city and not country:
        country = CITIES.get(_CITY_KEYS.get(K(city), ""), "")
    return Edition(
        raw=raw, number=number, number_text=number_text, publisher=publisher, city=city, places=tuple(places),
        country=country, hijri=hijri, gregorian=greg, editors=tuple(editors), role=role,
        contributors=tuple(contributors), kind=kind, rest=tuple(rest),
    )
