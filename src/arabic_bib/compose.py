"""Book and volume names from their parts, under a naming profile.

The default `warraq` profile writes::

    <title> - <author> - ت <editor> - <publisher> <city> <year>

with no parentheses, no commas, no «ط», no «=», within 240 bytes with the extension. **Nothing is shortened when the
whole name fits.** When it does not, parts give way in the profile's order — for `warraq`: the year, the city, a
subtitle, the publisher, editors after the second, other contributors, authors after the second, a long printed role,
people's names (to a shorter form of the same name), the words after each title's head, the second author, the
joined titles («ويليه»), the first editor — and the most important part dropped is put back whenever room allows.
A title is cut only at a natural break («جمع الجوامع في أصول الفقه» → «جمع الجوامع»), never inside a word or a
pair («القضاء والفتيا»).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from .authors import parse_author
from .edition import parse_edition
from .normalize import search_key
from .spelling import safe_filename

__all__ = [
    "Book", "Composed", "NameProfile", "PROFILES", "compose", "explain", "get_profile", "keep_label", "name_forms",
    "parse_name", "volume", "volumes",
]

N = search_key


def B(s: str) -> int:
    return len(s.encode())


# ------------------------------------------------------------------------------------------------------ profile
GIVE_WAY_WARRAQ = (
    "year", "city", "subtitle", "publisher", "editors_after_2", "contributors", "authors_after_2", "role",
    "person_names", "title_tails", "second_author", "joined_titles", "first_editor", "title_words", "author",
)


@dataclass(frozen=True)
class NameProfile:
    """A naming convention. Fields in the template: {title} {author} {editor} (role + names) {contributors}
    {imprint} (publisher city year) {publisher} {city} {year} {kinds}; a [...] group is written only when every field
    in it has a value."""

    name: str
    template: str = "{title}[ - {author}][ - {editor}][ - {contributors}][ - {imprint}][ - {kinds}]"
    max_bytes: int = 255  # per name, the extension included (ext4, NTFS, FAT: 255)
    extension: str = ".pdf"
    reserve_bytes: int = 0  # kept free (temporary suffixes of upload tools …)
    parentheses: bool = True
    commas: bool = True
    equals: bool = True  # «=» between alternative titles; False → «أو»
    ta_prefix: bool = True  # «ط <publisher>»; False → the publisher alone
    default_role: str = "ت"
    give_way: tuple[str, ...] = GIVE_WAY_WARRAQ
    # audit switches
    forbidden_words: tuple[str, ...] = ()
    check_wasl: bool = True
    one_file_folder: bool = False  # a folder that holds one file is flagged (it should be a plain file)
    numbered_99: bool = False  # «99 - الفهارس» is flagged (indexes take the number after the last volume)
    allowed_extensions: tuple[str, ...] = ()
    description: str = ""

    @property
    def limit(self) -> int:
        """Bytes left for the name without its extension."""
        return self.max_bytes - B(self.extension) - self.reserve_bytes


PROFILES: dict[str, NameProfile] = {
    "warraq": NameProfile(
        name="warraq",
        max_bytes=240,
        parentheses=False,
        commas=False,
        equals=False,
        ta_prefix=False,
        forbidden_words=("تحميل", "اونلاين", "أونلاين", "pdf ", "_alt", "نسخة ثانية"),
        one_file_folder=True,
        numbered_99=True,
        allowed_extensions=(".pdf",),
        description="The Warraq library rules: title - author - ت editor - publisher city; no () , ط =; 240 bytes.",
    ),
    "plain": NameProfile(
        name="plain",
        description="Any file system: forbidden characters out, 255 bytes, brackets and commas kept.",
    ),
    "author-first": NameProfile(
        name="author-first",
        template="[{author} - ]{title}[ - {editor}][ - {imprint}]",
        description="«Author - Title» for shelves sorted by author (Calibre-like).",
    ),
}


def get_profile(p: str | NameProfile) -> NameProfile:
    if isinstance(p, NameProfile):
        return p
    try:
        return PROFILES[p]
    except KeyError:
        raise ValueError(f"unknown naming profile {p!r}; choose one of {', '.join(PROFILES)}") from None


# ------------------------------------------------------------------------------------------------------- book
@dataclass(frozen=True)
class Book:
    """A book's parts, as printed. `author` may name several people («X ومحمد Y»)."""

    title: str
    author: str = ""
    editors: tuple[str, ...] = ()
    role: str = ""  # the editor's printed role; empty → the profile's default («ت»)
    contributors: tuple[str, ...] = ()  # other roles as printed: «قدم له فلان»
    publisher: str = ""
    city: str = ""
    year: str = ""
    kinds: tuple[str, ...] = ()  # «مخطوط», «رسالة ماجستير», «طبعة حجرية»

    @classmethod
    def parse(cls, title: str, author: str = "", edition: str = "", **kw: object) -> Book:
        """A book from a title, an author and an imprint line read by :func:`~arabic_bib.edition.parse_edition`."""
        e = parse_edition(edition) if edition else None
        role = ""
        if e and e.role:
            role = "" if re.fullmatch(r"ت\.?|تحقيق|تح|حققه|المحقق|محقق", e.role) else e.role
        fields: dict[str, object] = {
            "title": title,
            "author": author,
            "editors": tuple(e.editors) if e else (),
            "role": role,
            "contributors": tuple(e.contributors) if e else (),
            "publisher": e.publisher if e else "",
            "city": e.city if e else "",
            "kinds": (e.kind,) if e and e.kind else (),
        }
        fields.update(kw)
        return cls(**fields)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------------------- the title's anatomy
JOIN = re.compile(r"\s+(ويليه|ويليها|ومعه|ومعها|وبهامشه|وبهامشها|وبذيله|وذيله|وفي آخره|=)\s+")
SUB = re.compile(r"\s*،\s*|\s+-\s+|\s+(?:المسمى|المسماة|الموسوم|الموسومة|وهو|وهي)\s+")
PARTICLES = {N(w) for w in ["في", "من", "على", "عن", "إلى", "الى", "بين", "مع", "لما", "لمن", "لأهل", "لمعرفة", "لبيان", "لشرح", "بشرح", "شرح", "وهو", "أو"]}
WEAK_END = {N(w) for w in ["بن", "ابن", "أبي", "أبو", "عبد", "ذي", "ذو", "أهل", "دار", "شيخ", "الإمام", "الشيخ", "لما", "ما", "لمن", "الذي", "التي", "و", "في", "من", "على", "عن", "إلى", "أكثر", "أقل", "بعض", "كل", "أهم", "نحو", "حول", "ضد", "غير", "سائر", "جميع", "بين", "مع"]}
EDITION_KIND = re.compile(r"^(مخطوط|مخطوطة|رسالة( علمية| جامعية| ماجستير| دكتوراه|)|أطروحة.*|بحث محكم|نسخة خطية)$")
DATEWORD = re.compile(r"^([\d٠-٩]+|هـ|ه|م|-|–)$")
UPTO = {N(w) for w in ["إلى", "الى", "حتى"]}
SUFFIX = ("هما", "هم", "ها", "ه")
CLAUSE = {N(w) for w in ["فيما", "مما", "عما", "بما", "لما", "وما", "ومن", "وفي"]}
TASHKEEL = re.compile(r"[ً-ْٰ]")
RELATION = {N(w) for w in ["أثر", "أثره", "أثرها", "أثرهم", "آثار", "آثاره", "آثارها", "دور", "دوره", "دورها", "دورهم", "موقف", "موقفه", "موقفها", "منهج", "منهجه", "منهجها", "جهود", "جهوده", "جهودها", "علاقة", "علاقته", "علاقتها", "صلة", "صلته", "صلتها", "أهمية", "أهميته", "أهميتها", "تطبيق", "تطبيقه", "تطبيقاته", "تطبيقاتها", "انعكاس", "انعكاسه", "انعكاساته", "مكانة", "مكانته", "مكانتها", "مدى"]}
POINTER = {N(w) for w in ["ذلك", "ذلكم", "هذا", "هذه", "هذين", "تلك", "عليه", "عليها", "فيه", "فيها", "منه", "منها", "به", "بها", "له", "لها"]}


def tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" -،")
    s = re.sub(r"\(\s*\)", "", s)
    return s.strip()


def split_title(title: str) -> tuple[str, list[str], list[str]]:
    """The title's own brackets → (title without them, edition words such as «مخطوط», a subtitle); a one- or
    two-word aside stays inline («ابن رشد (الجد)» → «ابن رشد الجد»)."""
    ed: list[str] = []
    sub: list[str] = []

    def take(m: re.Match[str]) -> str:
        x = m.group(1).strip()
        if EDITION_KIND.match(x):
            ed.append(x)
            return " "
        if len(x.split()) <= 2:
            return " " + x + " "
        sub.append(x)
        return " "

    return tidy(re.sub(r"\(([^()]*)\)", take, title)), ed, sub


def _one_member(w: list[str], i: int) -> bool:
    """Is the «و…» word w[i] one member of a pair that cannot be cut off («القضاء والفتيا», «إتيانه واجتنابه»)?"""
    rest = [x for x in w[i + 1 :] if not DATEWORD.match(x)]
    if not rest:
        return True
    nx = N(rest[0])
    if nx in PARTICLES or nx in CLAUSE:
        return True
    if N(w[i])[1:].startswith(N("إيا")):
        return True
    raw = lambda x: TASHKEEL.sub("", x)  # noqa: E731
    sf = next((x for x in SUFFIX if raw(w[i]).endswith(x)), None)
    return bool(sf and len(raw(w[i])) > 4 and any(raw(x).endswith(sf) and len(raw(x)) > 3 for x in w[max(0, i - 3) : i]))


def _whole_clause(k: list[str]) -> list[str]:
    """A «و…» clause naming a relation («وأثره في …») is kept whole or dropped whole."""
    for j in range(len(k) - 1, max(0, len(k) - 4), -1):
        t = N(k[j])
        if t.startswith("و") and t[1:] in RELATION:
            return k[:j]
    if len(k) > 2 and N(k[-1]) in POINTER:
        for j in range(len(k) - 2, max(0, len(k) - 5), -1):
            if N(k[j]).startswith("و") and len(N(k[j])) > 2:
                return k[:j]
    return k


def cuts(seg: str) -> list[str]:
    """A title's natural breaks, longest prefix first: before a particle («في», «من», «فيما»), a «و…» or «لـ…» word,
    from the third word on; never inside a pair, a range («من … إلى …») or a «و…» clause that needs its end.

    >>> cuts("الاستذكار الجامع لمذاهب فقهاء الأمصار")
    ['الاستذكار الجامع']
    """
    w = seg.split()
    out: list[str] = []
    for i in range(len(w) - 1, 1, -1):
        n = N(w[i])
        if n in PARTICLES or n in CLAUSE or (
            len(n) > 3 and (n.startswith("و") or n.startswith("لل") or n.startswith("لم") or n.startswith("لا"))
        ):
            if n.startswith("و") and n not in PARTICLES and _one_member(w, i):
                continue
            if n in UPTO and any(N(x) == "من" for x in w[max(0, i - 6) : i]):
                continue
            k = w[:i]
            if len(k) > 2 and N(k[-2]) in {N(x) for x in ("ما", "مما", "فيما", "عما", "بما", "لما", "وما")}:
                continue
            if len(k) > 1 and n.startswith("ل") and N(k[-1]).startswith("و") and len(N(k[-1])) > 3:
                k.pop()
            while len(k) > 1 and N(k[-1]) in WEAK_END:
                k.pop()
            k = _whole_clause(k)
            if k and " ".join(k) not in out:
                out.append(" ".join(k))
    return out


def title_options(seg: str) -> list[str]:
    """A title part, whole, then without its subtitle, then cut at each natural break (longest first)."""
    out = [seg]
    ns = SUB.split(seg)[0].strip()
    if ns and ns != seg:
        out.append(ns)
    out += [c for c in cuts(ns) if c not in out]
    return out


PERSONS = re.compile(
    r"\s+و(?=(?:محمد|أحمد|عبد|علي|صالح|عمر|عثمان|إبراهيم|يوسف|حسن|حسين|أبو|أبي|ابن|إسماعيل|خالد|سعيد|مصطفى|"
    r"عامر|نبيل|محمود)\b|\S+\sالدين\b)"
)


def name_forms(x: str) -> list[str]:
    """A person's name and its shorter forms, longest first (≥ 2 words each when the name has more)."""
    if len(x.split()) <= 2:
        return [x]
    fs = [f for f in parse_author(x).forms() if len(f.split()) >= 2 or len(x.split()) <= 1]
    fs = [x] + [f for f in fs if f != x and N(f) != N(x) and len(f.split()) < len(x.split())]
    return sorted(dict.fromkeys(fs), key=lambda t: -len(t.split())) or [x]


def _people(author: str) -> list[str]:
    return [p.strip() for p in PERSONS.split(author) if p.strip()] if author else []


def keep_label(label: str) -> str:
    """A volume's label is kept only when it says what the file IS (cover, introduction, indexes, appendix,
    manuscript images), not a range of its contents («إحياء الموات - أمهات الأولاد»)."""
    lb = tidy(re.sub(r"^\((.*)\)$", r"\1", label or ""))
    m = FUNCTION.match(lb)
    if not m:
        return ""
    return re.sub(r"\s*\d+$", lambda x: x.group(0) if "فهارس" in lb or "ملحق" in lb else "", lb)


FUNCTION = re.compile(
    r"^(الواجهة|الغلاف|المقدمة|مقدمة التحقيق|مقدمة المحقق|الدراسة|قسم الدراسة|الفهارس|فهارس|الفهرس|الفهارس العامة|"
    r"الفهارس العلمية|ملحق|ملاحق|الملحق|صور المخطوطات?|المستدرك|الاستدراك|التكملة|الذيل)\b"
)
_AUTHOR_DEATH = re.compile(
    r"^(?:ت\.?|المتوفى|المتوفي|توفي)?\s*(?:بعد|قبل|نحو|حوالي)?\s*\d{1,4}(?:\s*[-–]\s*\d{1,4})?\s*(?:هـ|ه)?"
    r"(?:\s*/\s*\d{3,4}\s*م?)?$"
)


# ------------------------------------------------------------------------------------------------ the composer
@dataclass
class _State:
    n_joined: int
    seg_level: list[int]
    subtitle: bool = True
    n_people: int = 0
    people_form: int = 0
    n_editors: int = 0
    editor_form: int = 0
    role_level: int = 0
    n_contrib: int = 0
    publisher: bool = True
    city: bool = True
    year: bool = True
    title_words: int = 0  # words cut off the first title as a last resort
    author: bool = True

    def copy(self) -> _State:
        return replace(self, seg_level=list(self.seg_level))


@dataclass
class _Parts:
    segs: list[str]
    joins: list[str]
    opts: list[list[str]]
    heads: list[int]  # index in opts of each segment's head (its shortest natural form)
    sub: list[str]
    kinds: list[str]
    people: list[str]
    people_forms: list[list[str]]
    editors: list[str]
    editor_forms: list[str]
    roles: list[str]
    contrib: list[str]
    publisher: str
    city: str
    year: str


_FIELD = re.compile(r"\{(\w+)\}")


def _render(template: str, values: dict[str, str]) -> str:
    def group(m: re.Match[str]) -> str:
        body = m.group(1)
        names = _FIELD.findall(body)
        if names and all(values.get(n) for n in names):
            return _FIELD.sub(lambda f: values[f.group(1)], body)
        return ""

    s = template
    while re.search(r"\[[^\[\]]*\]", s):
        s = re.sub(r"\[([^\[\]]*)\]", group, s)
    return _FIELD.sub(lambda f: values.get(f.group(1), ""), s)


def _prepare(book: Book, prof: NameProfile) -> _Parts:
    title = tidy(book.title)
    kinds = [k for k in book.kinds if k]
    sub: list[str] = []
    if not prof.parentheses:
        title, ed_kinds, sub = split_title(title)
        kinds = ed_kinds + kinds
    author = TASHKEEL.sub("", book.author or "")
    if ";" in author or "؛" in author:  # Shamela's «short؛ full»: the full form when it holds the short one
        a, b = [y.strip() for y in re.split(r"[؛;]", author, maxsplit=1)]
        b = re.split(r"،", b)[0].strip()
        author = b if set(N(a).split()) <= set(N(b).split()) else a
    if not prof.parentheses:
        for x in re.findall(r"\(([^()]*)\)", author):
            x = tidy(x)
            if _AUTHOR_DEATH.match(x):
                continue  # «التويجري (1413 هـ)»: his death year, never the print's
            if x:
                kinds.append(x)
        author = tidy(re.sub(r"\([^()]*\)", " ", author))
    parts = JOIN.split(title)
    segs, joins = parts[0::2], parts[1::2]
    opts = [title_options(s)[:10] for s in segs]
    heads = [len(o) - 1 for o in opts]
    people = _people(author)
    pforms = [name_forms(p) for p in people]
    editors = [TASHKEEL.sub("", e).strip() for e in book.editors if e.strip()]
    eforms = name_forms(editors[0])[:4] if editors else []
    role0 = book.role or prof.default_role
    roles = [role0]
    rparts = role0.split(" و")
    if len(rparts) > 1:
        roles += [prof.default_role] if re.search(r"حقق|تحقيق", role0) else [
            " و".join(rparts[:j]) for j in range(len(rparts) - 1, 0, -1)
        ]
    return _Parts(segs, joins, opts, heads, sub, kinds, people, pforms, editors, eforms, roles,
                  [tidy(c) for c in book.contributors if tidy(c)], book.publisher.strip(), book.city.strip(),
                  str(book.year or "").strip())


def _build(p: _Parts, st: _State, prof: NameProfile) -> str:
    # title
    first = p.opts[0][st.seg_level[0]] if p.opts else ""
    if st.title_words:
        w = first.split()
        w = w[: max(1, len(w) - st.title_words)]
        while len(w) > 1 and N(w[-1]) in WEAK_END:
            w.pop()
        first = " ".join(w)
    t = first
    for i in range(1, st.n_joined):
        j = p.joins[i - 1]
        if j == "=" and not prof.equals:
            j = "أو"
        t += f" {j} {p.opts[i][st.seg_level[i]]}"
    if st.subtitle and p.sub:
        t += "، " + "، ".join(p.sub)
    # people
    author = ""
    if st.author and p.people:
        names = []
        for k, _name in enumerate(p.people[: st.n_people]):
            forms = p.people_forms[k]
            names.append(forms[min(st.people_form, len(forms) - 1)])
        author = " و".join(names)
    editor = ""
    if st.n_editors and p.editors:
        first_ed = p.editor_forms[min(st.editor_form, len(p.editor_forms) - 1)]
        names = [first_ed] + p.editors[1 : st.n_editors]
        editor = f"{p.roles[min(st.role_level, len(p.roles) - 1)]} " + " و".join(names)
    contributors = " - ".join(p.contrib[: st.n_contrib])
    pub = p.publisher if st.publisher else ""
    gone = bool(p.publisher) and not st.publisher  # the place and year of a print go with its printer
    city = p.city if (st.city and p.city and not gone and N(p.city) not in N(pub)) else ""
    year = p.year if (st.year and not gone) else ""
    if pub and prof.ta_prefix and not p.editors:
        pub = "ط " + pub
    imprint = " ".join(x for x in (pub, city, year) if x)
    kinds = [k for k in p.kinds if not (imprint and N(k) in N(imprint))]
    vals = {
        "title": t, "author": author, "editor": editor, "contributors": contributors, "imprint": imprint,
        "publisher": pub, "city": city, "year": year, "kinds": " - ".join(kinds),
        "editors": " و".join(p.editors[: st.n_editors]), "role": p.roles[0] if p.roles else "",
    }
    s = _render(prof.template, vals)
    if not prof.commas:
        s = re.sub(r"\s*[،,]\s*", " ", s)
    s = safe_filename(s, max_bytes=10_000, keep_parentheses=prof.parentheses)
    return tidy(s)


def _steps(p: _Parts, st: _State, step: str) -> bool:
    """Apply one notch of a give-way step; False when the step has nothing left to give."""
    if step == "year":
        if st.year and p.year:
            st.year = False
            return True
    elif step == "city":
        if st.city and p.city:
            st.city = False
            return True
    elif step == "subtitle":
        if st.subtitle and p.sub:
            st.subtitle = False
            return True
    elif step == "publisher":
        if st.publisher and p.publisher:
            st.publisher = False
            st.year = False  # a print's year belongs to its printer: never alone once the publisher has gone
            return True
    elif step == "editors_after_2":
        if st.n_editors > 2:
            st.n_editors -= 1
            return True
    elif step == "contributors":
        if st.n_contrib > 0:
            st.n_contrib -= 1
            return True
    elif step == "authors_after_2":
        if st.n_people > 2:
            st.n_people -= 1
            return True
    elif step == "role":
        if st.role_level < len(p.roles) - 1 and st.n_editors:
            st.role_level += 1
            return True
    elif step == "person_names":
        if st.n_editors and st.editor_form < len(p.editor_forms) - 1:
            st.editor_form += 1
            return True
        if p.people_forms and st.people_form < max(len(f) for f in p.people_forms) - 1:
            st.people_form += 1
            return True
    elif step == "title_tails":
        for i in range(st.n_joined - 1, -1, -1):  # the later joined titles first
            if st.seg_level[i] < p.heads[i]:
                st.seg_level[i] += 1
                return True
    elif step == "second_author":
        if st.n_people > 1:
            st.n_people = 1
            return True
    elif step == "joined_titles":
        if st.n_joined > 1:
            st.n_joined -= 1
            return True
    elif step == "first_editor":
        if st.n_editors > 0:
            st.n_editors = 0
            st.n_contrib = 0
            return True
    elif step == "title_words":
        if len(p.opts[0][st.seg_level[0]].split()) - st.title_words > 2:
            st.title_words += 1
            return True
    elif step == "author":
        if st.author and p.people:
            st.author = False
            return True
    else:
        raise ValueError(f"unknown give-way step {step!r}")
    return False


@dataclass(frozen=True)
class Composed:
    """A composed name and what gave way to make it fit."""

    name: str
    fits: bool
    gave_way: tuple[str, ...] = field(default=())
    bytes: int = 0


def explain(book: Book, profile: str | NameProfile = "warraq", *, limit: int | None = None) -> Composed:
    """Like :func:`compose`, with the list of steps that gave way."""
    prof = get_profile(profile)
    lim = prof.limit if limit is None else limit
    p = _prepare(book, prof)
    st = _State(
        n_joined=len(p.segs), seg_level=[0] * len(p.segs), n_people=len(p.people), n_editors=len(p.editors),
        n_contrib=len(p.contrib),
    )
    name = _build(p, st, prof)
    if B(name) <= lim:
        return Composed(name, True, (), B(name))
    history: list[tuple[str, _State]] = []
    for step in prof.give_way:
        while B(_build(p, st, prof)) > lim:
            before = st.copy()
            if not _steps(p, st, step):
                break
            history.append((step, before))
        if B(_build(p, st, prof)) <= lim:
            break
    # put back what gave way, the most important first, whenever it fits again
    for step, before in reversed(history):
        trial = _merge(st, before, step)
        if B(_build(p, trial, prof)) <= lim:
            st = trial
    name = _build(p, st, prof)
    gave = tuple(dict.fromkeys(s for s, _ in history if _differs(st, _State_full(p), s)))
    if B(name) > lim:  # one huge word: cut at a word boundary, then bytes
        name = safe_filename(name, max_bytes=lim)
    return Composed(name, B(name) <= lim, gave, B(name))


def _State_full(p: _Parts) -> _State:  # noqa: N802
    return _State(n_joined=len(p.segs), seg_level=[0] * len(p.segs), n_people=len(p.people),
                  n_editors=len(p.editors), n_contrib=len(p.contrib))


_STEP_FIELDS = {
    "year": ("year",), "city": ("city",), "subtitle": ("subtitle",), "publisher": ("publisher", "year"),
    "editors_after_2": ("n_editors",), "contributors": ("n_contrib",), "authors_after_2": ("n_people",),
    "role": ("role_level",), "person_names": ("editor_form", "people_form"), "title_tails": ("seg_level",),
    "second_author": ("n_people",), "joined_titles": ("n_joined",), "first_editor": ("n_editors", "n_contrib"),
    "title_words": ("title_words",), "author": ("author",),
}


def _merge(cur: _State, before: _State, step: str) -> _State:
    t = cur.copy()
    for f in _STEP_FIELDS[step]:
        setattr(t, f, list(before.seg_level) if f == "seg_level" else getattr(before, f))
    return t


def _differs(cur: _State, full: _State, step: str) -> bool:
    return any(getattr(cur, f) != getattr(full, f) for f in _STEP_FIELDS[step])


def compose(
    title: str | Book,
    author: str = "",
    edition: str = "",
    *,
    profile: str | NameProfile = "warraq",
    limit: int | None = None,
    **fields: object,
) -> str:
    """The name of a book (without its extension) under a profile: everything when it fits, else what keeps the
    most information in the profile's order of importance.

    `title` is a title string (with `author` and an imprint line `edition`, read by
    :func:`~arabic_bib.edition.parse_edition`) or a :class:`Book`. Extra keyword fields (``year=``, ``kinds=``,
    ``publisher=`` …) override what the imprint line gave.

    >>> compose("الرسالة", "الشافعي", "ت أحمد شاكر - مكتبة الحلبي، القاهرة")
    'الرسالة - الشافعي - ت أحمد شاكر - مكتبة الحلبي القاهرة'
    """
    book = title if isinstance(title, Book) else Book.parse(title, author, edition, **fields)
    return explain(book, profile, limit=limit).name


def volume(nn: str, book: Book | str, label: str = "", *, profile: str | NameProfile = "warraq", **kw: object) -> str:
    """«NN - <the book's name> - <label>»: every volume carries the whole name, shortened only when needed."""
    prof = get_profile(profile)
    b = book if isinstance(book, Book) else Book.parse(book, **kw)  # type: ignore[arg-type]
    label = tidy(re.sub(r"^\((.*)\)$", r"\1", label or ""))
    pre, post = f"{nn} - ", f" - {label}" if label else ""
    return pre + explain(b, prof, limit=prof.limit - B(pre) - B(post)).name + post


def volumes(
    book: Book, items: Sequence[tuple[str, str]], *, profile: str | NameProfile = "warraq"
) -> list[str]:
    """The files of one set: ONE shared name for every volume, sized for the longest «NN - … - <label>», so that
    no volume says less than another. `items` = [(nn, label)]; labels are kept only when :func:`keep_label` says so."""
    prof = get_profile(profile)
    clean = [(nn, keep_label(lb)) for nn, lb in items]
    room = min(prof.limit - B(f"{nn} - ") - (B(f" - {lb}") if lb else 0) for nn, lb in clean)
    core = explain(book, prof, limit=room).name
    return [f"{nn} - {core}" + (f" - {lb}" if lb else "") for nn, lb in clean]


# ------------------------------------------------------------------------------------------- reading a name back
_ROLE_HEAD = re.compile(
    r"^(?:ت|ترجمة|تحقيق|حققه|صححه|ضبطه|اعتنى|عني|شرح|تقديم|قدم|إشراف|جمع|إعداد|تخريج|مراجعة|راجعه|علق|تعليق|"
    r"قرأه|تنسيق|نسخه)(?:\s|$)"
)
_PUB_HEAD = re.compile(
    r"^(?:ط\s+)?(?:دار|مكتبة|المكتبة|مكتبه|مؤسسة|مطبعة|المطبعة|مطابع|المكتب|وزارة|مجمع|المجمع|جامعة|مركز|الهيئة|"
    r"المجلس|عالم|إدارة|الأمانة|بيت|شركة|منشورات|معهد|الجمعية|جمعية|الدار|دائرة|مجلس|طبعة حجرية)(?:\s|$)"
)
_KIND_SEG = re.compile(r"^(?:مخطوط|مخطوطة|رسالة(?: علمية| جامعية| ماجستير| دكتوراه)?|أطروحة.*|بحث محكم|نسخة خطية|"
                       r"طبعة حجرية|مستل.*)$")


def parse_name(name: str, *, is_folder: bool = False) -> dict[str, object]:
    """Read a name written by the `warraq` profile back into its parts.

    >>> parse_name("03 - الرسالة - الشافعي - ت أحمد شاكر - مكتبة الحلبي القاهرة.pdf")["publisher"]
    'مكتبة الحلبي'
    """
    s = name
    if not is_folder:
        s = re.sub(r"\.(pdf|epub|djvu|docx?|txt)$", "", s, flags=re.I)
    out: dict[str, object] = {}
    m = re.match(r"^(\d{1,4}) - (.+)$", s)
    if m:
        out["volume"] = m.group(1)
        s = m.group(2)
    segs = [x.strip() for x in re.split(r"\s+-\s+", s) if x.strip()]
    if not segs:
        return out
    out["title"] = segs[0]
    kinds: list[str] = []
    for i, seg in enumerate(segs[1:], 1):
        if _ROLE_HEAD.match(seg) and "editor" not in out:
            role, _, names = seg.partition(" ")
            if role != "ت":
                mm = re.match(r"^(.*?(?:عليه|له|لها|به|بها|وشرحه|وحققه|بتصحيحه))\s+(.+)$", seg)
                role, names = (mm.group(1), mm.group(2)) if mm else (role, names)
            out["role"] = role
            out["editor"] = names
            out["editors"] = [x.strip() for x in PERSONS.split(names) if x.strip()]
        elif _KIND_SEG.match(seg):
            kinds.append(seg)
        elif i == len(segs) - 1 and keep_label(seg):
            out["label"] = seg
        elif _PUB_HEAD.match(seg) or ("author" in out and "publisher" not in out):
            e = parse_edition(re.sub(r"^ط\s+", "", seg))
            if seg.startswith("طبعة حجرية"):
                kinds.append("طبعة حجرية")
            pub = e.publisher or (seg if not e.places else "")
            if pub:
                out["publisher"] = pub
            if e.city:
                out["city"] = e.city
            if e.hijri:
                out["year_hijri"] = e.hijri
            if e.gregorian:
                out["year"] = e.gregorian
        elif "author" not in out and i == 1:
            out["author"] = seg
        else:
            out.setdefault("rest", []).append(seg)  # type: ignore[union-attr]
    if kinds:
        out["kinds"] = kinds
    return out
