#!/usr/bin/env python3
"""
sort_pivot_list.py

pivot_qso_for_glabels.py -c 実行時の標準出力(以下のような行を含むテキスト)を
読み込み、ファイルごとの「ラベル数」「QSO数」を抽出して、ラベル数の多い順
→ 同数の場合はQSO数の多い順、でソートして表示する。

対象行の形式(pivot_qso_for_glabels.py の -c モード出力):
    UA0L.5.csv    (1ラベル)(1QSO)
    UA9MA.5.csv   (1ラベル)(1QSO)
    VK4FW.5.csv   (1ラベル)(3QSO)
    ZL1TQM.5.csv  (1ラベル)(1QSO)

使い方:
    python3 sort_pivot_list.py output.list.txt
    python3 sort_pivot_list.py output.list.txt --by qso        # QSO数優先でソート
    python3 sort_pivot_list.py output.list.txt --top 20        # 上位20件のみ表示
    python3 pivot_qso_for_glabels.py ... -c OUTDIR | python3 sort_pivot_list.py -   # パイプ入力
"""

import argparse
import re
import sys
from pathlib import Path

# 例: "  JK1MGC.5.csv\t(6ラベル)(30QSO)" または空白区切りにも対応
LINE_RE = re.compile(
    r"^\s*(?P<filename>\S+\.csv)\s+\((?P<labels>\d+)ラベル\)\((?P<qsos>\d+)QSO\)\s*$"
)


def parse_lines(text: str) -> list[dict]:
    """テキストから該当行を抽出し、[{'filename':..., 'labels':int, 'qsos':int}, ...] を返す。"""
    results = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if m:
            results.append({
                "filename": m.group("filename"),
                "labels": int(m.group("labels")),
                "qsos": int(m.group("qsos")),
            })
    return results


def sort_entries(entries: list[dict], by: str) -> list[dict]:
    if by == "qso":
        key = lambda e: (e["qsos"], e["labels"])
    else:  # "label" (デフォルト)
        key = lambda e: (e["labels"], e["qsos"])
    return sorted(entries, key=key, reverse=True)


def main():
    parser = argparse.ArgumentParser(
        description="pivot_qso_for_glabels.py -c の出力リストをラベル数・QSO数の多い順にソートする"
    )
    parser.add_argument("input", type=str, help="output.list.txt のパス。'-' で標準入力から読む")
    parser.add_argument("--by", choices=["label", "qso"], default="label",
                         help="ソート優先キー。label=ラベル数優先(デフォルト), qso=QSO数優先")
    parser.add_argument("--top", type=int, default=None, help="上位N件のみ表示")
    args = parser.parse_args()

    if args.input == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            sys.exit(f"エラー: ファイルが見つかりません: {path}")
        text = path.read_text(encoding="utf-8")

    entries = parse_lines(text)
    if not entries:
        sys.exit("エラー: '(Nラベル)(MQSO)' 形式の行が見つかりませんでした。"
                 "pivot_qso_for_glabels.py -c の出力を渡してください。")

    sorted_entries = sort_entries(entries, args.by)
    if args.top is not None:
        sorted_entries = sorted_entries[: args.top]

    name_width = max(len(e["filename"]) for e in sorted_entries)
    for e in sorted_entries:
        print(f"  {e['filename']:<{name_width}}  ({e['labels']}ラベル)({e['qsos']}QSO)")

    print(f"\n合計 {len(entries)} 件中 {len(sorted_entries)} 件を表示"
          f"(ソート基準: {'ラベル数優先' if args.by == 'label' else 'QSO数優先'})", file=sys.stderr)


if __name__ == "__main__":
    main()
