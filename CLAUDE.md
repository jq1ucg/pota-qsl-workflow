# pota-qsl-workflow

## Overview
Command-line tooling for the QSL-card workflow of **Parks On The Air (POTA)**
activations from Japan, bridging **PoLo** (POTA Logger) and **RUMLogNG**
ADIF exports through to print-ready QSL card data (glabels mail-merge CSV)
and LoTW upload files. All scripts are standalone Python 3 CLI programs
(argparse-based); there is no shared package/module structure or build
system. Comments and CLI help text are in Japanese.

## Status
Early-stage personal tooling — the repository holds a set of independent
scripts, no tests, no packaging (no `requirements.txt`/`pyproject.toml` yet).
Update this file as structure, dependencies, and conventions solidify.

## Conventions
- Each script keeps its own `VERSION` constant, starting at `1.0.0`, with a
  `変更履歴:` (changelog) section in its module docstring listing what
  changed at each version, plus an `オプション:` section documenting each
  CLI flag. Bump the version and add a changelog entry whenever a script's
  behavior or options change — see `rumlogng-merge-adif.py` or
  `split_adif_by_station_callsign.py` for the pattern to follow.

## Scripts (pipeline order)

1. **`rumlogng-merge-adif.py`** — Normalizes RUMLogNG ADIF exports (which
   lack a standard `<EOH>` header and may start mid-record) into standard
   ADIF, merges multiple files, and can dedupe records.
2. **`polo-merge-adif.py`** — Merges multiple PoLo ADIF exports into one
   file; can extract the POTA park ref/name from each file's header comment
   and stamp it into every record's `COMMENT`/`QSLMSG`, with dedupe support.
3. **`build_pota_ref_csv.py`** (+ `.orig` backup) — Scans ADIF files for
   `STATION_CALLSIGN` (JARL area number) and `MY_POTA_REF` (park ref, e.g.
   `JP-1181`) pairs and incrementally updates `POTA-REF.csv`. Looks up new
   parks via the `api.pota.app/program/parks/JP` API and resolves
   municipality / JCC/JCG/AJA numbers via GSI reverse-geocoding + Geolonia
   address data + the JARL JCC/JCG/AJA list.
4. **`polo-lotw-fill.py`** — Cross-references `MY_POTA_REF` against
   `POTA-REF.csv` to fill in `MY_STATE`, `MY_CNTY`, and a JCC/JCG/AJA tag,
   producing ADIF ready for LoTW/TQSL upload.
5. **`split_adif_by_station_callsign.py`** — Splits a `polo-lotw-fill.py`
   output ADIF into one file per `STATION_CALLSIGN` value (e.g. `JL1ICY/1`,
   `JL1ICY/2`), named `YYYYMMDD-STATION_CALLSIGN_lotw.adif` (run date, `/`
   replaced with `-`), so each portable-suffix station can be uploaded to
   LoTW/TQSL separately.
6. **`build_qsl_cards.py`** / **`polo_build_qsl_cards.py`** — Split a merged
   ADIF into one ADIF + CSV per contacted station (dedupes portable
   suffixes like `JQ1UCG/1` and DX-prefixed calls like `HL1/JK1MGC`),
   producing `output/qsl_cards.csv` (one row per station) and
   `output/detail/<CALL>.csv` (one row per QSO) for glabels mail merge.
   The `polo_` variant consumes `polo-lotw-fill.py` output specifically.
7. **`check_jarl_membership.py`** — Looks up callsigns on the JARL member
   search site via Selenium (parallel headless Chrome) to find non-members
   (QSL not forwardable); also absorbs `fetch_jarl_noqsl.py`'s job via `-f`.
8. **`fetch_jarl_noqsl.py`** — Fetches JARL's official "no QSL wanted"
   station list and formats it for `pivot_qso_for_glabels.py --exclude-file`.
9. **`pivot_qso_for_glabels.py`** — Pivots one-row-per-QSO CSVs into wide
   rows (N QSOs per label, default 5) for glabels mail-merge printing;
   supports merging multiple input files/directories and excluding
   callsigns via a list file.
10. **`sort_pivot_list.py`** — Sorts the summary listing printed by
    `pivot_qso_for_glabels.py -c` by label count / QSO count.
11. **`find_non_ja_calls.py`** — Utility to find generated filenames whose
    callsign doesn't match a JA amateur radio prefix pattern.

## Repository
- GitHub: https://github.com/jq1ucg/pota-qsl-workflow
- Owner: jq1ucg
