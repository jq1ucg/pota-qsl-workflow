# IC-7610 CI-V / RTTY 調査メモ

根拠: `IC-7610_ENG_CI-V_4.pdf`(A7380-7EX-4, 2025-09) と `IC-7610_JPN_Supp_5.pdf`(A7379-2J-5, 202509)。
PDF本体は `docs/ic7610/` にローカル保存(著作権のため git 管理外 = `.git/info/exclude`)。
数値は両PDFのコマンド表(p.3-12)から読み取ったもの。

## 確認できたこと

| 項目 | CI-V | 備考 |
|---|---|---|
| RTTYモード設定 | `06`/`26` モード 04=RTTY, 08=RTTY-R | 周波数 `05`/`25` |
| PTT | `1C 00` 00=RX/01=TX | USB SENDのDTR/RTSでも可 |
| **USB Keying (RTTY)** | `1A 05 00 97` 00=OFF,01=USB1(A)DTR,02=USB1(A)RTS,03=USB1(B)DTR,04=USB1(B)RTS | USB SEND(`1A 05 00 95`)と同じ割当は不可 |
| USB SEND | `1A 05 00 95` 同上 | PTT用 |
| RTTY Mark周波数 | `1A 05 00 41` 00=1275,01=1615,02=2125Hz | |
| RTTY Shift | `1A 05 00 42` 00=170,01=200,02=425Hz | |
| RTTY Keying極性 | `1A 05 00 43` 00=Normal,01=Reverse | |
| デコード出力ボーレート | `1A 05 01 21` 00=4800,01=9600,02=19200,03=38400 | 「Connectors > Decode Baud Rate」 |
| 外部キーパッド RTTY | `1A 05 01 00` 00/01 | External Keypad > RTTY |
| RTTYデコード設定 | `1A 05 02 33`〜`02 48` | USOS、改行コード、ディドル、TX USOS、送信時自動CR+LF、タイムスタンプ、ログ等 |
| CI-V USBエコーバック | `1A 05 01 16` | |
| CI-V ボーレート条件 | 注7 | USB1ポート利用時は「CI-V USB Port」=Unlink from [REMOTE]、Baud=115200 |

## 確認できなかったこと(コマンド表に存在しない)

- RTTYのデコード済み文字をCI-Vで取得するコマンド: **無い**
- RTTY送信文字をCI-Vで渡すコマンド: **無い**
  - `17` は CW メッセージ専用(注3: CWモードかつ送信状態/ブレークインONのときのみ)。
  - `1A 02` は CW KEYER メモリー。`28` は音声TXメモリー。
- 「Decode Baud Rate」「External Keypad」がどの物理(仮想COM)ポートに出るかは、
  CI-V資料には書かれていない。**本体取扱説明書(USB(B)/外部キーパッド/デコード出力の章)で要確認。**
