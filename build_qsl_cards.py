#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QSLカード印刷用スクリプト

1. 入力ADIFファイルを読み込む
2. 局コールサインをプライマリーキーとしてuniqする
   - ポータブルサフィックス型: JQ1UCG / JQ1UCG/1 / JQ1UCG/2 は "/" 以降を
     無視して同一局とみなす
   - 海外プレフィックス付き型: HL1/JK1MGC, HL3/AK1A のような
     "国別プレフィックス/本来のコールサイン" 形式は、本来のコールサイン側
     (JK1MGC, AK1A)を局の代表キーとしてuniqする
3. 局ごとにADIFファイルを作成する(Commentsは元ファイルの値をそのまま引用)
4. glabelsでの差し込み印刷用にCSVも作成できる
   - output/qsl_cards.csv       : 局ごとに1行の全局サマリCSV
   - output/detail/<CALL>.csv   : 局ごとに1交信1行の明細CSV
   いずれもQSO_COMMENT列には、ADIFのmy_pota_refフィールドの値から
   "MY POTA ACT REF# JP-XXXX" (全て大文字) を入れる(my_pota_refが無いQSOは空欄)
5. 画面表示した内容は、以下のファイルにも同時出力する
   - output/ADIF-Summary-YYYYMMDD-HHMM.txt  (--adif実行時)
   - output/CSV-Summary-YYYYMMDD-HHMM.txt   (--csv実行時)

出力先: output/ ディレクトリ

使い方:
  python3 build_qsl_cards.py 入力.adif            # ADIF・CSV両方を作成
  python3 build_qsl_cards.py 入力.adif --adif      # 局ごとADIFファイルのみ作成
  python3 build_qsl_cards.py 入力.adif --csv       # CSV(サマリ+明細)のみ作成

CHANGELOG:
    1.01 (2026-08-16) ADIFフィールド値の切り出しを文字数ベースから
         バイト数(UTF-8)ベースに修正。日本語などマルチバイト文字を
         含むフィールド(例: COMMENT)があると、文字数ベースのスライスでは
         後続フィールドまで巻き込んで誤読するバグを修正
         ([[polo_build_qsl_cards.py]]開発時に発覚)。
    1.00 (2026-08-11) 初版としてバージョン管理を導入。base_call()を拡張し、
         海外プレフィックス付き型(HL1/JK1MGC, HL3/AK1A等)を正しく
         本来のコールサイン側でグルーピングするよう改修
         (pivot_qso_for_glabels.py の normalize_call() と同じロジック)。
"""

__version__ = "1.01"

import argparse
import csv
import os
import re
from collections import defaultdict
from datetime import datetime

TAG_RE_BYTES = re.compile(rb"<(\w+):(\d+)(?::[^>]*)?>")
EOH_RE = re.compile(r"<eoh>", re.IGNORECASE)
EOR_RE = re.compile(r"<eor>", re.IGNORECASE)


def pota_comment(fields):
    """my_pota_refフィールドの値から "MY POTA ACT REF# JP-XXXX" (全て大文字) を返す。無ければ空文字"""
    ref = fields.get("my_pota_ref", "").strip()
    return f"My POTA Act Ref# {ref}".upper() if ref else ""


def pota_ref_without_comment_mark(fields):
    """my_pota_refはあるが、Comment欄に"JP-"の記載が無いQSOかどうかを判定する"""
    ref = fields.get("my_pota_ref", "").strip()
    if not ref:
        return False
    comment = fields.get("comment", "")
    return "JP-" not in comment.upper()


def load_records(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        data = f.read()

    m = EOH_RE.search(data)
    if m:
        header = data[: m.end()]
        body = data[m.end():]
    else:
        header = "<EOH>"
        body = data

    records = [r.strip() for r in EOR_RE.split(body) if r.strip()]
    return header, records


def parse_fields(record):
    """1レコード文字列からADIFフィールドを{フィールド名(小文字): 値}の辞書に変換

    ADIFの長さ指定はバイト数(UTF-8)であり、Pythonの文字数とは一致しない
    (日本語などのマルチバイト文字を含む場合にずれる)。そのため、いったん
    UTF-8バイト列に変換してからバイト単位でスライスする。
    """
    data = record.encode("utf-8")
    fields = {}
    for m in TAG_RE_BYTES.finditer(data):
        name = m.group(1).decode("ascii").lower()
        length = int(m.group(2))
        start = m.end()
        value = data[start:start + length].decode("utf-8", errors="replace")
        fields[name] = value
    return fields


# 「本来のコールサインらしい形式」判定用: プレフィックス(英字1〜2) + 数字1桁 + 英字1〜4文字
# (国別プレフィックス"HL1"のような「英字+数字」のみ・末尾に英字が無い短い符号とは
#  区別できるよう、末尾の英字を1文字以上に限定している。米国式の1文字接尾語
#  コールサイン(例: NZ4E, K1A)にも対応するため下限は1文字とする)
GENERIC_CALL_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z]{1,4}$")


def base_call(call):
    """局グルーピング用のプライマリーコールサインを返す。

    '/' を含む場合、以下の2パターンを区別する:
      1. ポータブル運用サフィックス型: JQ1UCG/1, JQ1UCG/2, JQ1UCG/QRP など
         → '/'の前(本来のコールサイン)を採用
      2. 海外プレフィックス付き型: HL1/JK1MGC, HL3/AK1A など
         → '/'の後ろ(本来のコールサイン)を採用

    判定は「本来のコールサインらしい形式(プレフィックス+数字+英字1〜4文字)」に
    どちらが一致するかで行う。'/'を含まない場合はそのまま返す。
    """
    call = call.strip().upper()
    parts = call.split("/")
    if len(parts) == 1:
        return parts[0]

    p0, p1 = parts[0], parts[1]
    p0_is_call = bool(GENERIC_CALL_RE.match(p0))
    p1_is_call = bool(GENERIC_CALL_RE.match(p1))

    if p1_is_call and not p0_is_call:
        # 例: HL1/JK1MGC → JK1MGC (プレフィックス側は本来のコールサイン形式でない)
        return p1
    # 例: JQ1UCG/1, JQ1UCG/QRP, JK1MGC/HL1 → 先頭側を採用(従来通り)
    return p0


def sort_qso_key(entry):
    fields = entry["fields"]
    return (fields.get("qso_date", ""), fields.get("time_on", ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("input", help="入力ADIFファイル")
    parser.add_argument("-o", "--outdir", default="output", help="出力先ディレクトリ (既定値: output)")
    parser.add_argument("--adif", action="store_true", help="局ごとのADIFファイルを作成する")
    parser.add_argument("--csv", action="store_true", help="glabels用CSVファイルを作成する")
    args = parser.parse_args()

    # どちらのオプションも指定されなければ両方作成する
    do_adif = args.adif or not (args.adif or args.csv)
    do_csv = args.csv or not (args.adif or args.csv)

    header, records = load_records(args.input)
    os.makedirs(args.outdir, exist_ok=True)

    groups = defaultdict(list)  # base_call -> [{"raw": record, "fields": {...}}, ...]
    for r in records:
        fields = parse_fields(r)
        call = fields.get("call", "")
        if not call:
            continue
        key = base_call(call)
        groups[key].append({"raw": r, "fields": fields})

    adif_log = []
    csv_log = []

    def log_both(text):
        print(text)
        adif_log.append(text)
        csv_log.append(text)

    def log_adif(text):
        print(text)
        adif_log.append(text)

    def log_csv(text):
        print(text)
        csv_log.append(text)

    log_both(f"バージョン: {__version__}")
    log_both(f"総QSO数: {len(records)}")
    log_both(f"局数(uniq): {len(groups)}")
    log_both(f"出力先: {os.path.abspath(args.outdir)}")
    log_both("-" * 60)

    for call in sorted(groups.keys()):
        entries = sorted(groups[call], key=sort_qso_key)

        if do_adif:
            outpath = os.path.join(args.outdir, f"{call}.adif")
            with open(outpath, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(header + "\n\n")
                for e in entries:
                    f.write(e["raw"] + " <eor>\n")
            log_adif(f"{call:12s} {len(entries):4d}件 -> {call}.adif")

        if do_csv:
            missing_dates = [
                e["fields"].get("qso_date", "")
                for e in entries
                if pota_ref_without_comment_mark(e["fields"])
            ]
            line = f"{call:12s} {len(entries):4d}件"
            if missing_dates:
                line += "  #POTA番号なし：" + "/".join(missing_dates)
            log_csv(line)

    if do_csv:
        csv_path = os.path.join(args.outdir, "qsl_cards.csv")
        detail_dir = os.path.join(args.outdir, "detail")
        os.makedirs(detail_dir, exist_ok=True)

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "CALL", "QSO_COUNT", "FIRST_DATE", "LAST_DATE",
                "BANDS", "MODES", "RST", "NAME", "QTH", "GRIDSQUARE",
                "QSO_DETAIL", "QSO_COMMENT",
            ])
            for call in sorted(groups.keys()):
                entries = sorted(groups[call], key=sort_qso_key)
                fset = [e["fields"] for e in entries]

                dates = [f.get("qso_date", "") for f in fset if f.get("qso_date")]
                bands = sorted({f.get("band", "") for f in fset if f.get("band")})
                modes = sorted({f.get("mode", "") for f in fset if f.get("mode")})
                rsts = sorted({f.get("rst_sent", "") for f in fset if f.get("rst_sent")})
                name = next((f.get("name", "") for f in fset if f.get("name")), "")
                qth = next((f.get("qth", "") for f in fset if f.get("qth")), "")
                grid = next((f.get("gridsquare", "") for f in fset if f.get("gridsquare")), "")

                detail_lines = []
                comment_lines = []
                for f in fset:
                    d = f.get("qso_date", "")
                    d_fmt = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
                    t = f.get("time_on", "")
                    t_fmt = f"{t[0:2]}:{t[2:4]}" if len(t) >= 4 else t
                    detail_lines.append(
                        f"{d_fmt} {t_fmt} {f.get('band', '')} {f.get('mode', '')} "
                        f"{f.get('rst_sent', '')}/{f.get('rst_rcvd', '')}"
                    )
                    comment_lines.append(pota_comment(f))

                writer.writerow([
                    call,
                    len(entries),
                    min(dates) if dates else "",
                    max(dates) if dates else "",
                    ",".join(bands),
                    ",".join(modes),
                    ",".join(rsts),
                    name,
                    qth,
                    grid,
                    "\n".join(detail_lines),
                    "\n".join(comment_lines),
                ])

                # 局ごとの明細CSV(1交信1行)
                detail_path = os.path.join(detail_dir, f"{call}.csv")
                with open(detail_path, "w", encoding="utf-8", newline="") as df:
                    dwriter = csv.writer(df)
                    dwriter.writerow([
                        "CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE",
                        "RST_SENT", "RST_RCVD", "QSO_COMMENT",
                    ])
                    for f in fset:
                        dwriter.writerow([
                            f.get("call", ""),
                            f.get("qso_date", ""),
                            f.get("time_on", ""),
                            f.get("band", ""),
                            f.get("mode", ""),
                            f.get("rst_sent", ""),
                            f.get("rst_rcvd", ""),
                            pota_comment(f),
                        ])

        log_csv("-" * 60)
        log_csv(f"サマリCSV作成: {csv_path}")
        log_csv(f"明細CSV作成: {detail_dir}/ ({len(groups)}ファイル)")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    if do_adif:
        adif_summary_path = os.path.join(args.outdir, f"ADIF-Summary-{timestamp}.txt")
        with open(adif_summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(adif_log) + "\n")
        print(f"サマリ出力: {adif_summary_path}")
    if do_csv:
        csv_summary_path = os.path.join(args.outdir, f"CSV-Summary-{timestamp}.txt")
        with open(csv_summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(csv_log) + "\n")
        print(f"サマリ出力: {csv_summary_path}")


if __name__ == "__main__":
    main()
