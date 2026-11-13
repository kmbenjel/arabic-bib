from __future__ import annotations

from pathlib import Path

CASES = Path(__file__).parent / "cases"


def load(name: str) -> list[list[str]]:
    """Rows of a tab-separated case table; «#» lines are comments, and each row is padded to the header width."""
    rows = []
    header = None
    with open(CASES / name, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                if header is None:
                    header = line[1:].strip().split("\t")
                continue
            r = line.split("\t")
            if header:
                r += [""] * (len(header) - len(r))
            rows.append(r)
    return rows


def lst(s: str) -> tuple[str, ...]:
    return tuple(x for x in s.split("|") if x) if s else ()
