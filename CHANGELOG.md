# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org/): the names
exported by `arabic_bib` keep their signatures within a major version, and the catalogue keys (`key_norm`,
`title_key`, `author_key`, «keys v1») never change.

## [0.1.0] - 2026-11-13

### Added
- Normalisation profiles `search`, `display`, `loose` and `NormProfile`; `normalize_mapped` with offsets into the
  original; `search_key`; frozen catalogue keys `key_norm`, `title_key`, `author_key` («keys v1»).
- Author names: `parse_author` (ism, kunya, nasab, laqab, nisba, shuhra, honorifics, death), `AuthorName.forms`,
  `match_authors` with a same / different / unknown verdict and reasons, `same_author`, `author_similarity`,
  `same_person`, `same_publisher`, `publisher_family`.
- Dates: `parse_death` (death words, ranges, two calendars, qualifiers, centuries, years in words), tabular
  Hijri ↔ Gregorian conversion (Julian before 1582), optional Umm al-Qura through `hijridate`, `century_label`.
- Numbers: ordinals (1–99, both genders) and cardinal years in words.
- `parse_edition` for imprint lines and catalogue cards.
- Names: `compose`, `explain`, `volume`, `volumes`, `parse_name`; profiles `warraq`, `plain`, `author-first`.
- Audit: `audit_name`, `audit_tree`, `fix_name`, rename plans (`from/to/reason` TSV), planfs profile export.
- Spelling: hamzat al-wasl check and fix, `safe_filename`.
- CLI `arabic-bib` with `demo`, `audit`, `compose`, `author`, `match`, `date`, `hijri`, `gregorian`, `edition`,
  `normalize`, `wasl`, `safe`, `profiles`.
- pocketshelf entry point `pocketshelf.profiles: warraq`.
- Head-to-head benchmark against PyArabic, CAMeL Tools, Maha and Tashaphyne (`bench/`).
