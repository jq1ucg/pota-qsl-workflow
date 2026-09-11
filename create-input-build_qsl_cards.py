#!/usr/bin/env python3
"""
create-input-build_qsl_cards.py

POTAアプリ(POTA公式ロギングアプリ)からエクスポートしたADIF
(alladif.adif等)を、build_qsl_cards.py がそのまま処理できる形式に
整形する。

対応が必要な理由:
  1. POTAアプリのエクスポートは、アクティベーション(運用)ごとに
     "<ADIF_VER:n>...<PROGRAMID:n>...<PROGRAMVERSION:n>...<EOH>" という
     ヘッダブロックが何度も出現し(ファイル全体で1つではない)、
     しかもその後のレコードが直後に続く(空行が無い場合もある)。
     build_qsl_cards.py の load_records() は最初の<EOH>までしかヘッダ
     として扱わないため、2個目以降のヘッダブロックはレコード本文に
     混入してしまう。本スクリプトはADIF_VER/PROGRAMID/PROGRAMVERSION/
     EOHタグをファイル全体から除去し、単一の正規ヘッダを付与し直す。
  2. POTAアプリのエクスポートは、自局のPOTA運用公園を
     MY_POTA_REF タグではなく MY_SIG(値:POTA)+MY_SIG_INFO(値:JP-XXXX)
     の組で記録する(P2P交信時は相手局の公園がSIG/SIG_INFOに入るが、
     これは自局の公園ではないため無視する)。build_qsl_cards.py は
     MY_POTA_REF タグの値からQSLカードのコメント
     ("MY POTA ACT REF# JP-XXXX")を作るため、MY_SIG=POTAのレコードには
     MY_SIG_INFOの値をそのままMY_POTA_REFタグとして追加する
     (既にMY_POTA_REFタグがあるレコードは変更しない)。
  3. CQRLOGからエクスポートしたADIFが混在している場合、ヘッダ部に
     "ADIF export from CQRLOG ..."、"Copyright (C) 2024 by Petr, OK2CQR
     and Martin, OK1RR"、"Internet: http://www.cqrlog.com" というフリー
     テキストの行や、<CREATED_TIMESTAMP:n>タグが含まれる。これらは
     QSOフィールドではなく、除去しないとレコード本文に混入してしまう
     ため、該当する行(<CREATED_TIMESTAMP:n>タグは値ごと)を除去する。

各レコードのフィールド値そのもの(MY_POTA_REF追加以外)は変更しない
(パススルー)。

使い方:
    python3 create-input-build_qsl_cards.py alladif.adif -o input_for_build_qsl_cards.adif
    python3 create-input-build_qsl_cards.py alladif.adif | python3 build_qsl_cards.py -
    python3 create-input-build_qsl_cards.py a.adif b.adif -o merged.adif --dedupe

オプション:
    input                  入力ADIFファイル(複数指定可)
    -o, --output PATH      出力先ファイルパス(省略時は標準出力)
    --sig-field NAME        自局アワード種別のタグ名 (default: my_sig)
    --sig-info-field NAME   自局アワード参照番号のタグ名 (default: my_sig_info)
    --sig-value VALUE       POTAを表すsig-fieldの値 (default: POTA。大文字小文字区別なし)
    --pota-field NAME       付与先タグ名 (default: my_pota_ref)
    -f, --force             既にpota-fieldがあるレコードも上書きする(省略時はスキップ)
    --dedupe                CALL+QSO_DATE+TIME_ON+BAND+MODEが同一のレコードを重複除去
    --version               バージョン番号を表示して終了

変更履歴:
    1.1.0  CQRLOGエクスポートのフリーテキスト行("ADIF export from
           CQRLOG ..."、Copyright表記、"Internet: http://www.cqrlog.com")
           と<CREATED_TIMESTAMP>タグの除去に対応。
    1.0.0  初版。ADIF_VER/PROGRAMID/PROGRAMVERSION/EOHの埋め込みヘッダ
           除去と、MY_SIG=POTAレコードへのMY_POTA_REF付与に対応。
"""

import argparse
import re
import sys
from pathlib import Path

VERSION = "1.1.0"

EOR_RE = re.compile(r"<eor>", re.IGNORECASE)
FIELD_RE = re.compile(r"<(\w+):(\d+)(?::[^>]*)?>", re.IGNORECASE)
HEADER_TAGS = ("ADIF_VER", "PROGRAMID", "PROGRAMVERSION", "CREATED_TIMESTAMP")
NOISE_LINE_SUBSTRINGS = (
    "ADIF export from CQRLOG",
    "Copyright (C) 2024 by Petr, OK2CQR and Martin, OK1RR",
    "Internet: http://www.cqrlog.com",
)


def remove_field(text: str, tag: str) -> str:
    """指定タグのフィールドを(値ごと)テキスト全体から除去する(全出現箇所)。
    値はASCII前提でバイト長=文字数として扱う
    (ADIF_VER/PROGRAMID/PROGRAMVERSIONはいずれもASCII値のため問題ない)。"""
    pattern = re.compile(rf"<{re.escape(tag)}:(\d+)(?::[^>]*)?>", re.IGNORECASE)
    out = text
    while True:
        m = pattern.search(out)
        if not m:
            break
        val_end = m.end() + int(m.group(1))
        out = out[:m.start()] + out[val_end:]
    return out


def strip_noise_lines(text: str) -> str:
    """CQRLOGエクスポートのヘッダに含まれるフリーテキスト行
    (NOISE_LINE_SUBSTRINGSのいずれかを含む行)を除去する。"""
    lines = text.splitlines(keepends=True)
    return "".join(ln for ln in lines if not any(s in ln for s in NOISE_LINE_SUBSTRINGS))


def strip_embedded_headers(text: str) -> str:
    """ファイル全体からADIF_VER/PROGRAMID/PROGRAMVERSION/CREATED_TIMESTAMP/
    EOHタグと、CQRLOGのフリーテキストヘッダ行を除去し、QSOレコードの
    フィールドのみを残す(ヘッダブロックが複数埋め込まれていても、
    出現位置に関わらずすべて除去する)。"""
    out = strip_noise_lines(text)
    for tag in HEADER_TAGS:
        out = remove_field(out, tag)
    out = re.sub(r"<eoh>", "", out, flags=re.IGNORECASE)
    return out


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
    return f"<{tag.lower()}:{len(value.encode('utf-8'))}>{value}"


def build_header() -> str:
    program_id = "create-input-build_qsl_cards"
    adif_ver = "3.1.4"
    return (
        f"ADIF Export converted by {program_id}.py v{VERSION}\n"
        f"<PROGRAMID:{len(program_id)}>{program_id}\n"
        f"<PROGRAMVERSION:{len(VERSION)}>{VERSION}\n"
        f"<ADIF_VER:{len(adif_ver)}>{adif_ver}\n"
        "<EOH>\n\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='+', help='入力ADIFファイル(複数指定可)')
    ap.add_argument('-o', '--output', metavar="PATH", help='出力先ファイルパス(省略時は標準出力)')
    ap.add_argument('--sig-field', default='my_sig', metavar='NAME',
                     help='自局アワード種別のタグ名 (default: my_sig)')
    ap.add_argument('--sig-info-field', default='my_sig_info', metavar='NAME',
                     help='自局アワード参照番号のタグ名 (default: my_sig_info)')
    ap.add_argument('--sig-value', default='POTA', metavar='VALUE',
                     help='POTAを表すsig-fieldの値 (default: POTA。大文字小文字区別なし)')
    ap.add_argument('--pota-field', default='my_pota_ref', metavar='NAME',
                     help='付与先タグ名 (default: my_pota_ref)')
    ap.add_argument('-f', '--force', action='store_true',
                     help='既にpota-fieldがあるレコードも上書きする(省略時はスキップ)')
    ap.add_argument('--dedupe', action='store_true',
                     help='CALL+QSO_DATE+TIME_ON+BAND+MODEが同一のレコードを重複除去')
    ap.add_argument('--version', action='version',
                     version=f'create-input-build_qsl_cards.py {VERSION}')
    args = ap.parse_args()

    sig_tag = args.sig_field.upper()
    sig_info_tag = args.sig_info_field.upper()
    pota_tag = args.pota_field.upper()
    sig_value = args.sig_value.strip().upper()

    sources = []
    for fname in args.input:
        path = Path(fname)
        if not path.exists():
            print(f"[error] ファイルが見つかりません: {fname}", file=sys.stderr)
            sys.exit(1)
        sources.append((fname, path.read_text(encoding='utf-8', errors='replace')))

    all_records = []
    seen = set()
    total_before = 0
    added = 0
    already_present = 0
    overwritten = 0
    no_sig = 0

    for fname, text in sources:
        body = strip_embedded_headers(text)
        records = parse_records(body)
        total_before += len(records)

        kept_this_file = 0
        for rec in records:
            fields = record_fields(rec)
            has_pota = pota_tag in fields and fields[pota_tag].strip()

            if has_pota and not args.force:
                already_present += 1
            elif fields.get(sig_tag, "").strip().upper() == sig_value and fields.get(sig_info_tag, "").strip():
                if has_pota:
                    overwritten += 1
                    rec = remove_field(rec, pota_tag)
                else:
                    added += 1
                rec = rec + " " + build_field(pota_tag, fields[sig_info_tag].strip())
            elif not has_pota:
                no_sig += 1

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
          f"{f' (重複除去 {dupes} 件)' if args.dedupe else ''}", file=sys.stderr)
    print(f"  {args.pota_field}: 追加 {added} 件 / 上書き {overwritten} 件 / "
          f"既存のためスキップ {already_present} 件 / "
          f"{args.sig_field}={args.sig_value}でないため付与せず {no_sig} 件", file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[info] 出力ファイルに書き込み完了: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
