#!/usr/bin/env python3
"""
rumlogng-merge-adif.py

RUMLogNG からエクスポートしたADIFを、polo-lotw-fill.py が読み込める
形式(正規のADIFヘッダ+<EOR>区切りレコード)に変換する。

背景:
  RUMLogNG のエクスポートは PoLo と異なり、
    - ファイル全体を通じて有効な <EOH> ヘッダを持たない場合がある
      (レコードがいきなり <call:...> から始まる)
    - MY_POTA_REF タグは各QSOレコードに既に個別で埋め込まれている
      (PoLoのようにファイル単位/ヘッダ単位でのPOTA情報抽出は不要)
  そのため polo-merge-adif.py の "-a" (ヘッダからPOTA情報を抽出して
  COMMENTに追加する)処理は不要で、本スクリプトは
    1) レコードを正しく読み取り(バイト長ベースでフィールド値を解析)
    2) 複数ファイルの結合・重複除去
    3) 標準的なADIFヘッダ(<EOH>付き)を付与
  を行い、polo-lotw-fill.py にそのまま渡せる出力を作る。
  各レコードのフィールド値そのものは変更しない(パススルー)。

使い方:
  python3 rumlogng-merge-adif.py input.adi -o converted.adi
  cat input.adi | python3 rumlogng-merge-adif.py > converted.adi
  python3 rumlogng-merge-adif.py day1.adi day2.adi -o converted.adi --dedupe

  # そのままpolo-lotw-fill.pyへパイプする例
  python3 rumlogng-merge-adif.py input.adi | python3 polo-lotw-fill.py -p POTA-REF.csv -o output.adi

オプション:
  input                 入力ADIFファイル(複数指定可・省略時は標準入力)
  -o, --output          出力先ファイルパス(省略時は標準出力)
  --dedupe              CALL+QSO_DATE+TIME_ON+BAND+MODE が同一のレコードを重複除去
  --pota-field NAME      検証対象のPOTAタグ名 (default: my_pota_ref)
                        (タグ有無の集計・警告表示にのみ使用。値の変更は行わない)
  -s, --station-callsign CALLSIGN
                        全レコードにSTATION_CALLSIGNタグを付与
                        (既存タグがある場合は-f指定時のみ上書き。
                        -f未指定時は既存タグがあればスキップし、無ければ付与)
                        例: -s "JL1ICY/3"
  -sc, --state-cnty STATE,AJACODE
                        全レコードにMY_STATE/MY_CNTY/JCCJCGAJAタグを付与
                        (既存タグがある場合は-f指定時のみ上書き。
                        タグごとに個別判定: 例えばMY_STATEのみ既存で
                        MY_CNTYが無い場合、-f無しでもMY_CNTYのみ付与される)
                        STATEは都道府県番号、AJACODEはJCC/JCG/AJAコード
                        (例: AJA100108)。
                        MY_STATE=STATE, MY_CNTY=STATE,AJACODEの数字部分,
                        JCCJCGAJA=AJACODEそのまま
                        例: -sc 10,AJA100108
                          -> MY_STATE=10 / MY_CNTY=10,100108 / JCCJCGAJA=AJA100108
  -f, --force            -s/-scで付与するタグが既存の場合に上書きする
                        (省略時は既存タグがあればそのフィールドはスキップする。
                        -s/-sc以外の処理には影響しない)
  --version              バージョン番号を表示して終了

変更履歴:
  1.0.0  初版。RUMLogNGエクスポート(ヘッダ無し/MY_POTA_REF埋め込み済み)を
         polo-lotw-fill.py互換の正規ADIF(ヘッダ+<EOR>区切り)に変換。
  1.1.0  -s/--station-callsign、-sc/--state-cntyオプションを追加。
         全レコードにSTATION_CALLSIGN、MY_STATE/MY_CNTY/JCCJCGAJAタグを
         付与できるようにした(既存タグがあれば上書き)。
  1.2.0  -f/--forceオプションを追加。-s/-scによる上書きは-f指定時のみとし、
         -f未指定時は既存タグがあるフィールドはスキップするよう変更
         (タグ単位で判定)。
  1.3.0  -s/-scで付与したタグの追加件数・上書き件数・スキップ件数をタグ別に
         標準エラー出力へ表示するようにした。
  1.4.0  -s/-scで付与するタグ(STATION_CALLSIGN/MY_STATE/MY_CNTY/JCCJCGAJA)
         をレコード内で改行区切りではなくスペース区切りにし、各QSOレコードが
         <EOR>まで1行に収まるよう修正(後続スクリプトが1行単位でしか
         パースできないケースに対応)。
  1.5.0  -s/-scで付与するタグを行頭ではなく既存フィールドの末尾に追加する
         よう変更。タグ名もRUMLogNGエクスポートの慣習に合わせ小文字で出力
         (<eor>タグも小文字化)。
"""

import argparse
import re
import sys
from pathlib import Path

VERSION = "1.5.0"

EOR_RE = re.compile(r"<eor>", re.IGNORECASE)
EOH_RE = re.compile(r"<eoh>", re.IGNORECASE)
FIELD_RE = re.compile(r"<(\w+):(\d+)(?::[^>]*)?>", re.IGNORECASE)


def strip_header(text: str) -> str:
    """<EOH>が存在すればそれより前(ヘッダ部)を除去してレコード部のみ返す。
    <EOH>が無い場合(RUMLogNGの典型)はテキスト全体をそのまま返す。"""
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


def build_field(tag: str, value: str) -> str:
    """<tag:バイト長>値 形式の1フィールド文字列を作る(タグは小文字。
    RUMLogNGエクスポートの慣習(小文字タグ)に合わせる)"""
    return f"<{tag.lower()}:{len(value.encode('utf-8'))}>{value}"


def remove_field(record: str, tag: str) -> str:
    """指定タグのフィールドを(値ごと)レコードから除去する。
    STATION_CALLSIGN/MY_STATE/MY_CNTY/JCCJCGAJAはASCII値のみを想定し、
    バイト長=文字数として扱う。"""
    pattern = re.compile(rf"<{re.escape(tag)}:(\d+)(?::[^>]*)?>", re.IGNORECASE)
    out = record
    while True:
        m = pattern.search(out)
        if not m:
            break
        val_end = m.end() + int(m.group(1))
        out = out[:m.start()] + out[val_end:]
    return out


def set_field(record: str, tag: str, value: str, existing_fields: dict, force: bool, counts: dict) -> str:
    """タグを付与する。既にrecordにtagが存在する場合、forceがFalseならスキップして
    そのまま返し、forceがTrueなら除去したうえで新しい値のタグを先頭に付与する。
    存在しない場合は常に先頭に付与する。countsにタグごとの追加/上書き/スキップ件数を積算する。"""
    tag_u = tag.upper()
    c = counts.setdefault(tag_u, {"added": 0, "overwritten": 0, "skipped": 0})
    if tag_u in existing_fields:
        if not force:
            c["skipped"] += 1
            return record
        c["overwritten"] += 1
    else:
        c["added"] += 1
    record = remove_field(record, tag)
    return record + " " + build_field(tag, value)


def parse_state_cnty(raw: str):
    """"STATE,AJACODE" 形式の -sc 引数を解析し、
    (my_state, my_cnty, jccjcgaja) のタプルを返す。
    例: "10,AJA100108" -> ("10", "10,100108", "AJA100108")"""
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        print(f"[error] -sc/--state-cnty の形式が不正です(STATE,AJACODEの形式で指定してください): {raw}",
              file=sys.stderr)
        sys.exit(1)
    state, ajacode = parts
    code_digits = re.sub(r"^[A-Za-z]+", "", ajacode)
    my_state = state
    my_cnty = f"{state},{code_digits}"
    return my_state, my_cnty, ajacode


def build_header() -> str:
    program_id = "rumlogng-merge-adif"
    adif_ver = "3.1.4"
    return (
        f"ADIF Export converted by rumlogng-merge-adif.py v{VERSION}\n"
        f"<PROGRAMID:{len(program_id)}>{program_id}\n"
        f"<PROGRAMVERSION:{len(VERSION)}>{VERSION}\n"
        f"<ADIF_VER:{len(adif_ver)}>{adif_ver}\n"
        "<EOH>\n\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='*', help='入力ADIFファイル(複数指定可・省略時は標準入力)')
    ap.add_argument('-o', '--output', metavar="PATH", help='出力先ファイルパス(省略時は標準出力)')
    ap.add_argument('--dedupe', action='store_true',
                     help='CALL+QSO_DATE+TIME_ON+BAND+MODEが同一のレコードを重複除去')
    ap.add_argument('--pota-field', default='my_pota_ref',
                     help='検証対象のPOTAタグ名 (default: my_pota_ref)')
    ap.add_argument('-s', '--station-callsign', metavar='CALLSIGN',
                     help='全レコードにSTATION_CALLSIGNタグを付与(既存タグは上書き)。例: -s "JL1ICY/3"')
    ap.add_argument('-sc', '--state-cnty', metavar='STATE,AJACODE',
                     help='全レコードにMY_STATE/MY_CNTY/JCCJCGAJAタグを付与(既存タグは-f指定時のみ上書き)。'
                          '例: -sc 10,AJA100108 -> MY_STATE=10 / MY_CNTY=10,100108 / JCCJCGAJA=AJA100108')
    ap.add_argument('-f', '--force', action='store_true',
                     help='-s/-scで付与するタグが既存の場合に上書きする(省略時はスキップ)')
    ap.add_argument('--version', action='version', version=f'rumlogng-merge-adif.py {VERSION}')
    args = ap.parse_args()

    pota_tag = args.pota_field.upper()

    my_state = my_cnty = jccjcgaja = None
    if args.state_cnty:
        my_state, my_cnty, jccjcgaja = parse_state_cnty(args.state_cnty)

    tag_counts = {}

    all_records = []
    seen = set()
    total_before = 0

    if args.input:
        sources = []
        for fname in args.input:
            path = Path(fname)
            if not path.exists():
                print(f"[error] ファイルが見つかりません: {fname}", file=sys.stderr)
                sys.exit(1)
            sources.append((fname, path.read_text(encoding='utf-8', errors='replace')))
    else:
        sources = [("<stdin>", sys.stdin.read())]

    has_pota = 0
    no_pota = 0

    for fname, text in sources:
        body = strip_header(text)
        records = parse_records(body)
        total_before += len(records)

        kept_this_file = 0
        for rec in records:
            fields = record_fields(rec)
            if pota_tag in fields and fields[pota_tag].strip():
                has_pota += 1
            else:
                no_pota += 1

            if args.station_callsign:
                rec = set_field(rec, 'STATION_CALLSIGN', args.station_callsign, fields, args.force, tag_counts)
            if args.state_cnty:
                rec = set_field(rec, 'MY_STATE', my_state, fields, args.force, tag_counts)
                rec = set_field(rec, 'MY_CNTY', my_cnty, fields, args.force, tag_counts)
                rec = set_field(rec, 'JCCJCGAJA', jccjcgaja, fields, args.force, tag_counts)

            if args.dedupe:
                key = dedupe_key(rec)
                if key in seen:
                    continue
                seen.add(key)

            all_records.append(rec)
            kept_this_file += 1

        print(f"  読込: {fname} ({len(records)}件 / 採用{kept_this_file}件)", file=sys.stderr)

    result = build_header()
    for rec in all_records:
        result += rec + " <eor>\n\n"

    dupes = total_before - len(all_records)
    print(f"完了(v{VERSION}): 総レコード数 {total_before} 件 / 出力 {len(all_records)} 件"
          f"{f' (重複除去 {dupes} 件)' if args.dedupe else ''} / "
          f"{args.pota_field}あり {has_pota} 件 / {args.pota_field}なし {no_pota} 件",
          file=sys.stderr)

    if tag_counts:
        tag_order = []
        if args.station_callsign:
            tag_order.append('STATION_CALLSIGN')
        if args.state_cnty:
            tag_order += ['MY_STATE', 'MY_CNTY', 'JCCJCGAJA']

        for tag in tag_order:
            c = tag_counts.get(tag, {"added": 0, "overwritten": 0, "skipped": 0})
            print(f"  {tag}: 追加 {c['added']} 件 / 上書き {c['overwritten']} 件"
                  f" / スキップ(既存のため) {c['skipped']} 件", file=sys.stderr)

        total_added = sum(tag_counts[t]["added"] for t in tag_order)
        total_overwritten = sum(tag_counts[t]["overwritten"] for t in tag_order)
        total_skipped = sum(tag_counts[t]["skipped"] for t in tag_order)
        print(f"タグ付与合計: 追加 {total_added} 件 / 上書き {total_overwritten} 件"
              f" / スキップ {total_skipped} 件"
              f"{'' if args.force else ' (-f未指定のため既存タグは上書きせずスキップ)'}",
              file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[info] 出力ファイルに書き込み完了: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
