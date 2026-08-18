#!/usr/bin/env python3
"""
fetch_jarl_noqsl.py

JARL公式サイトの「QSLカード受け取りを希望しない局リスト」
(https://www.jarl.org/Japanese/5_Nyukai/noqsl.html) を取得し、
pivot_qso_for_glabels.py の --exclude-file で読み込める形式の
除外リストファイルを生成する。

個別コールサインに加え、JARLが開設している中央局・地方局・補助局
(JA1RL、JA*RL、JA*YRL 等)もページ末尾の注記に基づき
コールサイン形式で自動的に追加する。

使い方:
    python3 fetch_jarl_noqsl.py -o jarl_noqsl.txt
    python3 fetch_jarl_noqsl.py -o jarl_noqsl.txt --url https://www.jarl.org/...  # URL変更時
    python3 fetch_jarl_noqsl.py  # -o省略時は標準出力へ出力(ステータスは標準エラー出力へ)

変更履歴:
    1.0.2 - -o/--output未指定時は標準出力へ出力するよう変更(ステータスメッセージは
            標準エラー出力へ移動し、リダイレクト時に混入しないようにした)
    1.0.1 - JARL開設局のパターンを正規表現(REGEX:)からコールサイン形式の
            列挙(JA0RL〜JA9RL、JA0YRL〜JA9YRL)に変更
    1.0.0 - 初版
"""

import argparse
import re
import sys
import urllib.request
from pathlib import Path

VERSION = "1.0.2"

DEFAULT_URL = "https://www.jarl.org/Japanese/5_Nyukai/noqsl.html"

CALLSIGN_SPAN_RE = re.compile(r"<span class='callsign'>([^<]*)</span>")
DATE_RE = re.compile(r"<div class='date'>([^<]*)</div>")

# JARL開設局(ページ末尾の注記に基づく。数字0〜9すべてを列挙):
#   中央局: JA1RL
#   地方局: JA0RL, JA2RL〜JA9RL
#   補助局: JA0YRL〜JA9YRL
JARL_BRANCH_CALLSIGNS = (
    [f"JA{n}RL" for n in range(10)]
    + [f"JA{n}YRL" for n in range(10)]
)


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_callsigns(html: str) -> list[str]:
    calls = []
    for m in CALLSIGN_SPAN_RE.finditer(html):
        call = m.group(1).strip()
        # "&nbsp;" などの空白プレースホルダーを除外
        if call and call != "&nbsp;" and re.match(r"^[A-Z0-9]+$", call):
            calls.append(call)
    return calls


def parse_date(html: str) -> str:
    m = DATE_RE.search(html)
    return m.group(1).strip() if m else "不明"


def build_exclude_file_content(calls: list[str], date_str: str, source_url: str) -> str:
    lines = [
        f"# JARL「QSLカード受け取りを希望しない局リスト」({date_str})",
        f"# 取得元: {source_url}",
        f"# fetch_jarl_noqsl.py version {VERSION}",
        "# pivot_qso_for_glabels.py --exclude-file で読み込む除外リスト",
        "#",
        f"# --- 個別コールサイン ({len(calls)}件) ---",
    ]
    lines.extend(calls)
    lines.append("#")
    lines.append(f"# --- JARL開設局 ({len(JARL_BRANCH_CALLSIGNS)}件) ---")
    lines.append("# 中央局(JA1RL)・地方局(JA*RL)・補助局(JA*YRL)")
    lines.extend(JARL_BRANCH_CALLSIGNS)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="JARLのQSLカード受け取り希望しない局リストを取得し除外リストファイルを生成する"
    )
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="出力する除外リストファイルのパス(省略時は標準出力へ出力)")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="取得元URL(デフォルト: JARL公式ページ)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()

    try:
        html = fetch_html(args.url)
    except Exception as e:
        sys.exit(f"エラー: {args.url} の取得に失敗しました: {e}")

    calls = parse_callsigns(html)
    if not calls:
        sys.exit("エラー: ページからコールサインを抽出できませんでした。"
                 "サイトの構造が変更された可能性があります。")

    date_str = parse_date(html)
    content = build_exclude_file_content(calls, date_str, args.url)

    if args.output is None:
        # -o未指定時は標準出力へ出力(パイプ/リダイレクトで使えるよう
        # ステータスメッセージは標準エラー出力に分離する)
        sys.stdout.write(content)
        dest_desc = "標準出力"
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        dest_desc = str(args.output)

    print(f"fetch_jarl_noqsl.py version {VERSION}", file=sys.stderr)
    print(f"取得日時表記: {date_str}", file=sys.stderr)
    print(f"個別コールサイン: {len(calls)}件", file=sys.stderr)
    print(f"JARL開設局: {len(JARL_BRANCH_CALLSIGNS)}件", file=sys.stderr)
    print(f"出力先: {dest_desc}", file=sys.stderr)


if __name__ == "__main__":
    main()
