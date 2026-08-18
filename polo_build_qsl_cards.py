#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QSLカード印刷用スクリプト (Polo系ADIF対応版)

polo-lotw-fill.py が出力したADIF(PoLo由来、MY_STATE/MY_CNTY付与済み)を
入力とし、build_qsl_cards.py と同じ形式の局ごとADIF/CSVを作成する。

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
   いずれもQSO_COMMENT列には、"My POTA Act Ref# " に元レコードの
   COMMENTSフィールドの値を追加した文字列を入れる(COMMENTSが無いQSOは空欄)
5. 画面表示した内容は、以下のファイルにも同時出力する
   - output/ADIF-Summary-YYYYMMDD-HHMM.txt  (--adif実行時)
   - output/CSV-Summary-YYYYMMDD-HHMM.txt   (--csv実行時)

出力先: output/ ディレクトリ

使い方:
  python3 polo_build_qsl_cards.py 入力.adif            # ADIF・CSV両方を作成
  python3 polo_build_qsl_cards.py 入力.adif --adif      # 局ごとADIFファイルのみ作成
  python3 polo_build_qsl_cards.py 入力.adif --csv       # CSV(サマリ+明細)のみ作成

build_qsl_cards.py との違い:
  ADIF仕様(ADIF Specification)ではコメントフィールドの正式名称は
  "COMMENT"(単数形)だが、polo-lotw-fill.py(PoLo由来)が出力するADIFでは
  非標準の "COMMENTS"(複数形)が使われている。そのため #POTA番号なし判定は
  "comment" を優先しつつ、存在しない場合は "comments" にフォールバックする。
  それ以外のロジック(base_call, ADIF/CSV出力形式)はbuild_qsl_cards.py v1.00
  と同一。
  なお、入力ADIFにはNAME/QTH/GRIDSQUARE(相手局側)フィールドが存在しないため、
  CSVの該当列は空欄になる(仕様通りの挙動、コード変更不要)。
  相手局側のPOTA_REF/SIG/SIG_INFO(パークトゥパーク情報)は、build_qsl_cards.py
  と同様に扱わず使用しない。
  QSO_COMMENT列の生成方法もbuild_qsl_cards.pyと異なる。build_qsl_cards.pyは
  MY_POTA_REFフィールドの値から "MY POTA ACT REF# JP-XXXX" (全て大文字) を
  組み立てるが、本スクリプトは "My POTA Act Ref# " に元レコードのCOMMENTS
  フィールドの値をそのまま追加する(MY_POTA_REFの値は参照しない)。

  -s/--station-callsign(build_pota_ref_csv.pyの-sと同じ考え方): 局ごと明細CSV
  (output/detail/<CALL>.csv)にSTATION_CALLSIGN列を追加する。ADIFレコードに
  station_callsignタグがあればその値をそのまま使い、無い場合はmy_pota_refから
  pota.app APIで公園のPOTA県コード(locationDesc)を求め、JARL_AREA_POTA_MAPPING
  でJARLエリア番号に変換し、"指定コールサイン/エリア番号" として補完する
  (build_pota_ref_csv.pyの-sと同じロジック。あくまでCSV出力にのみ反映し、
  入力ADIFファイル自体は変更しない)。
  -a/--add-jccjcgaja: 局ごと明細CSVにJCCJCGAJA列を追加する(polo-lotw-fill.py
  v1.2.0で付与されるjccjcgajaタグの値をそのまま使う。無ければ空欄)。
  -L/--excerpt-comment: QSO_COMMENT列を、既定の"My POTA Act Ref# "接頭辞付き
  全文ではなく、元のCOMMENT(またはCOMMENTS)フィールドの値のうち"||"より前の
  部分だけを抜粋した文字列にする(例: "My POTA Act Ref# TNX QSO es POTA
  JP-1805 ACT ! || CU AGN !" -> "TNX QSO es POTA JP-1805 ACT!")。
  いずれも未指定時は従来通りの列構成(CALL,QSO_DATE,TIME_ON,BAND,MODE,
  RST_SENT,RST_RCVD,QSO_COMMENT)のまま。両方指定時の列順は
  CALL,QSO_DATE,TIME_ON,BAND,MODE,RST_SENT,RST_RCVD,STATION_CALLSIGN,
  QSO_COMMENT,JCCJCGAJA (pivot_qso_for_glabels.pyのデフォルト列順と同一)。

CHANGELOG:
    1.3.1 (2026-08-17) -L/--excerpt-commentの抜粋結果で、末尾が" !"のように
         "!"の直前に空白がある場合はそれを詰めるよう修正
         (例: "TNX QSO es POTA JP-1805 ACT !" -> "TNX QSO es POTA JP-1805 ACT!")。
    1.3.0 (2026-08-17) -L/--excerpt-comment オプションを追加。QSO_COMMENT列を、
         既定の"My POTA Act Ref# "接頭辞付き全文ではなく、元のCOMMENT(または
         COMMENTS)フィールドの値のうち"||"より前の部分だけを抜粋した文字列に
         する(例: "My POTA Act Ref# TNX QSO es POTA JP-1805 ACT ! || CU AGN !"
         -> "TNX QSO es POTA JP-1805 ACT!")。未指定時は従来通り。
    1.2.0 (2026-08-17) -s/--station-callsign CALLSIGN オプションを追加。
         局ごと明細CSVにSTATION_CALLSIGN列を追加し、station_callsignタグが
         無いレコードはmy_pota_refをpota.app APIで検索してJARL_AREA_POTA_MAPPING
         でエリア番号に変換し補完する(build_pota_ref_csv.pyの-sと同じロジック、
         入力ADIFファイルは変更しない)。-a/--add-jccjcgaja オプションも追加し、
         局ごと明細CSVにJCCJCGAJA列(jccjcgajaタグの値)を追加できるようにした。
         --parks-json PATH(pota.app API取得結果のオフラインJSONキャッシュ、
         build_pota_ref_csv.pyと同じ形式)も追加。いずれも未指定時は従来通りの
         列構成のまま(後方互換)。
    1.1.0 (2026-08-16) QSO_COMMENTの生成方法を変更。MY_POTA_REFの値からの
         組み立てをやめ、"My POTA Act Ref# " + 元レコードのCOMMENTSフィールド
         の値、とする方式に変更。あわせて、ADIFフィールド値の切り出しを
         文字数ベースからバイト数(UTF-8)ベースに修正(日本語などマルチバイト
         文字を含むフィールドがあると後続フィールドまで巻き込んで誤読して
         いたバグを修正)。
    1.0.0 (2026-08-16) 初版。build_qsl_cards.py (v1.00) をベースに、
         polo-lotw-fill.py出力のPoLo系ADIFに対応。
         COMMENTフィールド名の差異(COMMENT優先・COMMENTSへフォールバック)
         にのみ対応。それ以外のロジックは変更なし。
"""

__version__ = "1.3.1"

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime

TAG_RE_BYTES = re.compile(rb"<(\w+):(\d+)(?::[^>]*)?>")
EOH_RE = re.compile(r"<eoh>", re.IGNORECASE)
EOR_RE = re.compile(r"<eor>", re.IGNORECASE)

POTA_JP_PARKS_API_URL = "https://api.pota.app/program/parks/JP"

# jarl_area_pota_mapping.csv の内容(不変の静的データ)。build_pota_ref_csv.pyと同一。
# 各タプルは (jarl_area, prefecture, pota_locationDesc, note)。
# prefectureが空の行(小笠原=JP-OG)はnoteを都道府県名の代わりに使う。
JARL_AREA_POTA_MAPPING = [
    ("1", "東京都", "JP-TK", ""),
    ("1", "", "JP-OG", "小笠原(東京都だがTKとは別コード)"),
    ("1", "神奈川県", "JP-KN", ""),
    ("1", "千葉県", "JP-CH", ""),
    ("1", "埼玉県", "JP-ST", ""),
    ("1", "茨城県", "JP-IB", ""),
    ("1", "栃木県", "JP-TC", ""),
    ("1", "群馬県", "JP-GM", ""),
    ("1", "山梨県", "JP-YN", ""),
    ("2", "愛知県", "JP-AI", ""),
    ("2", "静岡県", "JP-SZ", ""),
    ("2", "岐阜県", "JP-GF", ""),
    ("2", "三重県", "JP-ME", ""),
    ("3", "大阪府", "JP-OS", ""),
    ("3", "兵庫県", "JP-HG", ""),
    ("3", "京都府", "JP-KY", ""),
    ("3", "滋賀県", "JP-SH", ""),
    ("3", "奈良県", "JP-NR", ""),
    ("3", "和歌山県", "JP-WK", ""),
    ("4", "広島県", "JP-HS", ""),
    ("4", "岡山県", "JP-OY", ""),
    ("4", "島根県", "JP-SM", ""),
    ("4", "鳥取県", "JP-TT", ""),
    ("4", "山口県", "JP-YC", ""),
    ("5", "徳島県", "JP-TS", ""),
    ("5", "香川県", "JP-KG", ""),
    ("5", "愛媛県", "JP-EH", ""),
    ("5", "高知県", "JP-KC", ""),
    ("6", "福岡県", "JP-FO", ""),
    ("6", "佐賀県", "JP-SG", ""),
    ("6", "長崎県", "JP-NS", ""),
    ("6", "熊本県", "JP-KM", ""),
    ("6", "大分県", "JP-OT", ""),
    ("6", "宮崎県", "JP-MZ", ""),
    ("6", "鹿児島県", "JP-KS", ""),
    ("6", "沖縄県", "JP-ON", ""),
    ("7", "青森県", "JP-AO", ""),
    ("7", "岩手県", "JP-IW", ""),
    ("7", "宮城県", "JP-MG", ""),
    ("7", "秋田県", "JP-AK", ""),
    ("7", "山形県", "JP-YT", ""),
    ("7", "福島県", "JP-FS", ""),
    ("8", "北海道", "JP-HK", ""),
    ("9", "富山県", "JP-TY", ""),
    ("9", "石川県", "JP-IS", ""),
    ("9", "福井県", "JP-FI", ""),
    ("0", "新潟県", "JP-NI", ""),
    ("0", "長野県", "JP-NN", ""),
]


def load_jarl_area_mapping_static():
    """JARL_AREA_POTA_MAPPINGから POTA県コード -> (JARLエリア番号, 都道府県名) の辞書を作る。"""
    code_to_area_pref = {}
    for jarl_area, prefecture, pota_locationDesc, note in JARL_AREA_POTA_MAPPING:
        pref = prefecture or note
        code_to_area_pref[pota_locationDesc] = (jarl_area, pref)
    return code_to_area_pref


def fetch_jp_parks_from_api(quiet=False):
    """https://api.pota.app/program/parks/JP から日本全公園情報を取得し、
    {reference: {"locdesc":..., "lat":..., "lon":...}} を返す(取得失敗時はNone)。"""
    if not quiet:
        print(f"[info] pota.app APIから日本全公園情報を取得中: {POTA_JP_PARKS_API_URL}", file=sys.stderr)
    try:
        with urllib.request.urlopen(POTA_JP_PARKS_API_URL, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"[error] pota.app API取得失敗: {e}", file=sys.stderr)
        return None

    park_info = {}
    for row in data:
        ref = row.get("reference")
        if not ref:
            continue
        lat = row.get("latitude") or row.get("lat")
        lon = row.get("longitude") or row.get("lon") or row.get("lng")
        locdesc = row.get("locationDesc") or row.get("locationDescription") or ""
        park_info[ref] = {"locdesc": locdesc, "lat": lat, "lon": lon}
    if not quiet:
        print(f"[info] 公園情報 {len(park_info)}件を取得", file=sys.stderr)
    return park_info


def load_park_info_cached(cache_path, quiet=False):
    """--parks-json 指定時: キャッシュファイルがあればそれを使い、無ければAPI取得して保存する"""
    if cache_path and os.path.exists(cache_path):
        if not quiet:
            print(f"[info] 公園情報キャッシュを使用: {cache_path}", file=sys.stderr)
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    park_info = fetch_jp_parks_from_api(quiet=quiet)
    if park_info is None:
        return None
    if cache_path:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(park_info, f, ensure_ascii=False, indent=2, sort_keys=True)
        if not quiet:
            print(f"[info] 公園情報キャッシュを保存: {cache_path}", file=sys.stderr)
    return park_info


def resolve_station_callsign(fields, station_callsign_base, park_info, code_to_area_pref, warnings, label):
    """明細CSVのSTATION_CALLSIGN列の値を求める。
    レコードにstation_callsignタグがあればその値をそのまま使う。無い場合は、
    my_pota_refをpark_info(pota.app API取得結果)のlocationDescで引き、
    code_to_area_pref(JARL_AREA_POTA_MAPPING)でJARLエリア番号に変換し、
    station_callsign_base + '/' + エリア番号 として補完する。
    どこかで解決できなければ空文字を返し、warningsに理由を追記する。"""
    existing = fields.get("station_callsign", "").strip()
    if existing:
        return existing

    ref = fields.get("my_pota_ref", "").strip().upper()
    if not ref:
        warnings.append(f"{label}: station_callsignタグもmy_pota_refタグも無いため補完できません")
        return ""

    info = (park_info or {}).get(ref)
    if info is None:
        warnings.append(f"{label}: 公園REF {ref} がpota.app APIに見つからないためSTATION_CALLSIGNを補完できません")
        return ""

    codes = [c.strip() for c in (info.get("locdesc") or "").split(",") if c.strip()]
    if not codes:
        warnings.append(f"{label}: 公園REF {ref} のPOTA県コードが不明なためSTATION_CALLSIGNを補完できません")
        return ""

    area_pref = (code_to_area_pref or {}).get(codes[0])
    if area_pref is None:
        warnings.append(
            f"{label}: POTA県コード{codes[0]}に対応するJARLエリア番号がJARL_AREA_POTA_MAPPINGに"
            f"見つからないためSTATION_CALLSIGNを補完できません(公園REF {ref})")
        return ""
    area, _pref = area_pref
    if len(codes) > 1:
        warnings.append(
            f"{label}: 公園REF {ref} は複数県({','.join(codes)})にまたがるため、"
            f"先頭のPOTA県コード{codes[0]}のエリア番号{area}を使用します")

    return f"{station_callsign_base}/{area}"


def comment_text(fields):
    """コメント欄のテキストを返す。

    ADIF仕様上の正式フィールド名は "COMMENT"(単数形)だが、
    polo-lotw-fill.py出力(PoLo由来)では非標準の "COMMENTS"(複数形)が
    使われているため、commentを優先しcommentsにフォールバックする。
    """
    return fields.get("comment") or fields.get("comments", "")


def pota_comment(fields):
    """"My POTA Act Ref# " に元レコードのCOMMENTSフィールドの値を追加した文字列を返す。
    COMMENTS(またはCOMMENT)が無ければ空文字。"""
    comment = comment_text(fields).strip()
    return f"My POTA Act Ref# {comment}" if comment else ""


def pota_comment_excerpt(fields):
    """-L指定時のQSO_COMMENT: "My POTA Act Ref# "接頭辞は付与せず、元レコードの
    COMMENT(またはCOMMENTS)フィールドの値のうち "||" より前の部分だけを抜粋する
    (前後の空白は除去し、末尾が " !" のように"!"の直前に空白がある場合は詰める)。例:
      "TNX QSO es POTA JP-1805 ACT ! || CU AGN !"
      -> "TNX QSO es POTA JP-1805 ACT!"
    COMMENTS(またはCOMMENT)が無ければ空文字。"||"が無ければ全体を返す。"""
    comment = comment_text(fields).strip()
    if not comment:
        return ""
    excerpt = comment.split("||", 1)[0].strip()
    return re.sub(r"\s+!$", "!", excerpt)


def pota_ref_without_comment_mark(fields):
    """my_pota_refはあるが、Comment欄に"JP-"の記載が無いQSOかどうかを判定する"""
    ref = fields.get("my_pota_ref", "").strip()
    if not ref:
        return False
    comment = comment_text(fields)
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
    parser.add_argument("-s", "--station-callsign", metavar="CALLSIGN",
                         help="局ごと明細CSVにSTATION_CALLSIGN列を追加する際のベースコールサイン"
                              "(例: -s JL1ICY)。station_callsignタグがあるレコードはその値をそのまま"
                              "使い、無いレコードはmy_pota_refをpota.app APIで検索してJARL_AREA_POTA_"
                              "MAPPINGでエリア番号に変換し、CALLSIGN/エリア番号 の形で補完する"
                              "(build_pota_ref_csv.pyの-sと同じロジック。入力ADIFファイルは変更しない。"
                              "未指定時、STATION_CALLSIGN列自体を出力しない)")
    parser.add_argument("-a", "--add-jccjcgaja", action="store_true",
                         help="局ごと明細CSVにJCCJCGAJA列を追加する(jccjcgajaタグの値をそのまま使う。"
                              "無ければ空欄。未指定時、JCCJCGAJA列自体を出力しない)")
    parser.add_argument("-L", "--excerpt-comment", action="store_true",
                         help="QSO_COMMENT列を、既定の\"My POTA Act Ref# \"接頭辞付き全文ではなく、"
                              "元のCOMMENT(またはCOMMENTS)フィールドの値のうち\"||\"より前の部分だけを"
                              "抜粋した文字列にする(例: \"My POTA Act Ref# TNX QSO es POTA JP-1805 "
                              "ACT ! || CU AGN !\" -> \"TNX QSO es POTA JP-1805 ACT!\")")
    parser.add_argument("--parks-json", metavar="PATH",
                         help="pota.app API取得結果のオフラインJSONキャッシュ(-s指定時のみ使用。"
                              "存在すれば再利用、無ければ取得して保存)")
    args = parser.parse_args()

    comment_fn = pota_comment_excerpt if args.excerpt_comment else pota_comment

    # どちらのオプションも指定されなければ両方作成する
    do_adif = args.adif or not (args.adif or args.csv)
    do_csv = args.csv or not (args.adif or args.csv)

    park_info = None
    code_to_area_pref = None
    station_callsign_warnings = []
    if args.station_callsign:
        code_to_area_pref = load_jarl_area_mapping_static()
        park_info = load_park_info_cached(args.parks_json, quiet=False)
        if park_info is None:
            print("[error] 公園情報を取得できなかったため終了します(-s指定時は事前取得が必要です)",
                  file=sys.stderr)
            sys.exit(1)

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
                    comment_lines.append(comment_fn(f))

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
                # -s/-a指定時のみSTATION_CALLSIGN/JCCJCGAJA列を追加する
                # (pivot_qso_for_glabels.pyのデフォルト列順と同じ位置に挿入)
                detail_header = ["CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE", "RST_SENT", "RST_RCVD"]
                if args.station_callsign:
                    detail_header.append("STATION_CALLSIGN")
                detail_header.append("QSO_COMMENT")
                if args.add_jccjcgaja:
                    detail_header.append("JCCJCGAJA")

                detail_path = os.path.join(detail_dir, f"{call}.csv")
                with open(detail_path, "w", encoding="utf-8", newline="") as df:
                    dwriter = csv.writer(df)
                    dwriter.writerow(detail_header)
                    for qso_idx, f in enumerate(fset, 1):
                        row = [
                            f.get("call", ""),
                            f.get("qso_date", ""),
                            f.get("time_on", ""),
                            f.get("band", ""),
                            f.get("mode", ""),
                            f.get("rst_sent", ""),
                            f.get("rst_rcvd", ""),
                        ]
                        if args.station_callsign:
                            label = f"{call} QSO{qso_idx}({f.get('qso_date', '')} {f.get('time_on', '')})"
                            row.append(resolve_station_callsign(
                                f, args.station_callsign, park_info, code_to_area_pref,
                                station_callsign_warnings, label))
                        row.append(comment_fn(f))
                        if args.add_jccjcgaja:
                            row.append(f.get("jccjcgaja", ""))
                        dwriter.writerow(row)

        if station_callsign_warnings:
            log_csv("-" * 60)
            for w in station_callsign_warnings:
                log_csv(f"[warn] {w}")

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
