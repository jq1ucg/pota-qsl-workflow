# smarthamlog_lotw_upload.py 利用ガイド

Smart HAMLOG が出力した ADIF を LoTW 用に整形し、TQSL の CLI で署名・アップロードする
スクリプトです(v1.7.0 時点)。POTA 運用(JA)の QSO を、運用エリア(`/0` `/1` ...)ごとに
LoTW へ送る用途を想定しています。

## 1. 必要なもの

| 項目 | 内容 |
|---|---|
| Python | Python 3(標準ライブラリのみ。追加インストール不要) |
| TQSL | インストール済みで、証明書(`JQ1UCG/0` など)と Station Location を登録済みであること |
| `polo-lotw-fill.py` | **本スクリプトと同じフォルダ**に置く(関数を読み込んで使うため) |
| `POTA-REF.csv` | 公園REF → 県/市郡区/JCC の対応表(`-p` で指定。後述) |
| Station Location | TQSL 上の名前。既定では `STATION_CALLSIGN` の末尾 `/n` から `POTA-nAREA` を使う(例: `JQ1UCG/0` → `POTA-0AREA`) |

## 2. 基本の流れ

```bash
python3 smarthamlog_lotw_upload.py -p POTA-REF.csv ./adif-in/*.adi -o output --upload
```

1. Smart HAMLOG の ADIF(複数可)を読み込み、整形する
2. `STATION_CALLSIGN` ごとにファイルを分けて `output/YYYYMMDD-JQ1UCG-0_lotw.adif` のように書き出す
3. TQSL を呼び出して署名し、LoTW へアップロードする

**何も付けずに実行すると、整形とファイル出力だけを行い、送信しません**(dry-run)。
実行予定の TQSL コマンドが画面に表示されるので、内容を確認してから `--upload` を付けてください。

## 3. 動作モード

| 指定 | 動作 |
|---|---|
| (なし) | 整形・出力のみ。TQSL コマンドを表示(dry-run) |
| `--sign-only` | TQSL で署名して `.tq8` を作るだけ(送信しない) |
| `--upload` | TQSL で署名して LoTW へアップロード |

> **注意**: `--sign-only` で署名しただけでも、TQSL はそのQSOを「署名済み」と記録します。
> その後の `--upload` は「アップロードすべきQSOがない(終了コード8)」になります。
> 署名だけ試した後で送る場合は `--action all` を付けてください。
> 初回から送るつもりなら、`--sign-only` を挟まず `--upload` を直接使うのがおすすめです。

## 4. 日常の使い方(例)

### 4-1. 内容を確認する(送信しない)
```bash
python3 smarthamlog_lotw_upload.py -p POTA-REF.csv ./adif-in/*.adi -o output
```
`output/` の `*_lotw.adif` を開いて、`MY_STATE`・`MY_CNTY` などを確認します。

### 4-2. 送信する
```bash
python3 smarthamlog_lotw_upload.py -p POTA-REF.csv ./adif-in/*.adi -o output --upload
```

### 4-3. 署名済みのQSOを含めて再送する
```bash
python3 smarthamlog_lotw_upload.py -p POTA-REF.csv ./adif-in/*.adi -o output --upload --action all
```
LoTW 側で重複は無視されます。

### 4-4. 証明書にパスワードがある場合
パスワードはコマンドラインに直接書かず、環境変数で渡します。
```bash
TQSL_PASS='パスワード' python3 smarthamlog_lotw_upload.py -p POTA-REF.csv ./adif-in/*.adi -o output --upload --password-env TQSL_PASS
```

### 4-5. 日付で絞る
```bash
python3 smarthamlog_lotw_upload.py -p POTA-REF.csv ./adif-in/*.adi -o output --upload --start-date 20261107 --end-date 20261109
```

## 5. 主なオプション

| オプション | 説明 | 既定 |
|---|---|---|
| `-p, --potatable PATH` | `POTA-REF.csv`。指定すると `MY_STATE`/`MY_CNTY` などを付与 | なし |
| `-o, --output-dir DIR` | 整形後 ADIF / `.tq8` / ログの出力先 | `output` |
| `--upload` / `--sign-only` | 動作モード(上の表) | dry-run |
| `--action all\|compliant\|abort` | TQSL の重複・期間外QSOの扱い(`-a` に渡す) | `compliant` |
| `--tqsl PATH` | TQSL 実行ファイルのパス | PATH から探索 |
| `--location STATION=名前` | Station Location 名を個別指定(複数可) | 自動(`POTA-nAREA`) |
| `--location-template T` | 名前のテンプレート(`{station}` `{safe}` `{area}`) | `POTA-{area}AREA` |
| `--password-env VAR` | 証明書パスワードを読む環境変数名 | なし |
| `--cnty-format plain\|state` | `MY_CNTY` の形式。`plain` は `0908` | `plain` |
| `--location-mismatch update\|report\|ignore\|none` | ADIFの局所在地とStation Locationが食い違う場合の扱い(`-f` に渡す) | `update` |
| `--tqsl-config PATH` | TQSL の `config.xml`。県/市郡区の事前チェックに使う(`none` で無効) | 自動探索 |
| `--dv-mode keep\|dstar\|fm` | D-STAR の扱い | `keep` |
| `-c, --choice SPEC` | 複数県にまたがる公園の選択行(例: `JP-0209:2`) | なし |
| `--dedupe` | 同一QSO(局+相手+日時分+BAND+MODE+SUBMODE)を重複除去 | 無効 |
| `--start-date` / `--end-date` | 日付で絞る(YYYYMMDD。TQSL にも渡す) | なし |
| `--overwrite` | 既存の `MY_STATE`/`MY_CNTY` なども上書き | 無効 |
| `--tqsl-extra "ARGS"` | TQSL に追加で渡す引数 | なし |
| `--timeout SEC` | TQSL 1回あたりのタイムアウト | 300 |
| `--version` | バージョン表示 | |

詳細は `python3 smarthamlog_lotw_upload.py --help` を参照してください。

## 6. 自動で行う整形

| 内容 | 対処 |
|---|---|
| 公園番号が `MY_SIG_INFO`(`MY_SIG=POTA`)に入っている | `MY_POTA_REF` を補完 |
| `MY_STATE` / `MY_CNTY` が無い | `POTA-REF.csv` と突合して付与(`MY_STATE=09`、`MY_CNTY=0908`) |
| `FREQ` が不正(例: `7.005.5`) | `7.0055` に修正。直せない値や `BAND` と矛盾する値は削除 |
| 公園が複数エリアに登録されている(例: JP-0012) | `/n` サフィックスと CSV のエリア列で行を選ぶ |
| QSO の順序がばらばら | `QSO_DATE` → `TIME_ON` 順にソート |
| `STATION_CALLSIGN` が複数ある | 局ごとにファイルを分けて、それぞれ別々に署名・送信 |
| 相手局の `SIG` / `SIG_INFO`(P2P) | そのまま残す(LoTW 側では無視される) |

時刻は UTC として扱います(Smart HAMLOG の出力が UTC のため)。

## 7. POTA-REF.csv の書き方

列は次の5つです。

```
JARLエリア番号,公園REF番号,JP都道府県名,都道府県名+市区/郡名,JCC/JCG/AJA
0,JP-0012,JP-NN(長野県),長野県小諸市,JCC0908
1,JP-0012,JP-GM(群馬県),群馬県安中市,JCC1611
```

- **エリア列**は、運用した場所の JARL エリア(`/0`、`/1` など)です。同じ公園でもエリアが違えば別の行にします。
- JCC の数字部分から、`MY_STATE`(先頭2桁)と `MY_CNTY`(数字全体)が決まります。
- JCG 末尾の英字(例: `09015C`)は載せません(TQSL の選択肢に無いため)。
- 新しい公園は `build_pota_ref_csv.py` で自動追加できます。自動の値が実際の運用地と違う場合は、手で直してください。

## 8. 出力ファイル

`-o` で指定したフォルダに、次のファイルができます。

| ファイル | 内容 |
|---|---|
| `YYYYMMDD-JQ1UCG-0_lotw.adif` | 整形後の ADIF(局ごと) |
| `YYYYMMDD-JQ1UCG-0_lotw.tq8` | 署名済みファイル(`--sign-only` のとき) |
| `YYYYMMDD-JQ1UCG-0_lotw.tqsl.log` | TQSL の実行ログ(コマンド、終了コード、出力) |

## 9. 終了コード

| 終了コード | 意味 |
|---|---|
| 0 | 正常 |
| 1 | 入力・整形エラー |
| 2 | TQSL の実行エラー(アップロード失敗を含む) |
| 3 | TQSL が署名対象QSOを0件と判断(重複または期間外) |

## 10. トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `署名対象QSOが0件`(終了コード3、TQSL は 8) | 重複(署名済み)か期間外。画面に出る TQSL の出力を確認する。重複なら `--action all` を付ける。期間外なら TQSL で証明書の QSO 開始/終了日を確認する |
| 「局の所在地は QSO データの詳細と一致していない」 | `--location-mismatch update`(既定)で解消する。古い TQSL で `-f` が使えない場合は `none` にして、公園ごとに Station Location を用意する |
| 「'US County State' の値として '09' ... 正しくありません」 | `MY_CNTY` が `09,0908` の形式になっている。`--cnty-format plain`(既定)を使う |
| 「TQSLの選択肢に無い市郡区」の警告 | `POTA-REF.csv` の JCC が TQSL の選択肢に無い。TQSL の `config.xml` で値を確認して CSV を直す |
| 公園REF未突合の警告 | `POTA-REF.csv` に公園が無い。`build_pota_ref_csv.py` で追加する |
| 複数県にまたがる公園の警告 | `-c JP-0209:2` のように行番号を指定する(CSV 内で何番目の行か) |
| TQSL が見つからない | `--tqsl /usr/local/bin/tqsl` のようにパスを指定する(Windows は `tqsl.exe`) |
| D-STAR が受理されない | TQSL の設定データを更新する。それでも通らなければ `--dv-mode dstar`(または `fm`)を試す |

## 11. 既知の制限・未確認事項

- LoTW 上で D-STAR がどのモード区分(PHONE/DATA)に分類されるかは未確認です。
- 動作確認は TQSL 2.8.6(Linux)で行いました。他のバージョンでは `-f` や `-a` の挙動が違う可能性があります。
- 既存の `polo-lotw-fill.py` は、今も `MY_CNTY` を `09,0908`(カンマ付き)で出力します。TQSL 2.8.6 では
  この形式がエラーになるため、`polo-lotw-fill.py` の出力を TQSL へ直接渡す場合は再確認してください。
- 署名とアップロードの結果はTQSL側のログが正です。エラー時は `*.tqsl.log` を確認してください。
