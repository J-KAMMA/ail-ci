"""Export a pinned, relocatable AIL source compiler snapshot."""
import hashlib
import json
from pathlib import Path


README = r"""# AIL ソースコンパイラ SDK

ソースコンパイラ、標準モジュール、言語例、C 接続例を同梱しています。
モデルやサービスは不要です。型の決まった言語subsetと下記CLIを使う入口です。
汎用言語全体の完成、全例・全環境での動作、C相当の全体効率を保証するものではありません。

checkのfield/element type_detailsは必要な型と実際の型を公開名で返します。actual=nullは未分類です。
append/storeは要素型、extendはリスト型同士を比べます。--repair-contextの元版確認とeditで修正できます。

## ビルド失敗をJSONで取得する

compile・compile-module・compile-library・compile-cに`--json`を付けると、失敗も`ail.build/1`のJSONで返します。
Cコンパイル・リンクを別段階として記録し、同じgcc呼出しで行う場合はcompile_linkと表示します。
型の詳細、元ソースのSHA、コンパイラの行・列・メッセージを返します。stdout/stderrは各512KiBまで保持し、切詰めを明示します。
`--debug-dir 新しいフォルダ`で生成Cと診断を保持できます。通常は追加の保存をしません。既存フォルダや出力は上書きしません。
一意に一致したC関数本文は元AILの宣言位置へ対応付けます。対応できない場所は不明で、AILの厳密な文位置を推測しません。
この情報は生成ソフトを実行した証拠ではありません。runtime_verifiedはfalseです。

```text
python ail_chatgpt.py compile language_examples/config_batch.ail -o config_batch --json --debug-dir build-debug
```

AILの関数名doubleなどCの予約語も内部名へ変換します。公開AIL名と型は保持します。
CライブラリとC名前空間部品の未捕捉例外も、終了せず既存エラー戻り値へ変換します。
C APIのmessage[160]は159バイトまでのNUL終端prefixです。所有strのメッセージはUnicode境界・最初のNULで切ります。
## 組込み関数・methodの型を取得する

`api-builtin SYMBOL`で組込み関数や型付きmethodの宣言を直接取得します。引数を省くとinventoryを返します。

```text
python ail_chatgpt.py api-builtin open_binary
python ail_chatgpt.py api-builtin binaryfile.read
python ail_chatgpt.py api-builtin tcpsocket.send_some
```

公開228種類の呼出し形は実コンパイラの型変換で確認しています。戻り値・引数の所有権、receiverの変更、参照行/SHAを返します。
未確認の型・iterator・複合container等はunknownです。overloads=[]とsignature_known=falseは、引数ゼロという意味ではありません。
overloads_complete/errors_complete/coverage.completeはfalseで、全APIの列挙や例外・副作用の閉集合を保証しません。
宣言は呼出し先の束縛や実行時の動作確認ではありません。必要な関数だけ問い合わせてください。
## APIの所有権・副作用を確認する

`api`、`check --interface`、`context`に`--contracts`を付けると、署名に加えて所有権・副作用・例外の情報を取得します。
既定のJSONは変えません。`context --contracts --compact`の契約情報もeditに渡せます。
型注釈や静的解析から分かる情報と、分からない情報を区別します。`known: false`は「起きない」という意味ではありません。
契約情報自体は型検査・呼出し先の束縛・実行時の正しさの証明ではありません。元ソースのSHAと合わせて確認してください。

```text
python ail_chatgpt.py api config_core --contracts
python ail_chatgpt.py context language_examples/config_batch.ail --symbol validate_many --resolve-imports --contracts --compact
```

## リスト式を連結する

list[int]/list[float]/list[str]/list[bytes]のローカルへ、関数・型付きcallbackの戻り値や条件式・sliceをextendできます。
受信先を先に評価し、sourceは一度だけ評価して所有するsnapshotを保持します。throw時は連結しません。
型注釈がなくても静的に型が分かるlocalは対応します。借用parameterの変更は引き続き拒否します。
数値fieldは既存の現在slot更新規則、bytes fieldは捕捉したlist identity、str fieldは現在slot変更と読取りsnapshotの規則を保ちます。
文字列fieldもappend/extend/pop/clear/reverse/sort、要素・sliceの代入/削除、+=を使えます。通常readはdeep snapshotのままです。
文字列fieldの変更はpacked保存を作り直すためO(n+文字列量)で、連続appendは二乗costになり得ます。大量入力はlocalで作り、fieldへbulk extendします。
config_batch.ailのmerge_config_batchesは結果を一括結合し、結合元を保持します。分位点の例はinteger_quantiles.ailです。

```ail
fn parts()->list[int] {return [2,3];}
fn main()->int {let values=[1];values.extend(parts());print(len(values));return 0;}
```

## メッセージを持つ例外値

既存8種類の組込み例外は、引数なし、または任意のstr式1個で作れます。
`exception`型のローカル・関数引数・戻り値は値を所有し、別コンパイルしたモジュール間でも渡せます。

```ail
fn fail(message: str) -> int { raise ValueError(message); return 0; }
fn main() -> int {
    try { fail("invalid setting"); }
    except ValueError as e { print(e.kind + ": " + e.message); return 2; }
    return 0;
}
```

kind/messageは変更できないstrです。messageを取り出したstrは元の例外を解放しても使えます。
`raise e;`は値を再送出し、`raise;`は現在処理している例外を呼出先からも再送出します。
handlerの束縛名はそのhandler内だけで使い、既存の変数名は上書きしません。
UnicodeDecodeErrorはValueErrorとしても捕捉されるため、種類別の処理は具体的な種類を先に置きます。
未捕捉の例外は、空messageなら旧来の種類名、非空なら`Kind: message`をstderrに出して終了1です。
構造体フィールドとlist[exception]にも例外を保持できます。別名・置換・pop・clearでも値の寿命を維持します。
Callable[[exception],exception]とCallable[[list[exception]],list[exception]]でも同じ所有権規則を使えます。
利用者定義例外・chaining・dict/set/tupleへの格納・ネストした例外リストは未対応として拒否します。
複数設定ファイルの診断を最後にまとめる実用例はlanguage_examples/config_batch.ailです。
共有ランタイムはABI11です。旧ABIのobjectは再ビルドしてください。
実用例は`language_examples/config_validate.ail`です。

## 整数の読取りと直接出力（R796）

integer_decodeの幅・順序・検査・独立snapshotを維持し、整数表示を4桁単位で処理します。
整数行ストリームの公開関数は内部stateを使い、途中ValueErrorの直前とchunk完了時に状態を保存します。
既存のprivate stepの逐次更新は維持します。MIN値、出力、評価順は同じです。このR796変更時のABIは10です。
固定WSL/GCC13.3/rustc1.96の比較では現AIL比median時間0.82698、C比0.90096、Rust比0.66030でした。
この入力・機械・比較実装での実績です。全用途の最速や最高AI開発効率の証明ではありません。
要求heap/確保回数は両OS同じ、解放後ゼロ。Linux RSS5回も同じ。Windows RSSと速度は未測定です。
内部stateの並行・signal変更、custom allocatorでのstate変更、unsafe ABI headerは速度資格の対象外です。SEMANTICS §215。
## コンパイラの実行環境

現行の確認環境はWindows x86_64/Python3.13.6とLinux x86_64/Python3.12.3です。
Cコンパイラは各doctorで確認してください。生成nativeの実行にPythonは不要です。
過去互換のPython3.10.11 Windows埋込み版でも、移動SDKのdoctor実build/run、型API、
永続CLI/TCPアプリの実行と独立出力を部分確認しました。全検査・Linux3.10・通常導入は未確認です。
Python3.10は2026-10-01にupstream supportが終了しているため、現行利用は保守中のPythonを使います。
埋込み版はscript directoryを自動追加せず、SDKとpython/pkg-v12をその専用._pthへ明示する必要があります。
CLIのpython_supportedはcompilerのversion条件を表し、upstream supportや全体資格を保証しません。
出典: https://www.python.org/downloads/release/python-31011/
## 開発元のまとめた検証

開発元checkoutのrootから次を実行します。SDKだけの配布には、この検査用ファイル群は含めません。

```text
python -X utf8 -B AIL_CURRENT/ail_check.py --list
python -X utf8 -B AIL_CURRENT/ail_check.py
```

`--list`は選んだ検査IDだけを表示し、ビルドはしません。通常実行は配布対象・検査・参照helperの
manifest hash、PATH上のGCCと明示PIPE_CC、doctorの実build/runを確認してから順番に検査します。
失敗は終了1、環境・pin・probe・読み込み失敗は終了2です。skipは未検証として表示します。
全件skipを成功にはしません。この入口は初版の選択範囲で、全corpus/全API/Cの速度資格ではありません。
GitHub Actionsの設定はroot `.github/workflows/ail-sdk.yml`です。Windows/Linux、Python3.10/3.13で
同じ入口を使います。設定の作成はhosted CI成功の証拠ではありません。
SDK利用者は下のdoctor/integrityで導入を確認してください。

## LLMが生成したAILをビルド前に確認する

```text
python ail_chatgpt.py api checked_integer --symbol parse_int64_decimal
python ail_chatgpt.py api csv_column_stats --symbol csv_column_stats --types-used
python ail_chatgpt.py check my_program.ail
python ail_chatgpt.py check my_library.ail --library --interface
python ail_chatgpt.py check my_library.ail --library --interface --symbol my_function
```

`api MODULE`は配布対象のソースモジュールを名前で解決し、型検査済みの宣言を返します。
パス・.ail拡張子・未配布候補は指定できません。builtinやC/object部品の一覧ではありません。
依存モジュールと未選択本文も検査し、失敗時に成功APIを返しません。
Cをビルドせず、実際の構文・型検査の結果をJSONで返します。defaultのcheckにCコンパイラやモデルは不要です。
終了0はsource/type段階の成功、1はsource error、2は環境・I/O・dependency errorです。
`diagnostics`のcode/messageと、分かる場合の元sourceのpath/line/columnを修正に使えます。
コンパイラが失敗した文を特定できた場合は、元ソースの行・列とlocation_kind=source_statementを返します。式内部の位置ではなく文の先頭です。
不明な位置はnullです。`source_sha256`を確認してから同じsourceをcompileしてください。
型エラーで関数を特定できた場合、`function`と元ファイルの宣言位置を返します。`location_kind=function_declaration`は関数の先頭であり、誤った式の位置ではありません。
`--interface`は、検査が成功したソースと読込モジュールの関数・引数・戻り値・構造体・メソッドをJSONで返します。
関数の本体は含めません。型は宣言された注釈で、未注釈はnullです。builtinやコンパイル済みobjectのAPI一覧ではありません。
`--symbol NAME`を繰り返すと必要なtop-level関数だけを返します。struct宣言は保持します。
`--types-used`を追加すると、選択関数の宣言型からfield/constructor/method/callback型を辿って必要な構造体を残します。
型注釈が不明・未知alias・未対応形の場合は全構造体を保全し、struct_selection=all_when_unknownを返します。
interfaceとsymbolの指定が必要です。既定の全struct出力は変更しません。実トークン削減は未測定です。
選ばなかった関数も型検査し、不正な本文を除外して成功にしません。未知の名前やinterface無しの指定は終了2です。
check成功だけではlink・実行・出力の正しさは未確認です。`--object`指定時はcompiler identityを照会する場合があります。
AILをLLMが書く主言語にし、正答率・修正回数・total/uncached/output tokensとelapsed、実行費用で効率を測ります。
現在のPythonはcompiler実装手段で、生成したnative実行ファイルにPythonは不要です。最高効率やself-hostingは未達です。

## JSON Linesの永続キー・値ツール

```text
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ail_chatgpt.py compile language_examples/json_kv_main.ail --object file_identity.o -o json_kv
json_kv requests.jsonl state.json
```

1行につきJSON objectで命令を渡します。key/valueはUTF8文字列です。

```json
{"op":"set","key":"name","value":"AIL"}
{"op":"get","key":"name"}
{"op":"delete","key":"name"}
{"op":"count"}
```

全命令を処理した後、文字列objectのstate.jsonをキー順に保存し、JSON応答を標準出力へ出します。
状態ファイルがなければ空で開始します。読取りだけのバッチも状態を正規化して保存します。
LF/CRLF、未改行の最終命令、空行、空キー・空値・Unicode・NULを扱います。
重複member、不明命令/field、文字列以外の値、不正UTF8/JSONは終了2で既存状態を保持します。
inputとstateの同一path/別名も拒否します。入力/stateは8MiB、1行1MiB、命令4096、
空行を含むframe8192、キー4096個、キー1024bytes、値65536bytes、応答合計16MiBが上限です。
保存は新規に作れたstate.json.ail-stage内で準備して置換します。既存stageは触らず終了2です。
単一writer向けで、同時更新の整合性や停電時durabilityは保証しません。
保存後のstdout失敗では状態が保存済みの場合があります。処理速度の優位は未測定です。
## 同じキー・値処理をTCPで使う

```text
python ail_chatgpt.py compile language_examples/json_kv_tcp_main.ail -o json_kv_tcp
json_kv_tcp 0 state.json 2 3000
```

127.0.0.1だけに待ち受け、最初に実際のportを標準出力へ出します。引数は
PORT STATE CLIENT_COUNT WAIT_MS。port0は自動割当、client数1〜4096、待機1〜2147483647msです。
接続ごとにCLIと同じJSON Linesバッチを送り、送信を半閉鎖してから応答を受信してください。
EOFまで受信して全命令を検査・保存した後に応答します。接続は順番に処理します。
指定接続数を処理すると応答総数を標準出力へ出して終了します。
不正バッチは状態を保存せず応答なしで接続を閉じ終了4、file/socket/wait失敗は終了3です。
各read/write/accept待機の期限であり、継続通信を含む全体期限ではありません。
応答送信失敗が保存後に起こる場合があります。接続ごとの再読込により保存状態を引き継ぎます。
CLIの状態/入力/応答上限と単一writer条件も適用します。認証/TLS/並行client処理はありません。
速度優位は未測定です。共有のjson_kv_fileに保存処理をまとめています。
## CSVの整数列を集計する

```text
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ail_chatgpt.py compile language_examples/csv_column_stats_main.ail --object file_identity.o -o csv_column_stats
csv_column_stats INPUT.csv OUTPUT.tsv ZERO_BASED_COLUMN
```

引用符・フィールド内改行・UTF-8を含むCSVの選択列から、件数・合計・最小・最大をタブ区切り1行で出します。
空レコードは無視し、ヘッダーは特別扱いしません。選択値はASCII符号付きint64で、途中の合計も範囲を検査します。
既存csv_streamの厳格なCSVプロファイルに従い、不正値・不足列・同一出力パスは終了2。
全入力を検査してから出力を開くため、入力が不正な場合は既存出力を保持します。
入力strとUTF8 bytesを保持し、全行・全fieldのリストを組み立てず集計します。書込み自体はatomicではありません。
固定Linuxの131073行では旧版比の時間.163〜.176、追跡ヒープ約342MB→82MBを確認しました。全入力/Windows/C優位の保証ではありません。
ライブラリではcsv_column_stats(data:str,column:int)->IntegerColumnStatsを使えます。
逐次処理版も選べます。file_identity.oは上と同じものを使います。

```text
python ail_chatgpt.py compile language_examples/csv_column_stats_stream_main.ail --object file_identity.o -o csv_column_stats_stream
csv_column_stats_stream INPUT.csv OUTPUT.tsv ZERO_BASED_COLUMN
```

csv_column_stats_stream(reader:binaryfile,column:int,size:int)->IntegerColumnStatsはcaller所有のreaderを閉じません。
sizeは1〜1MiB。バイト状態から選択整数を集計し、使わないfieldや行の文字列を作りません。
保持メモリはchunkとUTF-8の未完了prefixに依存し、field長の制限は加えません。
EOFまで集計してからCLIが出力を開くため、遅い入力エラーでも既存出力を保持します。
既存str入力APIとCLIは保持します。測定したLinux固定入力では時間とメモリが減りましたが、
非常に長いfield・別入力・Windowsでの速度優位、最善C以上や全用途最速は未証明です。
## 準備

Python 3.10以降を構文上の下限としますが、最低版での動作は未確認です。
GNU互換のC拡張を扱えるCコンパイラが必要です。PATHまたは環境変数`PIPE_CC`で指定します。
主要5用途と移動後ビルドを確認した構成は次の2つです。

- Windows x86_64：Python 3.13.6、MinGW-w64 GCC 16.1.0。
- Ubuntu 24.04 x86_64：Python 3.12.3、GCC 13.3.0。

clean OS、CI、macOS、ARM、thread利用、全C workloadの効率は未検証です。
この検証は初期リリース全体の完了宣言ではありません。
以下はSDKディレクトリで実行します。`python`は利用可能な実行ファイルに置き換えてください。

```text
python ail_chatgpt.py doctor --check
python ail_chatgpt.py integrity
python ail_chatgpt.py --help
python ail_chatgpt.py compile --help
```

### 追加パッケージを入れないPython環境

既存のPythonとCコンパイラを使い、SDKの外に環境を作れます。pipやモデルは不要です。
SDKディレクトリで、Windowsは次を実行します。

```text
python -m venv --without-pip ../ail-python
../ail-python/Scripts/python.exe -B ail_chatgpt.py doctor --check
```

Linuxは次です。

```text
python3 -m venv --without-pip ../ail-python
../ail-python/bin/python -B ail_chatgpt.py doctor --check
```

このPythonを以下の`python`コマンドへ使ってください。既存のPATHまたは`PIPE_CC`でCコンパイラを指定します。
`doctor --check`は実際に小さなAILをビルド・実行し、`build_check.status`を返します。
失敗時は終了2、`phase`でconfiguration/compile/runを示します。
場所が見つかっただけの通常`doctor`は、ビルド・実行可能という証拠にはなりません。
probeは整数list・共有buffer・TCP待受/待機とbinary stdoutの代表確認です。全APIやクリーンOSの資格ではありません。
コンパイラ本体、必要なOSライブラリ、実行に必要なDLLが利用できる環境で確認します。
## 説明文とバイナリの出力

`print`と`write_stdout_bytes`を順番に使えます。後者はbytes/bytearrayをそのまま出力します。
Windowsの通常printはCRLF、バイナリは元のbyte列です。未出力の説明文がある時は、
データを保存してからflushします。失敗はOSErrorで、既に出た出力は取り消せません。

```text
python ail_chatgpt.py compile language_examples/mixed_output_main.ail -o mixed_output_program
```

引数に入力fileを一つ渡します。`AIL bytes N`と改行、N bytesの入力、`END`と改行を出します。
これはframe形式の例です。行だけを読むconsumerには適しません。契約はSEMANTICS §174です。

## 最初のプログラム

`hello.ail`を次の内容で保存します。

```text
fn main() -> int {
    let message: str = "hello";
    print(message);
    return 0;
}
```

```text
python ail_chatgpt.py compile hello.ail -o hello_program
python -c "from pathlib import Path; import subprocess; p=Path('hello_program').resolve(); subprocess.run([str(p if p.exists() else p.with_suffix('.exe'))],check=True)"
```

stdoutに`hello`と改行を出力し、終了コードは0です。
AILの`fn`/`let`構文の最小例は上記です。型・意味・拒否する構文は
`python/pkg-v12/SEMANTICS.md`を参照してください。仕様が明示しない意味はCPythonを参照します。
標準モジュールは`use`で読み込み、追加検索先は`-I ディレクトリ`です。
検索順はimport元の隣、`-I`の順、同梱`language_examples`です。

## 言語・APIの対応範囲

`fn`、型付き`let`、`struct`、`impl`、`use`、条件分岐、`for`・`while`、例外処理を使えます。
整数はsigned int64、小数はbinary64、文字列はUnicode、bytesはimmutableです。
型付きlist・dict・構造体には対応する組合せの制限があり、同じ変数の型変更は拒否します。
無制限整数、任意のPython package、汎用generic、threadや全OS APIの互換を約束しません。

各builtinの引数・エラー・所有権は`python/pkg-v12/SEMANTICS.md`、標準moduleの公開関数は
`language_examples/*.ail`の型付き宣言が契約です。下の5 CLIでは入力・出力を具体的に固定します。
`doctor`の`c_compiler_available`は実行ファイルが見つかったことを示し、C拡張の動作保証ではありません。
明示した`PIPE_CC`が見つからない場合、別コンパイラへ黙って切り替えません。

### CSVの書き戻しとサービスの期限

`csv_writer.csv_encode_row`はfieldをCSVへ戻し、quote/CRLF/Unicodeを扱います。
全文書き戻しCLIは入力検証後に出力し、入力・出力の同一fileを拒否します。

```text
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ail_chatgpt.py compile language_examples/csv_rewrite_main.ail --object file_identity.o -o csv_rewrite_program
```

実行引数は`INPUT OUTPUT`です。CSVのfield値を保ち、record改行をCRLFに揃えます。
全入力を保持します。書込み失敗時の原子性は保証しません。契約はSEMANTICS §176です。

`monotonic_ms()`で経過時間を測れます。起点未指定の整数millisecondsで、UTCではありません。
JSON poll CLIの末尾に`PEER_MS TOTAL_MS`を追加すると、接続ごとの停滞時間とbatch全体を制限します。
0はその期限を無効化します。既存6引数は従来通りです。期限到達は終了3、契約は§175です。

### 大きいCSVの逐次書き戻し

全入力を保持する版に加え、`csv_rewrite_stream`でcaller所有の入力・出力fileを逐次処理できます。

```text
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ail_chatgpt.py compile language_examples/csv_rewrite_stream_main.ail --object file_identity.o -o csv_stream_rewrite_program
```

実行引数は`INPUT OUTPUT CHUNK MAX_ROW_UNITS`です。例としてCHUNK4093、MAX_ROW_UNITS4096を使えます。
各値は1..1048576。行のunitsはfield数＋各fieldのUnicode文字数です。改行・引用符・UTF-8が
chunkをまたいでもfield値を保ってCRLF CSVへ書き戻します。空行は既存parserと同じく飛ばします。
**逐次版では、途中の不正入力・行上限・I/O失敗で出力が空または部分的に残ります。**
全文版の事前検証とは別の契約です。入力と出力の同一fileは開く前に拒否します。
契約はSEMANTICS §177。ライブラリはfileを閉じず、呼出側がflush/closeと独立fileを管理します。

### 共有ハンドルの型付きリスト

`list[bytearray]`、`list[binaryfile]`、`list[tcpsocket]`を、関数・構造体・固定callback・
元ソース不要のtyped objectでも使えます。append/extend/get/set/pop/clear/copy/slice/reverse/forに対応します。
listのcopyは要素を共有します。別のlistから同じbufferを書き換えると、元のbufferにも反映されます。
listをclearしても、取り出した要素や別のcopyが保持していれば使えます。契約はSEMANTICS §171です。

```text
python ail_chatgpt.py compile language_examples/handle_list_main.ail -o handle_list_program
```

実行すると`AIL!`と改行を出力します。空のlistは型を指定し、要素の型を混ぜません。
任意の入れ子、handleのsorting、Python ctypes・owned C wrapperへの新list変換は対応範囲外です。
既存objectはcompiler/runtime identityが変わるため、最新版で再ビルドしてください。
### 標準source APIの一覧

`language_examples/STANDARD_SOURCE_API.json`は、初版で名前を挙げた26source modulesの
69公開関数・各structの宣言を実装から抽出した一覧です。source/依存SHA、imports、source/type検査結果と
契約の出典を含みます。名前がunderscoreで始まる内部関数は一覧から除きますが、言語のaccess controlではありません。
builtin/C/object/entry programsの全APIやownership/error/runtime資格はこの一覧の対象外です。
必要な関数は`api MODULE --symbol NAME --types-used`で最新宣言を取得できます。
SDK export時は一覧のsource/依存SHAをpayloadと照合し、古い一覧や欠けた依存は出力を作る前に拒否します。
### 初版の標準API入口

| 用途 | 同梱モジュールまたはbuiltin | 契約 |
|---|---|---|
| 文字・binary検索 | `text_search`、`binary_search`、`str`/`bytes` methods | SEMANTICSと型付き宣言 |
| Unicode・codec | `utf8_stream`、`binary_numbers`、`binary_float64`、`base64_codec`、`url_codec` | 不正入力の例外と型幅は各宣言 |
| CSV | `csv_table`、`csv_stream`、`csv_group`、`csv_writer` | chunk境界、quote、CR/LF、整数集計 |
| JSON | `json_document`、`json_tree`、`json_pointer` | 全文解析、render、subtree、RFC6901 pointer |
| file・標準入出力 | `open_binary`、`binaryfile.read/readinto/write/seek/tell/flush/close`、`read_stdin_bytes`、`write_stdout_bytes` | SEMANTICS §128/§169ほか |
| directory・環境 | `directory_catalog`、`environment_config` | 型付き宣言とSEMANTICS §124/§130 |
| TCP | `tcp_connect`、`tcp_listen`、`tcpsocket` methods、`tcp_json_lines` | SEMANTICS §131/§132/§170 |
| callback・部品 | 固定署名`Callable`、`compile-module`、`--object` | SEMANTICSと生成metadata |

`bytearray`・file・socketは共有handleです。closeやblocking mode変更はaliasにも反映されます。
全ての型を任意に組み合わせられるという契約ではありません。flat numeric/str list引数の更新や、
任意のnested containerへfile/socketを入れる処理は対応範囲外です。
旧節の未対応記述と後続節が異なる場合、対応する新しい節の契約を参照してください。

## 5つのCLI workload

次のコマンドで実行ファイルを作ります。JSON queryは同梱C接続objectも必要です。

```text
python ail_chatgpt.py compile language_examples/csv_table_main.ail -o csv_program
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ail_chatgpt.py compile language_examples/json_query_main.ail --object file_identity.o -o json_program
python ail_chatgpt.py compile language_examples/binary_search_main.ail -o search_program
python ail_chatgpt.py compile language_examples/binary_cursor_records_main.ail -o records_program
python ail_chatgpt.py compile language_examples/numeric_scale_binary_main.ail -o scale_program
```

以下を`try_cli.py`として保存し、`python try_cli.py`で実行します。
Windowsの`.exe`補完とLinuxの実行pathを共通に扱い、binary stdoutはshellで変換せず保存します。
作業ディレクトリ内に例の入力・出力ファイルを作成します。

```python
from pathlib import Path
import struct
import subprocess

def run(name, *args):
    path = Path(name).resolve()
    if not path.exists():
        path = path.with_suffix('.exe')
    return subprocess.run([str(path), *args], check=True, capture_output=True).stdout

Path('search.bin').write_bytes(b'ababa')
assert run('search_program', 'find', 'search.bin', '6261').decode().strip() == '1'
Path('table.csv').write_bytes(b'a,2\nb,3\n')
print(run('csv_program', 'project', 'table.csv', '0', '7').decode(), end='')
Path('document.json').write_text('{"value":7}', encoding='utf8')
run('json_program', 'extract', 'document.json', 'selected.json', '/value')
assert Path('selected.json').read_text(encoding='utf8') == '7\n'
Path('records.bin').write_bytes(b'')
assert run('records_program', 'records.bin').decode().strip() == '0 0 0 0 0 0 0'
Path('numbers.bin').write_bytes(struct.pack('<2d', 1.5, -2.0))
scaled = run('scale_program', 'numbers.bin', '0', '2')
Path('scaled.bin').write_bytes(scaled)
assert struct.unpack('<2d', scaled) == (3.0, -4.0)
```

- `csv_table project INPUT COLUMNS SIZE`：UTF-8 CSV、0-based columnのcomma区切り、正のchunk byte数。
  stdoutは各行のJSON配列です。上の例は`["a"]`、`["b"]`の2行です。
  `group INPUT KEY_COLUMN VALUE_COLUMN SIZE`はint64値を集計したJSON配列を出力します。
  comma、quote、CR/LF/CRLF、空行の扱いと順序は`csv_stream.ail`/`csv_group.ail`に定義しています。
  成功0、usage・入力・I/Oエラー2。projectで後続入力が失敗しても先行出力は取り消しません。
- `json_query extract|string-map INPUT OUTPUT POINTER`：UTF-8 JSONとJSON Pointerを入力します。
  `~0`は`~`、`~1`は`/`です。extractはJSONと改行、string-mapは専用形式を出力fileへ保存します。
  入出力の同一fileを拒否します。成功0、handled入力・pointer・fileエラー2。
  不正UTF-8も終了2で拒否します。入力エラー時は既存の出力fileを変更しません。
- `json_query batch INPUT OUTPUT [POINTER ...]`：順番どおりの抽出結果をJSON配列として保存します。
  重複pointerを保持し、0件なら`[]`。後半のpointerが不正でも、書出し前に拒否して既存出力を保ちます。
  名前付き形式は`json_query MODE --input INPUT --output OUTPUT --pointer POINTER`です。
  batchの複数pointerは`--`の後へ置けます。`--pointer=`はrootを選びます。`--help`は終了0。
  `cli_args`はlong optionの純粋な解析、`json_pointer_batch`は既存nodeからの複数抽出を再利用できます。
  `sys.argv[START:STOP]`は所有されたlist[str]を生成し、型付き関数へ渡せます。step付きsliceは未対応。
- AILからは`use json_query_file;`を使い、例えば次の一呼出しで読込みから保存まで行えます。
  `let result=json_query_file("batch",input,output,["/items/0","/items/1"]);`
  成功は`result.stage==0`かつ`result.error==0`。工程とエラー番号はSEMANTICS §200です。
  呼出しには上と同じfile_identity objectが必要です。入力不正・抽出失敗は既存出力を保ちますが、
  実際の書込み失敗時の完全な復元は保証しません。typed APIの取得は次の形式です。
  `python ail_chatgpt.py api json_query_file --symbol json_query_file --types-used --object file_identity.o`
- `binary_search find|rfind|count|startswith|endswith INPUT NEEDLE_HEX [START END]`：
  生bytesを検索し、stdoutに整数1行。範囲はsigned int64、負index・空needleはbytesの意味に従います。
  成功0、usage・hex・range・I/Oエラー2。上のfind例の期待出力は`1`です。
- `binary_cursor_records INPUT`：13-byte recordをu8/u16le/u16be/u32le/u32beの順に読みます。
  stdoutはcount、5つの合計、読取byte位置の7整数。サイズは13の倍数、countは2^31以下。
  成功0、usage・不正record・I/Oエラー2。
- `numeric_scale_binary INPUT ORDER FACTOR`：8-byte binary64列を有限factorで各要素独立に乗算。
  orderは0=little endian、1=big endian。stdoutは同じ順序・endiannessのbinary列です。
  NaNの算術後payloadは未規定。成功0、usage・数値・サイズエラー2、I/Oエラー3。

CLI引数のusageは各`*_main.ail`を参照してください。コンパイラ引数は各commandの`--help`です。
上記の終了コードはentryがhandleする範囲であり、資源不足等のruntime trapまで統一しません。

## TCP JSON Linesサービス

```text
python ail_chatgpt.py compile language_examples/tcp_json_lines_main.ail -o json_server
```

実行引数は `HOST PORT CLIENT_COUNT WAIT_MS MAX_LINE` です。
例：`json_server 127.0.0.1 0 1 3000 1048576`（Windowsは `.exe`）。
最初のstdout行が待受portです。接続先へUTF-8 JSONとLFを送り、応答を読みます。
`{"value":7}\n`への応答は同じJSONとLFです。送信終了後に書込側を閉じると、
サーバーは接続を閉じ、指定接続数の処理後に応答総数をstdoutへ出します。
数値の表記、object順序、重複キーを保持します。入力はLFを除き最大1MiB。
空行、不正JSON/UTF-8、上限超過、LFなしの途中EOFを拒否します。
成功0、usage2、I/O・待機期限3、不正引数/入力4です。
WAIT_MSは1..2147483647、各I/O操作の待機期限です。要求全体の期限ではありません。
逐次接続のサービス例です。送信しながら応答を読んでください。
TLS・HTTP・並行サーバー・認証はこの例の機能に含みません。
## 複数接続のTCP JSON Linesサービス

```text
python ail_chatgpt.py compile language_examples/tcp_json_lines_poll_main.ail -o json_poll_server
```

引数は `HOST PORT CLIENT_COUNT IDLE_MS MAX_LINE MAX_ACTIVE` です。
例：`json_poll_server 127.0.0.1 0 2 3000 1048576 8`（Windowsは `.exe`）。
最初のstdout行がportです。UTF-8 JSONとLFを送り、各返信を読みます。
入力を送らない接続や返信を読まない接続があっても、別の接続を処理できます。
不正JSON/UTF-8/未完了行はその接続だけ閉じ、他の接続を続けます。
指定接続数を終えると成功0で返信総数を出します。usage2、I/O・batch idle3、不正入力4。
不正入力とI/Oの両方があれば4です。MAX_ACTIVEは1..1024、MAX_LINEはLFを除き1..1MiBです。
IDLE_MSはbatch全体でready eventが無い待機の期限です。個別接続や要求全体の期限ではありません。
単一threadでI/Oを切り替える例で、CPU並列処理・TLS・HTTP・認証は提供しません。

本体の `tcp_poll(peers, interests, milliseconds)` は、read=1/write=2/both=3/ignore=0を
指定した同じ長さの整数listへ、ready bitsを返します。millisecondsは-1無期限/0即時/INT_MAXまで。
空または全ignoreは即時です。snapshot、引数評価、エラーと所有権の契約はSEMANTICS §172です。
## 数値行を関数へ渡す

```ail
fn total(values:list[int])->int {return sum(values);}
fn main()->int {let rows=[[1,2,3]];print(total(rows[0]));return 0;}
```

数値のpool行を、既存のreadonly list引数へ渡せます。行alias・int-key dictの行も対応します。
引数の記述順で一度だけ評価し、inputをコピーしません。calleeから要素書込み/appendはできません。
外側の入れ子全体・tuple/float/string/object行は数値列と混同せず拒否します。SEMANTICS §207。
## 検査から修正に必要な文脈を取得する

```text
python ail_chatgpt.py check app.ail --repair-context
python ail_chatgpt.py edit app.ail --symbol main --base-sha256 HASH --body-text "return 0;" --context check.json -o candidate.ail
```

検査の全JSONをUTF-8でcheck.jsonへ保存します。文脈の抽出コマンドは不要です。
型エラーやreturn不足で関数を特定できた場合、repair_contextにその本文、呼出し候補の宣言、
元sourceと依存のSHA、source_pathを返します。import先の関数やmethodにも対応します。
検査と文脈取得の間に読込sourceが変われば文脈を拒否します。診断と終了コードは元のcheckと同じです。
成功時はnot_needed、構文エラー・Python構文・位置不明・明示module/objectなどはunavailableです。
返す宣言は型検査済みAPIではありません。修正候補全体のcheckと実行時の出力確認が必要です。
editの--contextにはcheck全体のJSONをそのまま渡せます。repair_contextだけを保存する従来の形も使えます。
全reportを渡す場合はsource_pathのfileだけを編集し、元caller全体の版や実行結果を保証しません。SEMANTICS §210。
戻り値の型不一致には、診断の`type_details`に`operation: "return"`、`expected`、`actual`が入ります。
比較した型から直接取得し、型の公開表記がない場合はnullです。未対応の注釈や他のエラーには保証しません。
既存の判定・エラー文は維持します。実モデルの完成費用削減は未測定です。SEMANTICS §211。
引数の型不一致には`operation: "argument"`、`callee`、`parameter`、`parameter_index`と必要/実際の型が入ります。
位置は確定した署名で0始まり、メソッドの受け手も含みます。キーワード引数でも署名の位置を示します。
呼出し検査の診断位置と修正対象は呼出し側です。型を取得できなければactualはnullです。
宣言と型要求の衝突は`operation: "parameter"`、`inference_scope: "signature_override"`として宣言側を指します。
後者は複数の呼出し情報やcompiler APIの要求を含むため、特定の呼出し位置は推定しません。引数の数・未対応形式等には保証しません。SEMANTICS §212。
float引数へ整数を渡す既存の変換は、位置指定でも使えます。宣言のfloat型を維持します。
2の53乗付近やint64端ではbinary64に丸められます。floatからintへの暗黙変換や外部ABIの置換は認めません。SEMANTICS §213。
モデルの呼出し・自動編集は行いません。実トークンや完成時間の改善は未測定です。SEMANTICS §209。

## 修正する関数の文脈だけを取得する

```text
python ail_chatgpt.py context app.ail --symbol transform --include-body
```

引数/返り値、ローカル呼出し候補の署名、関連するローカル型、imports、source/body SHAを返します。
本文を付けるのは`--include-body`指定時だけです。`Box.value`のmethodにも対応します。

`context --compact`は、引数のname/type/kind/defaultを共通の列と行で表す任意のJSON形式です。
型・検証状態・receiver・依存SHA・未解決呼出し・本文は保持し、edit --contextは復元後に同じ版検査を行います。
既定のJSONは変えません。実例のJSONは3147→2527bytesでしたが、モデルの正答率・総tokens・完成時間の改善は未測定です。
language_rules.exceptionsに現行の例外契約も含みます。引数なし、またはstr式1個のmessageとhandler bindingに対応します。chainingは未対応です。
raise ValueError;、raise ValueError();、raise ValueError("message");で例外を発生させます。except ValueError as eでkind/messageを確認できます。
checkのrepair_hintは、拒否した例外constructorの引数型・個数について同じ例外型の構文を示します。自動置換はしません。
AILのblock構文はassert未対応。Python互換構文のassertは捕捉不能の終了1で、ValueErrorの代用にはなりません。
型エラーがある本文も構文が正しければ読み取れます。返されたsource_sha256を次のeditへ渡します。
`--resolve-imports`を付けると、sourceのimport先も読み、呼出し候補の実在する署名と関連型を返します。
`-I DIR`で追加のmodule directoryを指定できます。dependency_sha256で読み取った依存の版も確認できます。
型不正やreturn不足のbodyは宣言だけ取得します。通常のcheck/editは従来どおり全体の型を検査します。
文脈JSONを保存してeditへ`--context context.json`を渡すと、依存の版を検査の前後で照合します。
依存の実装変更、対象違い、古い本体、検索先変更は出力前に拒否します。SEMANTICS §205。
このmodeはsource importsだけを固定します。明示`--module`は併用できず、object metadataは従来の型検査です。
既定contextは外部object/builtinの署名・契約を取得しません。--contractsで静的に分かる所有権・副作用・例外の情報を追加できますが、未分類builtinや外部objectの情報は不明のままです。
これは宣言の取得で、型/動作の正しさは未確認です。SEMANTICS §204。
other_call_expressionsに未取得の呼出しがあれば、apiや原本の契約で追加確認します。SEMANTICS §203。
## 関数本体だけを編集する

`check`が返すsource_sha256を使い、関数本体の候補をAIL文だけでbody.txtへ書きます。

```text
python ail_chatgpt.py edit app.ail --symbol transform --base-sha256 HASH --body body.txt -o candidate.ail
python ail_chatgpt.py edit app.ail --symbol transform --base-sha256 HASH --body-text "return x+1;" -o candidate.ail
```

複数関数の本文は `--edits-text` にJSON配列でまとめて指定できます。
例: `[{"symbol":"left","body":"return right()+1;"},{"symbol":"right","body":"return 40;"}]`。
`--symbol`は付けず、`--base-sha256`と`-o`は必須です。
全候補を一度だけ型検査します。`--context`を使う場合は配列の第一対象について取得したcontextを渡してください。

`Box.value`のようなメソッドも指定できます。署名・他の関数・コメントを保ち、元fileは変更しません。
元の版が古い、対象外へはみ出す、不正な型、既存の出力fileなら拒否します。候補全体を検査します。
libraryは`--library`、依存moduleは`-I`/`--module`、typed objectは`--object`を付けます。
成功はsource/type確認までで、動作の正しさと性能は未検証です。書込み障害時は新fileが部分的に残る
可能性があります。永続ID・複数file transaction・元fileへの自動適用はまだありません。SEMANTICS §202。
## バイナリ整数の行集計を逐次処理する

```text
python ail_chatgpt.py compile language_examples/row_reduce_stream_main.ail -o row_reduce_stream
row_reduce_stream INPUT.bin COLUMNS REPEAT
python ail_chatgpt.py api integer_row_stream --symbol integer_row_report_stream --types-used
```

Little-endian signed int64を行ごとに集計し、ASCII十進数とLFを出します。引数は従来のrow_reduce_mainと同じです。
標準API integer_row_report_stream(reader:binaryfile,cols:int,size:int)->bytesも利用できます。sizeは1〜1MiB。
readerはcaller所有で閉じません。途中の合計もint64範囲を確認し、部分record/row・overflowはValueErrorです。
全入力を検証してからCLIが出力するため、遅い不正入力でも部分出力を残しません。
保持するのは出力全体とchunkで、出力の固定メモリ保証はありません。返り値は独立したbytes snapshotです。
固定入力では確保ピークを減らしました。実行時間・C/Rust優位・全用途の最高効率は未認定です。SEMANTICS §208。
整数をbytearrayへ直接書く既存経路を使い、固定65537行×17列では確保要求約20万回を約860回へ減らしました。
総要求payloadは約41.8MB→32.2MB、ピーク差は576bytesです。速度の校正は未合格で、速度優位の認定ではありません。
## ファイル処理をAILだけで完結する

`make_dir`、`remove_file`、`remove_dir`、`replace_path`を使えます。契約はSEMANTICS §173です。
作成は1階層、directory削除は空のものだけです。replaceは既存の出力fileを置換するOS操作で、
cross-volume copyやreboot処理は行いません。directory置換・open-file・権限の結果はOSに従います。

```text
python ail_chatgpt.py compile language_examples/filesystem_main.ail -o filesystem_program
```

実行引数は新しいdirectoryのpathです。例は自分が作ったdirectory内でstage/resultを作り、
置換結果`new`＋NUL＋FFの5bytesをstdoutへ出し、作ったfile/directoryを片付けます。
既存directoryは変更せず終了4。usage2、NUL等ValueError3、OS error4、成功0です。
## object、C API、再書き出し

```text
python ail_chatgpt.py compile-module language_examples/binary_numbers.ail -o numbers.o
python ail_chatgpt.py compile-library language_examples/binary_numbers.ail --name numbers -o numbers_library
python ail_chatgpt.py export-sdk -o ../ail-sdk-copy
```

source-free再リンクには`.o`と隣接する`.o.json`を一緒に移動し、依存objectの全closureを
`--object`で渡します。layout・compiler/runtime identityの違うobjectは互換とみなしません。
bytesはimmutable値です。非保持helperの最適化は入力を呼出後へ逃がさない証明がある場合だけで、
未知C関数に非保持を仮定しません。fieldへの格納・snapshotの所有権規則はSEMANTICSに従います。
C APIの結果の所有権・解放は生成headerの契約に従ってください。

MANIFEST.jsonは同梱ファイルと書き出し元manifestのSHA-256を記録します。
sdk_filesがある版は、その固定一覧だけを書き出します。研究用ファイルの追加で配布範囲は変わりません。
新しく採用するファイルは一覧とSHA-256を更新します。選択したC interfaceの依存欠落は拒否します。
SDKの書き出しは全環境での動作保証ではありません。再書き出し先には、既存の親ディレクトリ内の
新しいディレクトリを指定してください。
"""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError(f'symlink or junction is not allowed: {part}')


def _local_file(root, path):
    _no_links(path)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f'not a local regular file: {path}')
    return resolved


def _declared_inputs(root, interface, value):
    for field in ('headers', 'sources', 'asm_sources', 'archives'):
        names = value.get(field, [])
        if not isinstance(names, list):
            raise ValueError(f'{interface}: {field} must be a list')
        for name in names:
            if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                    or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))):
                raise ValueError(f'{interface}: unsafe {field} path: {name!r}')
            yield _local_file(root, interface.parent / name)


def export_sdk(source_root: Path, output: Path) -> dict:
    """Write a new SDK directory, preserving partial output on copy failure."""
    source_root, output = Path(source_root).absolute(), Path(output).absolute()
    _no_links(source_root)
    _no_links(output)
    root = source_root.resolve(strict=True)
    output = output.resolve()
    if not root.is_dir() or not output.parent.is_dir():
        raise ValueError('source and output parent must be existing directories')
    if output.exists():
        raise ValueError(f'output already exists: {output}')
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('source and output directories must not contain each other')

    manifest_path = _local_file(root, root / 'MANIFEST.json')
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = _sha(manifest_bytes)
    source_manifest = json.loads(manifest_bytes)
    pins = source_manifest.get('sha256')
    if not isinstance(pins, dict):
        raise ValueError('source MANIFEST.json must contain a sha256 mapping')
    required = {'ail_chatgpt.py', 'ailc.py', 'ail_syntax.py', 'ail_sdk.py',
                'python/pkg-v12/SEMANTICS.md'}
    declared = source_manifest.get('sdk_files')
    if 'sdk_files' in source_manifest:
        if not isinstance(declared, list) or not declared:
            raise ValueError('sdk_files must be a nonempty list')
        for name in declared:
            if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                    or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))
                    or name in ('MANIFEST.json', 'SDK_README_JA.md')):
                raise ValueError(f'unsafe sdk_files path: {name!r}')
        if len(set(declared)) != len(declared) or not required <= set(declared):
            raise ValueError('sdk_files must be unique and contain compiler entry points and semantics')
        selected = {_local_file(root, root / name) for name in declared}
    else:
        selected = {root / name for name in required}
        # Newer legacy snapshots pin these CLI modules without sdk_files.
        # Older snapshots that predate the commands need neither module.
        selected.update(root / name for name in ('ail_source_edit.py', 'ail_source_context.py', 'ail_api_contracts.py', 'ail_native_build.py', 'ail_builtin_api.py', 'ail_builtin_syntax_forms.py', 'ail_sexpr.py', 'ail_slow_patterns.py', 'ail_modules.py', 'ail_ffi.py', 'ail_ffi_lower.py')
                        if name in pins)
        compiler = root / 'python' / 'pkg-v12'
        examples = root / 'language_examples'
        for directory in (compiler, examples):
            _no_links(directory)
            if not directory.is_dir():
                raise ValueError(f'missing source directory: {directory}')
        selected.update(p for p in compiler.iterdir() if p.suffix in ('.py', '.h'))
        # pinned C sources linked into programs (e.g. ail_wincon.c for the Windows console)
        selected.update(p for p in compiler.iterdir()
                        if p.suffix == '.c' and 'python/pkg-v12/' + p.name in pins)
        # The IR is a package below the compiler directory (python/pkg-v12/ir/, ir/passes/).
        if (compiler / 'ir').is_dir():
            selected.update(p for p in (compiler / 'ir').rglob('*.py') if '__pycache__' not in p.parts)
        selected.update(p for p in examples.iterdir() if p.suffix in ('.ail', '.c', '.h', '.S', '.s', '.json'))
        # bundled standard modules written in AIL over the C FFI (G5a): stdlib/zlib.py and its C glue
        if (root / 'stdlib').is_dir() and any(name.startswith('stdlib/') for name in pins):
            _no_links(root / 'stdlib')
            selected.update(p for p in (root / 'stdlib').iterdir() if p.suffix in ('.py', '.c', '.h'))

    # A selected C interface must include its full declared input closure.
    for path in tuple(selected):
        if path.suffix != '.json':
            continue
        path = _local_file(root, path)
        try:
            value = json.loads(path.read_bytes())
        except (ValueError, UnicodeDecodeError):
            if declared is None:
                selected.discard(path)
            continue
        if (isinstance(value, dict) and type(value.get('version')) is int
                and value['version'] == 1 and isinstance(value.get('functions'), dict)):
            dependencies = set(_declared_inputs(root, path, value))
            if declared is not None and not dependencies <= selected:
                raise ValueError(f'sdk_files missing C interface inputs: {path}')
            selected.update(dependencies)
        elif isinstance(value, dict) and value.get('schema') == 'ail.standard_source_api/1':
            pass
        elif declared is None:
            selected.discard(path)

    payloads = {}
    for path in sorted(selected):
        path = _local_file(root, path)
        name = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if _sha(data) != pins.get(name):
            raise ValueError(f'source missing pin or SHA-256 mismatch: {name}')
        payloads[name] = data
    catalog_bytes = payloads.get('language_examples/STANDARD_SOURCE_API.json')
    if catalog_bytes is not None:
        catalog = json.loads(catalog_bytes)
        dependencies = catalog.get('dependency_pins') if isinstance(catalog, dict) else None
        modules = catalog.get('modules') if isinstance(catalog, dict) else None
        if (not isinstance(catalog, dict) or catalog.get('schema') != 'ail.standard_source_api/1'
                or not isinstance(dependencies, dict) or not dependencies
                or not isinstance(modules, list) or not modules):
            raise ValueError('invalid standard source API inventory')
        for name, digest in dependencies.items():
            if not isinstance(name, str) or name not in payloads or _sha(payloads[name]) != digest:
                raise ValueError('stale or missing standard API dependency: ' + str(name))
        for row in modules:
            if (not isinstance(row, dict) or not isinstance(row.get('source'), str) or row.get('source') not in dependencies
                    or row.get('sha256') != dependencies[row['source']]):
                raise ValueError('stale standard API module declaration')
    if _sha(manifest_path.read_bytes()) != manifest_hash:
        raise ValueError('source manifest changed during preflight')
    payloads['SDK_README_JA.md'] = README.encode('utf-8')
    hashes = {name: _sha(data) for name, data in payloads.items()}
    result = {'kind': 'ail_language_sdk', 'version': 1, 'abi': 11,
              'sha256': hashes, 'original_manifest_sha256': manifest_hash,
              'sdk_files': sorted(name for name in payloads if name != 'SDK_README_JA.md'),
              'bytes': sum(map(len, payloads.values())), 'filecount': len(payloads)}
    output.mkdir()
    try:
        for name, data in payloads.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            _no_links(target)
            with target.open('xb') as stream:
                stream.write(data)
            if _sha(target.read_bytes()) != hashes[name]:
                raise ValueError(f'copied SHA-256 mismatch: {name}')
        for name in payloads:
            if name != 'SDK_README_JA.md' and _sha(_local_file(root, root / name).read_bytes()) != hashes[name]:
                raise ValueError(f'source changed during copy: {name}')
        if _sha(manifest_path.read_bytes()) != manifest_hash:
            raise ValueError('source manifest changed during copy')
        with (output / 'MANIFEST.json').open('xb') as stream:
            stream.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    except Exception as exc:
        raise RuntimeError(f'SDK export failed; partial directory retained at {output}: {exc}') from exc
    return {'output': str(output), **result}
