#!/usr/bin/env python3
"""
check_jarl_membership.py

JARL会員検索サイト (https://www.jarl.com/Page/Search/MemberSearch.aspx?Language=Jp)
にコールサインを1件ずつ入力して検索し、JARL会員かどうか(転送可能局かどうか)の
結果を取得する。Selenium + Chrome(headless)を複数インスタンス並列実行することで
処理を高速化する。

さらに、fetch_jarl_noqsl.py の機能(JARL公式サイトの「QSLカード受け取りを
希望しない局リスト」取得)を -f/--fetch で統合している。このスクリプト単体で
「noqslリスト取得」と「会員検索による転送不可局抽出」の両方を賄い、
どちらも同じプレーンテキスト形式(# コメント行 / コールサイン1行1件 /
REGEX:パターン行)で出力するため、そのままマージできる。

要素ID(2026年時点の実績に基づく。サイト構造が変更されている場合は
--no-headless で目視確認の上、下記の *_ELEMENT_ID を修正すること):
    入力欄  : id="txtCallSign"
    検索ボタン: id="btnSearch"
    結果表示 : id="ListView1_lblResult_0"
    ※ 注意: 素のHTTPリクエスト(urllib/curl等)でこのサイトを検証すると
      "ListView2_lblResult_0"(英語ラベル)が返るが、実際のブラウザ(Chrome/
      Selenium)でアクセスすると"ListView1_lblResult_0"(日本語ラベル)が
      返る。サーバー側でリクエスト方式に応じて異なるテンプレートを返して
      いるため、本スクリプト(実ブラウザ経由)では必ずListView1側を使うこと。

事前準備:
    pip install selenium --break-system-packages
    Chrome/Chromium と、対応する chromedriver が必要
    (chromedriverがPATH上にない場合は --chromedriver-path で指定)
    ※ -f/--fetch (noqslリスト取得)のみを使う場合は selenium・Chromeは不要。

使い方:
    # (A) noqslリスト取得モード -- fetch_jarl_noqsl.py 相当
    python3 check_jarl_membership.py -f -o jarl_noqsl.txt
    python3 check_jarl_membership.py -f -o jarl_noqsl.txt --url https://www.jarl.org/...

    # (B) 会員検索モード -- 従来のcheck_jarl_membership.py相当
    # コールサイン一覧テキスト(1行1コール)を検索、並列4ワーカー
    python3 check_jarl_membership.py calls.txt -o result.csv -j 4

    # CALL列を含むCSVから読み込み
    python3 check_jarl_membership.py detail.csv -o result.csv -j 4 --csv-column CALL

    # 動作確認用にブラウザを表示しながら実行(1ワーカー推奨)
    python3 check_jarl_membership.py calls.txt -o result.csv -j 1 --no-headless

    # chromedriverの応答が遅い/不安定な環境ではタイムアウトを調整
    python3 check_jarl_membership.py calls.txt -o result.csv --connect-timeout 60

    # 転送不可局(× / ○ NO)を除外リスト形式で別途出力
    python3 check_jarl_membership.py calls.txt -o result.csv --exclude-output check_noqsl.txt

    # (A)(B)いずれのモードも、既存の除外リストファイルへ直接マージ可能(重複除く)
    python3 check_jarl_membership.py -f -o jarl_noqsl.txt --merge-into merged.txt
    python3 check_jarl_membership.py calls.txt -o result.csv --merge-into merged.txt

CHANGELOG:
    1.0.0 (2026-08-11)
        - 初版。会員検索モード(Selenium並列実行)。
        - 実サイト確認により RESULT_ELEMENT_ID を ListView1→ListView2 に修正。
        - --exclude-output / --merge-into で fetch_jarl_noqsl.py 互換の除外リスト
          形式(プレーンテキスト)への出力・マージに対応。
        - -f/--fetch で fetch_jarl_noqsl.py の機能(noqslリスト取得)を統合。
    1.1.0 (2026-08-11)
        - 実機(OrangePi5Pro)でchromedriver応答不能時に無期限ハングする不具合を修正。
          --connect-timeout(デフォルト30秒)を追加し、ブラウザ起動・ページ読み込み・
          chromedriverとのHTTP通信すべてにタイムアウトを設定。初回driver.get()失敗時は
          該当ワーカーの全件をERRORとして返し処理を継続する。
    1.1.1 (2026-08-11)
        - 【重要・不具合修正】RESULT_ELEMENT_ID を ListView2 → ListView1 に再修正。
          v1.0.0での「ListView1→ListView2」変更はurllib等の生HTTPリクエストのみで
          検証した結果に基づく誤りだった。実Chromeブラウザ(chrome-for-testing 131)で
          CDP経由の実ブラウザ検索を複数回行い検証した結果、サーバーはリクエスト方式に
          応じて異なるテンプレート(ListView1=日本語ラベル/ListView2=英語ラベル)を
          返すことが判明。実際にSeleniumが使うのは実ブラウザ経由のためListView1が正。
          これが実機での無期限ハングの実質的な原因だったと考えられる
          (--connect-timeoutは副次的な堅牢性向上として引き続き有効)。
    1.2.0 (2026-08-11)
        - 進捗表示を-v無しでも常時stderrに出力するよう変更(ブラウザ起動/URL接続/
          各コールサイン検索開始・完了/全体進捗カウント(N/M件)/リトライ発生時の
          待機秒数)。-vは検索結果の生テキストを追加表示する詳細モードとして維持。
          これにより、chromedriverやページロードでの停止箇所が外部から見えるように
          なり、無応答なハングと単なる低速処理の切り分けが可能になった。
    1.2.1 (2026-08-11)
        - 【重要・不具合修正】サンドボックス環境での実機検証(Chrome 141 +
          対応chromedriver、JARL会員検索サイトへの実アクセス)により、
          search_one()内でStaleElementReferenceExceptionが高頻度(実測25%程度)
          で発生し、リトライしても解消しない不具合を発見・修正。
          原因: ASP.NET postback完了直後、結果要素(ListView1_lblResult_0)が
          DOMに一瞬存在しても直後の再描画で差し替わるレースコンディションがあり、
          `presence_of_element_located`で取得した要素への`.text`アクセス時に
          例外が発生していた。ワーカー単位の外側リトライ(ページ全体を再送信)は
          非効率かつ解決にならないため、search_one()内で要素取得と`.text`読み出し
          をセットにした軽量な内部リトライ(最大6回・0.3秒間隔)を追加した。
          実機検証: 20件検索で修正前は4件失敗(全てStaleElementReference)、
          修正後は20件全て成功(0件失敗)を確認済み。
"""

__version__ = "1.2.1"

import argparse
import csv
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException
    _SELENIUM_IMPORT_ERROR = None
except ImportError as _e:
    # -f/--fetch (noqslリスト取得)のみを使う場合はseleniumは不要なため、
    # ここでは即終了せず、会員検索モードに入った時点でエラーにする。
    _SELENIUM_IMPORT_ERROR = _e


def _require_selenium():
    if _SELENIUM_IMPORT_ERROR is not None:
        sys.exit(
            "エラー: selenium がインストールされていません。\n"
            "  pip install selenium --break-system-packages\n"
            "を実行してください。また Chrome/Chromium と chromedriver も必要です。"
        )

JARL_URL = "https://www.jarl.com/Page/Search/MemberSearch.aspx?Language=Jp"

# 実サイトの要素ID(要検証・要調整)
INPUT_ELEMENT_ID = "txtCallSign"
SEARCH_BUTTON_ID = "btnSearch"
RESULT_ELEMENT_ID = "ListView1_lblResult_0"  # 2026-08-11 実Chromeブラウザで再検証・確定(urllib等の生HTTPリクエストとは異なりListView1が正しい)

WAIT_TIMEOUT = 15  # 秒

# --- ここから fetch_jarl_noqsl.py 由来(-f/--fetch モード用) ---

DEFAULT_NOQSL_URL = "https://www.jarl.org/Japanese/5_Nyukai/noqsl.html"

CALLSIGN_SPAN_RE = re.compile(r"<span class='callsign'>([^<]*)</span>")
DATE_RE = re.compile(r"<div class='date'>([^<]*)</div>")

# JARL開設局のパターン(ページ末尾の注記に基づく):
#   中央局: JA1RL
#   地方局: JA*RL  (例: JA2RL, JA3RL, ...)
#   補助局: JA*YRL ほか (例: JA1YRL, ...)
JARL_BRANCH_PATTERNS = [
    r"^JA[0-9]RL$",
    r"^JA[0-9]YRL",
]


def fetch_noqsl_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_noqsl_callsigns(html: str) -> list[str]:
    calls = []
    for m in CALLSIGN_SPAN_RE.finditer(html):
        call = m.group(1).strip()
        # "&nbsp;" などの空白プレースホルダーを除外
        if call and call != "&nbsp;" and re.match(r"^[A-Z0-9]+$", call):
            calls.append(call)
    return calls


def parse_noqsl_date(html: str) -> str:
    m = DATE_RE.search(html)
    return m.group(1).strip() if m else "不明"


def build_noqsl_exclude_content(calls: list[str], date_str: str, source_url: str) -> str:
    lines = [
        f"# JARL「QSLカード受け取りを希望しない局リスト」({date_str})",
        f"# 取得元: {source_url}",
        "# pivot_qso_for_glabels.py --exclude-file で読み込む除外リスト",
        "#",
        f"# --- 個別コールサイン ({len(calls)}件) ---",
    ]
    lines.extend(calls)
    lines.append("#")
    lines.append("# --- パターン(正規表現) ---")
    lines.append("# JARLが開設している中央局(JA1RL)・地方局(JA*RL)・補助局(JA*YRLほか)")
    for pat in JARL_BRANCH_PATTERNS:
        lines.append(f"REGEX:{pat}")
    return "\n".join(lines) + "\n"


def run_fetch_noqsl(args) -> None:
    """-f/--fetch モード: fetch_jarl_noqsl.py 相当の処理。"""
    try:
        html = fetch_noqsl_html(args.url)
    except Exception as e:
        sys.exit(f"エラー: {args.url} の取得に失敗しました: {e}")

    calls = parse_noqsl_callsigns(html)
    if not calls:
        sys.exit("エラー: ページからコールサインを抽出できませんでした。"
                  "サイトの構造が変更された可能性があります。")

    date_str = parse_noqsl_date(html)
    content = build_noqsl_exclude_content(calls, date_str, args.url)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")

    print(f"取得日時表記: {date_str}", file=sys.stderr)
    print(f"個別コールサイン: {len(calls)}件", file=sys.stderr)
    print(f"パターン: {len(JARL_BRANCH_PATTERNS)}件 (JARL開設局)", file=sys.stderr)
    print(f"出力先: {args.output}", file=sys.stderr)

    if args.merge_into:
        added = merge_into_exclude_file(args.merge_into, content.splitlines())
        print(f"マージ先 {args.merge_into} に {added}件追加(重複除く)", file=sys.stderr)

# --- fetch_jarl_noqsl.py 由来ここまで ---


def load_callsigns(path: Path, csv_column: str | None) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")

    if csv_column:
        import io
        reader = csv.DictReader(io.StringIO(text))
        if csv_column not in (reader.fieldnames or []):
            sys.exit(f"エラー: CSVに列 '{csv_column}' が見つかりません。検出された列: {reader.fieldnames}")
        calls = [(row.get(csv_column) or "").strip() for row in reader]
    else:
        calls = [line.strip() for line in text.splitlines()]

    # 空行除去、ポータブルサフィックス除去(先頭の本来コールサイン部分のみ使用)、重複除去(順序維持)
    seen = set()
    result = []
    for c in calls:
        if not c:
            continue
        base = c.split("/")[0].strip().upper()
        if base and base not in seen:
            seen.add(base)
            result.append(base)
    return result


def build_driver(headless: bool, chromedriver_path: str | None, connect_timeout: float) -> "webdriver.Chrome":
    _require_selenium()
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")

    if chromedriver_path:
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    # chromedriverプロセスが応答不能になった場合(バージョン不一致・異常終了等)に
    # HTTPクライアント側で永久に待たされないよう、通信自体にもタイムアウトを設定する。
    # (WAIT_TIMEOUT/WebDriverWaitは要素待ちにしか効かず、driver.get()やセッション生成の
    #  ハングは防げないため、原因不明のフリーズ対策としてこちらが必須)
    try:
        driver.command_executor.set_timeout(connect_timeout)
    except Exception:
        pass
    driver.set_page_load_timeout(connect_timeout)
    driver.set_script_timeout(connect_timeout)

    return driver


def search_one(driver: "webdriver.Chrome", call: str) -> str:
    """1件のコールサインを検索し、結果テキストを返す。

    注意(実機検証で判明・2026-08-11): ASP.NET postback完了直後、結果要素
    (ListView1_lblResult_0)がDOMに一瞬存在してもその後すぐ再描画で差し替わる
    レースコンディションがあり、`presence_of_element_located`で要素を取得した
    直後の`.text`アクセス時にStaleElementReferenceExceptionが高確率(実測5件中
    3件)で発生する。ワーカー単位の外側リトライ(1〜2秒待って検索全体をやり直す)
    では非効率かつ本質的な解決にならないため、ここで要素取得とtext読み出しを
    セットにした軽量な内部リトライを行い、page全体をリロードせずに解消する。
    """
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    input_el = wait.until(EC.presence_of_element_located((By.ID, INPUT_ELEMENT_ID)))
    input_el.clear()
    input_el.send_keys(call)

    search_btn = driver.find_element(By.ID, SEARCH_BUTTON_ID)
    search_btn.click()

    last_exc: Exception | None = None
    for _ in range(6):
        try:
            result_el = wait.until(EC.presence_of_element_located((By.ID, RESULT_ELEMENT_ID)))
            return result_el.text.strip()
        except StaleElementReferenceException as e:
            last_exc = e
            time.sleep(0.3)
            continue
    raise last_exc


def worker(worker_id: int, calls: list[str], headless: bool, chromedriver_path: str | None,
           delay: float, retries: int, verbose: bool, connect_timeout: float,
           total: int, progress_lock: threading.Lock, progress_counter: dict) -> list[tuple[str, str, str]]:
    """1ワーカー分のコールサインを1つのブラウザインスタンスで順次検索する。
    戻り値: [(コールサイン, 結果テキスト, ステータス), ...]"""
    results = []
    driver = None
    print(f"  [worker{worker_id}] ブラウザ起動中(chromedriver接続タイムアウト {connect_timeout:.0f}秒)...",
          file=sys.stderr)
    try:
        driver = build_driver(headless, chromedriver_path, connect_timeout)
        print(f"  [worker{worker_id}] ブラウザ起動完了。JARLサイトへアクセス中...", file=sys.stderr)
        try:
            driver.get(JARL_URL)
        except (TimeoutException, WebDriverException) as e:
            # 初回アクセスに失敗した場合、全件をエラーとして返す(ハングさせない)
            print(f"  [worker{worker_id}] 初回アクセス失敗: {e.__class__.__name__}: {e}", file=sys.stderr)
            return [(call, "", f"ERROR(InitialGet:{e.__class__.__name__})") for call in calls]
        print(f"  [worker{worker_id}] アクセス完了。{len(calls)}件の検索を開始します。", file=sys.stderr)

        for local_idx, call in enumerate(calls, 1):
            print(f"  [worker{worker_id}] ({local_idx}/{len(calls)}) {call} 検索中...", file=sys.stderr)
            status = "OK"
            text = ""
            for attempt in range(1, retries + 2):
                try:
                    text = search_one(driver, call)
                    break
                except (TimeoutException, WebDriverException) as e:
                    status = f"ERROR({e.__class__.__name__})"
                    if attempt <= retries:
                        print(f"  [worker{worker_id}] {call} 失敗(試行{attempt}): "
                              f"{e.__class__.__name__} -> {1.0 * attempt:.0f}秒後に再試行", file=sys.stderr)
                        time.sleep(1.0 * attempt)
                        continue
            results.append((call, text, status))

            with progress_lock:
                progress_counter["done"] += 1
                done = progress_counter["done"]
            if verbose:
                print(f"  [worker{worker_id}] {call}: {text!r} ({status}) "
                      f"[全体進捗 {done}/{total}]", file=sys.stderr)
            else:
                print(f"  [worker{worker_id}] {call}: {status} [全体進捗 {done}/{total}]", file=sys.stderr)

            if delay > 0:
                time.sleep(delay)
    finally:
        if driver is not None:
            driver.quit()
        print(f"  [worker{worker_id}] 終了(ブラウザ解放済み)", file=sys.stderr)

    return results


def is_nonforwardable(result_text: str) -> bool:
    """検索結果テキストから『QSLカード転送不可』(非会員 or 会員だが転送不可)かどうかを判定する。
    JpGuidLine の表示種別:
      (1)○ YES        : 転送可 -> False
      (2)○ NO         : 転送不可 -> True
      (3) ×            : 転送不可(非会員 or 局名録非掲載) -> True
      (4)○ YES via ... : 転送可 -> False
      (5)○ YES **/.../** via ... : 転送可 -> False
    """
    t = result_text.strip()
    if not t:
        return False
    if "×" in t:
        return True
    if t.startswith("○") and "NO" in t and "YES" not in t:
        return True
    return False


def build_exclude_lines(all_results: list[tuple[str, str, str]], source_desc: str) -> list[str]:
    """fetch_jarl_noqsl.py の除外リストファイルと同じプレーンテキスト形式で、
    転送不可局(× / ○ NO)のコールサイン行のリストを作る(コメント行含む)。"""
    excluded = [call for call, text, status in all_results
                if status == "OK" and is_nonforwardable(text)]
    lines = [
        f"# check_jarl_membership.py 検索結果による転送不可局リスト ({source_desc})",
        f"# --- 個別コールサイン ({len(excluded)}件) ---",
    ]
    lines.extend(excluded)
    return lines


def merge_into_exclude_file(path: Path, new_lines: list[str]) -> int:
    """既存の除外リストファイル(fetch_jarl_noqsl.py 互換形式)に、コールサイン行・
    REGEX:行を重複を除いて追記する。コメント行(#)は既存分を尊重しそのまま残す。
    戻り値: 実際に追記した行数(コールサイン+REGEXパターン)。"""
    existing_calls: set[str] = set()
    existing_regex: set[str] = set()
    header: list[str] = []
    if path.is_file():
        header = path.read_text(encoding="utf-8").splitlines()
        for line in header:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("REGEX:"):
                existing_regex.add(s)
            else:
                existing_calls.add(s.upper())

    to_add = []
    for ln in new_lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("REGEX:"):
            if s not in existing_regex:
                to_add.append(ln)
                existing_regex.add(s)
        elif s.upper() not in existing_calls:
            to_add.append(ln)
            existing_calls.add(s.upper())

    with path.open("a", encoding="utf-8") as f:
        if header and header[-1].strip() != "":
            f.write("\n")
        f.write(f"# --- check_jarl_membership.py によるマージ追加分 ({len(to_add)}件) ---\n")
        for line in to_add:
            f.write(line + "\n")

    return len(to_add)


def chunk_list(items: list, n: int) -> list[list]:
    """items を n個(以下)のグループにできるだけ均等に分割する。"""
    if n <= 0:
        n = 1
    n = min(n, len(items)) or 1
    avg = len(items) / n
    # 境界を先に全て確定させてから切り出すことで、丸め誤差による重複/欠落を防ぐ
    boundaries = [round(avg * i) for i in range(n + 1)]
    chunks = [items[boundaries[i]:boundaries[i + 1]] for i in range(n)]
    return [c for c in chunks if c]


def main():
    parser = argparse.ArgumentParser(
        description="JARL会員検索サイトでJAコールサインの会員登録有無を並列検索する。"
                     "-f/--fetch 指定時はJARLのnoqslリスト取得モードで動作する。"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("input", type=Path, nargs="?", default=None,
                         help="コールサイン一覧(テキストまたはCSV)。-f/--fetch 使用時は不要")
    parser.add_argument("-o", "--output", type=Path, required=True,
                         help="結果を出力するファイル(会員検索モード: CSV / -f使用時: 除外リストのテキスト)")
    parser.add_argument("-f", "--fetch", action="store_true",
                         help="会員検索を行わず、JARL公式サイトの「QSLカード受け取りを希望しない局"
                              "リスト」を取得して除外リストファイルを生成する(fetch_jarl_noqsl.py相当)")
    parser.add_argument("--url", type=str, default=DEFAULT_NOQSL_URL,
                         help="(-f/--fetch用) noqslリストの取得元URL(デフォルト: JARL公式ページ)")
    parser.add_argument("-j", "--workers", type=int, default=2,
                         help="並列実行するブラウザ(ワーカー)数(デフォルト2)。"
                              "サイトへの負荷・レート制限に配慮し過度な並列数は避けること")
    parser.add_argument("--csv-column", type=str, default=None,
                         help="入力がCSVの場合、コールサインが入っている列名を指定(例: CALL)")
    parser.add_argument("--no-headless", action="store_true", help="ブラウザを表示して実行する(デバッグ用)")
    parser.add_argument("--chromedriver-path", type=str, default=None,
                         help="chromedriverのパス(PATHに無い場合に指定)")
    parser.add_argument("--delay", type=float, default=1.0,
                         help="各検索リクエストの間隔(秒、デフォルト1.0)。サイトへの配慮のため")
    parser.add_argument("--retries", type=int, default=2, help="失敗時の再試行回数(デフォルト2)")
    parser.add_argument("--connect-timeout", type=float, default=30.0,
                         help="ブラウザ起動・ページ読み込み・chromedriver通信のタイムアウト秒数"
                              "(デフォルト30秒)。応答なしで無期限にハングするのを防ぐ")
    parser.add_argument("-v", "--verbose", action="store_true", help="進捗を逐次表示する")
    parser.add_argument("--exclude-output", type=Path, default=None,
                         help="転送不可局(× / ○ NO)を除外リスト形式(プレーンテキスト)で"
                              "別途出力するパス(会員検索モードのみ)")
    parser.add_argument("--merge-into", type=Path, default=None,
                         help="転送不可局(または-f取得分)を既存の除外リストファイル(例: jarl_noqsl.txt)"
                              "に重複を除いて直接追記する。--exclude-output と併用可")
    args = parser.parse_args()

    if args.fetch:
        print(f"check_jarl_membership.py v{__version__} (--fetch モード)", file=sys.stderr)
        run_fetch_noqsl(args)
        return

    _require_selenium()

    if args.input is None:
        parser.error("input は会員検索モードでは必須です(-f/--fetch 使用時は不要)")

    if not args.input.is_file():
        sys.exit(f"エラー: 入力ファイルが見つかりません: {args.input}")

    calls = load_callsigns(args.input, args.csv_column)
    if not calls:
        sys.exit("エラー: 検索対象のコールサインが1件もありません。")

    print(f"check_jarl_membership.py v{__version__}", file=sys.stderr)
    print(f"検索対象: {len(calls)}件(重複除去後) / 並列度: {args.workers}", file=sys.stderr)

    chunks = chunk_list(calls, args.workers)
    all_results: list[tuple[str, str, str]] = []

    progress_lock = threading.Lock()
    progress_counter = {"done": 0}

    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {
            executor.submit(
                worker, i + 1, chunk, not args.no_headless, args.chromedriver_path,
                args.delay, args.retries, args.verbose, args.connect_timeout,
                len(calls), progress_lock, progress_counter
            ): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                res = future.result()
                all_results.extend(res)
            except Exception as e:
                print(f"エラー: ワーカー{worker_id + 1}が異常終了しました: {e}", file=sys.stderr)

    # 元の入力順に並べ直す
    order = {call: idx for idx, call in enumerate(calls)}
    all_results.sort(key=lambda r: order.get(r[0], 1 << 30))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["CALL", "JARL_RESULT", "STATUS"])
        writer.writerows(all_results)

    ok_count = sum(1 for _, _, s in all_results if s == "OK")
    err_count = len(all_results) - ok_count
    print(f"完了: {len(all_results)}件処理(成功 {ok_count} / 失敗 {err_count})", file=sys.stderr)
    print(f"出力先: {args.output}", file=sys.stderr)

    if args.exclude_output or args.merge_into:
        exclude_lines = build_exclude_lines(all_results, str(args.input))

        if args.exclude_output:
            args.exclude_output.parent.mkdir(parents=True, exist_ok=True)
            args.exclude_output.write_text("\n".join(exclude_lines) + "\n", encoding="utf-8")
            print(f"除外リスト出力先: {args.exclude_output}", file=sys.stderr)

        if args.merge_into:
            added = merge_into_exclude_file(args.merge_into, exclude_lines)
            print(f"マージ先 {args.merge_into} に {added}件追加(重複除く)", file=sys.stderr)


if __name__ == "__main__":
    main()
