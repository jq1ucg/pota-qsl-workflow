#!/usr/bin/env python3
"""
polo-merge-adif.py - 複数のADIFファイル(PoLo出力等)を1つのADIFにマージする

Version: 1.0.0

使い方:
    python3 polo-merge-adif.py file1.adi file2.adi ... -o merged.adi
    python3 polo-merge-adif.py *.adi -o merged.adi --dedupe
    python3 polo-merge-adif.py *.adi -o merged.adi -a
    python3 polo-merge-adif.py *.adi -o merged.adi -a -c "三重一斉移動"
    python3 polo-merge-adif.py *.adi -o merged.adi -a -c "三重一斉移動" -qma
    python3 polo-merge-adif.py *.adi -o merged.adi -a -c "三重一斉移動" -qmr

オプション:
    -o, --output   出力ファイル名 (省略時: merged.adi)
    --dedupe       CALL+QSO_DATE+TIME_ON+BAND+MODE が同一のレコードを重複除去
    -a             各ファイルのヘッダ行 "POTA at JP-xxxx 公園名 on YYYY-MM-DD" から
                   "JP-xxxx 公園名" を抽出し、そのファイル内の各レコードに追加する
    -c COMMENT     任意の文字列を各レコードに追加する(-aの後ろに追加)
    -qma           -a/-cの内容をCOMMENTSではなくQSLMSGタグに連結して記入する
    -qmr           -a/-cの内容をCOMMENTSではなくQSLMSGタグに書き換えて記入する(既存値を置換)
    --version      バージョン番号を表示して終了
"""

import argparse
import re
import sys
from pathlib import Path

VERSION = "1.1.0"

EOR_RE = re.compile(r"<eor>", re.IGNORECASE)
EOH_RE = re.compile(r"<eoh>", re.IGNORECASE)
FIELD_RE = re.compile(r"<(\w+):(\d+)(?::[^>]*)?>", re.IGNORECASE)
POTA_HEADER_RE = re.compile(r"POTA at (.+?) on \d{4}-\d{2}-\d{2}")


def extract_pota_info(text: str):
    """ヘッダ行の 'POTA at JP-xxxx 公園名 on YYYY-MM-DD' から 'JP-xxxx 公園名' を抽出"""
    idx = text.upper().find("<EOH>")
    header = text[:idx] if idx != -1 else text
    m = POTA_HEADER_RE.search(header)
    return m.group(1).strip() if m else ""


def parse_records(text: str):
    """ヘッダ部を除いたQSOレコード文字列のリストを返す"""
    m = EOH_RE.search(text)
    body = text[m.end():] if m else text
    records = []
    for chunk in EOR_RE.split(body):
        chunk = chunk.strip()
        if chunk:
            records.append(chunk)
    return records


def record_fields(record: str) -> dict:
    """<TAG:len>value 形式のフィールドを {TAG: value} に変換(キー判定用)"""
    fields = {}
    for match in FIELD_RE.finditer(record):
        tag = match.group(1).upper()
        length = int(match.group(2))
        start = match.end()
        value = record[start:start + length]
        fields[tag] = value
    return fields


def add_field(record: str, tag_name: str, text: str, replace: bool = False) -> str:
    """レコードの指定タグにtextを追加(またはreplace=Trueなら置換)する"""
    if not text:
        return record

    tag_re = re.compile(rf"<{tag_name}:(\d+)(?::[^>]*)?>", re.IGNORECASE)
    m = tag_re.search(record)
    if m:
        byte_length = int(m.group(1))
        start = m.end()
        # ADIFの長さはバイト数なので、バイト単位で値を切り出す
        old_value = record[start:].encode("utf-8")[:byte_length].decode("utf-8")
        end = start + len(old_value)
        new_value = text if replace else f"{old_value} {text}"
        new_tag = f"<{tag_name}:{len(new_value.encode('utf-8'))}>{new_value}"
        return record[:m.start()] + new_tag + record[end:]
    else:
        sep = "" if record.endswith(" ") else " "
        return record + f"{sep}<{tag_name}:{len(text.encode('utf-8'))}>{text} "


def dedupe_key(record: str):
    f = record_fields(record)
    return (
        f.get("CALL", "").upper(),
        f.get("QSO_DATE", ""),
        f.get("TIME_ON", ""),
        f.get("BAND", "").upper(),
        f.get("MODE", "").upper(),
    )


def main():
    ap = argparse.ArgumentParser(description="複数のADIFファイルを1つにマージする")
    ap.add_argument("files", nargs="+", help="入力ADIFファイル(複数指定可)")
    ap.add_argument("-o", "--output", default="merged.adi", help="出力ファイル名")
    ap.add_argument("--dedupe", action="store_true", help="重複QSOを除去する")
    ap.add_argument("-a", action="store_true",
                     help="ヘッダの'POTA at JP-xxxx 公園名'をCOMMENTSタグに追加する")
    ap.add_argument("-c", "--comment", default="",
                     help="任意のコメントを追加する(-aの後ろに挿入)")
    ap.add_argument("-qma", action="store_true",
                     help="-a/-cの内容をQSLMSGタグに連結して記入する(COMMENTSには記入しない)")
    ap.add_argument("-qmr", action="store_true",
                     help="-a/-cの内容をQSLMSGタグに書き換えて記入する(COMMENTSには記入しない)")
    ap.add_argument("--version", action="version", version=f"polo-merge-adif.py {VERSION}")
    args = ap.parse_args()

    if args.qma and args.qmr:
        ap.error("-qma と -qmr は同時に指定できません")

    target_tag = "QSLMSG" if (args.qma or args.qmr) else "COMMENTS"
    replace_mode = args.qmr

    all_records = []
    seen = set()
    total_before = 0
    skipped_files = []

    for fname in args.files:
        path = Path(fname)
        if not path.exists():
            skipped_files.append(fname)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")

        comment_parts = []
        if args.a:
            pota_info = extract_pota_info(text)
            if pota_info:
                comment_parts.append(pota_info)
            else:
                print(f"警告: {fname} のヘッダからPOTA情報を抽出できませんでした", file=sys.stderr)
        if args.comment:
            comment_parts.append(args.comment)
        comment_text = " ".join(comment_parts)

        records = parse_records(text)
        total_before += len(records)
        for rec in records:
            if comment_text:
                rec = add_field(rec, target_tag, comment_text, replace=replace_mode)
            if args.dedupe:
                key = dedupe_key(rec)
                if key in seen:
                    continue
                seen.add(key)
            all_records.append(rec)
        print(f"  読込: {fname} ({len(records)}件)"
              f"{f' [{target_tag}: {comment_text}]' if comment_text else ''}", file=sys.stderr)

    if skipped_files:
        print(f"警告: 見つからないファイルをスキップしました: {skipped_files}", file=sys.stderr)

    header = (
        f"ADIF Export merged by polo-merge-adif.py v{VERSION}\n"
        f"<PROGRAMID:10>merge_adif\n"
        f"<PROGRAMVERSION:{len(VERSION)}>{VERSION}\n"
        "<ADIF_VER:5>3.1.4\n"
        "<EOH>\n\n"
    )

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(header)
        for rec in all_records:
            f.write(rec + "\n<EOR>\n\n")

    dupes = total_before - len(all_records)
    print(f"\n完了: {args.output} に {len(all_records)}件を出力しました"
          f"{f'(重複 {dupes}件を除去)' if args.dedupe else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
