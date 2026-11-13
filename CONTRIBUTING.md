# Contributing

Thank you for helping. arabic-bib is rules over real catalogue strings, so the most valuable contribution is a
**string it gets wrong**.

## Report a wrong result

Open an issue («Wrong result») with the exact input, what arabic-bib returned (`arabic-bib author --json "…"`,
`arabic-bib match "…" "…"`, `arabic-bib date --json "…"`), and what it should return, with a source when it is a
fact (a biographical dictionary, a title page). Please paste text, not screenshots: the bytes matter.

## Add a case, then the fix

1. Add a row to the table in `tests/cases/` that covers your input (`authors.tsv`, `author_pairs.tsv`, `deaths.tsv`,
   `editions.tsv`, `normalize.tsv`, `wasl.tsv`, `audit.tsv`, `compose.tsv`). Tables are tab-separated; lines starting
   with `#` are comments; lists use `|`.
2. Run the tests and see it fail, then change the rule in `src/arabic_bib/` and see every row pass.

```bash
uv venv && uv pip install -e '.[dev]'
.venv/bin/pytest            # under 10 s
.venv/bin/ruff check src tests
```

Write cases yourself or take them from public facts. Do not paste whole catalogues or copyrighted text into the
fixtures.

## Author pairs

`tests/cases/author_pairs.tsv` labels each pair `same`, `different` or `unknown`: the decision a careful cataloguer
makes from the two strings alone. A held-out set from another catalogue (with its licence) is very welcome: it is the
honest measure of the matcher.

## Rules of the code

- Python ≥ 3.10, standard library only at run time.
- `title_key`, `author_key` and `key_norm` are frozen («keys v1»): `tests/test_keys.py` must never change.
- New options are keyword arguments with defaults; exported names keep their signatures.
- Media and benchmarks are made by scripts (`docs/media/make_media.py`, `bench/compare.sh`), never by hand.
