#!/usr/bin/env python3
"""
polo-lotw-fill.py

ADIFの各レコードの MY_POTA_REF タグを POTA-REF.csv と突合し、
LoTW(TQSL)アップロード用に MY_STATE / MY_CNTY を追加する。
また、JCC/JCG/AJAタグ(--jarl-fieldで指定、default: jccjcgaja)が
まだ付与されていなければ、同じ突合結果からその値も付与する。
(MY_GRIDSQUAREのジオコーディング処理は行わない)

  MY_STATE   : POTA-REF.csvの該当行「JCC/JCG/AJA」列の数字部分の先頭2桁
               例: JCC2103 -> "21"
  MY_CNTY    : "<MY_STATE>,<JCC/JCG/AJAの数字部分全体>"
               例: JCC2105 -> "21,2105"
  jccjcgaja  : POTA-REF.csvの該当行「JCC/JCG/AJA」列の値をそのまま付与
               例: JCC2105 -> "JCC2105"
               (該当行にJCC/JCG/AJA情報が無い(空欄)場合は付与しない)

対応表:
  --potatable / -p  POTA-REF.csv (必須)
      列: JARLエリア番号,公園REF番号,JP都道府県名,都道府県名+市区/郡名,JCC/JCG/AJA

複数県にまたがる公園REF(同じ公園REF番号に複数行、例: JP-0209)の場合の
候補選択は add_station_jcc.py と同じ方式:
  1) COMMENTタグ中の "(JP-XX)"/"（JP-XX）" 表記の県マーカーで一致する行
  2) -c/--choice で指定された行番号(公園REFがCSV内で何番目に出現するか、1始まり)
  3) どちらも無ければ先頭候補行を使用し、警告を出す

使い方:
  python3 polo-lotw-fill.py -p POTA-REF.csv input.adi > output.adi
  cat input.adi | python3 polo-lotw-fill.py -p POTA-REF.csv > output.adi
  python3 polo-lotw-fill.py -p POTA-REF.csv -c JP-0209:1,JP-0101:2 input.adi -o output.adi

オプション:
  input                入力ADIFファイル(省略時は標準入力)
  -p, --potatable      POTA-REF.csv のパス (必須)
  -o, --output         出力先ファイルパス(省略時は標準出力)
  --pota-field NAME    POTA参照用ADIFタグ名 (default: my_pota_ref)
  --jarl-field NAME    JCC/JCG/AJA用ADIFタグ名 (default: jccjcgaja)
  -c, --choice SPEC    複数県にまたがる公園REFのフォールバック選択行
                       (例: JP-0209:1,JP-0101:2)
  -lc, --list-choices  -pのCSVを読み込み、複数県にまたがる公園REFの選択肢一覧を
                       表示して終了する(ADIFは処理しない)
  --overwrite          既存のMY_STATE/MY_CNTY/JCC・JCG・AJAタグも上書きする
                       (未指定時は既存フィールドがあればスキップ)
  --version            バージョン番号を表示して終了

変更履歴:
  1.2.0  --jarl-field(default: jccjcgaja)タグが無い場合に、POTA-REF.csvの
         JCC/JCG/AJA列の値をそのまま付与する処理を追加。--overwrite指定時は
         既存タグも上書き対象に含める。該当行にJCC/JCG/AJA情報が無い場合は
         付与せず警告を出す。
  1.1.0  -lc/--list-choicesオプションを追加。複数県にまたがる公園REFの
         選択肢一覧(行番号 -> 公園REF,都道府県,市区/郡,JCC/JCG/AJA)を
         表示してADIF処理を行わずに終了できるようにした。
  1.0.0  初版。MY_POTA_REFタグ突合によるMY_STATE/MY_CNTY付与
         (MY_GRIDSQUAREのジオコーディングはpolo-lotw-fill.pyの対象外)
"""

import argparse
import csv
import re
import sys

VERSION = "1.2.0"

MY_POTA_REF_TAG_RE_TMPL = r"<{field}:(\d+)(?::[A-Za-z]+)?>"
JARL_TAG_RE_TMPL = r"<{field}:\d+(?::[A-Za-z]+)?>"
COMMENT_RE = re.compile(r"<comment(?:s)?:(\d+)(?::[A-Za-z]+)?>", re.IGNORECASE)
MY_STATE_TAG_RE = re.compile(r"<my_state:\d+(?::[A-Za-z]+)?>", re.IGNORECASE)
MY_CNTY_TAG_RE = re.compile(r"<my_cnty:\d+(?::[A-Za-z]+)?>", re.IGNORECASE)
PREF_MARKER_RE = re.compile(r"[\(（]([A-Za-z]{2}-[A-Za-z]{2})[\)）]")
CODE_RE = re.compile(r'^[A-Za-z]+(\d+)$')
EOH_RE = re.compile(r"<eoh>", re.IGNORECASE)


def load_potatable(path):
    """公園REF番号 -> [{"area":.., "pref_col":.., "muni_col":.., "jarl":..}, ...] の辞書。
    県境をまたぐ公園は同じ公園REF番号に複数行(出現順)が存在する。"""
    table = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = ['JARLエリア番号', '公園REF番号', 'JP都道府県名', '都道府県名+市区/郡名', 'JCC/JCG/AJA']
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            sys.exit(f"エラー: POTA-REF.csvに列がありません: {missing}\n実際の列名: {reader.fieldnames}")
        for row in reader:
            park = row['公園REF番号'].strip()
            entry = {
                "area": row['JARLエリア番号'].strip(),
                "pref_col": row['JP都道府県名'].strip(),
                "muni_col": row['都道府県名+市区/郡名'].strip(),
                "jarl": row['JCC/JCG/AJA'].strip(),
            }
            table.setdefault(park, []).append(entry)
    return table


def digits_only(code):
    m = CODE_RE.match(code)
    return m.group(1) if m else re.sub(r'\D', '', code)


def format_ref_entry_csv_line(park, entry):
    return f"{entry['area']},{park},{entry['pref_col']},{entry['muni_col']},{entry['jarl']}"


def parse_choice_spec(spec):
    """"JP-0209:1,JP-0101:2" -> {"JP-0209": 1, "JP-0101": 2} (1始まり)"""
    choices = {}
    if not spec:
        return choices
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"-c/--choiceの形式が不正です(公園REF:行番号): '{part}'")
        park, idx_str = part.split(":", 1)
        park = park.strip().upper()
        try:
            idx = int(idx_str.strip())
        except ValueError:
            raise ValueError(f"-c/--choiceの行番号が数値ではありません: '{part}'")
        if idx < 1:
            raise ValueError(f"-c/--choiceの行番号は1以上で指定してください: '{part}'")
        choices[park] = idx
    return choices


def describe_choices(choices, ref_table):
    lines = []
    for park, idx in choices.items():
        candidates = ref_table.get(park)
        if not candidates:
            lines.append(f"[warn] -c/--choice指定: {{'{park}': {idx}}} は、"
                          f"POTA-REF.csvに公園REF {park} が見つからないため無効です")
            continue
        if not (1 <= idx <= len(candidates)):
            lines.append(f"[warn] -c/--choice指定: {{'{park}': {idx}}} は、"
                          f"候補数({len(candidates)})の範囲外のため無効です")
            continue
        csv_line = format_ref_entry_csv_line(park, candidates[idx - 1])
        lines.append(f"[info] -c/--choice指定: {{'{park}': {idx}}} は、{csv_line} を使用")
    return lines


def select_ref_entry(park, candidates, comment, choices, qso_label, warnings):
    """優先順位: 1) COMMENT中の"(JP-XX)"表記  2) -c/--choice  3) 先頭候補行(警告)"""
    if len(candidates) == 1:
        return candidates[0]

    m = PREF_MARKER_RE.search(comment)
    if m:
        marker = m.group(1).upper()
        for c in candidates:
            if c["pref_col"].upper().startswith(marker):
                return c
        warnings.append(f"[warn] {qso_label}: COMMENT中の県マーカー({marker})が候補行と一致しません")

    if park in choices:
        idx = choices[park]
        if 1 <= idx <= len(candidates):
            return candidates[idx - 1]
        warnings.append(
            f"[warn] {qso_label}: -c/--choiceで指定された行番号{idx}が候補数({len(candidates)})の範囲外のため、先頭候補を使用")
        return candidates[0]

    warnings.append(
        f"[warn] {qso_label}: 複数県にまたがる公園でCOMMENTに県マーカーが無く、"
        f"-c/--choiceの指定も無いため、先頭候補を使用")
    return candidates[0]


def list_ambiguous_parks(ref_table):
    """同一公園REF番号で複数候補(複数県)が存在するものを "行番号 -> 公園REF,都道府県,市区/郡,JCC/JCG/AJA" 形式で列挙する"""
    lines = []
    for park in sorted(ref_table.keys()):
        candidates = ref_table[park]
        if len(candidates) <= 1:
            continue
        lines.append(f"{park}:")
        for idx, entry in enumerate(candidates, 1):
            lines.append(f"  {idx} -> {park},{entry['pref_col']},{entry['muni_col']},{entry['jarl']}")
    return lines


def split_header_and_body(adif_text):
    m = EOH_RE.search(adif_text)
    if m:
        return adif_text[:m.end()], adif_text[m.end():]
    return "", adif_text


def append_adif_field(record_text, field_name, value):
    tag = f"<{field_name}:{len(value.encode('utf-8'))}>{value}"
    stripped = record_text.rstrip(" \n")
    return f"{stripped} {tag} "


def replace_or_append_field(record_text, field_name, value, existing_tag_re):
    """既存タグがあれば値を置換、無ければ末尾に新規追加する"""
    m = existing_tag_re.search(record_text)
    if m:
        byte_length = int(re.match(r"<\w+:(\d+)", m.group(0)).group(1))
        start = m.end()
        end = start + len(record_text[start:].encode("utf-8")[:byte_length].decode("utf-8", errors="replace"))
        new_tag = f"<{field_name}:{len(value.encode('utf-8'))}>{value}"
        return record_text[:m.start()] + new_tag + " " + record_text[end:]
    return append_adif_field(record_text, field_name, value)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='?', help='入力ADIFファイル(省略時は標準入力)')
    ap.add_argument('-p', '--potatable', required=True, help='POTA-REF.csv のパス')
    ap.add_argument('-o', '--output', metavar="PATH", help='出力先ファイルパス(省略時は標準出力)')
    ap.add_argument('--pota-field', default='my_pota_ref', help='POTA参照用ADIFタグ名 (default: my_pota_ref)')
    ap.add_argument('--jarl-field', default='jccjcgaja', help='JCC/JCG/AJA用ADIFタグ名 (default: jccjcgaja)')
    ap.add_argument('-c', '--choice', metavar="SPEC",
                     help='複数県にまたがる公園REFのフォールバック選択行(例: JP-0209:1,JP-0101:2)')
    ap.add_argument('-lc', '--list-choices', action='store_true',
                     help='-pのCSVを読み込み、複数県にまたがる公園REFの選択肢一覧を表示して終了する(ADIFは処理しない)')
    ap.add_argument('--overwrite', action='store_true',
                     help='既存のMY_STATE/MY_CNTY/JCC・JCG・AJAタグも上書きする')
    ap.add_argument('--version', action='version', version=f'polo-lotw-fill.py {VERSION}')
    args = ap.parse_args()

    ref_table = load_potatable(args.potatable)
    print(f"[info] POTA-REF.csv読み込み中: {args.potatable} ({len(ref_table)}件)", file=sys.stderr)

    if args.list_choices:
        lines = list_ambiguous_parks(ref_table)
        if lines:
            print("\n".join(lines))
        else:
            print("複数県にまたがる公園REFはありません。", file=sys.stderr)
        sys.exit(0)

    try:
        choices = parse_choice_spec(args.choice)
    except ValueError as e:
        sys.exit(f"[error] {e}")
    if choices:
        for line in describe_choices(choices, ref_table):
            print(line, file=sys.stderr)

    if args.input:
        with open(args.input, encoding='utf-8', errors='replace') as f:
            adif_text = f.read()
    else:
        adif_text = sys.stdin.read()

    header, body = split_header_and_body(adif_text)
    parts = re.split(r"<eor>", body, flags=re.IGNORECASE)
    footer = parts[-1]
    records = parts[:-1]

    pota_field_re = re.compile(MY_POTA_REF_RE_TMPL := MY_POTA_REF_TAG_RE_TMPL.format(field=re.escape(args.pota_field)),
                                re.IGNORECASE)
    jarl_tag_re = re.compile(JARL_TAG_RE_TMPL.format(field=re.escape(args.jarl_field)), re.IGNORECASE)

    warnings = []
    stats = {"total": 0, "no_pota_ref": 0, "unmatched_park": 0, "state_added": 0,
              "cnty_added": 0, "skipped_existing": 0, "jarl_added": 0, "jarl_missing": 0}

    out_records = []
    for idx, record in enumerate(records, 1):
        stats["total"] += 1

        comment_m = COMMENT_RE.search(record)
        comment = comment_m.group(1) if comment_m else ""
        # comment_m.group(1) is the byte-length, not the value; re-extract value properly
        if comment_m:
            byte_len = int(comment_m.group(1))
            start = comment_m.end()
            comment = record[start:].encode("utf-8")[:byte_len].decode("utf-8", errors="replace")

        m = pota_field_re.search(record)
        if not m:
            stats["no_pota_ref"] += 1
            warnings.append(f"[warn] レコード{idx}: {args.pota_field}タグなし")
            out_records.append(record)
            continue

        byte_len = int(m.group(1))
        start = m.end()
        park = record[start:].encode("utf-8")[:byte_len].decode("utf-8", errors="replace").strip().upper()

        candidates = ref_table.get(park)
        if not candidates:
            stats["unmatched_park"] += 1
            warnings.append(f"[warn] レコード{idx}: 公園REF {park} がPOTA-REF.csvに見つかりません")
            out_records.append(record)
            continue

        qso_label = f"レコード{idx}(POTA {park})"
        entry = select_ref_entry(park, candidates, comment, choices, qso_label, warnings)

        digits = digits_only(entry["jarl"])
        my_state = digits[:2]
        my_cnty = f"{my_state},{digits}"

        new_record = record
        has_state = bool(MY_STATE_TAG_RE.search(record))
        has_cnty = bool(MY_CNTY_TAG_RE.search(record))

        if has_state and not args.overwrite:
            stats["skipped_existing"] += 1
        else:
            new_record = replace_or_append_field(new_record, "my_state", my_state, MY_STATE_TAG_RE)
            stats["state_added"] += 1

        if has_cnty and not args.overwrite:
            pass
        else:
            new_record = replace_or_append_field(new_record, "my_cnty", my_cnty, MY_CNTY_TAG_RE)
            stats["cnty_added"] += 1

        has_jarl = bool(jarl_tag_re.search(new_record))
        if not entry["jarl"]:
            stats["jarl_missing"] += 1
            warnings.append(
                f"[warn] {qso_label}: POTA-REF.csvにJCC/JCG/AJA情報が無いため"
                f"{args.jarl_field}タグを付与できません")
        elif has_jarl and not args.overwrite:
            pass
        else:
            new_record = replace_or_append_field(new_record, args.jarl_field, entry["jarl"], jarl_tag_re)
            stats["jarl_added"] += 1

        out_records.append(new_record)

    body_out = "<eor>".join(out_records) + "<eor>" + footer
    result = header + body_out

    for w in warnings:
        print(w, file=sys.stderr)

    print(f"完了(v{VERSION}): 総レコード数 {stats['total']} 件 / "
          f"MY_STATE付与 {stats['state_added']} 件 / MY_CNTY付与 {stats['cnty_added']} 件 / "
          f"{args.jarl_field}付与 {stats['jarl_added']} 件 / "
          f"{args.pota_field}タグなし {stats['no_pota_ref']} 件 / "
          f"公園REF未突合 {stats['unmatched_park']} 件 / "
          f"JCC/JCG/AJA情報なしのため未付与 {stats['jarl_missing']} 件 / "
          f"既存のため未上書き {stats['skipped_existing']} 件 / 警告 {len(warnings)} 件",
          file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[info] 出力ファイルに書き込み完了: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
