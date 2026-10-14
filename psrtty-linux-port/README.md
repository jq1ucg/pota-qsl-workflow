# PSRTTY 1.15 Linux移植版（非公式）

追加機能: **Hamlib rigctld へのTCP接続**（1.1: Yaesu/Kenwood、1.2: ICOMも対応。下記「rigctld接続」）。

- 基礎: PSRTTY（H.Tanaka / JH1HST、AKIHABARA-GIKEN）配布アーカイブ `PSRTTY-1.16.tar.gz`（内部 `__version__` は 1.15）
- 対象OS: Ubuntu 26.04 LTS（Ubuntu 24.04 LTS 上で動作確認）、x86_64 / aarch64
- 名称: **PSRTTY 1.15 Linux port 1.2**（作者公式版・作者保証版ではありません）
- 元ソースの `docs/DISTRIBUTION_TERMS.txt` に従い、改変点は本書の「変更点」、元の著作権表示は保持しています。
  配布する場合は、作者への事前通知と、改良版ソース全体・ビルド用スクリプトの提供が必要です。

## 導入

```bash
# 元の tar.gz を展開し、パッチを当てる
tar xzf PSRTTY-1.16.tar.gz && cd PSRTTY-1.16
patch -p1 < /path/to/psrtty-linux.patch   # 新規ファイル（*.sh, requirements-linux.txt 等）も含む
chmod +x *.sh
./install-linux.sh --hamlib            # apt依存 + venv + Hamlib 5(git)ビルド→/usr/local + デスクトップ登録
sudo usermod -aG dialout $USER         # CAT/外部PTTのシリアルに必須（再ログイン）
./psrtty.sh
```

`--no-apt` で apt を省略。Hamlib 5 が既にシステムにある（`ldconfig -p | grep libhamlib.so.5`）なら `--hamlib` は不要です。

## rigctld接続（TCP）

設定画面「無線機」タブで機種（Yaesu/Kenwood/ICOMのいずれか）を選ぶと **接続方式** が現れます。

| 項目 | 内容 |
|---|---|
| 接続方式 | `シリアル（直接）`（従来）／`rigctld（TCP）` |
| rigctldホスト | 既定 `127.0.0.1`（他PC・VMのrigctldも可） |
| rigctldポート | 既定 `4532`（1～65535） |

- 機種は **rigctld側につないだ無線機** に合わせて選びます（フィルター幅・データモード等の機種別制御に使用）。COMポートとCAT速度は不要です。
- 例: `rigctld -m 1035 -r /dev/ttyUSB0 -s 38400` を起動 → PSRTTYで `FT-991/A`・`rigctld（TCP）`・`127.0.0.1:4532`
- 実装: Hamlib の NET rigctl バックエンド（`RIG_MODEL_NETRIGCTL`=2）を動的リンクした libhamlib 経由で使用します。接続前に3秒のTCP疎通確認を行い、失敗時は接続先付きのエラーを表示します。周波数・PTT・モード・NB/NR・フィルター・ALC/SWR/PWRは従来のHamlib機種と同じ経路です。
### ICOMをrigctld経由で使う場合（1.2）

ICOMの標準経路（`civ.py`）はシリアルへCI-Vフレームを直接書き込むためTCPに載せられません。rigctld接続時は `IcomHamlibController` が Hamlib API 経由で同じ操作を行います（シリアル接続時は従来のCI-Vのまま）。

| 機能 | rigctld経由の扱い |
|---|---|
| 周波数・PTT・モード（LSB/USB/LSB-D/USB-D）・DATA ON | 対応（Hamlibの PKTLSB/PKTUSB） |
| NB / NR / AN(=ANF) / MN | 対応（Hamlibの対応状況次第。読めなければ「—」） |
| アンテナチューナー | `TUNER` 機能と `RIG_OP_TUNE` で対応（機種・Hamlib依存、**dummy rigでは未検証**） |
| ALC | Hamlibの値(0～1)を×255してCI-Vの0～255相当で表示 |
| SWR / PWR | Hamlibの校正値。機種別の独自校正表は使わない |
| **FIL1～3の切替** | **不可**（常に「不明」扱い） |
| CI-Vアドレス・CI-V速度・COMポート | 不要（画面から隠れる） |
| PTT方式 | `CI-V`（=rigctld経由）と`外部接続`のみ。RTS/DTRは不可（ローカルのシリアルが無いため） |
| 外部PTT専用機（IC-706など） | `外部接続`のみ（従来どおり） |
| 周波数範囲 | 100 kHz～15 GHz（IC-905等に対応） |

- ICOMのLAN接続（IC-705/7300/9700などの独自UDPプロトコル）はrigctldを介する場合のみ利用できます（Hamlib/wfview側の機能に依存）。
- 設定保存: `radio.link` (`serial`/`rigctld`)、`radio.rigctld_host`、`radio.rigctld_port`。プロファイルごとに保存され、ALC較正の識別にも含まれます（シリアル利用者の既存較正は影響なし）。
- 8言語（ja/en/ru/zh/ko/id/th/es）の文言を追加（`rigctld.*`）。ロシア語以下6言語の訳は機械的な短文で、ネイティブ確認はしていません。
- 注意: rigctld は認証も暗号化も持ちません。信頼できるネットワーク内でのみ使用してください。
- 検証: Hamlib 5.0.0~git の `rigctld -m 1`（ダミー無線機）に実接続し、Yaesu/ICOMの両方で、接続・周波数設定/取得（144 MHz、10 GHz帯含む）・PTT ON/OFF・モード4種の設定と読み戻し・データモード・接続拒否時のエラー表示を確認。**実機は未検証**。

## 変更点（Windows依存の除去）

| 箇所 | 内容 |
|---|---|
| `psrtty/paths.py` | `data_root()` 追加。config/logdata/var は従来どおり配置フォルダー、書き込み不可なら `~/.local/share/psrtty`。`PSRTTY_HOME` で上書き可 |
| `psrtty/app.py` | 保存先を `data_root()` へ。Linuxで `setDesktopFileName("psrtty")`（アイコン/タスクバー対応） |
| `psrtty/i18n.py`, `ui/cabrillo_dialog.py` | `var/` ログを `data_root()` へ |
| `psrtty/hamlib_radio.py` | **Hamlib 5 をシステムの共有ライブラリとして動的リンク**（探索順: `PSRTTY_HAMLIB` → `libhamlib.so.5` → `find_library` → `libhamlib.so.4` → 同梱 `lib/hamlib/`）。`rig_get_caps()` で機種の有無を事前確認（未対応Hamlibで `rig_init()` が**プロセスごと abort**する問題の回避）。`token`を`long`で受け渡し（Hamlib 5のABI）。`runtime_version()`追加 |
| `psrtty/ui/about_dialog.py` | Linuxでは実際にロードされたlibhamlibの版（`rig_version()`）を表示 |
| `psrtty/civ.py` | `/dev/ttyUSB*` 等に権限がない場合、候補表示と接続失敗に `dialout` の案内を追加 |
| `psrtty/ui/guide.py`, `frequency_guide.py` | 日本語フォントに `Noto Sans CJK JP` を追加（Yu Gothic UIが無い環境） |
| `psrtty/hamlib_radio.py` `radio.py` `alc_display.py` `ui/settings_dialog.py` `ui/main_window.py` `language/*.json` `english_fallback.py` | rigctld（TCP）接続（上記） |
| 新規 | `install-linux.sh` `build-hamlib-linux.sh` `psrtty.sh` `psrtty.desktop.in` `requirements-linux.txt` |

既に移植済みだった部分（変更不要）: PortAudio経由の音声（Windows固有のWASAPI処理は `sys.platform` 分岐済み）、
ライブラリ探索（`libhamlib-4.so` → `ctypes.util.find_library`）、`QDesktopServices` によるフォルダー/ファイル表示、
pyserialによるCI-V/CAT、`QLocalServer`（Unixドメインソケット）による二重起動防止。

## Linuxで使えない／無効な機能

- **アプリ内バージョンアップ（ZIP更新）**: Windows EXE専用。Linuxでは案内ダイアログのみ（更新はソース差し替え）
- **Turbo HAMLOG連携**: `WM_COPYDATA` を使うWindows専用。Linuxでは `LinkError` で無効。HAMLOG CSV/ADIF出力は使用可
- **PyInstaller / `build-windows.ps1` / `psrtty.spec`**: Windows用。Linuxはソース+venv配布（`psrtty.exe` 前提の更新機構が絡むため意図的に非凍結）
- zLog/Z-Server連携、プリンター(シリアル)、Cabrillo、ADIFは動作に依存なし（TCP/シリアルのみ）

## 既知の注意

1. **Hamlib（動的リンク）**: `rigctld Hamlib 5.0.0~git 2026-10-12 SHA=d099fe27d` 相当の `libhamlib.so.5` をシステムから読み込みます。
   同梱しません。上流 `master` のSONAME（`libhamlib.so.5`）・関数シグネチャ・全13機種のモデル番号は実ビルドで確認済みですが、
   **指定コミット d099fe27d 自体は上流 master 上に見つからず（手元の master は 470518f, 2026-10-11）未検証**です。
   Ubuntu標準のHamlib 4.5.5 では FTX-1 が存在せず、本移植版は選択時にエラー表示します（元のままだとアプリごと落ちます）。
   別の場所のHamlibを使う場合: `PSRTTY_HAMLIB=/path/to/libhamlib.so.5 ./psrtty.sh`
2. **音声デバイス**: Linuxでは ALSA/PulseAudio/PipeWire の全ホストAPIが `名前 [API #番号]` で列挙されます。
   アプリは固定サンプルレート・モノラルで開くため、`hw:` 直指定より `pipewire` / `pulse` / `default` を選ぶのが安全です。
3. **Wayland（26.04のGNOMEは既定）**: ウィンドウ位置の保存復元・前面化はコンポジターが制限します。`--reset-window` は有効。
   XWaylandで動かす場合は `QT_QPA_PLATFORM=xcb ./psrtty.sh`。
4. **シリアルのDTR/RTS**: LinuxではOS側が open 時に両線をアサートします。PTTをRTS/DTRで制御する配線では、接続時に一瞬送信状態になる可能性があります（実機未検証）。
5. **ModemManager**: 一部USBシリアルを横取りしてCATが開けないことがあります（`sudo systemctl stop ModemManager` で切り分け）。
6. 実機（無線機・声音デバイス）での送受信は**未検証**です。UI・設定・ロジックのテストのみ実施しました。

## 検証結果

Hamlib 5.0.0~git（上流master）をビルドし `LD_LIBRARY_PATH` で動的ロードして確認: バージョン取得、全13機種の存在、ダミー無線機での周波数の設定/取得、`rig_set_conf`。

元ソースの `python -m unittest discover`（643件, `QT_QPA_PLATFORM=offscreen`）: 642件成功。
失敗1件 `test_connect_failure_ui_keeps_ticking` はタイマー回数に依存する時間依存テスト（移植前の元ソースでも同じ結果）。
移植後（rigctld・ICOM対応込み）: 669件中、時間/環境依存の2件（`test_connect_failure_ui_keeps_ticking`、`test_v60` のマウスカーソル形状）を除き成功。後者は単独実行で成功。実rigctldを使うテストは `rigctld` がPATHに無い場合スキップ。

## このディレクトリについて

元ソースの配布条件（無改変再配布不可、改良版は条件付き）のため、**PSRTTY本体は含めず差分パッチのみ**を置いています。
`psrtty-linux.patch` は `diff -ruN` 形式で、元の `PSRTTY-1.16.tar.gz` に `patch -p1` で適用します。
