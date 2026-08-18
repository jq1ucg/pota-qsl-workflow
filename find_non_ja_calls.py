#!/usr/bin/env python3
"""
find_non_ja_calls.py

指定ディレクトリ内のファイル名から、日本(JA)のアマチュア無線コールサイン
パターンに当てはまらないものを抽出する。

JAコールサインの想定パターン:
    プレフィックス: JA-JS (1文字目J、2文字目A-S) または 7J-7N, 8J-8N
    + 数字1桁(地域番号 0-9)
    + サフィックス英字 1〜4文字
    例: JA1ABC, JQ1UCG, JG2HPG, 7K4XYZ, 8N1ABC

ファイル名側の許容要素:
    - 拡張子(.csv, .adif 等)は無視して判定
    - ポータブル運用サフィックス "/数字" (例: JG2HPG_2 → JG2HPG/2 相当)を許容
      ※ファイル名には "/" を使えないため "_" 区切りを想定
    - build_qsl_cards.py / pivot_qso_for_glabels.py が生成する
      "_5" のような末尾の「1ラベルあたりQSO数」を表すサフィックスは
      コールサイン本体ではないため、判定前に除去する

使い方:
    python3 find_non_ja_calls.py /path/to/directory            # JA以外を抽出(デフォルト)
    python3 find_non_ja_calls.py /path/to/directory --ext csv
    python3 find_non_ja_calls.py /path/to/directory -ja         # JAのみを抽出(反転)
    python3 find_non_ja_calls.py /path/to/directory --japan-only --ext csv
    python3 find_non_ja_calls.py /path/to/directory -c          # コールサインのみ表示(コンパクト)
    python3 find_non_ja_calls.py /path/to/directory -ja -c      # JAのみ・コールサインのみ表示
    python3 find_non_ja_calls.py --test          # 自己検証テストのみ実行
    python3 find_non_ja_calls.py --version

CHANGELOG:
    1.0.0 (2026-08-11) 初版としてバージョン管理を導入。
         -c/--compact オプションを追加(判定文字列=コールサインのみを1行1件で表示)。
"""

__version__ = "1.0.0"

import argparse
import re
import sys
from pathlib import Path

# JAプレフィックス: J[A-S] または 7[J-N] または 8[J-N]
JA_PREFIX_RE = r"(?:J[A-S]|7[J-N]|8[J-N])"

# コールサイン本体: プレフィックス + 数字1桁 + 英字1〜4文字
JA_CALL_CORE_RE = rf"{JA_PREFIX_RE}[0-9][A-Z]{{1,4}}"

# ポータブルサフィックス(/数字、または "_数字" をポータブル表記とみなす場合)は任意
JA_CALL_FULL_RE = re.compile(rf"^{JA_CALL_CORE_RE}(?:/[0-9])?$")

# build_qsl_cards.py / pivot_qso_for_glabels.py 由来の
# 「1ラベルあたりQSO数」を表す末尾サフィックス (例: _5, _10, .5, .10)
LABEL_COUNT_SUFFIX_RE = re.compile(r"[_.](\d+)$")


def strip_label_count_suffix(stem: str) -> str:
    """ファイル名(拡張子なし)末尾の '_数字' または '.数字'(1ラベルあたりQSO数サフィックス)
    を除去する。ポータブル運用の '_数字'(例: JG2HPG_2 → JG2HPG/2)との区別はできないため、
    このスクリプトでは「1ラベルあたりQSO数」由来のサフィックスのみを対象とし、
    ポータブルサフィックスは判定時に別途 '/' 表記として許容する(下記 normalize 参照)。
    """
    m = LABEL_COUNT_SUFFIX_RE.search(stem)
    if m:
        return stem[: m.start()]
    return stem


def is_ja_callsign(call: str) -> bool:
    """文字列がJAコールサインパターンに一致するか判定する。大文字小文字は区別しない。"""
    return bool(JA_CALL_FULL_RE.match(call.upper()))


def extract_candidate(filename: str) -> str:
    """ファイル名からコールサイン候補文字列を抽出する(拡張子・ラベル数サフィックス除去)。"""
    stem = Path(filename).stem
    stem = strip_label_count_suffix(stem)
    return stem


def find_files(directory: Path, ext: str | None = None, japan_only: bool = False) -> list[tuple[str, str]]:
    """ディレクトリ内のファイルを走査し、判定結果に応じたファイルの
    (ファイル名, 判定に使った候補文字列) のリストを返す。

    japan_only=False(デフォルト): JAコールサインパターンに一致しないファイルを抽出
    japan_only=True            : JAコールサインパターンに一致するファイルのみを抽出
    """
    results = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if ext and path.suffix.lstrip(".").lower() != ext.lstrip(".").lower():
            continue
        candidate = extract_candidate(path.name)
        matched = is_ja_callsign(candidate)
        if matched == japan_only:
            results.append((path.name, candidate))
    return results


def find_non_ja_files(directory: Path, ext: str | None = None) -> list[tuple[str, str]]:
    """後方互換用ラッパー: JAコールサインパターンに一致しないファイルを抽出する。"""
    return find_files(directory, ext=ext, japan_only=False)


# ---------------------------------------------------------------------------
# 自己検証テスト
# ---------------------------------------------------------------------------

def run_self_tests() -> None:
    # 1. is_ja_callsign() の正例・否定例
    valid_calls = [
        "JA1ABC", "JG2HPG", "JQ1UCG", "JS3XYZ", "JR6ABC",
        "7K4XYZ", "7J1AAA", "8N1ABC", "8J1RL",
        "ja1abc",           # 小文字も許容
        "JG2HPG/2",         # ポータブルサフィックス付き
    ]
    invalid_calls = [
        "ZL1TQM",    # ニュージーランド
        "K1ABC",     # 米国(プレフィックスK)
        "W1AW",      # 米国
        "VK2ABC",    # オーストラリア
        "JT1ABC",    # モンゴル(Jで始まるがJAレンジ外: J[T-Z]は非該当)
        "JA1",       # サフィックス無し(不完全)
        "J1ABC",     # 数字プレフィックス欠落
        "9J1AAA",    # 9J(ザンビア、8/7以外)
        "",          # 空文字
        "JG2HPG_5",  # ラベル数サフィックスを除去せずに渡した場合は不一致になるべき
    ]

    failures = []
    for c in valid_calls:
        if not is_ja_callsign(c):
            failures.append(f"FAIL(valid想定なのに不一致): {c!r}")
    for c in invalid_calls:
        if is_ja_callsign(c):
            failures.append(f"FAIL(invalid想定なのに一致): {c!r}")

    # 2. extract_candidate() のファイル名処理
    cases = [
        ("JG2HPG.csv", "JG2HPG"),
        ("JG2HPG_5.csv", "JG2HPG"),          # ラベル数サフィックス除去(アンダースコア)
        ("JG2HPG.5.csv", "JG2HPG"),          # ラベル数サフィックス除去(ドット)
        ("JG2HPG_10.adif", "JG2HPG"),
        ("JG2HPG.10.csv", "JG2HPG"),
        ("ZL1TQM.csv", "ZL1TQM"),
        ("qsl_cards.csv", "qsl_cards"),      # サマリファイル名(数字サフィックス無し)
    ]
    for filename, expected in cases:
        got = extract_candidate(filename)
        if got != expected:
            failures.append(f"FAIL(extract_candidate): {filename!r} -> {got!r} (期待値 {expected!r})")

    # 3. find_non_ja_files() の統合テスト(一時ディレクトリを使用)
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        names = [
            "JG2HPG.csv", "JG2HPG_5.csv", "JQ1UCG.csv",
            "ZL1TQM.csv", "K1ABC.csv", "qsl_cards.csv", "notes.txt",
        ]
        for n in names:
            (tmp / n).write_text("dummy", encoding="utf-8")

        non_ja = {name for name, _ in find_non_ja_files(tmp)}
        expected_non_ja = {"ZL1TQM.csv", "K1ABC.csv", "qsl_cards.csv", "notes.txt"}
        if non_ja != expected_non_ja:
            failures.append(
                f"FAIL(find_non_ja_files): got={sorted(non_ja)} expected={sorted(expected_non_ja)}"
            )

        non_ja_csv_only = {name for name, _ in find_files(tmp, ext="csv")}
        expected_csv_only = {"ZL1TQM.csv", "K1ABC.csv", "qsl_cards.csv"}
        if non_ja_csv_only != expected_csv_only:
            failures.append(
                f"FAIL(find_files --ext csv): got={sorted(non_ja_csv_only)} "
                f"expected={sorted(expected_csv_only)}"
            )

        # japan_only=True: JAに一致するファイルのみ抽出
        ja_only = {name for name, _ in find_files(tmp, japan_only=True)}
        expected_ja_only = {"JG2HPG.csv", "JG2HPG_5.csv", "JQ1UCG.csv"}
        if ja_only != expected_ja_only:
            failures.append(
                f"FAIL(find_files japan_only=True): got={sorted(ja_only)} "
                f"expected={sorted(expected_ja_only)}"
            )

        ja_only_csv = {name for name, _ in find_files(tmp, ext="csv", japan_only=True)}
        if ja_only_csv != expected_ja_only:
            failures.append(
                f"FAIL(find_files japan_only=True --ext csv): got={sorted(ja_only_csv)} "
                f"expected={sorted(expected_ja_only)}"
            )

    if failures:
        print("自己検証テスト: 失敗", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        sys.exit(1)
    else:
        total = len(valid_calls) + len(invalid_calls) + len(cases) + 4
        print(f"自己検証テスト: 全{total}件 成功")


def main():
    parser = argparse.ArgumentParser(
        description="ディレクトリ内のファイル名をJA(日本)コールサインパターンで抽出する"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("directory", type=Path, nargs="?", help="走査対象ディレクトリ")
    parser.add_argument("--ext", type=str, default=None, help="対象拡張子を限定する(例: csv)")
    parser.add_argument("-ja", "--japan-only", action="store_true",
                         help="JAコールサインパターンに一致するファイルのみを抽出する"
                              "(指定しない場合は従来通り、一致しないファイルを抽出)")
    parser.add_argument("-c", "--compact", action="store_true",
                         help="コールサイン(判定文字列)のみを1行1件で表示する"
                              "(ファイル名やヘッダー行は表示しない)")
    parser.add_argument("--test", action="store_true", help="自己検証テストのみ実行して終了する")
    args = parser.parse_args()

    if args.test or args.directory is None:
        run_self_tests()
        if args.directory is None:
            return

    if not args.directory.is_dir():
        sys.exit(f"エラー: ディレクトリが存在しません: {args.directory}")

    results = find_files(args.directory, ext=args.ext, japan_only=args.japan_only)

    if args.compact:
        for _, candidate in results:
            print(candidate)
        return

    label = "JAコールサインパターンに一致する" if args.japan_only else "JAコールサインパターンに一致しない"

    if not results:
        print(f"{label}ファイルはありませんでした。")
        return

    print(f"{label}ファイル ({len(results)}件):")
    for filename, candidate in results:
        print(f"  {filename}\t(判定文字列: {candidate!r})")


if __name__ == "__main__":
    main()
