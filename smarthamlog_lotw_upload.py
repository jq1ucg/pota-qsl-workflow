#!/usr/bin/env python3
"""
smarthamlog_lotw_upload.py

Smart HAMLOG が出力した ADIF を LoTW 向けに整形し、TQSL の CLI 経由で
署名・アップロードする。

LoTW へのアップロードは TQSL による署名(.tq8化)が必須のため、本スクリプトは
LoTW の Web API を直接叩かず、インストール済みの TQSL(tqsl / tqsl.exe)を
サブプロセスとして呼び出す。

Smart HAMLOG 出力 ADIF の特徴と、本スクリプトの対処:
  1. 公園REFが MY_POTA_REF ではなく MY_SIG_INFO(MY_SIG=POTA)に入っている
       -> MY_POTA_REF を補完(polo-lotw-fill.py の突合ロジックを流用して
          MY_STATE / MY_CNTY / jccjcgaja を付与。-p 指定時)
  2. FREQ に不正値がある(例: "7.005.5" = 7.0055MHz のkHz区切り風表記)
       -> 2個目以降の "." を除去して "7.0055" に修正。直せない値/BANDと
          矛盾する値は FREQ を削除(TQSL は BAND から処理できる)
  3. D-STAR が MODE=DIGITALVOICE + SUBMODE=DSTAR
       -> 既定ではそのまま(MODE=DIGITALVOICE, SUBMODE=DSTAR)。
          --dv-mode で MODE=DSTAR / FM への変換も可
  4. レコードが QSO 日時の降順など不揃い
       -> QSO_DATE → TIME_ON 順にソート
  5. STATION_CALLSIGN は JQ1UCG/0 のような運用地サフィックス付き
       -> STATION_CALLSIGN ごとにファイルを分け、TQSL の Station Location
          もそれぞれ指定してアップロード
  6. 相手局の SIG/SIG_INFO(P2P)が入っているレコードがある
       -> そのまま保持(LoTW側では無視される)

動作モード(安全のためデフォルトはアップロードしない):
  (指定なし)     ADIFの整形・出力のみ。実行するTQSLコマンドを表示(dry-run)
  --sign-only    TQSLで署名して .tq8 を作成するだけ(アップロードしない)
  --upload       TQSLで署名してLoTWへアップロードする

使い方:
  # 整形のみ(内容確認)
  python3 smarthamlog_lotw_upload.py -p POTA-REF.csv *.adi -o output

  # アップロード(Station Location 名を指定)
  python3 smarthamlog_lotw_upload.py -p POTA-REF.csv *.adi -o output \\
      --upload --location "JQ1UCG/0=JQ1UCG-0 Portable"

  # TQSL の場所とパスワード(環境変数)を指定
  TQSL_PASS=xxxx python3 smarthamlog_lotw_upload.py *.adi --upload \\
      --tqsl "C:/Program Files (x86)/TrustedQSL/tqsl.exe" --password-env TQSL_PASS

オプション:
  input                   Smart HAMLOG ADIFファイル(複数指定可)
  -o, --output-dir DIR    整形後ADIF/.tq8/ログの出力先(default: output)
  -p, --potatable PATH    POTA-REF.csv。指定時のみ MY_STATE/MY_CNTY/jccjcgaja を付与
  --pota-field NAME       公園REFの出力タグ名 (default: my_pota_ref)
  --jarl-field NAME       JCC/JCG/AJA用タグ名 (default: jccjcgaja)
  -c, --choice SPEC       複数県にまたがる公園REFの選択行 (例: JP-0209:1)
  --overwrite             既存の MY_STATE/MY_CNTY/JCC等も上書き
  --dv-mode MODE          DIGITALVOICE+DSTARの扱い (keep|dstar|fm, default: keep)
                            keep : MODE=DIGITALVOICE, SUBMODE=DSTAR のまま
                                   (ADIF 3.1系の正式形式)
                            dstar: MODE=DSTAR(単独モード)に変換, SUBMODEは削除
                            fm   : MODE=FM に変換, SUBMODEは削除
                          ※TQSLが受理しない場合は、TQSLの設定データ更新、または
                            TQSL「環境設定 > ADIFモード」での割当て、もしくは
                            --dv-mode dstar を試す
  --dedupe                STATION+CALL+日時(分)+BAND+MODE+SUBMODE が同一なら重複除去
  --start-date YYYYMMDD   この日付以降のQSOのみ対象 (TQSL -b にも渡す)
  --end-date YYYYMMDD     この日付以前のQSOのみ対象 (TQSL -e にも渡す)
  --sign-only             TQSLで署名のみ行い .tq8 を出力(アップロードしない)
  --upload                TQSLで署名してLoTWへアップロード
  --tqsl PATH             TQSL実行ファイル (default: PATHから tqsl を探索)
  --location SPEC         STATION_CALLSIGN=Station Location名 (複数指定可)
  --location-template T   --location未指定局の名称テンプレート
                          ({station}=STATION_CALLSIGN, {safe}="/"を"-"に置換,
                          {area}=末尾"/n"の数字)
                          (default: "POTA-{area}AREA"。"/n"が無い局は "{station}")
  --password-env VAR      証明書パスワードを読む環境変数名(コマンドラインに直接は渡さない)
  --action ACTION         TQSLの重複/期間外QSOの扱い all|compliant|abort
                          (default: compliant)
  --cnty-format FMT       MY_CNTYの出力形式 (state|plain, default: state)
                            state: "09,0908"(県番号,JCC。従来形式)
                            plain: "0908"(接頭辞なし)
                          ※TQSLが『'US County State' の値として '09' ... 正しくありません』
                            と言う場合は plain を試す
  --location-mismatch M   ADIFの局所在地(MY_STATE/MY_CNTY等)とStation Locationが
                          食い違う場合のTQSLの扱い。TQSLの -f に渡す
                          (update|report|ignore|none, default: update)
                            update: ADIFの値でStation Locationの値を上書きして署名
                            report: 食い違いを報告(エラー扱い)
                            ignore: ADIFの局所在地情報を無視しStation Locationの値を使用
                            none  : -f を渡さない(古いTQSLで -f が使えない場合)
  --tqsl-extra "ARGS"     TQSLへ追加で渡す引数(shlex分割)
  --timeout SEC           TQSL 1回あたりのタイムアウト秒 (default: 300)
  --version               バージョン番号を表示して終了

終了コード:
  0 正常 / 1 入力・整形エラー / 2 TQSL実行エラー(アップロード失敗含む)
  3 TQSLが署名対象QSOを0件と判断(全QSOが重複または期間外。TQSL終了コード8)

変更履歴:
  1.6.0  --cnty-format を追加(state|plain, default: state)。plain指定で MY_CNTY を
         "0908" の形(県番号の接頭辞なし)で出力する。TQSLが "09,0908" のカンマ前を
         米国の州として解釈し『'US County State' の値として '09' ... 正しくありません』
         で停止する場合に使う。TQSLが署名対象0件/エラーを返した場合、TQSLの
         出力(エラー本文)の末尾をコンソールにも表示する。
  1.5.0  TQSL終了コード8(全QSOが重複/期間外=署名対象0件)を [ok] ではなく
         [warn] として表示し、終了コード3を返すようにした。--sign-only で
         .tq8 が作られなかった場合も検出する。対処のヒント(--action all、
         証明書のQSO有効期間確認)を表示する。
  1.4.0  --location-mismatch を追加(default: update)。TQSLの -f オプションとして
         渡し、ADIFのMY_STATE/MY_CNTY(公園ごとのJCC等)でStation Locationの値を
         上書きして署名する。これが無いとTQSLが「局の所在地は QSOデータの詳細と
         一致していない('JA City/Gun/Ku' の値は '0906' ですが、QSO データの値は
         '0908' です)」で停止する。
  1.3.0  --dv-modeの既定を dstar から keep に戻した(MODE=DIGITALVOICE +
         SUBMODE=DSTARのまま送る。dstar/fmは明示指定で利用可)。
  1.2.0  Station Locationの既定名を STATION_CALLSIGN の "/n" から
         "POTA-nAREA"(例: JQ1UCG/0 -> POTA-0AREA)で決めるようにした
         (--location-templateの既定を "POTA-{area}AREA" に変更。"/n" の無い
         局は {station} にフォールバック。{area} プレースホルダを追加)。
  1.1.0  --dv-modeの既定を keep から dstar に変更(D-STARをMODE=DSTARで送る)。
         同一公園REFが複数行ある場合、STATION_CALLSIGNの"/n"とPOTA-REF.csvの
         JARLエリア番号で候補行を自動的に絞り込むようにした(例: JQ1UCG/0 の
         JP-0012 は長野側、JQ1UCG/1 の JP-0012 は群馬側)。-c指定がある公園は
         従来どおり絞り込まず-cの行番号を優先。
  1.0.0  初版。Smart HAMLOG ADIF の整形(MY_POTA_REF補完, FREQ修正,
         DSTAR変換, MY_STATE/MY_CNTY/JCC付与)とTQSL CLI経由の署名/アップロード
"""

import argparse
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

VERSION = "1.6.0"

EOR_RE = re.compile(rb"<eor>", re.IGNORECASE)
EOH_RE = re.compile(rb"<eoh>", re.IGNORECASE)
FIELD_RE = re.compile(rb"<(\w+):(\d+)(?::[^>]*)?>")

# TQSL終了コード(TQSLマニュアル記載)
TQSL_EXIT = {
    0: "成功",
    1: "ユーザーによりキャンセル",
    2: "LoTWにより拒否された",
    3: "LoTWサーバーから想定外の応答",
    4: "TQSLエラー",
    5: "TQSLlibエラー",
    6: "入力ファイルを開けない",
    7: "出力ファイルを開けない",
    8: "全QSOが重複または期間外(アップロード対象なし)",
    9: "一部QSOが重複または期間外(残りはアップロード済み)",
    10: "コマンド構文エラー",
    11: "LoTW接続エラー",
}
# 8/9 は「新規なし/一部重複」であり致命的失敗ではない
TQSL_OK_CODES = {0, 8, 9}

# バンド別の周波数範囲(MHz)。FREQとBANDの矛盾検出用
BAND_RANGES = {
    "2190M": (0.1357, 0.1378), "630M": (0.472, 0.479), "560M": (0.501, 0.504),
    "160M": (1.8, 2.0), "80M": (3.5, 4.0), "60M": (5.06, 5.45), "40M": (7.0, 7.3),
    "30M": (10.1, 10.15), "20M": (14.0, 14.35), "17M": (18.068, 18.168),
    "15M": (21.0, 21.45), "12M": (24.89, 24.99), "10M": (28.0, 29.7),
    "6M": (50.0, 54.0), "4M": (70.0, 71.0), "2M": (144.0, 148.0),
    "1.25M": (222.0, 225.0), "70CM": (420.0, 450.0), "33CM": (902.0, 928.0),
    "23CM": (1240.0, 1300.0),
}


# ---------------------------------------------------------------- ADIF 入出力
def split_records(data: bytes):
    """バイト列からヘッダを除去し、<EOR>区切りのレコード(bytes)リストを返す"""
    m = EOH_RE.search(data)
    body = data[m.end():] if m else data
    return [c.strip() for c in EOR_RE.split(body) if c.strip()]


def parse_fields(rec: bytes):
    """[(TAG, value), ...] を出現順で返す。長さはバイト長で解釈(ADIF仕様)"""
    out, pos = [], 0
    while True:
        m = FIELD_RE.search(rec, pos)
        if not m:
            break
        n = int(m.group(2))
        start = m.end()
        out.append((m.group(1).decode("ascii").upper(),
                    rec[start:start + n].decode("utf-8", errors="replace")))
        pos = start + n
    return out


def get(fields, tag, default=""):
    for t, v in fields:
        if t == tag:
            return v
    return default


def set_field(fields, tag, value, overwrite=True):
    """tagがあれば置換(overwrite時)、無ければ末尾に追加。変更したらTrue"""
    for i, (t, _) in enumerate(fields):
        if t == tag:
            if overwrite:
                fields[i] = (tag, value)
                return True
            return False
    fields.append((tag, value))
    return True


def del_field(fields, tag):
    fields[:] = [(t, v) for t, v in fields if t != tag]


def format_record(fields) -> str:
    parts = [f"<{t}:{len(v.encode('utf-8'))}>{v}" for t, v in fields]
    return " ".join(parts) + " <EOR>\n"


def build_header(station: str) -> str:
    pid = "smarthamlog_lotw_upload"
    ver = "3.1.4"
    return (f"ADIF for LoTW by {pid}.py v{VERSION} (STATION_CALLSIGN={station})\n"
            f"<ADIF_VER:{len(ver)}>{ver}\n"
            f"<PROGRAMID:{len(pid)}>{pid}\n"
            f"<PROGRAMVERSION:{len(VERSION)}>{VERSION}\n"
            "<EOH>\n\n")


# ---------------------------------------------------------------- 整形処理
def fix_freq(freq: str, band: str):
    """(新しいFREQ or None, 変更内容メッセージ or None) を返す。
    Noneは「FREQを削除」の意味。"""
    orig = freq.strip()
    new = orig
    msg = None
    if not re.fullmatch(r"\d+(\.\d+)?", new):
        if re.fullmatch(r"[\d.]+", new) and new.count(".") > 1:
            head, *rest = new.split(".")
            new = head + "." + "".join(rest)  # 7.005.5 -> 7.0055
            msg = f"FREQ修正 '{orig}' -> '{new}'"
        else:
            return None, f"FREQ '{orig}' は数値として不正なため削除"
    rng = BAND_RANGES.get(band.upper())
    if rng and not (rng[0] <= float(new) <= rng[1]):
        return None, f"FREQ '{new}' がBAND {band} の範囲外のため削除"
    return new, msg


def load_fill_module():
    """polo-lotw-fill.py(ハイフン入りファイル名)を動的import"""
    path = Path(__file__).resolve().with_name("polo-lotw-fill.py")
    if not path.exists():
        sys.exit(f"[error] polo-lotw-fill.py が見つかりません: {path}")
    spec = importlib.util.spec_from_file_location("polo_lotw_fill", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def normalize_record(fields, args, ctx, label):
    """1レコードを整形する。致命的な欠落があれば理由文字列、問題なければNoneを返す"""
    w = ctx["warnings"]
    st = ctx["stats"]

    # --- 必須項目の検査
    for tag in ("STATION_CALLSIGN", "CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE"):
        if not get(fields, tag).strip():
            return f"{tag} がありません"
    if not re.fullmatch(r"\d{8}", get(fields, "QSO_DATE")):
        return f"QSO_DATE が不正です: {get(fields, 'QSO_DATE')}"
    if not re.fullmatch(r"\d{4}(\d{2})?", get(fields, "TIME_ON")):
        return f"TIME_ON が不正です: {get(fields, 'TIME_ON')}"

    # --- FREQ修正
    if get(fields, "FREQ"):
        new, msg = fix_freq(get(fields, "FREQ"), get(fields, "BAND"))
        if msg:
            st["freq_fixed" if new else "freq_dropped"] += 1
            if not new:
                w.append(f"[warn] {label}: {msg}")
        if new is None:
            del_field(fields, "FREQ")
        else:
            set_field(fields, "FREQ", new)

    # --- DIGITALVOICE/DSTAR
    if get(fields, "MODE").upper() == "DIGITALVOICE" and args.dv_mode != "keep":
        sub = get(fields, "SUBMODE").upper()
        if sub == "DSTAR":
            set_field(fields, "MODE", "DSTAR" if args.dv_mode == "dstar" else "FM")
            del_field(fields, "SUBMODE")
            st["dv_converted"] += 1

    # --- 公園REF補完 (MY_SIG=POTA, MY_SIG_INFO)
    pota_tag = args.pota_field.upper()
    if not get(fields, pota_tag) and get(fields, "MY_SIG").upper() == "POTA" \
            and get(fields, "MY_SIG_INFO").strip():
        ref = get(fields, "MY_SIG_INFO").strip().upper()
        if "," in ref:
            first = ref.split(",")[0].strip()
            w.append(f"[warn] {label}: MY_SIG_INFOに複数の公園REF({ref})。"
                     f"突合には先頭({first})を使用")
        set_field(fields, pota_tag, ref)
        st["pota_ref_added"] += 1

    # --- MY_STATE / MY_CNTY / JCC (POTA-REF.csv 突合)
    if ctx["ref_table"] is not None and get(fields, pota_tag):
        park = get(fields, pota_tag).split(",")[0].strip().upper()
        cands = ctx["ref_table"].get(park)
        if not cands:
            st["unmatched_park"] += 1
            w.append(f"[warn] {label}: 公園REF {park} がPOTA-REF.csvに見つかりません")
        else:
            mod = ctx["fill"]
            # 同一公園が複数行ある場合、/n サフィックスとJARLエリア番号で絞り込む
            m_area = re.search(r"/(\d)$", get(fields, "STATION_CALLSIGN").strip())
            if len(cands) > 1 and m_area and park not in ctx["choices"]:
                narrowed = [c for c in cands if c["area"] == m_area.group(1)]
                if narrowed:
                    cands = narrowed
            entry = mod.select_ref_entry(park, cands, get(fields, "COMMENT"),
                                         ctx["choices"], label, w)
            digits = mod.digits_only(entry["jarl"])
            if not digits:
                st["jarl_missing"] += 1
                w.append(f"[warn] {label}: 公園REF {park} のJCC/JCG/AJA情報が空のため"
                         f"MY_STATE/MY_CNTYを付与できません")
            else:
                state = digits[:2]
                if set_field(fields, "MY_STATE", state, args.overwrite):
                    st["state_added"] += 1
                cnty = digits if args.cnty_format == "plain" else f"{state},{digits}"
                if set_field(fields, "MY_CNTY", cnty, args.overwrite):
                    st["cnty_added"] += 1
                set_field(fields, args.jarl_field.upper(), entry["jarl"], args.overwrite)
    elif ctx["ref_table"] is not None:
        st["no_pota_ref"] += 1

    return None


# ---------------------------------------------------------------- TQSL
def find_tqsl(path_arg):
    if path_arg:
        p = shutil.which(path_arg) or (path_arg if os.path.exists(path_arg) else None)
        return p
    found = shutil.which("tqsl") or shutil.which("tqsl.exe")
    if found:
        return found
    for cand in (r"C:\Program Files (x86)\TrustedQSL\tqsl.exe",
                 r"C:\Program Files\TrustedQSL\tqsl.exe",
                 "/Applications/TrustedQSL/tqsl.app/Contents/MacOS/tqsl",
                 "/usr/local/bin/tqsl", "/usr/bin/tqsl"):
        if os.path.exists(cand):
            return cand
    return None


def parse_locations(specs):
    locs = {}
    for s in specs or []:
        if "=" not in s:
            sys.exit(f"[error] --location の形式が不正です(STATION=名称): '{s}'")
        k, v = s.split("=", 1)
        locs[k.strip().upper()] = v.strip()
    return locs


def build_tqsl_cmd(tqsl, adif_path, location, args, tq8_path=None):
    cmd = [tqsl, "-d", "-x", "-q", "-a", args.action, "-l", location]
    if args.location_mismatch != "none":
        cmd += ["-f", args.location_mismatch]
    if args.start_date:
        cmd += ["-b", args.start_date]
    if args.end_date:
        cmd += ["-e", args.end_date]
    if tq8_path:
        cmd += ["-o", str(tq8_path)]
    else:
        cmd += ["-u"]
    if args.tqsl_extra:
        cmd += shlex.split(args.tqsl_extra)
    cmd.append(str(adif_path))
    return cmd


def mask_cmd(cmd):
    """表示用。パスワード引数は伏せる"""
    out, skip = [], False
    for c in cmd:
        out.append("****" if skip else shlex.quote(c))
        skip = (c == "-p")
    return " ".join(out)


def run_tqsl(cmd, password, timeout):
    full = list(cmd)
    if password:
        full[1:1] = ["-p", password]
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "", f"タイムアウト({timeout}秒)"
    return r.returncode, r.stdout, r.stderr


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="+", help="Smart HAMLOG ADIFファイル(複数指定可)")
    ap.add_argument("-o", "--output-dir", default="output", metavar="DIR")
    ap.add_argument("-p", "--potatable", metavar="PATH")
    ap.add_argument("--pota-field", default="my_pota_ref")
    ap.add_argument("--jarl-field", default="jccjcgaja")
    ap.add_argument("-c", "--choice", metavar="SPEC")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dv-mode", choices=["keep", "dstar", "fm"], default="keep")
    ap.add_argument("--dedupe", action="store_true")
    ap.add_argument("--start-date", metavar="YYYYMMDD")
    ap.add_argument("--end-date", metavar="YYYYMMDD")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--sign-only", action="store_true")
    mode.add_argument("--upload", action="store_true")
    ap.add_argument("--tqsl", metavar="PATH")
    ap.add_argument("--location", action="append", metavar="SPEC")
    ap.add_argument("--location-template", default="POTA-{area}AREA")
    ap.add_argument("--password-env", metavar="VAR")
    ap.add_argument("--action", choices=["all", "compliant", "abort"], default="compliant")
    ap.add_argument("--cnty-format", default="state", choices=["state", "plain"])
    ap.add_argument("--location-mismatch", default="update",
                    choices=["update", "report", "ignore", "none"])
    ap.add_argument("--tqsl-extra", metavar="ARGS")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--version", action="version",
                    version=f"smarthamlog_lotw_upload.py {VERSION}")
    args = ap.parse_args()

    for name in ("start_date", "end_date"):
        v = getattr(args, name)
        if v and not re.fullmatch(r"\d{8}", v):
            sys.exit(f"[error] --{name.replace('_', '-')} はYYYYMMDD形式で指定してください: {v}")

    # --- POTA-REF.csv
    ctx = {"warnings": [], "ref_table": None, "fill": None, "choices": {},
           "stats": dict(total=0, freq_fixed=0, freq_dropped=0, dv_converted=0,
                         pota_ref_added=0, state_added=0, cnty_added=0,
                         unmatched_park=0, jarl_missing=0, no_pota_ref=0)}
    if args.potatable:
        ctx["fill"] = load_fill_module()
        ctx["ref_table"] = ctx["fill"].load_potatable(args.potatable)
        try:
            ctx["choices"] = ctx["fill"].parse_choice_spec(args.choice)
        except ValueError as e:
            sys.exit(f"[error] {e}")
        print(f"[info] POTA-REF.csv読み込み: {args.potatable} ({len(ctx['ref_table'])}件)",
              file=sys.stderr)
    elif args.choice:
        print("[warn] -c/--choice は -p/--potatable 指定時のみ有効です", file=sys.stderr)

    # --- 読み込み・整形
    by_station = {}
    skipped, dupes, out_of_range = 0, 0, 0
    seen = set()
    for fname in args.input:
        path = Path(fname)
        if not path.exists():
            sys.exit(f"[error] ファイルが見つかりません: {fname}")
        for i, rec in enumerate(split_records(path.read_bytes()), 1):
            ctx["stats"]["total"] += 1
            fields = parse_fields(rec)
            label = f"{path.name}#{i}(CALL={get(fields, 'CALL', '?')} " \
                    f"{get(fields, 'QSO_DATE', '?')} {get(fields, 'TIME_ON', '?')})"
            err = normalize_record(fields, args, ctx, label)
            if err:
                skipped += 1
                print(f"[error] {label}: {err} -> スキップ", file=sys.stderr)
                continue
            qd = get(fields, "QSO_DATE")
            if (args.start_date and qd < args.start_date) or \
               (args.end_date and qd > args.end_date):
                out_of_range += 1
                continue
            station = get(fields, "STATION_CALLSIGN").strip()
            if args.dedupe:
                key = (station.upper(), get(fields, "CALL").upper(), qd,
                       get(fields, "TIME_ON")[:4], get(fields, "BAND").upper(),
                       get(fields, "MODE").upper(), get(fields, "SUBMODE").upper())
                if key in seen:
                    dupes += 1
                    continue
                seen.add(key)
            by_station.setdefault(station, []).append(fields)

    for w in ctx["warnings"]:
        print(w, file=sys.stderr)
    if not by_station:
        sys.exit("[error] 出力対象のレコードがありません")

    # --- ファイル出力
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    locs = parse_locations(args.location)
    jobs = []
    for station in sorted(by_station):
        recs = sorted(by_station[station],
                      key=lambda f: (get(f, "QSO_DATE"), get(f, "TIME_ON")))
        safe = station.replace("/", "-")
        adif_path = out_dir / f"{today}-{safe}_lotw.adif"
        adif_path.write_text(build_header(station) + "".join(format_record(f) for f in recs),
                             encoding="utf-8")
        m_area = re.search(r"/(\d)$", station)
        if station.upper() in locs:
            location = locs[station.upper()]
        elif m_area or "{area}" not in args.location_template:
            location = args.location_template.format(
                station=station, safe=safe, area=m_area.group(1) if m_area else "")
        else:
            location = station  # "/n" が無い局はSTATION_CALLSIGNそのまま
        jobs.append((station, adif_path, location, len(recs)))

    st = ctx["stats"]
    print(f"整形完了(v{VERSION}): 入力 {st['total']} 件 / 出力 {sum(j[3] for j in jobs)} 件 / "
          f"スキップ {skipped} 件 / 期間外 {out_of_range} 件 / 重複除去 {dupes} 件\n"
          f"  FREQ修正 {st['freq_fixed']} / FREQ削除 {st['freq_dropped']} / "
          f"{args.pota_field}補完 {st['pota_ref_added']} / "
          f"MY_STATE付与 {st['state_added']} / MY_CNTY付与 {st['cnty_added']} / "
          f"DSTAR変換 {st['dv_converted']} / 公園REF未突合 {st['unmatched_park']} / "
          f"警告 {len(ctx['warnings'])}", file=sys.stderr)
    for station, p, loc, n in jobs:
        print(f"  {station}: {n} 件 -> {p}  (Station Location: {loc})", file=sys.stderr)

    # --- TQSL
    do_tqsl = args.upload or args.sign_only
    tqsl = find_tqsl(args.tqsl)
    if do_tqsl and not tqsl:
        sys.exit("[error] TQSLが見つかりません。--tqsl で tqsl(.exe) のパスを指定してください")
    password = None
    if args.password_env:
        password = os.environ.get(args.password_env)
        if password is None:
            sys.exit(f"[error] 環境変数 {args.password_env} が設定されていません")

    failed = False
    nothing = False
    for station, adif_path, location, n in jobs:
        tq8 = adif_path.with_suffix(".tq8") if args.sign_only else None
        cmd = build_tqsl_cmd(tqsl or "tqsl", adif_path, location, args, tq8)
        if not do_tqsl:
            print(f"[dry-run] {mask_cmd(cmd)}", file=sys.stderr)
            continue
        print(f"[tqsl] {station}: {n}件を{'署名' if args.sign_only else 'アップロード'}中 ...",
              file=sys.stderr)
        print(f"[tqsl] {mask_cmd(cmd)}", file=sys.stderr)
        rc, out, err = run_tqsl(cmd, password, args.timeout)
        log = out_dir / f"{adif_path.stem}.tqsl.log"
        log.write_text(f"cmd: {mask_cmd(cmd)}\nexit: {rc}\n--- stdout ---\n{out}\n"
                       f"--- stderr ---\n{err}\n", encoding="utf-8")
        if rc not in (None, 0, 9):
            tail = [l for l in (out + "\n" + err).splitlines()
                    if l.strip() and "QThreadStorage" not in l][-25:]
            if tail:
                print(f"--- TQSL出力(末尾) {station} ---\n" + "\n".join(tail) +
                      "\n---", file=sys.stderr)
        if rc is None:
            print(f"[error] {station}: {err}", file=sys.stderr)
            failed = True
        elif rc == 8:
            nothing = True
            print(f"[warn] {station}: exit=8 署名対象QSOが0件でした"
                  f"{'(.tq8は作成されていません)' if args.sign_only else '(何もアップロードされていません)'}"
                  f"  (ログ: {log})\n"
                  "       全QSOが『TQSLの署名済み記録との重複』か『証明書のQSO有効期間外』です。\n"
                  "       - 過去に同じQSOを署名/アップロード済みなら --action all で再署名できます\n"
                  "         (LoTW側で重複は無視されます)\n"
                  "       - それでも0件なら、TQSLで当該局の証明書のQSO開始/終了日を確認してください",
                  file=sys.stderr)
        elif rc in TQSL_OK_CODES:
            if args.sign_only and not tq8.exists():
                failed = True
                print(f"[error] {station}: exit={rc} ですが {tq8} が作成されていません  (ログ: {log})",
                      file=sys.stderr)
                continue
            print(f"[ok] {station}: exit={rc} {TQSL_EXIT[rc]}  (ログ: {log})", file=sys.stderr)
        else:
            print(f"[error] {station}: exit={rc} {TQSL_EXIT.get(rc, '不明')}  (ログ: {log})",
                  file=sys.stderr)
            if err.strip():
                print(err.strip(), file=sys.stderr)
            failed = True

    if not do_tqsl:
        print("[info] 実際に送るには --upload を付けて再実行してください", file=sys.stderr)
    sys.exit(2 if failed else (3 if nothing else 0))


if __name__ == "__main__":
    main()
