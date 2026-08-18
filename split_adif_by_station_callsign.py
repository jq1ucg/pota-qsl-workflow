#!/usr/bin/env python3
"""
split_adif_by_station_callsign.py

polo-lotw-fill.py 実行後のADIF(MY_STATE/MY_CNTY/JCCJCGAJA付与済み)を、
各レコードの STATION_CALLSIGN タグの値ごとに別ファイルへ分割する。
これにより、LoTW(TQSL)へ STATION_CALLSIGN 単位でアップロードできる。

出力ファイル名:
    YYYYMMDD-STATION_CALLSIGN_lotw.adif
    (YYYYMMDDはスクリプト実行日。STATION_CALLSIGN中の "/" は "-" に置換)
    例: STATION_CALLSIGN "JL1ICY/1" -> 20260818-JL1ICY-1_lotw.adif

STATION_CALLSIGNタグが無い(または空の)レコードは警告を表示してスキップする。
出力先ディレクトリ内の同一局のレコードはQSO_DATE→TIME_ON順にソートする。

使い方:
    python3 split_adif_by_station_callsign.py input.adif
    python3 split_adif_by_station_callsign.py input.adif -o output_dir
    python3 split_adif_by_station_callsign.py a.adif b.adif -o output_dir --dedupe
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

VERSION = "1.0.0"

EOR_RE = re.compile(r"<eor>", re.IGNORECASE)
EOH_RE = re.compile(r"<eoh>", re.IGNORECASE)
FIELD_RE = re.compile(r"<(\w+):(\d+)(?::[^>]*)?>", re.IGNORECASE)


def strip_header(text: str) -> str:
    """<EOH>が存在すればそれより前(ヘッダ部)を除去してレコード部のみ返す。
    <EOH>が無い場合はテキスト全体をそのまま返す。"""
    m = EOH_RE.search(text)
    return text[m.end():] if m else text


def parse_records(text: str):
    """<EOR>区切りのQSOレコード文字列のリストを返す(空要素は除外)"""
    records = []
    for chunk in EOR_RE.split(text):
        chunk = chunk.strip()
        if chunk:
            records.append(chunk)
    return records


def record_fields(record: str) -> dict:
    """<TAG:len>value 形式のフィールドを {TAG: value} に変換する。
    valueはADIFの仕様通りバイト長で切り出す(日本語等マルチバイト対応)。"""
    fields = {}
    for m in FIELD_RE.finditer(record):
        tag = m.group(1).upper()
        byte_len = int(m.group(2))
        start = m.end()
        value = record[start:].encode("utf-8")[:byte_len].decode("utf-8", errors="replace")
        fields[tag] = value
    return fields


def dedupe_key(record: str):
    f = record_fields(record)
    return (
        f.get("CALL", "").upper(),
        f.get("QSO_DATE", ""),
        f.get("TIME_ON", ""),
        f.get("BAND", "").upper(),
        f.get("MODE", "").upper(),
    )


def safe_filename_part(station_callsign: str) -> str:
    """STATION_CALLSIGN値からファイル名に使える文字列を作る("/"を"-"に置換)"""
    return station_callsign.replace("/", "-")


def build_header(station_callsign: str) -> str:
    program_id = "split_adif_by_station_callsign"
    adif_ver = "3.1.4"
    return (
        f"ADIF Export split by {program_id}.py v{VERSION} "
        f"(STATION_CALLSIGN={station_callsign})\n"
        f"<PROGRAMID:{len(program_id)}>{program_id}\n"
        f"<PROGRAMVERSION:{len(VERSION)}>{VERSION}\n"
        f"<ADIF_VER:{len(adif_ver)}>{adif_ver}\n"
        "<EOH>\n\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='+', help='入力ADIFファイル(複数指定可)')
    ap.add_argument('-o', '--output-dir', metavar="DIR", default="output",
                     help='出力先ディレクトリ(省略時: output/。無ければ作成する)')
    ap.add_argument('--dedupe', action='store_true',
                     help='CALL+QSO_DATE+TIME_ON+BAND+MODEが同一のレコードを重複除去')
    ap.add_argument('--version', action='version',
                     version=f'split_adif_by_station_callsign.py {VERSION}')
    args = ap.parse_args()

    sources = []
    for fname in args.input:
        path = Path(fname)
        if not path.exists():
            print(f"[error] ファイルが見つかりません: {fname}", file=sys.stderr)
            sys.exit(1)
        sources.append((fname, path.read_text(encoding='utf-8', errors='replace')))

    by_station = {}
    total_records = 0
    skipped_no_station = 0
    seen = set()
    dupes = 0

    for fname, text in sources:
        body = strip_header(text)
        records = parse_records(body)
        total_records += len(records)

        for rec in records:
            fields = record_fields(rec)
            station = fields.get("STATION_CALLSIGN", "").strip()
            if not station:
                skipped_no_station += 1
                print(f"[warn] STATION_CALLSIGNタグが無いレコードをスキップします "
                      f"({fname}, CALL={fields.get('CALL', '?')}, "
                      f"QSO_DATE={fields.get('QSO_DATE', '?')} "
                      f"TIME_ON={fields.get('TIME_ON', '?')})", file=sys.stderr)
                continue

            if args.dedupe:
                key = (station,) + dedupe_key(rec)
                if key in seen:
                    dupes += 1
                    continue
                seen.add(key)

            by_station.setdefault(station, []).append((fields.get("QSO_DATE", ""),
                                                         fields.get("TIME_ON", ""), rec))

    if not by_station:
        print("[error] 出力対象のレコードがありません(全レコードでSTATION_CALLSIGNが空でした)",
              file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y%m%d")
    written = []
    for station in sorted(by_station):
        records = sorted(by_station[station], key=lambda r: (r[0], r[1]))
        filename = f"{today}-{safe_filename_part(station)}_lotw.adif"
        out_path = out_dir / filename

        content = build_header(station)
        for _, _, rec in records:
            content += rec + " <eor>\n\n"

        out_path.write_text(content, encoding="utf-8")
        written.append((station, filename, len(records)))

    print(f"完了(v{VERSION}): 総レコード数 {total_records} 件 / "
          f"出力 {sum(n for _, _, n in written)} 件 / "
          f"STATION_CALLSIGNなし(スキップ) {skipped_no_station} 件"
          f"{f' / 重複除去 {dupes} 件' if args.dedupe else ''}", file=sys.stderr)
    for station, filename, n in written:
        print(f"  {station}: {n} 件 -> {out_dir / filename}", file=sys.stderr)


if __name__ == "__main__":
    main()
