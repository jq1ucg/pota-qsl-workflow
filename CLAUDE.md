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
12. **`smarthamlog_lotw_upload.py`** (v1.7.0) — Takes **Smart HAMLOG** ADIF
    exports, normalizes them for LoTW (reuses `polo-lotw-fill.py` functions),
    splits by `STATION_CALLSIGN`, and signs/uploads via the **TQSL CLI**.
    Dry-run by default; `--sign-only` makes `.tq8`, `--upload` uploads.
    See "LoTW / TQSL knowledge" below before changing it.
    User guide (Japanese): `README-smarthamlog-lotw.md`.

## LoTW / TQSL knowledge (learned in practice, TQSL 2.8.6)

Verified on the user's machine (`~/pota-parks/bin/` script, `~/pota-parks/data/POTA-REF.csv`):
- Working command (all 329 QSOs of 2026-11-07..09 uploaded, exit 0):
  `python3 smarthamlog_lotw_upload.py -p POTA-REF.csv *.adi -o output --upload`
  (add `--action all` if TQSL reports "以前に署名されたQSO").
- Station Locations in TQSL are `POTA-0AREA`, `POTA-1AREA`, `POTA-2AREA`
  (chosen from the `/n` suffix of `STATION_CALLSIGN`); base `JQ1UCG` is separate.
- TQSL `config.xml` (`/usr/local/share/TrustedQSL/config.xml`): `JA_PREFECTURE` is a
  2-digit code (09=Nagano, 10=Tokyo, 16=Gunma); `JA_CITY_GUN_KU` values are
  **plain codes under each prefecture** (`0908`, `09015`, `100120`, `1611`).
  => ADIF must be `MY_STATE=09` and `MY_CNTY=0908` (NO `09,` prefix).
  `MY_CNTY=09,0908` (US-style "ST,county", still emitted by `polo-lotw-fill.py`)
  makes TQSL stop with "'US County State' の値として '09' ... 正しくありません".
  That script was NOT changed; use `--cnty-format plain` (default) in the
  smarthamlog script, and re-check `polo-lotw-fill.py` before trusting it.
- The station location's fixed JCC differs per park, so TQSL must be run with
  `-f update` (ADIF MY_STATE/MY_CNTY override the location); otherwise it stops with
  "局の所在地は QSO データの詳細と一致していない". Default in the script.
- TQSL processes newest QSO first, so the error "line N" is always the last record;
  it is not specific to that record.
- `--sign-only` marks QSOs as signed in TQSL's duplicate DB; a later `--upload`
  then exits 8 ("No QSOs to upload"). Use `--upload` directly, or `--action all`.
  (Alternative: upload the saved `.tq8` via the LoTW web page / TQSL GUI.)
- TQSL exit codes: 0 ok, 8 nothing to sign (all dup/out of range, or error), 9 partial.
- `MODE=DIGITALVOICE` + `SUBMODE=DSTAR` is accepted by TQSL 2.8.6 (kept by default;
  `--dv-mode dstar|fm` exist as fallbacks). How LoTW classifies D-STAR (PHONE/DATA)
  is NOT verified.
- The script reads TQSL's `config.xml` to pre-check (MY_STATE, MY_CNTY) pairs.

Smart HAMLOG ADIF quirks: park ref is in `MY_SIG_INFO` (not `MY_POTA_REF`);
`FREQ` can be malformed (`7.005.5` -> fixed to `7.0055`); times are UTC;
other station's park is in `SIG_INFO`; no `MY_STATE`/`MY_CNTY`.

`POTA-REF.csv` (tracked in this repo; the user's live copy is elsewhere):
the area column is the JARL area of the *operation* (`/0`, `/1`); the same park
can have one row per area (e.g. JP-0012: area 0 = JP-NN JCC0908, area 1 = JP-GM
JCC1611) and the script picks the row by the `/n` suffix. User-supplied JCC/JCG
values override auto-geocoded ones; a trailing letter in JCG codes (e.g. `09015C`)
is NOT kept in `POTA-REF.csv`.

Environment notes: the cloud sandbox cannot reach `lotw.arrl.org` (host not
allowed), so TQSL/LoTW behavior cannot be checked there; ask the user to run
commands on their own machine and paste logs. `pycache` from importing
`polo-lotw-fill.py` should not be committed.

## Repository
- GitHub: https://github.com/jq1ucg/pota-qsl-workflow
- Owner: jq1ucg
