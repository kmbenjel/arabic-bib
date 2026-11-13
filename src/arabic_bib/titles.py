"""Title keys and the parts of a book title («… ويليه …», «… أو …», a subtitle)."""

from __future__ import annotations

import re

from .normalize import key_norm

__all__ = ["JOINERS", "split_joined", "title_key"]

#: words that join two works in one volume, as printed: «ويليه», «ومعه», «وبهامشه», «=» (an alternative title)
JOINERS = ("ويليه", "ويليها", "ومعه", "ومعها", "وبهامشه", "وبهامشها", "وبذيله", "وذيله", "وفي آخره", "=")
_JOIN_RE = re.compile(r"\s+(" + "|".join(map(re.escape, JOINERS)) + r")\s+")
_ASIDE = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def title_key(title: str | None) -> str:
    """A title's catalogue key (keys v1, frozen): asides in brackets dropped, cut at the first « - », « ط », « ت »,
    :func:`~arabic_bib.normalize.key_norm`, a leading «كتاب» dropped when more words follow.

    >>> title_key("كتاب الأمّ (ط. دار المعرفة) - الشافعي")
    'الام'
    """
    t = _ASIDE.sub(" ", title or "")
    t = re.split(r"\s+-\s+|\s+ط\s|\s+ت\s", " " + t + " ")[0]
    w = key_norm(t).split()
    if w and w[0] == "كتاب" and len(w) > 1:
        w = w[1:]
    return " ".join(w)


def split_joined(title: str) -> list[tuple[str, str]]:
    """«جمع الجوامع ويليه همع الهوامع» → [("", "جمع الجوامع"), ("ويليه", "همع الهوامع")]."""
    parts = _JOIN_RE.split(title.strip())
    out = [("", parts[0].strip())]
    for j, p in zip(parts[1::2], parts[2::2]):
        out.append((j, p.strip()))
    return out
