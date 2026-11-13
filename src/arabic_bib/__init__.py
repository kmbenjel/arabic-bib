"""arabic-bib: Arabic bibliographic text — normalisation, names, authors, dates and editions.

The names below are the stable API (semver): they keep their signatures; new options come as keyword arguments.
"""

from __future__ import annotations

from .audit import Issue, audit_name, audit_tree, fix_name
from .authors import (
    AuthorMatch,
    AuthorName,
    author_key,
    author_similarity,
    author_tokens,
    match_authors,
    parse_author,
    publisher_family,
    same_author,
    same_person,
    same_publisher,
)
from .compose import Book, NameProfile, compose, explain, get_profile, parse_name, volume, volumes
from .dates import (
    Death,
    century_label,
    century_of,
    gregorian_to_hijri,
    gregorian_year_to_hijri,
    hijri_to_gregorian,
    hijri_year_to_gregorian,
    parse_century,
    parse_death,
    strip_dates,
)
from .edition import Edition, parse_edition
from .normalize import (
    Mapped,
    NormProfile,
    key_norm,
    normalize,
    normalize_mapped,
    search_key,
    strip_diacritics,
    to_ascii_digits,
)
from .numerals import cardinal_value, ordinal_value, ordinal_word
from .spelling import fix_wasl, safe_filename, wasl_errors
from .titles import split_joined, title_key

__version__ = "0.1.0"

__all__ = [
    "AuthorMatch", "AuthorName", "Book", "Death", "Edition", "Issue", "Mapped", "NameProfile", "NormProfile",
    "audit_name", "audit_tree", "author_key", "author_similarity", "author_tokens", "cardinal_value",
    "century_label", "century_of", "compose", "explain", "fix_name", "fix_wasl", "get_profile",
    "gregorian_to_hijri", "key_norm", "gregorian_year_to_hijri", "hijri_to_gregorian", "hijri_year_to_gregorian",
    "match_authors", "normalize", "normalize_mapped", "ordinal_value", "ordinal_word", "parse_author",
    "parse_century", "parse_death", "publisher_family", "parse_edition", "parse_name", "safe_filename", "same_author", "same_person",
    "same_publisher", "search_key", "split_joined", "strip_dates", "strip_diacritics", "title_key",
    "to_ascii_digits", "volume", "volumes", "wasl_errors", "__version__",
]
