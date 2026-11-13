"""Hooks for other tools.

* `pocketshelf <https://warraq.benjelloun.dev/pocketshelf/>`_ reads a book's fields from its file name through the
  ``pocketshelf.profiles`` entry point: :func:`pocketshelf_profile`.
"""

from __future__ import annotations

import re

from .authors import parse_author
from .compose import parse_name
from .dates import hijri_year_to_gregorian

__all__ = ["pocketshelf_profile"]


def pocketshelf_profile(stem: str, is_folder: bool = False) -> dict[str, object] | None:
    """A `warraq` name → pocketshelf's fields (title, author, author_death, author_calendar, editor, publisher,
    place, year, edition, volume, lang); None when the name does not look like one."""
    p = parse_name(stem, is_folder=is_folder)
    if not p.get("title") or not (p.get("author") or p.get("editor") or p.get("publisher")):
        return None
    out: dict[str, object] = {"title": p["title"]}
    if re.search("[\u0600-\u06ff]", stem):
        out["lang"] = "ar"
    if p.get("author"):
        a = str(p["author"])
        out["author"] = a
        d = parse_author(a).death
        if d:
            out["author_death"] = d
            out["author_calendar"] = "ah"
    if p.get("editor"):
        out["editor"] = p["editor"]
    if p.get("publisher"):
        out["publisher"] = p["publisher"]
    if p.get("city"):
        out["place"] = p["city"]
    if p.get("year"):
        out["year"] = int(p["year"])  # type: ignore[call-overload]
    elif p.get("year_hijri"):
        out["year"] = hijri_year_to_gregorian(int(p["year_hijri"]))[0]  # type: ignore[call-overload]
    if p.get("kinds"):
        out["edition"] = " - ".join(p["kinds"])  # type: ignore[arg-type]
    if p.get("volume") and not is_folder:
        out["volume"] = p["volume"]
    return out
