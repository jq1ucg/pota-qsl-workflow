# PSRTTY 1.15 Linux移植版（非公式）

- 基礎: PSRTTY（H.Tanaka / JH1HST、AKIHABARA-GIKEN）配布アーカイブ `PSRTTY-1.16.tar.gz`（内部 `__version__` は 1.15）
- 対象OS: Ubuntu 26.04 LTS（Ubuntu 24.04 LTS 上で動作確認）、x86_64 / aarch64
- 名称: **PSRTTY 1.15 Linux port 1.0**（作者公式版・作者保証版ではありません）
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
移植後（テスト6件追加・既存テスト4件を保存先変更/Hamlib探索順に合わせ修正）: 649件中648件成功、失敗は上記の同じ時間依存テスト1件のみ。

## このディレクトリについて

元ソースの配布条件（無改変再配布不可、改良版は条件付き）のため、**PSRTTY本体は含めず差分パッチのみ**を置いています。
`psrtty-linux.patch` は `diff -ruN` 形式で、元の `PSRTTY-1.16.tar.gz` に `patch -p1` で適用します。
