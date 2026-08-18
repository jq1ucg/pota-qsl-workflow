#!/usr/bin/env python3
"""
pivot_qso_for_glabels.py

glabelsの差し込み印刷(Merge)で1ラベルに複数QSOを印刷するため、
1行1QSOのCSVを「1行=最大N QSO」の横持ち(ワイド)形式に変換する。

入力CSV列: CALL,QSO_DATE,TIME_ON,BAND,MODE,RST_SENT,RST_RCVD,QSO_COMMENT (必須)
           STATION_CALLSIGN,JCCJCGAJA (任意。無ければ空欄として出力する)
  (build_qsl_cards.py の局ごと明細CSV、または全局まとめCSVのどちらでも可)

出力CSV列: CALL1,QSO_DATE1,TIME_ON1,BAND1,MODE1,RST_SENT1,RST_RCVD1,STATION_CALLSIGN1,
           QSO_COMMENT1,JCCJCGAJA1,
           CALL2,QSO_DATE2,... (N組分)
           (-cn/--column-names指定時は、指定したカラム名・順序に番号を付与したものになる)

同一コールサインのQSOをQSO_DATE→TIME_ON順にソートし、N件(デフォルト5)ごとに
1行へまとめる。端数(N件未満)は空文字で埋める。QSO数がNを超える局は、
自動的に複数行(=複数ラベル/複数枚のQSLカード)に分割される。

使い方:
    python3 pivot_qso_for_glabels.py input.csv                       # 単一ファイル、標準出力
    python3 pivot_qso_for_glabels.py input.csv -o output.csv         # 単一ファイル、ファイル出力
    python3 pivot_qso_for_glabels.py a.csv b.csv c.csv -o output.csv # 複数ファイルをマージして処理
    python3 pivot_qso_for_glabels.py ./detail/ -o output.csv         # ディレクトリ内の全*.csvをマージ
    python3 pivot_qso_for_glabels.py ./detail/ -o output.csv -r      # サブディレクトリも再帰的に含める
    python3 pivot_qso_for_glabels.py input.csv --per-label 5
    python3 pivot_qso_for_glabels.py input.csv -cn "CALL,QSO_DATE,TIME_ON,BAND,MODE,RST_SENT,STATION_CALLSIGN,QSO_COMMENT,JCCJCGAJA"

複数ファイル/ディレクトリを指定した場合、全ファイルのQSOを読み込んだ上でコールサイン
正規化(normalize_call)によりグルーピングするため、build_qsl_cards.py側のファイル分割
(例: HL1.csv と JK1MGC.csv が別ファイルになっているケース)をまたいで同一局のQSOを
1つにまとめられる。

CHANGELOG:
    1.22 (2026-08-17) -cn/--column-names オプションを追加。出力(横持ち)のカラム名・
         順序をカンマ区切り文字列で指定できるようにした(番号はプログラム側で自動付与)。
         指定時、入力CSVの必須列チェックも-cnで指定した列名に従う(未指定時は従来通り
         デフォルトの列順・必須列チェック)。
    1.21 (2026-08-17) 入力CSVからSTATION_CALLSIGN・JCCJCGAJA列も取り込むように変更。
         出力(横持ち)の列順は CALL,QSO_DATE,TIME_ON,BAND,MODE,RST_SENT,RST_RCVD,
         STATION_CALLSIGN,QSO_COMMENT,JCCJCGAJA (各N組)。この2列は任意列とし、
         入力CSVに無い場合は空欄として出力する(既存の入力CSVとの後方互換を維持)。
    1.20 (2026-08-11) --exclude-file オプションを追加。fetch_jarl_noqsl.py で
         生成した除外リストファイル(個別コールサイン、および REGEX: プレフィックス
         による正規表現パターン)に一致する局を出力から除外できる。
         正規化コールサイン(normalize_call後)に対して照合する。
    1.12 (2026-08-11) -c/--per-call のファイル一覧表示に、ラベル数に加えて
         局ごとの実QSO数も表示するよう変更(例: JK1MGC.5.csv (6ラベル)(28QSO))。
    1.11 (2026-08-11) -c/--per-call のファイル名を <正規化コールサイン>.csv から
         <正規化コールサイン>.<PER_LABEL>.csv (例: JK1MGC.5.csv) に変更。
    1.10 (2026-08-11) -c/--per-call オプションを追加。-oと排他指定で、
         コールサインごとに個別のCSVファイル(<正規化コールサイン>.csv)を
         出力先ディレクトリ(省略時はカレントディレクトリ)に作成する。
    1.00 (2026-08-11) 初版。以下の機能を含む:
         - 1QSO1行CSV → N QSOごとの横持ち形式への変換
         - QSO_DATE/TIME_ONの表示用フォーマット変換(YYYY/MM/DD, HH:MM)
         - コールサイン正規化によるグルーピング(ポータブルサフィックス
           JG2HPG/2、海外プレフィックス HL1/JK1MGC、米国式1文字接尾語
           HL3/NZ4E に対応)
         - 複数ファイル/ディレクトリ入力によるマージ処理(-r で再帰対応)
         - -o/--output にディレクトリを指定した場合のエラーチェック
"""

__version__ = "1.22"

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_FIELDS = ["CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE", "RST_SENT", "RST_RCVD",
                   "STATION_CALLSIGN", "QSO_COMMENT", "JCCJCGAJA"]

# 入力CSVに必須の列(-cn/--column-names未指定時のデフォルト)。STATION_CALLSIGN/JCCJCGAJAは
# 任意列とし、入力に無い場合は空欄として出力する(古い形式のCSVとの後方互換のため)。
DEFAULT_REQUIRED_FIELDS = ["CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE", "RST_SENT", "RST_RCVD", "QSO_COMMENT"]


def parse_column_names(spec: str) -> list[str]:
    """-cn/--column-names の値("A,B, C"のようなカンマ区切り、前後の空白は無視)を
    列名のリストに変換する。空要素・重複はエラーとする。"""
    names = [n.strip() for n in spec.split(",")]
    names = [n for n in names if n]
    if not names:
        sys.exit("エラー: -cn/--column-namesに列名が指定されていません")
    seen = set()
    dupes = sorted({n for n in names if n in seen or seen.add(n)})
    if dupes:
        sys.exit(f"エラー: -cn/--column-namesに重複した列名があります: {dupes}")
    return names

# 「本来のコールサインらしい形式」判定用: プレフィックス(英字1〜2) + 数字1桁 + 英字1〜4文字
# (国別プレフィックス"HL1"のような「英字+数字」のみ・末尾に英字が無い短い符号とは
#  区別できるよう、末尾の英字を1文字以上に限定している。米国式の1文字接尾語
#  コールサイン(例: NZ4E, K1A)にも対応するため下限は1文字とする)
GENERIC_CALL_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z]{1,4}$")


def format_date(value: str) -> str:
    """QSO_DATE(YYYYMMDD)を YYYY/MM/DD に変換する。形式が合わない場合は元の値をそのまま返す。"""
    v = (value or "").strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[0:4]}/{v[4:6]}/{v[6:8]}"
    return v


def format_time(value: str) -> str:
    """TIME_ON(HHMMSSまたはHHMM)を HH:MM に変換する。形式が合わない場合は元の値をそのまま返す。"""
    v = (value or "").strip()
    if len(v) in (4, 6) and v.isdigit():
        return f"{v[0:2]}:{v[2:4]}"
    return v


def collect_csv_paths(inputs: list[Path], recursive: bool) -> list[Path]:
    """指定された入力(ファイル/ディレクトリの混在可)から、実際に読み込むCSVパスの
    一覧を組み立てる。ディレクトリは *.csv を展開する(recursive指定時はサブディレクトリも)。"""
    paths: list[Path] = []
    for item in inputs:
        if not item.exists():
            sys.exit(f"エラー: 指定されたパスが存在しません: {item}")
        if item.is_dir():
            pattern = "**/*.csv" if recursive else "*.csv"
            found = sorted(item.glob(pattern))
            if not found:
                sys.exit(f"エラー: ディレクトリ内にCSVファイルが見つかりません: {item}")
            paths.extend(found)
        else:
            paths.append(item)
    return paths


def load_rows(input_path: Path, required_fields: list[str]) -> list[dict]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required_fields if c not in reader.fieldnames]
        if missing:
            sys.exit(f"エラー: 入力CSVに必要な列がありません({input_path}): {missing}\n"
                      f"検出された列: {reader.fieldnames}")
        return list(reader)


def load_rows_multi(input_paths: list[Path], required_fields: list[str]) -> list[dict]:
    """複数CSVファイルを読み込み、全行を1つのリストにまとめて返す。"""
    all_rows: list[dict] = []
    for p in input_paths:
        all_rows.extend(load_rows(p, required_fields))
    return all_rows


def normalize_call(call: str) -> str:
    """グルーピング用にコールサインを正規化する。

    '/' を含む場合、以下の2パターンを区別する:
      1. ポータブル運用サフィックス型: JG2HPG/2, JG2HPG/QRP など
         → '/'の前(本来のコールサイン)を採用
      2. 海外プレフィックス付き型: HL1/JK1MGC, VK9/JA1ABC など
         → '/'の後ろ(本来のコールサイン)を採用

    判定は「本来のコールサインらしい形式(プレフィックス+数字+英字2〜4文字)」に
    どちらが一致するかで行う。'/'を含まない場合はそのまま返す。
    表示用の元の値(row中のCALL列そのもの)は変更しない。
    """
    call = call.strip()
    parts = call.split("/")
    if len(parts) == 1:
        return parts[0]

    p0, p1 = parts[0], parts[1]
    p0_is_call = bool(GENERIC_CALL_RE.match(p0))
    p1_is_call = bool(GENERIC_CALL_RE.match(p1))

    if p1_is_call and not p0_is_call:
        # 例: HL1/JK1MGC → JK1MGC (プレフィックス側は本来のコールサイン形式でない)
        return p1
    # 例: JG2HPG/2, JG2HPG/QRP, JK1MGC/HL1 → 先頭側を採用(従来通り)
    return p0


def group_by_call(rows: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        call = (row.get("CALL") or "").strip()
        if call:
            key = normalize_call(call)
            groups[key].append(row)
    return groups


def load_exclude_file(path: Path) -> tuple[set, list]:
    """除外リストファイルを読み込む。

    形式:
      - '#' で始まる行はコメント(無視)
      - 空行は無視
      - 'REGEX:' で始まる行は正規表現パターンとして扱う
      - それ以外は個別コールサイン(大文字小文字を区別せず完全一致)として扱う

    戻り値: (個別コールサインの集合(大文字), コンパイル済み正規表現のリスト)
    """
    if not path.is_file():
        sys.exit(f"エラー: 除外リストファイルが見つかりません: {path}")

    exact_calls = set()
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("REGEX:"):
            pattern_str = line[len("REGEX:"):].strip()
            try:
                patterns.append(re.compile(pattern_str))
            except re.error as e:
                sys.exit(f"エラー: 除外リストファイル内の正規表現が不正です: {pattern_str!r} ({e})")
        else:
            exact_calls.add(line.upper())

    return exact_calls, patterns


def is_excluded(call: str, exact_calls: set, patterns: list) -> bool:
    """正規化済みコールサインが除外リストに一致するか判定する。"""
    upper = call.upper()
    if upper in exact_calls:
        return True
    for pat in patterns:
        if pat.match(upper):
            return True
    return False


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def build_wide_header(per_label: int, fields: list[str]) -> list[str]:
    header = []
    for i in range(1, per_label + 1):
        header.extend(f"{f}{i}" for f in fields)
    return header


def build_wide_row(chunk: list[dict], per_label: int, fields: list[str]) -> dict:
    row = {}
    for i in range(1, per_label + 1):
        if i <= len(chunk):
            src = chunk[i - 1]
            for f in fields:
                value = src.get(f, "")
                if f == "QSO_DATE":
                    value = format_date(value)
                elif f == "TIME_ON":
                    value = format_time(value)
                row[f"{f}{i}"] = value
        else:
            for f in fields:
                row[f"{f}{i}"] = ""
    return row


def sanitize_filename(call: str) -> str:
    """コールサインをファイル名として安全な文字列に変換する
    ('/'などファイル名に使えない文字を'_'に置換)。"""
    return re.sub(r'[\\/:*?"<>|]', "_", call)


def write_per_call_files(groups: dict, per_label: int, sort: bool, outdir: Path,
                          fields: list[str]) -> list[tuple[str, Path, int, int]]:
    """局(正規化後コールサイン)ごとに個別のワイド形式CSVファイルを作成する。
    戻り値: (正規化コールサイン, 出力ファイルパス, ラベル数, QSO数) のリスト。"""
    outdir.mkdir(parents=True, exist_ok=True)
    header = build_wide_header(per_label, fields)
    results = []

    for call in sorted(groups.keys()):
        qsos = groups[call]
        if sort:
            qsos.sort(key=lambda r: (r.get("QSO_DATE", ""), r.get("TIME_ON", "")))

        out_rows = [build_wide_row(chunk, per_label, fields) for chunk in chunked(qsos, per_label)]

        filename = f"{sanitize_filename(call)}.{per_label}.csv"
        out_path = outdir / filename
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(out_rows)

        results.append((call, out_path, len(out_rows), len(qsos)))

    return results


def main():
    parser = argparse.ArgumentParser(description="1QSO1行のCSVをglabels差し込み印刷用の横持ち形式に変換する")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("input", type=Path, nargs="+",
                         help="入力CSV(1行1QSO)。複数ファイル指定可。ディレクトリ指定時は"
                              "*.csvを自動展開してマージする")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("-o", "--output", type=Path, default=None,
                               help="出力CSV(1行=最大N QSO)を1ファイルにまとめて出力。"
                                    "省略時は標準出力に出力。-cとは併用不可")
    output_group.add_argument("-c", "--per-call", type=Path, nargs="?", const=Path("."),
                               metavar="OUTDIR",
                               help="コールサインごとに個別のCSVファイルを作成する"
                                    "(ファイル名は <正規化コールサイン>.csv)。"
                                    "出力先ディレクトリを省略した場合はカレントディレクトリ。"
                                    "-oとは併用不可")
    parser.add_argument("--per-label", type=int, default=5, help="1ラベルあたりのQSO数(デフォルト5)")
    parser.add_argument("-cn", "--column-names", metavar="CSV_COLUMNS", default=None,
                         help="出力(横持ち)のカラム名と順序をカンマ区切りで指定する"
                              "(例: -cn \"CALL,QSO_DATE,TIME_ON,BAND,MODE,RST_SENT,"
                              "STATION_CALLSIGN,QSO_COMMENT,JCCJCGAJA\")。"
                              "各カラム名には1始まりの番号が自動付与される"
                              "(例: CALL -> CALL1,CALL2,...)。"
                              "指定時、入力CSVの必須列チェックもここで指定した列名に従う。"
                              "未指定時のデフォルトは CALL,QSO_DATE,TIME_ON,BAND,MODE,"
                              "RST_SENT,RST_RCVD,STATION_CALLSIGN,QSO_COMMENT,JCCJCGAJA"
                              "(このうちSTATION_CALLSIGN/JCCJCGAJAのみ入力必須列からは除外される)")
    parser.add_argument("--exclude-file", type=Path, default=None,
                         help="除外リストファイル(fetch_jarl_noqsl.py 等で生成)。"
                              "一致した局(正規化コールサイン基準)は出力に含めない")
    parser.add_argument("-r", "--recursive", action="store_true",
                         help="入力にディレクトリを含む場合、サブディレクトリも再帰的に走査する")
    parser.add_argument("--sort", action="store_true", default=True,
                         help="QSO_DATE,TIME_ON順にソートする(デフォルト有効)")
    args = parser.parse_args()

    if args.column_names is not None:
        fields = parse_column_names(args.column_names)
        required_fields = fields
    else:
        fields = DEFAULT_FIELDS
        required_fields = DEFAULT_REQUIRED_FIELDS

    csv_paths = collect_csv_paths(args.input, args.recursive)
    rows = load_rows_multi(csv_paths, required_fields)
    groups = group_by_call(rows)

    excluded_count = 0
    if args.exclude_file is not None:
        exact_calls, patterns = load_exclude_file(args.exclude_file)
        excluded_calls = [call for call in groups if is_excluded(call, exact_calls, patterns)]
        for call in excluded_calls:
            del groups[call]
        excluded_count = len(excluded_calls)

    if args.output is not None and args.output.is_dir():
        sys.exit(f"エラー: -o/--output にはファイルパスを指定してください(ディレクトリが指定されました): {args.output}")

    # -c モード: コールサインごとに個別ファイルを出力
    if args.per_call is not None:
        if args.per_call.exists() and not args.per_call.is_dir():
            sys.exit(f"エラー: -c/--per-call には既存のファイルではなくディレクトリを指定してください: {args.per_call}")

        results = write_per_call_files(groups, args.per_label, args.sort, args.per_call, fields)
        total_labels = sum(n for _, _, n, _ in results)

        print(f"バージョン: {__version__}", file=sys.stdout)
        print(f"入力ファイル数: {len(csv_paths)}", file=sys.stdout)
        if args.exclude_file is not None:
            print(f"除外局数: {excluded_count}  (除外リスト: {args.exclude_file})", file=sys.stdout)
        print(f"局数: {len(groups)}", file=sys.stdout)
        print(f"出力ラベル数(合計): {total_labels}  (1ラベルあたり最大{args.per_label}QSO)", file=sys.stdout)
        print(f"出力先ディレクトリ: {args.per_call}", file=sys.stdout)
        print(f"作成したファイル ({len(results)}件):", file=sys.stdout)
        for call, path, n_labels, n_qsos in results:
            print(f"  {path.name}\t({n_labels}ラベル)({n_qsos}QSO)", file=sys.stdout)
        return

    header = build_wide_header(args.per_label, fields)
    out_rows = []
    label_count = 0

    for call in sorted(groups.keys()):
        qsos = groups[call]
        if args.sort:
            qsos.sort(key=lambda r: (r.get("QSO_DATE", ""), r.get("TIME_ON", "")))
        for chunk in chunked(qsos, args.per_label):
            out_rows.append(build_wide_row(chunk, args.per_label, fields))
            label_count += 1

    if args.output is None:
        # 標準出力へCSVを出力し、ステータスメッセージはstderrへ逃がす
        # (リダイレクトでCSVデータのみをファイルに落とせるようにするため)
        writer = csv.DictWriter(sys.stdout, fieldnames=header)
        writer.writeheader()
        writer.writerows(out_rows)
        out_dest = "標準出力"
        print_target = sys.stderr
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(out_rows)
        out_dest = str(args.output)
        print_target = sys.stdout

    print(f"バージョン: {__version__}", file=print_target)
    print(f"入力ファイル数: {len(csv_paths)}", file=print_target)
    if args.exclude_file is not None:
        print(f"除外局数: {excluded_count}  (除外リスト: {args.exclude_file})", file=print_target)
    print(f"局数: {len(groups)}", file=print_target)
    print(f"出力ラベル数(行数): {label_count}  (1ラベルあたり最大{args.per_label}QSO)", file=print_target)
    print(f"出力先: {out_dest}", file=print_target)


if __name__ == "__main__":
    main()
