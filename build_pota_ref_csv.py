#!/usr/bin/env python3
"""
指定ディレクトリを再帰的に検索して *.adi / *.adif ファイルを開き、
各QSOレコードの STATION_CALLSIGN タグ(例: JQ1UCG/2)からJARLエリア番号を、
MY_POTA_REF タグから公園REF番号(例: JP-1181)を抽出する。

既存の POTA-REF.csv(-o で指定、既に存在すれば読み込む)と突合し、
まだ登録されていない (JARLエリア番号, 公園REF番号) の組み合わせのみを
新規行として追記する(差分更新)。

新規に見つかった公園REF番号については、pota.app APIの
  https://api.pota.app/program/parks/JP
から日本全公園のGRIDLOCATOR(緯度経度)・POTA県コード(locationDesc)を
一括取得し、市区町村名・JCC/JCG/AJA番号への変換ロジック(GSI逆ジオコーディングAPI
+ muni.js + Geolonia住所データ + JARL公式JCC/JCG/AJAリスト)は、旧スクリプト
match_pota_jarl_area.py の実装をそのまま本ファイル内に統合している
(外部ファイルへの依存を無くすため、別モジュールとしてのimportはしない)。

前提:
  - STATION_CALLSIGN には必ず "/n" 形式のエリア番号サフィックスが
    付与されているものとして扱う(付いていないレコードはスキップし警告。
    ただし-s/--station-callsign指定時は後述の方法で補完する)。
  - 複数の都道府県にまたがる公園は、既存 POTA-REF.csv と同じ流儀で
    県コードごとに複数行を出力する(各行のJARLエリア番号は共通して
    STATION_CALLSIGNから得たエリア番号を使う。POTA県コードから求まる
    エリア番号は使わない)。

jarl_area_pota_mapping.csv(JARLエリア番号↔都道府県↔POTA県コードの対応表)は
不変の静的データのため、外部ファイルを読み込まずスクリプト内に直接埋め込んでいる。

使い方:
    python3 build_pota_ref_csv.py <ADIF検索ルートディレクトリ> -o POTA-REF.csv [options]
    python3 build_pota_ref_csv.py -i input1.adi -i input2.adi -o POTA-REF.csv [options]
    python3 build_pota_ref_csv.py <ADIF検索ルートディレクトリ> -s JL1ICY -o POTA-REF.csv
    python3 build_pota_ref_csv.py -i input1.adi -s JL1ICY -u -o POTA-REF.csv

オプション:
    adif_root              ADIFファイルを再帰検索するルートディレクトリ(-f/-i指定時は不要。
                           -iと同時指定はできない)
    -i, --input ADIF_FILE  読み込むADIFファイルを個別に指定する(複数回指定可)。指定時は
                           ディレクトリの再帰検索を行わず、指定したファイルのみを読み込む
                           (adif_rootディレクトリ指定とは排他。-e/--excludeは無視される)
    -s, --station-callsign CALLSIGN
                           STATION_CALLSIGNタグが無いADIFレコードを補完する際のベース
                           コールサイン(例: -s JL1ICY)。指定時、STATION_CALLSIGNタグが
                           無くMY_POTA_REFタグはあるレコードについて、公園REF番号を
                           pota.app APIで検索してPOTA県コード(locationDesc)を求め、
                           JARL_AREA_POTA_MAPPINGでJARLエリア番号に変換し、
                           CALLSIGN/エリア番号 の形でSTATION_CALLSIGNを補完してから抽出する
                           (未指定時、STATION_CALLSIGNタグが無いレコードは従来通り
                           スキップされる。-f/--full指定時は無視される)
    -u, --update-station-callsign
                           -sで補完されるSTATION_CALLSIGNタグを、実際に-i/--inputで指定
                           したADIFファイルへ書き込んで更新する(-sおよび-iと同時指定が
                           必須。ディレクトリ再帰検索には非対応)。-u未指定時、-sは
                           集計・表示のみで元ファイルは変更しない。上書き前に元ファイルを
                           <path>.bakとしてバックアップする
    -o, --output PATH     出力CSV(-a指定時、または既存ファイルがあり-n未指定時は読み込んで差分追記する。
                           省略時は新規分のみ標準出力へ出力)
    -n, --new              既存の-o出力ファイルが存在してもそれを無視し、新規作成(上書き)する
    -a, --append            既存の-o出力ファイルに対して差分追記する(-o省略時かつ-n未指定時のデフォルト動作と同じ)
    --parks-json PATH     pota.app API取得結果のオフラインJSONキャッシュ
                           (指定時、ファイルが存在すればAPI問い合わせをせずこれを使う。
                            存在しない場合はAPIから取得しこのパスへ保存する)
    --muni-cache PATH     市町村名/JCC・JCG・AJA番号の問い合わせ結果をJSONでキャッシュするファイル
    --no-muni              市町村名・JCC/JCG/AJA番号の問い合わせを行わない(該当2カラムは空欄)
    -j, --jobs N            GSI逆ジオコーディングAPIへの並列問い合わせ数(デフォルト: 10)
    --dry-run                ファイルへの書き込みを行わず、追加(または新規作成)される行と件数のみ表示する
    -e, --exclude DIRNAME  この名前(完全一致)のディレクトリを検索対象から除外する。
                           複数回指定して複数ディレクトリを除外できる
                           (例: -e "POTA-Aichi,Gifu,Mie" -e POTA-Gifu)
                           -i指定時はディレクトリ検索自体を行わないため無視される
    -f, --full              ADIFを検索せず、pota.app APIから日本の全POTA対象公園リストを
                           取得し、それを元にPOTA-REF.full.csv(固定ファイル名)を
                           新規作成する。既存の-o出力ファイルは読み込まない
                           (-o/-n/-aは無視される)。adif_root引数も不要
    -q, --quiet              進捗表示を抑制する
    --version                バージョン番号を表示して終了

変更履歴:
    1.0.0 (2026-08-16) 初版
    1.1.0 (2026-08-16) -n/--new(既存出力ファイルを無視して新規作成)、
                        -a/--append(既存出力ファイルへの差分追記、デフォルト動作の明示指定)
                        オプションを追加。-n/-aは同時指定不可。
                        従来--dry-runの短縮形だった-nは-n/--newと衝突するため廃止
                        (--dry-runは長い形式のみに変更)。
    1.2.0 (2026-08-16) jarl_area_pota_mapping.csvの内容(不変の静的データ)を
                        スクリプト内にPythonの定数として直接埋め込み、外部ファイル
                        引数(mapping_csv_path)を廃止。
    1.3.0 (2026-08-16) -e/--exclude DIRNAME オプションを追加(複数回指定可)。
                        指定した名前(完全一致)のディレクトリを検索から除外する。
                        ディレクトリ探索方式をglob再帰からos.walkに変更
                        (除外ディレクトリ以下を丸ごと探索対象から外すため)。
    1.4.0 (2026-08-16) 外部モジュールmatch_pota_jarl_area.pyへの依存を廃止し、
                        市区町村名・JCC/JCG/AJA番号変換ロジックを本ファイル内に
                        直接統合(単一ファイルで完結するように変更)。
    1.5.0 (2026-08-16) -f/--full オプションを追加。ADIFを検索せずpota.app APIの
                        日本全公園リストからPOTA-REF.full.csv(固定ファイル名)を
                        新規作成する。エリア番号はSTATION_CALLSIGNではなくPOTA県
                        コードからjarl_area_pota_mappingで求める(ADIF由来モードとは
                        エリア番号の算出方法が異なる)。
    1.6.0 (2026-08-17) -i/--input ADIF_FILE オプションを追加(複数回指定可)。
                        読み込むADIFファイルを個別に指定できるようにした。指定時は
                        ディレクトリの再帰検索を行わず、指定したファイルのみを読み込む
                        (adif_rootディレクトリ引数とは排他。-e/--excludeは無視される)。
    1.7.0 (2026-08-17) -s/--station-callsign CALLSIGN オプションを追加。
                        STATION_CALLSIGNタグが無いADIFレコードについて、MY_POTA_REFの
                        公園REF番号をpota.app APIで検索してPOTA県コード(locationDesc)を
                        求め、JARL_AREA_POTA_MAPPINGでJARLエリア番号に変換し、
                        CALLSIGN/エリア番号 の形でSTATION_CALLSIGNを補完してから抽出する
                        ようにした(未指定時は従来通りスキップ。-f/--full指定時は無視)。
    1.8.0 (2026-08-17) -u/--update-station-callsign オプションを追加。-s指定時、
                        従来は集計・表示のみだった補完結果を、-i/--inputで指定した
                        ADIFファイルへ実際にSTATION_CALLSIGNタグとして書き込めるように
                        した(-s/-iと同時指定が必須。ディレクトリ再帰検索は非対応)。
                        上書き前に元ファイルを<path>.bakへバックアップする。
"""

import argparse
import concurrent.futures
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "1.8.0"

DEFAULT_JOBS = 10
POTA_JP_PARKS_API_URL = "https://api.pota.app/program/parks/JP"

# --- 以下、市区町村名・JCC/JCG/AJA番号変換ロジック(旧match_pota_jarl_area.py由来) ---
GSI_REVGEOCODE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
GSI_MUNI_MASTER_URL = "https://maps.gsi.go.jp/js/muni.js"
GEOLONIA_JA_URL = "https://geolonia.github.io/japanese-addresses/api/ja.json"
JARL_JCC_URL = "https://www.jarl.org/Japanese/A_Shiryo/A-2_jcc-jcg/jcc-list.txt"
JARL_JCG_URL = "https://www.jarl.org/Japanese/A_Shiryo/A-2_jcc-jcg/jcg-list.txt"
JARL_AJA_URL = "https://www.jarl.org/Japanese/A_Shiryo/A-2_jcc-jcg/ku-list.txt"
GSI_REQUEST_INTERVAL_SEC = 0.5  # GSI APIへの負荷軽減用のウェイト(ワーカースレッドごと)

CSV_HEADER = ["JARLエリア番号", "公園REF番号", "JP都道府県名", "都道府県名+市区/郡名", "JCC/JCG/AJA"]

# jarl_area_pota_mapping.csv の内容(不変の静的データ)を直接埋め込む。
# 各タプルは (jarl_area, prefecture, pota_locationDesc, note)。
# prefectureが空の行(小笠原=JP-OG)はnoteを都道府県名の代わりに使う
# (旧match_pota_jarl_area.pyのload_jarl_area_mapping()と同じ扱い)。
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
    """埋め込み済みのJARL_AREA_POTA_MAPPINGから
    POTA県コード(例: 'JP-AI') -> (JARLエリア番号, 都道府県名) の辞書を作る。
    旧match_pota_jarl_area.pyのload_jarl_area_mapping()が外部CSVから作るものと同じ形式・同じ内容。"""
    code_to_area_pref = {}
    for jarl_area, prefecture, pota_locationDesc, note in JARL_AREA_POTA_MAPPING:
        pref = prefecture or note
        code_to_area_pref[pota_locationDesc] = (jarl_area, pref)
    return code_to_area_pref


def load_muni_cache(cache_path):
    if cache_path is None:
        return {}
    try:
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_muni_cache(cache_path, cache):
    if cache_path is None:
        return
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


MUNI_LINE_RE = re.compile(r'GSI\.MUNI_ARRAY\["(\d+)"\]\s*=\s*\'\d+,([^,]*),\d+,\s*([^\']*)\'')


def load_muni_master(verbose=False):
    """GSIのmuni.js(muniCd -> (都道府県名, 市区町村名(郡名なし短縮名)))を取得しdictで返す。失敗時は空dict。"""
    try:
        with urllib.request.urlopen(GSI_MUNI_MASTER_URL, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        if verbose:
            print(f"[warn] muni.js取得失敗: {e}", file=sys.stderr)
        return {}

    master = {}
    for m in MUNI_LINE_RE.finditer(text):
        cd, pref, name = m.group(1), m.group(2), m.group(3).replace("\u3000", "")
        master[cd.zfill(5)] = (pref, name)
    if verbose:
        print(f"[info] muni.js読み込み: {len(master)}件", file=sys.stderr)
    return master


def load_geolonia_pref_cities(verbose=False):
    """Geolonia住所データ(都道府県ごとの郡名付き市区町村名一覧)を取得する。失敗時は空dict。"""
    try:
        with urllib.request.urlopen(GEOLONIA_JA_URL, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        if verbose:
            print(f"[warn] Geolonia住所データ取得失敗: {e}", file=sys.stderr)
        return {}
    if verbose:
        total = sum(len(v) for v in data.values())
        print(f"[info] Geolonia住所データ読み込み: {total}件", file=sys.stderr)
    return data


GUN_PREFIX_RE = re.compile(r"^(.*?郡)")  # 非貪欲(「上郡町」のように町名自体に郡を含む例への対策)


def build_muni_award_unit_map(muni_master, geolonia_pref_cities, jarl_master, verbose=False):
    """muniCdごとに (表示用「都道府県+市区/郡名」, JCC/JCG/AJA番号) を算出する。
    戻り値: award_map(表示用), jarl_award_map(JCC/JCG/AJA番号、該当なしはNone)"""
    award_map = {}
    jarl_award_map = {}
    unmatched = 0
    for muni_cd, (pref, short_name) in muni_master.items():
        candidates = geolonia_pref_cities.get(pref, [])
        full_name = None
        for c in candidates:
            if c == short_name:
                full_name = c
                break
        if full_name is None:
            for c in candidates:
                if _norm_kana(c) == _norm_kana(short_name):
                    full_name = c
                    break
        if full_name is None:
            for c in candidates:
                if c.endswith(short_name) and c != short_name:
                    full_name = c
                    break
        if full_name is None:
            for c in candidates:
                if _norm_kana(c).endswith(_norm_kana(short_name)) and _norm_kana(c) != _norm_kana(short_name):
                    full_name = c
                    break
        if full_name is None:
            # Geolonia側に見つからない場合(政令市の親コードなど)はmuni.jsの短縮名で代用
            full_name = short_name
            unmatched += 1

        gun_match = GUN_PREFIX_RE.match(full_name)
        if gun_match:
            award_map[muni_cd] = pref + gun_match.group(1)
            gun_base = gun_match.group(1)[:-1]
            jarl_award_map[muni_cd] = lookup_jarl_award(
                jarl_master, pref, full_name, gun_base=gun_base, town_short=short_name)
        else:
            award_map[muni_cd] = pref + full_name
            jarl_award_map[muni_cd] = lookup_jarl_award(jarl_master, pref, full_name)

    if verbose:
        jarl_hit = sum(1 for v in jarl_award_map.values() if v)
        print(f"[info] muniCd->都道府県+市区/郡 変換マップ作成: {len(award_map)}件 "
              f"(Geolonia未一致でmuni.js短縮名を使用: {unmatched}件, "
              f"JCC/JCG/AJA特定: {jarl_hit}件)", file=sys.stderr)
    return award_map, jarl_award_map


def _norm_kana(s):
    """ヶ/ヵ表記ゆれ・梼/檮異体字を吸収するための正規化"""
    return s.replace("\u30f6", "\u30b1").replace("\u30f5", "\u30ab").replace("檮", "梼")


def _strip_pref_suffix(pref):
    if pref == "北海道":
        return pref
    return re.sub(r"(都|道|府|県)$", "", pref)


def _fetch_cp932(url, verbose=False, label=""):
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = resp.read()
        return data.decode("cp932", errors="replace")
    except urllib.error.URLError as e:
        if verbose:
            print(f"[warn] {label}取得失敗: {e}", file=sys.stderr)
        return None


_JCC_HEADER_RE = re.compile(r"^([^\d\*]{1,12}?)\s*(\d{2})\s*$")
_JCC_LINE_RE = re.compile(r"^(\*)?\s*(\d{4,6})\s+([A-Za-z0-9\.\-\(\)' ]+?)\s{2,}(\S+)")
_JCG_PARENT_RE = re.compile(r"^(\*)?\s*(\d{5})\s+([A-Za-z0-9\.\-\(\)' ]+?)\s{2,}(\S+)")
_JCG_CHILD_RE = re.compile(r"^\s+([A-Za-z][A-Za-z0-9]*)\s+(\S+)")
_JCG_BASE_RE = re.compile(r"^([^\(（]+)")
_AJA_HEADER_RE = re.compile(r"^(\S+?)[\(（](\d{4})[\)）]\s*$")
_AJA_LINE_RE = re.compile(r"^(\d{6})\s+([A-Za-z][A-Za-z0-9]*)\s+(\S+)\s*$")


def load_jarl_award_master(verbose=False):
    """JARL公式のJCC/JCG/AJAリストを取得・パースし、都道府県名文字列マッチング用の
    ルックアップ構造を返す(取得失敗時は空の構造。この場合JCC/JCG/AJA列は全て空欄になる)。
    戻り値: dict with keys pref_to_area, jcc_master, aja_master, jcg_children, jcg_base"""
    jcc_text = _fetch_cp932(JARL_JCC_URL, verbose, "JCCリスト")
    jcg_text = _fetch_cp932(JARL_JCG_URL, verbose, "JCGリスト")
    aja_text = _fetch_cp932(JARL_AJA_URL, verbose, "AJA(区)リスト")

    result = {"pref_to_area": {}, "jcc_master": {}, "aja_master": {},
              "jcg_children": {}, "jcg_base": {}}
    if jcc_text is None or jcg_text is None or aja_text is None:
        return result

    pref_to_area = {}
    for line in jcc_text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        m = _JCC_HEADER_RE.match(line)
        if m and not re.search(r"[A-Za-z]", m.group(1)):
            pref_to_area[re.sub(r"\s+", "", m.group(1))] = m.group(2)
    result["pref_to_area"] = pref_to_area

    jcc_master = {}
    for line in jcc_text.splitlines():
        m = _JCC_LINE_RE.match(line)
        if not m:
            continue
        abolished, code, roman, kanji = m.groups()
        if abolished:
            continue
        area2 = code[:2]
        name = (kanji + "区") if len(code) == 6 else (kanji + "市")
        jcc_master[(area2, _norm_kana(name))] = code
    result["jcc_master"] = jcc_master

    gun_entries, current = [], None
    for line in jcg_text.splitlines():
        m = _JCG_PARENT_RE.match(line)
        if m:
            abolished, code, roman, kanji = m.groups()
            current = {"abolished": abolished is not None, "code": code,
                       "kanji": kanji.strip(), "children": []}
            gun_entries.append(current)
            continue
        m2 = _JCG_CHILD_RE.match(line)
        if m2 and current is not None:
            current["children"].append(m2.group(2).strip())

    jcg_children, jcg_base_lists = {}, {}
    for g in gun_entries:
        if g["abolished"]:
            continue
        area2 = g["code"][:2]
        for child in g["children"]:
            jcg_children[(area2, _norm_kana(child))] = g["code"]
        base = _JCG_BASE_RE.match(g["kanji"]).group(1)
        jcg_base_lists.setdefault((area2, base), []).append(g["code"])
    result["jcg_children"] = jcg_children
    result["jcg_base"] = {k: v[0] for k, v in jcg_base_lists.items() if len(v) == 1}

    aja_master = {}
    cur_parent_code = cur_parent_name = None
    for line in aja_text.splitlines():
        line = line.rstrip("\n")
        m = _AJA_HEADER_RE.match(line.strip())
        if m:
            cur_parent_name, cur_parent_code = m.groups()
            continue
        if "※" in line:
            continue
        m2 = _AJA_LINE_RE.match(line)
        if m2 and cur_parent_code:
            code, roman, kanji = m2.groups()
            name = cur_parent_name + kanji + "区"
            aja_master[(code[:2], _norm_kana(name))] = code
    result["aja_master"] = aja_master

    if verbose:
        print(f"[info] JARL JCC/JCG/AJAマスタ読み込み: "
              f"JCC{len(jcc_master)}件 JCG(郡名一意){len(result['jcg_base'])}件 "
              f"JCG(町村名){len(jcg_children)}件 AJA{len(aja_master)}件", file=sys.stderr)
    return result


def lookup_jarl_award(jarl_master, pref, name, gun_base=None, town_short=None):
    """都道府県名+市区/郡名(name)からJCC/JCG/AJA番号を引く。該当なしはNoneを返す。"""
    area2 = jarl_master["pref_to_area"].get(_strip_pref_suffix(pref))
    if area2 is None:
        return None
    nname = _norm_kana(name)
    if nname.endswith("市"):
        c = jarl_master["jcc_master"].get((area2, nname))
        return f"JCC{c}" if c else None
    if nname.endswith("区"):
        c = jarl_master["jcc_master"].get((area2, nname))
        if c:
            return f"JCC{c}"
        c = jarl_master["aja_master"].get((area2, nname))
        return f"AJA{c}" if c else None
    if town_short:
        c = jarl_master["jcg_children"].get((area2, _norm_kana(town_short)))
        if c:
            return f"JCG{c}"
    if gun_base:
        c = jarl_master["jcg_base"].get((area2, _norm_kana(gun_base)))
        if c:
            return f"JCG{c}"
    return None


def query_gsi_muni_cd(lat, lon, verbose=False):
    """GSI逆ジオコーディングAPIで緯度経度からmuniCdを取得する。失敗時はNoneを返す。"""
    params = urllib.parse.urlencode({"lat": lat, "lon": lon})
    url = f"{GSI_REVGEOCODE_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        if verbose:
            print(f"[warn] GSI API問い合わせ失敗 lat={lat} lon={lon}: {e}", file=sys.stderr)
        return None

    results = data.get("results")
    if not results:
        return None
    return results.get("muniCd")


def resolve_all_municipalities(sorted_refs, park_info, cache, award_map, jarl_award_map,
                                jobs=DEFAULT_JOBS, quiet=False):
    """キャッシュにない公園REFについて、GSI逆ジオコーディングAPIを並列(jobs並列)で問い合わせ、
    結果({"muni":都道府県+市区/郡名, "jarl":JCC/JCG/AJA番号})をcacheに書き込む。
    lat/lonが無い、またはpark_infoに無いものは cache[ref] = {"muni": None, "jarl": None} とする。
    旧バージョンのキャッシュ(文字列やjarlキー欠落)は不完全とみなし再取得する。"""
    to_query = []
    for ref in sorted_refs:
        entry = cache.get(ref)
        if isinstance(entry, dict) and "muni" in entry and "jarl" in entry:
            continue
        info = park_info.get(ref)
        if info is None or not info["lat"] or not info["lon"]:
            cache[ref] = {"muni": None, "jarl": None}
            continue
        to_query.append((ref, info["lat"], info["lon"]))

    total = len(to_query)
    if total == 0:
        return

    def worker(item):
        ref, lat, lon = item
        muni_cd = query_gsi_muni_cd(lat, lon, verbose=not quiet)
        time.sleep(GSI_REQUEST_INTERVAL_SEC)
        muni = jarl = None
        if muni_cd:
            # muni.jsのキーは都道府県コードが1桁の場合(01~09)は先頭ゼロなしの4桁になっているため、
            # APIが返す5桁ゼロ埋めのmuniCdはそのままだと引けないことがある。両方の形で試す。
            key = muni_cd if muni_cd in award_map else muni_cd.lstrip("0")
            muni = award_map.get(key)
            jarl = jarl_award_map.get(key)
        return ref, lat, lon, muni_cd, muni, jarl

    if not quiet:
        print(f"[info] GSI逆ジオコーディングAPIへ並列({jobs}並列)で{total}件問い合わせます", file=sys.stderr)

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(worker, item): item[0] for item in to_query}
        for future in concurrent.futures.as_completed(futures):
            ref, lat, lon, muni_cd, muni, jarl = future.result()
            cache[ref] = {"muni": muni, "jarl": jarl}
            done += 1
            if not quiet:
                print(f"[progress] {done}/{total} {ref}: lat={lat} lon={lon} "
                      f"-> muniCd={muni_cd} -> {muni} / {jarl}", file=sys.stderr)

STATION_CALLSIGN_RE = re.compile(r"<station_callsign:\d+>([^\s<]+)", re.IGNORECASE)
MY_POTA_REF_RE = re.compile(r"<my_pota_ref:\d+>([^\s<]+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 1. ADIFファイルの再帰検索とタグ抽出
# ---------------------------------------------------------------------------

def find_adif_files(root_dir, exclude_dirnames=None):
    """root_dir配下を再帰的に検索し、*.adi / *.adif ファイルのパス一覧を返す(大小文字区別なし)。
    exclude_dirnamesに含まれる名前のディレクトリ(名前の完全一致)は、
    そのディレクトリ以下ごと検索対象から除外する。"""
    exclude_set = set(exclude_dirnames or [])
    adif_ext = {".adi", ".adif"}
    found = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # os.walk中にdirnamesをin-placeで書き換えると、それ以下の探索が丸ごとスキップされる
        dirnames[:] = [d for d in dirnames if d not in exclude_set]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in adif_ext:
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def resolve_input_files(file_paths, warnings):
    """-i/--input で明示指定されたADIFファイルパスのリストを検証する。
    存在しないファイルはwarningsに記録して除外し、残りを重複排除・ソートして返す。"""
    resolved = []
    for path in file_paths:
        if not os.path.isfile(path):
            warnings.append(f"{path}: ファイルが存在しないためスキップ")
            continue
        resolved.append(path)
    # 重複指定を除去しつつ順序を安定させるためソート
    return sorted(set(resolved))


def update_input_files_station_callsign(file_paths, station_callsign_base, park_info,
                                         code_to_area_pref, quiet=False):
    """-u/--update-station-callsign: -i/--input で指定されたADIFファイルのうち、
    STATION_CALLSIGNタグが無くMY_POTA_REFタグがあるレコードへ、
    station_callsign_base + '/' + エリア番号 のSTATION_CALLSIGNタグを実際に書き込み、
    ファイルを更新する(上書き前に元ファイルを <path>.bak としてバックアップする)。
    ヘッダー部・<EOR>区切り以外の元テキストは一切変更しない(該当レコードへのタグ追記のみ)。
    戻り値: 実際にタグを追加したレコードの総数。"""
    warnings = []
    updated_total = 0
    for path in file_paths:
        if not os.path.isfile(path):
            warnings.append(f"{path}: ファイルが存在しないためスキップ")
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            warnings.append(f"{path}: 読み込み失敗 ({e})")
            continue

        # <EOH>より前(ヘッダー部)は変更しない。<EOR>もデリミタとして温存し、
        # それ以外のレコード内テキストは元のまま(追加分のみ末尾に付与)にする。
        header_parts = re.split(r"(<eoh>)", text, maxsplit=1, flags=re.IGNORECASE)
        if len(header_parts) == 3:
            header_full = header_parts[0] + header_parts[1]
            body = header_parts[2]
        else:
            header_full = ""
            body = text

        segments = re.split(r"(<eor>)", body, flags=re.IGNORECASE)
        updated_here = 0
        for idx in range(0, len(segments) - 1, 2):
            record_text = segments[idx]
            if not record_text.strip():
                continue
            call_m = STATION_CALLSIGN_RE.search(record_text)
            ref_m = MY_POTA_REF_RE.search(record_text)
            if call_m or not ref_m:
                continue  # 既にSTATION_CALLSIGNがある、またはMY_POTA_REFが無いレコードは対象外

            ref = ref_m.group(1).strip().upper()
            info = (park_info or {}).get(ref)
            if info is None:
                warnings.append(
                    f"{path} レコード{idx // 2}: 公園REF {ref} がpota.app APIに見つからないため"
                    f"STATION_CALLSIGNを追加できません")
                continue

            codes = [c.strip() for c in (info.get("locdesc") or "").split(",") if c.strip()]
            if not codes:
                warnings.append(
                    f"{path} レコード{idx // 2}: 公園REF {ref} のPOTA県コードが不明なため"
                    f"STATION_CALLSIGNを追加できません")
                continue

            area_pref = (code_to_area_pref or {}).get(codes[0])
            if area_pref is None:
                warnings.append(
                    f"{path} レコード{idx // 2}: POTA県コード{codes[0]}に対応するJARLエリア番号が"
                    f"JARL_AREA_POTA_MAPPINGに見つからないためSTATION_CALLSIGNを追加できません"
                    f"(公園REF {ref})")
                continue
            area, _pref = area_pref
            if len(codes) > 1:
                warnings.append(
                    f"{path} レコード{idx // 2}: 公園REF {ref} は複数県({','.join(codes)})にまたがるため、"
                    f"先頭のPOTA県コード{codes[0]}のエリア番号{area}を使用してSTATION_CALLSIGNを追加します")

            value = f"{station_callsign_base}/{area}"
            tag = f"<station_callsign:{len(value.encode('utf-8'))}>{value}"

            nl_m = re.match(r"^(.*?)([\r\n]*)$", record_text, re.DOTALL)
            content, trailing_nl = nl_m.group(1), nl_m.group(2)
            content = content.rstrip(" ")
            segments[idx] = f"{content} {tag} {trailing_nl}"
            updated_here += 1
            warnings.append(f"{path} レコード{idx // 2}: STATION_CALLSIGNタグ {value} を追加しました")

        if updated_here == 0:
            continue

        backup_path = path + ".bak"
        try:
            with open(backup_path, "w", encoding="utf-8") as bf:
                bf.write(text)
        except OSError as e:
            warnings.append(f"{path}: バックアップ作成失敗のため書き込みを中止しました ({e})")
            continue

        new_text = header_full + "".join(segments)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
        updated_total += updated_here
        if not quiet:
            print(f"[info] {path}: STATION_CALLSIGNタグを{updated_here}件追加して更新しました"
                  f"(バックアップ: {backup_path})", file=sys.stderr)

    if not quiet:
        for w in warnings:
            print(f"[warn] {w}", file=sys.stderr)
        print(f"[info] -u指定によるSTATION_CALLSIGN追加: 合計{updated_total}件", file=sys.stderr)
    return updated_total


def area_from_station_callsign(callsign):
    """STATION_CALLSIGN(例: JQ1UCG/2, JQ1UCG/2/P)からJARLエリア番号(1文字)を抽出する。
    見つからない場合はNoneを返す。"""
    parts = callsign.strip().upper().split("/")
    for part in parts[1:]:
        if len(part) == 1 and part.isdigit():
            return part
    return None


def extract_pairs_from_adif(adif_path, warnings, station_callsign_base=None,
                             park_info=None, code_to_area_pref=None):
    """1つのADIFファイルから (エリア番号, 公園REF番号) のペアの集合を抽出する。
    MY_POTA_REFが無いレコードは対象外として黙ってスキップする。
    STATION_CALLSIGNからエリア番号を判定できないレコードは、station_callsign_base
    (-s指定)が無ければスキップする。station_callsign_base指定時は、MY_POTA_REFの
    公園REF番号をpark_info(pota.app API取得結果)のlocationDescで引き、
    code_to_area_pref(JARL_AREA_POTA_MAPPING)でJARLエリア番号に変換し、
    station_callsign_base + "/" + エリア番号 のSTATION_CALLSIGNを補完したものとして扱う
    (公園が複数県にまたがる場合は県コードごとに複数ペアを追加する)。"""
    pairs = set()
    try:
        with open(adif_path, encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError as e:
        warnings.append(f"{adif_path}: 読み込み失敗 ({e})")
        return pairs

    # ヘッダー(<EOH>より前)を除外してレコード分割
    body = re.split(r"<eoh>", data, maxsplit=1, flags=re.IGNORECASE)[-1]
    for i, record in enumerate(re.split(r"<eor>", body, flags=re.IGNORECASE)):
        if not record.strip():
            continue
        call_m = STATION_CALLSIGN_RE.search(record)
        ref_m = MY_POTA_REF_RE.search(record)
        if not ref_m:
            continue  # POTA以外のQSOレコードは対象外(黙ってスキップ)

        ref = ref_m.group(1).strip().upper()

        if not call_m:
            if station_callsign_base is None:
                warnings.append(f"{adif_path} レコード{i}: STATION_CALLSIGNタグが無いためスキップ")
                continue

            info = (park_info or {}).get(ref)
            if info is None:
                warnings.append(
                    f"{adif_path} レコード{i}: STATION_CALLSIGNタグが無く、"
                    f"公園REF {ref} もpota.app APIに情報が無いため-s補完できずスキップ")
                continue

            codes = [c.strip() for c in (info.get("locdesc") or "").split(",") if c.strip()]
            if not codes:
                warnings.append(
                    f"{adif_path} レコード{i}: STATION_CALLSIGNタグが無く、"
                    f"公園REF {ref} のPOTA県コードが不明なため-s補完できずスキップ")
                continue

            for code in codes:
                area_pref = (code_to_area_pref or {}).get(code)
                if area_pref is None:
                    warnings.append(
                        f"{adif_path} レコード{i}: POTA県コード{code}に対応するJARLエリア番号が"
                        f"JARL_AREA_POTA_MAPPINGに見つからないため-s補完できずスキップ"
                        f"(公園REF {ref})")
                    continue
                area, _pref = area_pref
                synthesized = f"{station_callsign_base}/{area}"
                warnings.append(
                    f"{adif_path} レコード{i}: STATION_CALLSIGNタグが無いため"
                    f"-s指定により{synthesized}として補完(公園REF {ref}, POTA県コード{code})")
                pairs.add((area, ref))
            continue

        area = area_from_station_callsign(call_m.group(1))
        if area is None:
            warnings.append(
                f"{adif_path} レコード{i}: STATION_CALLSIGN='{call_m.group(1)}' から"
                f"エリア番号を判定できないためスキップ")
            continue
        pairs.add((area, ref))
    return pairs


def scan_directory(root_dir, exclude_dirnames=None, quiet=False,
                    station_callsign_base=None, park_info=None, code_to_area_pref=None):
    """root_dir配下の全ADIFファイルから (エリア番号, 公園REF番号) の集合を作る。
    exclude_dirnamesに含まれる名前のディレクトリは検索対象から除外する。
    station_callsign_base以降の引数はextract_pairs_from_adifの-s補完にそのまま渡す。"""
    files = find_adif_files(root_dir, exclude_dirnames=exclude_dirnames)
    if not quiet:
        if exclude_dirnames:
            print(f"[info] 除外ディレクトリ名: {sorted(exclude_dirnames)}", file=sys.stderr)
        print(f"[info] ADIFファイル {len(files)}件を検出", file=sys.stderr)
    all_pairs = set()
    warnings = []
    for path in files:
        pairs = extract_pairs_from_adif(path, warnings, station_callsign_base=station_callsign_base,
                                         park_info=park_info, code_to_area_pref=code_to_area_pref)
        all_pairs |= pairs
    if not quiet:
        for w in warnings:
            print(f"[warn] {w}", file=sys.stderr)
        print(f"[info] (エリア,公園REF) のユニークな組み合わせ {len(all_pairs)}件を抽出", file=sys.stderr)
    return all_pairs


def scan_files(file_paths, quiet=False,
                station_callsign_base=None, park_info=None, code_to_area_pref=None):
    """-i/--input で指定された個別ADIFファイルのみから (エリア番号, 公園REF番号) の集合を作る。
    ディレクトリの再帰検索は行わない(-i指定時はadif_rootと排他)。
    station_callsign_base以降の引数はextract_pairs_from_adifの-s補完にそのまま渡す。"""
    warnings = []
    files = resolve_input_files(file_paths, warnings)
    if not quiet:
        print(f"[info] -i指定によりADIFファイル {len(files)}件を対象とします"
              f"(ディレクトリ再帰検索は行いません)", file=sys.stderr)
    all_pairs = set()
    for path in files:
        pairs = extract_pairs_from_adif(path, warnings, station_callsign_base=station_callsign_base,
                                         park_info=park_info, code_to_area_pref=code_to_area_pref)
        all_pairs |= pairs
    if not quiet:
        for w in warnings:
            print(f"[warn] {w}", file=sys.stderr)
        print(f"[info] (エリア,公園REF) のユニークな組み合わせ {len(all_pairs)}件を抽出", file=sys.stderr)
    return all_pairs


# ---------------------------------------------------------------------------
# 2. 既存出力CSVの読み込み(差分判定用)
# ---------------------------------------------------------------------------

def load_existing_csv(path):
    """既存のPOTA-REF.csvを読み込み、(既存(エリア,REF)の集合, 既存の全行リスト) を返す。
    ファイルが無ければ (空集合, 空リスト) を返す。"""
    if path is None or not os.path.exists(path):
        return set(), []
    existing_pairs = set()
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            rows.append(row)
            existing_pairs.add((row[0], row[1]))
    return existing_pairs, rows


# ---------------------------------------------------------------------------
# 3. pota.app APIから日本全公園情報を取得(新規公園REFのみ使用)
# ---------------------------------------------------------------------------

def fetch_jp_parks_from_api(quiet=False):
    """https://api.pota.app/program/parks/JP から日本全公園情報を取得し、
    match_pota_jarl_area.load_park_info() と同じ形式の辞書
    {reference: {"locdesc":..., "lat":..., "lon":...}} を返す。"""
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
        # APIのフィールド名はドキュメント未整備のため複数の候補名を試す。
        # 実機で実行し実際のJSON構造と差異があれば、この対応表のみ調整すればよい。
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


# ---------------------------------------------------------------------------
# 4. 新規行の組み立て
# ---------------------------------------------------------------------------

def build_new_rows(new_pairs, park_info, code_to_area_pref, muni_lookup, quiet=False):
    """新規に追加する (area, ref) ペアから出力行を組み立てる。
    match_pota_jarl_area.build_table() と同様に、公園が複数県にまたがる場合は
    県コードごとに複数行を出力するが、JARLエリア番号はSTATION_CALLSIGN由来のものを使う。"""
    rows = []
    missing_park_info = []
    for area, ref in sorted(new_pairs):
        info = park_info.get(ref)
        if info is None:
            missing_park_info.append(ref)
            rows.append([area, ref, "(pota.app APIに該当なし)", "", ""])
            continue

        codes = [c.strip() for c in (info.get("locdesc") or "").split(",") if c.strip()]
        if not codes:
            codes = ["?"]
        entry = muni_lookup.get(ref) or {}
        muni = entry.get("muni") or ""
        jarl = entry.get("jarl") or ""
        for code in codes:
            _, pref = code_to_area_pref.get(code, ("?", code))
            pref_str = f"{code}({pref})"
            rows.append([area, ref, pref_str, muni, jarl])

    if missing_park_info and not quiet:
        print(f"[warn] pota.app APIに情報が無い公園REF: {sorted(set(missing_park_info))}", file=sys.stderr)
    return rows


FULL_OUTPUT_FILENAME = "POTA-REF.full.csv"


def build_full_rows(park_info, code_to_area_pref, muni_lookup, quiet=False):
    """pota.app APIで取得した日本全公園情報から、全公園分の行を組み立てる(-f/--full用)。
    ADIFのSTATION_CALLSIGN情報が無いため、JARLエリア番号はPOTA県コード
    (locationDesc)からjarl_area_pota_mappingで求める(通常のADIF由来モードとは
    エリア番号の求め方が異なる点に注意)。"""
    rows = []
    for ref in sorted(park_info):
        info = park_info[ref]
        codes = [c.strip() for c in (info.get("locdesc") or "").split(",") if c.strip()]
        if not codes:
            codes = ["?"]
        entry = muni_lookup.get(ref) or {}
        muni = entry.get("muni") or ""
        jarl = entry.get("jarl") or ""
        for code in codes:
            area, pref = code_to_area_pref.get(code, ("?", code))
            pref_str = f"{code}({pref})"
            rows.append([area, ref, pref_str, muni, jarl])
    if not quiet:
        print(f"[info] 全公園{len(park_info)}件から{len(rows)}行を組み立て", file=sys.stderr)
    return rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="ADIFを再帰検索してSTATION_CALLSIGN/MY_POTA_REFからPOTA-REF.csvを差分更新する")
    root_group = parser.add_mutually_exclusive_group()
    root_group.add_argument("adif_root", nargs="?",
                             help="ADIFファイルを再帰検索するルートディレクトリ(-f/-i指定時は不要。-iとは排他)")
    root_group.add_argument("-i", "--input", metavar="ADIF_FILE", action="append", default=[],
                             help="読み込むADIFファイルを個別に指定する(複数回指定可)。"
                                  "指定時はディレクトリの再帰検索を行わず、指定したファイルのみを読み込む"
                                  "(adif_rootディレクトリ指定とは排他。-eは無視される)")
    parser.add_argument("-f", "--full", action="store_true",
                         help=f"ADIFを検索せず、pota.app APIから日本の全POTA対象公園リストを取得し、"
                              f"それを元に{FULL_OUTPUT_FILENAME}を新規作成する"
                              f"(既存の-o出力ファイルは読み込まない。-oや-n/-aは無視される)")
    parser.add_argument("-o", "--output", metavar="PATH",
                         help="出力CSV(既存ファイルがあれば読み込んで差分追記。省略時は新規分のみ標準出力へ)")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("-n", "--new", action="store_true",
                             help="既存の-o出力ファイルを無視して新規作成(上書き)する")
    mode_group.add_argument("-a", "--append", action="store_true",
                             help="既存の-o出力ファイルへ差分追記する(デフォルト動作の明示指定)")
    parser.add_argument("--parks-json", metavar="PATH",
                         help="pota.app API取得結果のオフラインJSONキャッシュ(存在すれば再利用、無ければ取得して保存)")
    parser.add_argument("--muni-cache", metavar="PATH",
                         help="市町村名/JCC・JCG・AJA番号の問い合わせ結果JSONキャッシュ")
    parser.add_argument("--no-muni", action="store_true",
                         help="市町村名・JCC/JCG/AJA番号の問い合わせを行わない")
    parser.add_argument("-j", "--jobs", type=int, default=DEFAULT_JOBS,
                         help=f"GSI逆ジオコーディングAPIへの並列問い合わせ数(デフォルト: {DEFAULT_JOBS})")
    parser.add_argument("-s", "--station-callsign", metavar="CALLSIGN",
                         help="STATION_CALLSIGNタグが無いADIFレコードを補完する際のベースコールサイン"
                              "(例: -s JL1ICY)。指定時、STATION_CALLSIGNタグが無くMY_POTA_REFタグは"
                              "あるレコードについて、公園REF番号をpota.app APIで検索してPOTA県コード"
                              "(locationDesc)を求め、JARL_AREA_POTA_MAPPINGでJARLエリア番号に変換し、"
                              "CALLSIGN/エリア番号 の形でSTATION_CALLSIGNを補完してから抽出する"
                              "(未指定時、STATION_CALLSIGNタグが無いレコードは従来通りスキップされる。"
                              "-f/--full指定時は無視される)")
    parser.add_argument("-u", "--update-station-callsign", action="store_true",
                         dest="update_station_callsign",
                         help="-s/--station-callsignで補完されるSTATION_CALLSIGNタグを、実際に"
                              "-i/--inputで指定したADIFファイルへ書き込んで更新する"
                              "(-s/--station-callsignおよび-i/--inputと同時指定が必須)。"
                              "-u未指定時、-sは集計・表示のみ行い元ファイルは変更しない。"
                              "上書き前に元ファイルを<path>.bakとしてバックアップする")
    parser.add_argument("--dry-run", action="store_true",
                         help="ファイルへの書き込みを行わず、追加(または新規作成)される内容のみ表示する")
    parser.add_argument("-e", "--exclude", metavar="DIRNAME", action="append", default=[],
                         help="この名前(完全一致)のディレクトリを検索対象から除外する。"
                              "複数回指定可能(例: -e POTA-Gifu -e \"POTA-Aichi,Gifu,Mie\")。"
                              "-i指定時はディレクトリ検索自体を行わないため無視される")
    parser.add_argument("-q", "--quiet", action="store_true", help="進捗表示を抑制する")
    parser.add_argument("--version", action="store_true", help="バージョン番号を表示して終了")
    return parser


def run_full_mode(args, quiet=False):
    """-f/--full: pota.app APIから日本の全POTA対象公園を取得し、
    既存のPOTA-REF.csv(-o)は一切読み込まずFULL_OUTPUT_FILENAMEへ新規作成する。"""
    code_to_area_pref = load_jarl_area_mapping_static()

    park_info = load_park_info_cached(args.parks_json, quiet=quiet)
    if park_info is None:
        print("[error] 公園情報を取得できなかったため終了します", file=sys.stderr)
        sys.exit(1)

    cache = load_muni_cache(args.muni_cache)
    if args.no_muni:
        muni_lookup = {}
    else:
        all_refs = sorted(park_info)
        muni_master = load_muni_master(verbose=not quiet)
        geolonia_pref_cities = load_geolonia_pref_cities(verbose=not quiet)
        jarl_master = load_jarl_award_master(verbose=not quiet)
        award_map, jarl_award_map = build_muni_award_unit_map(
            muni_master, geolonia_pref_cities, jarl_master, verbose=not quiet)
        resolve_all_municipalities(
            all_refs, park_info, cache, award_map, jarl_award_map,
            jobs=args.jobs, quiet=quiet)
        muni_lookup = cache
        if args.muni_cache:
            save_muni_cache(args.muni_cache, cache)

    rows = build_full_rows(park_info, code_to_area_pref, muni_lookup, quiet=quiet)
    rows.sort(key=lambda r: (r[0], r[1], r[2]))

    if args.dry_run:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
        return

    with open(FULL_OUTPUT_FILENAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    if not quiet:
        print(f"[info] {FULL_OUTPUT_FILENAME} を新規作成しました(合計{len(rows)}行)", file=sys.stderr)


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    quiet = args.quiet

    if args.full:
        run_full_mode(args, quiet=quiet)
        sys.exit(0)

    if not args.adif_root and not args.input:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    if args.input and args.exclude and not quiet:
        print("[info] -i指定のため-e/--excludeは無視されます", file=sys.stderr)

    if args.update_station_callsign:
        if not args.station_callsign:
            parser.error("-u/--update-station-callsignは-s/--station-callsignと同時に指定してください")
        if not args.input:
            parser.error("-u/--update-station-callsignは-i/--input指定時のみ使用できます"
                          "(ディレクトリ再帰検索には対応していません)")

    code_to_area_pref = load_jarl_area_mapping_static()

    # -s指定時は、STATION_CALLSIGN欠落レコードの補完にpota.app APIの公園情報が
    # 抽出段階(ステップ1)で必要になるため、通常より前倒しで取得しておく
    # (見つかれば、後段ステップ3での再取得は不要になる)
    park_info = None
    if args.station_callsign:
        if not quiet:
            print(f"[info] -s指定: STATION_CALLSIGNタグが無いレコードは"
                  f"{args.station_callsign}/<エリア番号>として補完します", file=sys.stderr)
        park_info = load_park_info_cached(args.parks_json, quiet=quiet)
        if park_info is None:
            print("[error] 公園情報を取得できなかったため終了します(-s指定時は事前取得が必要です)",
                  file=sys.stderr)
            sys.exit(1)

    # 1. ADIF検索(-i指定時は明示ファイルのみ。それ以外はディレクトリ再帰検索)
    if args.input:
        found_pairs = scan_files(args.input, quiet=quiet, station_callsign_base=args.station_callsign,
                                  park_info=park_info, code_to_area_pref=code_to_area_pref)
    else:
        found_pairs = scan_directory(args.adif_root, exclude_dirnames=args.exclude, quiet=quiet,
                                      station_callsign_base=args.station_callsign,
                                      park_info=park_info, code_to_area_pref=code_to_area_pref)

    # -u指定時: -sによる補完を集計・表示のみで終わらせず、-iで指定したADIFファイルへ
    # 実際にSTATION_CALLSIGNタグを書き込む(要-s+-i、事前にparser.errorで検証済み)
    if args.update_station_callsign:
        update_input_files_station_callsign(
            args.input, args.station_callsign, park_info, code_to_area_pref, quiet=quiet)

    # 2. 既存CSVとの差分判定(-n/--new指定時は既存ファイルの内容を無視する)
    if args.new:
        existing_pairs, existing_rows = set(), []
        if not quiet and args.output and os.path.exists(args.output):
            print(f"[info] -n指定のため既存の{args.output}の内容は無視して新規作成します", file=sys.stderr)
    else:
        existing_pairs, existing_rows = load_existing_csv(args.output)
    new_pairs = {(a, r) for (a, r) in found_pairs if (a, r) not in existing_pairs}
    if not quiet:
        print(f"[info] 既存{len(existing_pairs)}件 / 新規{len(new_pairs)}件", file=sys.stderr)

    if not new_pairs:
        if not quiet:
            print("[info] 新規に追加すべき (エリア,公園REF) はありません", file=sys.stderr)
        if not args.dry_run and args.output:
            pass  # 変更なしなので書き込み不要
        sys.exit(0)

    # 3. 新規公園REFの情報取得(pota.app API、必要な場合のみ。-s指定によりステップ1で
    #    既に取得済みならAPIへの再問い合わせはせずそれを再利用する)
    if park_info is None:
        park_info = load_park_info_cached(args.parks_json, quiet=quiet)
    if park_info is None:
        print("[error] 公園情報を取得できなかったため終了します", file=sys.stderr)
        sys.exit(1)

    # 4. 市町村名・JCC/JCG/AJA変換(新規公園REFのみ)
    new_refs = sorted({ref for (_, ref) in new_pairs})
    cache = load_muni_cache(args.muni_cache)
    if args.no_muni:
        muni_lookup = {}
    else:
        muni_master = load_muni_master(verbose=not quiet)
        geolonia_pref_cities = load_geolonia_pref_cities(verbose=not quiet)
        jarl_master = load_jarl_award_master(verbose=not quiet)
        award_map, jarl_award_map = build_muni_award_unit_map(
            muni_master, geolonia_pref_cities, jarl_master, verbose=not quiet)
        resolve_all_municipalities(
            new_refs, park_info, cache, award_map, jarl_award_map,
            jobs=args.jobs, quiet=quiet)
        muni_lookup = cache
        if args.muni_cache:
            save_muni_cache(args.muni_cache, cache)

    # 5. 新規行の組み立て
    new_rows = build_new_rows(new_pairs, park_info, code_to_area_pref, muni_lookup, quiet=quiet)

    if not quiet:
        print(f"[info] 追加行数: {len(new_rows)}", file=sys.stderr)

    if args.dry_run:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for row in new_rows:
            writer.writerow(row)
        sys.exit(0)

    if args.output:
        all_rows = existing_rows + new_rows
        all_rows.sort(key=lambda r: (r[0], r[1], r[2]))
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(all_rows)
        if not quiet:
            print(f"[info] {args.output} を更新しました(合計{len(all_rows)}行)", file=sys.stderr)
    else:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for row in new_rows:
            writer.writerow(row)


if __name__ == "__main__":
    main()
