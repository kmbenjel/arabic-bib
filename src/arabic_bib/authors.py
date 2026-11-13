"""Classical Arabic personal names: their parts, their shorter forms, and whether two forms name one person.

A classical name is a sequence of parts, each with its own role:

========  ==================================  ===========================================
part      what it is                          example (Ibn Taymiyya)
========  ==================================  ===========================================
kunya     «أبو / أم …», a teknonym            أبو العباس
laqab     an honorific epithet                تقي الدين
ism       the given name                      أحمد
nasab     the chain «بن …» of forefathers     بن عبد الحليم بن عبد السلام بن تيمية
nisba     origin, tribe, school («ـي»)        الحراني، الدمشقي، الحنبلي
shuhra    the name by which he is known       ابن تيمية
========  ==================================  ===========================================

Catalogues give any subset of these, in any order, so «ابن تيمية» and «أحمد بن عبد الحليم بن تيمية الحراني» must
meet, while «ابن حجر العسقلاني» and «ابن حجر الهيتمي» must not. :func:`match_authors` gives a verdict
(``same`` / ``different`` / ``unknown``) with its reasons; a match that rests only on common parts (محمد، شمس الدين،
الدمشقي) is ``unknown``, never ``same``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .dates import Death, parse_death, strip_dates
from .normalize import key_norm, search_key

__all__ = [
    "AuthorMatch",
    "AuthorName",
    "COMMON_TOKENS",
    "author_key",
    "author_similarity",
    "author_tokens",
    "match_authors",
    "parse_author",
    "same_author",
    "same_person",
    "publisher_family",
    "same_publisher",
]

K = search_key


def _set(words: str) -> frozenset[str]:
    return frozenset(K(w) for w in words.split())


def _phrases(text: str) -> frozenset[str]:
    return frozenset(K(p) for p in text.split("|") if p.strip())


HONORIFICS = _phrases(
    "الإمام|الامام|الحافظ|الشيخ|العلامة|العلامه|القاضي|الأستاذ|الاستاذ|الدكتور|د.|د|أ.د.|أ. د.|أ.د|الأستاذ الدكتور|"
    "المحدث|الفقيه|المقرئ|المؤرخ|الأديب|الحاج|سيدي|المحقق|العارف بالله|سماحة|فضيلة|معالي|الشيخ العلامة|المفسر|"
    "الإمام الحافظ|المسند|الرحالة|الفيلسوف|الطبيب|الشاعر|اللغوي|النحوي|الوزير|الأمير|السلطان|الخليفة|القطب|الولي|"
    "مولانا|حضرة|الشريف|الأصولي"
)
# honorific titles that do identify a person in practice; they support a match but never contradict one
TITLES = _phrases(
    "شيخ الإسلام|شيخ الاسلام|حجة الإسلام|حجة الاسلام|إمام الحرمين|امام الحرمين|الشيخ الرئيس|سلطان العلماء|"
    "شمس الأئمة|فخر الإسلام|ذو النون|الإمام الأعظم|الإمام الأكبر|شيخ الأزهر|حكيم الأندلس|المعلم الثاني|"
    "قاضي القضاة|أمير المؤمنين|جار الله"
)
TRAILING = re.compile(
    r"\s*(?:رحمه الله(?: تعالى)?|رحمها الله|رحمهم الله|رضي الله عنهما?|رضي الله عنها|حفظه الله|"
    r"عليه السلام|قدس سره|غفر الله له|نفع الله به)\s*$"
)
KUNYA_HEADS = _set("أبو أبي أبا أم ابو ابي ابا")
LINKS = _set("بن ابن بنت ولد")
IBN, BINT = K("ابن"), K("بنت")
LAQAB_TAILS = _set("الدين الدولة الإسلام الملك السنة الأئمة الشريعة القضاة")
# titles written after a modern name («إسماعيل باشا», «محمد بك»): honorifics wherever they stand
POST_TITLES = _set("باشا بك بيك أفندي افندي آغا اغا خان")
# given names that begin with the article (an «ال» word is otherwise a nisba or an epithet)
AL_ISMS = _set(
    "الحسن الحسين القاسم العباس الفضل الربيع الليث المغيرة النعمان الوليد المنذر الحارث المهدي المعتمد المأمون "
    "المنصور الهادي الرشيد المعتصم المتوكل الأحنف الأعمش الأسود الخليل المفضل المبارك المختار الزبير الصادق "
    "الطاهر الأمين البشير المكي الطيب العربي الهادي"
)
# a «ال» word ending in «ـي» that is an epithet or a given name, not a nisba
NOT_NISBA = _set("المهدي الهادي المكي العربي الولي")

# Parts too common to identify anybody alone (normalised). Extend per catalogue with ``match_authors(common=…)``.
COMMON_GIVEN = _set(
    "محمد أحمد علي عمر عثمان إبراهيم إسماعيل يوسف يحيى الحسن الحسين حسن حسين محمود مصطفى خالد سعيد سعد صالح موسى "
    "عيسى سليمان داود جعفر حمزة زيد عمرو منصور قاسم القاسم طاهر نصر سالم خليل إدريس عبد الله عبد الرحمن عبد العزيز "
    "عبد الملك عبد الوهاب عبد القادر عبد الرحيم عبد الكريم عبد السلام عبد اللطيف عبد الواحد عبد الحميد عبد الغني "
    "عبد المجيد عبد الرزاق عبد الحق محمد علي الرحمن الله العزيز الكريم أبو بكر بكر عبيد الله"
) | frozenset({K("عبد الله"), K("عبد الرحمن"), K("عبد العزيز"), K("عبد الملك"), K("عبد الوهاب"),
               K("عبد القادر"), K("عبد الرحيم"), K("عبد الكريم"), K("عبد السلام"), K("عبد اللطيف"),
               K("عبد الواحد"), K("عبد الحميد"), K("عبد الغني"), K("عبد المجيد"), K("عبد الرزاق"),
               K("عبد الحق"), K("ابو بكر"), K("عبيد الله")})
COMMON_KUNYA = frozenset(
    K(x)
    for x in (
        "أبو عبد الله", "أبو محمد", "أبو بكر", "أبو الحسن", "أبو العباس", "أبو الفضل", "أبو القاسم", "أبو علي",
        "أبو حفص", "أبو عمر", "أبو عمرو", "أبو الحسين", "أبو إسحاق", "أبو إبراهيم", "أبو أحمد", "أبو عبد الرحمن",
        "أبو سعيد", "أبو الفتح", "أبو الفرج", "أبو جعفر", "أبو زكريا", "أبو يوسف", "أبو منصور", "أبو طاهر",
        "أبو حامد", "أبو العلاء", "أبو الوليد", "أبو المعالي", "أبو البركات", "أبو الخير", "أبو عثمان", "أبو زيد",
        "أبو سليمان", "أبو موسى", "أبو داود", "أبو نصر", "أبو سعد", "أبو الطيب", "أبو مسلم", "أبو عمران",
    )
)
COMMON_NISBA = _set(
    "الحنبلي الشافعي المالكي الحنفي الظاهري الأشعري الماتريدي الصوفي السلفي الأثري الدمشقي المصري البغدادي "
    "القاهري المكي المدني الأندلسي المغربي الشامي الحلبي الكوفي البصري اليمني الفاسي التونسي العراقي النجدي "
    "الحجازي الخراساني الرازي القرشي الأنصاري الهاشمي التميمي الأزدي الخزرجي الأوسي الحسني الحسيني العلوي الكناني "
    "الأموي العباسي الثقفي الكندي الأسدي الشيباني المخزومي الأزهري الشنقيطي الإفريقي العثماني التركي الهندي "
    "الفارسي البكري الصديقي العمري"
)
COMMON_TOKENS: frozenset[str] = COMMON_GIVEN | COMMON_NISBA
_EPITHET_COMMON = _set("الكبير الصغير الأكبر الأصغر الأوسط الثاني الأول الخطيب")
_GENERATION = _set("الجد الحفيد الابن الأب")  # «ابن رشد الجد»: an epithet, never part of «ابن X»

# token stop list of :func:`author_tokens`
_STOP_TOKENS = _set("بن ابن ابي ابو ابا عبد الله محمد احمد علي الامام الحافظ الشيخ العلامه القاضي الدين شيخ الاسلام ت ط")


@dataclass(frozen=True)
class Unit:
    kind: str  # honor | title | kunya | ism | nasab | laqab | epithet | nisba | ibn | family
    text: str

    @property
    def key(self) -> str:
        return K(self.text)


@dataclass(frozen=True)
class AuthorName:
    """The parts of an author's name, each as written (use :func:`search_key` to compare them)."""

    raw: str
    ism: str = ""
    kunya: str = ""
    nasab: tuple[str, ...] = ()
    laqab: tuple[str, ...] = ()  # «تقي الدين», «الجاحظ», titles such as «شيخ الإسلام»
    nisba: tuple[str, ...] = ()
    shuhra: str = ""
    honorifics: tuple[str, ...] = ()
    death: int | None = None  # Hijri death year
    dates: Death | None = field(default=None, compare=False)
    units: tuple[Unit, ...] = field(default=(), compare=False, repr=False)

    @property
    def name(self) -> str:
        """The name without honorifics or dates."""
        return " ".join(u.text for u in self.units if u.kind != "honor")

    def as_dict(self) -> dict[str, object]:
        return {
            "ism": self.ism, "kunya": self.kunya, "nasab": list(self.nasab), "laqab": list(self.laqab),
            "nisba": list(self.nisba), "shuhra": self.shuhra, "honorifics": list(self.honorifics),
            "death": self.death,
        }

    def forms(self) -> list[str]:
        """The name and its shorter forms, longest first: full; without honorifics; a long nasab kept to its first
        and last links; the first and last of three nisbas; kunya + nisbas; laqab + nisba; the shuhra."""
        us = [u for u in self.units if u.kind != "honor"]
        txt = lambda xs: " ".join(u.text for u in xs)  # noqa: E731
        out = [txt(self.units), txt(us)]
        names = [u for u in us if u.kind in ("ism", "nasab")]
        rest = [u for u in us if u.kind not in ("ism", "nasab")]
        nis = [u for u in us if u.kind == "nisba"]
        if len(names) > 3:  # «علي بن حسن بن علي بن عبد الحميد» → «علي بن حسن بن عبد الحميد»
            keep = {id(names[0]), id(names[1]), id(names[-1])}
            short: list[Unit] = []
            for k, u in enumerate(us):
                if u.kind == "link" and k + 1 < len(us) and us[k + 1].kind == "nasab" and id(us[k + 1]) not in keep:
                    continue
                if u.kind in ("ism", "nasab") and id(u) not in keep:
                    continue
                short.append(u)
            out.append(txt(short))
        if len(nis) >= 3:
            out.append(txt([u for u in us if u.kind != "nisba" or u is nis[0] or u is nis[-1]]))
        if self.kunya and nis:
            out.append(f"{self.kunya} {' '.join(u.text for u in nis)}")
            out.append(f"{self.kunya} {nis[0].text}")
        lq = [u for u in rest if u.kind == "laqab" and K(u.text).split()[-1] == K("الدين")]
        if lq and nis:
            out.append(f"{lq[0].text} {nis[-1].text}")
        if self.ism and self.nasab and any(u.kind == "link" for u in self.units):
            tail = " ".join(u.text for u in nis) or self.shuhra
            out.append(f"{self.ism} {'بنت' if self._female else 'بن'} {self.nasab[0]} {tail}")
        if self.shuhra:
            out.append(self.shuhra)
        seen: list[str] = []
        for f in out:
            f = re.sub(r"\s+", " ", f).strip()
            if f and f not in seen:
                seen.append(f)
        return sorted(seen, key=lambda t: -len(t.split()))

    @property
    def _female(self) -> bool:
        return any(K(u.text) == BINT for u in self.units if u.kind == "link")


# ----------------------------------------------------------------------------------------------------- parsing
_SHUHRA_RE = re.compile(r"\s*[،,]?\s*(?:المعروف|المشهور|الشهير|المعروفة|المشهورة|الشهيرة)\s+بـ?\s*(?=\S)")
_ALT_SEP = re.compile(r"\s*[؛;]\s*")
_PAREN = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")


def raw_aal(w: str) -> bool:
    return w in ("آل", "ال")


# classical nicknames and epithets that begin with the article (not a nisba, not a family name)
EPITHETS = _set(
    "الجاحظ الفراء الأخفش المبرد الخليل الأعمش الجد الحفيد الصغير الكبير الأكبر الأصغر الخطيب الأعشى الفرزدق "
    "الأخطل الحطيئة النابغة الشنفرى المتنبي الأعرج الأحول الأعمى الضرير الأصم الطويل القصير الأحمر الأسود "
    "الحافظ الإمام الشيخ القاضي المفسر الوزير الأمير السلطان الخليفة المهدي المنصور الرشيد المأمون"
)


def _is_nisba(k: str) -> bool:
    return k.startswith("ال") and k.endswith("ي") and len(k) > 4 and k not in NOT_NISBA


def _take_element(words: list[str], i: int) -> int:
    """How many words form the name element starting at words[i] (after a link): «عبد X», «أبي X», «X الدين»."""
    n = len(words)
    k = K(words[i])
    if k in KUNYA_HEADS and i + 1 < n:
        return 3 if K(words[i + 1]) == K("عبد") and i + 2 < n else 2
    if k == K("عبد") and i + 1 < n:
        return 2
    if i + 1 < n and K(words[i + 1]) in LAQAB_TAILS:
        return 2
    return 1


def _split_units(words: list[str]) -> list[Unit]:
    out: list[Unit] = []
    i, n = 0, len(words)
    while i < n:
        k = K(words[i])
        two = K(" ".join(words[i : i + 2])) if i + 1 < n else ""
        three = K(" ".join(words[i : i + 3])) if i + 2 < n else ""
        lead = not any(u.kind in ("name", "nasab", "kunya", "nisba", "ibn") for u in out)  # titles come first
        if k in POST_TITLES and out:
            out.append(Unit("honor", words[i]))
            i += 1
            continue
        if raw_aal(words[i]) and i + 1 < n:
            out.append(Unit("family", " ".join(words[i : i + 2])))  # «آل الشيخ»
            i += 2
            continue
        if lead and three in HONORIFICS:
            out.append(Unit("honor", " ".join(words[i : i + 3])))
            i += 3
            continue
        if two in TITLES:
            out.append(Unit("title", " ".join(words[i : i + 2])))
            i += 2
            continue
        if lead and two in HONORIFICS:
            out.append(Unit("honor", " ".join(words[i : i + 2])))
            i += 2
            continue
        if lead and k in HONORIFICS and (i + 1 < n):
            out.append(Unit("honor", words[i]))
            i += 1
            continue
        if k in LINKS and i + 1 < n:
            prev = out[-1].kind if out else ""
            j = _take_element(words, i + 1)
            el = words[i + 1 : i + 1 + j]
            starts = not [u for u in out if u.kind not in ("honor", "title", "laqab")]
            after_bin = any(u.kind == "link" and K(u.text) == K("بن") for u in out)
            bare = sum(1 for u in out if u.kind == "name") >= 2 and not any(u.kind == "link" for u in out)
            if k == IBN and (starts or after_bin or bare or prev in ("nisba", "epithet", "laqab", "title", "ibn", "family")):
                # «ابن X» at the start or after the nisbas: the name he is known by (a family or a forefather)
                if j == 1 and i + 2 + j - 1 < n:
                    nxt = K(words[i + 1 + j])
                    if nxt.startswith("ال") and not _is_nisba(nxt) and not K(el[0]).startswith("ال") \
                            and nxt not in _EPITHET_COMMON and nxt not in _GENERATION:
                        el = words[i + 1 : i + 3]  # «ابن قيم الجوزية», «ابن سيد الناس»
                out.append(Unit("ibn", f"{words[i]} {' '.join(el)}"))
            else:
                out.append(Unit("link", words[i]))
                out.append(Unit("nasab", " ".join(el)))
            i += 1 + len(el)
            continue
        if k in KUNYA_HEADS and i + 1 < n:
            j = _take_element(words, i)
            out.append(Unit("kunya", " ".join(words[i : i + j])))
            i += j
            continue
        if k == K("عبد") and i + 1 < n:
            out.append(Unit("name", " ".join(words[i : i + 2])))
            i += 2
            continue
        if i + 1 < n and K(words[i + 1]) in LAQAB_TAILS:
            out.append(Unit("laqab", " ".join(words[i : i + 2])))
            i += 2
            continue
        if k.startswith("ال") and len(k) > 2:
            nxt = K(words[i + 1]) if i + 1 < n else ""
            names_before = any(u.kind in ("name", "nasab") for u in out)
            if (nxt in LINKS and nxt != IBN) or (not names_before and k in AL_ISMS and nxt not in LINKS):
                out.append(Unit("name", words[i]))
            elif _is_nisba(k) or (names_before and k not in EPITHETS and k not in AL_ISMS and out and out[-1].kind in
                                  ("name", "nasab", "nisba", "laqab")):
                out.append(Unit("nisba", words[i]))  # «الحراني»; a family name «العثيمين» after the names
            elif names_before and k in AL_ISMS and out and out[-1].kind in ("name", "nasab"):
                out.append(Unit("name", words[i]))  # «محمد الطاهر ابن عاشور»
            else:
                out.append(Unit("epithet", words[i]))
            i += 1
            continue
        out.append(Unit("name", words[i]))
        i += 1
    # names: the first is the ism, the next ones (with or without «بن») the nasab
    res: list[Unit] = []
    have_ism = False
    for u in out:
        if u.kind == "name":
            if not have_ism:
                res.append(Unit("ism", u.text))
                have_ism = True
            else:
                res.append(Unit("nasab", u.text))
        elif u.kind == "nasab" and not have_ism:
            # «بن X» with no name before it: the kunya was the name («أبو بكر بن العربي»)
            res.append(u)
        else:
            res.append(u)
    return res


_FUSED = (
    (re.compile(r"(?<![\w])(أبو|أبي|أبا|ابو|ابي|ابا)(?=ال\w{2,}|[^\s\d]{3,})"), r"\1 "),  # «أبوالحسن», «أبيالكرم»
    (re.compile(r"(?<![\w])(عبد|عبيد)(?=ال\w{2,})"), r"\1 "),  # «عبدالكريم» (never «عبده»)
    (re.compile(r"(?<![\w])(\w{2,})(?=(?:الدين|الدولة|الإسلام|الاسلام)(?![\w]))"), r"\1 "),  # «عزالدين»
)


def _unfuse(s: str) -> str:
    """Particles written without their space in some catalogues: «أبوالحسن», «عبدالكريم», «عزالدين»."""
    for rx, rp in _FUSED:
        s = rx.sub(rp, s)
    return s


def _clean(raw: str) -> tuple[str, str, Death | None]:
    """→ (the name without dates and brackets, an explicit shuhra, the dates)."""
    s = _unfuse(raw or "")
    d = parse_death(s)
    s = strip_dates(s)
    s = TRAILING.sub("", s)
    shuhra = ""
    m = _SHUHRA_RE.search(s)
    if m:
        shuhra = s[m.end() :].strip(" ،,.ـ")
        shuhra = re.sub(r"^(?:ال)?(?:شيخ|إمام|امام|حافظ|قاضي|علامة)\s+", "", shuhra)  # «بالشيخ الخضري»
        s = s[: m.start()].strip(" ،,")

    def paren(mt: re.Match[str]) -> str:
        x = (mt.group(1) or mt.group(2) or "").strip()
        return f" {x} " if len(x.split()) <= 2 else " "  # «ابن رشد (الجد)» → inline

    s = _PAREN.sub(paren, s)
    s = re.sub(r"[\"“”„«»]+", " ", s).strip()
    parts = [p.strip() for p in _ALT_SEP.split(s) if p.strip()]
    if len(parts) >= 2:
        # Shamela's «short؛ full» form: the short one is the shuhra, the full one is parsed
        short, full = parts[0], parts[1]
        if len(short.split()) > len(full.split()):
            short, full = full, short
        shuhra = shuhra or short
        s = full
    elif "،" in s or "," in s:
        # a library catalogue's inverted form «الذهبي، محمد بن أحمد», «ابن خلدون، عبد الرحمن بن محمد»,
        # «"إبن المقفع، عبد الله"», «كاترمير، ا. م.»: the head is the name he is known by; the name is written back
        # in its natural order, the head after the given names
        head, tail = (x.strip() for x in re.split(r"\s*[،,]\s*", s, maxsplit=1))
        hk = K(head).split()
        laqab_head = len(hk) == 2 and hk[1] in LAQAB_TAILS
        if (1 <= len(head.split()) <= 3 and tail and len(tail.split()) <= 5 and not re.search(r"[0-9٠-٩]", tail)
                and not laqab_head):
            shuhra = shuhra or head
            s = f"{tail} {head}"
        else:
            s = re.sub(r"\s*[،,]\s*", " ", s)
    s = re.sub(r"[\"«»:.\-–]+", " ", s)
    return re.sub(r"\s+", " ", s).strip(), shuhra, d


def parse_author(name: str | None) -> AuthorName:
    """Split an author's name into its parts.

    >>> a = parse_author("شيخ الإسلام تقي الدين أبو العباس أحمد بن عبد الحليم بن تيمية الحراني (ت 728 هـ)")
    >>> a.ism, a.kunya, a.nasab, a.nisba, a.death
    ('أحمد', 'أبو العباس', ('عبد الحليم', 'تيمية'), ('الحراني',), 728)
    """
    raw = name or ""
    s, shuhra, d = _clean(raw)
    words = s.split()
    units = _split_units(words)
    ism = next((u.text for u in units if u.kind == "ism"), "")
    kunya = next((u.text for u in units if u.kind == "kunya"), "")
    nasab = tuple(u.text for u in units if u.kind == "nasab")
    laqab = tuple(u.text for u in units if u.kind in ("laqab", "epithet", "title"))
    nisba = tuple(u.text for u in units if u.kind in ("nisba", "family"))
    honor = tuple(u.text for u in units if u.kind == "honor")
    if not shuhra:
        ibns = [u.text for u in units if u.kind == "ibn"]
        named = [u for u in units if u.kind not in ("honor", "link")]
        if ibns:
            shuhra = ibns[-1]
        elif len(named) == 1 and named[0].kind in ("nisba", "epithet", "kunya", "laqab", "title", "family"):
            shuhra = named[0].text
    return AuthorName(
        raw=raw, ism=ism, kunya=kunya, nasab=nasab, laqab=laqab, nisba=nisba, shuhra=shuhra,
        honorifics=honor, death=d.hijri if d else None, dates=d, units=tuple(units),
    )


# ---------------------------------------------------------------------------------------------------- keys
_TITLE_PREFIX = re.compile(
    r"^(?:(?:الإمام|الامام|الحافظ|الشيخ|العلامة|العلامه|شيخ الإسلام|شيخ الاسلام|القاضي|الأستاذ|الدكتور|د)\.?\s+)+"
)


def author_key(name: str | None) -> str:
    """A catalogue author's key (keys v1, frozen): the part before the first «؛» or «;», leading titles dropped
    (الإمام، الحافظ، الشيخ، العلامة، شيخ الإسلام، القاضي، الأستاذ، الدكتور، د.), :func:`~arabic_bib.normalize.key_norm`.
    Dates are not removed (they are part of the catalogue's string); use :func:`strip_dates` first if you need that.

    >>> author_key("الإمام الشاشي؛ إسحاق بن إبراهيم")
    'الشاشي'
    """
    a = re.split(r"[؛;]", name or "")[0].strip()
    return key_norm(_TITLE_PREFIX.sub("", a))


def author_tokens(name: str | None) -> frozenset[str]:
    """The distinctive words of a name (no «بن», «أبو», «عبد», «محمد», titles …), normalised."""
    return frozenset(w for w in K(strip_dates(name or "")).split() if w not in _STOP_TOKENS and len(w) > 2)


# -------------------------------------------------------------------------------------------------- matching
@dataclass(frozen=True)
class AuthorMatch:
    """The verdict on two name forms: ``same``, ``different`` or ``unknown`` (not enough to tell)."""

    verdict: str
    score: float
    reasons: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.verdict == "same"


def _strip_al(k: str) -> str:
    return k[2:] if k.startswith("ال") and len(k) > 4 else k


def _fold_kunya(k: str) -> str:
    w = k.split()
    if w and w[0] in ("ابي", "ابا"):
        w[0] = "ابو"
    return " ".join(w)


@dataclass
class _Feat:
    a: AuthorName
    ism: str
    nasab: list[str]
    kunya: str
    laqab: set[str]  # «X الدين»
    titles: set[str]
    epithets: set[str]
    nisba: set[str]
    ibn: set[str]  # X of every «ابن X» he can be called by: his forefathers and his own «ابن X»
    shuhra: str
    size: int


def _features(a: AuthorName) -> _Feat:
    ibn = {K(u.text)[len("ابن ") :] for u in a.units if u.kind == "ibn"}
    ibn |= {K(x) for x in a.nasab}
    if a.shuhra and K(a.shuhra).startswith("ابن "):
        ibn.add(K(a.shuhra)[4:])
    lq = {K(u.text) for u in a.units if u.kind == "laqab"}
    ti = {K(u.text) for u in a.units if u.kind == "title"}
    ep = {K(u.text) for u in a.units if u.kind == "epithet"}
    ni = {K(x) for x in a.nisba}
    sh = K(a.shuhra)
    if sh and not sh.startswith("ابن ") and sh.startswith("ال"):
        (ni if _is_nisba(sh) else ep).add(sh)
    size = len([u for u in a.units if u.kind not in ("honor", "link")]) or (1 if sh else 0)
    return _Feat(a, K(a.ism), [K(x) for x in a.nasab], _fold_kunya(K(a.kunya)), lq, ti, ep, ni, ibn, sh, size)


def _ibn_supported(x: str, L: _Feat) -> bool:
    """`x` is the X of a «ابن X» (as written, normalised); L.ibn holds the long form's forefathers likewise."""
    sx = _strip_al(x)
    for y in L.ibn:
        if x == y:
            return True
        sy = _strip_al(y)
        # «ابن القيم» ~ «ابن قيم الجوزية»: one is the head of the other; never «ابن العربي» ~ «ابن عربي»
        if sy.startswith(sx + " ") or sx.startswith(sy + " "):
            return True
    # «ابن عثيمين» ~ «العثيمين», «ابن الجوزي» ~ «الجوزي»
    return any(_strip_al(n) == x for n in L.nisba | L.epithets)


def match_authors(a: str | AuthorName, b: str | AuthorName, *, common: Iterable[str] | None = None) -> AuthorMatch:
    """Do two name forms name the same person?

    ``same``: every part of the shorter form is found in the longer, and at least one of them is distinctive (a
    shuhra «ابن X», a rare nisba or laqab, a kunya that is not «أبو عبد الله», or the ism with its father and
    grandfather). ``different``: two death years more than two years apart, or the forms disagree on the ism, the
    father, the kunya, a «X الدين» laqab or two distinctive nisbas. ``unknown``: anything else, notably a match that
    rests only on common parts (محمد, شمس الدين, الدمشقي).

    `common` adds normalised tokens to the built-in list of common parts (e.g. the frequent names of a catalogue).

    >>> match_authors("ابن تيمية", "أحمد بن عبد الحليم بن تيمية الحراني").verdict
    'same'
    >>> match_authors("ابن حجر العسقلاني", "ابن حجر الهيتمي").verdict
    'different'
    """
    A = a if isinstance(a, AuthorName) else parse_author(a)
    B = b if isinstance(b, AuthorName) else parse_author(b)
    extra = frozenset(K(x) for x in common) if common else frozenset()
    cg = COMMON_GIVEN | extra
    cn = COMMON_NISBA | extra
    reasons: list[str] = []
    if A.death and B.death and abs(A.death - B.death) > 2:
        return AuthorMatch("different", 0.0, (f"death-conflict:{A.death}!={B.death}",))
    ca = A.dates.century if A.dates else None
    cb = B.dates.century if B.dates else None
    if ca and cb and ca != cb and not (A.death and B.death):
        return AuthorMatch("different", 0.05, (f"century-conflict:{ca}!={cb}",))
    fa, fb = _features(A), _features(B)
    if not fa.size or not fb.size:
        return AuthorMatch("unknown", 0.0, ("empty-name",))
    na, nb = K(A.name), K(B.name)
    if na and na == nb:
        toks = set(na.split()) - {"بن", "ابن", "ابو", "ابي", "عبد"}
        if toks and toks <= (cg | cn | _STOP_TOKENS):
            return AuthorMatch("unknown", 0.5, ("identical-but-common",))
        return AuthorMatch("same", 1.0, ("identical",))
    S, L = (fa, fb) if fa.size <= fb.size else (fb, fa)
    support = 0
    distinctive = 0
    conflicts: list[str] = []
    checked = 0

    # ism and nasab
    if S.ism:
        checked += 1
        if L.ism:
            if S.ism == L.ism:
                support += 1
                reasons.append(f"ism:{S.ism}")
                if S.ism not in cg:
                    distinctive += 1
            elif S.ism in L.ibn and not S.nasab:
                pass  # the ism of a short form may be a forefather of the long one (rare): neutral
            else:
                conflicts.append(f"ism-conflict:{S.ism}!={L.ism}")
        elif S.ism in L.ibn or _strip_al(S.ism) in {_strip_al(x) for x in L.epithets | L.nisba}:
            support += 1  # «سيبويه» against a form that gives it as a laqab
    if S.nasab:
        checked += 1
        if L.nasab:
            ok = _nasab_fits(S.nasab, L.nasab, cg) or (
                len(S.nasab) >= 2 and _ibn_supported(K(S.nasab[-1]), L) and _nasab_fits(S.nasab[:-1], L.nasab, cg))
            if ok:
                support += 1
                reasons.append(f"nasab:{' '.join(S.nasab)}")
                if len(S.nasab) >= 2 or any(x not in cg for x in S.nasab):
                    distinctive += 1
            else:
                conflicts.append(f"nasab-conflict:{' '.join(S.nasab)}!={' '.join(L.nasab)}")
        elif all(_ibn_supported(K(x), L) for x in S.nasab[-1:]) and L.ibn:
            support += 1
    # «ابن X»: his own or a forefather's name
    for u in S.a.units:
        if u.kind != "ibn":
            continue
        checked += 1
        x = K(u.text)[4:]
        if _ibn_supported(x, L):
            support += 1
            reasons.append(f"shuhra:{u.text}")
            if x not in cg:
                distinctive += 1
        elif x not in cg and (any(v.kind == "ibn" for v in L.a.units) or K(L.shuhra).startswith("ابن ")):
            # another «ابن …» (a long nasab may stop before the forefather he is named after: Ibn al-Athir)
            conflicts.append(f"ibn-conflict:{u.text}")
    # kunya
    if S.kunya:
        checked += 1
        if L.kunya:
            if S.kunya == L.kunya:
                support += 1
                reasons.append(f"kunya:{S.kunya}")
                if S.kunya not in COMMON_KUNYA:
                    distinctive += 1
            else:
                conflicts.append(f"kunya-conflict:{S.kunya}!={L.kunya}")
    # laqab «X الدين»
    for x in S.laqab:
        checked += 1
        if x in L.laqab:
            support += 1
            reasons.append(f"laqab:{x}")
        elif L.laqab:
            conflicts.append(f"laqab-conflict:{x}")
    for x in S.titles:
        if x in L.titles:
            support += 1
            reasons.append(f"title:{x}")
    # epithets and nisbas: «الجاحظ», «السيوطي», «الحراني»
    l_al = L.nisba | L.epithets
    s_rare = [x for x in S.nisba | S.epithets if x not in cn and x not in _EPITHET_COMMON]
    l_var = l_al | {y[:-1] for y in l_al if y.endswith("ي") and len(y) > 5} | {y + "ي" for y in l_al}
    for x in S.nisba | S.epithets:
        checked += 1
        if x in l_var or _strip_al(x) in L.ibn:
            support += 1
            reasons.append(f"nisba:{x}")
            if x not in cn and x not in _EPITHET_COMMON:
                distinctive += 1
    l_rare = [x for x in l_al if x not in cn and x not in _EPITHET_COMMON]
    if s_rare and l_rare and not (set(s_rare) & set(l_rare)) and not any(_strip_al(x) in L.ibn for x in s_rare):
        # two distinctive nisbas or epithets and not one in common: «العسقلاني» / «الهيتمي», «الجد» / «الحفيد»
        if not (set(s_rare) & l_var) and not (set(l_rare) & (S.nisba | S.epithets)):
            conflicts.append(f"nisba-conflict:{'/'.join(s_rare)}!={'/'.join(l_rare)}")
    # the nasab triple: ism + father + grandfather all agree — distinctive even when each name is common
    if S.ism and S.ism == L.ism and len(S.nasab) >= 2 and _nasab_fits(S.nasab, L.nasab, cg) and \
            S.nasab[:2] == L.nasab[:2]:
        distinctive += 1
        reasons.append("nasab-triple")

    # each form has a name the other lacks: «فخر الدين الرازي» / «ابن أبي حاتم الرازي»
    for X, Y in ((S, L), (L, S)):
        x_lq = [x for x in X.laqab if x not in Y.laqab]
        y_ibn = [v for v in Y.a.units if v.kind == "ibn" and not _ibn_supported(K(v.text)[4:], X)]
        x_ibn = [v for v in X.a.units if v.kind == "ibn"]
        if x_lq and y_ibn and not x_ibn and not conflicts:
            conflicts.append(f"name-conflict:{x_lq[0]}!={y_ibn[0].text}")
    if conflicts:
        return AuthorMatch("different", round(0.2 * support / max(checked, 1), 3), tuple(conflicts + reasons))
    coverage = support / max(checked, 1)
    if support and distinctive:
        return AuthorMatch("same", round(0.75 + 0.25 * coverage, 3), tuple(reasons))
    if support and S.nisba and L.nisba and not (S.nisba & L.nisba):
        # only common parts in common, and their nisbas differ: «الخطيب البغدادي» / «الخطيب الشربيني»
        return AuthorMatch("different", 0.15, (f"nisba-mismatch:{'/'.join(S.nisba)}!={'/'.join(L.nisba)}", *reasons))
    if support:
        return AuthorMatch("unknown", round(0.3 + 0.3 * coverage, 3), ("only-common-tokens", *reasons))
    if S.shuhra and L.shuhra and K(S.shuhra) != K(L.shuhra) and S.size <= 2 and L.size <= 2:
        # two short «known as» forms that share nothing: «الغزالي» / «ابن رشد»
        return AuthorMatch("different", 0.05, (f"shuhra-conflict:{S.shuhra}!={L.shuhra}",))
    # no structural support: fall back to distinctive tokens (forms the parser could not read: Latin, odd orders)
    ta, tb = author_tokens(A.name), author_tokens(B.name)
    ts, tl = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    rare = {t for t in ts if t not in cg and t not in cn}
    if ts and ts <= tl and rare:
        return AuthorMatch("same", 0.75, ("tokens:" + " ".join(sorted(ts)),))
    return AuthorMatch("unknown", round(0.3 * coverage, 3), ("no-shared-part",))


def _nasab_fits(s: list[str], l: list[str], cg: frozenset[str]) -> bool:  # noqa: E741
    """The short nasab is in the long one: the father first, then forefathers in order (generations may be skipped);
    a short nasab of one distinctive name may be any forefather («أحمد بن حنبل» = «أحمد بن محمد بن حنبل»)."""
    if not s:
        return True
    if not l:
        return False
    if len(s) == 1 and s[0] not in cg:
        return s[0] in l or any(_strip_al(s[0]) == _strip_al(x) for x in l)
    if s[0] != l[0]:
        return False
    it = iter(l[1:])
    return all(any(x == y for y in it) for x in s[1:])


def author_similarity(a: str | AuthorName, b: str | AuthorName, **kw: object) -> float:
    """``match_authors(a, b).score``: 1.0 identical, ≥ 0.75 same person, < 0.3 different."""
    return match_authors(a, b, **kw).score  # type: ignore[arg-type]


def same_author(a: str | AuthorName, b: str | AuthorName, **kw: object) -> bool:
    """True when :func:`match_authors` says ``same``."""
    return match_authors(a, b, **kw).verdict == "same"  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------- editors and publishers
_PUB_STOP = _set(
    "بن ابن أبو ابو أبي ابي عبد الله محمد أحمد احمد علي الشيخ الدكتور د الأستاذ الاستاذ تحقيق ت ط دار مكتبة "
    "المكتبة مطبعة المطبعة مؤسسة شركة الكتب للنشر والنشر النشر والتوزيع التوزيع للطباعة الطباعة و في من القاهرة "
    "بيروت دمشق الرياض مصر لبنان وأولاده واولاده وشركاه ناشرون للنشر والتوزيع الإسلامية"
)


def _toks(s: str) -> set[str]:
    return {w for w in K(re.sub(r"[()،,.\-–/]", " ", s or "")).split() if len(w) > 2 and w not in _PUB_STOP}


def same_person(a: str, b: str) -> bool:
    """Two spellings of a modern person's name (an editor, a translator): they share at least two distinctive
    words, or the shorter has only one and the longer has it.

    >>> same_person("محمد محيي الدين عبد الحميد", "الشيخ محمد محيى الدين عبد الحميد")
    True
    """
    ta, tb = _toks(a), _toks(b)
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return len(short & long_) >= min(2, len(short))


#: Printing houses known under several names (public history of Arabic printing). A name belongs to a family when
#: all the words of one of its patterns are in it. Extend with ``same_publisher(..., families=…)``.
PUBLISHER_FAMILIES: dict[str, tuple[str, ...]] = {
    "bulaq": ("بولاق", "المطبعة الأميرية", "المطبعة الكبرى الأميرية", "المطبعة الكبرى ببولاق"),
    "babi-halabi-mustafa": ("مصطفى البابي الحلبي", "مكتبة الحلبي", "مطبعة الحلبي", "مصطفى الحلبي"),
    "babi-halabi-isa": ("عيسى البابي الحلبي", "دار إحياء الكتب العربية"),
    "dairat-al-maarif": ("دائرة المعارف العثمانية", "دائرة المعارف النظامية", "مجلس دائرة المعارف"),
    "salafiyya-cairo": ("المطبعة السلفية", "المكتبة السلفية ومكتبتها"),
}


def publisher_family(name: str, families: dict[str, tuple[str, ...]] | None = None) -> str:
    """The family key of a printing house known under several names, or "".

    >>> publisher_family("المطبعة الكبرى الأميرية ببولاق")
    'bulaq'
    """
    words = set(K(name).split())
    for key, pats in (families or PUBLISHER_FAMILIES).items():
        for pat in pats:
            pw = set(K(pat).split())
            if pw and pw <= words | {w.removeprefix("ب") for w in words}:
                return key
    return ""


def same_publisher(a: str, b: str, *, families: dict[str, tuple[str, ...]] | None = None) -> bool:
    """Two forms of a publisher's name: the same distinctive words once places and generic words are set aside
    («دار الفكر» is not «دار الفكر المعاصر»).

    >>> same_publisher("دار الكتب العلمية - بيروت", "دار الكتب العلمية")
    True
    """
    fa, fb = publisher_family(a, families), publisher_family(b, families)
    if fa or fb:
        return fa == fb
    ta, tb = _toks(a), _toks(b)
    if not ta or not tb:
        return K(a) == K(b) and bool(K(a))
    return ta == tb
