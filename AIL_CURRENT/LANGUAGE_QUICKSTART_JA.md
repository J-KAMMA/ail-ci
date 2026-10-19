> プログラムを書くための英語の要約は AIL_REFERENCE.md（短いコア、最初に全文を読む）と AIL_REFERENCE_MORE.md（残り全部。コア末尾の行番号索引で必要な節だけ読む）。

## ローカルのリストを反転し、文字列を取り出す

所有するローカルの `list[int]`・`list[float]`・`list[str]` は `reverse()` を使えます。
`list[str]` の `pop()`／`pop(index)` は、取り出した後に元のリストを空にしても使える文字列を返します。

```ail
fn main()->int {
    let words:list[str]=["first","last"];
    words.reverse();
    let saved=words.pop();
    words.clear();
    print(saved);
    return 0;
}
```

出力は `first` です。借用引数の変更は拒否します。小数リストの `sort()` は未対応です。
整数と小数のループで同じ変数名を再利用しても、整数を小数へ丸めず保持します。`int(float)` は有限でint64範囲内の値を0方向へ切り捨て、それ以外をValueErrorにします。

# AILを言語として使う最小の入口

AILのソースを `.ail` に書き、単独の実行ファイルへコンパイルできます。

現行の到達判定は `../AIL_PROGRESS_CRITERIA_20261005.md` 冒頭にあります。
下の旧改訂にある5/12（42%）は当時の記録であり、現在の完成率ではありません。

## pipでインストールして使う（ail-lang, G13）

```
pip install ail-lang
ail run prog.py              # 一時的な実行ファイルへコンパイルして実行（プログラムへの引数は prog.py の後ろ）
ail build prog.py -o prog    # 単独の実行ファイルを作る（-o を省くと拡張子を除いた名前）
ail check prog.py            # 型・構文の検査だけ（Cコンパイラ不要。終了コード0=通過、1=ソースの誤り、2=設定・I/O）
```

`ail` は `ail_chatgpt.py` の薄い入口です。`run`/`build` は `compile` に、`check` は `check` に対応します。
`compile`・`compile-module`・`compile-library`・`compile-c`・`api`・`api-builtin`・`context`・`edit`・`doctor`・
`integrity`・`cache`・`export-sdk` はそのまま渡せます（`python -m ail_lang` でも同じ）。`--syntax`・`-I DIR`・
`--static`・`--no-cache` などのオプションはソースファイルの前に書きます。

- 同梱物は `export-sdk` が選ぶファイルと同じです（MANIFEST.json の `sdk_files` と SHA-256）。`ail integrity` で照合できます。
  `experiments/`・`docs/design`・`a held-out task set`・`evidence/` は入りません。
- 実行時にCコンパイラが要ります。探す順は `$PIPE_CC`、PATH上の `cc`・`clang`・`gcc`、`zig cc`（`$AIL_ZIG`、PATH上の `zig`、
  `pip install "ail-lang[zig]"` で入るziglang）。無ければ、入れ方を示すメッセージを出して終了コード2で止まります。`ail doctor` で確認できます。
- ビルドキャッシュ（G3）はユーザーごとです。`$AIL_CACHE`、無ければLinuxは `$XDG_CACHE_HOME/ail`（既定 `~/.cache/ail`）、macOSは
  `~/Library/Caches/ail`、Windowsは `%LOCALAPPDATA%\ail\cache`（Windowsではキャッシュ自体がまだ無効）。他のユーザー所有のディレクトリは使わず、
  キャッシュなしで動きます。`ail cache path|stats|clear`、`--no-cache` または `AIL_NO_CACHE=1` で無効にできます。
- ホイールの組み立て: リポジトリ直下で `pip wheel --no-deps .`（標準ライブラリだけのビルドバックエンド `packaging/ail_wheel_backend.py`。
  ネットワーク不要。sdistは作りません）。バージョンの出どころは `packaging/ail_lang/__init__.py` の1か所です。
  `test_ail_packaging` がホイールの中身をSDK選択と突き合わせ、新しいvenvへのインストールで実行します。

## プロジェクト・言語サーバー・デバッグ（ail new / ail lsp / ail build --debug）

```
ail new hello && cd hello    # hello/ail.toml, hello/src/main.py, hello/.gitignore を作る
ail run                      # ファイル名なし: 今のディレクトリから上へ探したプロジェクトのentryをビルドして実行
ail build                    # build/hello を作る（作り直しも可。--debug なら build/hello-debug）
ail check                    # entry の型・構文検査（Cコンパイラ不要）
ail lsp                      # 言語サーバー（標準入出力）
```

`ail.toml`（または pyproject.toml の `[tool.ail]`。両方あれば ail.toml）のキーは次の5つだけです。未知のキーや型違いは名前を挙げて止まります。

```
name = "hello"            # 実行ファイル名（省略: ディレクトリ名）
entry = "src/main.py"     # 入口のモジュール（必須。.py か .ail）
link = ["z", "m"]         # リンクするCライブラリ（-lz -lm。名前だけ）
strict = false            # true: 遅い汎用経路で動くプログラムをビルドせず、理由と write instead を出して止める
module_path = ["src"]     # 追加のモジュールディレクトリ（-I と同じ。entryのディレクトリは常に探す）
```

- `strict = true` は `ail build --strict` と同じです（型付き経路だけを許し、妨げを全部、書き換え案つきで出して終了コード3で止まる。下の「厳格モード」）。言語サーバーでも、型付き経路の拒否が警告ではなく**エラー**になります。
- パッケージレジストリはまだありません。他のプロジェクトのコードは `module_path` で置いたディレクトリから読みます。
- `ail build prog.py -o prog` の単体ファイル形式は今まで通りです。`link` と `compile --link LIB` は、ソースの `link("LIB")`（cratebridge）と同じ仕組みで、同じ並びでリンクされます。
- **言語サーバー** `ail lsp`: ファイルを開いた時・保存した時に `ail check` を走らせて診断を出します（ディスク上のファイルを検査）。
  妨げの一覧は `compile --strict --json`（ail.strict/1）から取り、読み込めない・構文エラー・汎用経路でも作れないものは**エラー**、型付き経路が断ったが汎用経路で作れるものは**警告**
  「runs on the slow general path because …」です。どちらも `write instead:` の書き換え案を含み、診断にマウスを置く（hover）と案が出ます。
  二次式になりやすい書き方（slow_patterns）は情報です。警告かエラーかを決めるため、その時だけ1回ビルドします（Cコンパイラが要り、結果は
  ソースのハッシュごとに覚えます。無ければ警告に「Cコンパイラが無いので分からない」と付きます）。
- **デバッグ** `ail build --debug`: `-g -O0` でビルドし、各文の前に元の `.py`/`.ail` の行への `#line` を入れます。gdb で
  `break prog.py:12` → `run` → `next` と Python の行で進められます（モジュールを import していればそのファイルの行）。
  捕まえなかった例外は、CPython互換のメッセージの後に `  raised near /path/prog.py:3`（最後に実行を始めた文＝raiseの行、
  実行時エラーならそれが起きた文）を1行足します。`--debug` なしの標準エラーは従来のまま（DIFFERENCES A4）です。
  汎用経路にフォールバックしたプログラムには行対応が無いので、そう表示します（`strict = true` で事前に気付けます）。
  `--separate` やオブジェクトの結合ではモジュール側の .o は `-O2` のままです。

## 厳格モード: 型付き経路で作れないなら拒否する（--strict）

型付き経路が受け付けないプログラムは、既定では遅い一般経路（約20倍遅い）で作られ、`note: ... built on the general path (about 20x slower) ...; run with --strict to see why` の1行が出ます（`AIL_QUIET_FALLBACK=1` で消せます）。速さを保証したいときは `--strict` を付けます。

```
ail build --strict prog.py -o prog     # ail run --strict prog.py も、環境変数 AIL_STRICT=1 も同じ
ail build --strict --json prog.py      # 妨げ(blocker)の一覧を機械可読のJSON(ail.strict/1)で標準出力へ
```

- 型付き経路で作れるプログラムは、付けない場合と同じCコード・同じ実行ファイルになります。
- 作れない場合は終了コード3で、最初の1件ではなく見つかった妨げをすべて出します。各件に `file:line:col`、該当コード、構成要素、型付きにならない理由、`write instead:`（型付きで通る書き換え）が付きます。
- 並び順は、その妨げが止めているコードの量（その関数と、それを呼ぶ関数の行数）が多い順です。上から直し、もう一度実行します。
- JSONは `blockers[]` に `rank path line column function statement construct why write_instead blocks_lines blocks_functions message` を持ちます。LLMに渡せば1回で直せます。
- `AIL_NO_GENERAL=1` だけを付けた場合は従来どおり最初の拒否1件で止まります。

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

## 空の関数・ブロック（R732）

`fn noop()->void {}`や`if condition {}`の空本文は、何もしない処理として使えます。
コメントだけの本文も同じです。条件や繰り返し入力の評価、finallyの実行は省略されません。
値を返す関数とmainには、引き続き必要なreturnが必要です。空のstruct/impl宣言は未対応です。
`edit --body-text ""`でもvoid関数を空本文に修正できます。原本のSHA確認と候補の型検査は行われます。

## 契約: requires と ensures（2026-10-11）

関数本文の先頭に、入口の条件`requires 条件;`と出口の条件`ensures 条件;`を書けます。
`requires`は呼び出し時に、`ensures`はすべての`return`の直前（戻り値なしの関数は本文の末尾でも）に検査します。
`ensures`の中の`result`は戻り値です。同名のローカル変数があっても、契約の中では戻り値を指します。

```ail
fn isqrt(n: int) -> int {
    requires n >= 0;
    ensures result * result <= n;
    ensures (result + 1) * (result + 1) > n;
    let r: int = 0;
    while (r + 1) * (r + 1) <= n { r += 1; }
    return r;
}
```

違反すると、stderrに`requires failed in isqrt: n >= 0`のように関数名と条件を出し、終了1で止まります（tryでは捕捉しません）。
契約は本文の最初の文としてだけ書けます。途中・ブロックの中・`requires`での`result`・戻り値なしの関数の`result`はコンパイル時に拒否します。
メソッドでも使え、メッセージの関数名は`Account.withdraw`のようになります。

## S式の書き方（2026-10-11）

同じAILをS式（前置記法・括弧で区切る）でも書けます。先頭が`(`のファイルはS式として読み、
通常のブロック構文へ変換してから同じ検査・コンパイルを通すので、意味は1つです。
`python ail_sexpr.py FILE.ail`で、ブロック構文とS式を相互に変換できます（コメントは残りません）。

```ail
(fn isqrt ((n int)) int
  (requires (>= n 0))
  (ensures (<= (* result result) n))
  (let r int 0)
  (while (<= (* (+ r 1) (+ r 1)) n) (+= r 1))
  (return r))
(fn main () int (print (isqrt (int (@ sys.argv 1)))) (return 0))
```

形の一覧は`ail_sexpr.py`の先頭にあります。同梱の全ソースが「ブロック構文→S式→ブロック構文」で同じ構文木に戻ることをテストで確かめています。
長さの実測（同梱258本）: S式は空白を詰めた文字数で1.04倍、語の数で1.13倍。今のLLMのトークナイザでは括弧の分だけ長く、主な書き方はブロック構文のままです。

## 他のOS・CPU向けにビルドする（2026-10-11）

`compile --target`で、[zig](https://ziglang.org/) の`zig cc`を使ったクロスコンパイルができます。
zigは各OSのCライブラリを同梱しているので、1つの環境からLinux・Windows・macOSの実行ファイルを作れます。

```text
python ail_chatgpt.py compile --target windows program.ail -o program.exe
python ail_chatgpt.py compile --target macos program.ail -o program-macos
```

targetは`linux` `linux-arm64` `windows` `macos`（arm64） `macos-x86_64`です。
zigは`$AIL_ZIG`、PATH、`~/tools/zig/zig`の順に探します。見つからなければ止まります。
WSLでWindows向けに作ったrecords・numeric・csvの各アプリは、Windows上でLinux版と同じ出力になることを確認しています。

## LLMでAILを開発する入口

型付きの関数・モジュールで実装し、必要なAPIだけを取得できます。
同梱ソースのAPIは`api MODULE`、自作モジュールは`check PATH --library --interface`で取得します。

```text
python ail_chatgpt.py api checked_integer --symbol parse_int64_decimal
python ail_chatgpt.py check library.ail --library --interface --symbol function_name
python ail_chatgpt.py check program.ail
python ail_chatgpt.py compile program.ail -o program
```

checkのJSON診断で修正し、同じsource_sha256のソースをcompileします。
field/elementのtype_detailsは、必要な型と実際の型を公開名で返します。
append/storeは要素型、extendはリスト型同士を比べます。actual=nullは未分類であり、型が正しい証拠ではありません。
location_kind=source_statementは誤った文の先頭、function_declarationは関数の先頭です。
check成功後も、実行結果は独立した期待出力と照合してください。
ネイティブ実行にPythonは不要です。総トークン・修正回数・時間の改善は未実証です。
## 同じCSV集計APIの実行効率（R693）

`csv_column_stats(data:str,column:int)`は、全行・全fieldをリストに展開せず集計します。
公開署名・整数幅・途中overflow・quote・UTF8・最終行・エラー時の出力保持は維持します。
入力strとUTF8 bytesは保持するため、入力サイズに依存するメモリは残ります。
固定Linuxの131073行では、元版比の時間.163〜.176、追跡ヒープ約342MB→82MBを確認しました。
小さい条件・Windowsの速度、全用途のC以上の効率は未証明です。
LLMが新しい内部処理を書く必要はなく、同じ公開関数を使えます。
## 汎用言語としての開発対象

自分の関数・型・構造体・モジュールでプログラムを組み立て、単独の実行ファイルへ
コンパイルする言語として開発しています。数値処理に加えて、文字列・バイナリ・
コンテナ・ファイル入出力・例外処理を言語本体と標準APIで扱います。
現在は64ビット整数、小数、文字列、bytes、型付きリスト・辞書、構造体、`use` による
モジュール分割とソース不要のobjectリンクが使えます。対応する型・操作には制限があります。
型付きの静的関数値とTCP接続・待受・非ブロッキングI/Oも使えます。クロージャ・汎用ジェネリック・スレッド・
OS向けの低層APIまで揃った状態は未達です。

R586で構造体同士を組み合わせる型の合成を追加しました。
R587で利用者定義型を引数・戻り値にする静的callbackを追加しました。
R588で受けた例外の再送出を追加しました。型の合成・callback・例外伝播を組み合わせ、
モジュールの別コンパイルと値の寿命を確認して、ライブラリを組み立てる能力を広げています。

### JSON配列の不要な全走査を省く（R661）

JSON Pointerの配列添字は、文書のノード数を安全な上限として検査し、
目的の子が見つかるまで一度だけ走査します。要素数を先に数える全走査を省きます。
文書全体・pointer全体の検証、巨大な添字、不正な数字、重複object key、例外の順序を維持します。
固定した整数配列の3query CLIではLinux400.52→355.65ms、約11%短縮を確認しました。
Windowsの速度差は未判定です。同じ限定仕事の独立C参照は大幅に速く、C超えは未達です。

### バイナリ内の1バイトを数える（R659）

`data.count(b"\0")`などの1バイト集計は、Linuxで対象バイトの疎密に応じて
標準memchrと既存の一括集計を選びます。Windowsでは既存の集計関数を選びます。
固定128MiBの疎な入力では、Linuxの全体時間21.76→16.40ms、約25%短縮を確認しました。
強めたCのmemchr参照との時間差は未判定で、同等性や全用途のC超えの証明ではありません。
密な入力や密度切替も確認していますが、すべての入力で速くなる保証ではありません。
型・負の範囲・非重複count・別名・評価順・例外・所有権の契約を維持します。

### 標準入力の不要な確保・コピーを省く（R657）

`read_stdin_bytes`の結果をループ内で使い終わり、外へ残さないと証明できる場合、
コンパイラが共有受信バッファを直接使います。戻り値・別名・再読込み・未知の呼出し・
stdio callbackがあり得る処理は従来の所有bytesを維持します。利用者の構文や契約は変わりません。
固定128MiB集計のLinuxでは27.04→22.66msを確認しました。Windowsの時間差は未判定です。
別の固定4MiB集計では両OSの要求heapピーク65,600→144bytesを確認しました。
これは要求heapだけで、64KiB共有バッファ・stack・RSS・Cの全用途との比較を含みません。

### 数値配列のフィールドをループで読む（R605）

単純な整数変数・定数の添字は、配列全体をコピーせず一要素を読みます。
list[int] と list[float] の負の添字・範囲検査を保持しています。
副作用のある添字は従来の独立snapshotを残します。
固定の実用処理は約535msから約41msへ改善しました。C超えや全用途の保証ではありません。

### TCPサーバーを作る（R601）

```ail
use tcp_echo_server;
fn main()->int {
    let listener = tcp_listen("127.0.0.1", 0, 16);
    try {
        print(listener.local_port());
        flush_stdout();
        let connection = listener.accept();
        try { tcp_echo_connection(connection, 8192); }
        finally { connection.close(); }
    } finally { listener.close(); }
    return 0;
}
```

`tcp_listen(host,port,backlog)` は接続を待ち受け、`accept()` は独立した接続を返します。
portの0はOSによる空きポート割当てです。`local_port()` で実際のポートを取得できます。
backlogは1〜2147483647で、実際の待ち行列の上限はOSに従います。
待受けを閉じても受付済みの接続は使えます。待受けにsend/recv/recv_into/shutdown_writeを
呼ぶとOSError、通常の接続でacceptを呼んでもOSErrorです。閉じた後はValueErrorです。
hostはASCII、待受けportは0〜65535です。待受けは最初に成功したアドレス候補一つです。
アドレス再利用・TLS・期限・非同期処理の指定はまだありません。

```text
python ail_chatgpt.py compile language_examples/tcp_echo_server_main.ail -o tcp_echo_server
tcp_echo_server 127.0.0.1 0 2 8192
```

最初の行に割り当てたポートを出力し、2接続を順番に処理した後、合計バイト数を出力して終了します。
クライアントは送信したバイトと同じ応答を受け取れます。大きな入力は応答を読みながら送ってください。
成功0、引数数2、通信失敗3、不正引数4です。クライアントが接続・EOF送信をしなければ待機します。

### TCPでバイナリを送受信する（R600）

```ail
fn main()->int {
    let connection: tcpsocket = tcp_connect("127.0.0.1", 9000);
    try {
        connection.send(b"request");
        connection.shutdown_write();
        let buffer = bytearray(8192);
        let count = connection.recv_into(buffer);
        write_stdout_bytes(bytes(buffer[:count]));
    } finally { connection.close(); }
    return 0;
}
```

`tcp_connect(host,port)` はASCIIのホスト名・IPv4・IPv6と、1〜65535のポートを受け付けます。
`send(bytes-or-bytearray)` は全バイトを送った数を返し、失敗ではOSErrorです。
`recv(size)` は最大sizeの独立bytes、`recv_into(buffer)` は受信数を返してバッファの先頭を更新します。
一度で全応答を受け取れるとは限りません。正数サイズでの空受信は相手からのEOFです。
0サイズの受信は通信せず0を返します。recvのsizeは0〜2147483647です。
`shutdown_write()` の後も受信でき、送信はOSErrorになります。
代入・構造体・関数・callbackは同じ接続とclosed状態を共有します。closeは何度呼んでも構いません。
閉じた後の操作はValueErrorです。最後の参照がなくなれば接続を閉じます。
通信は待機型です。期限指定・非同期処理・TLSはまだありません。待受けはR601で追加しました。

```text
python ail_chatgpt.py compile language_examples/tcp_file_exchange_main.ail -o tcp_file_exchange
tcp_file_exchange 127.0.0.1 9000 input.bin output.bin 8192
```

ファイルを分割して送り、送信EOFを通知してから応答を分割保存し、受信バイト数を出力します。
相手は入力EOFまで受信した後、応答をEOFまで送るプロトコルにしてください。
成功0、引数数2、通信・ファイル失敗3、不正引数4です。
不正チャンク・同じ入力出力・入力不在・接続失敗では旧出力を開きません。
後半の通信・保存失敗では出力の一部が残ることがあります。

### 環境変数と作業ディレクトリを使う（R599）

```ail
use environment_config;
fn main()->int {
    print(get_env("AIL_CONFIG_LABEL", "default"));
    print(env_int("AIL_CONFIG_COUNT", 1));
    print(env_bool("AIL_CONFIG_ENABLED", 0));
    print(current_dir());
    return 0;
}
```

`get_env(name,default)` は未設定ならdefault、設定済みの空値なら空文字を返します。
返した文字列は後の呼出しから独立しています。名前は空・NUL・`=`・不正Unicodeを拒否します。
defaultにはNULを含められます。OSから受け取る値とパスは厳格なUnicodeとして扱い、
不正な値はUnicodeDecodeErrorです。`current_dir()` は現在の絶対パスを返します。
`env_int` は整数へ変換し、`env_bool` は空白を除いた1/0/true/false（大文字可）を受け付けます。
不正な値はValueErrorです。環境変数の書換えや作業ディレクトリの変更は行いません。

```text
python ail_chatgpt.py compile language_examples/environment_config_main.ail -o environment_config
environment_config
```

このCLIはAIL_CONFIG_COUNT（既定1）・AIL_CONFIG_ENABLED（既定0）と現在のディレクトリを
一つのJSONとして出力します。成功0、引数数2、OS取得失敗3、不正設定・Unicode4です。

### UTF-8テキストを分割して読む（R598）

```ail
use utf8_reader;
fn main()->int {
    let reader=utf8_reader_open("input.txt",8192);
    try {
        while True {
            let text=utf8_reader_next(reader);
            if text=="" { break; }
            print(text,end="");
        }
    } finally { utf8_reader_close(reader); }
    return 0;
}
```

日本語や絵文字がバイトの読込み境界をまたいでも、完成した文字だけを返します。
空文字はEOFです。不正なUTF-8や末尾の未完文字はValueErrorになります。
チャンクは正数です。`utf8_reader_from_file(file,chunk)` は既存のbinaryfileを共有し、
readerを閉じると元のfileと別名も閉じます。改行・BOM・NULは変換しません。

```text
python ail_chatgpt.py compile language_examples/utf8_copy_main.ail -o utf8_copy
utf8_copy input.txt output.txt 8192
```

厳格UTF-8として読んで同じバイト列を書き、Unicode文字数を表示します。
成功0、引数数2、I/O3、不正UTF-8・チャンク・文字数4です。
同じ入力・出力実体と不正チャンクは出力を開く前に拒否します。
途中の入力不正やI/O失敗では出力の一部が残ることがあります。

### ファイルを開いたまま分割して処理する（R597）

```ail
let file: binaryfile = open_binary("input.bin", "r");
try {
    let buffer = bytearray(16384);
    let count = file.readinto(buffer);
    print(count);
    print(file.tell());
} finally { file.close(); }
```

`read(size)` は有限長のbytes、`readinto(buffer)` は既存バッファへ読んだ数を返します。
バッファの長さは変えず、短い読込みでは残りを保持します。
`write(bytes-or-bytearray)`・flush・seek・tell・closeを使えます。
代入や構造体は同じカーソルと開閉状態を共有し、最後の参照がなくなれば閉じます。
明示closeの失敗はOSError、閉じた後の操作はValueErrorです。

```text
python ail_chatgpt.py compile language_examples/binary_stream_copy_main.ail -o binary_stream_copy
binary_stream_copy input.bin output.bin 16384
```

一定サイズのバッファでコピーし、コピーしたバイト数を出力します。
チャンクは正数、同じ入力・出力実体は拒否します。引数や入力の確認前に旧出力を切り詰めません。
途中のI/O失敗では出力の一部が残ることがあります。成功0、引数数2、I/O3、不正チャンク4です。
modeはr/w/aと各+、bの通常表記が使え、常にバイナリです。テキスト・with構文は追加していません。
更新modeの読書き切替をランタイムが同期し、appendはseek後も末尾へ書きます。
関数・callback・別objectからも使えます。旧objectは新compiler identityで再ビルドしてください。

### バイナリを1バイト単位で書き換える（R596）

```ail
let buffer: bytearray = bytearray(bytes([0, 1, 127, 255]));
let saved = bytes(buffer);
buffer[0] = 42;
buffer.append(7);
print(bytes(buffer).hex());
print(saved.hex());
```

出力は `2a017fff07` と `00017fff` です。バッファの要素は0〜255、実体は1バイトです。
代入・関数・構造体フィールドは変更を共有し、`.copy()`・スライス・コピー構築は独立します。
`bytes(buffer)` は不変コピーです。0引数・長さ・bytes・別buffer・整数リストから構築できます。
負の長さや範囲外の値はValueError、添字の範囲外はIndexErrorです。
append・extend・clear・pop・reverse・len・反復を使え、自己追加による伸長も扱います。
スライスの代入、文字列の暗黙変換、未対応の入れ子コンテナは追加していません。

```text
python ail_chatgpt.py compile language_examples/binary_buffer_example.ail -o binary_buffer_example
binary_buffer_example
python ail_chatgpt.py compile language_examples/binary_buffer_xor_main.ail -o binary_buffer_xor
binary_buffer_xor input.bin output.bin 255
```

`use binary_buffer;` でバッファをその場で変換できます。ファイル例は同じ入力・出力実体を拒否し、
引数と入力を確認してから書き込みます。成功0、引数数2、I/O3、不正キー4です。
関数・callback・別objectリンクから使えます。Pythonのcompile_fn ctypes入口でPython bytearrayを
共有する変換は未対応です。旧objectは新しいcompiler identityで再ビルドしてください。
この実体幅は言語機能の追加であり、Cとの速度優位やプロセス全体のメモリ削減の証明ではありません。

### 構造体に処理を保持して差し替える（R594）

```ail
struct State { offset: int; }
struct Handler { state: State; apply: Callable[[State,int],int]; }
fn add(state: State, value: int) -> int { return value + state.offset; }
fn subtract(state: State, value: int) -> int { return value - state.offset; }
fn main() -> int {
    let handler = Handler(State(3), add);
    let saved = handler.apply;
    handler.apply = subtract;
    print(saved(handler.state, 10));
    print(handler.apply(handler.state, 10));
    return 0;
}
```

出力は13、7です。構造体は同じ型の関数へ処理を差し替えられ、保存した関数値は旧処理を保ちます。
状態は型付きの構造体へ明示的に保持して引数で渡します。クロージャやbound method値の追加ではありません。
既存のcallback引数・戻り値型と所有権規則を使い、関数の型が違う代入やNoneは拒否します。
呼出しは関数を先に選び、その後で引数を左から一度ずつ評価します。
代入は右辺を先に評価し、その後で所有者を評価します。

```text
python ail_chatgpt.py compile language_examples/record_policy_example.ail -o record_policy
record_policy
```

`use record_policies;` で状態付きのレコード選択・表示を再利用できます。
例は閾値以上と未満の選択を切り替え、保存済み関数と訪問回数も示します。
関数フィールドを持つ同型の構造体を直接比較するとValueErrorです。
自己型を関数の引数型へ指定できますが、実際に構造体を所有する循環は引き続き拒否します。
ABI10は維持し、旧objectは変更したcompiler identityで再ビルドします。

### ディレクトリの名前とパスの種類を調べる（R593）

```ail
let names: list[str] = list_dir(".");
for name in names {
    print(name);
    print(path_exists(name));
    print(is_dir(name));
}
```

`list_dir(path)` は直下の名前だけを取得します。`.`・`..` は含めず、順序は未指定です。
`path_exists(path)` は存在、`is_dir(path)` はディレクトリかどうかを0/1で返します。
シンボリックリンクの参照先を調べ、存在しないパスは0、ほかの取得失敗はOSErrorです。
空パスは判定APIで0、列挙APIではOSError、NULを含むパスはValueErrorです。
取得した名前のリストは保存・関数返却・フィールドへ格納できます。

```text
python ail_chatgpt.py compile language_examples/directory_catalog_main.ail -o directory_catalog
directory_catalog .
```

直下の名前をソートし、名前・ディレクトリ判定・存在判定をJSON配列で出力します。
成功0、引数数2、取得失敗3、不正Unicode・パス4で終了します。
POSIXの非UTF-8名やWindowsの不正UTF-16名はUnicodeDecodeErrorです。
Windowsでは列挙パスのワイルドカードを拒否し、POSIXでは名前の一部として扱います。
再帰探索・streaming・列挙中の変更に対する一括の整合性は保証しません。

### 数値リストをコピーし、辞書の要素を更新する（R592）

```ail
fn shifted(values: list[int], amount: int) -> list[int] {
    let result = values.copy();
    for i in range(len(result)) { result[i] += amount; }
    return result;
}
```

整数・小数リストの `.copy()` は独立したリストを返します。読み取り専用の引数からも
コピーを作って更新でき、入力は変わりません。小数のビット列も保持します。
型付き辞書の要素は `counts[key] += 1` のように更新できます。
構造体の辞書フィールドにも使え、文字列・bytes辞書は同じ型の値による `+=` に対応します。
存在しないキーは右辺を実行する前にKeyError、借用辞書の直接更新は引き続き拒否します。

フィールド更新は、所有者・キー・旧値・右辺の順に一度ずつ評価します。
右辺がフィールドを置き換えた場合、保持した所有者の現在のフィールドへ計算結果を書きます。
これはAILの既存フィールド更新と同じ規則です。失敗時に右辺の副作用は取り消しません。

```text
python ail_chatgpt.py compile language_examples/collection_state_example.ail -o collection_state
collection_state
```

出力は順に9、11、2、7です。入力リスト・コピー・辞書の保存済みsnapshotの独立性を示します。
ABI10は維持していますが、旧compiler identityのobjectは再ビルドしてください。

### CSVを選択・集計してJSONへ出力する（R590）

```text
python ail_chatgpt.py compile language_examples/record_report_main.ail -o record_report
record_report input.csv report.json positive
```

入力はheaderなしの2列CSV（文字列キー、符号付きASCII整数）です。
`all`・正数だけの`positive`・0以外の`nonzero`から選び、初期順と重複キーを保ちます。
全行を検証してから選択し、選択対象の合計をint64の範囲で確認します。
出力は `{"rows":[{"key":"a","value":3}],"count":1,"total":3}` の形式、末尾改行なしです。
quoted改行・comma・quote、Unicode・NUL、整数の最小/最大値を扱います。

`use record_report;` でread/select/total/render/runを分けて再利用できます。
`ReportConfig` は `ReportPaths` を保持し、選択には型付きcallbackを使っています。
成功0、引数数2、I/O3、不正UTF-8/CSV/整数/mode/合計4です。
検証失敗時は旧出力を保ち、同じ実体の入力・出力は書込み前に拒否します。
`same_file(path1,path2)` も標準APIとして使えます。存在しないpathはfalse、識別失敗はOSErrorです。
実行中のpath差し替えや書込み途中の原子性までは保証しません。

実装はAILの型・標準ライブラリを組み合わせています。Cは独立した比較参照です。
固定8193行の測定は全文一致ですが、前後A/Aが変動しているため速度優位は未判定です。
読込み・解析の観測割合約56%とAmdahl上限約2.29倍は、正式な速度資格とは区別してください。

R591では元の参照を残し、キー所有領域を必要量で確保するC候補を別ファイルへ作りました。
固定入力では所有キー要求33,558,528→114,248 byte、別の作業bufferは4,096 byteです。
これはC候補の要求量であり、AILのメモリ改善やプロセス全体のピークを示しません。
候補とのLinux固定64実行は校正を通過し、AIL21.4ms/C3.2ms、read/parseの比較は約12.3ms/1.3msでした。
最善のCの証明や全用途への一般化ではありません。AILの改善対象を選ぶための基準です。

### 値を使わずに式を実行する（R589）

```ail
read_bytes(path).decode();
text.encode();
parts[0];
False and fail();
```

対応済みの値を一度評価して、結果を捨てられます。副作用・境界検査・例外は通常どおり発生し、
短絡で実行しない分岐は実行しません。文字列・bytes・コンテナ・構造体の結果は既存の回収処理で解放します。
print・I/O・void関数・文専用の更新操作も使えます。それらを代入の右辺として使えるようにする変更ではありません。
未対応の操作やgeneratorを、結果を捨てるだけで使えるようにはしません。

```text
python ail_chatgpt.py compile language_examples/utf8_validate_main.ail -o utf8_validate
utf8_validate input.txt
```

入力全体をstrict UTF-8で検証し、成功なら `valid UTF-8` と出力します。入力は変更しません。
成功0、引数数2、I/O3、不正UTF-8 4です。全入力を読み込む方式で、速度優位やstreamingのメモリ上限は未証明です。

### 受けた例外を呼出し元へ返す（R588）

```ail
fn checked(value: str) -> int {
    try { return int(value); }
    except ValueError {
        print("invalid number");
        raise;
    }
    return 0;
}
```

`raise;` は、現在処理中の例外を同じ種類で再送します。呼び出したhelper・callback・別objectでも使えます。
処理中の例外がなければRuntimeErrorです。内側で別の例外を処理しても、終了後は外側の例外に戻ります。
伝播中のfinallyは保留された例外を扱い、通常のfinallyは外側の現在の例外を引き継ぎます。
例外のメッセージ・traceback・`raise ... from ...`・独自例外クラスは未対応です。

```text
python ail_chatgpt.py compile language_examples/reraise_example.ail -o reraise_example
reraise_example
```

この例は `invalid record`、`caller caught ValueError` を出力して終了します。
既存objectは変更したcompiler identityで再ビルドしてください。

### 利用者定義型を共通の処理へ渡す（R587）

```ail
use record_queries;
fn positive(row: QueryRecord) -> int { return row.value > 0; }
fn value(row: QueryRecord) -> int { return row.value; }
fn main() -> int {
    let rows: list[QueryRecord] = [QueryRecord("a", -1), QueryRecord("b", 3)];
    let selected = query_select(rows, positive);
    print(query_total(selected, value));
    selected[0].value = 7;
    print(rows[1].value);
    return 0;
}
```

出力は3、7です。predicateの型は `Callable[[QueryRecord],int]`。
選択結果のリストは独立し、各レコードは共有します。入力順を保ち、訪れたレコードごとにpredicateを一度呼びます。
`Callable[[Point],Point]` のように構造体を返す関数も渡せます。戻された参照は、引数や親を置き換えた後も保持できます。
文字列・bytes・整数/小数リストを返す既存のcallbackにも構造体引数を使えます。
関数の選択を一度、引数を左から一度ずつ評価します。後続引数の副作用があっても先に選んだレコードを保持します。
型名が違うレコード、None、未知型は拒否します。クロージャ・bound method値・関数のfield/container保存は未対応です。
objectの署名にも型提供元への依存を記録します。旧objectは再ビルドしてください。

### 構造体の中に別の構造体を保持する（R586）

```ail
struct Point { x: int; y: int; }
struct Rect { origin: Point; width: int; }
fn main() -> int {
    let point = Point(2, 3);
    let rect = Rect(point, 4);
    let saved = rect.origin;
    point.x = 5;
    print(rect.origin.x);
    rect.origin = Point(8, 9);
    print(saved.x);
    return 0;
}
```

出力は5、5です。親は子の参照を保持し、読み出した子も同じ値を共有します。
親の置換・解放後も、取り出して保持した子を使えます。複数段のフィールドアクセスとメソッド呼出しに対応します。
コンストラクタ引数は左から一度、フィールド代入は右辺→所有者の順に評価します。
宣言型と違う構造体やNone、未知型、構造体リストを含む循環した所有関係は拒否します。

`use geometry2d;` では `Point2`、2つのPoint2を持つ `Box2` と、
`box2_new`・境界を含む `box2_contains`・独立した子を作る `box2_copy` を使えます。
newは軸の下限≤上限を確認し、不正な順序やNaNはValueErrorです。公開フィールドの変更は共有相手にも反映します。
ABI10を維持していますが、以前のcompiler identityで作ったobjectは再ビルドしてください。

### 構造体の辞書を直接更新する（R585）

`dict[str,int]` / `dict[str,float]` / `dict[str,str]` / `dict[str,bytes]` の
フィールドに要素代入・削除、`clear`・`update`・`pop`・`setdefault` を使えます。

```ail
struct Counts { values: dict[str,int]; }
fn add(counts: Counts, key: str) -> int {
    let total = counts.values.setdefault(key, 0) + 1;
    counts.values[key] = total;
    return total;
}
```

読み出した辞書は独立したsnapshotです。更新は共有する構造体の現在のフィールドに作用します。
メソッドは所有者→引数、要素代入は右辺→所有者→キーの順に一度ずつ評価します。
キーは文字列、値とdefaultは宣言した型を使います。小数辞書では整数からの変換も使えます。
欠けたキーの削除・defaultなしpopはKeyErrorです。clear/updateは文として使います。
辞書引数そのものへの更新は拒否します。構造体の辞書フィールドでは、数値の演算と文字列・bytesの`+=`に対応しています。

再利用部品 `use named_counters;` はnew・add・snapshotを提供します。
次のCLIはUTF-8の各行を集計し、初出順にUTF-8キーのhexと件数をタブ区切りで出力します。
空行・NUL・Unicodeを区別できます。入力全体を読み出すため、ストリーミング処理ではありません。

```text
python ail_chatgpt.py compile language_examples/line_counts_main.ail -o line_counts
line_counts input.txt counts.tsv
```

成功0、引数数2、I/O3、UTF-8不正4。入力検証が失敗した場合は旧出力を保ちます。
書込み途中のatomic性や速度優位は保証しません。整数overflowは従来どおり実行停止です。

### 数値リストの範囲を代入・削除する（R584）

構造体の `list[int]` / `list[float]` フィールドにslice代入・削除を使えます。

```ail
samples.values[1:3] = [1.5, 2.5, 3.5];
samples.values[::-1] = samples.values;
del samples.values[::2];
```

stepが1なら挿入・短縮・長さの変更ができます。その他のstepでは、代入する要素数と選択範囲の要素数が
完全一致する必要があります。不一致とstep0はValueErrorで、更新操作前の値を保ちます。
正負の動的step、省略した境界、範囲外のclipping、int64最小・最大境界を扱います。
右辺を独立したリストにしてから、所有者・lower・upper・stepを左から一度ずつ評価し、最後の現在のfieldを更新します。
削除は所有者から評価します。境界の関数自身の副作用は取り消しません。整数・小数の型は完全一致が必要です。
通常の読込み・copy・slice・保持した結果は独立snapshotのままです。

`numeric_ring` に `sample_ring_extend(ring, values)` と `sample_ring_feed_batch(ring, data)` を追加しました。
一括版は同じ生bit出力を確認していますが、速度優位は未判定です。既定の `sample_ring_feed` は従来方式を維持します。
この改訂は言語機能の追加です。一括処理の候補と比較したsource・入力・結果は保存しています。

### 数値リストの長さをコピーなしで読む（R583）

`len(owner.integers)` / `len(owner.floats)` は、所有者を一度評価して保持し、検査後の長さだけを返します。
長さを読むために全要素のsnapshotを作りません。空・不正span・巨大長の検査は従来のsnapshotと共通です。
通常のフィールド読込み、copy、sliceは引き続き独立したリストを作ります。

同じ16MiBのサンプル処理で、長さ取得のsnapshot6,283,520回・copy411,309,901,792 byteを0へ除去し、
必要な保持snapshot4回・131,088 byteを維持しました。各実行の出力は独立した生byte参照と全文一致しています。
前後の観測中央値は9.41秒→74.3msですが、正式な速度資格・C以上の効率とは別の観測です。
この変更は数値リストの直接フィールドに共通して適用します。ABI10のobjectは再ビルドしてください。

### 構造体の中の数値リストを更新する（R582）

`list[int]` / `list[float]` のフィールドへ直接append・extend・pop・clear・reverse、
整数添字による要素代入・削除ができます。構造体を部品の状態として使えます。

```ail
struct Samples { values: list[float]; }
fn add(samples: Samples, value: float) -> void {
    samples.values.append(value);
}
```

読み出しとcopyは従来どおり独立したリストです。更新後も、前に読み出した値を保持できます。
メソッドは所有者を先に一度選び、引数を評価してから、その所有者の現在のフィールドへ操作します。
引数の関数がフィールドを置換した場合は置換後の内容を更新します。値をコピーして後から書き戻す操作ではありません。
要素代入は右辺→所有者→添字、削除は所有者→添字の順です。各式を一度だけ評価します。
負の添字を扱い、範囲外・空popはIndexErrorです。更新前の引数が例外になれば更新操作を行いません。
引数自身の副作用は取り消しません。整数・小数の型は完全一致が必要です。
pop以外のメソッドは文として使います。R584でsliceへの代入・削除に対応します。sortと`+=`は未対応です。

標準部品 `use numeric_ring;` では、`sample_ring_new(capacity)`、`sample_ring_push(ring, value)`、
`sample_ring_snapshot(ring)` と、little-endian binary64の分割入力を処理する `sample_ring_feed(ring, data)` を使えます。
capacityは正の整数、保持する要素数はcapacity以下です。feedは完成した要素を取り込み、未完成の最大7byteを返します。
snapshotは古い順の独立した小数リストです。clearは確保済み容量を保持し、所有者の解放時にbufferも解放します。
公開フィールドを手動で変更してcapacity・長さ・nextの関係を壊した場合は、push・feed・snapshotがValueErrorで拒否します。

```text
python ail_chatgpt.py compile language_examples/sample_tail_main.ail -o sample_tail
sample_tail input-f64le.bin output-f64le.bin 8193
```

CLIは64KiB以下のfile_chunksを使い、最後の指定個数のbinary64サンプルを古い順に書き出します。
末尾が不完全なら書込み前に拒否します。成功0、引数数2、I/O3、不正capacity・データ4。
読込み・検証の失敗では旧出力を保ちます。書込み途中のatomic性、プロセス全体のメモリ上限、速度優位は未証明です。
NaN payload・符号付きゼロを含むビット列の移動を検査しています。値に浮動小数演算を加える機能ではありません。

### 構造体レコードを数値処理へ渡す（R581）

構造体のリストから整数・小数のリストを作る、単一の内包表記を使えます。

```ail
struct Point { x: float; y: float; }
fn energies(points: list[Point]) -> list[float] {
    return [p.x * p.x + p.y * p.y for p in points if p.x >= 0.0];
}
```

源を一度評価し、各要素でfilterを評価してから結果を作ります。束縛変数は外側の同名変数を変更しません。
構造体リストは通常のforと同じ共有参照です。走査中のclear・appendは後続の走査へ反映し、
元の変数の再代入は既に選んだリストを置き換えません。処理中の要素はclear後も保持します。
結果の数値リストは独立しており、右辺の例外では代入前の結果を保ちます。
構造体・文字列を結果にする形、混在型、入れ子、複数generatorはこの追加の対象外です。
源は名前・関数結果・構造体フィールド・sliceに対応します。構造体literalリストを直接源にする形は未対応です。
型付きの空リストも初期化できます。`let points: list[Point] = [];` と、型が確定したリストへの `points = [];` を扱います。

同梱の `language_examples/points_energy_main.ail` はlittle-endian binary64の座標ペアを読み、
各ペアの `x*x+y*y` をbinary64ファイルへ書きます。PythonやCの処理部品を呼ぶことなくAILで処理します。

```text
python ail_chatgpt.py compile language_examples/points_energy_main.ail -o points_energy
points_energy input-f64le-pairs.bin output-f64le.bin
```

終了コードは成功0、引数2、I/O3、不完全なペア・binary64データ4です。
入力検証の失敗では旧出力を保ちます。書込み途中の失敗についてatomic性は保証しません。
浮動小数の演算は既存のbinary64契約に従い、これは新機能の追加で、速度優位の実証ではありません。

## 開発用SDKを別の場所で使う（R561）

R570では関数を引数・戻り値・ローカル変数として扱えます。共通処理に、実行する関数を渡せます。

```ail
fn twice(x: int) -> int { return x * 2; }
fn apply(values: list[int], operation: Callable[[int], int]) -> int {
    let total = 0;
    for value in values { total += operation(value); }
    return total;
}
fn main() -> int {
    let operation: Callable[[int], int] = twice;
    print(apply([1, 2, 3], operation));
    return 0;
}
```

Callableの引数はint/float/str/bytes/list[int]/list[float]です。R571では結果にstr/bytes/
list[int]/list[float]も使え、呼出し元がその保存領域を所有します。結果を保持したまま次の呼出しができます。
文字列・配列の引数は読取り専用。型は完全一致が必要です。静的な関数を選んで保持・再代入し、
factoryから返せます。通常ビルド・分離ビルド・ソース不要objectでも同じ型を使います。
呼び出す関数と引数は左から一度ずつ評価します。未初期化の呼出し・間接再帰の上限はRuntimeErrorです。
間接呼出しは共有の関数深さ512を上限とし、対象プログラムの通常の関数フレームも数えます。
クロージャ、lambda、関数を含むコンテナ・構造体、入れ子のCallable型は未対応です。
ABI10は維持しますが、以前のobjectは再ビルドしてください。

R571の `callback_text_pipeline` は、利用者の整形関数を渡せるテキスト変換部品です。
`rewrite_lines(text, operation)` は各 `splitlines()` 要素に順番どおり一度ずつ関数を適用し、
LFで連結します。元の文字列がLFで終わる場合だけ末尾LFを付け、空入力は空出力です。
同梱の `callback_text_rewrite_main.ail` はUTF-8ファイルを `trim` / `frame` で変換します。
不正modeはファイル操作前に拒否。終了コードは成功0、引数2、I/O3、UTF-8/変換エラー4です。

```ail
use callback_text_pipeline;
fn decorate(line: str) -> str { return "[" + line + "]"; }
fn main() -> int {
    let text = read_bytes(sys.argv[1]).decode();
    let result = rewrite_lines(text, decorate);
    write_bytes(sys.argv[2], result.encode());
    return 0;
}
```

文字列の内包表記も使えます。たとえば `[decorate(line) for line in text.splitlines()]`、
`[str(i) for i in range(n) if i % 2 == 0]` は `list[str]` を作ります。
単一generatorの対応するrange・名前付き配列・slice・split結果を扱い、束縛は外側の同名変数を保ちます。
右辺が失敗した場合は代入前の値を保ちます。複数generator・async・混在/入れ子は未対応です。
`str * int` / `int * str` の反復も使えます。左右を一度ずつ順に評価し、非正回数は空文字列。
Unicode/NULを保持し、非空結果は独立した領域を所有します。大きすぎる結果・OOMは致命的停止です。

R572ではリストを名前へ代入せず、そのまま走査できます。

```ail
for mode in ["trim", "frame"] { print(mode); }
let doubles = [x * 2.0 for x in [1.5, 2.25]];
print(sum([1, 2, 3]));
```

整数だけ、小数だけ、文字列だけの平坦なリストと空リストを扱います。
全要素を左から一度ずつ評価してから、ループ・絞り込み・集約を始めます。
内包表記・generatorの同名変数は外側を変更しません。通常forの変数は既存の固定型を使います。
連続sliceを走査源に使え、数値sliceを値として作る場合は既存の正負stepも使えます。
混在・入れ子・bytesの直接リスト走査は未対応です。空リストの既定要素型はintです。
`callback_text_variants_main.ail` は一つのUTF-8入力を読み、出力prefixへ `.trim.txt` と `.frame.txt` を作ります。
引数2、I/O3、不正UTF-8/変換4、成功0で終了します。二つの出力は順番に書くため、一括更新の保証はありません。

R573では文字列を源にする内包表記と、数値へ変換する集約も使えます。
`[character for character in text]` は `list[str]`、`[len(character) for character in text]` は `list[int]` を作ります。
文字の単位はUnicodeコードポイントです。絵文字のUTF-16ペアは一つ、結合文字は別々に走査します。
源を一度保持してから順番に処理するため、後続の関数呼出しや同名変数の束縛で走査元が変わりません。
`sum(len(character) for character in text)` のように、int/float結果へ変換するsum/min/maxが使えます。
any/allのgeneratorは短絡し、リスト内包表記を渡す場合は要素を全部作ってから判定します。
空のsumは0です。既存の空min/maxは致命的停止、未変換文字列のsum/min/maxは拒否します。

同梱の `text_characters` の `map_characters(text, operation)` に `Callable[[str], str]` を渡せます。
`text_escape_main.ail` はUTF-8入力のbackslash・NUL・TAB・CR・LFを可視のescape文字列へ置き換えます。
終了コードは成功0、引数2、I/O3、不正UTF-8/変換4です。入力失敗では旧出力を保ちますが、書込みのatomic性は保証しません。

R575では、所有文字列を返す型付きcallbackの内包表記をすぐjoinする場合、中間リストを省く経路があります。
たとえば `"".join([operation(character) for character in text])` は結果を連結先へコピーし、各callback結果を解放します。
区切りを先に保持し、入力・callback・filterの評価順を保ちます。空要素の間にも区切りを入れます。
保持する名前付きリスト、複雑な述語、対象引数以外を渡す呼出しなどは従来のリスト経路を使います。
既存の実用文字変換では、同じ全文出力で約1MiB入力の明示要求peakが102,446,598から9,962,361 byteへ減りました。
これは要求量の比較で、物理RSS・全用途のメモリ優位・確定した速度差ではありません。

R576では、入力引数または固定文字列だけを返す関数を、安全な即時joinで借用して使えます。
実行時に関数pointerが検証済みの対象と一致する場合だけ、内部の借用版を呼び、連結直後に所有結果を解放する経路を省きます。
公開Callableの所有結果、未知のcallback、ソース不要provider、副作用や確保を含む関数は従来の契約を使います。
NULL・深さ512・例外時のcounter/cleanupを維持します。
同じ約1MiBの文字変換ではmapの確保要求が629,168から20回へ減りました。peakは9,962,361 byte、終了後live0です。
時間の校正は未通過なので、速度差・最良C以上・全用途の達成としては扱いません。

R577では、新しく連結した所有文字列をそのまま関数から返す場合、bufferの所有者を呼出し元へ引き渡します。
通常の変数・literal・view・finallyで保留するreturnは従来のコピーを保ちます。公開の所有権契約は変わりません。
同じ実用入力で返却時の1,887,444 byteの確保・コピーを除き、peak要求は8,075,007 byteへ減りました。
速度は未校正です。コピー量と寿命・例外の検証に基づく変更です。

R578では、即時joinのcallbackが検証済みの純粋なSTR関数に実際のpointerで一致する場合、入力snapshotも省きます。
区切り・入力・callback値の順に評価し、入力の所有者が生存する間だけ借用します。
未知・副作用あり・sourcefreeで証明できないcallbackは従来の入力コピーを維持します。
同じ実用入力で1,363,154 byteの確保・コピーを除き、map確保18回、copy要求838,864 byte、終了後live0を確認しました。
peak要求は8,075,007 byteで変わりません。時間の校正は未通過です。

R579ではUTF-8 encodeを一回走査の容量調整へ変更しました。初期容量はUTF16単位数の1.5倍を切上げ、
必要時だけ成長し、従来の最大幅内に収めます。返すbytesの長さは実際に書いたUTF-8 byte数です。
同じ実用入力でencodeの確保要求2,831,166→1,415,583 byte、全体peak8,075,007→6,659,424 byteへ減りました。
この入力では再確保なし。別入力では成長が必要です。巨大長・不正サロゲート・OOMの既存拒否を維持します。
正確な長さを事前計数する候補は計数費が増える観測があったため採用せず、比較記録だけ残します。
速度差は未確定です。

R580では `read_bytes(...).decode()` や所有bytesを返す直接の関数呼出しについて、
独立した文字列へdecodeした直後に一時bytesを解放します。不正UTF-8の例外でも解放します。
名前で保持したbytes、literal、sliceなどの寿命は変えません。

R569では `try { ... } finally { ... }` が使えます。正常終了、名前付き例外、
`return`・`break`・`continue` で抜ける場合に実行します。`except`・`else` とも組み合わせられます。
戻り値はfinallyより先に一度評価し、文字列・bytes・整数/小数リストはその内容を保存します。
finallyからのreturn・例外・break・continueは保留中の終了を上書きします。
grid・tuple・複数リストABI・混在行・unmanaged objectを返しながらfinallyを通る経路は
まだ拒否します。これらはfinallyを完了してから返してください。致命的停止・OOMは実行保証の対象外です。

R568では `range(start, stop, step)` の正負の動的stepを扱えます。
通常のfor、整数・小数の内包表記、保存したrange、`list(range(...))` で使えます。
引数は左から一度ずつ評価します。stepが0なら空範囲でも `ValueError` です。
3引数版の要素数はint64上限までで、それを超える範囲は反復前に停止します。

R567では小数の内包表記・絞り込み・返却が使えます。たとえば
`return [value * factor for value in values];` は `list[float]` を返します。
小数列の走査では値を整数に切り捨てません。整数との混在・入れ子は拒否します。

R566では整数リストの内包表記を代入する際の全件再コピーを除去しました。
右辺の完成後に保存領域を渡し、右辺の例外時は代入前の値を保ちます。
`range` 引数の評価は左から一度ずつです。既存objectは再ビルドしてください。

R564では整数データの一括変換を追加しました。`use binary_integers;` で
`pack_integers(values, width, order)` と `unpack_integers(data, width, order)` を使えます。
幅1/2/4は符号なし、幅8は符号付き64ビット、orderは0（little endian）/1（big endian）です。
不正な幅・順序・範囲・端数長は `ValueError`。結果は独立した保存領域を持ちます。

```ail
use binary_integers;
fn main() -> int {
    let values = [0, 1, 4294967295];
    let data = pack_integers(values, 4, 0);
    let decoded = unpack_integers(data, 4, 0);
    write_stdout_bytes(pack_integers(decoded, 4, 1));
    return 0;
}
```

組込み `integer_encode` / `integer_decode` も同じ引数で使用できます。
引数は左から右に一度ずつ評価し、後続引数に変更の可能性があれば入力を先に保存します。
整数リストとbytesを同時に保持するAPIです。既存の単一整数用 `binary_numbers` も使えます。

R565では、関数へ渡した整数リストの添字を通常・分離・objectリンクで統一しました。
`xs[-1]` は末尾、`xs[-len(xs)]` は先頭です。空リストや範囲外は `IndexError`。
前版では通常ビルドがこの検査を省く場合がありました。修正後は既存objectを再ビルドしてください。

SDKの整数レコード集計例はR562へ更新済みです。入力と例外処理をmainに置き、
集計ループと報告作成を `binary_records_report` に分けています。同じ出力を両OSで確認し、
固定Windowsの全6組で旧版より全体時間が短くなりました。全プログラムで同じ効果を保証しません。

`../AIL_SDK_CURRENT` に言語コンパイラ・標準AIL部品・接続例をまとめています。
説明は `../AIL_SDK_CURRENT/SDK_README_JA.md`。PythonとCコンパイラは別途必要です。
開発元の履歴・モデル・計測記録を持ち運ぶ必要はありません。
自分の `.ail` はSDKの外で編集し、SDK内の `ailc.py` を指定してコンパイルできます。

新しい内容を書き出す場合は、AIL_CURRENTから次を実行します。出力先は既存の親の下の新規ディレクトリです。

```powershell
& 'C:/path/to/python.exe' -X utf8 -B .\ail_chatgpt.py export-sdk -o ..\my-ail-sdk
```

SDKは独立したスナップショットです。開発・更新の正本は引き続きAIL_CURRENTです。
クリーンな新規PCへの導入、全例・全回帰検査、外部公開は未確認です。

## 自分のプロジェクトで標準部品を使う（R560）

標準部品のソースをコピーせず、任意のプロジェクトの `.ail` から `use` できます。

```ail
use binary_numbers;
fn main() -> int {
    write_stdout_bytes(pack_u16_le(513));
    return 0;
}
```

この内容を `app.ail` に保存し、AILの `ailc.py` を指定してコンパイルします。
このPCでは `py -3` がPythonを検出できないため、確認済みの実行ファイルを直接指定します。

```powershell
$ailPython = 'C:/path/to/python.exe'
$ailCompiler = 'C:/path/to/AIL_CURRENT/ailc.py'
& $ailPython -X utf8 -B $ailCompiler .\app.ail -o .\app
.\app.exe
```

下の既存コマンド例の `py -3` は、このPCでは `& $ailPython` に置き換えて実行してください。
出力は `01 02` の2byteです。独自ライブラリは `-I lib` または `--module-path lib` で追加でき、
複数指定できます。相対ディレクトリはコマンドを実行した場所を基準にします。

`use name;` は、取り込む側のファイルの隣、指定した `-I` の順、AIL同梱の
`language_examples` の順に `name.ail` を探します。見つかったファイルが不正な場合は拒否し、
後の候補へ切り替えません。入れ子の `use` にも同じ順序を適用します。
`compile`・`compile-module`・`compile-library` で利用できます。
`--module` による明示ファイル指定と、`--object` による元ソース不要リンクも引き続き使えます。
標準部品に外部C依存がある場合、そのobjectは別途ビルドして指定します。
これは開発時の部品検索の追加で、実行速度の改善を示すものではありません。

## ファイルをbytesのカーソルへ読み込む（R552）

`use binary_cursor_file;` の `binary_cursor_file(path)` は、読み込んだbytesを
`BinaryCursor`へ渡します。新しく作られたbytesをフィールドへ直接代入する場合、
コンパイラが所有権を移し、入力全体の二重コピーを省きます。
既存のbytes変数やスライスを代入する場合は、従来のコピーを保ちます。
ファイル用の余分な読込み容量は縮めてからフィールドに渡します。
メモリ削減を確認した変更です。固定Windows比較では旧版から約1.18倍の本体時間短縮と
プロセスのPeakWorkingSet低下を観測しましたが、測定の揺れがあり時間の正式優位は未実証です。
C参照よりは遅いままです。詳細は `../AIL_LATEST_DEV_20260928.md` のR553にあります。

## WAV音声を変換する（R557）

`wav_audio_main.ail` は16bit PCMのモノラル・ステレオWAVを読み、音量変更または切出しを行います。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o "$env:TEMP\wav-identity.o"
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/wav_audio_main.ail --object "$env:TEMP\wav-identity.o" -o "$env:TEMP\wav-audio.exe"
& "$env:TEMP\wav-audio.exe" gain input.wav output.wav 1 2
& "$env:TEMP\wav-audio.exe" trim input.wav excerpt.wav 44100 22050
```

gainの引数は整数の分子・分母。分子は-65536～65536、分母は1～65536です。
負値もゼロ方向へ丸め、signed16の範囲へ飽和させます。負の分子は位相を反転します。
trimの引数は最初のフレームとフレーム数。ステレオでは左右の組を1フレームと数えます。
RIFFのサイズ、チャンク境界・パディング、PCM形式、フレームの整合性を検査します。
fmtは16/18byte、PCMの18byte形式のcbSizeは無視します。fmt/dataは各一つ、順序は自由です。
未知チャンクと付加メタデータはbyte単位で保持し、時間位置などの内容を再計算しません。
圧縮音声、8/24/32bit、RF64、WAVE_FORMAT_EXTENSIBLEはこのAPIの対象外です。
入力と同じファイルへの書込みは拒否します。検証エラーはstatus 2、I/Oエラーは3です。
同一ファイルの判定は既存のOS用C部品を使い、音声の解析・変換はAILで実装しています。
検証と変換が終わってから出力を書きます。書込み障害による部分出力の巻戻しは保証しません。
ライブラリの入口はwav_pcm16_parse / pcm16_gain / pcm16_trim / wav_audio_gain / wav_audio_trimです。
入力全体をメモリへ読みます。R559のgainは標準ランタイムの `pcm16_scale_le` で、
一度の出力確保へ直接変換し、中間整数配列とチャンク結合を省きます。
Windows CPU0の固定比較では本体中央値が旧AIL20.90ms→新AIL9.25ms、独立C8.70msでした。
PeakWorkingSet中央値も22,708KiB→18,226KiB。時間には大きな揺れがあり正式優位は未実証です。
Linuxの速度と必要ピークは未測定。比較条件は `../AIL_LATEST_DEV_20260928.md` のR559にあります。
独立参照との全文一致、通常・分離・元ソース不要リンクをWindows/Linuxで確認済みです。
形式の根拠：[Microsoft RIFF](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-)
と[WAVEFORMATEX](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/ns-mmeapi-waveformatex)。

## 小数の区間と余り（R555）

floatにも `//`、`%`、`//=`、`%=` を使えます。
例えば `5.5 // 2.0` は `2.0`、`-5.5 % 2.0` は `0.5` です。
余りは除数の符号を持ち、ゼロ除算は `ZeroDivisionError` になります。
整数同士の演算は従来のint64のままです。小数と混ぜるとbinary64へ変換します。
負のゼロも保持します。NaNのペイロード・符号は保証しません。

## 型を推論した小数変数を更新する（R550）

floatの局所変数・引数にも `+=`、`-=`、`*=`、`/=`、`**=` を使えます。
明示的な型注釈がなくても、既存のbinary64演算と同じ意味で処理します。

```ail
fn main() -> int {
    let value = 1.5;
    value += 0.5;
    value *= 3.0;
    value /= 2.0;
    print(value);
    return 0;
}
```

出力は `3.0`。右辺は一度だけ評価し、右辺や演算が例外を投げた場合は更新前の値を保持します。
floatの `//=`、`%=` も使えます（R555）。ビット演算は拒否します。
通常ビルドと元ソースのないAIL部品、binary64の符号付きゼロ・subnormal・丸め・非有限値、
10003回の更新と途中例外を独立Pythonの全byteに照合。新規3項目を両OSで確認しました。
これは言語機能の追加であり、高速化の主張ではありません。

## CSVの小数列をキー別に集計する（R525）

`csv_float_group_main.ail` はCSVを読み、各キーの件数・合計・最小・最大をJSONへ出力します。
AIL_CURRENTからビルドします。Windowsでは出力先に一時フォルダを指定できます。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/csv_float_group_main.ail -o "$env:TEMP\csv-float-group.exe"
& "$env:TEMP\csv-float-group.exe" input.csv 0 1 65536
```

引数は入力ファイル・キー列・値列・読込みサイズ。列番号は0始まり、サイズは正のint64です。
数値はASCIIの符号・小数点・指数表記を受理し、空白・桁区切り・NaN/Infを拒否します。
有限のbinary64へ変換できる値だけを集計し、underflowによる符号付きゼロは受理します。
入力順のbinary64加算なので、十進数の厳密計算や並べ替え可能な加算ではありません。
途中の非有限な合計や件数オーバーフローもエラーです。
先に現れたキーの順序を保ち、最小・最大が同値なら最初の値のビットを保持します。

入力・構文・列・集計のエラーではJSONを出力せず、stderrとstatus 2で終了します。
成功時は全結果とLFを出力し、flushの失敗も捕捉します。出力障害時の部分書込みは巻き戻せません。
ライブラリはchecked_float64 / csv_float_group、集計のsnapshotは所有する値です。
addのValueErrorではそのバッチの変更を反映せず、再試行できます。

新規8＋既存2＝10項目が両OSでPASS、skip0。通常・分割・移動後ソース不要リンクを確認。
型付きstruct-listの直接引数の誤判定も修正しました。ABI10・runtimeを維持。
速度・必要ピークは未測定。初版の達成記録は5/12（42%）、開発goalは継続中です。

## 小数値を名前で保持する（R524）

`dict[str, float]` を型付き変数・関数・メソッド・構造体のフィールドで使えます。
キーは文字列、値はbinary64です。例えば次のfn/let構文で集計できます。

```ail
fn main() -> int:
    let totals: dict[str, float] = {"sample": 1.5}
    totals["sample"] += 0.25
    print(totals.get("sample", 0.0))
    return 0
```

keys()/values()/copy()は所有するスナップショットを返します。
values()はlist[float]で、sum/min/max/enumerate/reversedにも対応。
借用引数は読取り専用、フィールドはスナップショット取得と全体置換です。
整数値はbinary64へ変換され、2^53を超える整数の精度は保証しません。
通常ビルドと分割・ソース不要リンクを両OSで検証。ABI10の新しい型名はfdict。
新規9＋既存4＝13項目がWindows/Linux各PASS、skip0。
速度・全体ピークメモリは今回測定していません。初版の達成記録は5/12（42%）のまま。

## Windowsで同じ整数レコードを測定する（R523）

Windows x64・単一CPUグループ・CPU0向けの測定ドライバを追加しました。
同じ入力1,048,577件、256反復、O2、既存の測定順序と1.10基準を使用します。
Cの集計処理・全文照合は変更せず、Windowsの時刻・使用量・引数の処理だけ対応。
各反復でwide argvを解放し、原本・生成C・実行ファイル・入力・参照の不変を確認します。

358.454sで4ビルド、24境界、4誤出力制御、76拒否検査、26測定実行を完走。
130呼出しのCPU0・hash/mtime保持と全文一致を確認しました。
ただしAIL A/A 1.0770・計測負荷1.1165、C A/A 1.2652・計測負荷1.3225で校正不成立。
時間の優劣は未認定です。診断上の変換割合90.20%、Amdahl上限10.20倍、
参照能力の仮定100%に対し達成2.415%も未資格値で、候補実装の根拠には使いません。
PeakWorkingSetSizeは必要ピークやLinux RSSと同一の指標ではありません。

Defenderのフォルダーアクセス制御（event1123）がPythonのOneDrive保存を拒否しました。
明示的な --record-root は既存の一時フォルダ配下だけを許可し、新規ファイル・リンク拒否を維持。
既定では元の作業フォルダ/MANIFEST確認を維持し、セキュリティ設定は変更していません。
成功・失敗記録の所在とSHAはAIL_LATEST_DEV_20260928.md冒頭へ。
新規判定5件は両OS、既存判定7件はWindows、時刻・幅境界18件はnative CでPASS。
本体/runtime/ABI10はR522のまま。速度採用なし、初版5/12（42%）、goal active。

## 出力の確定と書込み失敗を捕捉する（R522）

共通API `flush_stdout();` を追加しました。引数なしの文で、値としては使えません。
stdoutのstdio bufferを出力し、flush失敗または既存のerror flagをOSErrorとして捕捉できます。
空のflushも許可。成功時だけdirtyを解除し、text/bytesの出力モードを変更しません。
fn/let構文とPython構文はどちらも .ail ファイルでビルドできます。

```text
fn main() -> int {
    try { print("result"); flush_stdout(); return 0; }
    except OSError { print("output failed", file=sys.stderr); return 2; }
}
```

検索CLIで、正常入力でもLinuxの/dev/fullへ出力すると終了0・stderrなしになることを再現。
print後にこのAPIを呼び、出力失敗を終了2・output write failedへ修正しました。
入力読込み失敗の既存メッセージは保持します。失敗までに書いた出力は巻き戻しません。

Linux/Windows各distinct11件PASS。両構文・通常/分割、stdin待ち前の可視性、
整数/float/Unicode/NUL、raw bytes、型切替拒否、chunkループで保持したbytes、
同名ユーザー関数、source-free libraryの移動後2再リンクを確認。
5用途（CSV/JSON/検索/整数集計/binary64変換）は独立した正常全文参照と
readonly stdoutへの正確な失敗終了を検査し、入力・原本・出力先/objectのhash/mtimeを保持。
Linuxは/dev/fullも確認。Windowsのこの検査はreadonly descriptorを使用します。
初回のfixture/検査指定の失敗を修正し、影響した検査だけを再実行しました。
詳細契約はpython/pkg-v12/SEMANTICS.md §29.3。ABI10を維持、性能は未測定。
初版5/12（42%）のまま。全公開APIの確定、配布/fullCI、時間/必要ピークの条件は未達。


## C参照の測定を長くして再確認（R521）

現行R520の本体で、固定CPU0・1,048,577レコード・256反復の既存R515測定方針を再実行。
AIL側は校正を通りましたが、C側はA/A 1.3479・観測負荷1.4311で比較不成立でした。
C参照だけ2048反復へ延ばす専用測定を追加。同じO2/ffp-contract=off、
2 warm＋12 measuredの固定順序、各反復の全文出力・hash/mtime保持を確認しました。
154.217sで完走し、6境界・2誤出力control・14引数guardは通過。
CのA/A 1.2176・観測負荷1.2170・変換工程A/A 1.2705で、既存1.10基準を満たしません。
AIL/C全体比較・物理上限・速度採用は未成立。反復時間の不足だけを原因と断定できません。

判定ロジックはLinux/Windows各distinct10件PASS、skip0。
Windows初回の一時フォルダ権限エラー1件は通常権限でその1件だけ再実行してPASS。
hostの反復上限guard/診断だけ拡張し、default32、Cの実処理、本体/runtime/ABI10を維持。
記録はlanguage_examples/binary_cursor_records_profile_linux_r521.jsonと
language_examples/binary_cursor_reference_calibration_linux_r521.json。前者のrevision:R515は測定方針の版です。
初版の固定12条件は5/12（42%）。未資格の速度見積りを採用根拠にしません。


## 整数引数のエラー契約とライブラリのリンクを修正（R520）

`checked_integer.ail` に `parse_int64_text(text:str)->int` を追加しました。
符号付きint64のASCII十進数を読み、前後の25種類の整数用空白を許可します。
空、符号のみ、内部の空白、underscore、非ASCII数字、範囲外は捕捉できるValueErrorです。
厳格な `parse_int64_decimal` とbytes版、checked additionの契約は維持しています。

`binary_search_main.ail` のstart/endと `numeric_scale_binary_main.ail` のbyteorderはこのAPIを使います。
範囲外を渡したときの終了1「integer overflow」を、既存の終了2・空stdout・CLIのエラー文へ揃えました。
読込み前に整数を検査し、不正な整数と存在しない入力が重なっても引数エラーを返します。

関連検査で、既存の整数集計objectとentryに同じmethodを二重定義する不具合を再現しました。
combined Cではmethodをstaticに保ち、分割C unitの出力だけ別unitからリンク可能にするよう修正。
通常/実際の分割/元ソースのない移動先でのobject再利用を検査しています。
Linuxは対象と関連のdistinct9件、Windows最終10件79.341s PASS、skip0。
25種空白、int64端点と範囲外、129桁、1MiB超検索、64MiB超数値変換を独立Pythonの全出力と照合。
入力と再利用objectのhash/mtimeを保持。runtime/ABI10は不変、速度改善は未測定です。
初版の固定12条件は5/12（42%）のまま。仕様/API全体の確定と配布/fullCIは未完了です。

## 固定幅レコード配列の型注釈（R519）

Python構文と `fn`/`let` 構文で、初期値付きのレコード配列を宣言できます。

```text
let numbers:list[tuple[int,int]]=[];
let points:list[tuple[float,float]]=[(1.25,2.5)];
let records:list[tuple[int,bytes]]=[(7,b"header")];
```

同じ幅・型配置のappend、再代入、localからのlistコピー、負の添字に対応。
整数はint64、floatはbinary64として扱い、暗黙の型混合を拒否します。
全fieldの評価が終わってから配列を更新するため、後ろのfieldが例外になっても部分的なrowを残しません。
localの整数/bytesレコードを同じ型注釈の関数引数へ渡せます。借用引数の転送も対応。
localはBPOOL、借用引数はslots/blob表現で、呼出し前に変換します。blobは呼出し元の関数終了まで保持します。

extend、未初期化、空tuple、可変幅、入れ子tuple、float/bytes混合、all-bytes、
借用した混在レコードからlocalへのコピーは拒否します。
新5件がLinux/WindowsでPASS。通常/分割、独立Python参照、全解放、移動後のsource-free再リンクを確認。
Windowsでは影響する既存6件もPASS。レビュー後の変更2件だけを再検査しました。
速度は未測定。初版の固定12条件は引き続き5/12（42%）で、仕様/API全体の確定は未完了です。

## floatレコード参照とメソッドの分割リンクを修正（R518）

appendで構築するfloatレコードの参照と、C unitに分けたclass methodのリンクを修正しました。
通常buildのmethod生成Cと、methodなしの分割生成Cは変更前と一致します。
Linuxで対象2件、Windowsで対象2件＋関連2件PASS。出力は独立Python参照と一致し、全解放も確認。
速度比較は行っていません。R518時点ではfloatのtuple-list literal、localの混在注釈は未対応でした。

## 整数とbytesのレコード配列を一度に構築（R517）

`append`で組み立てる形に加え、型を推論するlocalで次の書き方が使えます。

```python
rows = [(7, b"header"), (11, b"\x00\xff")]
rows = [(rows[-1][0], rows[0][1]), (13, b"tail")]
```

整数はint64のまま、bytesは既存のBPOOLで保持します。bytesのfieldが先頭・末尾・複数でも、
同じ幅と型配置のレコードを扱えます。fieldをソース順に一度ずつ評価し、右辺が完成してから
代入先を更新するため、途中で例外になった場合は元のrowsを保持します。
listコピー、負の添字、bytes fieldを関数へ渡す型推論も確認しました。

新規6件＋既存18件をWindows/Linux各24件PASS、skip0。独立Python参照と全出力が一致し、
正常/分割build、catch/早期return/unwindの全解放、int64両端/2^53超、幅/型拒否を確認。
R516で未実行だったlegacy BPOOLのown-tryもnativeで確認しました。
検証中に見つけた整数ROWS runtimeの2つのpointer member参照を修正。ABI10は不変です。

localの明示注釈 `list[tuple[int,bytes]]` はまだ未対応です。
BPOOLの内容は関数終了時に解放する既存方式で、再代入ごとの早期回収は実装していません。
今回は構文と正しさの対応で、速度/peak削減の測定・全corpus/fullCIは未実施です。

## 例外管理用セルの確保を一つへ統合（R516）

コンパイラ本体で、例外から戻った後も値を保持する管理用セルを、関数ごとに一つのheap frameへ
まとめました。scalarのvolatile、所有権、内容の解放、外部ABI10は保持しています。
heapの中身を使い、setjmp後に変わる値を自動変数のstructへ移していません。
frame pointerはsetjmp前に一度だけ代入。通常returnとunwindで内容を解放した後、frameを一度解放します。

R512の集計アプリを変更せず、元のcompiler/source/生成Cの一致を確認して比較しました。
7入力サイズ×3回の全21出力が独立Python参照と一致し、欠けた末尾7件も出力なしで拒否。
全入力・失敗で管理用セルの確保21回を除去し、正常時の確保回数39→18回を実測しました。

| 10万レコードの全仕事 | 変更前 | 変更後 |
|---|---:|---:|
| 確保回数 | 39 | 18 |
| 累積確保要求bytes | 2601850 | 2601850 |
| copy要求bytes | 1300206 | 1300206 |
| 計測heap peak bytes | 2601641 | 2601641 |

確保回数の削減として採用します。payload量・peak・copy削減や速度向上を示した結果ではありません。
管理セル22個→一つでも、同じ型の内容とゼロ初期化量を保持しています。
scalarだけのtry、tryなしのcontainerなど3生成形は変更前と同じCです。

新しい4件を含む14件をWindows/LinuxでPASS、skip0。
例外後の再代入・tuple dictの追加列・早期return・再帰・別object分割・全解放・OOM、
ユーザー関数名との衝突、元ソースなしの再リンクを確認しました。
複数poolを同時に使う例でsarena/barena/pool/dpoolを実行。
legacy bpoolは同じcell生成へ接続していますが、今回のnative例では未実行です。

最初のOOM検査はruntimeがatexitを実行せず観測に失敗し、失敗calloc内の観測へ修正。
管理pointer名との衝突も通常/分割buildで再現して修正し、前のresource記録は保持しています。
R516最終記録はbinary_cursor_integer_resources_r516_after_corrected.json。
既存測定器のR512形式を保持し、compiler SHAと生成C SHAで変更後を識別します。
driver費用は記録のelapsed_ns、build費用はbuild_ns。どちらも実行速度比較やAI総token費ではありません。

R515のrusageは検証・setupを含むprocess全体で、work内のCPU時間との差から待ちを確定できません。
未校正のC投影から速度候補を作らず、今回は独立確認できる確保回数を削減しました。
fullCI/全corpus/arm64/32bit/物理roof/速度改善/全用途最速/AI最高効率は未達です。

## ゲストCPUを固定した整数処理測定（R515）

新しく起動する測定driverと子processだけを、既存tasksetでゲストCPU0へ固定しました。
Pythonは許可maskを読むだけで変更せず、nativeも開始/終了CPUと単一maskを検査します。
Windowsホストの物理CPU配置・周波数・他の負荷は固定していません。

```text
taskset -c 0 python3 -B language_examples/binary_cursor_records_profile.py --passes 256 --cpu 0 --record language_examples/未登録の新規記録.json
```

--cpu指定は256回/R515だけを受理します。CPUはexact int0..1023で、nativeの欠落・重複・
余分なfield、不一致CPU、boolを整数にした値、不正flagを拒否。従来の32/R513と256/R514は保持。
Windows/Linux各7件PASS、skip0。全6656全文＋24境界一致、末尾誤り4と引数/欠け末尾76を拒否。
全正常processでCPU開始/終了0、単一mask確認。元/計測生成CはR514と同じSHAです。

| 校正の最大比（基準≤1.10） | AIL | C |
|---|---:|---:|
| 同じ実装同士のA/A | 1.096580 | 1.568972 |
| 通常版と計測版の差 | 1.134751 | 1.337291 |
| 校正 | 未資格 | 未資格 |

CPU固定だけでは校正は改善しませんでした。因果をCPU移動と確定せず、失敗を保全します。
診断plain256回中央値AIL14.564376s/C0.893655s、pair比16.329903（IQR15.893530〜16.823164）。
保存＋集計share0.966360/Amdahl29.726101、C到達比0.035125/仮定1.0投影14.796423は
診断用です。高速化候補を作る理由や速度採用に使いません。
driver204.206s、4build合計1.955774s。AI token費は含まず、速度改善/物理roofは未実証です。

記録binary_cursor_records_profile_r515.jsonとR513/R514を保持。本体・library・runtime・ABI10、
R512の資源削減は保持しています。次は同じ実装内のCPU時間と壁時間を照合し、
計測器の追加処理とホスト側の待ちを分けて調べます。


## 反復時間を伸ばして整数処理を測定（R514）

R513のC側の仕事時間が約0.13秒だったため、入力1048577レコードは変えず、
反復を32→256回/processへ固定して測定しました。新規記録を作り、R513の失敗記録は保持しています。
26processの交互順序、A/A・計測版の差の基準1.10、IQRと両順序の判定は変更していません。
元のAIL生成Cと計測CはR513と同じSHAです。本体・library・runtime・ABI10は不変です。

```text
python3 -B language_examples/binary_cursor_records_profile.py --passes 256 --record language_examples/未登録の新規記録.json
```

既定の--passes 32はR513形式、256はR514形式です。未対応の回数/revisionを拒否します。
hostの上限は既定32、明示した実験では256。0/符号/先頭0/桁あふれ/上限超過を拒否します。
新検査を含む5件がWindows/LinuxでPASS、skip0。
native4binaryで全6656回＋24境界が独立Python参照へ一致し、末尾誤り4件、
引数28件・欠けた末尾48件を拒否。入力・参照・binary・source pinを保持しました。

| 校正の最大比（基準≤1.10） | AIL | C |
|---|---:|---:|
| 同じ実装同士のA/A | 1.084724 | 1.166412 |
| 通常版と計測版の差 | 1.094164 | 1.205768 |
| 校正 | 適格 | 未資格 |

AILの保存＋集計の壁時間割合0.961306、無限工程Amdahl上限25.844007を取得。
ただしC側は未資格なので、C比較とC能力を使った投影は診断用です。
通常版256回の仕事時間中央値AIL14.938777s、C1.057445s、
pair AIL/C14.718977（IQR14.364012〜15.100160）。
C工程能力への到達比0.039148、仮定比1.0の全体投影13.101583も、
高速化候補の着手理由や速度優位の認定には使いません。

AILの工程中央値はread539.562ms、field442.174ms、集計13678.463ms、write12.607ms。
全体の残差には他のsetup/整形/free/flush等を保持。各中央値の和は全体中央値ではありません。
child process peak RSS中央値は両方88600KiBで、独立したcandidate必要メモリの差を示していません。
driver216.896s、4build合計2.326s。AI総token費用は含みません。

記録binary_cursor_records_profile_r514.jsonを保全。今回の延長理由は短いC仕事時間であり、
校正成功を待つ反復や基準緩和は行っていません。物理roof・最善C・速度改善は未証明です。
読取確認時のWSLはRyzen7 8840U、許可CPU0..15、既存tasksetあり。
実測中のCPU移動はまだ記録していません。
次はこの測定専用processのCPU配置を固定し、条件を記録して比較します。

## レコード集計の全仕事と工程を比較（R513）

language_examples/binary_cursor_records_profile.pyで、R512の元CLIと独立したC実装を測定します。
通常版と計測版を別々に作り、読込み、構造体への保存、集計ループ全体、出力を測ります。
整数ごとの時計は挿入しません。通常版には工程の時計を加えていません。
Cは入力を一度保持して同じ5列を集計し、内部の不要な構造体コピーは作りません。
残差には他の初期化、AILの文字列整形、解放、flushなどを残します。

Linux、C11 -O2 -ffp-contract=off、1048577レコード（13631501bytes）、
32回/process、固定26process（暖機2＋測定24）で、全832回の全文を独立Python参照へ照合。
0/1/2/5041/5042/80661レコードの24境界出力、末尾誤り4拒否、
引数28拒否と欠けた末尾48拒否も確認し、入力と参照のSHA/mtimeを保持しました。
判定器4件はWindows/LinuxでPASS、skip0。Linuxで4binaryのnative実行を確認しました。

| 校正の最大比（基準≤1.10） | AIL | C |
|---|---:|---:|
| 同じ実装同士のA/A | 1.151520 | 1.324828 |
| 通常版と計測版の差 | 1.174725 | 1.364200 |

両方とも未資格です。次の値は診断用で、速度優位の認定や高速化候補の着手理由には使えません。

- 通常版32回の仕事時間中央値: AIL1.795400s、C0.129828s。
- 対になったAIL/C中央値13.745589、IQR13.444666〜13.946613。両順序で同じ向きですが校正失敗。
- 保存＋集計の壁時間割合0.957043、無限工程Amdahl上限23.279200。
- 実測C工程能力への到達比0.038300、仮定比1.0なら全体12.560986倍という条件付き投影。
- 工程中央値はAIL読込み67.051ms、保存78.302ms、集計1590.667ms、出力1.575ms。
  個々の中央値の和は全体中央値ではありません。
- child process peak RSS中央値は両方88464KiB。単独の処理データ量や物理メモリ上限を示す値ではありません。

生の失敗記録binary_cursor_records_profile_r513.jsonを保全し、
校正成功を待つ再試行・基準緩和はしていません。機械上限、最善C、速度改善は未証明です。
driver31.963s、4build合計2.372s。AI総token費用は含みません。
実行はLinuxでbinary_cursor_records_profile.py --record 未登録の新規パスを使います。
元のbinary_cursor_integer_profile.pyとR512本体・資源記録は保持しています。
次は測定時間とばらつきの原因を確認し、有効な時間価格を得てから集計の実装候補を選びます。

## 整数読込みの一時bytesを除去（R512）

BinaryCursorのread_u8/read_u16_le/read_u16_be/read_u32_le/read_u32_beは、
remaining()で位置と幅を検査してからdataの各byteを直接読みます。
値の計算が完了した後だけpositionを進め、失敗時の位置を保持します。
take/peek/seek/skip/reset、owned bytesの契約とcompiler/runtime/ABI10は変更していません。
既存のlibrary objectは再ビルドしてください。

新しいlanguage_examples/binary_cursor_records_main.ailは13bytesの固定レコードを集計します。
順序はu8、u16 little、u16 big、u32 little、u32 bigです。
出力はレコード数、5列の合計、最終位置を空白で区切った1行です。
長さが13の倍数でない入力はstdoutへ結果を書く前に拒否します。
レコード数を2^31以下に制限し、最大uint32の合計もsigned64に収めます。
既存のAILR抽出用binary_records_main.ailは保持しています。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_cursor_records_main.ail -o records.exe
.\records.exe input.bin
```

| 10万レコード・50万回の整数読込みを含む全仕事 | R511 | R512 |
|---|---:|---:|
| 成功した確保要求回数 | 1500039 | 39 |
| 累積確保要求bytes | 67901850 | 2601850 |
| 明示的copy要求回数 | 500017 | 17 |
| 明示的copy要求bytes | 2600206 | 1300206 |
| 計測ヒープのピーク要求bytes | 2601641 | 2601641 |

Linuxで0/1/2/5041/5042/65537/100000レコードを各3回、前後全42出力を
独立Python int.from_bytes参照へ照合。入力SHA/mtimeと全解放を確認し、計数も反復一致しました。
1レコードあたり確保15回・653bytes、copy5回・13bytesを除去。空入力の全counterは不変です。
前後14件の不正末尾も出力前に拒否し、解放を確認しました。
明示的要求の計数で、allocator header/libc内部/物理転送/stack/RSS/実行時間を含みません。
速度向上・C優位・機械上限への到達は未測定です。工程割合/Amdahl/参照到達比の時間価格は未取得で、
今回は時間の投影を根拠にせず、測定した資源削減として採用しました。

Windows/Linux各7件PASS、skip0。非周期1MiB超、全uint32値域の端点、
signed64の位置・件数端点、12種類の欠けた末尾、繰返し失敗と修復、receiverの一度の評価、
保持したbytesとfield再代入、通常/分離ビルド、元ソースなしの移動objectの2再リンクを確認。
資源取得費はbefore2.265s、after2.921s（after build0.829sを含む）。比較実行時間ではありません。
記録はbinary_cursor_integer_resources_before_r512.jsonとbinary_cursor_integer_resources_after_r512.json。
再実行はLinuxでbinary_cursor_integer_resources.py --record 未登録の新規パス --stage afterを使います。
次はこのレコード処理の全仕事を最適化C参照と比較し、有効な工程測定から次の候補を選びます。

## 隣接範囲の再結合を一つの出力へ融合（R511）

binary_cursor_rejoin(data, first, second)は、入力の[0,first)と[first,first+second)を結合します。
隣接する二範囲の結果は入力の先頭first+second bytesです。
firstを0..len(data)、次にsecondを0..len(data)-firstで検査してから合計を計算します。
合計0なら空bytes、それ以外は先頭範囲の独立したowned snapshotを一度作って返します。
内部のclass作成、field全保存、take中間値、join走査を除きました。
一般のBinaryCursor methodとslice、compiler/runtime/ABI10は従来どおりです。library objectは再buildしてください。

| 64MiB+8bytesの元アプリ再結合 | R509/R510 | R511 |
|---|---:|---:|
| 計測ヒープのピーク要求bytes | 268436524 | 134218676 |
| 成功した確保要求bytes合計 | 268436853 | 134218877 |
| 明示的copy要求bytes合計 | 201326616 | 67108872 |

元アプリの前後各72出力を同じ独立Python参照と照合し、入力保持・全解放を確認。
正の再結合21組で入力サイズ2倍のcopy要求を除き、全24組で確保要求・ピーク要求が減少。
空入力はピーク66584→66413、確保66851→66614bytes。slice48組の全counterは不変です。
資源記録はbytes_return_resources_after_r509_final.jsonとbytes_return_resources_after_r511.jsonです。

新規3件と既存cursor4件で、非周期1MiB超、NUL/全256値、小さい全split、
signed64端点、負の引数/超過のValueError、例外後の再試行、parameter view、再代入/churn後の
owned結果保持、通常/分離compile、source-free移動objectの2再リンクをWindows/Linuxで確認。
比較判定2件も両環境で成功。計測した範囲の資源改善として採用しました。
不正な外部C spanや、資源不足時の全ての例外発生順序を同値証明したとは扱いません。

着手理由はR510で有効だった工程割合0.449403、Amdahl上限1.816211、
実測済みC transform能力に対する到達比0.296000、仮定比1.0の全体見積り1.462800です。
この見積りは実装変更後の速度の証明ではありません。

旧生成CはR510のSHAと完全一致させ、候補・一回コピーC参照と固定39processで比較しました。
各32pass、63境界＋1248passの全文一致、末尾byte誤り3件の拒否を確認。
A/A最大は旧1.444、候補1.139、C1.160で固定1.10基準を超え、時間比較はunqualifiedです。
診断pair中央値は旧/候補1.610、C/候補0.983ですが、速度向上やC優位を確定しません。
候補のpeak RSS中央値132716KiB、旧263788KiB、C132712KiBは検査を含むchild process値です。
物理メモリ転送量・機械上限・最善C・全用途最速は未証明です。
記録bytes_rejoin_compare_r511.jsonを保全し、成功待ちの再測定・基準緩和は行っていません。
測定driver費用は資源9.554s、比較363.664s。AI総token費用は含みません。

次は残る走査・所有期間・読込みと出力を、他のbinary library処理でも確認します。

## バイナリ再結合の工程時間（R510）

R509の本体と元のcursor/applicationを固定し、64MiB+8bytesを各processで32回処理しました。
通常版とhelper計測版は別binary。独立Python file-range参照との全文比較を毎回行い、
比較時間をworkから除きました。workにはopen/reopen、読込み、計算、書込み、flush、解放を含めます。
物理ディスクへの永続化（fsync）は含みません。入力・oracle・binary・sourceのhashを保持しています。

| 用途 | AIL A/A最大 / observer最大 | C A/A最大 / observer最大 | 判定 |
|---|---:|---:|---|
| 全文slice | 1.213 / 1.119 | 1.092 / 1.097 | 校正失敗、速度保留 |
| 内部slice | 1.094 / 1.125 | 1.234 / 1.235 | 校正失敗、速度保留 |
| 再結合 | 1.090 / 1.050 | 1.064 / 1.093 | 固定1.10基準を通過 |

再結合の通常版32回のwork中央値はAIL9.532s、C6.099s。
6つのprocess pairのAIL/C時間比中央値1.520、IQR1.510〜1.587。
実行順の両方向でもCが速く、この入力・機械・実装ではCの優位を確認しました。
AILが速くなった結果ではありません。C参照は入力と独立した所有出力をmallocし、
二つの隣接範囲をコピーする実装です。最善のCや物理上限を示しません。

計測版でfield保存＋take＋joinは全体の44.940%。
この工程だけを無限に速めたAmdahl上限1.816倍、同じ工程の実測C能力に対するAILの到達比0.296。
到達比1.0を仮定した全体の条件付き見積り1.463倍です。採用前に新しい全仕事で再測定します。
helperの外にあるCLI/constructor/所有登録/外側の解放/flush等は残差に含め、
重なるhelper呼出しは計測器が拒否します。

全84境界実行と78 processの全2496 passで全文一致。最終byte誤り4件を拒否、
不正syntax引数36件で出力sentinelを保持。判定器4件はWindows/Linuxとも成功。
peak RSS中央値は再結合AIL263788KiB、C132712KiBですが、全文検査も含むprocessの値です。
記録はlanguage_examples/bytes_return_profile_r510.json、測定総費用626.482s、
4binaryのbuild合計2.325s。AIの総token費はこの記録に含みません。
32回は同一process内で相関し、6pairのIQRは信頼区間ではありません。
失敗したsliceの記録を保全し、成功するまでの再測定や基準緩和は行っていません。

次は純粋な再結合library処理の検査・切出し・joinを一つの走査へまとめる候補を選び、
一般のBinaryCursor methodの契約を保ったまま、全文・境界・資源・時間を比較します。
R510自体は計測機能の追加で、compiler/runtime/ABI10の変更と速度改善の採用はありません。

## join直前の中間bytesリストを省く（R509）

bytes.joinへ直接渡す、16要素以下で呼出し・代入を含まないリスト式を扱います。
separatorを従来どおり保存し、各要素を左から右へ一度ずつ評価して、一時的なspan配列を作ります。
既存joinが同期的に結果をコピーするまで各spanが生きることを確認しています。
一時array/headerは所有権登録・解放・返却をしません。17要素以上、共有/名前のリスト、
呼出しやwalrusを含む要素は従来の所有リストです。field読込みのsnapshotと例外解放も保持します。
各spanの検証も要素ごとに行い、不正spanを後続の算術例外より先に拒否します。
runtime/ABI10を変更せず、新しいコンパイラでobjectを再buildしてください。

元のbinary_cursor_main.ailとlibraryで前後各72回、全144全文が独立Python file-range参照と一致。
入力SHA/mtimeと全解放を保持。全文/内部sliceの全counterは不変です。
正のrejoin21pairで結果サイズのcopy要求を一つ除去し、24pairで中間listのheap確保を除きました。

| 64MiB+8bytesの再結合 | R508 | R509 |
|---|---:|---:|
| 計測対象ヒープのピーク要求bytes | 335545556 | 268436524 |
| 成功した確保要求bytes合計 | 335545885 | 268436853 |
| realloc要求bytes合計 | 128 | 0 |
| 明示的なcopy要求bytes合計 | 268435488 | 201326616 |

空入力の再結合もheap確保要求67011→66851bytes、ピーク66680→66584bytes。
一時array/headerのstack使用量はこのheap counterに含まれず、実際のstack量とRSSは未計測です。
最終候補はWindows/Linux各9種類で確認しました。新しい4件で0/1/2/16/17要素、
view/field/条件式、empty/NUL/nonUTF8/全256値/1MiB超、separatorと要素の評価順序、
途中例外/不正spanの拒否順序/全解放/source-free再リンクを確認。既存cursor3件と幅・確保失敗2件も通過。
初期候補では他の関連検査も通しましたが、不正spanの検証順序が不足しており、そのまま採用していません。

物理転送量・実行時間短縮・Cへの優位を示す結果ではありません。
記録はlanguage_examples/bytes_return_resources_before_r509.jsonとafter_r509_final.jsonです。

## 呼出し連鎖でもowned bytesを引き渡す（R508）

内部で生成するchecked bytes関数・メソッドの正常な非空戻り値は、独立した長さどおりの確保です。
この呼出し結果を直接返すか、一度だけ代入したローカル値を返す場合にも、既存の転送を適用します。
再帰・早期return・例外からのreturnも同じ返却処理を通します。空の暗黙returnは空値です。
外部objectのowned flagには容量の保証がないため、直接の外部呼出しはコピー経路を保ちます。
内部関数が外部結果をコピーして返した後は、その内部関数の契約を使えます。
部分ビュー・再代入・借用・数値融合が置換したローカル値は従来のコピーです。
runtime/ABI10はR507のままです。objectは新しいコンパイラで再buildしてください。

元のbinary_cursor_main.ailとlibraryを変更せず、前後各72回の全144全文が独立Python参照と一致。
入力SHA/mtimeと全解放を保持し、正のslice39pairで結果サイズの確保/copy要求を一つずつ除きました。
rejoinと空結果のcounterは全不変です。

| 64MiB+8bytesの全文slice | R507 | R508 |
|---|---:|---:|
| 計測payloadのピーク確保bytes | 268436494 | 201327622 |
| 成功した確保要求bytes合計 | 268436759 | 201327887 |
| 明示的なcopy要求bytes合計 | 201326616 | 134217744 |

内部sliceではピーク268436490→201327620bytes。再結合のピーク335545556bytesは不変。
数値融合で読込み容量を再利用したcalleeは返却時にexact-sizeへコピーし、その後のwrapperだけ転送。
全出力を0/1/8193/131073個のbinary64で確認し、通常のbytes連鎖・再帰・引数順序・保持・解放・
source-free移動libraryと外部C bytes結果を含め、Windows/Linux各19種類を検査しました。
既存のfield選択検査は、呼出しwrapperの転送と対象methodを区別するよう修正しています。

payload要求の計測であり、RSS・物理転送量・速度向上・Cへの優位を示しません。
記録はlanguage_examples/bytes_return_resources_before_r508.jsonとafter_r508.jsonです。

## classのslice戻り値で重複コピーを省く（R507）

classフィールドの長さと単純な添字は、既に全コピーを省いていました。
今回の対象は、フィールドのsliceが作った独立したbytesを返すときの二重目のコピーです。
名前で指定したreceiverのbytesフィールドを、呼出しを含まない境界でsliceする式、
またはその結果を一度だけ代入したローカル値を、既存の所有権転送へ接続しました。
フィールド全体、部分ビューの再slice、再代入、関数を含む境界・receiver、未知の呼出しはコピー経路です。
ABI10とランタイムはR506から変更していません。objectは新しいコンパイラで再buildしてください。

元のbinary_cursor_main.ailとlibraryで、前後各72回・全144全文を独立Python file-range参照と照合。
入力SHA/mtimeと全解放を保持し、正の60pairで結果サイズの確保要求とcopy要求を一つずつ除きました。
64MiB+8bytesの全文sliceでは、確保要求335545631→268436759bytes、
copy要求268435488→201326616bytes。ピーク確保268436494bytesは変わりません。
再結合も確保要求402654757→335545885bytes、copy要求335544360→268435488bytesへ減りましたが、
ピーク335545556bytesは変わりません。空結果のcounterは不変です。

Windows/Linux各9種類を確認しました。直接/ローカルsliceの選択、借用・呼出し境界の保守経路、
INT64端を含む8境界、空/NUL/nonUTF8/全256値/1MiB超の全文、field更新/receiver差替え後の保持、
副作用の順序・遅延分岐・例外・全解放、source-free移動libraryの2再リンクを含みます。
既存cursorとfield subscriptの実用検査も確認しました。

計測はpayload要求量であり、RSS・物理転送量・実行時間短縮・Cへの優位を示しません。
記録はlanguage_examples/bytes_return_resources_before_r507.jsonとafter_r507.jsonです。

## 再利用ライブラリの戻り値コピーを減らす（R506）

本体コンパイラとランタイムが、出力長と確保長が一致する私有bytesを、
戻り値として引き渡せるようになりました。戻り値の公開APIとABI10は変えていません。

対象はbytes構築・fromhex・join・replace・translate・removeprefix/removesuffix・反復・float64_encode。
直接返す式、または一度だけ代入したローカル値を確認し、ランタイムが現在のarenaに一つだけある
同じ先頭ポインタを検査して登録を外します。残るbufferは従来どおり解放し、呼出し側が戻り値を所有します。
借用値、部分ビュー、再代入、classフィールド、未知の呼出し、read_bytes、UTF-8 encode、連結はコピー経路。
数値融合が元のencodeを置き換えたローカル値も転送しません。空のbytes()にarenaを新設しません。

既存binary_cursor_main.ailと元libraryをそのまま使い、各72回の前後資源計測を実施。
0/1/65535/65536/65537/1MiB+1/8MiB+1/64MiB+8bytes、全文slice・内部slice・rejoinを各3回。
全144全文が独立したPython file-range期待値と一致し、入力SHA/mtimeと全解放を保持しました。
sliceと空入力は全counterが不変。正のrejoin21pairは戻り値サイズの確保/コピーを一つずつ除去。

| 64MiB+8bytesの再結合 | R505 | R506 |
|---|---:|---:|
| 計測payloadのピーク確保bytes | 402654428 | 335545556 |
| 成功した確保要求bytes合計 | 469763629 | 402654757 |
| 明示的なcopy要求bytes合計 | 402653232 | 335544360 |

Windows/Linux各24種類の検査で確認しました。既存カーソル・base64・C bytes戻り値・置換/変換20件、
新しい選択条件・全文/例外/解放・幅/重複/確保失敗・source-free移動library4件。
classへ保存後のフィールド更新、後続呼出し、部分ビューも含みます。Cのcaller-buffer ABIとguard保持も確認。
最初の確保失敗shimはmallocだけを捕まえて失敗し、実際のcalloc経路を合わせて該当検査を通しました。
生成コード検査のWindows一時ディレクトリ片付けもsandboxでは拒否され、通常の許可環境で通しました。

計測後の空constructor選択条件修正とコメント更新は、現compilerが同じ測定済みアプリのCを生成することを
SHAで確認しています。計測recordの当時のsource pinsは書き換えていません。
payload要求の削減を示す結果です。RSS・物理traffic・実行速度・最適化Cに対する優位は未実証。
残るclassフィールドの全コピーと所有期間を調べ、速度へ進む前に全仕事の工程割合/上限/比較達成比を測ります。

## 共通読込みを実用プログラムで確認する（R505）

共通ランタイムの `read_bytes(path)` が、同じopen descriptorの通常ファイルの正のサイズを
初期容量の目安に使います。別のpathをstatし直さず、実際の読込みが返すbyte数を優先します。
サイズ不明/非通常file/0/負値/幅超過は従来の65536開始、目安による確保失敗も従来容量へ戻します。
満杯時はEOFを確認してから拡張し、伸びた入力の最初のbyteも保持します。短くなった入力も読めます。
snapshot/atomic readや新しい公開APIを追加したわけではありません。

以下をWindows/Linuxの両方で最後まで実行しました。

- CSV→JSON: 通常source・分離compile・移動したsource-free依存library。Unicode/引用符/改行と長い全文をPython csv/jsonで照合。
- JSON抽出: 通常/分離compile、1MiB超入力、長い文字列/数値・8191/8192/8193nodes、末尾不正も拒否。
  Python独立codecと出力照合、失敗前の入力/既存出力とaliasを保持。
- バイナリ検索: 5種類の操作、1MiB超・65536境界、通常/分離/object再利用をPython bytesで照合。
- C/AIL再利用object: 移動した部品で4MiB超のbyte checksum、binary/NUL/CRLF/不正UTF-8とエラーを確認。

各platform13件（容量3＋stdin/proof3＋実用7）が成功、skip0。
同じhandleのsize hintと実データが違うケース、cap1の拡張、読込み/EOF probe/close/確保失敗を確認しました。
`read_stdin_bytes`の消費条件も、既存の一つのint size引数に修正。0引数は未対応のまま拒否します。

同じ数値処理の各72回の前後計測は全144出力が独立期待値と一致し、入力SHA/mtimeと全解放を保持。
前はR504採用後のraw counterと全72一致。独立C、空入力、explicit copy/zero要求は前後不変です。
全正の通常入力でrealloc要求がなくなり、ピーク確保量と確保要求合計が減りました。

| 約64MiB＋8bytes入力のAIL | R504 | R505 |
|---|---:|---:|
| 計測対象payloadのピーク確保bytes | 134218370 | 67109514 |
| 成功した確保要求bytes合計（realloc含む） | 268370747 | 67109699 |
| realloc要求回数 | 11 | 0 |
| explicit copy要求bytes | 134217744 | 134217744 |

これは要求counterで、RSS・物理転送量・時間短縮の証明ではありません。時間比較は実施していません。
計測後のstdin arity修正でも、数値処理の生成C SHAは計測時と完全一致することを再確認しました。
実際の並行file変更は未検証で、size hint差の決定的なモデルを使用しています。

最初のWindows用raw検査はstdoutのtext変換で誤った差分を作り、整形が長時間続きました。
binary出力と短い失敗表示へ修正した検査は成功。旧検査の停止は自動承認レビューで拒否され、
ユーザーの明示許可後にそのPIDだけ停止しました。失敗/停止の費用も成功と分けて保持します。

次は再利用library境界のcopyと保持量を実測し、実用アプリ全体の十分に最適化したCとの比較を進めます。
工程割合/Amdahl/到達済み比較能力は同じ全仕事の有効な測定を使い、旧の未校正値を転用しません。

## 処理全体から実行方式を決める（R504）

[現行設計](docs/FASTEST_GENERAL_PLAN_20260914.md)に、必要な計算・転送・依存関係から
所有権、走査統合、SIMD、thread数、入出力まで選ぶ開発順序をまとめました。
数値処理に続き、文字列/バイナリ処理、検索/集計でもこの設計を確認します。
旧測定を現在の機械上限に転用せず、全仕事への効果で優先順位を決めます。

本体の基礎として、builtin読込み直後の私有bytesを、最後の使用を確認できた場合だけ
融合変換の出力bufferへ再利用します。借用入力・alias・後の観測は従来の独立出力経路です。
入力ファイルは保持し、算術順序/endian/例外/ABIを保ちます。新しい公開APIは不要です。

同じ元source/importsで消費を無効/有効にした各72回の資源計測を実施しました。
全144出力が独立した有限Python期待値と一致し、入力SHA/mtimeと全解放を確認しました。
無効側の全counterはR501採用後と完全一致。独立Cとexplicit copy要求は前後で不変です。

| 約64MiB＋8bytes入力のAIL | 消費無効 | 消費有効 |
|---|---:|---:|
| 計測対象payloadのピーク確保bytes | 201327242 | 134218370 |
| 成功した確保要求bytes合計（realloc含む） | 335479619 | 268370747 |
| calloc zero要求bytes | 67109414 | 542 |
| explicit copy要求bytes | 134217744 | 134217744 |

正の全入力で出力payload一つ（入力byte数と同量）の確保/zero要求がなくなりました。
arenaの登録は増えず、同じ所有bufferを使います。これは要求counterで、RSS/物理転送量ではありません。
readerの容量倍増は残り、必要な入力byte数の約2倍を確保する条件があります。
次の資源対象は読込み容量と所有期間。速度対象は同契約の全仕事を有効に測ってから選びます。

Windows/Linux各13件（既存12＋追加loop1）が成功。borrowed/alias/refusal、4endian組合せとoperand順、
unaligned/guard/empty/不正arena/重複所有、40回の全文出力と例外後の全解放、source-free libraryの再利用を確認。
最初のloop検査に置いた根拠のない1MiBピーク上限は失敗し、必要な全文出力/例外/解放条件へ修正しました。
loop全体の有界メモリを証明したとは扱いません。性能再試行なし、速度/物理限界/全用途最速は未実証です。

## 入力保持・独立出力の条件で機械の到達性能を測る（R503）

機械の能力を使う方式を決めるため、必要な仕事量・所有権・確保・転送・並列化を分けて測りました。
今回は現行F64PIPE helperと独立Cの両方で、入力を保持し、別の出力へbinary64を0.5倍にします。
R502のC参照は私有入力のin-place更新でした。その契約差をCの命令生成の差と混同しません。
copy条件は同じ入力の全文コピーで、scaleとは事前に別の期待値にしています。

[測定器](language_examples/numeric_hardware_profile.py)と[Linux host](language_examples/numeric_hardware_host.c)は、
fresh出力の確保・kernel・解放、resident出力、永続workerの1/2/4/8/16threadを分けます。
入力・期待値・入力snapshotの読込み、resident出力への初回書込みとworker準備はsetup、全解放はteardownです。
workは確保＋kernelと、全文照合後の解放の2区間の和です。kernelのdispatch同期は含みます。
worker作成APIはsetup、最初のdispatchにはworkerの起動待ちが残る場合があります。
AIL内のarena/payload確保は、生成した計測用コードだけのhookで分離します。本体runtimeは変更していません。
fresh kernelには初回書込みのpage fault等も含まれ、算術命令だけの時間ではありません。
callocを使うAILとmallocを使うCの要求も異なります。residentは同じbufferを保持し、その交換条件を隠しません。

固定13warm＋156測定process、各32回、計5408回の長い全文出力と入力snapshotが一致しました。
182境界、末尾誤答13件、引数拒否15件、成功済みworker0/1/3件で起動に失敗したときのjoin、
0/1/7/8/9/257要素・unaligned buffer・guardを保つ2328dispatchも確認しています。
親は追加で不正な組合せ・長さ不一致・byte端数・最大幅超過24件を検査しました。
Windows/Linux各5種類の固定順序・幅・校正1.10境界・順序逆転・resident選択を確認しました。

[最初の実測記録](language_examples/numeric_hardware_profile_r503.json)、64MiB+8bytes・有限値/gradual underflowを含む入力:

| 32回の条件 | plain work中央値 | profile kernel中央値 | 論理read＋write GB/s |
| --- | ---: | ---: | ---: |
| 現行AIL、fresh、通常O2 | 2.805349秒 | 2.505338秒 | 1.714 |
| 独立C、fresh、通常O2 | 2.133536秒 | 1.829455秒 | 2.348 |
| 独立C、fresh、O3/native | 1.847521秒 | 1.467935秒 | 2.926 |
| 独立C、resident、1thread | 0.208584秒 | 0.213775秒 | 20.091 |
| 同2thread | 0.176067秒 | 0.175875秒 | 24.421 |
| 同4thread | 0.166538秒 | 0.171670秒 | 25.019 |
| 同8thread | 0.176675秒 | 0.177099秒 | 24.252 |
| 同16thread | 0.183124秒 | 0.189846秒 | 22.623 |
| copy resident、1thread | 0.168825秒 | 0.179556秒 | 23.920 |
| 同2thread | 0.127231秒 | 0.135335秒 | 31.736 |
| 同4thread | 0.109521秒 | 0.112469秒 | 38.188 |
| 同8thread | 0.179120秒 | 0.180116秒 | 23.846 |
| 同16thread | 0.184274秒 | 0.188574秒 | 22.776 |

GB/sは16×要素数×32/kernel時間という論理量です。物理DRAM転送量、物理roof、理論上限ではありません。
profileとplainは別標本です。各6組のplain比には入力保持/fresh条件とresident条件の違いも含まれます。
residentはO3/native、同一機械専用。fastmathは使わず、全buildでffp-contract=offにしています。
親の再ビルドは3つの生成物/実行物のSHAと一致し、nativeにvmulpd、通常版にmulsdを確認しました。
これはSIMD命令の存在の証拠で、SIMD単独の速度差の証明ではありません。

**全13条件でA/Aまたはobserverの上限1.10を超え、速度資格は不成立です。**
最速thread/referenceは未選択、速度採用なし。成功狙い再実行や基準緩和はしていません。
最初のbuildはruntimeをhostより先に置く際のstdio/stdlib等header不足で停止し、
native測定前に生成器のheaderを修正しました。測定は上の一回だけです。
pure test初回のcycle1順序期待値も実際の固定scheduleへ修正しました。

診断価格: AIL helper workのkernel割合0.889690、無限kernelを仮定したAmdahl上限9.06535、
同じfresh/通常O2のC kernel達成率に対する比0.730223、仮定比1.0で全体投影1.31582。
校正失敗のため実装理由には使いません。このworkにはfile IOがなく、R502全仕事の上限1.46424とは範囲が違います。
snapshot/期待値/照合はcacheを温め、CPU/RSSはそれらとworkerを含みます。物理roofは未資格です。

次の本体対象は、全使用と所有権を確認できる私有bufferの消費です。
入力保持が外から観測できる借用/aliasを維持し、読込みが作った独立bufferの最後の使用で、
重複した出力確保を除けるかを調べます。独立出力一致と確保/copy要求の削減でまず資格を取ります。
時間資格が成立する前に、診断投影を理由にSIMD/最大threadを本体へ入れません。
R501の融合・資源削減と旧失敗記録は保持しています。測定総費用220.349秒、
build AIL0.854464秒/default C0.371215秒/native C0.382839秒です。AI実モデル比較費ではありません。

再現（Linux、新record名が必要）:

```sh
python3 -B language_examples/numeric_hardware_profile.py --record language_examples/new_hardware_profile.json
```


## 必要な仕事量から機械の限界を探る（R502）

実行方式は、必要な計算と転送→所有権と寿命→一括確保と走査統合→SIMDと並列化の順で選びます。
R501で中間配列をなくした後、資源counterを外して、同じ元ソースの配列経路・融合経路・独立Cを測りました。
Cは入力ファイルを私有bufferへ読み、そこで更新します。AILの融合helperは借用入力を保持し、独立出力を作ります。
この実装・確保・所有権の違いを、CPU命令や物理帯域の違いと混同しません。

[固定手順](language_examples/numeric_pipeline_fusion_profile.py)は3warm＋36測定process、各32回の全仕事、
3programを各roundで交互に並べ、cycleで順番を回転、plain/profileはABBA/BAABです。
速度比較は同cycle・同roundのplain同士6組。工程clockを止めたplainにも選択branchは残ります。
各回の全出力を独立有限Python算術と照合し、検査時間はworkから除きます。
資源counterはありません。全1248回の長い仕事、42境界、誤った末尾3件、引数拒否12件を確認しました。

[最初の実測記録](language_examples/numeric_pipeline_fusion_profile_r502.json)、64MiB+8bytes・係数0.5・Linux:

| 32回の全仕事 | 元配列 | 融合 | 独立C |
| --- | ---: | ---: | ---: |
| plain wall中央値 | 17.7124秒 | 9.7538秒 | 6.1527秒 |
| profile変換工程のwall割合中央値 | 60.0654% | 31.7053% | 2.3492% |
| A/A最大比 | 1.1943 | 1.2680 | 1.2819 |
| observer最大比 | 1.2125 | 1.2105 | 1.1918 |

元配列/融合のplain各組比は1.5525〜2.2776、中央値1.8794、IQR1.7137〜1.9448。
ただし**3programとも固定した校正上限1.10を超え、速度資格は不成立**です。
このIQRは6標本の記述で、信頼区間ではありません。32回は一つのprocess内の相関した反復です。
成功狙いの再実行やgate緩和はしていません。R496/R497/R499の失敗も保持しています。

診断用の工程価格: 元配列は変換割合0.600654、無限に速い変換を仮定したAmdahl上限2.50409、
達成C変換性能への比0.0134643。融合は割合0.317053、同上限1.46424、達成Cへの比0.0472556。
仮定する達成C比1.0に対して、全体投影はそれぞれ2.45439/1.43281ですが、校正失敗のため実装理由に使いません。
達成Cは物理roofではありません。binary64 read/write・filesystemの物理上限は未測定です。

次は入力保持・独立出力の同じ契約で、確保込みの変換とresident変換を分け、
同じread/write処理の実効帯域とSIMD・スレッド数の曲線を測ります。その後、全仕事で選択を検証します。
計算だけを並列化する前に、残る入出力・確保・解放と必要な転送量を確かめます。
今回はcompiler/runtime/言語仕様を変更していません。R501の資源削減と本体統合は維持しています。
親の独立再計算で固定39件・時計・価格・比・13source pins・2生成形・期待値hashを確認しました。
Windows/Linux各8種類の校正境界・順序・幅・誤判定拒否を確認。測定総費用473.456秒、
buildは元配列1.3341秒/融合0.8889秒/C0.3010秒です。AI実モデル比較費ではありません。

再現（Linux、新record名が必要）:

```sh
python3 -B language_examples/numeric_pipeline_fusion_profile.py --record language_examples/new_fusion_profile.json
```

workには出力reopen/flush・関数cleanupを含み、phase外の費用も残します。
whole-output検査はcacheを温めます。process CPU/RSSは検査と期待値も含み、
cold IO・fsync永続化・work単独RSS・全用途最速の資格にはしません。


## 中間配列を作らず一回の走査へまとめる（R501）

実用のdecode→一対一乗算→encodeを、一つの独立出力bufferへの走査にまとめる本体実装を追加しました。
元の入力は変更しません。関数名による判定ではなく、[解析器](python/pkg-v12/float64_fusion.py)が
codec wrapperのbody・純粋mapのbody・中間配列の全使用を確認し、compilerが型・注釈・返却契約を検査します。
中間値の再利用、alias、calleeのshadow、未知body、副作用・途中return/break等があれば元経路へ戻ります。
別objectの未知bodyを推測して融合しません。公開APIの追加や全言語共通IRの導入は不要でした。

元の実用ソースを同じ最新版で融合無効/有効にして、[元経路](language_examples/numeric_pipeline_resources_before_r501.json)と
[融合経路](language_examples/numeric_pipeline_resources_after_r501.json)を測りました。
前後各72件、計144件の全出力が独立Python期待値と一致、入力保持と全解放も確認しました。
各3回の資源量は同一。融合無効の資源量はR500の結果と完全一致、独立Cの資源量も前後不変です。

| 8388609要素、64MiB+8bytes | 配列を使う元経路 | 一回走査 |
| --- | ---: | ---: |
| 同時payload確保ピーク | 402653986bytes | 201327242bytes |
| 成功したpayload確保要求累計、realloc込み | 805241755bytes | 335479619bytes |
| 明示memcpy/memmove要求bytes | 268435488bytes | 134217744bytes |

**ピーク約50%、確保要求累計約58.3%、コピー要求bytes50%の削減**です。
これらはallocatorが数えたpayloadと要求量で、RSS・物理traffic・libc内部・header/stdio内部を含みません。
scalarの8byte要求へ変わるため、LEの明示copy要求回数は4→16777218回に増えます。
計測器が各要求を数える負担も異なります。実際のlibc呼出し回数やCPU費・速度に読み替えません。
時間校正は未実施で、**速度向上・物理限界到達は未資格**です。R496/R497/R499の失敗も保持しています。

Windows/Linux各31種類を確認。独立算術と元経路、両入力/出力endian、0/1/8192/8193/65537要素、
特殊floatの事前NaN契約、unaligned/幅/NULL/arena、OOM3箇所、1001回の解放、誤出力拒否、
型・shadow・追加使用のfallback、元のC buffer ABIとC連携を含みます。
融合したAILライブラリを日本語/emojiパスへ移動し、ソースなしで8196要素の全出力を照合しました。
解析器もobject identityへ含めました。ABI10不変、再利用objectは新compiler/runtimeで再ビルドしてください。

現行資源測定の再現例（Linux）:

```sh
python3 -B language_examples/numeric_pipeline_resources.py --disable-fusion --record language_examples/new_array_resources.json
python3 -B language_examples/numeric_pipeline_resources.py --record language_examples/new_fused_resources.json
```

新しいrecord名が必要です。fusion工程はmap欄にまとめ、decode/encode欄はゼロになります。
旧R499の5工程timerは生成形の変化を拒否するため、この新版へそのまま使えません。
次はcounterなしの元経路/融合/独立Cを固定手順で測り、現在の工程割合・Amdahl上限・参照達成比を再評価します。
その結果からファイル読込み、既知長確保、SIMD/threadsのどこへ進むかを選びます。

## コンピュータの制約から実行方式を決める（R500）

設計の順序を、必要な仕事と転送→所有権と寿命→一括確保と走査統合→SIMDと並列化に置きます。
独立したbinary64乗算は1要素1乗算・論理read8/write8bytesです。これは最低限の仕事量で、
CPUの物理メモリ転送量ではありません。file経路には入力と出力も必要です。
現在の複数配列・返却copy・arena snapshotを減らしてから、実効帯域と依存関係で実行方式を選びます。

まずcompiler/runtimeの**独立所有のfloat配列の返却**を変更しました。
通常AILのNULL/0呼出しで、非空かつ容量=長さならbufferをspillへ渡し、元をゼロ化して既存cleanupへ進みます。
借用parameter・空・余剰capacity・十分/短いC bufferは従来のcopy経路です。
余剰capacityまで移すと保持メモリが増えるため、その形は転送しません。ABI10不変、objectは再ビルドが必要です。

[変更前](language_examples/numeric_pipeline_resources_before_r500.json)と
[変更後](language_examples/numeric_pipeline_resources_after_r500.json)を、
元の実用AILソース・importsと独立Python期待値で確認しました。
0/1/8192/8193/65537/8388609要素×LE/BE×AIL/C×3回、**前後144件の全出力・入力保持・解放が一致**。
資源量は3回同一、全計測項目は増加なし、独立Cは変更なしです。

| 8388609要素、64MiB+8bytes | 変更前AIL | 変更後AIL |
| --- | ---: | ---: |
| 明示memcpy/memmove要求 | 335544360bytes | 268435488bytes |
| 成功したpayload確保要求の累計、reallocを含む | 872350627bytes | 805241755bytes |
| payload同時確保ピーク | 402653986bytes | 402653986bytes |

コピー要求を20%、確保要求の累計を67108872bytes減らしました。**ピークメモリの削減や速度向上は未達**です。
[計測器](language_examples/numeric_pipeline_resources.py)は明示要求を数え、allocator header・libc内部コピー・
stdio内部・RSS・物理転送量を含みません。Cのscalar memcpy要求も物理トラフィックに換算しません。
Windows/Linuxそれぞれ18種類を確認。幅・NULL・空・capacity余り・overlap・借用入力・nested return・
NaNのraw bits・反復/例外解放・source-free object、末尾誤り/欠落/余分な出力の拒否を含みます。

次にまとめて作る対象は、**codec→純粋な一対一map→codecの走査統合**です。
関数名による決め打ちではなく、body・全使用箇所・alias/escape・副作用・例外を確認します。
中間配列がこの鎖以外で使われず、引数を一度だけ順番どおり評価できる場合に限定します。
元bytesは不変のまま、一つのowned出力へ変換します。未知のcallee・別objectの未検証body・
途中break/return・未対応のfloat契約は現行経路へ戻します。公開APIの追加は先行条件にしません。
既知長mapの一括確保と返却の所有権も共通仕様にします。SIMD/threadsはその後に同じ出力契約で選びます。
shared spill/例外/arenaを持つ関数を、そのまま同時実行できるとは扱いません。

R499の時間校正失敗を保持し、2.67倍の投影や旧roof表を採用根拠に使っていません。
今回の採用根拠は独立出力一致と直接数えた確保/copy要求です。物理roof・最高速度・全用途最速は未実証です。

## 実用の数値処理を工程ごとに値付けする（R499）

[numeric_pipeline_profile.py](language_examples/numeric_pipeline_profile.py)は、
R498の実際のAILソースとsource importsをコンパイルし、read/decode/map/encode/writeを測ります。
callerの所有権受渡しも対象にし、出力の開き直し・flush・関数の解放を全体時間へ含めます。
比較する[独立C実装](language_examples/numeric_pipeline_host.c)は、privateな入力bufferで
decode→乗算→encodeを一回の走査へ統合します。入力ファイルは変更しません。
要素数・入力・有限factor0.5・出力byte順序は同じです。

64MiB+8bytesを各processで32回処理し、**全26jobs/832回の出力を独立Python期待値と全文照合**しました。
空/末尾lane/8193/65537要素を含む28境界、誤った末尾oracleの2controls、
引数を拒否して既存outputを保持する12件も確認しました。純Pythonの計測検査3種類PASS。
[初回の全結果](language_examples/numeric_pipeline_linux_r499.json)は校正失敗も含めて保存しています。

| 32回のcomplete file pipeline | AIL観測中央値 | 独立fused C観測中央値 |
| --- | ---: | ---: |
| 全体work | 18.240s | 5.338s |
| decode+map+encode | 11.554s | 0.129s |
| peak RSS、oracleを含む | 395056KiB | 132776KiB |

AILの変換工程は全体workの61.053〜64.953%、中央値63.295%でした。
同一programのA/A最大差はAIL29.423%/C14.851%、observer差は30.260%/14.437%で、
事前10%を超えています。**上限の値付けは未適格、新しい最適化は未採用**です。
診断値の工程割合0.632946/Amdahl上限2.724392、C参照達成比0.011180/仮定1.0からの
全体投影2.672861倍を実装根拠に使いません。中央値の表も再現可能な速度保証ではありません。

単にappendを速くするだけでなく、decode/return/encodeの配列確保とcopyを一緒に扱う設計が必要です。
次は実測時間の成功待ち再試行ではなく、現行経路の確保量・copy箇所・所有権を直接調べます。
既知長mapの一括確保、owned returnの移動、最後の使用が終わる中間配列の除去を設計候補にします。
副作用・alias・短いcaller buffer・overlap・NaN演算の意味を維持できる範囲を限定します。

oracleの検査は時計の外ですがcacheに影響し、process CPU/RSSには含まれます。
fsyncによる永続化の時間を含めていません。既存roof表のread-only stream/f32 FMAを、
今回のbinary64 read/writeやfilesystemの物理上限に読み替えません。新しい物理roofは未計測です。
旧R496/R497の校正失敗、R498本体とobject契約は変更していません。

## 大きいbinary64配列をAIL単体で処理する（R498）

`float64_decode(data: bytes, byteorder: int) -> list[float]` と
`float64_encode(values: list[float], byteorder: int) -> bytes` を本体に追加しました。
byteorderは0がlittle endian、1がbig endian。2つの位置引数を左から一度ずつ評価します。
整数として扱うFalse/Trueも0/1です。他のorderや8bytesの倍数でない入力はValueError。
decodeは独立して変更できる配列、encodeは変更されないbytesを返します。
変換自体は整数操作とmemcpyで、NaNの符号・payload・signaling bit、±0、subnormal、Infを保存します。
変換後の浮動小数点演算までNaN payloadを保存する契約ではありません。
固定8192要素制限はありません。実際のメモリとint64/size_t/PTRDIFFの幅が上限です。

[再利用ライブラリ](language_examples/binary_float64.ail)と
[数値変換プログラム](language_examples/numeric_scale_binary_main.ail)を追加しました。
外部C部品なしで、ファイルを読む→decode→各値に有限factorを乗算→encode→binary stdoutまで実行します。
stdoutに出すため入力ファイルを上書きしません。シェルで同じ入力先にリダイレクトしないでください。

```sh
python -B ail_chatgpt.py compile language_examples/numeric_scale_binary_main.ail -o scale
./scale input.bin 0 0.5 > result.bin
python -B -m unittest test_ail_float64_codec -v
```

引数不正・不正recordはexit2、IOエラーはexit3です。読込み・変換が失敗した場合stdoutは空です。
出力中のIOエラーは途中まで出力され得ます。任意のIEEE入力の乗算でNaN payloadは未指定です。
Windows/Linux各19種類（新規6・関連13）PASS、skip0。
empty/1/78/8192/8193/65537要素を両endianで全文照合し、元ソースを除去して移動したobjectを再利用しました。
64MiB+8bytesのlittle endian、65,544bytesのbig endianの実用処理は独立Python参照と全byte一致。
後続引数によるfield/list変更・途中例外、native幅/NULL/arena12件、割当て失敗3箇所、
1001回までの繰返しと終了後の追跡allocation/bytes/frameゼロも確認しました。
[検証範囲と制約](language_examples/float64_codec_r498.json)を保存しています。
旧binary_float_recordsのC部品/API・8192上限・NaN classの契約はそのまま使用できます。
ABI10は維持しますがcompiler/runtimeのidentityが変わるため、objectは新版で再ビルドしてください。

### 能力から実行方式を決める順序

この仕事の計算は要素ごと独立した乗算1回、最低限の論理read/writeは8+8bytesです。
ファイル全体の経路では、decode・map・encodeの別bufferと受渡しcopyも存在します。
処理を統合して必要passを減らすには、入力snapshot・alias・戻り値の所有契約を先に確定します。
既知の要素数に対する一括確保とowned結果の受渡しを設計し、通常のAIL呼出しとcaller bufferの両方を対象にします。
その後、実測したcompute能力・メモリ帯域・IO能力・依存関係に合わせてSIMDとthread数を選びます。

R496/R497の校正失敗は保持しています。C参照の観測性能を物理roofと呼びません。
本項は実用処理を可能にする言語機能で、速度・メモリ削減の採用や限界到達の証明ではありません。
新しい最適化を作る前に、その経路の工程割合・Amdahl上限・参照達成比を有効な測定で値付けします。

## 数値配列の能力をメモリ上で測る（R497）

[resident計測](language_examples/numeric_scale_resident.py)を追加しました。
64MiB+8bytesの同じ配列を64回変換し、各回で全文出力と元の入力を比較します。
初期読込み・確保・first-touch、最終書込みと検査時間を変換の価格から除き、
callee内部の確保・成長・コピー・解放と、C参照のthread生成・終了を含めます。
「RAMにあるデータを繰り返し変換する」という条件の実効性能です。

78jobs/4614回の変換、42境界、誤った末尾出力と入力書換えを検出する3controls、
幅・thread数・pass数・modeの不正15件を確認しました。純Pythonの検査3種類PASS。
[全結果](language_examples/numeric_scale_resident_linux_r497.json)を保存しています。

| 64回のcomplete call | kernel時間の観測中央値 | 論理read+writeの観測GB/s |
| --- | ---: | ---: |
| 現行AIL、1thread | 4154.567ms | 2.068 |
| 独立C、1thread | 464.827ms | 18.480 |
| 独立C、2threads | 322.481ms | 26.637 |
| 独立C、8threads | 338.763ms | 25.357 |

AILのcomplete callはresident workload時間の99.096〜99.522%でした。
C参照は2threads以降の伸びが小さい観測です。C2/C8のA/A・observerは事前10%内ですが、
AIL/C1/C4/C16は超過し、**全体校正は未適格・最適threadは未選択**です。
診断値のphase share0.993779/Amdahl160.747、C達成比0.077621/仮定1.0からの
resident投影11.996倍を実装理由にしません。物理compute/DRAM roofとfile全体の速度は未実証です。

実行方式の設計は、要素数既知のmapで出力を一括確保し、owned結果の余分な受渡しcopyを減らす方向です。
十分なcaller bufferへの直接出力だけでなく、通常のAIL関数呼出しのspill/adoptも対象にします。
短いbuffer・部分overlap・snapshot保持・浮動小数点の意味を保つ必要があります。
先に実用のbinary64入力→変換→出力をAIL単体で書ける経路を作り、既存のC依存・8192要素制限を残すAPIも維持します。
新しい本体最適化を採用した結果ではありません。

## 数値配列の実行方式を先に測る（R496）

`float_values_scale` と同じappend形を現行compilerで生成し、独立Cの1/2/4/8/16スレッドと比較する
[数値配列の計測](language_examples/numeric_scale_profile.py)を追加しました。
仕事はIEEE binary64の各値を0.5倍し、同じ順序のbinary64ファイルを出力することです。
1要素の仕事は乗算1回、必要な配列読出し8bytes・書込み8bytesです。要素間の計算依存はありません。
この16bytesは論理量で、cache/DRAMやファイルI/Oの物理転送量ではありません。
NaN/Infを含めた任意floatの資格ではなく、有限値・符号付きzero・subnormalの固定入力です。

Linux/WSLで64MiB+8bytesの全文出力78回と、empty/末尾lane/幅/丸め/不均等thread分割42件が
独立Pythonのmultiply/pack期待値と一致しました。検査ロジック3種類PASSです。
[初回の全結果](language_examples/numeric_scale_linux_r496.json)を保存しています。
読込み・完全なscale呼出し・書込みを分け、clockを外した同一プログラムとも比較しました。

初回は書込みの占有が大きく、AILのprofile実行で全体wallの54.2〜81.9%でした。
全ての比較でA/Aまたはobserver差が事前10%を超え、**上限の値付けは未適格**です。
診断値のscale割合17.014%から得るAmdahl上限1.205倍、C参照の達成比0.074985と
仮定1.0から得る全体1.1868倍は、最適化を実装する根拠に使いません。C参照は物理roofではありません。
最速thread数は選んでいません。初回計測後に総費用timerの変数再利用を修正しました。
旧recordの誤った総費用値は明示して保持し、個別wall/phase/出力と採否は変更していません。

次の実行設計は、まずresident配列の処理とファイルI/Oを分離して能力を測ることです。
配列の固定長確保と所有bufferの受渡しを検討し、必要なpassを減らしてからSIMD/thread数を選びます。
浮動小数点の加算reductionやFMA化を、独立した乗算と同じ意味で扱いません。

## bytes検索の保護コピーを式の寿命に収める（R495）

`bytes.find/rfind/count` の引数評価順・結果・幅の検査を維持し、一時的な保護コピーの寿命を短くしました。

- receiverとneedleがbytesの名前またはliteral、boundsが整数の名前・literal・符号付きliteralだけなら、元のbufferを借用します。
- calleeやfield等が含まれる場合は、後続引数が値を変更しても安全なコピーを作り、検索完了・途中例外時にそのコピーを解放します。
- 元の入力・別名・sliceは保持します。caller側で生成した他の一時値やfield読出しの所有コピーまで自動解放するものではありません。

既存の値を変えるcallee・nested search・途中例外・短絡評価・empty needle・INT64/NULL境界を検証しました。
8193行の全文照合とnative割当て数、301回の例外・別名保持と最大メモリを独立Python参照に対して検査しています。
Windows/Linux各13種類PASS/skip0。通常の整数CLIと分離ビルドも両環境で確認しています。

固定Linux/WSL・warm page cache・約24.26MB/262146行で、同一のfind版AIL clientを
原版/新版コンパイラでビルドして390回比較し、すべて独立期待出力と一致しました。
原版はR494初版とbinary SHAも一致しています。新しい所有規則を事前基準で採用しました。

| 同じfind版の処理 | 実行時間の観測中央値 | cycle内peak RSSの中央値 |
| --- | ---: | ---: |
| 原版コンパイラ | 222.023ms | 114512KiB |
| 新版コンパイラ | 62.393ms | 24448KiB |
| 独立C参照 | 71.729ms | 24448KiB |

原版比paired wall中央値3.44262/IQR[3.35515,3.55846]、peak RSS78.65%減、A/A最大8.9717%です。
C参照/新版のcycle集計比IQR[1.03817,1.14547,1.20374]、観測中央値では新版が約1.15倍です。
比較対象は独立したC参照1実装であり、全C実装・全用途・物理roofの上限を示すものではありません。
工程割合/Amdahl/物理roofは今回取得していません。速度予測をせず、再現した資源増加を修正してから測りました。
原版とR494bの別時点の時間差を、新しい改善率へ数えません。
[全比較R495](language_examples/bytes_search_regions_linux_r495.json)と
[コンパイラ/runtimeの変更](language_examples/bytes_search_regions_r495.patch)を保存しています。
stdlibの整数表APIもfindを使う簡潔な形へ接続しました。元のstr APIと出力契約は維持しています。
ABI10は維持しますが、compiler/runtime identityが変わるためobjectは現行版で再ビルドしてください。

## 中間データを作らない整数表の集計（R494）

`checked_integer` の `parse_int64_decimal_bytes(text: bytes)` と、
`integer_column_stats` の `integer_column_stats_bytes(data: bytes, column: int)` を追加しました。
入力bytesを保持したまま全文UTF8検証を済ませ、行とTAB列の範囲を直接解析します。
全文UTF16・行一覧・列一覧を作りません。元のstr APIも使用できます。

ASCIIの符号と十進数字、任意の先頭zero、INT64_MIN/MAX、各行を足した途中totalの範囲を検査します。
11改行・CRLF・空入力・NUL・非BMP・不正UTF8の検出優先順位を維持します。
負のcolumn/不足列/空field/不正整数/範囲外はValueErrorです。
全文をread済みのbytesで処理するAPIで、OSのstream読込みや並列reduceではありません。

`language_examples/integer_column_stats_bytes_main.ail` は新しい経路を使うCLIです。
AIL_CURRENTで通常の公開コマンドからビルドできます。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o identity.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/integer_column_stats_bytes_main.ail --object identity.o -o stats-bytes.exe
./stats-bytes.exe input.tsv output.tsv 1
```

列番号は0始まりです。出力はcount・total・minimum・maximumのTAB区切り1行です。
通常/分離ビルドをWindows/Linuxで検証し、入力と同一fileを出力にした場合や、
UTF8/列/整数が不正の場合は入力と既存出力を保護します。

固定Linux/WSL・warm page cache・約24.26MB/262146行で原版CLIと比較しました。
390実行すべてで独立期待出力と一致し、入力保持・CPU内訳・SHAも確認しました。
原版比のpaired wall比の中央値1.72044、inclusive IQR[1.66373,1.77851]、
A/A最大4.6123%で事前基準を通り、この明示的bytes API/CLIを採用します。

| 同じ固定処理 | 実行時間の観測中央値 | cycle内peak RSSの中央値 |
| --- | ---: | ---: |
| 元のstr経路 | 184.715ms | 84096KiB |
| byte範囲経路 | 107.322ms | 24448KiB |
| 独立C参照 | 90.650ms | 24448KiB |

peak RSSは70.93%減。C参照より約18.39%遅く、C以上や機械の物理限界への到達は未達です。
時間は起動・ファイル読込・検証・集計・書出し・解放を含む単一processのwallです。
工程割合/Amdahl/物理roofは今回取得していません。過去の未校正値で説明しません。
IQRは有限観測の判定で、統計的保証や未知の入力・別機械への保証ではありません。
初版はbytes.findが行ごとの保護コピーをarenaへ蓄積し、遅くなりメモリも増えたため採用しませんでした。
修正版はTABのbyte位置を一度だけ走査します。一般bytes.findの所有契約は維持しています。
[採用比較R494b](language_examples/integer_column_stats_bytes_linux_r494b.json)と
[初版の不採用記録R494](language_examples/integer_column_stats_bytes_linux_r494.json)を保存しています。
原版と初版の別時点の時間差を改善・悪化へ数えません。

## UTF8の行をbyte範囲で処理する（R493）

`for line in data.utf8_lines()` を追加しました。dataはbytes、lineもbytesです。
全文のstrict UTF8検証を先に済ませ、各行を元のbufferの範囲として渡します。
この処理は全文UTF16と行一覧を確保せず、入力byteを変更しません。

```ail
fn main() -> int {
    let data: bytes = "日本語\nsecond\n".encode();
    for line in data.utf8_lines() {
        print(line.hex());
    }
    return 0;
}
```

11種類の改行、CRLF、末尾改行、空入力、NUL、非BMPを扱い、receiverは一度だけ評価します。
後方に不正UTF8があっても最初の行処理より前にUnicodeDecodeErrorを報告します。
引数・keyword・for-else・tuple target・iterator自体の保持は未対応です。同名の利用者定義メソッドは維持します。
元のbufferと同じbytes寿命契約を使います。OSからのstream読込ではなく、手元のbytesを扱うAPIです。

Windows/Linuxの独立参照・8193行全出力、参照保持、例外と資源解放、raw幅/NULL境界を検証しています。
速度改善の採用は未確定です。変更前の融合区間計測R492は392全出力一致ですが、
A/A最大17.74%、AIL observer11.62%、C observer10.81%で未校正でした。
観測82.317%/全除去Amdahl5.655/C区間比0.38268（仮定1.0）を速度予測へ使いません。
[区間計測の記録](language_examples/integer_column_stats_fusion_price_linux_r492.json)を保持しています。
R494bで列選択とchecked整数解析を組み合わせた実用処理を比較・採用しました。結果と範囲は上の節を参照してください。

## 実効能力から実行方式を設計する（R491）

細部の命令短縮を先行する進め方を改め、仕事量・データ表現・依存関係と機械の実効能力から実行方式を選びます。
最初の融合候補は「全文読込→全文strict UTF8検証→byte範囲の行/列走査→順序付きchecked集計」。
不要な全文UTF16・行/列一覧を省く設計です。入力の不変性、11改行・CRLF、INT64各prefixとエラー優先順を保ちます。
本体への融合実装・高速化の採用はこれからです。

Linux/WSLで64MiBの独立copyを32回、1/2/4/8/16threadで固定35回実行しました。
入力・出力の全byteとchecksumは一致し、別枠のnative境界18件、解析/集計の3検査も成功しました。
生成ASMでmemcpyがpass loop内に残ること、全35記録・測定順・率・A/A・source SHAを独立再計算しました。
中央値のpayload速度は1thread 12.95、2thread 17.77、4thread 21.59、8thread 12.10、16thread 12.84 GB/sです。
2threadのA/A最大差26.09%が事前の10%条件を超えたため、全体校正は未適格でthreadを自動選択しません。
この負荷の観測では4threadが最速でしたが、他のソフトや物理DRAM上限へ一般化しません。
payloadの2倍のlogical copy trafficと実際の物理転送量を区別し、後者は未確認です。

[固定校正と全記録](language_examples/memory_copy_calibration_linux_r491.json)、
[再利用する校正driver](language_examples/memory_copy_calibration.py)を保存しています。
工程割合/Amdahl/C達成比は未校正のまま。算術・I/O・GPU上限、融合候補の全体時間/メモリ比較は未達です。
全体goalは継続中です。

## 数値フィールド更新の測定と限界（R490）

構造体の数値更新に、receiverの保持4回と対応する解放4回がある生成Cを取得しました。
現在の本体と同じ実行ファイルSHAを再現し、読み出しは既に参照を借りていることも確認しました。

64回に1回のサンプリングと空の時計読み取りを使う観測器を実装し、処理順序・対象範囲・診断値の4検査が成功しました。
固定負荷の392回で全出力と入力が参照に一致し、全CPU内訳・測定順序・48ブロックの合計も再検査しました。
ただし、A/A最大差5.30%に対し、計測あり／なしの差はAILで最大16.05%、Cで10.35%となり、10%の条件を超えました。
測定位置による補正値の変化も大きく、Cでは空の時計費用を引いた値が負になるブロックが2組ありました。

したがって、成分の値付けは未校正です。参考値の外挿割合0.666%・完全除去Amdahl1.0067・経験的C比0.188（仮定1.0）を、
実装理由や性能上限として使いません。receiverの保持を省く変更は本体へ入れていません。
[全測定R490](language_examples/integer_column_stats_field_price_linux_r490.json)、
[生成Cの確認](language_examples/integer_column_stats_field_codegen_linux_r490b.json)、初回取得失敗を保存しています。

次は、内側の処理へ時計を追加する方式を離れ、既存のCPUサンプリングで大きな費用の順位を調べます。
ローカルにgprofとglibcの `monstartup` / `_mcleanup` / `profil` 宣言がありました。staticリンクと実行はまだ未検証です。
CPUのPC分布を実行時間の工程割合へそのまま換算しません。実測の読み方は[GNU sampling誤差](https://sourceware.org/binutils/docs/gprof/Sampling-Error.html)を参照します。
本体の高速化は今回未達で、全体ゴールは継続中です。

## 時間とメモリを両方扱う採用判定（R489）

採用判定を、既存の「速度IQRが1.0をまたぐなら引分け」という規則に合わせました。
速度で負けが示されず、メモリ削減率のIQR下側が正なら、メモリ改善として採用できます。
各回の全文一致・入力不変・正常終了に加え、時間とpeak RSSのA/A検査を必須にしています。
引分けは統計的同等性や、将来の無悪化を保証するものではありません。

同じコピー削減候補を、評価順修正だけを含む現在の本体と、測定前に固定した390回のABBA配置で直接比較しました。
全390回の独立参照出力と入力が一致し、A/A最大差は時間8.96%、RSS0%で基準内でした。
今回は速度IQRが0.97219–0.99818と全体で1.0未満になり、速度で負けるため既定へ採用していません。

| R489の比較対象 | 実行時間の観測中央値 | cycle内peak RSSの中央値 |
| --- | ---: | ---: |
| 現在の本体 | 146.890ms | 84,096KiB |
| コピー削減候補 | 150.160ms | 77,952KiB |
| 独立C参照（O2） | 77.968ms | 24,448KiB |

候補はメモリ6MiB（7.31%）削減と引き換えに、時間中央値が約2.23%増えました。CPU中央値も145.448→148.377msでした。
[全実測R489](language_examples/integer_column_stats_split_transfer_linux_r489.json)と
[同じ候補の4行patch](language_examples/fresh_string_split_transfer_r488.patch)を保存しています。
R487/R488の記録は変更していません。R489は比較基準が違い、過去の回との時間差を改善・悪化の証拠にしません。

判定器は `language_examples.integer_column_stats_profile.summarize_transfer(raw)` で再利用できます。
速度引分け＋メモリ改善の採用、明確な速度低下、A/A不安定、測定順序・型・幅・欠損・同じ観測の重複を含む11検査が成功しました。
正式な共有selectorの確認条件は変更していません。この判断は固定負荷の観測IQRに基づき、信頼区間や全用途の最適性を示しません。

本体の評価順修正は維持しています。次の速度調査対象は数値fieldの書き込み時に重なるreceiverの保持・解放です。
読み出しは既に参照を借りており、重複したretainがあるという仮説は訂正しました。削減対象の占有時間はまだ未測定です。
C以上の速度、校正された工程価格、総AI効率最良は未達で、全体ゴールは継続中です。

## 分割の評価順修正と本体候補の実測（R488）

本体では `receiver().split(separator())` をreceiver→separatorの順に一度ずつ評価するよう修正しました。
receiverの例外ではseparatorを実行せず、separatorの例外・空区切りでも代入先の旧値を保持します。
両方が単純な変数または固定文字列の場合は、余分な一時変数を作りません。
最終本体の3検査はWindows/Linuxでスキップなし成功。8,193行の全出力と301周・602回の例外処理後の全解放も参照と照合しています。

fresh split結果の一覧領域を移動してコピーを省く候補は、計装なしの旧版・候補・Cで比較しました。
R487/R488の各390回、計780回すべてで独立参照との全文一致・入力不変を確認しました。
R488は旧版SHAを過去の測定と完全一致させ、A/A最大4.86%は基準内でした。
しかし旧版/候補の速度IQRは0.97696–1.00630で1.0をまたぎ、事前条件では引分けです。

| R488の比較対象 | 実行時間の観測中央値 | peak RSSの中央値 |
| --- | ---: | ---: |
| 旧本体の比較基準 | 126.207ms | 84,096KiB |
| 未採用の移動候補 | 127.273ms | 77,952KiB |
| C参照 | 64.695ms | 24,448KiB |

候補のメモリ削減6MiB（約7.3%）は観測しましたが、高速化の採用条件を満たさず既定本体へ入れていません。
[候補の4行patch](language_examples/fresh_string_split_transfer_r488.patch)と
[全実測R488](language_examples/integer_column_stats_split_transfer_linux_r488.json)、
[先行候補の全実測R487](language_examples/integer_column_stats_split_transfer_linux_r487c.json)を残しています。
表の候補値を、採用後の本体性能と扱わないでください。最終本体には評価順の不具合修正を残しました。

[生成コード・逆アセンブルの診断](language_examples/integer_column_stats_codegen_linux_r486c.json)では、
集計・整数解析・UTF-8変換はアドレスとコメントを除いた命令列が一致し、計装版の呼出し元ではスタックが160bytes増えていました。
これは静的診断で、CPU時間の内訳や計装による遅さの原因を証明したものではありません。
集計の定義は共有objectではなく再コンパイルするentry TU内です。R485時の共有objectに関する仮説を訂正します。
R485の工程価格は未校正のままです。条件付きstats比率50.48%/完全除去Amdahl2.019倍/C達成比0.485（仮定1.0）を、
コピー単独の値付けや物理上限に使いません。

次は生成コードの構造体参照の管理処理を調べ、実測で占有時間を確認してから削減候補を選びます。
C以上の速度・全用途最速・総AI効率最良は未達で、全体ゴールは継続中です。

## CPU内訳を含む性能比較（R485）

R484で追加したuser/system内訳を同じ固定入力・392回・ABBA配置で取得しました。
全出力一致・入力不変・全バイナリSHAのR484との一致を確認しました。
全392記録でuser_seconds + system_seconds = cpu_secondsでした。
A/A最大差1.55%は基準内ですが、AIL計装の最大差14.20%（8組中1組が10%超）により工程の価格は未校正です。
C計装の最大差は3.25%でした。未校正の記録から高速化候補を採用していません。

最大差の組（8実行合計）は、AIL通常版wall1.181914s / CPU1.164964s、
計装版wall1.349772s / CPU1.335143sでした。
追加CPU170.179msの内訳はuser150.148ms / system20.031msで、待ち時間だけでは説明できません。
原因を計装の時計呼出しやコード配置へ確定したわけではありません。

条件付きの集計工程比率50.48%（観測範囲46.46–51.44%）、完全除去のAmdahl上限2.019倍、
C同工程の達成比0.485（仮定1.0）。Cは別表現の実装で、物理的な上限ではありません。
この固定負荷の1実行観測中央値はAIL133.680ms / C70.063ms、peak RSS中央値84,096 / 24,448KiBです。
AILは約1.91倍遅く、C以上は未達。R484との時点差はAIL本体の速度改善へ数えません。
[CPU内訳を含む全測定](language_examples/integer_column_stats_price_linux_r485_cpu.json)を保存しました。

次は計装による影響を切り分け、生成コードの不要なリスト領域コピー・確保・解放を価格に基づいて検討します。
C連携の追加件数は性能の進捗へ数えません。候補の採用は独立参照との長い全出力一致と実測で判断します。

## 計測記録の保存場所とCPU内訳（R484）

R483と同じ測定器・入力・392回・ABBA配置・最大10%基準で、実行中の記録をLinux一時領域へ保存しました。
全出力一致・入力不変、R483との全バイナリSHA一致を確認しました。
計測あり/なしの最大差はAIL 9.31%、C 5.76%でしたが、A/A最大16.32%（8組中2組が10%超）のため、
価格判定は不合格です。保存場所が原因だったとの因果関係や、速度改善は主張しません。

未校正の条件付き集計工程比率50.39%、完全除去のAmdahl上限2.016倍、
C参照の達成比0.501（仮定1.0）。C参照は物理的な上限ではありません。
この固定負荷の1実行観測中央値はAIL 169.233ms / C 91.365ms、
peak RSS中央値は84,096 / 24,448KiBです。R483との時点差をAILの改善へ数えません。
[保存した全測定](language_examples/integer_column_stats_price_linux_r484_tmp.json)を参照してください。

遅い同一バイナリ実行ではwall536.250msに対してCPU534.404msが観測され、
待ち時間だけでは説明できません。以後の `wall_clock="monotonic_raw"` の測定は、
合計CPUに加え、既存wait4記録の `user_seconds` と `system_seconds` を返します。
既定の測定API・時計・native record・合計CPUの意味は変えません。
R484の過去recordへ未取得の内訳を補ってはいません。この追加だけで原因や高速化を実証したとは扱いません。

CPU内訳の境界・既定APIの3検査がWindowsで、同じ3検査と実wait4記録・CPU時計照合の計5検査がLinuxで、スキップなし成功しました。
実RAW recordのuser/system各値と合計の一致、microsecond・0・非有限値・負値・合計overflowを確認しています。

## 現在の性能比較（R483）

目標は、同じ仕事・出力・機械で最適化したC以上の時間・メモリ効率を追求することです。
C連携は比較・再利用の手段で、機能の追加件数は速度改善の証拠にしません。
整数表の集計では、24,260,455 bytesの固定入力を392回測定し、全出力一致と入力不変を確認しました。
順序を近接したA→B→B→Aへ変更しましたが、A/A最大12.2%、計測あり/なし最大23.3%差が残り、
既存の最大10%基準で価格判定は不合格です。高速化候補は作成・採用していません。

未校正の条件付き観測では集計工程が49.47%、完全除去を仮定した全体の上限は1.979倍、
Cの同工程に対する達成比は0.436（仮定1.0）でした。C参照は別表現の実装で、物理的な上限ではありません。
この固定負荷の1実行中央値はAIL 226.640ms / C 104.342ms、
プロセスpeak RSS中央値は84,096 / 24,448KiBでした。ばらつきを含む未校正の診断値です。
現状のAILがC以上の効率に達したとは扱いません。成功するまでの再実行や外れ値除外は行っていません。
[全測定・未校正の理由](language_examples/integer_column_stats_price_linux_r483.json)を保存しています。
測定順序・既存価格判定の8検査はWindows/Linuxでスキップなし成功しました。
全用途最速・総AI効率最良は未達です。

## 数値リストを持つ構造体とC連携（R482）

構造体に `list[int]` と `list[float]` を保持できます。構築・フィールドの読出し・置換で
独立したコピーを作るため、元のリストや構造体を変更しても取得済みの値を使えます。
整数とfloatの要素型は一致させてください。暗黙の変換はしません。空の `[]` はフィールドの型に従います。

```ail
struct Series { values: list[int]; }
let source: list[int] = [1, 2];
let series = Series(source);
let saved: list[int] = series.values;
saved.append(3);
series.values = saved;
```

R582では直接の `series.values.append(...)`、要素代入・削除・reverseに対応します。sortと`+=`は未対応です。
型付きのローカルへ読み出して変更し、フィールドへ戻してください。
len・添字・slice・for・reversedを使えます。走査中にフィールドを置換しても、走査開始時の値を辿ります。
関数・メソッドから返した数値リストも所有する値です。Cや読取り専用の関数へ渡す時は、
名前を付けた型付きリストを使ってください。float内包表記はR567で追加しました。空リスト再代入の範囲は変わりません。

`numeric_series.ail` は `IntegerSeries` / `FloatSeries` と、
`integer_series_new` / `float_series_new`、`values_copy()` / `replace(values)` を提供します。
`integer_series_render(series)` は各整数にLFを付け、空なら空文字列を返します。
`numeric_series_native_main.ail` は既存C部品を使い、昇順の整数列から指定範囲を取り出す
`integer_series_native_between(series, low, high)` と、
`float_series_native_average(series, window)` を提供します。重複した整数は使えます。
逆順の範囲は空、非昇順の入力はValueErrorです。平均のwindowは1以上、要素数以下です。
結果は元の入力とCの一時領域から独立しています。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/c_integer_result.c --interface language_examples/c_integer_result.json -o series-integer.o
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/c_float_result.c --interface language_examples/c_float_result.json -o series-float.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/numeric_series_native_main.ail --object series-integer.o --object series-float.o -o numeric-series.exe
.\numeric-series.exe input.tsv 1 -100 100
```

引数は `INPUT COLUMN LOW HIGH`、列番号は0から数えます。厳密なASCII十進int64を解析し、
入力を全て処理してから整数を1行ずつ出力します。空の結果は空出力です。
成功は0、不正な引数・UTF-8・整数・非昇順・I/O失敗はstderr付きの2です。
処理エラーではstdoutを出しません。出力先のI/O失敗で書込み済みbytesを戻す保証はありません。
全入力とコピーを保持するため、プロセス全体のメモリ上限や速度向上を示す機能ではありません。
ABI10は維持していますが、旧コンパイラで作ったAIL objectはソースから再ビルドしてください。

Windows・Linuxで新規10種類と関連8種類、計18種類がスキップなしで成功しました。
独立Python参照との1MiB超の全出力、int64端・2^53超、0/1/8191..8193要素、値の保持を確認しました。
NaNのpayload・無限大・負のゼロ・非正規化数は、生成したフィールド・メソッド・通常/spill戻り値を通して全ビット一致しました。
追跡した301回の例外処理後は、割当・使用バイト・後始末の枠が0でした。
通常・分離ビルドと、日本語パスへ移動したソースなし部品の逆順2通りの再リンクも成功しています。
全corpus/必要CI・実arm64/32ビット・全割当失敗時の回復・総メモリ上限・速度改善・総AI効率最良は未検証です。

## JSON Linesの値を選択し項目を組み替える（R481）

JSON Linesの各文書から同じPointerの値を取り出すか、指定した名前とPointerで新しいオブジェクトを作れます。
既存のJSON Pointer規則を使い、数値の元の表記・部分木の重複キー・出現順を保ちます。

| 部品 | API |
| --- | --- |
| `json_projection.ail` | `json_projection_new(names, pointers)` / `json_projection_parse(text)` |
| `json_projection.ail` | `json_document_select(document, pointer)` / `json_document_project(document, projection)` |
| `json_document_batch.ail` | `json_documents_select(batch, pointer)` / `json_documents_project(batch, projection)` / `json_documents_render_lines(batch)` |
| `json_lines_io.ail` | `json_lines_read_file(path, size)` |

`JsonProjection`は`names: list[str]`と`pointers: list[str]`を保持します。newは同じ長さ、
重複しないUnicodeの項目名とPointerの構文を検査し、一覧をコピーして保持します。
空の名前、空の指定、同じPointerの繰返しは使えます。公開フィールドを変更した後も、使う時に再検証します。
parseは項目名からPointer文字列へのJSONオブジェクトを受け取り、重複する項目名や文字列以外の値を拒否します。
空の指定は各文書を`{}`にしますが、元の全文書の妥当性検査は省きません。

選択・項目変換の結果は、新しい文書と新しいノードです。元の一覧やノードを変更・破棄しても使えます。
元の文書は変更しません。名前の曖昧さや不正な文書・指定は`ValueError`、
参照先の欠落は`KeyError`です。空の文書集まりでも指定を検証します。
render_linesは全件を検証・描画してから、各文書にLFを付けた文字列を返します。空の集まりは空文字列です。

`json_lines_transform_main.ail`の引数は`INPUT SIZE MODE SPEC`です。
SIZEは正のint64。selectのSPECはPointerそのもの、projectのSPECは上記JSONオブジェクトです。

```powershell
python -B ail_chatgpt.py compile language_examples/json_lines_transform_main.ail -o json-transform.exe
.\json-transform.exe events.jsonl 65536 select /payload
.\json-transform.exe events.jsonl 65536 project '{"id":"/id","value":"/payload/value"}'
```

コマンドは指定を入力ファイルのopen前に検査し、全入力の読込み・変換・描画が成功した後だけ、
コンパクトJSONを1文書1行で出力します。空入力は空出力。成功は0、不正な引数・指定・入力・欠落・I/O失敗は
stderr付きの2で、処理の失敗ではstdoutを出しません。出力先のI/O失敗で書込み済みのbytesを戻す保証はありません。
入力と結果を全件保持するため、メモリ使用量は入力と指定に応じて増えます。速度改善やメモリ上限の証明ではありません。
旧`json_lines_main.ail`のJSON配列出力と`json_lines_collect_file`も使えます。

Windows・Linuxで新規8種類と既存コマンド2種類の計10種類が、スキップなしで成功しました。
1MiB超の全出力、全6JSON型、512段の部分木、65,537桁の数値表記、Unicode/NULと重複キーを独立Python参照へ照合しました。
元の文書・指定の変更後の値保持、途中の解析・参照失敗で出力しないこと、指定のopen前拒否を確認しました。
通常・分離ビルドと、ソースなしの11ライブラリ＋実ファイル処理helperを日本語パスへ移した逆順2通りの再リンクも成功しています。
入力・object・型情報の内容と更新時刻を保持し、型情報の改変や誤った引数を実行物の生成前に拒否しました。
本体・ランタイム・ABI10は変更していません。全corpus/必要CI・実arm64/32ビット・全割当失敗の回復・
新しい部品の割当カウンタ資格・プロセスのメモリ上限・速度向上・総AI効率最良は未検証です。

## 構造体のリストを保持しJSON Linesを読む（R479）

`list[構造体名]` をローカル変数の型と構造体のフィールドに使えます。
定義が後にある構造体と、循環しない入れ子にも対応します。
自己参照・循環する型、未知の要素型、異なる構造体を入れる代入は拒否します。

```ail
struct Item { value: int; }
struct Box { items: list[Item]; }
fn main() -> int {
    let items: list[Item] = [Item(7)];
    let box = Box(items);
    box.items.append(Item(8));
    print(len(items));
    let copied = box.items.copy();
    items.clear();
    print(len(copied));
    return 0;
}
```

この例は2を2回出します。構造体リストは参照を共有し、フィールドの読込み・初期化・代入でも同じリストを使います。
`copy()` とスライスはリスト本体を分け、要素の構造体は共有します。
保持したリストと要素は、元のフィールドの置換・構造体の解放後も使えます。
フィールドを直接、走査・添字参照/代入/削除・append/extend/pop/clear/reverse/sortできます。
sortのキーは対応する数値・文字列・バイト列のフィールドに限ります。

`json_document_value.ail` はJSON文書を保持する部品です。

| API | 結果 |
| --- | --- |
| `json_document_new(text)` | 解析した `JsonDocument` |
| `json_document_copy(document)` | 各ノードも独立させた文書 |
| `json_document_render(document)` | JSON文字列 |
| `json_documents_new()` | 文書の集まり |
| `json_documents_append(batch, documents)` | 全追加文書を検証し深くコピーして追加 |
| `json_documents_render(batch)` | 文書全体のJSON配列（末尾LFなし） |

文書は `nodes: list[JsonValue]`、文書の集まりは `documents: list[JsonDocument]` を持ちます。
追加がValueErrorになった場合は、その呼び出し前の状態を保ちます。追加後に入力文書を変更しても、追加済みの文書は変わりません。
JSONのメンバー順・重複キー・数値表記を保持します。文字列のエスケープは出力時に整えます。

`json_lines.ail` の `json_lines_decoder_new()`、`json_lines_decode_feed(decoder, text)`、
`json_lines_decode_finish(decoder)` で、分割入力からJSON文書リストを受け取れます。
LFで物理行を分け、ASCII空白・タブ・CRだけの行を省きます。
`line` は空白行を含む物理行数です。最後のLFがない文書もfinishで読みます。
feedが失敗すれば、その呼び出し前の状態を保持します。finishの失敗後は追加入力で修復できます。
finishが成功すると閉じ、その後のfeed/finishは空入力でもValueErrorです。

```powershell
python ailc.py language_examples/json_lines_main.ail -o ail_json_lines
.\ail_json_lines.exe input.jsonl 65536
```

正のint64サイズを開く前に検査し、UTF-8とJSON Lines両方のfinishを行います。
全入力が成功してからJSON配列とLFをstdoutへ出します。空入力は `[]` とLFです。
成功は終了0、不正引数・UTF-8・JSON・入出力エラーは終了2とstderrで、エラー時のstdoutは空です。
BOMを除去せず、入力ファイルを書き換えません。文書全体を保持するため、総メモリは入力とともに増えます。
速度向上やプロセスのメモリ上限を実証した機能ではありません。

Windows/Linuxで新規12種類・関連8種類、計20種類の検査がskipなしで成功しました。
独立したPythonのJSON解析と木の出力を参照に、数値表記・重複キー・Unicode/NULを含む1MiB超の全出力を照合しました。
共有とコピー、MIN64/MAX64添字、空/0/1/8191..8193要素、失敗時の状態保持と再試行、終了後の拒否を確認しました。
追跡した301回の例外処理では終了後の割当・使用バイト・後始末の枠が0でした。
型グラフ検査の再帰上限不具合を修正し、1,500段の正常・循環・未知型を検査しました。修正前後で実行プログラム8本の生成Cは完全一致しました。
元ソースなしの部品を日本語パスへ移動し、逆順2通りの再リンクと通常・分離コマンドの出力、入力/object/型情報の保持を確認しました。
全corpus/必要CI・実arm64/32ビット・全割当失敗時の回復・プロセス定常メモリ・速度向上・総AI効率最良は未検証です。


## 辞書を持つ構造体とCSVの集計・列選択（R478）

構造体に `dict[str,int]`、`dict[str,str]`、`dict[str,bytes]` を保持できます。
初期化・代入・読み出しで辞書とキー、文字列・バイト列の値を独立してコピーします。
構造体の参照は共有されます。取り出した辞書や値は、元フィールドの置換後も保持できます。
フィールドの要素への直接代入や `clear/pop/update/setdefault` は拒否します。
ローカルへ取り出して変更し、フィールドへ代入してください。
フィールドを直接走査する `for` と `items()` は、開始時の1つのコピーを最後まで走査します。

`csv_group.ail` と `csv_project.ail` を `use` して再利用できます。

| API | 結果 |
| --- | --- |
| `csv_groups_new()` | 集計状態 |
| `csv_groups_add(groups, rows, key_column, value_column)` | キーごとの件数・合計・最小・最大を追加 |
| `csv_groups_snapshot(groups)` | 初出順の独立した `list[CsvGroup]` |
| `csv_groups_render(groups)` | 集計結果のJSON配列（末尾LFなし） |
| `csv_project_row(row, columns)` | 指定順の列を持つ新しい行 |
| `csv_project_rows(rows, columns)` | 新しい行リスト |

列番号は0からです。重複した列指定と空の列指定を使えます。元の行番号は保持します。
負の列番号・不足する列はValueErrorです。空の行リストでも負の指定を拒否します。
集計値はASCIIの符号付き十進int64です。合計は各追加時に範囲を検査し、後の相殺を見込んで範囲外を許しません。
集計への1回の追加がValueErrorになれば、その呼び出し前の集計状態を保持します。

```powershell
python ailc.py language_examples/csv_table_main.ail -o ail_csv_table
.\ail_csv_table.exe project input.csv "2,0,2" 65536
.\ail_csv_table.exe group input.csv 0 1 65536
```

`project` は選んだ列をJSON Linesとしてstdoutへ出します。列指定 `""` では各行が空配列になります。
`group` はキー列・数値列を集計し、初出順のJSON配列を全入力成功後に1回出します。
項目は `key,count,total,minimum,maximum` の順です。両モードとも末尾はLFです。
正のint64読込みサイズと非負の列番号をファイルを開く前に検査します。
成功は終了0、不正引数・UTF-8・CSV・列・整数・入出力エラーは終了2とstderrです。
集計は入力エラー時にstdoutを出しません。列選択は遅いエラーで既に出した行が残り得ます。
ヘッダーの特別扱い・BOMの除去・入力ファイルの変更はしません。
長いフィールド・異なるキー・保持した値・一時領域によってメモリは増え得ます。
速度向上やプロセス全体のメモリ上限を実証した機能ではありません。

Windows/Linuxで新規11種類・関連7種類、計18種類の検査がskipなしで成功しました。
PythonのCSV reader・順序付き辞書・JSON writerを独立参照にし、1MiB超を含む全出力を照合しました。
int64端・中間合計/件数の範囲外・Unicode/NUL・重複/空の列指定・遅い入力エラーと再試行を確認しました。
辞書3種類の独立コピー、直接走査中の元フィールド置換、保持したキー/値、301回の例外処理を確認し、追跡した割当・使用バイト・後始末の枠は終了後0でした。
元ソースなしで日本語パスへ移動した部品を逆順2通りで再リンクし、通常・分離コマンドと入力/object/型情報の保持を確認しました。
全corpus/必要CI・実arm64/32ビット・全割当失敗時の回復・プロセス定常メモリ・速度向上・総AI効率最良は未検証です。


## 分割入力をUTF-8・CSVとして読み続ける（R477）

構造体のフィールドに `list[str]` を使えます。初期化・代入で文字列とリストを独立して保持し、読み出しも独立したコピーになります。

```ail
struct Row { fields: list[str]; }
fn main() -> int {
    let values: list[str] = ["日本語", "", "😀"];
    let row = Row(values);
    values.clear();
    let kept = row.fields;
    row.fields = ["next"];
    print("|".join(kept));
    return 0;
}
```

`row.fields.append(...)`や要素への直接代入など、フィールドそのものの変更は拒否します。読み出したローカル変数を変更してから `row.fields = values` と代入してください。構造体の参照は共有されますが、取り出したリストと文字列は後の置換や構造体の解放後も保持できます。

次のライブラリで、入力の境界をまたぐ文字とCSVの行を扱えます。

| API | 結果 |
| --- | --- |
| `utf8_decoder_new()` | UTF-8の読込み状態 |
| `utf8_decode_feed(decoder, data)` | 完成したUTF-8部分の文字列 |
| `utf8_decode_finish(decoder)` | 最後の検査と終了 |
| `csv_decoder_new()` | CSVの読込み状態 |
| `csv_decode_feed(decoder, text)` | 完成した行の `list[CsvRow]` |
| `csv_decode_finish(decoder)` | 最後の行と終了 |
| `csv_stream_row_json(row)` | 文字列のJSON配列 |

UTF-8は厳格に検査し、不完全な末尾だけを最大3バイト保持します。BOMやNULを取り除きません。
CSVはカンマ区切り・二重引用符を使い、引用符内のCR/LFと二重引用符を保持します。引用符外のCRLFは入力の分割をまたいでも1つの行末になります。
空白の除去・値の数値化はせず、空の記録を省きます。`CsvRow.number` は0から連続し、`fields` が列の文字列です。

feedでValueErrorになった場合、その呼び出し前の状態を保ちます。不完全なUTF-8や閉じていない引用符はfinishでValueErrorとなり、状態を開いたまま保ちます。
成功したfinishは状態を閉じ、その後のfeed/finishは空入力でもValueErrorです。

```powershell
python ailc.py language_examples/csv_stream_main.ail -o ail_csv_stream
.\ail_csv_stream.exe input.csv 65536
```

正のint64サイズをファイルを開く前に検査し、完成した行ごとにコンパクトなJSON配列とLFをstdoutへ出します。入力ファイルを書き換えません。
成功は終了0、不正引数・UTF-8・CSV・入出力エラーは終了2とstderrです。
遅い位置のエラーでは、既にstdoutへ出した完成行が残ります。各feedは状態を保ちますが、入力全体の原子的な出力ではありません。
64KiBの読込み上限や3バイトの未完成UTF-8は、プロセスのメモリ上限を意味しません。長いCSVフィールド・保持した行・関数内の一時領域は増え得ます。速度向上は実証していません。

Windows/Linuxで新規12種類・関連7種類、計19種類の検査がskipなしで成功しました。
Pythonの増分UTF-8デコーダとCSV reader/JSON writerを独立参照にし、全分割位置の小入力と1MiB超の全出力を照合しました。
NUL・Unicode・引用符内の改行・CRLF分割、厳格拒否、失敗時の状態保持と再試行、int64行番号・容量・添字の境界、保持したリストと文字列、sourceなし移動後の逆順2再リンクを確認しました。
追跡した所有権検査では終了後の割当・使用バイト・後始末の枠が0でした。容量のSIZE_MAX検査だけではPTRDIFF上限を拒否できない実行不具合を修正しました。
Windows初回の検査側不備2件を修正し、残った容量不具合も直して失敗対象だけ再実行しました。Linuxは修正後の19種類を1回検査しました。
全corpus/必要CI・実arm64/32ビット・全割当失敗時の回復・プロセスの定常メモリ上限・速度向上・総AI効率の最良性は未検証です。

## ファイルをバイナリの塊で読む（R476）

`for chunk in file_chunks(path, size)`で、ファイルを少量ずつ読み取れます。
pathは文字列、sizeは正のint64で、2個の位置引数を左から1回ずつ評価します。sizeが0以下なら、ファイルを開く前にValueErrorです。
1回の読み取りは最大`min(size, 65536)`バイトです。NUL、CRLF、Ctrl-Z、UTF-8として不正なバイトも変換しません。

```ail
fn main() -> int {
    for chunk in file_chunks("input.bin", 65536) {
        write_stdout_bytes(chunk);
    }
    return 0;
}
```

chunkは所有権のあるbytesで、後の読み取りやファイルの解放後も保持できます。
EOFの空データは反復に渡さず、以前のchunkを上書きしません。空入力で一度も束縛されなかった変数の参照は、既存の反復と同じfatal NameErrorです。
EOF・break・return・ループを抜ける例外でファイルを閉じます。ループ内で捕捉した例外やcontinueでは読み取りを続けます。
読み取りエラーはOSErrorで、エラーを伴う途中の塊は渡しません。読込みはCの[fread](https://sourceware.org/glibc/manual/latest/html_node/Block-Input_002fOutput.html)を使います。
file_chunksは直接forで使う構文で、第一級のファイル値・汎用イテレーター・with openではありません。

`binary_file_chunks.ail`は次の部品を提供します。

| API | 結果 |
| --- | --- |
| `file_chunk_totals(path, size)` | `[総バイト数, 塊の数, NUL数, LF数, CR数, 最大塊長]` |
| `copy_file_chunks(source, destination, size)` | コピーした総バイト数 |

集計は合計のint64上限を検査します。コピーはサイズ・入力と出力の同一実体を検査し、入力を開いて最初の読み取りが成功してから出力を置換します。
後の塊は既存のappend_bytesで追記します。空入力は有効なopen/EOFの後に空の出力を作ります。
開始前の失敗では入力と既存出力を保持します。途中の読み書きの失敗では部分的な出力が残り得ます。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/binary_file_chunks_main.ail --object file_identity.o -o ail_file_chunks
.\ail_file_chunks.exe stats input.bin 65536
.\ail_file_chunks.exe copy input.bin output.bin 65536
```

statsは6整数をTABで区切り、LFで終えます。copyの成功は終了0・stdout/stderrなしです。不正引数・ValueError・OSErrorは終了2・stderrありです。
バッファの64KiB制限はプロセスのメモリ上限ではありません。保持したデータや解析から外れるループは増え得ます。
原子的書込み・同時パス置換・全割当失敗時の回復・速度向上は保証しません。

Windows/Linuxで新規9種類・関連5種類、計14種類の検査がskipなしで成功しました。
独立したPythonのバイナリ読込みと全出力を照合し、16MiB超の対象ループでは追跡した割当が512KiB以下、終了後の残存割当・使用バイト・開いたファイル・後始末の枠が0でした。
読み取りの部分エラーと再試行、サイズやEOFの境界、保持した値、元入力/既存出力、ソースなし移動後の再リンクを検査しました。
Windowsでリスト共有をコピーと誤った検査1件を修正し、その対象だけ再実行しました。
静的領域・libc・RSS、全corpus/必要CI・実arm64/32ビット・全割当失敗時の回復・速度向上・総AI効率の最良性は未検証です。

## 長い名前と小数時刻を持つPAXアーカイブ（R475）

PAX形式のtarを読み書きするライブラリを追加しました。長いパス・リンク先・所有者名、大きなUID/GID、小数や負の時刻を、UTF-8文字列の元の表記として保持します。
既存のUSTAR用API（R474）はそのまま使えます。

| 部品 | API |
| --- | --- |
| `pax_attributes.ail` | `pax_attributes_decode/encode/merge/validate`、`pax_header_base`、`pax_extension_header` |
| `pax_archive.ail` | `pax_entries_decode`、`pax_names`、`pax_member`、`pax_entry_attributes`、`pax_entry_name`、`pax_entry_validate` |
| `pax_write.ail` | `pax_entries_encode` |

`PaxEntry`は順に`header: bytes`、`attributes: bytes`、`data: bytes`を持ちます。
headerは元の実メンバーヘッダー512バイト、attributesは有効なglobal/local属性をPAX形式で符号化したバイト列、dataは実データです。
`pax_entry_attributes(entry)`は独立した`dict[str,str]`を返します。属性は整数や浮動小数へ変換せず保存します。
sizeだけは、実バッファの残量を上限として解析し、データ長と照合します。

属性レコードの長さはUTF-8のバイト数で検査します。重複属性は最後の値を採用し、最初の出現位置を保持します。
local属性はglobal属性より優先し、空の値は削除の印として保持します。空のpathもそのまま返し、元ヘッダーの名前へ戻しません。
空のsizeはデータ境界を確定できないため拒否します。UID/GIDは空かASCII十進数、時刻は空か`[-]整数[.小数]`です。
キー内のNULと`=`は拒否し、値内のNULや改行は保持します。UTF-8以外のhdrcharset、sparse拡張、GNU volume拡張は未対応です。
[PAX属性の参考](https://www.gnu.org/software/tar/manual/html_node/PAX-keywords.html)と[レコード解析の参考](https://go.dev/src/archive/tar/strconv.go)を使い、この範囲を明示しています。

再書出しは有効な属性を各メンバーのlocal追加ヘッダーへまとめます。
元の実ヘッダー・属性値の表記・データ・順序・重複を保持し、追加ヘッダーの境界、padding、終端のブロック数は正規化します。
元のチェックサムを検査した後、属性が上書きする旧フィールドは解析から除きます。
全記録を検証した後に名前やメンバーを返し、孤立したlocalヘッダー、不正な末尾global属性、非ゼロの終端後データも拒否します。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/pax_main.ail --object file_identity.o -o ail_pax
.\ail_pax.exe normalize input.tar normalized.tar
.\ail_pax.exe concat left.tar right.tar combined.tar
.\ail_pax.exe extract input.tar selected.bin path/to/member.bin
```

出力と入力の同一実体を拒否し、全入力の検査と出力生成の後に1回書き込みます。concatの左右には同じ入力を指定できます。
成功は終了0・stdout/stderrなし、不正形式・メンバー・IO・引数は終了2・stderrありです。書込み前の失敗では入力と既存出力を保持します。
アーカイブ内のパスからツリーやリンクを作る操作はありません。全入力のメモリ保持、原子的でない書込み、同時パス置換、OS引数のNUL制限は残ります。
GNU longname・圧縮・sparse・UTF-8以外のPAX属性は未対応です。
属性が上書きしない旧数値のbase-256形式やUTF-8以外の旧名前も拒否します。

Windows/Linuxで新規12種類の検査がskipなしで成功しました。
独立PAX/USTARコーデックと実際のPython PAX writer/readerで、長いUTF-8名・全8種の記録・UIDや時刻の元の表記・1MiB超の出力全体を確認しました。
元ヘッダーの保持、属性が上書きする不正な旧フィールド、空属性、長さ・末尾・遅い位置の不正入力、入力/既存出力の保持、所有権とソースなし移動後再リンクも検査しました。
Windowsの初回は検査入力の長さを誤って1件失敗し、その入力だけ修正して対象を再実行しました。言語本体とUSTAR部品は変更していません。
全corpus/必要CI・実arm64/32ビット・巨大バッファ・速度向上・総AI効率の最良性は未検証です。

## tarアーカイブを読み書きする（R474）

USTAR形式の既存アーカイブを、AILの構造体レコード列として読み書きできます。
通常ファイル・ハードリンク・シンボリックリンク・文字/ブロックデバイス・ディレクトリ・FIFO・連続ファイルの記録を扱います。
リンクや特殊ファイルはアーカイブ内の記録として保持します。

| 部品 | API |
| --- | --- |
| `tar_header.ail` | `tar_header_decode(header)` / `tar_header_encode(entry)` |
| `tar_archive.ail` | `tar_entries_decode(data)` / `tar_names(entries)` / `tar_member(entries, name)` |
| `tar_write.ail` | `tar_entries_encode(entries)` |

`TarEntry`は順に、`name: str`、`typeflag: int`、`mode: int`、`uid: int`、`gid: int`、
`size: int`、`mtime: int`、`linkname: str`、`uname: str`、`gname: str`、
`devmajor: int`、`devminor: int`、`data: bytes`を持ちます。
typeflagは0～7で、0と7はdataを持つファイル、他はsize=0/data空です。
ヘッダーだけのdecodeはdataを空で返し、encodeはメタデータだけを検証します。
アーカイブのencodeとnames/memberは、sizeとdataの長さも全件照合します。

512バイトのヘッダーと符号なしチェックサム、USTAR magic/version、非負の八進数フィールドを検査します。
文字列はUTF-8として読み、先頭NULまでかフィールド全幅を使います。作成時は文字列中のNULを拒否します。
nameはUTF-8で100バイト以内、長い場合はスラッシュでprefix155バイト以内と末尾name100バイト以内に分割できる必要があります。
linknameは100バイト、uname/gnameは32バイト以内です。
mode/uid/gid/devmajor/devminorは0～2,097,151、size/mtimeは0～8,589,934,591です。
GNU/PAXの追加ヘッダー、base-256数値、圧縮、UTF-8以外の名前は未対応です。
[USTARヘッダーの参考仕様](https://www.gnu.org/software/tar/manual/html_node/Standard.html)に沿い、この文字コードと数値範囲を採用しています。

アーカイブ全体は512バイト境界にそろえ、終端のゼロブロック2個と、その後がすべてゼロであることを確認します。
入力のデータpaddingは内容を問わず読み、出力ではゼロにします。
再書出しはヘッダーの数字表記・padding・NULの旧通常ファイルフラグを正規化し、
表現するメタデータ・データ・順序・同名の複数記録を保持します。
namesは同名も含めて返します。memberは全件を検証した後、未登録名をKeyError、
複数の一致やデータを持たない記録をValueErrorにします。
元の入力を変更しない、新しい構造体と所有権のあるバイト列を返します。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/tar_main.ail --object file_identity.o -o ail_tar
.\ail_tar.exe normalize input.tar normalized.tar
.\ail_tar.exe concat left.tar right.tar combined.tar
.\ail_tar.exe extract input.tar selected.bin path/to/member.bin
```

concatは順序と重複を保持し、同じ入力を2回指定できます。
extractは指定した出力ファイルへ1記録のデータを書きます。アーカイブ内のパスからディレクトリやリンク、特殊ファイルを作る操作はありません。
出力が入力と同じ実体なら拒否し、全入力の検証と出力の生成後に1回書き込みます。
成功は終了0・stdout/stderrなし、不正形式・メンバー・IO・引数は終了2・stderrありです。
書込み前の失敗では元ファイルと既存出力を保持します。
全入力をメモリに保持します。原子的書込み・同時パス置換・巨大バッファの割当成功は保証しません。

Windows/Linuxで新規12種類の検査がskipなしで成功しました。
独立USTARコーデックとPython tarfileを使い、全8種の記録・全メタデータ・1MiB超の出力全体・Python生成アーカイブとの互換性を確認しています。
長さ・八進数・UTF-8・チェックサム・終端・重複・元入力の保持と、ソースなし移動後の再リンクも検査しました。
値の返却と例外で終わるobject関数を受理し、正常な落ち抜けと裸returnを拒否する本体修正を含みます。
全corpus/必要CI・実arm64/32ビット・巨大バッファ・速度向上・総AI効率の最良性は未検証です。

## バイナリデータを持つ辞書（R473）

`dict[str,bytes]`を変数・読み取り専用引数・所有権を持つ戻り値として使えます。
Unicode/NULを含む文字列キーと、空または任意のバイト列の値を保持します。

```ail
fn copied(values: dict[str,bytes]) -> dict[str,bytes] {
    let result: dict[str,bytes] = values;
    result["追加"] = b"\x00\xff";
    return result;
}
fn main() -> int {
    let original: dict[str,bytes] = {"画像": b"\x00\x80\xff"};
    let saved: bytes = original["画像"];
    let values: list[bytes] = original.values();
    let independent: dict[str,bytes] = copied(original);
    original.clear();
    write_stdout_bytes(saved);
    return 0;
}
```

辞書の代入・copy・戻り値はキーと値を独立して所有します。
取得した値やkeys/valuesの一覧は、元の辞書を変更・削除しても使えます。
keysは`list[str]`、valuesは`list[bytes]`、itemsの反復値は`str, bytes`です。
len、in/not in、添字、del、get(key, default)、pop(key[, default])、
setdefault、update、clear、copyを使えます。値とdefaultはbytes、キーはstrが必要です。
引数の辞書を直接変更するとコンパイル時に拒否します。ローカルへコピーして変更してください。
既存キーの更新は位置を保持し、削除して再登録すると末尾へ移ります。
辞書の直接反復中に追加・削除・clear・辞書の置換を行うと`RuntimeError`です。
既存キーの値だけの更新はできます。keys/valuesは独立した一覧なので元の辞書を変更できます。

| 部品 | API |
| --- | --- |
| `byte_map.ail` | `byte_map_decode(data)` / `byte_map_encode(values)` |
| `byte_map.ail` | `byte_map_copy(values)` / `byte_map_merge(left, right)` |
| `byte_map.ail` | `byte_map_keys(values)` / `byte_map_values(values)` |

保存形式は`AILM`の4バイトと件数のu32 little-endian、その後に各レコードの
キーのUTF-8バイト数・値のバイト数（各u32 little-endian）、キー、値を並べます。
順序を保持し、値は文字に変換しません。mergeは同じキーの最後の値と最初の位置を使います。
decodeは短い入力・不正な長さや件数・キーのUTF-8・重複キー・末尾の余分なバイトを拒否します。
件数と長さは実際の残り入力に収まることを確認してから切り出します。
encodeの件数と各長さはu32以内、合計はint64以内です。
キーのUTF-8変換と所有権付きの辞書取得は、符号化後の長さを確認する前に実行されます。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/byte_map_main.ail --object file_identity.o -o byte_map
.\byte_map.exe normalize input.ailm output.ailm
.\byte_map.exe merge left.ailm right.ailm merged.ailm
.\byte_map.exe extract input.ailm selected.bin 画像
```

CLIは全入力を検証してから1回書き込みます。出力が入力と同じ実体なら拒否します。
mergeで同じ入力を2回指定することはできます。成功は終了0・stdout/stderrなしです。
不正入力・未登録キー・ファイルや引数のエラーは終了2・stderrありで、
書込み前の失敗では入力と既存出力を保持します。NULや非常に長いキーのCLI引数にはOSの制限が適用されます。
全入力・辞書・独立コピーを保持し、原子的な書込みや同時のパス置換は保証しません。
bmapを受け渡す再利用objectは現在のコンパイラで構築してください。
structの辞書フィールドや公開C headerの辞書型は今回の追加範囲に含みません。

Windows/Linuxで新規12・関連12、計24種類の検査がskipなしで成功しました。
1MiB超を含む全出力を独立Python参照と照合し、32種類の型拒否、14種類の内部境界、ソースなし移動後の再リンクを確認しています。
対象の寿命検査では終了時の割当件数・使用バイト数・後始末の枠が0でした。
全corpus/必要CI・実arm64/32ビット・巨大バッファ・速度向上・総AI効率の最良性は未検証です。

## JSONの編集と設定の変更（R472）

既存のJSON文書表現を使って、値の置換・削除・追加と設定のマージができます。
各APIは新しいノード一覧を返し、元の一覧・構造体・文字列は変更しません。

| 部品 | API |
| --- | --- |
| `json_edit.ail` | `json_replace_at(nodes, pointer, value)` / `json_remove_at(nodes, pointer)` |
| `json_edit.ail` | `json_object_set_at(nodes, pointer, key, value)` / `json_array_insert_at(nodes, pointer, index, value)` |
| `json_merge_patch.ail` | `json_merge_patch(target, patch)` |

replaceは根も置換できます。removeで根を削除すると`ValueError`です。
object_setは選んだオブジェクトのキーを既存位置で置換し、未登録なら最後に追加します。
対象キーの重複は`ValueError`で、関係しない重複は保持します。
array_insertは直接の子の番号0から要素数までを受け付け、末尾にも追加できます。
範囲外は`IndexError`、対象が必要なコンテナ型でない場合は`ValueError`です。
入力と差し込む値を全検証してから処理し、Pointerのエラー規則はR470と同じです。
入れ子の親番号を振り直し、数値の表記、Unicode/NUL、メンバー順を保持します。

マージは[RFC 7396](https://www.rfc-editor.org/rfc/rfc7396)のJSON Merge Patchです。
オブジェクトのpatchは再帰的な変更を表し、nullメンバーはキーの削除を意味します。
配列・スカラーのpatchは対象全体を置換し、既存の対象がオブジェクトでなければ空のオブジェクトから変更します。
オブジェクトのnull値を設定する形式ではありません。根のnullや配列内のnullは使えます。
AILでは両入力の全オブジェクトの重複キーを事前に拒否します。置換される枝も対象です。
既存キーの位置を保持し、新規キーはpatchの順に追加します。再帰呼出しによる深さ制限は設けていません。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/json_merge_main.ail --object file_identity.o -o json_merge
.\json_merge.exe input.json changes.json output.json
```

CLIは入力・patchのUTF-8とJSON全体を検証し、変更と描画を終えてから1回書き込みます。
出力はコンパクトJSONと末尾LFです。成功は終了0・stdout/stderrなしです。
不正入力・重複キー・ファイルエラー・入力またはpatchと同じ出力先は終了2・stderrありです。
書込み前のエラーでは入力・patch・既存出力を保持します。入力とpatchを同じファイルにすることはできます。
全入力と変更途中の文書を保持し、原子的な書込み・同時のパス置換は保証しません。
これは使える処理の追加で、速度向上の主張ではありません。

Windows/Linuxで新規10種類の検査がskipなしで成功しました。
Windows初回の移動後検査1件はmainだけを分離ビルドへ渡して失敗し、
処理モジュールと入口を分けた同じ検査の再実行で成功しました。
Windowsのテスト収集で編集3件を重複実行した点もmodule参照へ修正し、
検査関数・独立参照を変えず、以後の収集数が3+3+2+2になることを確認しています。
深さ512、8191..8193メンバー、65537文字と任意幅の数値、全6型、
入力変更・破棄後の値保持、ソースなし移動と逆順再リンクを検査しました。
公開CLIでも1MB超の入力を含む全出力が独立Python参照へ一致しました。
新しいJSON部品の割当カウンタ資格、全corpus/必要CI・実arm64/32ビット・
速度向上・総AI効率の最良性は未検証です。

## JSONの値を指定して取り出す（R470）

JSON文書の配列・オブジェクト・文字列・数値・真偽値・nullから、指定した値を取り出せます。
既存の`json_parse_document`の`list[JsonValue]`表現を使い、数値をint64/floatへ丸めません。

| 部品 | API |
| --- | --- |
| `json_tree.ail` | `json_validate_nodes(nodes)` / `json_render_document(nodes)` / `json_subtree(nodes, index)` |
| `json_pointer.ail` | `json_pointer_segments(pointer)` / `json_pointer_index(nodes, pointer)` / `json_pointer_extract(nodes, pointer)` |
| `json_string_map.ail` | `json_string_map_parse(text)` / `json_string_map_at(nodes, pointer)` |

文書は単一の根を持ち、親を先に並べ、部分木が連続する必要があります。
空の一覧、不正なkind・parent・key・text、閉じた部分木への再訪問は`ValueError`です。
描画はキー・文字列をJSONエスケープし、数値の元の表記・重複キー・出現順を保持します。
ライブラリの描画に末尾LFはありません。部分木は新しい構造体の一覧で、親番号を振り直し、
根のparentを-1、keyを空にします。元の構造体や一覧を変更しても使えます。
部分木のindexは0以上の絶対番号で、範囲外は`IndexError`です。

Pointerは[RFC 6901](https://www.rfc-editor.org/rfc/rfc6901)の通常の文字列形式です。
空文字列は根、`/items/0`はitems配列の先頭を指定します。
キー内の`~`は`~0`、`/`は`~1`で表し、`~01`は一度だけ復号して`~1`になります。
空のキー・Unicode/NULを扱い、文字の正規化はしません。
参照したキーが重複して曖昧な場合や不正なescapeは`ValueError`です。
配列番号はASCIIの`0`または先頭0なしの数字列で、無効な表記は`ValueError`、
存在しないキー・番号・`-`は`KeyError`です。巨大な番号も桁あふれせず拒否します。
URIの`#`形式や、JSONで引用されたPointer自体の復号は行いません。

文字列辞書への変換では、選択した値がオブジェクトで、直接の子がすべて文字列である必要があります。
それ以外は`ValueError`です。変換先は独立した`dict[str,str]`で、重複キーは最初の位置と
最後の値を使います。これは辞書変換の規則で、Pointerの曖昧なキーへの参照拒否は変わりません。
`json_scalar_kind(token)`は未引用リテラルのnull=0・真偽値=1・数値=2を判定し、
それ以外の不正なリテラルはValueErrorです。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/json_query_main.ail --object file_identity.o -o json_query
.\json_query.exe extract input.json selected.json /items/0
.\json_query.exe string-map input.json settings.json /settings
```

CLIは入力JSON全体を検証し、結果を描画してから1回書き込みます。出力はJSONと末尾LFです。
成功は終了0・stdout/stderrなし、不正UTF-8・JSON・Pointer・型・ファイル・同一出力先のエラーは
終了2・stderrありです。書込み前の失敗では既存出力と入力を保持します。
ライブラリのPointerはNULや長いキーも扱いますが、CLI引数にはOSの文字・長さ制限が適用されます。
全入力を保持し、原子的な書込みや同時のパス置換は保証しません。

json_documentの追加APIと依存部品をobjectで使う場合は、それらを再ビルドしてください。

Windows/Linuxで新規10・関連4対象が成功しました。Windows初回では旧JSON文書検査の
不正UTF-8応答だけ6例が失敗し、現在の捕捉可能な仕様へ修正した2対象の再実行で成功しました。
深さ2048、8191..8193要素、65537文字のキー・値・配列番号、任意幅の数値表記、
誤った文書表現、正確なエラー種別、元データ変更後の保持、6部品のソースなし移動後2再リンクを確認しています。
公開コマンドではWindowsで2,474,732バイトの入力から、部分抽出・辞書化・全6型の抽出を行い、
すべての出力バイトが独立参照へ一致しました。入力と依存19ファイルは不変です。
全corpus/必要CI・実arm64/32ビット・速度向上・総AI効率の最良性は未検証です。

## 文字列の値を持つ辞書と設定ファイル（R469）

初期値付き変数、読み取り専用の関数・メソッド引数、所有権を持つ戻り値に
`dict[str,str]`を使えます。キーと値はUnicode/NULを含む文字列です。

```ail
fn renamed(values: dict[str,str]) -> dict[str,str] {
    let result: dict[str,str] = values;
    result["名前"] = "AIL";
    return result;
}
```

代入・`copy()`は独立したコピーです。検索・更新・削除・`len`・`in`・`clear`・`update`
に対応します。`get(key, default)`と`setdefault(key, default)`は文字列のdefaultを明示し、
`pop(key[, default])`も使えます。取り出した値は、元の辞書を変更・削除しても保持できます。
`keys()`と`values()`は独立した文字列リストです。挿入順、反復中の構造変更の拒否、
読み取り専用の引数、複数代入などの拒否は次節の整数値の辞書と同じ規則です。

`str.find(needle)`も追加しました。1個の位置引数を受け取り、Unicodeの文字位置を返します。
空のneedleは0、見つからなければ-1です。開始位置・終了位置・キーワード引数は未対応です。

`string_map.ail`は設定の読込み、独立コピー、結合、キー一覧、値一覧、JSON描画の6 APIです。
設定は1行の最初の`=`で区切り、キー前後の空白を除き、値は空白・引用符・`#`・`;`・`=`
を含めそのまま保持します。空行と、空白を除いた先頭が`#`の行は無視します。
区切りなし・空キーは拒否し、重複キーは最初の位置と最後の値を使います。
行区切りは`str.splitlines()`の規則です。引用符の解釈、変数展開、エスケープ解除、
行途中のコメント処理はありません。一般のINIや環境変数ファイルの互換パーサーではありません。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/string_map_main.ail --object file_identity.o -o string_map
.\string_map.exe input.conf result.json
```

出力は挿入順のJSON objectと末尾LFです。空入力は`{}\n`です。
不正なUTF-8・設定・入力と同じ出力先は書込み前に拒否し、成功時のstdout/stderrは空です。
全入力を保持し、書込みの原子性や同時のパス置換は保証しません。

Windows/Linux各35テスト（新規13・関連22）と、旧文字列コンテナの9実行例・2拒否例が成功しました。
完全出力、Unicode/NUL・空のキーと値、8191..8193要素、28種の型・変更・find引数の拒否、
評価順・短絡評価、例外後の保持、移動後のソースなしobject再リンクを確認しています。
対象の寿命検査は終了時の割当・使用byte・解放フレームが0です。辞書の一覧を反復しながら
一時文字列を作る場合も、後続の要素が解放されないことを文字列値・整数値の辞書で確認しました。
公開コマンドではWindowsで2,413,464バイト・8,198データ行を変換し、
2,474,225バイトのJSON全体が独立計算へ一致しました。入力と依存14ファイルは不変です。
全corpus/CI・実arm64/32ビット・速度向上・総AI効率の最良性は未検証です。

## 型付き辞書と文字列キーの表（R468）

初期値付き変数、関数引数、戻り値に`dict[str,int]`を使えます。
キーは文字列、値は符号付き64ビット整数です。空辞書も型を指定でき、別の型への暗黙変換は拒否します。

```ail
fn copied(values: dict[str,int]) -> dict[str,int] {
    let result: dict[str,int] = values;
    result["追加"] = 17;
    return result;
}
```

代入・`copy()`は独立したコピーです。引数は読み取り専用で、変更するにはローカルへ
コピーします。関数から返した辞書は呼出し元が所有し、元の辞書や動的なキーが解放された後も使えます。

検索・更新・削除・`len`・`in`・`clear`・`update`・`copy`に対応します。
`get(key, default)`と`setdefault(key, default)`には整数のdefaultを明示してください。
`pop(key)`はキーがなければKeyError、`pop(key, default)`は指定値を返します。
`keys()`と`values()`は独立したリストを返します。

挿入順を保ち、既存値の更新では順序が変わりません。削除して再挿入したキーは末尾になります。
`for key in values`と`for key, value in values.items()`では、値の上書きはできますが、
キーの追加・削除・空でない辞書の消去・反復元の再代入はRuntimeErrorです。
`for key in values.keys()`は作成済みのキー一覧を反復するため、元の辞書を変更できます。
複数代入・保存したitems view・Noneのdefault・構造体フィールド・ctypes公開は今回の対象外です。

`integer_map.ail`は、タブ2列の表を辞書へ読む、コピー、結合、キー一覧、検査付き合計、
JSON描画の6 APIを提供します。CLIはUTF-8の入力表をJSON objectと末尾LFに変換します。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/integer_map_main.ail --object file_identity.o -o integer_map
.\integer_map.exe input.tsv result.json
```

キーは空文字列も使えます。重複キーは最後の値で上書きし、最初の挿入位置を保ちます。
整数は符号とASCII数字だけの厳密なint64、行区切りは`str.splitlines()`の規則です。
空入力は`{}\n`を出力します。列数違反・不正な整数・UTF-8・入力と同じ出力ファイルは、
書込み前に拒否します。合計APIは途中のoverflowでもValueErrorです。
全入力を保持し、書込みの原子性や同時のパス置換は保証しません。

Windows/Linux各26テスト（新規12・関連14）と、旧文字列コンテナの9実行例・2拒否例が成功しました。
完全出力、int64両端・2^53境界、Unicode/NUL、8191..8193要素、21種の型・変更拒否、
評価順、例外後の値保持、ソースなしobjectの移動後2再リンクを確認しています。
直接・条件付きで返した辞書も、対象fixture終了時の割当・使用byte・解放フレームは0です。
公開コマンドではWindowsで1,235,553バイト・8,198行を変換し、1,263,695バイトのJSON全体が
独立計算へ一致しました。入力と依存15ファイルは不変です。
全corpus/CI・実arm64/32ビット・速度向上・総AI効率の最良性は未検証です。

## 型付きリストと整数列の書出し（R467）

初期値付きの変数に`list[int]`・`list[float]`・`list[str]`を宣言できます。
空リストの要素型も固定され、混在した初期値や異なる型の再代入は拒否します。
floatの要素には`float(value)`を明示してください。
型付きリストの`clear()`は型を保ったまま空にします。

```ail
let numbers: list[int] = [1, 2, 3];
let weights: list[float] = [-0.0, 0.5];
let words: list[str] = ["日本語", "", str(17)];
words = [words[2], words[0], words[1]];
```

関数の`list[int]`引数・戻り値は従来の整数`list`と同じ契約です。
整数・float・文字列リストの引数は読み取り専用で、変更するにはローカルへコピーします。
数値リストの代入は既存のコピー規則を維持します。文字列リストのコピーは独立した
要素配列を持ち、関数から返した動的なUnicodeやNULも呼出し元で保持できます。
リストの初期化・再代入は右辺を左から一度ずつ評価し、例外になれば元の値を維持します。

`typed_sequences.ail`は整数列の読込み・反転・描画、float列の倍率変換、文字列列の
コピーを提供します。CLIはUTF-8のタブ区切り表から指定列を取り、全値を逆順に
十進数とLFで書き出します。合計は計算しないため、各値がint64内なら合計のoverflowは関係しません。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/integer_column_values_main.ail --object file_identity.o -o integer_column_values
.\integer_column_values.exe input.tsv reversed.tsv 1
```

列番号は0から数えます。符号とASCII数字だけの厳密なint64を受け付け、行区切りは
`str.splitlines()`の規則です。空入力の出力は空です。列不足、不正な整数・UTF-8、
入力と同じ出力ファイルは書込み前に拒否します。全入力を保持し、書込みの原子性や
同時のパス置換は保証しません。通常・分離ビルドと`compile-module`による再利用が対象です。
構造体フィールドの許可型や外部ctypes向けコンテナ公開の範囲は変更していません。

Windows/Linux各30対象（新規10・関連既存20）が成功しました。完全出力、floatの実ビット、
int64両端・2^53境界、Unicode/NUL、8191..8193要素、29種の型拒否、例外後の値保持、
ソースを除いたobjectの移動後2再リンクを確認しています。終了時の割当・使用byte・
解放フレームは対象fixtureで0です。返却リストを含むFalse分岐の追加検査も両OSで成功しました。
公開コマンドでは1,254,462バイト・8,198行の入力の全値を独立計算へ照合しました。
全corpus/CI・実arm64/32ビット・速度向上・総AI効率の最良性は未検証です。

## 整数表の工程を測る（R466）

現行の表集計CLIを、独立したC実装とPythonの整数計算に照合して測れます。
生成Cは公開ビルドの子プロセスで捕捉し、同じオブジェクト・フラグに時計だけを追加します。
独立した公開ビルドと捕捉した基準バイナリのSHAが異なる場合は測定前に停止します。

```sh
python3 -B language_examples/integer_column_stats_profile.py new-report.json --rows 131072 --cycles 8 --repeats 8
```

Linux専用です。出力先には存在しないJSONパスを指定します。各測定点で同じ入力を8回実行し、
毎回の全出力・入力不変・終了値とCPU時間・最大RSS・壁時計を記録します。工程は読込み、
復号、集計、描画とUTF-8符号化、書込みです。起動・パス同一性検査・区間外の解放は別の残余です。
`--repeats 1`もあります。工程割合は観測版の値で、基準版の工程時間を直接測った値ではありません。

R466では12,130,336バイト・131,074行を使い、単発56回と8回集計392回の全出力が
独立計算へ一致しました。出力は`131074<TAB>-1<TAB>-9223372036854775808<TAB>9223372036854775807<LF>`です。
新規検査はWindows/Linux各11対象（C参照4・測定式と拒否境界7）が成功しています。

**速度の価格付けは未校正です。** 8回集計でも同じバイナリ同士の最大比は1.4903、
観測版との最大比はAIL1.3338・C1.1318で、事前に固定した1.10以内の検査を通りませんでした。
CPU時間も増減しています。原因を特定した結果ではありません。
R471では入力を24,260,455バイト・262,146行へ増やし、測定記録はLinuxの一時領域へ保存して
終了後に1回だけコピーしました。392実行の全出力と入力保持は成功し、公開・捕捉バイナリも一致しました。
最大比は同一バイナリ1.2902・AIL観測版1.2774・C観測版1.1903で、同じ1.10基準を通りませんでした。
この実行も未校正で、保存先が揺れの原因だったと特定した結果ではありません。評価全体は約72.04秒でした。
記録は`language_examples/integer_column_stats_price_linux_r471.json`です。高速化候補は作成・採用していません。
R480では同じ12,130,336バイトの入力を現行コンパイラで、事前に32組・各測定点8実行へ固定して測りました。
1,544実行の全出力・入力保持は成功し、公開・捕捉バイナリも一致しました。
同一バイナリの最大比1.3970、AIL観測版1.3810、C観測版1.6947で、1.10以内の検査は不合格です。
評価全体は243.64秒。記録は`language_examples/integer_column_stats_price_linux_r480.json`です。
工程割合・Amdahl上限・参照比は未校正の診断値で、最適化を実装・採用する根拠には使いません。
C参照は異なる内部表現を使う実装で、物理上限ではありません。追加再試行や高速化候補の作成・採用はしていません。
以下はR466の未校正の観測中央値で、最適化を作る理由や採用の根拠にはしていません。

| 工程 | 観測版の壁時計に占める割合 | 工程を消せた場合の条件付きAmdahl上限 | C参照工程時間 / AIL工程時間 |
| --- | ---: | ---: | ---: |
| 読込み | 11.55% | 1.131倍 | 0.994 |
| 復号 | 28.15% | 1.392倍 | 0.377 |
| 集計 | 51.32% | 2.054倍 | 0.517 |
| 描画・符号化 | 0.0042% | 1.00004倍 | 1.326 |
| 書込み | 0.219% | 1.0022倍 | 0.992 |

比較上の仮定はC参照と同じ工程時間（比1.0）です。CはUTF-8を検査してbytesを走査し、
AILはUnicodeを構築するため、表現が異なります。C参照は機械の性能上限ではありません。
全体のC時間/AIL時間の中央値0.462も未校正の比較値で、高速化の採用はしていません。
4試行の測定準備・検証を含む既知の評価時間は合計約84.58秒で、モデルや編集の総費用は含みません。
失敗した準備2件と単発・8回集計の原記録は`language_examples/integer_column_stats_price_linux_r466*.json`に残しています。
独立C参照のWindowsパスはネイティブCRTの文字コードに依存し、AILと同じUnicodeパス保証はありません。
WindowsのC診断時計はミリ秒単位で、性能評価には使いません。全corpus/CI・実arm64/32ビットは未検証です。

## 型付き変数と整数表の集計（R465）

初期値付きのローカル変数に`int`・`float`・`str`・`bytes`・既存の構造体名を宣言できます。
`list[bytes]`も引き続き使えます。

```ail
let total: int = 0;
let scale: float = float(total);
let name: str = "日本語";
let data: bytes = b"\x00\xff";
let parts: list[bytes] = [data];
```

型は関数内で固定し、初期値と後の代入が一致しなければビルドを拒否します。
整数をfloat変数へ渡す場合は`float(value)`と明示します。同じ型の再宣言と、型の合う
ループ変数・拡張代入も使えます。初期値のない宣言は対象外です。
数値・文字列リストのローカル型宣言はR467で追加しています。
関数の文字列・bytes戻り値は従来どおり`fn ... -> str`・`fn ... -> bytes`で明示します。

`checked_integer`は符号付き64ビットの厳密な十進解析と、範囲を超えない加算を提供します。
`IntegerColumnStats`は件数・合計・最小値・最大値を保存し、不正な件数や合計のoverflowで
状態を変更しません。CLIはUTF-8のタブ区切り表から指定列を集計します。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/integer_column_stats_main.ail --object file_identity.o -o integer_column_stats
.\integer_column_stats.exe input.tsv report.tsv 1
```

列番号は0から数えます。出力は`件数<TAB>合計<TAB>最小値<TAB>最大値<LF>`の一行です。
空の入力は4項目とも0です。整数は先頭の`+`・`-`とASCII数字だけを受け付け、空白を許しません。
途中で合計が範囲を超えたら、後の行で相殺されても失敗します。引用符付きCSVではありません。
行区切りは`str.splitlines()`の規則です。空行・列不足・不正な整数・UTF-8は書込み前に拒否します。
出力が入力と同じファイルの場合も拒否します。全入力を読み、書込みの原子性や同時置換は保証しません。
`bytes.decode()`の不正UTF-8は`UnicodeDecodeError`または親の`ValueError`で捕まえられます。
Windows/Linux各25対象（新規12・関連既存13）が成功しました。完全出力、通常・分離ビルド、
ソースを除いた依存objectの移動後2再リンク、型拒否、例外と終了時の解放を検査しています。
公開コマンドもWindowsで実行し、1,470,502バイト・8,198行の表の結果へ全一致しました。
全corpus/CI・実arm64/32ビット・速度向上は未検証です。

## 複数ファイルをレコード列へまとめる（R464）

`BinaryRecordBatch(records)`は`list[bytes]`にレコードを保存する部品です。
`append(kind, payload)`は種類0..65535のレコードを追加します。
`append_record(encoded)`と`extend_records(values)`は完全な単一レコードだけを受け付けます。
extendは全要素を検査してから追加し、後ろの要素が不正でもリストを変更しません。
`snapshot()`は独立したリスト、`clear()`は共有リストの消去、`finish()`は結合したbytesです。
公開フィールドを直接変更した場合もfinishで再検査します。

単一レコードは`AILR`・種類uint16 BE・長さuint32 LE・内容です。
finishは先頭の`AILR`を一度だけ出力し、各レコードの種類・長さ・内容を続けます。
空のbatchは`b"AILR"`です。保存済みの単一レコードにはそれぞれmagicが含まれます。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/binary_records_pack_main.ail --object file_identity.o -o binary_records_pack
.\binary_records_pack.exe records.bin 42 first.bin 65535 second.bin 42 third.bin
python ailc.py language_examples/binary_records_main.ail --object file_identity.o -o binary_records
.\binary_records.exe records.bin selected.bin 42
```

Linuxでは`./binary_records_pack`と`./binary_records`を実行します。
同じ種類・入力の重複、空・NUL・非UTF8の内容を扱い、既存の抽出CLIで選択できます。
出力がどの入力と同じファイルでも拒否します。引数・種類・読込み・レコード検査は
書込み前に行い、異常はstderr・終了2となって既存出力を保ちます。
全入力をメモリへ読みます。書込みの原子性と同時のファイル置換に対する保護は保証しません。
通常・分離ビルドと、現行の依存objectをソースなしで移動した2再リンクを検査しました。
フィールドのbytesリスト反復も使え、反復中のフィールド置換・所有者再代入を扱います。
Windows/Linux各20対象（新規10・関連既存10）が成功し、終了時の割当・bytes・解放frameが
ゼロであることを検査しました。Windowsの既存symlink8ケースは権限不足で未検証です。
上の公開コマンドもWindowsで実行し、packの131,622バイトと抽出結果の131,600バイトを
独立計算へ全一致させています。全corpus/CI・実arm64/32ビット・速度は未検証です。

## リストを持つ構造体とフィールド集約（R463）

構造体フィールドにも`parts: list[bytes];`を宣言できます。
コンストラクタ・フィールド代入はリストを共有し、変更は別名からも見えます。
別のリストへフィールドを置換しても、以前に取得したリストは保持できます。
所有者の変数を再代入したり、関数の終了で解放されたりしても、取得済みのリストは使えます。
要素のbytesも保持します。
リスト自体のコピーが必要なら`parts.copy()`やスライスを使います。
数値・文字列リストや任意の構造体を持つフィールドは対象外です。
リストフィールドを持つ構造体の一覧も使え、整数・浮動小数点・文字列・bytesのフィールドでソートできます。
bytesリストフィールドをソートキーにすることは拒否します。

`BinaryFieldCollection(parts, separator)`はリストと区切りを保存する再利用部品です。
`append(value)`・`extend(values)`・`pop(index)`・`clear()`・`reverse()`・`sort()`でリストを変更し、
`replace`で別のリストを共有します。`snapshot()`は独立したリスト、`join()`は結合したbytesを返します。
`binary_field_collection(data, separator)`は非空の区切りで入力を分割して作ります。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/binary_field_collection_main.ail --object file_identity.o -o binary_field_collection
.\binary_field_collection.exe reverse input.bin reversed.bin separator.bin
.\binary_field_collection.exe sort input.bin sorted.bin separator.bin
```

Linuxでは`./binary_field_collection`で実行します。バイナリ区切り、空のフィールド、NULや
非UTF8の内容を扱います。sortはbytesの辞書順です。引数・空区切り・読込みの異常、
出力が入力または区切りファイルと同じ場合はstderrと終了2になり、書込み前の既存出力を保ちます。
全読込み・全変換で、逐次処理や書込みの原子性、同時にファイルが置換される場合の保護は保証しません。
通常・`--separate`・現行objectからのソースなし再利用ができます。旧objectは再ビルドしてください。
Windows/Linux各29項目（新機能12・関連既存17）が成功しました。完全出力、移動後2再リンク、
構築途中の例外・解放・型拒否を検査しています。上のC連携・ailcコマンドもWindowsで実行し、
反転・ソートとも独立計算の65,800バイトへ一致しました。全corpus/CI・実arm64/32ビットと速度は未検証です。

## バイト列のリストを部品間で渡す（R462）

関数・メソッドの引数と戻り値に`list[bytes]`を使えます。
`let parts: list[bytes] = [];`で空のリストにも型を指定できます。
代入・引数・戻り値は同じリストを共有し、追加・要素変更・clearは別名からも見えます。
`list(parts)`、`parts.copy()`、スライス、`sorted(parts)`は独立したリストを作ります。
要素のbytesは保持され、取り出したbytesは元リストの変更・解放後も使えます。
数値リストの型との混在は拒否します。構造体のbytesリストフィールドは上のR463で使えます。

新しい`binary_fields_codec`は、任意のバイナリ区切りで分割した各フィールドを
Base64の行へ変換し、元のバイト列へ復元します。既存のcount/field/rejoin CLIも残ります。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/binary_fields_codec_main.ail --object file_identity.o -o binary_fields_codec
.\binary_fields_codec.exe encode input.bin encoded.txt separator.bin
.\binary_fields_codec.exe decode encoded.txt restored.bin separator.bin
```

Linuxでは`./binary_fields_codec`で実行します。`separator.bin`に非空の区切りを保存します。
Base64の行間はLFで、末尾へ改行を追加しません。空のフィールドも保持します。
不正な引数・Base64・空区切り・読込み失敗はstderrと終了2になり、既存出力を保ちます。
出力が入力または区切りファイルと同じファイルなら拒否します。全読込みと全変換を行い、
書込み失敗時の原子的保存や、同時にファイルが置換される場合の保護は保証しません。
`--separate`と現行コンパイラで作ったソースなしobjectも使えます。旧objectは再ビルドしてください。
Windows/Linuxそれぞれで、新機能12項目と関連既存23項目が成功しました。
1MiB超の独立した全出力、移動後の2回の再リンク、別名・例外・割当失敗を含みます。
全corpus/CI・実arm64/32ビットは未検証で、速度向上の主張はありません。

## バイナリの書込みとレコード生成（R459）

`language_examples/binary_writer.ail`で、現在のバイト列を持つ`BinaryWriter`を使えます。
`write_u8(value)`、`write_u16_le(value)`、`write_u16_be(value)`、
`write_u32_le(value)`、`write_u32_be(value)`は符号なし整数を追加します。
値域はそれぞれ0..255、0..65535、0..4294967295です。範囲外では`ValueError`を送出し、
既存のデータを保ちます。`append(data)`はbytesを追加し、`clear()`は空にします。
これらは値を返さないメソッドです。`finish()`は現在のbytesを返します。
取得済みの結果は、その後の追加・初期化・変数の再代入後も保持できます。

```ail
use binary_writer;
fn main() -> int {
    let writer = BinaryWriter(b"AIL");
    writer.write_u16_be(258);
    let saved = writer.finish();
    writer.clear();
    write_stdout_bytes(saved);
    return 0;
}
```

出力は`41 49 4C 01 02`の5バイトです。ソースを隣へ置いて`use`するか、
`compile-module`で作ったobjectを`--object`で渡せます。
現在の実装は追加ごとにバイト列を連結します。大量の小さな書込みをまとめる
容量予約や、ファイルへの逐次書込みの機能はありません。

`binary_record_encode(kind, payload)`は、既存の抽出CLIが読める1レコードを返します。
種類は0..65535、payload長は32ビット符号なしの範囲です。
`binary_records_create_main.ail`は入力ファイルをその形式に包む実行例です。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/binary_records_create_main.ail --object file_identity.o -o binary_records_create
python ailc.py language_examples/binary_records_main.ail --object file_identity.o -o binary_records
.\binary_records_create.exe input.bin records.bin 42
.\binary_records.exe records.bin restored.bin 42
```

Linuxでは`python3 -B`と`./実行ファイル名`に替えます。
生成CLIも種類のASCII表記・入力と出力のファイル識別を検査し、
異常は終了2・標準エラー診断・空の標準出力です。書込み前の異常では既存出力を保ちます。
照会後の同時差替えや、書込み失敗時の原子的な復元は保証しません。

今回の5対象はWindowsとLinuxで成功しました。全u8、代表u16/u32とint64端点の拒否、
1MiB超の全バイト出力、生成→抽出、分割ビルド、移動したソースなし部品の2回の再リンク、
301回の例外後再利用と全リンクの解放を確認しています。
Windowsのリンク作成8条件は権限不足で未検証、Linuxでは実行しています。
上のコマンドと5バイトの例もWindowsで実行確認しました。
4GiB超のpayload、全corpus/CI、実arm64/32ビットは未検証です。

## 同じファイルの識別と上書き防止（R458）

`language_examples/file_identity.ail`の`file_paths_same(source_path, destination_path)`は、
既存の入力と出力が同じファイルなら1、別ファイルまたは出力が存在しなければ0を返します。
入力が存在しない、空文字列、NULを含むパス、その他の照会失敗は`OSError`です。
0は出力へ書き込めることを保証しません。ディレクトリにも使えます。

C連携部品はWindowsのファイルID、Linuxのデバイス番号とinodeで識別します。
日本語・絵文字のパス、相対表記、ハードリンク、シンボリックリンクを扱います。
識別は照会時点の結果です。照会後に別プロセスがファイルを差し替えることまでは防ぎません。

Windowsは今回の7対象を修正段階ごとに成功確認しました。権限不足によりリンク作成の
9条件は未検証です。Linuxは最終実装の7対象すべて成功し、リンク条件も実行しました。
移動したソースなしC部品とAIL部品での2回の再リンク、独立参照との全出力一致、
1万回の照会後にC部品の確保が残らず、WindowsハンドルとLinuxファイル記述子が
増えないことを確認しました。OS内部やAILブリッジ全体の確保を測った結果ではありません。
下の2段階のビルドコマンドもWindowsで実行し、独立した259バイトの期待値と
ハードリンクへの上書き拒否を確認しています。

## 整数読込みとバイナリレコード抽出（R457）

`BinaryCursor`で、符号なし8・16・32ビット整数を読めます。
`read_u8()`、`read_u16_le()`、`read_u16_be()`、`read_u32_le()`、`read_u32_be()`は
AILの`int`を返します。`le`は下位バイト先頭、`be`は上位バイト先頭です。
成功時に1・2・4バイト進み、不正な位置や不足した入力では`ValueError`を送出して位置を保ちます。
32ビット最大値`4294967295`まで扱います。64ビット符号なし読込みは提供していません。

`language_examples/binary_records_main.ail`は、指定した種類のペイロードを抽出する実行プログラムです。
ファイル形式は先頭の4バイト`AILR`と、続く0件以上のレコードです。
各レコードは種類（16ビット・be）、長さ（32ビット・le）、その長さのペイロードで構成します。
空のペイロードも許します。選択しなかったレコードも最後まで検査し、全入力が正しい場合だけ
一致したペイロードを順番に結合して出力ファイルへ書きます。

```powershell
python ail_chatgpt.py compile-c language_examples/file_identity.c --interface language_examples/file_identity.json -o file_identity.o
python ailc.py language_examples/binary_records_main.ail --object file_identity.o -o binary_records
.\binary_records.exe input.bin selected.bin 42
```

Linuxでは`./binary_records input.bin selected.bin 42`で実行します。
`--separate`によるソースの分割ビルドと、移動したソースなしカーソル部品からの再リンクも検査します。
種類の引数はASCII数字と任意の先頭符号1個で、空白を含めず、値は0..65535です。
先頭ゼロと`-0`は許し、非常に長い引数も各桁の計算前に範囲を検査します。
異常は標準エラーに診断して終了値2、標準出力は空です。引数・入力・形式の異常では
既存の出力ファイルを書き換えません。書込み自体の失敗では出力が一部変更されることがあります。
入力と出力には別のファイルを指定してください。R458では同一の引数字列に加え、
相対表記やリンクによる同じファイルも書込み前に拒否します。
入力全体を読み、選択したペイロードをまとめて出力します。

Windows・Linuxの各20検査で、新5対象と関連15対象が成功しました。全バイトの出力、
1MiB超の入力、int64端点、切断後の位置保持、添字評価中のフィールド変更、移動後再リンク、
全リンクの例外後解放を含みます。この20検査はR457時点の結果です。
R458の現在のコマンドと別名検査は上の節を参照してください。
名前付きbytesフィールドの添字・境界に呼出しや代入式がない場合は、全体コピーを省きます。
スライスは選択部分を所有コピーにするため、後でフィールドを変更しても保持した値は変わりません。
副作用のある境界や関数で得た受け手には従来のコピーを保ちます。既存objectは再ビルドしてください。

Linuxの固定128KiB入力を整数単位で合計する仕事では、変更前の生成Cを保存して交互に8組測り、
中央値が975.27msから12.34msになりました。全組の短縮が観測したA/A差を上回りました。
これはこの機械・仕事・入力での比較です。工程割合の計測は未校正で、条件付き上限の達成や
全用途の速度、全corpus/CI・実arm64/32ビットの検証を示す結果ではありません。

## 値を返さないメソッド（R456）

状態を変更するメソッドには`-> void`を使えます。呼出しは独立した文にします。
値を代入・表示・計算・条件に使ったり、voidメソッドから値を返したりすることは拒否します。

```ail
struct Counter { value: int; }
impl Counter {
    fn set(self, value: int) -> void { self.value = value; }
    fn reset(self) -> void { self.value = 0; return; }
}
fn main() -> int {
    let counter = Counter(0);
    counter.set(value=3);
    print(counter.value);
    counter.reset();
    print(counter.value);
    return 0;
}
```

通常・複数ソースの`--separate`・ソースなしobjectで使えます。型と引数順序を保ち、
構造体を返す関数やメソッドの連鎖も受け手にできます。メソッドに戻り値注釈がない場合は、
値を返さない実装を引き続き拒否します。例外メッセージの引数は未対応です。
objectのABIは10のままですが、更新後のコンパイラで既存objectを再ビルドしてください。

新6検査と関連既存31検査の37対象を確認しました。Windowsは修正段階で全対象が成功し、
最後の連鎖戻り値修正後もvoidの4検査を成功確認。Linuxは最終実装で37検査すべて成功しました。
上の例もWindowsでそのまま構築・実行し、期待する`3`・`0`を出力しています。
全出力、移動後再リンク、型・メタデータの拒否、例外後の解放、既存C連携を含みます。
全corpus/CI・実arm64/32ビットの検証や、新しい速度改善の採用を示す結果ではありません。

## 構造体のメソッドとバイナリカーソル（R454）

宣言した構造体へ`impl`でインスタンスメソッドを追加できます。先頭の引数は型なしの`self`、
残りの引数は型付きで、呼出しでは位置指定・キーワード指定を使えます。
bytes・strを返すメソッドは、関数内の領域が解放された後も結果を保持します。

```ail
struct Blob { data: bytes; }
impl Blob {
    fn suffix(self, start: int) -> bytes { return self.data[start:]; }
}
fn main() -> int {
    let blob = Blob(b"AIL\x00\xff");
    let saved = blob.suffix(start=3);
    blob.data = b"changed";
    write_stdout_bytes(saved);
    return 0;
}
```

同じ構造体へ複数の`impl`を追加できます。未知の構造体、フィールドと同じメソッド名、
重複メソッド、コンストラクタの置換は拒否します。型付きの戻り値は、通常の関数と同様に、
戻る経路に値が必要です。例外を送出して終わる経路も認めます。
メソッドの呼出し対象にはローカル変数・`self`に加え、対応する構造体を返す関数呼出しや
構築式も使えます。構造体を返すメソッドも、元のオブジェクトの別名を保持します。

`binary_cursor`は現在位置を持つ読込み部品です。

| 操作 | 結果と位置 |
| --- | --- |
| `BinaryCursor(data, 0)` | bytesと初期位置を保持 |
| `cursor.remaining()` | 残りのバイト数 |
| `cursor.peek(count)` | 次のcountバイトを返し、位置を保つ |
| `cursor.take(count)` | 次のcountバイトを返し、位置を進める |
| `cursor.skip(count)` | 位置を進め、新しい位置を返す |
| `cursor.seek(position)` | 絶対位置を指定する。戻り値なし |
| `cursor.reset()` | 位置を0に戻す。戻り値なし |

件数は非負で、残りの長さ以下に限ります。範囲外の件数・壊れた位置は`ValueError`になり、
位置を変更しません。全入力はメモリへ読み込みます。一定のメモリ上限や速度向上の主張はありません。

R456の`seek`は0以上・データ長以下の絶対位置だけを受け入れ、範囲外では元の位置を保持します。
有効な絶対位置への変更と`reset`は、壊れた旧位置も修復できます。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_cursor_main.ail --separate -o binary_cursor
./binary_cursor.exe slice input.bin 8 16
./binary_cursor.exe rejoin input.bin 8 16
```

Linuxでは`python3 -B`と`./binary_cursor`を使います。
sliceは指定範囲、rejoinは先頭から2回取り出した範囲を結合し、生bytesをstdoutへ出します。
入力を変更しません。不正引数・64ビット整数範囲外・読込み失敗は終了2で出力が空です。
書込み失敗も終了2ですが、途中までの出力が残る場合があります。

R455では、メソッドをソースなしobjectから直接呼べます。ABIは10です。
以前のobjectは現行コンパイラで再ビルドしてください。公開関数
`binary_cursor_slice(data, offset, count)`・`binary_cursor_rejoin(data, first, second)`も使えます。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/binary_cursor.ail -o binary_cursor.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_cursor_object_main.ail --object binary_cursor.o -o direct_cursor
./direct_cursor.exe slice input.bin 8 16
```

再利用に必要なのは同じ機械向けの`.o`と隣接する`.o.json`、宣言された依存objectです。
利用側のソースに`use binary_cursor;`は不要です。メソッドの型・呼出し先・所有結果・依存を
照合し、メタデータと実objectの契約が一致しなければリンクを拒否します。
listを返すメソッドのobject公開は未対応です。voidメソッドはR456で対応しました。

R455の新機能9検査と関連既存40検査の49種類がWindows/Linuxで成功しました。
ソース削除・移動後の2回リンク、全バイト・1MiB超の入力とUnicode文字列、構造体の別名、
メタデータ改変18ケース、301回の例外・再試行と部品全体の終了後解放を含みます。

R454では新機能16検査と関連既存76検査の92種類がWindows/Linuxで成功しました。
全256バイト・NUL・非UTF8・1MiB超の全出力、通常/分離ビルド・移動objectの2回再リンク、
位置の破損・int64境界・拒否後の位置保持、Unicode文字列とbytesの保持、301回の例外と再試行、
終了後のlive/bytes/解放frameゼロを含みます。既存の自由関数のバッファ戻り値ABIも検査しました。
上のメソッド例をWindowsでそのまま実行し、期待する`00 FF`の全2バイトと一致しました。
Linuxの初回はWSL起動タイムアウトで検査未開始でしたが、通常の再試行で92検査が成功しました。
全corpus/CI・実arm64/32ビットの確認や、全用途の速度向上を示す結果ではありません。

## バイナリの分割・結合（R453）

`data.split([separator[, maxsplit]])`はbytesを分割し、bytesのローカルリストを返します。
区切りの省略・`None`はASCIIの空白（9～13、32）をまとめて扱い、空の要素を作りません。
bytesの区切りを指定すると、先頭・末尾・連続区切りの空要素を残します。空の区切りは`ValueError`です。
maxsplitはintで、負数なら全件、0なら分割しません。空白分割の0は先頭の空白だけを除きます。

```ail
fn main() -> int {
    let fields = b"|a||b|\x00".split(b"|", 3);
    write_stdout_bytes(b"\x00".join(fields));
    return 0;
}
```

リストの長さ・索引・反復、`separator.join(parts)`で使えます。`b"|".join(data.split())`、
bytes要素のリストリテラル、空の`[]`も使えます。引数は位置指定だけで、任意のiterableは対象外です。
`list(parts)`は要素を保持してリストをコピーし、自己コピーでも内容を失いません。
`separator.join(sorted(parts))`も使え、元の順序を変えずソートした結果を結合します。
ここでの`sorted`は位置指定1引数だけです。短絡した分岐では分割や引数の副作用を実行しません。
bytesリストは`list[bytes]`の引数・戻り値として関数境界を越えられます。
数値リストの型として渡すことは拒否します。各要素は所有したbytesを持ち、
取り出したbytesと結合結果は呼出し側の所有領域へ保持します。
コンテナを使うループのメモリ上限や速度向上は主張しません。

再利用部品`binary_fields`とCLIは、明示した区切りでの個数・要素取得・再結合を扱います。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_fields_main.ail --separate -o binary_fields
./binary_fields.exe count input.bin "00 FF" 3
./binary_fields.exe field input.bin "00 FF" -1 3
./binary_fields.exe rejoin input.bin "00 FF" "0A" 3
```

maxsplitの省略は-1です。countは10進数とLF、field/rejoinは生bytesをstdoutへ出します。
負の要素番号も使えます。不正引数・空区切り・16進形式・64ビット範囲外・要素範囲外・読込み失敗は
終了2で出力が空です。書込み失敗も終了2ですが、途中までの出力が残る場合があります。
入力は全読込みで、元ファイルを変更しません。既存objectは現行コンパイラで再ビルドしてください。

新機能18検査と関連既存27検査の45種類がWindows/Linuxで成功しました。
独立Python参照の586分割ケースで、各要素の長さ・全byteを照合しました。全256バイト、
1,048,832バイトの入力、通常/分離ビルド・移動object再リンク、自己コピー・元の順序保持、
フィールド変更・短絡評価・301回の例外と再試行、終了後のlive/bytes/解放frameゼロを含みます。
生Cでspan・リスト・pool・handle・加算/成長の境界、splitの8箇所とjoinの2箇所の失敗注入を確認しました。
新機能の接続不具合と既存bytesソートのCポインタ参照ミスを修正してから再検査しています。
説明書の上記ソースもそのままWindowsで実行し、Python参照の全7バイトと一致しました。
幅マクロは実32ビットの資格ではありません。全corpus/CI・arm64/32ビットは未確認です。

## バイナリの変換・先頭末尾の除去（R452）

`data.translate(table[, delete])`は元のバイトからdeleteに含まれる値を除き、
残った値を256バイトのtableで変換します。tableの長さが256以外なら`ValueError`です。
`data.removeprefix(prefix)`・`data.removesuffix(suffix)`は一致する先頭・末尾を1回だけ除きます。
空または不一致のprefix/suffixは内容を変えません。引数はbytesの位置指定だけです。

```ail
fn main() -> int {
    let table = [];
    for i in range(256) { table.append(255 - i); }
    let data = b"HEAD\x00\xffTAIL";
    write_stdout_bytes(data.removeprefix(b"HEAD").removesuffix(b"TAIL").translate(bytes(table), b"\x00"));
    return 0;
}
```

receiver・各引数を左から一度ずつ評価し、後のフィールド変更から取得済みの値を保護します。
空以外の結果は変更なしでも新しい所有領域へコピーします。`None`の変換表、str/整数の引数、
キーワードは対象外です。bytesを返すクラスメソッドも引き続き未対応です。

再利用部品`binary_transform`に3関数と、次のCLIがあります。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_transform_main.ail --separate -o binary_transform
./binary_transform.exe removeprefix input.bin "48 45 41 44"
./binary_transform.exe removesuffix input.bin "54 41 49 4C"
./binary_transform.exe translate input.bin TABLE_HEX "00 FF"
```

`TABLE_HEX`には変換表256バイトの16進表現を渡します。CLIは全読込み後に生のbytesをstdoutへ出し、
入力を書き換えません。不正引数・16進形式・表の長さ・読込み失敗は終了2で出力が空です。
書込み失敗は終了2ですが、途中までの出力が残る場合があります。既存objectは再ビルドしてください。
これは言語・標準機能の追加で、速度向上の主張ではありません。

仕様・担当ファイルを先に固定し、6.1 Solの5担当で並列実装した後、主担当が統合して実行しました。
新機能15検査と関連既存25検査の40種類がWindows/Linuxで成功しました。独立Python参照の
784境界結果、全256バイト、1MiB超の全出力、型拒否31ケース、評価順・例外後の再試行・
301回呼出しの解放、安全なループのpeak、登録失敗時の解放、移動objectの再リンクを含みます。
説明書の上記ソースもWindowsでそのままビルドし、期待する1バイトのNUL出力と一致しました。
検査コードの初期メモリ上限違反は、解放対象外のリスト生成をループ内に置いた前提を修正し、
出力・終了時解放・対象ループの上限を再確認しました。幅マクロは実32ビット資格ではありません。
全corpus/CI・arm64/32ビットは未確認です。

## 検索計測の生成コード差を修正（R451）

前回の検索計測では、時計の挿入で2バイト比較の特殊化が失われ、計測版だけが
ループごとに汎用`memcmp`を呼んでいました。固定した2バイトneedleの長さを検査し、
計測側でも同じ定数長の比較を維持するよう修正しました。AIL本体の最適化ではありません。
今回測った原版・計測版と同じSHAの実行ファイルから、両方の直接比較を確認しています。

32MiB・6周期の38実行は全出力・入力保持・工具の同一性を通りました。ただしA/A最大1.144、
計測追加の最大1.191で10%の校正条件を満たさず、`pricing_qualified=false`です。
記述値は複製29.51%、走査24.41%、各実行で合算した割合の中央値53.80%。完全除去を仮定した
Amdahl上限は1.419・1.323・2.165倍です。複製は実測memcpy読書き5.510GB/sの58.13%で、
ハードウェア上限ではありません。仮定する目標達成率は未設定で、最適化の作成・採用はしていません。
全費用8.457秒、build2.356秒、計測と照合5.500秒（照合2.011秒を含む）を生データへ保存しました。

生データは`language_examples/bytes_search_price_linux_r451_32m.json`です。先に指定した64MiBは
工具の32MiB上限で実行前に拒否され、その失敗も`bytes_search_price_linux_r451.json`へ残しています。
解析・生成の境界10検査はWindows/Linuxで成功。R447の生データと未校正判定も保持しています。

## バイナリの置換（R450）

`data.replace(old, replacement[, count])`はbytesをbytesへ置換し、新しいbytesを返します。
一致は重ならない順に置換します。回数を省略するか負数なら全件、0なら内容を変えません。
空のoldは先頭・各バイト間・末尾へ挿入します。countはint、引数は位置指定だけです。

```ail
fn main() -> int {
    let data = b"ababa\x00\xff";
    write_stdout_bytes(data.replace(b"aba", b"\xff\x00", 1));
    return 0;
}
```

receiver・old・replacement・countを左から一度ずつ評価します。後の式がフィールドを変えても
先に取得したバイト列を保持します。文字列・整数パターン、float/Noneの回数、キーワードは対象外です。
空の結果を除き、変更なしでも別の所有領域へコピーします。全読込み・評価順保持のコピー費があり、
一定メモリや速度向上の主張ではありません。bytesを返すクラスメソッドは引き続き未対応です。

再利用部品`binary_replace(data, old, replacement, count)`と、バイナリをstdoutへ出すCLIを追加しました。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_replace_main.ail --separate -o binary_replace
./binary_replace.exe input.bin "00 FF" "FE 00" 2
```

CLIは入力を書き換えません。不正引数・16進形式・回数・読込み失敗は終了2でstdoutが空です。
回数は符号付き10進数で、64ビット範囲外を整数変換前に拒否します。空白・先頭のゼロを扱います。
出力先で書込みエラーが起きた場合も終了2ですが、書込み済みの出力が残ることがあります。
以前のオブジェクトは現行コンパイラで再ビルドしてください。

新機能15検査と関連既存14検査の29種類をWindows/Linuxで確認しました。
Python参照の647境界結果、1MiB超の全出力、全256バイト、64ビット両端、型拒否、
評価順・フィールド変更・例外・301回呼出し・安全なループのpeak、移動部品の再リンクを含みます。
生Cで3幅各360ケースと不正span・出力サイズを照合し、登録時の失敗を注入して解放と再実行も確認しました。
幅の縮小は実32ビットの資格ではありません。全corpus/CI・arm64/32ビットは未確認です。

## バイナリの先頭・末尾判定（R448）

`data.startswith(prefix[, start[, end]])`と`data.endswith(suffix[, start[, end]])`を使えます。
範囲の先頭・末尾が一致すれば1、一致しなければ0です。判定する値はbytes、境界はintです。

```ail
fn main() -> int {
    let data = b"\x89PNG\r\n\x1a\n";
    print(data.startswith(b"\x89PNG"));  # 1
    print(data.endswith(b"\x1a\n"));    # 1
    print(data.startswith(b"PNG", 1, 4)); # 1
    return 0;
}
```

境界の省略・負数・空prefixは下記の検索と同じ範囲規則です。有効な範囲の空prefixは1ですが、
開始が全長を超える範囲や終了が開始より前の範囲は0です。複数prefixのtupleは対象外です。
receiver・prefix・境界を左から一度ずつ評価し、後のフィールド変更や例外から先の値を保護します。
bytes引数の安全なrangeループで、解放用の参照取得を再代入として拒否する不具合も修正しました。

再利用部品`binary_startswith`・`binary_endswith`は4引数で呼べます。既存CLIにも判定モードを追加しました。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_search_main.ail --separate -o binary_search
./binary_search.exe startswith image.png "89 50 4E 47 0D 0A 1A 0A"
./binary_search.exe endswith input.bin "00 FF" 0 65536
```

CLIは全読込みの後に1/0を出力し、入力を書き換えません。不正引数・読込み失敗は終了2です。
既存objectは現行コンパイラで再ビルドしてください。評価順のための複製費があり、速度改善は主張しません。

新機能11検査・公開CLI3検査・既存検索7検査の計21種類をWindows/Linuxで確認しました。
独立Python参照、1020境界ケース、1MiB超の全入力、全256バイト、INT64両端、
型拒否32ケース、順序・短絡・フィールド変更・例外後の解放、安全なループのpeakを含みます。
raw Cの縮小幅検査は実32ビット環境の資格ではありません。全corpus/CI・arm64/32ビットは未確認です。

## 検索の複製費と走査費の計測（R447）

Linuxの`language_examples/bytes_search_profile.py`は、bytes.countの評価順を守る複製と、
検索の走査を分けて計時します。独立したPythonの全出力、scalar Cの走査、実測memcpyを照合します。
計測JSONは新規ファイルだけに保存し、既存結果を上書きしません。

```sh
python3 -B language_examples/bytes_search_profile.py --size 33554432 --cycles 4 --out new_search_price.json
```

R447の32MiB・4周期はウォームアップ込み26実行の全出力と入力保持、ソース・工具の同一性を確認しました。
ただしA/A最大比1.298、計測追加の最大比2.129で校正条件を満たさず、`pricing_qualified=false`です。
記述的な工程割合の中央値は複製18.22%、走査55.23%、各実行で合計してからの中央値は73.29%。各工程を完全に除去できるという仮定の
Amdahl上限は1.223・2.233・3.745倍です。実測memcpyの読書き5.181GB/sに対して、複製の達成率は53.09%。
これはハードウェア上限ではなく、仮定する目標達成率は未設定です。この結果を根拠に最適化は作成・採用していません。
生データは`language_examples/bytes_search_price_linux_r447.json`、解析の境界10検査はWindows/Linuxで成功しました。
起動・読込み・確保・解放を含む全体時間と、計測・照合の費用もJSONに保存します。この固定入力以外へ一般化しません。

## バイナリの範囲検索と件数（R446）

`data.find(needle[, start[, end]])`は最初の位置、`rfind`は最後の位置を返します。
一致がなければ-1です。`count`は重ならない一致の件数を返します。needleはbytes、境界はintです。
開始・終了位置を省略すると0と全長を使い、負数は末尾から数えます。結果は元のdata内の位置です。

```ail
fn main() -> int {
    let data = b"ababa\x00\xff";
    print(data.find(b"aba", 1));       # 2
    print(data.rfind(b"a", 0, 5));    # 4
    print(data.count(b"aba"));        # 1
    return 0;
}
```

開始が全長を超える範囲や終了が開始より前の範囲は一致なしです。
有効な範囲の空needleは、findで開始、rfindで終了、countで範囲の長さ+1になります。
リテラル・関数の戻り値・フィールド・スライス・生成したbytesからも呼べます。
receiver、needle、start、endを左から一度ずつ評価し、後の式がフィールドを変更しても先の値を使います。
文字列・整数needle、None境界、キーワードは対象外です。strの検索機能は変更していません。

`binary_search.ail`の`binary_find`・`binary_rfind`・`binary_count`は
`(data: bytes, needle: bytes, start: int, end: int)`を受ける再利用部品です。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_search_main.ail --separate -o binary_search
./binary_search.exe find input.bin "00 FF"
./binary_search.exe count input.bin "00" 0 65536
```

CLIは任意のバイナリを全読込みして、位置または件数を標準出力へ返します。
不正引数・16進形式・範囲の数値・読込み失敗は終了2で標準出力が空です。入力ファイルを書き換えません。
whole-file保持と、評価順を守るためのbytes複製費があります。速度改善や一定メモリを主張しません。
再利用objectはsidecarと一緒に移動し、以前の部品は現行コンパイラで再ビルドしてください。

新規13検査と既存の例外処理6検査はWindows/Linuxで成功しました。独立Python参照、
全256バイト、符号付き64ビットの境界、1MiB超の入力、通常・分離・移動後の部品再利用を含みます。
短絡を破る既存の`or`変換と、Windows x64 MinGWの例外復帰時の異常終了も修正しました。
bytesを返すクラスメソッドは未対応です。任意のループで一定メモリは保証しません。
全corpus/CI・arm64/32ビットの資格は未確認です。

## バイナリの生成・複製・反復（R444）

`bytes()`は空、`bytes(n)`はnバイトのゼロ列、`bytes(data)`はbytesを独立した領域へ複製します。
`data * n`と`n * data`はbytesの反復です。どちらも式を左から一度だけ評価します。
後で評価する式が元のフィールドを書き換えても、先に読み取ったbytesを使用します。

```ail
fn main() -> int {
    let data = bytes(4) + 2 * b"\xff";
    write_stdout_bytes(bytes(data));
    return 0;
}
```

生成したbytesは変更できません。負の`bytes(n)`は捕捉できる`ValueError`、
0以下の反復回数は空です。空bytesの反復はINT64_MAX回でも空です。
長さや正の反復積が符号付き64ビット・SIZE_MAX・PTRDIFF_MAXに収まらない場合は、
確保前に`bytes too long`で停止します。実際の確保失敗は既存仕様の捕捉できないエラーです。
整数リストからの既存の生成も使えます。任意のiterable・文字列・文字コード指定は対象外です。

`binary_layout.ail`は幅までゼロ埋めする`binary_pad(data, width)`と
`binary_repeat(data, count)`を提供します。padは入力より小さい幅を`ValueError`にします。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_layout_main.ail --separate -o binary_layout
./binary_layout.exe pad input.bin padded.bin 4096
./binary_layout.exe repeat input.bin repeated.bin 3
```

ファイル全体を読み、処理が完了してから出力を開きます。引数・幅の不正や読込み失敗は
終了2で標準出力が空になり、既存出力を保持します。入力と出力を同じファイルにもできます。
OSの書込み途中の失敗を原子的に戻す機能はありません。全入力と結果をメモリに保持します。
再利用objectは`.o.json`と一緒に移動してください。以前の部品は現行コンパイラで再ビルドします。
この追加は言語機能であり、速度改善は主張しません。

## Base64の改善前の計測（R443）

Linuxで現在のエンコーダ、独立したscalar C実装、実測したmemcpy転送目標を比較できます。
出力全体をPythonのBase64参照と照合し、工程割合、Amdahl上限、CPU・最大RSS、
同一実装の時間差、計測挿入の影響、ビルド・検証費をJSONへ保存します。

```sh
python3 -B language_examples/base64_profile.py --size 8388608 --cycles 4 --out /tmp/base64-price.json
```

結果は診断用で、最適化の採用は行いません。`pricing_qualified=false`なら改善の根拠に使えません。
A/Aまたは計測挿入の時間比が対称比で1.10を超える場合、あるいは計測区間が10ms未満の場合に無効とします。
R443の8MiB・4組の2回の実行は全出力が一致しましたが、時間変動により価格付けは未達です。
`base64_price_linux_r443.json`と`base64_price_linux_r443_002.json`に両方の生データを保持しています。
C実装はAILのlist・文字列の寿命管理を含まず、memcpyは実測転送目標で、理論的な機械限界ではありません。

## JSON文書・Base64・URLデータを扱う（R441）

| ライブラリ | 公開API | 戻り値 |
| --- | --- | --- |
| `json_document.ail` | `json_parse_document(text)` | 親番号を持つ`list[JsonValue]` |
| 同上 | `json_compact(text)` | 妥当性を検査し、文字列の外側の空白だけを除いたJSON |
| `base64_codec.ail` | `base64_encode(data)` / `base64_decode(text)` | 標準Base64のstr / 元のbytes |
| `url_codec.ail` | `url_percent_encode(data)` / `url_percent_decode(text)` | パーセント表現のstr / 元のbytes |

JSON文書は文字列・数値・真偽値・null・配列・オブジェクトを扱います。`json_text.ail`も必要です。
`JsonValue`は`kind: int`、`parent: int`、`key: str`、`text: str`を持ち、親を先に並べます。
kindはnull=0、真偽値=1、数値=2、文字列=3、配列=4、オブジェクト=5です。
根のparentは-1、子のparentは一覧内の親番号です。オブジェクトの子だけが復号済みkeyを持ちます。
文字列のtextは復号済みの内容、数値のtextは元の表記です。null/真偽値は元のリテラル、
配列/オブジェクトのtextは空です。重複したキーと出現順を保持します。
数値をint64/floatへ暗黙に丸めません。値が一つだけであること、数値・区切り・終端を検査し、
不正入力は`ValueError`です。孤立サロゲートは文字列ライブラリと同じく拒否します。

Base64は`A-Z a-z 0-9 + /`を使用し、端数には`=`を付けます。復号は正規のpaddingと
未使用ビットが0であることも検査します。空白、URL用の`- _`、padding省略・過剰・途中挿入を拒否します。
URL変換は英数字と`-._~`だけをそのまま残し、他のバイトを大文字の`%HH`にします。
復号ではASCIIの通常文字と大小どちらの`%HH`も受け付け、`+`を空白に変えません。
不完全・不正なescapeや通常文字の非ASCIIは`ValueError`です。復号結果はbytesで、NUL・非UTF-8も保持します。
どちらの変換も空入力を受け付けます。

### ファイル変換CLI

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/data_convert_main.ail --module language_examples/json_text.ail --module language_examples/json_document.ail --module language_examples/base64_codec.ail --module language_examples/url_codec.ail --separate -o data_convert
./data_convert.exe json-compact input.json compact.json
./data_convert.exe base64-encode input.bin encoded.txt
./data_convert.exe base64-decode encoded.txt restored.bin
./data_convert.exe url-encode input.bin escaped.txt
./data_convert.exe url-decode escaped.txt restored.bin
```

`compile-module`と`--object`で各部品を再利用できます。CLIは入力をすべて読んで変換が成功してから
出力を開くので、形式エラーでは既存出力を保持します。ファイル障害・不正UTF-8は終了2です。
全入力・結果をメモリに保持し、書込み途中のOS障害に対する原子的置換は行いません。
これは対応する実用データ形式を増やす機能で、処理速度や任意プログラムの同値性を証明するものではありません。

## 文字と16進データを直接変換する（R440）

```ail
let character = chr(128512);              # 😀
let text = b"\x00\xff".hex();            # "00ff"
let data = bytes.fromhex("00 FF\r\n");   # b"\x00\xff"
print(bytes.fromhex("00ff")[-1]);         # 255
```

`chr`は整数を一つ受け、Unicode scalarの一文字を返します。NUL・BMP外文字にも対応します。
負数、U+10FFFFを超える値、U+D800〜U+DFFFの孤立サロゲートは`ValueError`です。
`ord(chr(value))`や文字列の連結・関数戻り値・構造体フィールドとして使えます。
型・引数数・キーワードはコンパイル時に検査します。同名のユーザー関数・構造体を優先します。

`bytes.hex()`は1バイトを小文字の16進2文字へ変換します。区切り文字の指定は未対応です。
`bytes.fromhex(text)`は大文字・小文字の両方を受け、空文字列は空のbytesになります。
バイト対の間と前後にはASCIIの空白・TAB・LF・CR・VT・FFを許します。
対の途中の空白、奇数桁、NUL、不正文字、Unicodeの空白は`ValueError`です。
キーワード・別の引数型は拒否します。文字・バイナリの型を暗黙に混ぜません。

型付き関数の結果・フィールド・スライスも入力にでき、入力を一度だけ評価します。
生成したbytesを直接添字やスライスで読み取れます。受信値を保持してから添字・境界を評価するので、
その式が元のフィールドを更新しても、読取り対象は保持されます。短絡で実行しない側は変換しません。
JSON文字列ライブラリの文字生成も、現在は`chr`を使用します。

### 16進形式のファイルを読む・書く

`hex_files.ail`の`hex_file_write(path, data)`は16進UTF-8テキストを書いて元のバイト数を返し、
`hex_file_read(path)`は16進テキストをbytesへ戻します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/hex_files_main.ail --module language_examples/hex_files.ail --separate -o hex_files
./hex_files.exe encode input.bin output.hex
./hex_files.exe decode output.hex restored.bin
```

`compile-module`と`--object`でも再利用できます。不正な16進入力は出力ファイルを書き始める前に拒否します。
不正UTF-8はValueErrorで捕捉され、CLIは終了2です。入力・結果はメモリへ保持し、書込み途中のOS障害に対する
原子的な置換は行いません。

安全性を判定できる`range`ループでは、一時bytesを反復ごとに回収します。生きている名前・別名・
スライスを先にコピーして保持します。コンテナへの保持・フィールド代入・未知の呼出しなどがある場合は
従来の寿命管理を使います。任意のループの一定メモリや速度改善を保証する機能ではありません。
今回のcompiler/runtime変更により、以前のobjectは再ビルドしてください。

## CSV・JSON文字列・パスのライブラリ（R439）

次の部品はAILで実装しており、`--module`でソースを読み込むか、`compile-module`で作った部品を再利用できます。

| 部品 | 公開API | 対応範囲 |
| --- | --- | --- |
| `language_examples/csv_table.ail` | `csv_parse(text)` | カンマ区切り、引用符、二重引用符のエスケープ、引用内改行 |
| `language_examples/json_text.ail` | `json_quote(text)` / `json_unquote(token)` | JSON文字列一つの生成・読取り |
| `language_examples/path_posix.ail` | `path_basename` / `path_dirname` / `path_join` / `path_normalize` | OSに依存しない字句的なPOSIXパス操作 |

CSVの戻り値は`list[CsvCell]`で、各セルは`row: int`、`column: int`、`text: str`を持ちます。
行・列は0から始まり、空レコードは省略します。空欄と末尾カンマは保持し、CR・LF・CRLFを
レコード区切りとして扱います。引用符内の改行は元のまま保持します。
引用符は欄の先頭だけで開始でき、閉引用符の後には区切りか入力末尾だけを許します。
不正な引用符や未完の引用欄は`ValueError`です。区切り変更・型変換・ヘッダー解釈は行いません。

`json_quote`は制御文字をエスケープし、それ以外のUnicode scalarを保持します。
`json_unquote`は前後の空白や余分な値を許さず、エスケープしたサロゲート対は一文字へ戻します。
孤立したサロゲート、未完・不正エスケープ、直接書かれた制御文字は`ValueError`です。
JSONオブジェクト・配列・数値全般を読み込むAPIではありません。

パスでは`/`だけが区切りで、`\\`は通常の文字です。空パスの正規化は`.`、先頭のちょうど二つの
スラッシュは保持します。絶対パスを右側へ結合すると左側を置き換えます。
ファイルシステム照会、シンボリックリンク解決、Windowsドライブ処理、アクセス範囲の保証はありません。
NULを含む文字列も字句的データとして扱いますが、OSへ渡せるパスとは限りません。

### CSVファイルからJSONへ変換する

`csv_json.ail`がCSVとJSON文字列の部品を組み合わせます。すべてのセルを文字列として、
JSONの行配列にします。入力はUTF-8で、空レコードは省略します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/csv_json_main.ail --module language_examples/csv_table.ail --module language_examples/json_text.ail --module language_examples/csv_json.ail --separate -o csv_json
./csv_json.exe input.csv
```

引数不足・不正CSV・読込み失敗・不正UTF-8は終了2で標準出力は空です。
bytes.decode()のUnicodeDecodeErrorはValueErrorで捕捉されます。ファイル全体と変換結果をメモリへ保持するため、ストリーム変換ではありません。
ソースなし部品を使う場合はCSV、JSON文字列、連携用の3つの`.o`と`.o.json`を一緒に渡します。
この追加による速度改善は測定していません。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/csv_table.ail -o csv_table.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/json_text.ail -o json_text.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/csv_json.ail --object csv_table.o --object json_text.o -o csv_json.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/csv_json_main.ail --object csv_table.o --object json_text.o --object csv_json.o -o csv_json_object
```

## ファイルのメタデータを調べる（R438）

`file_size(path)`は通常ファイルの論理サイズをバイト単位で返します。
位置引数一つの`str`を渡し、戻り値は符号付き64bit整数です。

```ail
fn main() -> int {
    if len(sys.argv) < 2 { return 2; }
    try { print(file_size(sys.argv[1])); }
    except (OSError, ValueError) { return 2; }
    return 0;
}
```

Unicode・空白を含むパス、型付き関数や構造体フィールドの文字列も渡せます。
パスは一度だけ評価し、短絡で実行しない側は評価しません。
パス中のNULは`ValueError`、存在しないパス・ディレクトリ・特殊ファイル・照会失敗は`OSError`です。
ファイルへのシンボリックリンクは通常のOSの解決に従います。
整数範囲を超えるサイズは停止し、捕捉できる`OverflowError`ではありません。

本文の読取りAPIを呼ばず、照会後のハンドルとパス用メモリを解放します。
結果はその時点のメタデータです。仮想ファイルや変更中のファイルでは、後で読んだ本文の長さと
一致するとは限りません。複数ファイルをまとめて固定したスナップショットにはしません。

[file_manifest.ail](language_examples/file_manifest.ail)は、この標準機能で一覧を作るライブラリです。
[file_manifest_main.ail](language_examples/file_manifest_main.ail)は、パス順にサイズと合計を表示します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/file_manifest_main.ail --module language_examples/file_manifest.ail --separate -o file_manifest
./file_manifest.exe first.bin second.bin
```

元ライブラリソースなしで使う場合も、同じ入口を使えます。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/file_manifest.ail -o file_manifest.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/file_manifest_main.ail --object file_manifest.o -o file_manifest_object
./file_manifest_object.exe first.bin second.bin
```

引数なし・途中の照会失敗は終了2で標準出力は空です。既存の`inventory.ail`は全内容を読んで数える
仕様を保ちます。この追加による速度改善は測定していません。以前のobjectは再ビルドしてください。

## 複数の構造体レコードを扱う（R430〜R437）

同じ構造体型のリストを作り、関数へ渡し、返せます。

```ail
struct Item { name: str; size: int; }
fn empty_items() -> list[Item] { let rows = []; return rows; }
fn total(rows: list[Item]) -> int {
    let out = 0;
    for row in rows { out += row.size; }
    return out;
}
fn main() -> int {
    let rows = empty_items();
    rows.append(Item("first", 7));
    let alias = rows;
    let kept = rows[0];
    alias.clear();
    print(kept.name); print(total(rows));
    return 0;
}
```

出力は`first`、`0`です。リストも共有参照なので、別名からの変更が見えます。
`[Item(...), Item(...)]`、`[]`の後の構造体`append`、`len`、添字の読取り・代入、
`append`、`extend`、`reverse`、キー付き`sort`、`pop()`/`pop(index)`、`clear`、`for row in rows`に対応します。
負の添字は末尾から数え、空・範囲外は`IndexError`です。空リストの真偽値は偽です。
要素を名前へ取り出せば、リストの消去後もそのフィールドを使えます。
反復は開始時のリストを保持し、そのリストへの追加・消去を各回に反映します。

空リストの型は後の`append`、同型リストからの`extend`または戻り値注釈で定まります。リストを返す関数は、
上のように名前へ代入してから返してください。
R432では`rows[i].field`、`make(...).field`、`rows.pop().field`を直接読み書きできます。
`rows[i].size += 1`のような更新も対象を一度だけ評価します。
単純代入は右辺を先に評価し、`+=`などは対象と変更前の値を先に保持します。
右辺が元リストを消去しても、`+=`の対象は更新が終わるまで残ります。
文字列・bytesは変更前の値をコピーするので、右辺が同じフィールドを変更しても影響を受けません。
別の構造体型・数値との混在、リストの入れ子、スライスへの代入・削除、反復器からの複製、内包表記は未対応です。
`use`/`--module`によるソース再利用と`--separate`に対応します。
`list[Item]`を公開引数・戻り値にする`compile-module`にも対応します（R431）。
構造体名・フィールドの順序と型・リストの要素型を内部ABI9の契約に保存します。
型を定義した部品への依存も契約に含め、必要な`.o`と`.o.json`を一緒に渡してください。
C ABIへの構造体リスト公開は未対応です。以前のobjectは現行コンパイラで再ビルドしてください。

[inventory.ail](language_examples/inventory.ail)はこのリストを使うライブラリです。
複数ファイルを順に読み、パス・サイズの一覧と合計を表示します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/inventory_main.ail --separate -o inventory
./inventory.exe first.bin second.bin
```

引数なし・読込み失敗は終了2で、一覧を標準出力へ出しません。
元ライブラリソースなしで使う入口は次のとおりです。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/inventory.ail -o inventory.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/inventory_object_main.ail --object inventory.o -o inventory_object
./inventory_object.exe first.bin second.bin
```

2番目のコマンドには`inventory.ail`は不要です。`.o`と`.o.json`は移動しても再利用できます。
この入口だけでは分割するソース関数がないので、`--separate`は付けません。
各ファイルの全内容を読んで数える実例で、ディレクトリ列挙やメタデータだけの取得ではありません。
出力一致と参照の解放を検査した機能追加です。速度改善を示す測定ではありません。

直接アクセスは通常ビルド・分割ソース・元ソースなしobjectでも使えます。
対象は非空のscalar構造体です。不明フィールドや型の違う代入はコンパイル時に拒否します。
整数の範囲超過は既存仕様どおり処理を停止し、`OverflowError`として捕捉する機能はありません。

R433では`rows.extend(other)`で同じ型の一覧を結合し、`rows.reverse()`でその場で順序を反転できます。
`extend`の引数は名前、型付き関数のリスト結果、同型のリストリテラル（`[]`も可）です。
`rows.extend(rows)`は呼出し時の元の要素数だけを追加します。要素の実体は共有されます。
`append`/`clear`/`extend`/`reverse`/`sort`は単独の文として使い、値を返す関数としては使いません。
これらのメソッドの対象はリストを保持する名前です。

ファイル一覧ライブラリの`inventory_merge(left, right)`は結合後の件数を、
`inventory_reverse(rows)`は反転後の件数を返します。結合後に`right.clear()`しても、
`left`が保持するレコードは残ります。元ソースなしobjectでも同じAPIを使えます。

R434では、構造体のフィールドで安定した並べ替えができます。

```ail
rows.sort(key=lambda item: item.size);
rows.sort(key=lambda item: (item.size, item.name), reverse=True);
rows.sort(key=lambda item: -item.size);
```

キーは一つのフィールド、またはフィールドのタプルです。数値フィールドには単項`-`も使えます。
`int`・`float`・`str`・`bytes`を値として比較し、同じキーの元の順序は降順でも保ちます。
`reverse`は省略、またはリテラル`True`/`False`を指定します。`key`は必須です。
任意の関数・演算をキーとして実行する機能や、キーなしで構造体自体を比較する機能はありません。
小数キーの仕様は、NaNを除く値（無限大は可）です。選んだフィールドにNaNがあれば、
順序を変える前に`ValueError`になります。キーに選ばない小数フィールドのNaNは影響しません。
PythonのNaNを含む並べ替え結果との一致を保証する仕様ではありません。
作業用メモリは要素数に比例し、割当失敗は既存仕様どおり処理を停止します。

`inventory_sort_size(rows, descending)`はサイズ順、`inventory_sort_path(rows)`はパス順に並べ替え、
件数を返します。`descending`は整数で、0が昇順、0以外が降順です。
同サイズのファイルは元の順序を保ちます。元ソースなしobjectでも再利用できます。

R435では、元の順序を残して別の一覧を作れます。

```ail
let copy = list(rows);
let ordered = sorted(rows, key=lambda item: (item.size, item.name));
let descending = sorted(rows, key=lambda item: item.size, reverse=True);
```

一覧の順序・長さは独立します。`copy.clear()`しても`rows`は消えません。
要素そのものは共有する浅いコピーなので、フィールドの変更は両方に見えます。
引数は型が分かる構造体リスト、またはそれを返す関数の結果です。
`list`は位置引数一つ、`sorted`のキー・降順・小数の仕様は上の`sort`と同じです。
入れ子の`list(sorted(...))`、戻り値の引数への受渡し、直接の`len`・反復・真偽値・添字も使えます。
コピーの添字の範囲外は`IndexError`です。失敗した`sorted`は元の一覧の順序と代入先を変えません。
一覧のbufferとソート用bufferが必要です。任意サイズでの一定メモリや割当失敗からの回復は保証しません。
引数なしの既存`list()`は空の数値リストです。構造体リストの型が必要な空一覧は、上の注釈付き関数で作ります。
`list`のキーワード引数は拒否します。

`inventory_copy(rows)`、`inventory_ordered_size(rows, descending)`、`inventory_ordered_path(rows)`は、
件数でなく新しい`list[FileInfo]`を返します。元の一覧を保ったまま別の表示順を作れます。
これらの結果も元ソースなしobjectから再利用できます。

R436では、構造体リストを番号付き・逆順で反復できます。

```ail
for rank, item in enumerate(rows, start=1) { print(rank, item.name); }
for item in reversed(rows) { print(item.name); }
for rank, item in enumerate(sorted(rows, key=lambda item: item.size)) {
    print(rank, item.size);
}
```

`enumerate`の開始番号は省略時0で、位置引数または`start=`で整数を指定します。
元一覧を保持してから開始番号を一度評価します。番号は符号付き64bitで、次の要素の番号が
範囲を超える場合は停止します。最大値の番号で終わる一要素や、その場の`break`は停止しません。
前の要素がすでに出力されている場合もあり、捕捉できる`OverflowError`ではありません。
番号付き反復は、元一覧への追加・消去を各回に反映します。
逆順反復は開始時の末尾添字から進み、途中の追加で増えた末尾へは戻りません。
各回で現在の長さ・要素を読み、消去などで添字が範囲外になったら終わります。
反復中に一覧の名前を別の値へ代入しても、保持した元一覧を使います。
直接の`for`だけに対応し、反復器を値として保持したり、反復器同士を入れ子にしたりする機能は未対応です。

[inventory_ranked_object_main.ail](language_examples/inventory_ranked_object_main.ail)は、
元の入力順を保ちながらサイズの降順で順位を表示し、その後に入力の逆順と合計を表示します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/inventory.ail -o inventory.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/inventory_ranked_object_main.ail --object inventory.o -o inventory_ranked
./inventory_ranked.exe first.bin second.bin
```

同サイズでは元の順序を保ちます。引数なし・途中の読込み失敗は終了2で標準出力は空です。
この機能追加による速度改善は測定していません。

R437では、スライスで一覧の一部を別の一覧へ取り出せます。

```ail
let page = rows[1:3];       # 添字1から、3を含めず取り出す
let tail = rows[-2:];      # 末尾の2件
let backwards = rows[::-1];
let every_other = rows[::2];
for rank, item in enumerate(rows[1:3], start=1) { print(rank, item.name); }
```

開始・終了・刻み幅は省略でき、指定する値は符号付き64bit整数です。
範囲外の境界は一覧の長さへ合わせるので、空・逆転した範囲も空一覧として扱えます。
負の刻み幅では省略した終了位置と明示した`-1`は異なります。
`rows[::-1]`は全件の逆順、`rows[:-1:-1]`は空です。刻み幅0は`ValueError`になります。
元一覧、開始、終了、刻み幅を左から一度ずつ評価し、その後の一覧の長さで範囲を決めます。
境界を計算する関数が要素を追加・消去した場合、その変更は反映されます。

結果の順序・長さは独立し、要素は共有する浅いコピーです。
元の一覧を消去しても取り出した要素は残り、フィールドの変更は両方に見えます。
型付き関数の結果・スライスの結果もさらに切り出せます。
直接の`len`・真偽値・添字・反復・`enumerate`・`reversed`、`list`/`sorted`への受渡しも使えます。
境界式の例外や刻み幅0では代入先の元の値を保ちますが、境界式が行った変更は取り消しません。
コピー用メモリは選んだ要素数に比例し、割当失敗は既存仕様どおり停止します。
スライスへの代入・削除は未対応です。部品は現行コンパイラで再ビルドしてください。

`inventory_slice(rows, start, stop, step)`は、ファイル一覧から指定範囲を取り出すAPIです。
[inventory_page_object_main.ail](language_examples/inventory_page_object_main.ail)はこのAPIを使います。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/inventory.ail -o inventory.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/inventory_page_object_main.ail --object inventory.o -o inventory_page
./inventory_page.exe 1 3 1 first.bin second.bin third.bin
```

開始・終了は0から数え、終了は含みません。選んだ一覧の件数、1からの番号・パス・サイズ、合計を表示します。
引数不足・整数でない引数・刻み幅0・読込み失敗は終了2で、標準出力は空です。
全入力ファイルを読んでから選びます。メタデータだけの取得や速度改善を示す実例ではありません。

## 名前付き構造体と矩形計算

`struct`で名前と型を持つフィールドを定義できます。

```ail
struct Point { x: int; y: float; }
fn identity(p: Point) -> Point { return p; }
fn main() -> int {
    let p = Point(3, 0.5);
    let q = identity(p);
    q.x += 4;
    print(p.x);
    return 0;
}
```

結果は`7`です。構造体は共有参照なので、`q = p`や関数から同じ値を返す場合、
フィールドの更新は両方から見えます。Cの構造体の値コピーとは異なります。
現在のフィールド型は`int`（符号付き64bit）、`float`（binary64）、`str`、`bytes`です。
宣言順の位置引数で構築し、引数は左から一度ずつ評価します。
整数フィールドへの小数の暗黙切捨て、型違いの引数・戻り値、未定義フィールドを拒否します。
`.x = ...`と`.x += ...`等の数値演算が使え、複合代入は元の値を右辺より先に読みます。
構造体名の引数・戻り値注釈は実際の型と照合します。
フィールドにコンテナや構造体を持つ宣言、空の構造体、メソッド定義はこの構文では未対応です。
構造体自体への数値変換・演算・添字への使用、構造体を選ぶ三項式も拒否します。
計算には数値フィールドを取り出し、値の選択には`if`/`else`の文を使います。

[geometry.ail](language_examples/geometry.ail)と[rectangle_main.ail](language_examples/rectangle_main.ail)は、
二つの矩形の面積・交差面積・和集合面積を求めるCLIです。
`use geometry;`で別ファイルの構造体と型付き関数を再利用します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/rectangle_main.ail --separate -o rectangle
./rectangle.exe 0 0 3 4 1 2 6 6
```

出力は順に`12`、`20`、`4`、`28`です。Linuxでは`python3 -B`でビルドし、`./rectangle`を実行します。
座標は±1,000,000,000で、`x0 <= x1`かつ`y0 <= y1`が必要です。
面積は最大4×10^18、和集合は最大8×10^18となりint64内です。
不正な引数は終了コード2となり、結果を標準出力へ出しません。
型自体は座標を制限しないため、この範囲検査には`make`を使います。

通常ビルド・`--separate`の両方に対応します。
`compile-module`で構造体と型付き関数を`.o`へ公開できます。
`.o`と`.o.json`を一緒に保存し、呼出し側へ`--object`で渡せば元ソースなしで再利用できます。
構造体は名前で型を区別し、フィールド名・型・順序を契約に含めます。
同じ名前の型を複数の部品から公開することはできません。
依存する部品もすべて`--object`で渡してください。構造体のC ABI公開は未対応です。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/geometry.ail -o geometry.o
py -3 -X utf8 -B ail_chatgpt.py compile rectangle_object.ail --object geometry.o -o rectangle_object
```

`rectangle_object.ail`には、たとえば次を記述します。
`--object`で型と関数を読み込むので、このソースに`use geometry;`は不要です。

```ail
fn main() -> int {
    let a = make(0, 0, 3, 4);
    let b = make(1, 2, 6, 6);
    print(area(a)); print(area(b)); print(intersection(a, b));
    return 0;
}
```

出力は`12`、`20`、`4`です。元ソースを取り除いて移動したgeometry部品でも、
独立したPythonの矩形計算と境界入力・乱数200組・不正入力を照合します。
構造体は参照を数えて解放します。別名・関数引数・戻り値が同じ値を保持している間は
領域を保ち、最後の参照がなくなったら解放します。同じ型の引数の再代入と自己代入にも対応します。
ローカル・式の一時参照は通常終了と例外による関数終了で解放し、構築途中の例外でも領域を解放します。
一時参照は次の評価または関数終了まで残る場合があるため、常に即時解放する保証ではありません。
固定個数の参照を使う検査では1/16/10,000反復の終了時割当がゼロで、10,000反復の最大割当は
16反復と同じ範囲でした。再帰の深さや参照の数が増える処理まで一定メモリとする保証はありません。
Python風構文の固定形classも、これら4型のフィールドなら同じ参照管理を使います。

### 文字列・バイナリを持つ再利用部品

```ail
struct Artifact { label: str; data: bytes; revision: int; }
```

文字列とbytesは構築・フィールド代入時に部品自身の領域へコピーします。
読み出した値も呼出し側が保持するため、`let saved = item.label;`の後にフィールドを
更新したり`item`を再代入したりしても`saved`は変わりません。
文字列とbytesの混用を拒否し、自己代入・`+=`にも対応します。
所有するフィールドは最後の構造体参照の解放時に解放します。
読み出したコピーは呼出し側の関数領域を使うため、任意の長いループで即時回収・一定メモリを保証しません。

[artifact.ail](language_examples/artifact.ail)は文字列の名前・任意のbytes・非負のrevisionを持つ部品です。
[artifact_main.ail](language_examples/artifact_main.ail)はその部品を使ってバイナリファイルをコピーし、
名前・revision・byte数を表示します。入力をUTF-8として解釈しません。
revisionは前後の空白を除いたASCII十進数字で、0〜9223372036854775807です。
先頭のゼロは許します。符号・空文字・範囲外は書込み前に終了コード2で拒否します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/artifact.ail -o artifact.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/artifact_main.ail --object artifact.o -o artifact
./artifact.exe input.bin output.bin "日本語😀" 7
```

構造体だけを定義した部品も公開できます。空payloadと全256種のbyteを含む入力、
65KiBを超える入力、元ソースなしの移動後実行、不正revisionと入力失敗を検査します。
出力書込みのatomic/durable保証はありません。メモリ不足は回復可能な例外ではなく終了となります。

再検証は`py -3 -X utf8 -B -m unittest -v test_ail_numeric_struct test_ail_geometry test_ail_struct_lifetimes test_ail_struct_objects test_ail_struct_object_resources test_ail_text_structs test_ail_text_struct_resources`です。
独立したPythonの矩形計算と200組の入力を全出力で照合し、整数端・混在フィールド・
評価順・返却された別名・不正入力も確認します。速度改善の測定ではありません。
コンパイラの実装識別が変わるので、既存の型付きobjectは現行ソースで再生成してください。
R425のアクセスログ速度結果は保存済み実行物と当時のコンパイラに限定されます。
当時のソースhashを要求する比較・移動後検査は、今回のコンパイラ変更との混用を拒否します。

## アクセスログの集計CLI

リクエスト数・転送量・HTTPステータス別の件数を出す[アクセスログ集計](language_examples/access_log/README.md)を追加しました。URLの先頭で絞り込め、UTF-8ファイルを1行ずつ処理します。不正行・数値上限・読込み失敗を扱い、全出力を独立したPython参照と比較します。対応するログ形式と実測の範囲は実例の説明書にあります。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/access_log/main.ail -o access_log
./access_log.exe access.log /api/
```

ファイルの全量読込みと行反復では、不正UTF-8を`except UnicodeDecodeError`で捕捉できるようになりました。UTF-8変換の失敗時も全量読込みの一時バッファと反復用ファイルを解放します。標準入力やbytesのdecodeにはこの追加の捕捉規則を適用していません。例外の属性やPythonの例外オブジェクトを返す機能ではありません。

このCLIの長負荷では、読んだ行の保持を解消してLinuxのピークRSS中央値を149,172→640KiBへ減らしました。独立参照と同じ全出力、24組と前後A/A、固定16MiB上限を確認し、メモリ上限回復として採用しています。速度確認は未成立です。ビルド済みWindows/Linux実行物・小さい入力と実測範囲は実例の説明書にあります。

整数・浮動小数点のリストを返す関数を単独の文として呼び出し、結果を捨てることもできます。既存の所有一時領域を使い、再呼出しや例外後も適切に解放します。

## binary64の数値レコード列

`binary_float_records.ail`とC実装を使い、最大8,192件の数値をLE/BEのbytesへ変換し、大きなファイルの指定レコード範囲を読み取れます。方向は0がLE、1がBEです。8192件/65536bytesを超える変換・不完全なレコード・負の位置・末尾インデックスの上限超過は拒否します。非NaN値は符号付きゼロを含めbit一致、NaNはクラス一致だけを保証し、符号・payloadは保証しません。

公開`compile-c`で`binary_ranges.c/json`と`binary_float_records.c/json`を構築し、それぞれのAIL wrapperを`compile-module`で構築します。`binary_float_records_main.ail`へ4個のobjectを`--object`で渡すと、入力path・出力path・最初のrecord・件数・出力方向を受け取る変換CLIになります。入力はLEです。不正引数・短い入力・入力読込み失敗では既存の出力を保ちます。成功時の書込みはatomic/durableを保証しません。

再検証: `py -3 -X utf8 -B -m unittest test_binary_float_records -v`。独立したPython structの期待値、最大件数、NaN/subnormal/inf、所有コピー、4objectsの元ソースなし再利用・移動後実行、大きいファイルの位置指定を確認します。速度・省メモリの改善結果ではありません。

検証結果と数値プロファイルは[binary_float_records_r414.json](language_examples/binary_float_records_r414.json)に保存しています。

## AILのブロック構文

AILのブロック構文では、Python風のインデントの代わりに `fn`、`const`、`let`、
波括弧とセミコロンを使えます。`struct`で数値フィールドを持つ型も宣言できます。
入口は引数なしの `fn main()` です。

```powershell
py -3 -B ailc.py language_examples/block_use_math.ail -o block_main
./block_main.exe
```

結果は `21` です。ソース内の `use block_math;` が同じフォルダの
`block_math.ail` を読み、定数と関数を一緒にコンパイルします。
`fn sum_to(n: int) -> int` の引数・戻り値注釈はバックエンドの型推論でも検査します。
関数呼出しの数値・文字列引数は記述順に評価し、名前付き引数でも記述順を守ります。
数値の二項演算と文字列・bytesの連結・比較は左から評価し、連鎖比較では中間項を一度だけ評価します。
平坦な整数配列・小数配列の `values = [式1, 式2]` は各要素を左から一度ずつ評価し、すべて成功してから
代入先を置き換えます。`values = [values[-1], values[0]]` では代入前の要素を読めます。
`let weights = [0.25, 0.5, 0.25];` のように小数配列を直接初期化できます。
要素はすべて小数式に揃えます。整数と小数を混ぜる場合は、整数側に明示的な `float(...)` が必要です。
要素の評価中に例外が起きると代入は行われません。ただし、右辺で既に実行した `pop()` や
C関数の副作用まで取り消すものではありません。コンパイラの実装識別が変わるため、既存の `.o` は再生成してください。
文字列・bytesのスライスでは受け手、下限、上限を、添字では受け手、添字を順に評価します。
引数か戻り値の注釈があるAILソースは型付き経路でビルドできる場合だけ受理します。
矛盾した注釈を汎用経路で無視して実行することはありません。
値を返す型の注釈付き関数では、`try` 本体と各 `except`、または `else` と各 `except` が
戻り値を返す経路も検査します。値を返さずに正常終了できる経路は拒否します。
戻り値は `-> int`、`-> float`、`-> str`、`-> bytes`、`-> list` を指定でき、型推論と一致し、すべての経路で
値を返す場合だけ受理します。`main` の注釈は `-> int` のみです。`-> str` は補助関数の
文字列を一度の呼び出しで渡し、代入・表示・連結・別関数への引数に利用できます。
`language_examples/block_use_text.ail` と `block_text.ail` が複数ソースの実例です。
値を返さない関数は `fn notify(n: int) -> void { print(n); }` と書けます。
`return;` による早期終了と、末尾まで実行して終了する形に対応します。`return 値;` は拒否します。
呼出しは文として使い、代入・表示・計算・条件式・配列の値には使えません。`main` は引き続き整数を返します。
`void` 関数は `compile-module` でも公開でき、元ソースがなくても別のAILソースから呼べます。
`py -3 -B ailc.py language_examples/block_use_text.ail -o block_use_text` でビルドします。
現在の既定ランタイムは内部でUTF-16単位を使います。ソース中のBMP外の文字についても、
`len`・添字・スライス・比較・反復ではUnicodeの文字単位へ変換します。
標準入力と `open(path).read()` のUTF-8でも、BMP外文字を同じ文字単位で扱います。
`.strip(chars)`・`.lstrip(chars)`・`.rstrip(chars)` はBMP外文字を1文字として照合します。
`use` はトップレベルに書きます。参照先はそのファイルの隣、`-I` の順、同梱標準部品から探します。
参照先からさらに `use` でき、同じファイルは一度だけ取り込みます。循環、欠落、
同名定義はビルド前に拒否します。通常ビルドはソース結合です。
型付き経路でビルドできるプログラムは `--separate` を付けると、補助ソースの関数と
入口ソースの関数を別々のCオブジェクトへコンパイルしてからリンクできます。

```powershell
py -3 -B ailc.py language_examples/number_lines.ail --separate -o number_lines_linked
./number_lines_linked.exe .\input.txt .\numbered.txt
```

コンパイラはビルド時に全ソースをまとめて型解析します。中間オブジェクトは一時フォルダに
置きます。別ビルドで再利用する場合は後述の `compile-module` を使います。補助ソース内の入れ子関数と、型付き経路が
受理しない機能は拒否します。通常のビルドは従来の単一Cファイル方式です。
両方式の出力を独立参照と照合して実測するには、Linuxで
`python3 -B language_examples/bench_link_units.py --rows 200000 --cycles 6` を実行します。
先頭の `fn`、`const` または `use` 宣言でこの構文を選びます。必要なら `--syntax ail` または
`--syntax python` で明示的に固定できます。補助ファイルも個別に判定されます。
標準入力、条件分岐、ループを使う例は `language_examples/block_stdin.ail` です。
複数行をEOFまで読む `language_examples/block_line_stats.ail` は、件数と合計を出力します。
空入力、CRLF、改行なし、20,000行、符号付き64ビット両端を独立したPython参照と照合済みです。
不正な整数行を飛ばして集計を続ける例は `language_examples/recovering_line_stats.ail` です。

```powershell
py -3 -B ailc.py language_examples/recovering_line_stats.ail -o recovering_line_stats
"7", "bad", "-3", "0" | ./recovering_line_stats.exe
```

出力は有効行数 `3`、不正行数 `1`、合計 `4` の3行です。解析用の補助関数が投げる
`ValueError` を捕捉します。整数と途中の合計は符号付き64ビットの範囲を使います。
不正UTF-8や整数合計のオーバーフローまで読み飛ばすものではありません。
文字列を外へ保存しないと確認できるローカルの数値返却関数は、呼出しを含むループでも
不要になった文字列領域を反復ごとに回収できます。再帰・多段呼出しも同じ条件で解析します。
外部オブジェクトの関数や、可変の引数・不明な呼出しがある場合はこの回収を追加しません。
上記の形で40万行・110万バイトを処理した検査では、追跡した動的確保のピークは
13,566,352バイトから565バイトになりました。静的領域・C標準入出力・プロセス全体のRSSを
含む値ではなく、速度改善の測定でもありません。長い行や保持する文字列が大きければ必要領域は増えます。

`language_examples/filter_errors.ail` は `use filter_rules;` で文字列判定関数を取り込み、
補助ファイルの `const ERROR_PREFIX = "ERR:";` を共有します。
UTF-8入力から `ERR:` で始まる行を出力します。WindowsではCRLFと単独CRをLFに
正規化してから処理し、出力はOSのテキスト改行になります。64KiB境界をまたぐCRLF、
NUL、Ctrl-Z、改行なしも独立したPython参照と生バイトで照合済みです。
既定の型付き文字列はU+10FFFFまで受け入れ、不正UTF-8は停止します。
`main` の戻り値はプロセスの終了値になります。

`language_examples/codepoint_checksum.ail` は `use codepoint_checksum_core;` で
別ソースの関数を取り込み、`sys.argv[1]` で指定したUTF-8ファイルの文字数と
文字単位のチェック値を表示します。次のようにビルドして実行します。

```powershell
py -3 -B ailc.py language_examples/codepoint_checksum.ail -o codepoint_checksum
./codepoint_checksum.exe .\input.txt
```

`open(path).read()` は宣言済みの仕様どおり改行を変換しません。`CRLF` は2文字、
単独の`CR`は1文字として数えます。Windowsでも日本語や絵文字を含む引数のパスを
UTF-8へ正しく変換してからファイルを開きます。
ファイル全体がASCIIなら、そのバイト列を文字列の保存領域として使います。
ASCII以外を含むUTF-8ファイルは検証・復号し、同じ文字単位で扱います。
引数不足や読み込み失敗は標準エラー出力に表示し、終了値をそれぞれ2、3にします。
`print(..., file=sys.stderr)` と `file=sys.stdout` に対応します。任意のファイル値は未対応です。
`print` の引数と `sep`・`end` は記述順に評価し、すべて成功してから出力します。

`language_examples/line_histogram.ail` は別ソースの `line_histogram_core.ail` を読み、
UTF-8ファイルの各行を文字列キーの辞書で数えます。最初に現れた順に
「行、タブ、回数」を表示します。空行もキーとして扱います。
`for line in content.splitlines()` は元の文字列を一度だけ評価し、行を順に取り出します。
中間の行リストは作りません。`let lines = content.splitlines();` のようにリストを
変数へ保存する場合は、従来どおり全行のリストを作ります。

`language_examples/number_lines.ail` は `number_lines_core.ail` の関数で行番号を付け、
`write_text(path, text);` でUTF-8ファイルへ保存します。既存ファイルは上書きし、
改行は変換しません。引数を左から評価してからファイルを開き、読書き失敗は
`except OSError` で捕捉できます。`write_text` は文として使い、戻り値はありません。

```powershell
py -3 -X utf8 -B ailc.py language_examples/number_lines.ail -o number_lines
./number_lines.exe .\input.txt .\numbered.txt
```

出力ファイルも独立Python参照と照合して処理時間を測るには、
`python3 -B language_examples/bench_number_lines.py --rows 200000 --keys 1000 --cycles 6`
を実行します。入力・出力・実行ファイルは一時フォルダに作成して終了時に消します。

```powershell
py -3 -B ailc.py language_examples/line_histogram.ail -o line_histogram
./line_histogram.exe .\input.txt
```

この用途の出力一致と処理時間を再測定するには、
`py -3 -X utf8 -B language_examples/bench_line_histogram.py --rows 2000000 --keys 1000 --cycles 3`
を実行します。入力と実行ファイルは一時フォルダに作成し、終了時に消します。
Python参照と stdout・stderr・終了値を一致させてから、実行順を交替して計測します。
手書きC比較版も含みますが、Cが扱う入力は LF 区切りのUTF-8バイト列に限定します。
AILとPythonはCRLFやUnicode行区切りでも照合し、Cは比較対象の入力だけを照合します。
計測値は起動・ファイル読込みを含み、処理段階ごとの測定は含みません。
段階の概算には同じコマンドに `--phase` を加えます。読込み、行分割、辞書集計、
表示を別々のAILプログラムとの差から見積もるため、厳密な関数別プロファイルではありません。
AIL同士の測定揺れ以下の差は最適化根拠に使いません。
大きい入力をASCII行だけにする場合は `--ascii-only` を加えます。
変更前のLinux実行ファイルがある場合は `--baseline /path/to/baseline` を加えます。
両方を同じ一時フォルダに置き、境界入力と全量入力の出力をPython参照と照合してから、
交互に実行して時間比を出します。
Linuxでは `python3 -B language_examples/profile_line_histogram.py --rows 2000000 --keys 1000 --cycles 6`
で、ビルド時に一時生成したCへ計時を挿入し、パスを開く処理・読込み等・
バッファ拡張・UTF-8復号を測れます。読込み等には最初の領域確保と閉じる処理も含みます。
ASCIIだけの入力は `--ascii-only` で測れます。この場合の `decode` はASCII確認を含む
文字列化経路の時間で、UTF-8復号そのものの時間ではありません。
同じソースで行リストを明示的に作る比較版も一時ビルドし、最大RSSを測ります。
通常版・計時版・比較版は7入力で独立Python参照と出力を照合します。
計時の挿入自体が実行時間へ影響し得るため、通常版との全体時間も一緒に確認します。
現在の直接反復では行リスト作成関数を呼ばないため、この計時版に行分割の個別時間はありません。

現在のブロック構文は `fn`、トップレベルの数値・文字列 `const`、関数内の `let`・代入・呼出し・
`return`・`raise`・`if`/`elif`/`else`・`while`・`for`・`try`/`except`/`finally` に対応します。
`except ZeroDivisionError` のように名前を指定し、`except (ValueError, ZeroDivisionError)` で
複数の種類をまとめて捕捉できます。`try` の後の `else` は例外がなかった場合だけ実行します。
捕捉できる名前は `ValueError`、`ZeroDivisionError`、`IndexError`、`KeyError`、
`EOFError`、`OSError`、`FileNotFoundError`、`RuntimeError` です。
`OSError` と `FileNotFoundError` は同じ内部区分です。
`raise ValueError();` のように明示的に
発生させることもできます。
例外の値・メッセージ、`except ... as` は未対応です。finallyの現在の制限は冒頭にあります。
関数内では `let counts = {1: 7, 2: 11};` の辞書や `let seen = {3, 4};` の集合を
ブロックの波括弧と区別して書けます。`if 1 in {1: 2} { ... }` のような条件も使えます。
注釈なしの経路では入れ子辞書と集合リテラルを実行照合済みです。`-> int` などの注釈を
付けた厳格経路では単純な数値辞書と、整数・文字列・bytesの各単一キー種の集合リテラルを
実行照合済みです。異なるキー種の混在、浮動小数点や入れ子コンテナの集合要素は拒否します。
整数キー・整数値の二段辞書 `let d = {1: {2: 3}};` は `d[1][2]` の読書き、
`len(d[1])`、`2 in d[1]` に対応します。`let h = d[1]; let alias = h;` で
内側辞書を共有でき、`alias[2] = 4;` は `d[1][2]` に反映されます。`d[4] = h;` で
別の外側キーにも同じ内側辞書を格納できます。外側辞書を作り直しても、変数 `h` が
指す内側辞書は関数から戻るまで使えます。`for k in h`、`for k in d[1]`、
`for k in h.keys()`、`for v in h.values()`、`for k, v in h.items()` は挿入順で
反復します。反復中に内側辞書の要素数を変えると `RuntimeError` が発生し、
`except RuntimeError` で捕捉できます。二段の複合代入、
内側辞書の反復以外のメソッド、外側辞書そのものの別名代入は未対応として拒否します。
内側辞書の保存領域は関数から戻る際に解放します。長いループで何度も作り直す用途では、
関数が戻るまで古い内側辞書の領域も保持します。
式の意味は既存のAILに従い、
論理演算は `and`/`or`/`not` を使います。Cの `&&`、`||`、`!` は誤解を避けるため拒否します。
コメントは `#`、整数の切り捨て除算は `//` です。構文変換後に既存のAILバックエンドで
コンパイルする段階なので、コンパイラ自身はまだPythonとCコンパイラを必要とします。

数値行集計の出力一致と実行時間を再測定するには、次を実行します。

```powershell
py -3 -B language_examples/bench_line_stats.py --rows 1000000 --cycles 2 --phase-count
```

AIL・Python・手書きCの出力を先に照合し、全順序を交替して12巡測ります。C比較版は
62バイト以下のASCII十進行だけを対象とします。結果は入力と環境に限定した記述値で、
この測定だけで最速候補や最適化を採用しません。
`--phase-count` は整数変換と加算を外したAIL版も同じ入力で照合し、
全処理との差からその部分の時間比率とAmdahl上限を概算します。
別の実行ファイル同士の比較なので、関数単位のプロファイルではありません。
同時に `while` と `for line in sys.stdin` の件数版・集計版を比較します。
計測の揺れを超える改善が確認できるまでは、元の集計版を基準にしてください。

### 行番号付けの測定

行番号付けの工程診断はLinuxで次を使います。

```bash
python3 -B language_examples/profile_number_lines.py --rows 2000000 --cycles 6 --sample-every 1024 --ascii-only
python3 -B language_examples/bench_ascii_copy_write.py --rows 2000000 --cycles 6
python3 -B language_examples/bench_owned_return.py --rows 2000000 --cycles 24 --ascii-only
```

1本目は計測あり/なし両版を独立Python出力と照合し、工程時間とA/Aを記録します。
2本目は同一出力の単純コピー/書込みの実測参照で、ハードウェアの上限ではありません。
3本目は固定した現行runtimeから旧処理とASCII幅保持候補を一時生成します。既定runtimeは変更しません。
2026-10-01は候補の対比中央値1.4462でしたが、旧版A/A最大1.4947を超えず保留です。
計測版のコピー/書込み割合40.27%からの除去上限1.674倍、実測参照まで縮める見積り1.383倍は
条件付きの概算です。任意入力の速度や最高効率を保証しません。
詳しい数値・生データ・費用とhash検査の範囲は `README_AUTO_ENTRY_JA.md` に記載しています。
現行ツールはAIL入口・module・runtime・codegenの開始時hashを固定し、終了時の不一致を拒否します。
runtimeが固定版と異なると候補比較は停止します。未知の版のhashへ無条件に差し替えないでください。

## 従来のPython風構文

```powershell
py -3 -B ailc.py language_examples/hello.ail -o hello
./hello.exe
```

Linuxでは `python3 -B ailc.py language_examples/hello.ail -o hello`、
実行は `./hello` です。実行結果は `42` です。ビルド時にPythonとCコンパイラが必要です。
関数とループを使う例は `language_examples/sum.ail` にあり、実行結果は `21` です。
補助関数を別ファイルに分ける場合は、次のように明示します。

```powershell
py -3 -B ailc.py language_examples/use_math.ail --module language_examples/math.ail -o use_math
./use_math.exe
```

結果は `21` です。`math.ail` の定数 `LIMIT` と関数 `sum_to` を使っています。
補助ファイルには関数定義と数値・文字列リテラルの定数を書けます。
数値のリスト・タプルも可ですが、文字列の配列は定数として未対応です。
同名の定義や実行時に計算するトップレベルの代入は拒否します。
コンパイラは補助ソースと入口ソースを一緒に解析します。`--separate` なら関数を
別々のCオブジェクトへコンパイルしてリンクします。再利用できるオブジェクトの作成は
次の別コマンドを使います。

## コンパイル済みモジュールの再利用

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/block_text.ail -o block_text.o
py -3 -B ailc.py language_examples/object_text_main.ail --object block_text.o -o object_text
./object_text.exe
```

結果は `item:7` です。Linuxでは `py -3` を `python3`、実行名を `./object_text` に替えます。
最初のコマンドで機械語の `block_text.o` と型情報の `block_text.o.json` を生成します。
この2ファイルを一緒に移動すれば、モジュールの元ソースがなくても別の入口へリンクできます。
入口に `use block_text;` は書かず、`--object` で既存オブジェクトを指定します。
複数のオブジェクトは `--object` を繰り返して渡します。既存の出力は上書きしません。

コンパイル済みモジュールから別のモジュールを呼ぶこともできます。上で作った
`block_text.o` の `label` を使うライブラリと、その入口を次のように構築します。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/object_report.ail --object block_text.o -o object_report.o
py -3 -B ailc.py language_examples/object_report_main.ail --object object_report.o --object block_text.o -o object_report
./object_report.exe
```

結果は `[item:7]` です。モジュールのコンパイルには直接呼び出す依存オブジェクトを渡します。
入口をリンクするときには、間接的に必要なものも含め、すべての `.o` と隣の `.o.json` を用意します。
依存は保存先のパスによらない型契約とオブジェクトのhashで記録するので、一式を移動できます。
不足・別契約への差し替え・内容変更・公開名の衝突・依存関数名の再束縛は拒否します。
現在の契約形式はversion 8です。以前のオブジェクトは元ソースから再生成してください。
依存モジュールの内容を変えた場合は、それを使うモジュールも
元ソースから再生成してください。

不正な整数行を捕捉して集計を続ける例も、解析関数を一度コンパイルして再利用できます。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/object_integer_parser.ail -o integer_parser.o
py -3 -B ailc.py language_examples/recovering_line_stats_main.ail --object integer_parser.o -o recovering_stats
"7", "bad", "-3", "0" | ./recovering_stats.exe
```

出力は有効件数 `3`、不正件数 `1`、合計 `4` の3行です。型情報には、コンパイラが本体を調べて
入力文字列を外へ保持しないと確認した数値返却関数の集合も記録します。利用側はこの情報を使い、
入力ループの不要な文字列領域を回収します。確認済み関数を呼ぶ別モジュールにも引き継げます。
この情報は機械語の契約識別子と依存hashに結び付け、JSONだけの追加・削除はリンク時に拒否します。
`compile-c` の関数にはこの確認を自動付与しません。任意の外部オブジェクトの安全性を保証する仕組みではありません。
二段階のライブラリを移動し、元ソースなしで40万行を処理する検査では、全出力がPython参照と一致し、
追跡対象の動的確保ピークは256 KiB未満、既知の文字列キャッシュを解放した後の残留は0でした。
静的バッファ・libc内部・RSSを含む値や、速度改善の測定ではありません。

`int`・有限の `float`・`str` のリテラル定数も公開できます。定数だけのモジュールも使えます。
次の例は、設定定数、判定関数、標準入力を読む入口を別々にコンパイルします。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/object_filter_config.ail -o object_filter_config.o
py -3 -B ail_chatgpt.py compile-module language_examples/object_filter_rules.ail --object object_filter_config.o -o object_filter_rules.o
py -3 -B ailc.py language_examples/object_filter_main.ail --object object_filter_config.o --object object_filter_rules.o -o object_filter
"OK:one", "ERR:two" | ./object_filter.exe
```

出力は `ERR:two` と `matched=1` の2行です。設定モジュールの `ERROR_PREFIX` は判定関数で、
`REPORT_PREFIX` は入口で使います。定数は読み取り専用で、同名の引数・局所変数・関数や
別モジュールの公開名と衝突すると拒否します。整数は符号付き64ビット、文字列は空文字・
NUL・Unicode文字を扱います。定数値は型情報にも保存され、機械語内の契約識別子と照合します。
利用側へはコンパイル時の値として取り込みます。依存から取り込んだ定数は自動で再公開しません。
元ソースを消した後でも、すべての依存 `.o` と `.o.json` を一緒に移動してリンクできます。

関数は型が明示されたトップレベル関数が対象です。引数と戻り値は
`int`・`float`・`str`・`bytes`・`list` を指定できます。`bytes` リテラルの公開定数にも対応します。
`bytes`を含むコンテナの公開定数は未対応です。
引数と戻り値には小数配列 `list[float]` も指定できます。入力は読み取り専用、戻り値は呼出し側が所有します。
文字列・バイナリ戻り値は呼出し側が所有し、対応済みの例外はモジュールをまたいで捕捉できます。
戻り値は関数終了前にコピーするため、局所変数のスライスや連結、ファイル読込の結果も返せます。
`list` は平坦な符号付き64ビット整数列です。入力は読み取り専用、戻り値は呼出し側が所有し、
別モジュールへの引数・直接返却・反復・集計に使えます。入力の添字も境界検査を行い、
範囲外は `IndexError` として捕捉できます。小数・文字列・バイナリ・行・入れ子の配列は拒否します。
`return []` や `return [minimum, maximum]` と直接書けます。要素は左から一度ずつ評価し、
呼出し結果や整数式も使えます。既存の `integer_series.ail` の `bounds` は、空入力で `[]`、
それ以外では `[min(values), max(values)]` を返す実例です。
例外で呼出し元へ戻るとき、飛び越えるAIL関数が所有する配列・辞書・文字列/bytesの領域は
解放します。捕捉側が保持する値は残るので処理を続けられます。捕捉側自身で増やし続ける領域や
すべての外部C資源を自動解放する保証はありません。finallyに後始末を書けますが、致命的停止は対象外です。
入れ子関数、クラス、配列・真偽値・計算式の定数、既定値付き引数、
および汎用経路への切替は未対応として拒否します。
`abs`・`len` などの組込み名は、公開関数名として使用できません。
R360から実行ファイルの入口は `--object` とソースの `--module`・`use` を併用できます。
読み込んだソースをまとめて型検査し、既存オブジェクトをリンクします。
R392から`--object`と`--separate`を併用できます。ソースの各モジュールを別のCオブジェクトへ構築し、
既存のC/AILライブラリとリンクします。例外・標準入出力などのruntime状態は一つを共有します。
推移的なobject依存と隣接metadata全体が必要です。ソースの公開名とobjectの公開名の衝突、
ABI・対象環境・compiler/runtime identity・内容の不一致は従来どおり拒否します。
R361から `compile-module` も推移的な `use` を読み込み、一つのオブジェクトにまとめます。
共有依存は一度だけ読み込みます。関数名・定数名は全ソースで共通なので、同名定義は拒否します。
依存するCオブジェクトは内包せず、利用時にも完全なオブジェクトとmetadataを渡します。

標準入力のバイト数とNUL数を数える、三つのAILソース＋既存C実装の例です。
次の出力先は、新しいディレクトリを作って指定してください。

```powershell
mkdir byte_scan_build
py -3 -B ail_chatgpt.py compile-c language_examples/byte_search.c --interface language_examples/byte_search.json -o byte_scan_build/native.o
py -3 -B ailc.py language_examples/byte_scan_stdin.ail --separate --object byte_scan_build/native.o -o byte_scan_build/byte_scan
```

`use`で`byte_scan_counts.ail`、さらに`byte_search_core.ail`を読み込み、Cのborrowed bytes関数を呼びます。
引数なしでバイナリ標準入力を8,192バイトずつ読み、`bytes=数`と`zeros=数`をLF区切りで出力します。
テキストの正規化はしません。これは利用機能の実例で、最速の計数アルゴリズムという主張はありません。
Linuxでは独立Pythonの`len`/`bytes.count`に対し、空・全byte値・NUL/CRLF/Ctrl-Z・境界・
16,777,472バイトを含む7入力の全出力を照合しました。
公開auto構築と移動後検証の結果は`language_examples/byte_scan_separate_linux_r392.json`です。

関連Linux検査15件が成功。Windowsではcompiler変更前の原版autoの4検査が成功しましたが、今回の新しい分割接続の
3検査中1件は実行ファイル起動時に`WinError 225`で拒否され、2件成功・1件未完了です。
Windows全体の資格を通過したとは扱いません。セキュリティ設定は変更していません。
今回compiler実装が変わったため、旧`.o`を現在のcompilerで再リンクするには再構築が必要です。
旧実行ファイル・配布物・履歴は保全しています。
元AILソースを除去しても再利用でき、C API用にはすべての依存を同じ `--c-api-name` で構築します。

整数列ファイルから閾値以上の値を選び、昇順に並べた隣接値の差分を求める例です。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/integer_series.ail -o integer_series.o
py -3 -B ailc.py language_examples/integer_series_main.ail --object integer_series.o -o integer_series
./integer_series.exe values.txt 7
```

`values.txt` に `9`、`-2`、`7`、`7`、`12` を1行ずつ書くと、出力は件数 `3` と差分 `0`、`2`、`3`
の4行です。同じ `.o` と `.o.json` を別の入口にも使えます。整数列の元ソースはリンク時に不要です。
読込失敗は終了値3、整数として解釈できない入力は終了値4となり、標準エラーへ理由を出します。

対象OS・CPUアーキテクチャ・Cコンパイラ・AILの型付き生成器とランタイムが同じ場合の再利用です。
対象や実装の不一致、オブジェクトの変更、型情報と機械語の契約の不一致は拒否します。
AIL更新後は元ソースから再コンパイルしてください。このモジュール形式は内部ABIです。
Cから呼ぶ場合は、次の専用入口でCヘッダーとオブジェクトを生成します。

## AILライブラリをCから呼ぶ

`compile-library` は型付きAIL関数をCから呼べるヘッダーとオブジェクトへ変換します。
生成先は既存の親ディレクトリ内の新規フォルダにしてください。
ビルドにはPython 3.10以上とC11対応GCCを使います。実行時はPythonも元のAILソースも不要です。

```powershell
py -3 -B ail_chatgpt.py compile-library language_examples/binary_record.ail --name record -o record_lib
gcc -std=c11 -I record_lib language_examples/binary_record_host.c record_lib/record.o -o record_host.exe
./record_host.exe
```

結果は `packed=264 restored=256 invalid=1` です。C側で用意した全256バイト値を
AILでレコード化・復元し、不正入力ではC側にエラー番号1を返して実行を継続します。
Linuxでも同じビルド手順を使えます（`py -3` を `python3` に変更）。
WindowsのGCCでは、日本語を含むパス引数でリンクに失敗する場合があります。
対象のフォルダを作業ディレクトリにし、上のようにASCIIの相対名で指定してください。

生成物は `record.h`、`record.o`、`library.json` です。OS・CPU・Cツールチェーンに対応する
オブジェクトを使用します。ヘッダーとオブジェクトを一緒に移動でき、元ソースは不要です。
公開シンボルに内容識別子を付け、異なる版のヘッダーとオブジェクトの混用をリンク時に拒否します。
長期固定ABIではありません。数学ライブラリが必要な場合は `library.json` の
`link_libraries` に `m` が入り、リンクコマンドに `-lm` を加えます。

| AIL型 | Cの引数 | Cの出力先 |
|---|---|---|
| `int` | `int64_t` | `int64_t *` |
| `float` | `double` | `double *` |
| `void`（戻り値のみ） | — | 出力先引数なし |
| `str` | `record_view`：UTF-8のポインタとバイト数 | `record_buffer *` |
| `bytes` | `record_view`：生バイトのポインタとバイト数 | `record_buffer *` |
| `list`（int64要素） | `record_int_view`：読み取り専用int64_tポインタと要素数 | `record_int_buffer *` |
| `list[float]` | `record_float_view`：読み取り専用doubleポインタと要素数 | `record_float_buffer`：所有するdoubleポインタと要素数 |

各関数は `int record_関数名(引数..., 出力先, record_error *)` という形です。
`-> void` 関数だけは出力先を省いた `int record_関数名(引数..., record_error *)` になります。
このC APIの整数の戻り値は状態番号であり、AILのvoid関数が値を返すわけではありません。
戻る整数は状態番号で、0が成功です。失敗時には出力先の値を変更しません。
`record_error *` はNULLでも構いません。状態は1～7が順にValueError、ZeroDivisionError、
IndexError、KeyError、EOFError、OSError、RuntimeError、8が確保失敗等の致命的エラー、
9が不正なC引数、10が同じライブラリの呼出し実行中です。メッセージは最大159バイト、
assertのメッセージは `assertion failed` になります。

入力ポインタは呼出し中読み取り可能な領域を指し、NULLは長さ0の場合だけ使えます。
文字列の長さにも終端NULを含めず、途中のNULはデータとして扱います。
成功した `record_buffer` は呼出し側の所有物で、別の呼出し後も保持できます。
`record_int_buffer` も同じ所有規則です。整数配列の `size` はバイト数ではなく要素数です。
入力は正しくアラインされた `int64_t` 領域を指します。返却配列は入力と別の所有領域になり、
空の返却配列は `{NULL, 0}` です。Cライブラリ内の平坦な配列添字は負数を長さから数え、
範囲外は状態3、サイズの表現範囲超過やNULLと非ゼロ長の組合せは状態9を返します。
使い終えたら、そのライブラリの `record_free(buffer.data)` で一度だけ解放してください。
同じ出力変数へ次の成功結果を上書きする前に、前のバッファを解放してください。
小数入力の `record_float_view` も要素数を指定します。NULLと非ゼロ長、サイズの表現範囲超過、
doubleのalignment不一致は状態9で拒否し、出力先を変更しません。添字の範囲外は状態3です。

通常終了・未捕捉エラーとも、一回の呼出しで残った内部メモリとファイルを解放します。
呼出し内の長いループのメモリ使用量を一定にはしません。途中のファイル書込みや標準出力は
取り消しません。同じライブラリへの同時・再帰的なC呼出しは待機せず状態10を返します。
型付きソースの `use` と `--module` に対応します。外部 `.o` は下記の専用方式で接続します。
`input()`、`sys`、整数/小数配列以外のコンテナの公開は未対応です。整数列は `list[int]` ではなく `list`、
小数列の引数・戻り値は `list[float]` と宣言します。行列・レコード配列は拒否します。
AIL内部でも、平坦な整数リストを `xs = f(values)`、`return f(values)`、
`g(f(values))` の形で受け渡せます。補助関数にも `-> list` を指定します。
結果は一度だけ計算し、受取側が所有します。再代入時は先に新しい結果を求めてから
前の領域を解放するため、`xs = f(xs)` とループ内の再利用にも対応します。
`len(f(values))`、`f(values)[index]`、`for value in f(values)`、内包表記や
`sum(f(values))` などの集計でも直接使えます。呼出しは一度だけ実行します。
負数添字に対応し、範囲外は `IndexError`、空列の `min`・`max` は `ValueError` です。
整数の `sum` も各加算でint64の範囲を検査し、超過時に丸めません。
`any`・`all` のジェネレータは結果が確定した所で止まります。リスト内包表記は先に
全要素を評価し、集合内包表記は重複を除いてから集計します。集合の要素は整数です。
レコード・bytes要素・入れ子を整数リストとして渡す形は拒否します。
呼出し引数に前処理の文が必要な式も拒否するので、先に変数へ保存してください。
C実用例、所有権、エラー後の復帰、
確保失敗、ソース削除・移動後のリンクをWindows/Linuxで検査しています。
これは機能追加であり、速度優位を測定したものではありません。

#### C実装を呼ぶAILオブジェクトを、Cから再利用する

R343から、C向けのライブラリ名を決め、依存のC/AILオブジェクトを `--c-api-name` 付きで構築できます。
最終の `compile-library --name` と全依存の名前を一致させ、依存を全て `--object` で渡します。
この例はCのCRC計算、別コンパイルしたAILの増分/範囲処理、Cへ公開するAIL入口を接続します。

```powershell
New-Item -ItemType Directory crc_api_build
py -3 -X utf8 -B language_examples/c_headers_workflow/build_crc_library.py --c-api-name capicrc --out crc_api_build/native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/c_headers_workflow/crc32_stream.ail --c-api-name capicrc --object crc_api_build/native.o -o crc_api_build/stream.o
py -3 -X utf8 -B ail_chatgpt.py compile-library language_examples/c_headers_workflow/crc_c_api.ail --name capicrc --object crc_api_build/native.o --object crc_api_build/stream.o -o crc_api_lib
```

生成する `capicrc.h` / `capicrc.o` / `library.json` だけで、元のC/AILソースや依存objectなしでCから使えます。
ユーザーのCソースを `gcc -std=c11 -I crc_api_lib host.c crc_api_lib/capicrc.o -lm -o host.exe` でリンクします。
Linuxでは `py -3` を `python3` に、実行物を `.exe` なしにします。
Windowsの日本語パスは、ライブラリ先を作業ディレクトリにしてASCIIの相対名でリンクしてください。

公開関数は次の形です（ヘッダーの内容識別子付きマクロを使います）。

```c
int capicrc_update(int64_t previous, capicrc_view data, int64_t *out, capicrc_error *error);
int capicrc_file_crc(capicrc_view utf8_path, int64_t *out, capicrc_error *error);
```

previousの範囲外は状態1、読込み失敗は状態6で戻り、失敗時の*outは保持します。
パスはUTF-8です。Windowsのmain(argv)がUTF-8とは限らないため、C側で適切に変換して渡します。
同じ方式を一般の `compile-c --c-api-name NAME` / `compile-module --c-api-name NAME` に使えます。
通常object、異なる名前、足りない依存は拒否し、専用objectを通常のAIL入口へ混用することも拒否します。
R360から `compile-library` は専用 `--object` とソースの `use` / `--module` を併用できます。
読み込むソースとオブジェクトの公開名が衝突する場合は拒否します。専用namespaceと依存の条件は同じです。

専用objectは、生成runtimeの状態・致命的エラー・確保・ファイル管理を同じC呼出し境界へ接続します。
結合後は公開APIとfree以外の定義をローカル化し、別名のライブラリ同士の状態を分けます。
GNU系のrelocatable linkとobjcopyが必要です。ビルド記録にobjcopyのpath/hashと依存ABI/hashを保存します。
通常objectの代用ではなく、このライブラリ名専用です。ツールのidentity変更後は依存を再構築します。
現在この方式のassembly依存は拒否します。信頼済みCが別allocator、任意のexit、入力ポインタの保持等を
行う場合まで保護する仕組みではありません。標準の借用・所有権のC契約を守ってください。

Windows/Linuxでソースなしの移動後リンク、CRCの独立参照一致、エラー後の復帰、bytes/list所有権、
別名2ライブラリと再入状態10を確認しました。複数Cソースの確保後・ファイルopen後の失敗を含む
30回の検査で、呼出し前から増えた追跡確保とファイルは残りませんでした。RSSや速度の測定ではありません。
R344では、正常呼出しの20回の確保を一つずつ失敗させても、状態8/out保持/追跡残量0と
直後の回復を両OSで確認しました。先に返したbytes、借用入力、file、生成物の不変と、
正常返却196,613バイトの独立期待値一致を検査しています。libc内部や任意allocatorは対象外です。

#### Cから整数列を処理する

`integer_series.ail` は閾値以上の値の選別と並べ替え、時系列の差分、最小/最大を提供します。
`integer_series_host.c` は同じ読み取り専用入力を三つの関数へ渡し、返却配列を保持・照合・解放します。
`filtered_differences` は `differences(above(values, minimum))` をAIL内で接続し、
選別・並べ替え後の差分を一回のC呼出しで返します。実例では `[0, 2, 3]` を照合します。
`filtered_change_total` は、その戻り値を `sum` へ直接渡して合計 `5` を返します。
差分がint64範囲を超えた場合は通常の整数演算と同じく失敗し、丸めて返しません。

```powershell
py -3 -B ail_chatgpt.py compile-library language_examples/integer_series.ail --name series -o series_lib
gcc -std=c11 -I series_lib language_examples/integer_series_host.c series_lib/series.o -lm -o series_demo.exe
.\series_demo.exe
```

期待出力は `selected=4 differences=4 bounds=-2,12` です。ヘッダーとオブジェクトを移動しても
組を保てば使えます。過小な内部返却バッファで内容を落とす経路も修正し、0～65,538要素の
受取容量と、65,537要素の内容回収を検査しました。検査名は `test_ail_c_library.py` を参照。

### 複数のAILソースからCライブラリを作る

`use binary_record;` は、そのソースと同じフォルダの `binary_record.ail` を読みます。
そこからの `use` もたどり、同じファイルは一度だけ取り込みます。関数・定数名は共通で、
循環依存・名前の重複・AIL定数の書き換えや引数による隠蔽は拒否します。
`use` だけを記した入口も使えます。複数ソースの全関数に引数と戻り値の型が必要です。
既定では全関数を公開します。`--export 関数名` を繰り返すと、Cへ公開する関数を選べます。

```powershell
py -3 -B ail_chatgpt.py compile-library language_examples/binary_record_files.ail --name records --export save_record --export load_record -o records_lib
gcc -std=c11 -I records_lib language_examples/binary_record_files_host.c records_lib/records.o -o record_files.exe
./record_files.exe output.bin
```

この例は `binary_record_files.ail` の保存・読込み関数から、別ファイルのレコード処理を
呼び出します。65,537バイトを保存・復元し、結果は
`saved=65545 restored=65537 missing=6` です。`output.bin` が既にあれば置き換えます。
C実用例のパス引数はUTF-8として扱い、Windowsの通常の狭い文字列argvとは文字コードが
異なる場合があります。上のASCII名はそのまま使用できます。

この指定では `save_record`・`load_record` と解放用の `records_free` だけがCの公開関数です。
内部で使う `pack_record`・`unpack_record` はヘッダー・公開一覧に出ず、外からリンクできません。
存在しない関数・定数・同じ関数の二重指定は拒否します。公開関数の組み合わせも内容識別子に
含めるため、指定を変えたら新しいヘッダーとオブジェクトの組で利用してください。
内部の補助関数も従来の型付き `int`・`float`・`str`・`bytes` 契約が必要です。
非公開指定によって対応外の型や構文が使えるようになるわけではありません。

`--module helper.ail` で追加ソースを指定することもできます。`use` で既に読み込んだものは
重複取り込みせず、同じ `--module` の二重指定や入口自身の指定は拒否します。
`--syntax auto` は各ファイルでブロック構文・Python風構文を判別します。
生成したオブジェクトには依存ソースのコードも含み、Cでのリンク・実行時にはソース一式は不要です。
これは複数ソースの一括ビルドで、既存の `.o` を追加リンクする機能ではありません。

## C実装をAILから呼ぶ

`compile-c` は、Cの関数と型を宣言したJSONから、AIL用の `.o` と `.o.json` を生成します。
作成後はCソースや元のJSONなしで、通常の `--object` と同じように入口や別のAILライブラリから使えます。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_interop.c --interface language_examples/c_interop.json -o c_interop.o
py -3 -B ailc.py language_examples/c_interop.ail --object c_interop.o -o c_interop
./c_interop.exe .\input.txt
```

この例はUTF-8ファイルのバイト数とチェック値を表示します。ファイルの改行は変換しません。
チェック値は、各バイトに1から始まる位置を掛けた合計を1,000,000,007で割った余りです。
Linuxでは `py -3` を `python3`、実行名を `./c_interop` に替えます。

型宣言の例は次のとおりです。

```json
{
  "version": 1,
  "functions": {
    "byte_count": {
      "symbol": "native_byte_count",
      "params": [["text", "str"]],
      "result": "int"
    }
  }
}
```

`byte_count` がAILで呼ぶ名前、`native_byte_count` がC側の関数名です。
この宣言に対応するC関数の型は次になります。

```c
int64_t native_byte_count(const unsigned char *data, size_t length);
```

| 型JSONの指定 | Cで受ける型 |
|---|---|
| `int` | `int64_t` |
| `bool` | `_Bool` / 標準 `bool`。AIL側は `int`、0/1のみ |
| `int8` / `uint8` | `int8_t` / `uint8_t`。AIL側は `int` |
| `int16` / `uint16` | `int16_t` / `uint16_t`。AIL側は `int` |
| `int32` | `int32_t`。AIL側は `int` |
| `uint32` | `uint32_t`。AIL側は `int` |
| `float` | `double` |
| `float32` | `float`。AIL側は `float`。有限値のみ |
| `str` 引数 | `const unsigned char *` と `size_t` の2引数 |
| `cstr` 引数 | UTF-8と終端NULを持つ `const char *` の1引数。AIL側は `str` |
| `bytes` 引数 | 同じ2引数。変換せず、任意のバイト列をコピー |
| `list` 引数 | `const int64_t *` と `size_t`。平坦な整数列の借用領域と要素数 |
| `float_list` 引数 | `const double *` と `size_t`。平坦な小数列の借用領域と要素数 |
| `float_list` 戻り値 | `ail_c_float_view`。コピー完了まで有効なdouble領域と要素数 |
| `float32_list` 引数 | `const float *` と `size_t`。有限値をbinary32へ変換した一時領域と要素数 |
| `float32_list` 戻り値 | `ail_c_float32_view`。コピー完了まで有効なfloat領域と要素数 |

戻り値は `int`・上表の8/16/32ビット整数・`float`・`float32`・`bytes`・`str`・整数の `list`・小数の `float_list` / `float32_list`・`void` です。引数なしはCで `(void)` と書きます。
型の不一致、可変長引数、型を省略した旧式のC関数はビルド時に拒否します。
`str` 引数はUTF-8へ変換し、NULも長さに含めます。終端NULは保証しません。
通常のAILの文字出力と同様に、不対のUTF-16サロゲートはU+FFFDへ変換します。
C側は渡された領域を読み取り専用として呼出し中だけ利用し、ポインタを保持・解放してはいけません。
コールバックとC側の `longjmp` は未対応です。C関数は通常の `return` で戻す必要があります。
`bytes` も呼出し中だけ読み取れます。`str` と `bytes` は別の型で、自動変換はしません。

入力は、C11のアダプターと、明示したローカルヘッダー、コンパイラー既定のシステムヘッダーが対象です。
数学ライブラリが必要ならJSONのトップレベルに
`"libm": true` を加えます。宣言したC関数名はライブラリごとに内部名へ変換します。
その他のCの外部シンボルは、`static` にするか、他のライブラリと衝突しない名前を使ってください。
Cソースは利用者が信頼するコードを指定します。型検査はC実装のメモリ安全性や計算結果を証明するものではありません。
ASCII保存形式の文字列は一括コピーし、それ以外はUTF-8へ変換します。
文字列とbytesの領域の確保・引数の配置・解放は同じです。

### CのNUL終端文字列を渡す（R383）

型JSONで入力を `cstr` にすると、既存Cライブラリの `const char *` 引数へ
AILの `str` を渡せます。たとえば次の宣言に対応するCの型は
`int64_t native_length(const char *text);` です。

```json
{"version":1,"functions":{"length":{"symbol":"native_length","params":[["text","cstr"]],"result":"int"}}}
```

UTF-8の一時領域の末尾にNULを追加します。空文字にも有効な終端領域を渡します。
埋込みNULはCを呼ぶ前に `ValueError` にし、途中で文字列を切り捨てません。
複数引数の各終端は独立しています。Cは呼出し中だけ読み取り、領域の保存・変更・解放はできません。
`cstr` は入力専用で、戻り値の文字列には既存の長さ付き `str` を使います。
既存 `str` の長さ付き引数とNULの扱いは維持します。既存オブジェクトは実装識別が変わるため再生成してください。
これはCとの互換機能で、速度改善の主張ではありません。

### アセンブリの処理をAILから呼ぶ

型JSONに `"asm_sources": ["asm_checksum.S"]` を加えると、主Cソースと同じディレクトリの
宣言した `.S` をCプリプロセッサ付きアセンブラで構築し、型付きオブジェクトへまとめます。
今回の対象は、既存のGCC/GNU assemblerツールチェーンです。
主 `.c` には、アセンブリ関数の正確なCプロトタイプを書きます。既存の `compile-c` と `--object` を使います。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/asm_checksum.c --interface language_examples/asm_checksum.json -o checksum.o
py -3 -B ailc.py language_examples/asm_checksum.ail --object checksum.o -o checksum
./checksum.exe input.bin
```

この実例はx86-64 Windows/Linux用です。入力はlittle-endianの64ビット整数を並べたファイルで、
結果は合計を2^64で折り返し、符号付き整数として表示します。空入力は0、8バイト単位でない入力は終了2、
ファイルを読めない場合は終了3です。入力を変更せず、全入力をメモリへ読み込みます。
AILの通常の整数演算は範囲外で失敗します。この実例の折返しは、アセンブリ関数に明示した別の仕様です。

Windows/Linuxの[呼出し規約](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention)は同じではありません。
実例はWindowsのスタック引数と[System V AMD64 ABI](https://gitlab.com/x86-psABIs/x86-64-ABI/-/blob/master/x86-64-ABI/low-level-sys-info.tex)の
スタック引数を別に扱います。Cプロトタイプ検査は、アセンブリ本体の型・レジスタ保存・スタック配置を証明しません。
他のCPU/OSには、その対象の実装が必要です。これはAILから直接アセンブリを生成するbackendではありません。

`.S` の相対パスを明示します。外部へ解決するパス、重複/衝突、欠落を拒否し、内容をオブジェクト識別に含めます。
付属ファイルは既存の `headers` に `.h` / `.inc` として宣言します。CPPとGAS両方の依存記録を検査し、
未宣言の付属ファイルは拒否します。宣言済み `.include` / `.incbin` の受理も検証しました。
公開シンボル名が `.S` 本体またはCPPの `#include` 内で名前置換を受ける形にします。GASの `.include` は
CPPの名前置換を受けません。非公開の外部シンボルも衝突しない名前にする必要があります。

両OSで7整数引数・int64両端・符号付きゼロ/subnormal・別オブジェクトの名前分離と、
65,537語までのファイル照合、ソースなしの移動後リンク・実行を確認しました。速度改善は未測定です。
compiler identityが変わるため、既存のAIL/Cオブジェクトは再構築してください。

同じAIL呼出し側でC加算とアセンブリ加算を比較する入口もあります。

```powershell
py -3 -X utf8 -B language_examples/asm_checksum_workflow/workflow.py --out NEW.json
```

比較用入口はstdinからファイル名を読みます。独立28ケース、65,537語の交互測定とA/A、
一時配布物の移動後検証を通します。既存の出力ファイルは上書きしません。
R324では両OSで一致しましたが、C/アセンブリの安定した速度優位は確認できませんでした。
Linuxの時間中央値はASM0.752秒/C0.770秒、WindowsはASM0.730秒/C0.742秒です。
元のASM候補を保持した判定は、ASMの優位性の証明ではありません。
加算工程の割合・Amdahl上限・物理roofは未測定です。直接assembly backendは未実装で、
既存コンパイラと、必要な箇所で使用する `.S` の接続を併用します。

共通Cアダプターのコピー工程も測れます。

```powershell
py -3 -X utf8 -B language_examples/asm_checksum_workflow/copy_profile.py --out NEW.json
```

R325の計測版では、入力全体の繰返しコピーがLinux98.36%/Windows92.76%を占めました。
コピーだけを完全除去できるという条件付き上限は60.93倍/13.81倍で、通常版の改善予測ではありません。
同量コピーC参照の達成率は98.51%/86.67%。Windows参照の時計校正は失敗しているため予測に使いません。
両OSとも79測定呼出しの全出力/入力が独立参照に一致しました。原版/診断版には28ケースも実施しています。
R325時点では物理roof、通常版の工程割合、コピーを省く接続の実装/採用は未達でした。
R326の明示借用接続と比較結果は次節に記載します。物理roofと通常版の工程割合は引き続き未証明です。
JSONの計測器hashは、測定後の失敗ログ保存修正前の版を示します。

### Cへbytesをコピーせず渡す

C入力の型JSONに `borrowed_bytes` を指定できます。AIL側では通常の `bytes` 引数です。
C側の型は `const unsigned char *` と `size_t` の組で、呼出し中だけ元の領域を読み取ります。
Cはこのポインタへ書込み、保存、解放をせず、通常の関数復帰をする必要があります。
この契約の遵守は型検査だけでは証明できません。同じ入力を複数引数に渡した時のポインタ一致も保証しません。
通常の `bytes` / `str` の一時コピーは維持します。`borrowed_bytes` は戻り値には指定できません。

負の長さ・size_tを超える長さ・非空NULLはC呼出し前に拒否します。空NULLは許可します。
任意の非NULLポインタの有効性は検査できません。借用入力を `bytes` 結果として返す場合も、
既存の所有コピーを行うため、AILの結果は呼出し後も独立して保持できます。
compiler identityが変わるため、既存AIL/Cオブジェクトは再構築してください。

チェックサム例では読み取り専用C関数に、次の型JSONを使えます。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/asm_checksum.c --interface language_examples/asm_checksum_borrowed.json -o checksum_borrowed.o
py -3 -X utf8 -B ailc.py language_examples/asm_checksum.ail --object checksum_borrowed.o -o checksum_borrowed
./checksum_borrowed.exe input.bin
```

同じAIL/C/ASM本体でコピー版と借用版を比較する入口です。

```powershell
py -3 -X utf8 -B language_examples/asm_checksum_workflow/workflow.py --candidate borrowed_bytes --out NEW.json
```

R326は両OSで独立28ケース、長い入力の全出力照合、交互測定/A/A、ソースなしの移動後検証を通しました。
最終測定の時間中央値はLinux592.201→2.416ms、Windows602.884→13.954ms。
中央値同士の比は245.142倍/43.206倍です。これは65,537語のチェックサムと当該機械に限る値です。
速度優先判定で借用を選択し、Windowsのピークworking set中央値は6,452→6,460KiBの増加も受け入れています。
実オブジェクトの逆アセンブルで、元のmemcpy（Linuxは__memcpy_chk）/malloc/freeと、借用版での除去を確認しました。
コピーだけでなく呼出し毎の確保/解放も省くので、R325の計測版のコピーだけを除く上限とは比較条件が異なります。
物理roof・通常版の工程割合・他ソフト/入力での速度優位は未証明です。比較用配布物は一時領域だけで選択し、
既存ソフトは置き換えません。恒久的に使う時は上記の明示設定を指定してください。

### Cの32ビット小数を使う

Cの `float native_value(float x)` には、型JSONで引数と戻り値を `float32` と指定します。

```json
{"version":1,"functions":{"value":{"symbol":"native_value","params":[["x","float32"]],"result":"float32"}}}
```

AILでは `let x = value(0.1);` のように通常の `float` として扱います。
Cへ渡す時に32ビットへ丸め、戻る時にdoubleへ拡張します。元のdoubleと結果が同一になる保証はありません。
丸めは対象のC実装と実行時の浮動小数点環境に従います。既存の `float` 宣言はdoubleのままです。

この接続は有限値用です。引数のNaN・無限大・±FLT_MAXの外側は、変換とC呼出しの前に `ValueError` になります。
Cが非有限値を返した場合も `ValueError` ですが、C内の副作用はすでに実行されています。
引数用の文字列/bytes領域は、戻り値の拒否前に解放します。捕捉しない場合は専用診断と終了1になります。
非常に小さい値はsubnormalやゼロに丸められます。Cソースは丸めモードやsubnormal処理を変更しない前提で使用してください。
対象は8ビットbyte・binary32精度/指数・subnormal対応のC型に限定し、ビルド時に検査します。

Windows/Linuxの既定の浮動小数点環境で、符号付きゼロ、各有限指数、subnormal境界、丸めの中点とその隣、
乱数を含む7,720入力をPythonの `struct` とビット単位で照合しました。
これは対象環境の検証であり、任意のC実装/変更済み浮動小数点環境で同じ丸めになる証明ではありません。
現行コンパイラー/runtimeでCとAILのobjectを再構築してください。配列には次の `float32_list` を指定します。

### Cの32ビット小数配列を渡して受け取る

型JSONの `float32_list` は、AILの `list[float]` とCのfloat配列を接続します。
AIL内部はdoubleのままです。Cへ渡す全要素が有限かつ±FLT_MAX以内であることを検査してから、
一時領域のfloatへ変換します。C側はその領域を呼出し中だけ読み取り、保持・変更・解放してはいけません。
同じAIL配列を複数の引数へ渡しても、Cのポインタが同じになる保証はありません。

```c
typedef struct { const float *data; size_t size; } ail_c_float32_view;
ail_c_float32_view native_clip(const float *values, size_t count, float limit);
```

`ail_c_float32_view` の型定義はアダプターが提供します。Cソースで重複して定義する必要はありません。
戻り値の `size` は要素数です。Cの入力領域や静的領域を返せますが、コピー完了まで有効でなければなりません。
戻った全要素の有限性を検査し、AILが所有するdouble配列へコピーしてから一時領域を解放します。
CがNaN/無限大を返すと `ValueError` です。入力拒否ではCを呼びませんが、戻り値拒否ではCの副作用を取り消しません。
NULLは要素数0のみ許し、長さ・サイズの積・alignmentを検査します。任意の非NULL領域の有効性を保証するものではありません。
丸めとunderflowの契約は単一値の `float32` と同じです。既存の `float_list` はdoubleの借用のままです。
この版のコンパイラーでC/AILのobjectを再構築してください。任意のCポインタを扱う機能ではありません。

`c_float32_clip` は、空白区切りの数値ファイルをfloat32配列としてCへ渡し、指定した非負の上限±limitに収めます。
Cの作業領域を明示的に解放してから、AILが保存した結果をlittle-endian binary32ファイルへ書き出します。
入力とlimitを先にbinary32へ丸めてから比較する仕様です。既定のIEEE浮動小数点環境を使ってください。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_float32_clip.c --interface language_examples/c_float32_clip.json -o clip_native.o
py -3 -B ailc.py language_examples/c_float32_clip.ail --object clip_native.o -o clip_file
./clip_file.exe values.txt clipped.f32le 1.0
```

不正な数値、非有限値、範囲外、負のlimitは終了2になり、既存の出力を変更しません。
ファイルのI/Oエラーは終了3です。書込み途中の失敗に対するatomicな保存は保証しません。
配列と出力をメモリ上に置く実装です。この機能追加による速度改善は未測定です。

#### 小数配列をスタックとして使う

局所的に所有する小数配列では、`values.pop()` で末尾を取り出せます。
`values.pop(i)` は指定位置を取り出し、負の添字は末尾から数えます。戻り値は小数です。
空配列や範囲外の添字は `IndexError` になり、そのpopによる配列の変更はありません。
関数の `list[float]` 引数は借用のままです。加工するときは局所配列へコピーします。

再利用ライブラリの実例は、入力を保ったまま小数列を逆順にします。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/float_reverse.ail -o reverse.o
py -3 -B ailc.py language_examples/float_stack.ail --object reverse.o -o float_stack
./float_stack.exe
```

出力は `1.5`、`-0.0`、`0.25`、入力の長さ `3` の順です。
末尾のpopは要素をずらしません。途中のpopは後続要素をずらすため、長さに応じた時間がかかります。
小数の添字、余分な引数、キーワード引数、借用引数や定数の変更、小数タプル行のpopは拒否します。
コンパイラ実装が変わったため、既存のAIL/Cオブジェクトは再構築してください。

#### 係数配列を直接初期化してCへ渡す

`c_float32_filter.ail` は、`let weights = [0.25, 0.5, 0.25];` で係数を作り、
Cの数値フィルターへ渡します。現在値・一つ前・二つ前の入力をこの順に重み付けします。
先頭の不足要素はゼロとして扱い、出力の要素数は入力と同じです。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_float32_filter.c --interface language_examples/c_float32_filter.json -o filter_native.o
py -3 -B ailc.py language_examples/c_float32_filter.ail --object filter_native.o -o filter_file
./filter_file.exe values.txt filtered.f32le
```

入力は空白区切りの数値、出力はlittle-endian binary32です。入力をbinary32へ丸めた後、
各乗算と加算を別々にbinary32へ丸めます。加算の初期値は正のゼロで、積和を一命令に融合する仕様ではありません。
既定の最近接・中点偶数丸めとgradual underflowを前提とし、Cではvolatile中間値で各段の格納を行います。
AILはCの結果を保存し、Cの作業領域を解放した後にファイルを書きます。
不正/非有限/範囲外の入力は終了2で既存出力を保持します。I/Oエラーは終了3で、書込み失敗のatomic性は保証しません。
この例は小数配列の初期化と別コンパイルしたC接続の実例です。

同じ数値仕様のPython実装との比較は、次で実行できます。結果JSONには新しいパスを指定します。

```powershell
py -3 -B language_examples/float32_filter/workflow.py --out filter-comparison.json
```

比較用の入力はASCIIの十進数・指数表記で、桁区切りの下線を使いません。
区切りはASCII空白です。Unicode空白で区切る入力は比較対象外であり、拒否する保証もありません。
Python原版はarray/ctypes、独立検査器はstructを使い、各段の丸めを含めて全出力バイトを照合します。
固定65,537値の仕事を前後A/A・交互測定に通し、balanced方針で時間・CPU・メモリを比較します。
実行時間0.5秒/64MiBの条件は個別の入力一式の観測最大にも適用します。
構築・資格検査・比較・配布・移動後検証までの費用は、アプリの実行時間と分けて記録します。
候補の採用はこの仕事・入力・機械についての判断です。全用途の優位性や投資回収済みを意味しません。
R318では両OSで37ケースの独立照合、途中の丸めを省く誤実装の検出、固定入力の移動後検証まで成功しました。
数値と費用の記録は同じフォルダーの `comparison_linux_20261001_r318.json` と
`comparison_windows_20261001_r318.json`、概要は `README_AUTO_ENTRY_JA.md` にあります。

工程を調べる場合は、通常版・旧計測版・補正版の時計無効/有効を比較します。

```powershell
py -3 -B language_examples/float32_filter/calibration.py --out filter-calibration.json
```

新規JSONを指定してください。4種類の全24実行順を使い、前後A/Aとwarmupを含む112回で、
毎回65,537値の全出力を独立参照と照合します。補正版の時計無効/有効は同一実行ファイルです。
一時的な子プロセス用環境変数は呼出し後に復元します。入力準備・出力照合はアプリ時間の外です。
`comparisons["normal -> controlled_timed"]` が補正版と通常版の比較です。
最上位の `instrumentation_within_observed_noise` は旧計測版についての値なので区別してください。

R319では両OSで112回の照合に成功しました。旧 `profile.py` は障害再現用として保存しています。
Windowsでは旧版の `_POSIX_C_SOURCE` 定義が数値変換の接続先を変え、通常版より明確に遅くなりました。
補正版はWindowsでこの定義を追加しません。ノイズ内という結果は計測負荷ゼロの証明ではありません。
工程割合は計測版の診断値であり、通常版の割合・高速化予測・採用根拠として確定していません。
記録は同じフォルダーの `calibration_linux_20261001_r319.json` と
`calibration_windows_20261001_r319.json`。詳細は `README_AUTO_ENTRY_JA.md` にあります。

同じ数値仕様のC参照と、現在のAIL+C版を比較する入口もあります。

```powershell
py -3 -B language_examples/float32_filter/c_comparison.py --out filter-c-comparison.json
```

`c_reference.c` はASCII数値をdouble経由でbinary32へ変換し、既存のCフィルターと同じコードを使います。
入力をすべて検査してから出力を開きます。全言語共通の置換ではなく、この入力・丸め仕様の参照です。
AIL版を原版として固定し、C参照を独立検査・交互測定・前後A/A・一時配布・移動後照合へ通します。
結果には探索側の選択と総費用を保存します。配布物は一時ディレクトリで検証後に除去され、
AILコンパイラの実装や既存アプリが自動でC版へ置き換わることはありません。
R320では両OSで成功しました。`c_comparison_{linux,windows}_20261001_r320.json` に生データを収録しています。
工程をまたぐ実装差があるため、この比較だけで数値解析単独の速度差やハードウェア限界は分かりません。

AILとCの工程時間・生成アセンブリを診断する入口は次です。

```powershell
py -3 -B language_examples/float32_filter/reference_profile.py --out filter-reference-profile.json
```

各実装の通常版・時計無効・時計有効を12通りの順序で測り、前後のA/Aを含む102呼出しで
65,537値の全出力と入力不変を照合します。通常版は各37ケースの独立検査も通します。
時計無効/有効は同じ実行ファイルです。生成アセンブリのhashと静的なcall先も保存します。
R322では両OSで実行済みで、`reference_profile_{linux,windows}_20261001_r322.json` に記録しています。
両通常版は数値変換でstrtodを呼びました。直接アセンブリ化の速度優位を示したものではありません。
LinuxのAIL計測版は観測ノイズの条件を満たさず、工程割合を通常版の値として確定できません。
Cは解析時点でbinary32へ変換し、AILはdouble配列を後で変換するなど工程境界も異なります。
アセンブリ生成は現在のCコンパイラ経由の診断で、AILから直接生成するbackendの実装ではありません。

#### 実ファイルをbinary32へ変換する

`language_examples/float32_file` は、little-endianのIEEE binary64が連続した入力を、
little-endianのIEEE binary32へ変換する実例です。ヘッダーはなく、入力8バイトが出力4バイトになります。
Cが入力をdoubleとして読み、上記 `float32` 引数変換で丸め、AILが結果をバイト列にして保存します。
この実例の契約は「最近接・中点では偶数丸め、ゼロの符号保持、gradual underflow」です。
対象はWindows/LinuxのIEEE形式・既定の浮動小数点環境で、契約JSONと結果JSONにこの条件を記録します。
一般のfloat32接続が全C実装でこの丸めを保証する意味ではなく、実例の境界oracleで確認する条件です。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/float32_file/native.c --interface language_examples/float32_file/native.json -o float32_native.o
py -3 -B ailc.py language_examples/float32_file/candidate.ail --object float32_native.o -o float32_file
./float32_file.exe input.f64le output.f32le
```

空入力は空出力になります。入力長が8の倍数でない場合、NaN/無限大、±FLT_MAXの外側は
`invalid input` と終了2で拒否し、既存出力は変更しません。読書きの失敗は `file error` と終了3です。
書込み自体のI/O失敗まで原子的に保護する仕様ではありません。入力全体と出力用整数リストをメモリに置きます。
出力形式で許容する丸めを事前に決めた実例であり、binary64の値を完全保存する変換ではありません。

Pythonの独立実装との比較は次で実行します。出力JSONには新しいパスを指定してください。

```powershell
py -3 -B language_examples/float32_file/workflow.py --out float32-comparison.json
```

固定65,537レコードについて、時間・CPU・メモリ、前後A/Aと交互測定を確認します。
採用方針はbalanced、アプリ実行0.5秒/64MiB以内です。候補が速くても他の条件を満たさなければ元実装を残します。
R315以降、時間/CPU上限は計測器内で繰り返した各入力一式の合計値の最大で判定します。
比較用の平均値とは別に、`observed_maxima` と、各呼出し/入力一式の記録を `measurement_blocks` に保存します。
12比較組と原版の前後各6回のA/Aを対象とし、比較前の2回のwarmupはこの上限判定から除外します。
旧記録に個別の値が残っていない場合、時間/CPU上限を確認済みとは扱えず、その上限を条件とする新たな採用判断を拒否します。
実行時間にはファイル準備・検証・成果物の配送を含めず、比較処理全体の時間を別に記録します。
30入力の独立照合に加え、配布物を移動して元ソース/ビルド/資格フォルダーを参照できなくした状態で再検証します。
記録はこの仕事・入力・機械の範囲に限ります。新たな高速化案の工程割合/Amdahl/roofの根拠には別の測定が必要です。

### Cの戻り値のない関数を呼ぶ

型JSONで `"result": "void"` と指定すると、Cの `void` 関数をAILから文として呼べます。
初期化や状態更新などに使い、架空の戻り値は作りません。引数の型としての `void` は認めません。
文字列・bytes引数の変換領域は、通常の戻り値を持つ関数と同じくC呼出し後に解放します。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_fnv_stream.c --interface language_examples/c_fnv_stream.json -o stream_native.o
py -3 -B ail_chatgpt.py compile-module language_examples/c_fnv_stream_library.ail --object stream_native.o -o stream_library.o
py -3 -B ailc.py language_examples/c_fnv_stream.ail --object stream_native.o --object stream_library.o -o stream_hash
./stream_hash.exe .\input.bin 2166136261
```

この例はファイルを読み込み、8,192バイトずつCの状態を更新して最後にFNV-1a値を取得します。
ファイル読込み自体は全体をメモリに置きます。Cの状態は一つで、処理前に初期化します。
空更新ではAILライブラリの `return;` を使います。空入力と分割境界の前後、1MiB超を含む11入力を
独立Python参照と照合し、元ソースなし・移動後のリンクでも検証しています。速度・メモリ削減の主張ではありません。

#### FNVファイル処理をAIL/Cから再利用する

R345の `hash_file(path: str, seed: int) -> int` は、上のAILライブラリの追加APIです。
ファイルを最大8,192バイトずつ補助関数で読み、Cの更新関数へ渡します。
補助関数から戻る際に、その読込み領域を解放します。呼出しごとにseedで初期化するため、
異なるファイル・seedを続けて処理できます。seedは0～4,294,967,295、範囲外は空ファイルでもValueError。

上の `stream_native.o` / `stream_library.o` を使い、ファイル用の入口を構築できます。

```powershell
py -3 -X utf8 -B ailc.py language_examples/c_fnv_stream_file.ail --object stream_native.o --object stream_library.o -o stream_file
./stream_file.exe input.bin 2166136261
```

CLIはファイル名とseedの2引数で、成功時はハッシュ値を10進表示します。
引数数・seedの値のエラーは終了2、読込みのOSErrorは終了3。エラー時のstdout/stderrは空です。
既存objectは追加APIを含むように再構築してください。

Cから使う場合はライブラリ名専用の依存を構築し、`file_hash` を公開します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/c_fnv_stream.c --interface language_examples/c_fnv_stream.json --c-api-name fnv -o fnv_native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/c_fnv_stream_library.ail --object fnv_native.o --c-api-name fnv -o fnv_stream.o
py -3 -X utf8 -B ail_chatgpt.py compile-library language_examples/c_fnv_stream_api.ail --object fnv_native.o --object fnv_stream.o --name fnv -o fnv_lib
```

生成ヘッダーの `fnv_file_hash(fnv_view utf8_path, int64_t seed, int64_t *out, fnv_error *error)` を呼びます。
成功0、seed範囲外/NULパスは状態1、読込み失敗は状態6。失敗時の*outを保持し、次の呼出しで再初期化します。
元ソースや依存objectを配布せず、`fnv.h` / `fnv.o` / `library.json` だけでリンクできます。
Windowsの日本語パスでのリンクは出力先を作業ディレクトリにし、ASCIIの相対名を使います。
LinuxではPythonを `python3`、実行物を `.exe` なしにします。

範囲ごとにファイルを開き直すため、処理中に変わらないseek可能な通常ファイルが対象です。
単一openのストリームやスナップショットではありません。Cの手動reset/update/finishは共有状態を持つ既存APIです。
同じC APIライブラリの同時呼出しはbusyになります。これは再利用機能の追加で、速度優位やRSS上限の主張ではありません。
Windows/Linuxで26入力×4seedを独立Python FNV-1aと照合し、移動後のAIL/C利用、
空入力の範囲外seed、エラー後の復帰/out保持、入力/生成物不変、既存の手動更新も確認しました。

### Cの8・16・32ビット整数を使う

AILの整数は符号付き64ビットです。C関数の引数・戻り値が `int32_t` または `uint32_t` の場合は、
型JSONでそれぞれ `int32`・`uint32` と指定します。AILソースの型注釈は通常の `int` のままです。
8/16ビット型も `int8`・`uint8`・`int16`・`uint16` と指定できます。

| 型 | 引数の範囲 |
|---|---:|
| int8 | −128～127 |
| uint8 | 0～255 |
| int16 | −32,768～32,767 |
| uint16 | 0～65,535 |
| int32 | −2,147,483,648～2,147,483,647 |
| uint32 | 0～4,294,967,295 |

どの型も変換前に範囲を検査し、範囲外は捕捉可能な `ValueError`、戻り値は符号を保ってAILの `int` へ拡張します。

```json
{"symbol": "native_fnv1a", "params": [["data", "bytes"], ["seed", "uint32"]], "result": "uint32"}
```

この関数のCプロトタイプは `uint32_t native_fnv1a(const unsigned char *data, size_t length, uint32_t seed)` です。
符号付き引数の範囲は−2,147,483,648～2,147,483,647、符号なしは0～4,294,967,295です。
範囲外ならC関数を呼ばず、`ValueError` を発生させます。暗黙の切捨てや周回変換は行いません。
`try` / `except ValueError` で捕捉して次の入力へ進めます。捕捉しない場合は従来どおり
`C <型名> argument out of range` を表示し、終了コード1で停止します。
これはC引数への範囲検査であり、AILの64ビット整数演算の桁あふれ全般を捕捉可能にするものではありません。
戻り値はAILの `int` へ拡張し、例えば `UINT32_MAX` は負数にせず4,294,967,295として返します。
主ソース・追加ソースとも、JSONとC関数の幅や符号が違えばビルド時に拒否します。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_fnv32.c --interface language_examples/c_fnv32.json -o fnv32.o
py -3 -B ailc.py language_examples/c_fnv32.ail --object fnv32.o -o fnv32
./fnv32.exe .\input.bin 2166136261
```

この例は指定した初期値からファイルのFNV-1a 32ビット値を求めます。
範囲外の初期値は捕捉し、`seed must be in 0..4294967295` と表示して終了コード2を返します。
別コンパイルしたAIL関数を経由しても捕捉でき、正常値で再度C関数を呼べます。
この動作を使うには旧版のC/AILオブジェクトを現行runtimeで再構築してください。
FNV-1aは空入力・全バイト値・NUL/改行・8KiB/64KiBの前後・1,048,832バイトを含む12入力を、
独立したPythonの整数演算と照合しています。元ソースなしのAILライブラリ構築、移動後リンク、
上下限と直外側、64ビット極値の拒否、引数の左から一度だけの評価も検査しています。

16ビットの実例はCRC-16（多項式0x1021、反射なし、最終XORなし、初期値指定）です。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_crc16.c --interface language_examples/c_crc16.json -o crc16.o
py -3 -B ailc.py language_examples/c_crc16.ail --object crc16.o -o crc16
./crc16.exe .\input.bin 65535
```

14種類のバイナリ入力（最大1,048,832 bytes）と初期値0/32,768/65,535の全42組を、
独立したPython `binascii.crc_hqx` と照合しました。元ソースなしのAILライブラリを介し、
移動後にリンクしても一致します。範囲外の初期値は説明を表示して終了2を返します。
4つの8/16ビット型は合計131,584個の全表現可能値、直外側とint64極値、混在引数、
幅/符号の不一致、C未呼出し、捕捉後再実行をWindows/Linuxで検証済み。速度改善の測定ではありません。

### Cのboolを直接呼ぶ（R380）

型JSONの引数・戻り値を `bool` と指定すると、Cの `_Bool`、または
`#include <stdbool.h>` の標準 `bool` を直接使えます。AIL側は既存の `int` で、
引数は0/1のみです。他の値はC呼出し前に捕捉可能な `ValueError`、戻り値は0/1になります。
`uint8_t` や `int64_t` をboolの代わりとして宣言することはできません。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/c_bool.c --interface language_examples/c_bool.json -o bool.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/c_bool.ail --object bool.o -o contains_nul
./contains_nul.exe .\input.bin 0
```

例は入力にNULバイトがあれば1、なければ0を表示します。第2引数を1にすると結果を反転します。
空入力・全256値・64KiB境界・1MiB超の入力を独立Python参照と照合し、型不一致、
int64端点/-1/2の事前拒否、元ソースなしの移動再利用、自己完結C APIのエラー後回復を
Windows/Linuxで確認済みです。速度改善やAIL独自のbool演算を追加したものではありません。

### Cの64ビット符号なし値を全ビット受け渡す（R375）

Cの `uint64_t` 引数・戻り値は、型JSONで `uint64_bits` と指定できます。
AIL側の型注釈は `int` です。AILの符号付き64ビット整数を、C側では同じ64ビットの
符号なし値として扱う契約です。ハッシュ値やビットマスクを切り捨てずに渡せます。

| Cのuint64値 | AILのint値 |
|---|---:|
| 0 | 0 |
| 2^63−1 | 9,223,372,036,854,775,807 |
| 2^63 | −9,223,372,036,854,775,808 |
| 2^64−1 | −1 |

引数 `x` はCへ `x mod 2^64` として渡します。戻り値 `u` は `u < 2^63` ならそのまま、
それ以外は `u−2^64` で返します。戻すときは範囲外のunsigned→signedキャストに頼らず、
範囲内の変換と `−1−(UINT64_MAX−u)` で求めます。
[C11委員会草案6.3.1.3](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)の
整数変換規則を踏まえた処理です。
AILの符号なし整数演算を追加したものではなく、AILでの型・表示は従来の `int` です。
8/16/32ビット型の範囲検査は引き続き適用されます。

```json
{"symbol": "native_fnv64", "params": [["data", "bytes"], ["seed", "uint64_bits"]], "result": "uint64_bits"}
```

C関数は `uint64_t native_fnv64(const unsigned char *data, size_t length, uint64_t seed)` です。
符号付き `int64_t` などと宣言が違えばビルドを拒否します。
公開例は、指定した初期値からファイルのFNV-1a 64ビット値を求めます。
通常の初期値14695981039346656037は、AILでは−3750763034362895579として渡します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/c_fnv64.c --interface language_examples/c_fnv64.json -o fnv64.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/c_fnv64.ail --object fnv64.o -o fnv64
./fnv64.exe .\input.bin -3750763034362895579
```

LinuxではPythonを `python3`、実行物を `.exe` なしにします。
CLIの初期値はAILのint64範囲で入力してください。範囲外の十進整数は桁あふれで終了1になります。
例えば `hello` のファイルは−6615550055289275125を表示します。
Cの符号なし値として表示したい場合、その値は11831194018420276491です。

Windows/Linuxで符号の両端、全64ビットの単独位置、固定seedの加算/XORを独立Python整数へ照合しました。
公開ファイル例は12入力×6初期値を直接実行と別AILライブラリ経由の両方で確認。
空・全byte・NUL/改行・8KiB/64KiBの前後・1,048,832 bytesを含みます。
元Cソースなしのライブラリ構築、移動後のリンクとC API consumer、生成物と入力の不変も確認しました。
C APIでも引数・結果は `int64_t` の表現です。元入力objectを削除した後も自己完結ライブラリから呼び出せました。
新規4検査と既存整数/小数/文字列の影響4検査は両OSで成功、skipなし。
現行runtimeでobjectを再構築してください。速度改善・任意Cの安全性・全2^64値の網羅を証明したものではありません。

### ローカルのCヘッダーを使う

型宣言JSONのトップレベルに `"headers": ["crc32.h", "detail/crc_constants.h"]` を指定すると、
Cソースのあるディレクトリーから、列挙したファイルの内容を一時ビルド領域へコピーします。
`#include "crc32.h"` のように引用符で読み込み、ヘッダーがさらに使うローカルヘッダーも列挙します。
JSONの場所ではなく、Cソースの場所が基準です。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_headers/checksum.c --interface language_examples/c_headers/checksum.json -o checksum.o
py -3 -B ailc.py language_examples/c_headers/checksum.ail --object checksum.o -o checksum
./checksum.exe .\input.bin
```

この例はファイル全体のCRC-32を10進整数で表示します。認証用のハッシュではありません。
空入力、全256バイト値、改行/NUL、8KiB・64KiB前後、1,048,832バイトを含む11入力を
Pythonのzlib参照と照合しています。Cソース・JSON・ヘッダーを削除した後のAILライブラリ構築と、
オブジェクトを別の場所へ移動した後のリンク・実行も検査対象です。速度優位の測定はしていません。

パスは英数字・`_`から始まる各成分に英数字・`_`・`-`・`.`を使い、`/`で区切る相対パスです。
拡張子は `.h` または `.inc`。絶対パス、`..`、重複、大文字小文字だけの違い、
Windowsの予約名、末尾が`.`の成分、ファイルとディレクトリーが衝突する宣言は拒否します。
解決先がCソースのディレクトリー外になる参照も拒否します。

宣言ヘッダーの内容hashは生成シンボルに含めます。元ファイルを後で変更しても、
生成済みオブジェクトの内容は変わりません。コンパイルは取り込んだコピーを読み、
全依存をそのコピーまたはコンパイラー既定のシステムヘッダーに照合します。
このCビルドでは環境変数 `CPATH`・`C_INCLUDE_PATH`・`CPLUS_INCLUDE_PATH`・`OBJC_INCLUDE_PATH` による
暗黙の追加検索パスは使いません。システムヘッダーの内容固定やCコードの安全性を保証する仕組みではありません。
追加Cソースは次のように明示できます。自動収集や任意の外部ライブラリのリンクは未対応です。
旧オブジェクトは現行版で再構築が必要です。

### 複数のCソースを一つのライブラリにする

型宣言JSONのトップレベルに `"sources": ["crc.c", "detail/update.c"]` を指定します。
各 `.c` を別々の翻訳単位としてコンパイルし、再配置可能な一つのオブジェクトへ結合します。
主ソースには公開関数の宣言が必要です。定義は主ソースまたは追加ソースに置けます。
追加ソースにはJSONの公開関数プロトタイプを挿入し、定義との型の食い違いをコンパイル時に拒否します。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_sources/api.c --interface language_examples/c_sources/api.json -o split_crc.o
py -3 -B ailc.py language_examples/c_sources/checksum.ail --object split_crc.o -o split_crc
./split_crc.exe .\input.bin
```

追加ソースのパスは主ソースのディレクトリー基準です。ヘッダーと同じ相対パス規則で、拡張子は `.c` に限ります。
主ソース自身の再指定、ヘッダーとのパス衝突、ディレクトリー外への参照は拒否します。
ソースとヘッダーの内容をビルド前に取り込み、そのhashを公開シンボルの識別に含めます。
各ソースは自身のディレクトリーと取り込んだファイルのルートから宣言ヘッダーを参照できます。
`.c` の `#include` は使わず、共通宣言を列挙したヘッダーへ置いてください。

各翻訳単位の `static` な状態は独立します。JSONの公開関数だけを内部名へ変換するため、
それ以外の外部シンボルには他ライブラリと衝突しない名前が必要です。任意のCシンボルの自動分離は行いません。
内部ヘルパーの翻訳単位間の型一致には、通常のCと同じく共通ヘッダーを使ってください。
コンパイル・結合に失敗した場合、出力オブジェクトとメタデータは作成しません。
生成後は元ソース・ヘッダーがなくても、AILライブラリからの呼出しや移動後のリンクができます。
この例はCRCの処理を分割したもので、速度改善を主張するものではありません。

### 構築済みの静的Cライブラリを使う（R367/R368）

型宣言JSONへ `"archives": ["lib/example.a"]` を加えると、Cアダプターから参照する
静的ライブラリのメンバを生成オブジェクトへ取り込めます。ライブラリの関数を直接JSONの公開名にせず、
供給元のヘッダーを使う短いCアダプターで呼び出します。同じGCCターゲットの通常の `.a` が対象です。

```powershell
# 既存の分割C実装を一時的なarchiveへ構築し、再利用オブジェクトだけ残す例
py -3 -X utf8 -B language_examples/c_archives/build.py -o archive_crc.o
py -3 -X utf8 -B ailc.py language_examples/c_archives/checksum.ail --object archive_crc.o -o archive_crc
./archive_crc.exe ./input.bin
```

Linuxでは `py -3` を `python3`、実行名を `./archive_crc` に替えます。
構築には既存GCCと、その `-print-prog-name=ar` が返すarchiveツールが必要です。
生成後の `.o` と `.o.json` は、元の `.a`・Cソース・ヘッダーなしで移動して再利用できます。

archiveの相対パスは主Cソースのディレクトリー基準です。外への解決、欠落、不正な拡張子、
重複と他入力とのパス衝突を拒否します。全archive内容を先に固定し、そのhashを公開識別子へ含めます。
複数archiveはlinker groupで解決し、循環参照にも対応します。参照されないメンバは取り込みません。
別ファイルに依存するthin archiveは非対応です。archive内部の型・メモリ安全性の証明や、
外部Cシンボルの自動分離は行いません。アダプターとライブラリのABIは正しい供給元ヘッダーで合わせます。
R368では `--c-api-name` を指定したarchiveのC API再公開にも対応しました。
malloc/calloc/realloc/free/fopen/fclose/_wfopenの参照を、そのC APIの資源管理へ結びます。
選択されたメンバによる独自allocator定義やexit/abort/外部longjmpは拒否します。
確認したGCCの別名も対象ですが、任意バイナリの資源管理・安全性を証明する機能ではありません。
コンパイラ実装が変わったため、以前のAIL/Cオブジェクトは元ソースから再構築してください。

```powershell
py -3 -X utf8 -B language_examples/c_archives/build.py --c-api-name checksum -o archive_api.o
py -3 -X utf8 -B ail_chatgpt.py compile-library language_examples/c_archives/library.ail --object archive_api.o --name checksum -o checksum-library
gcc -std=c11 -O2 -I checksum-library language_examples/c_archives/consumer.c checksum-library/checksum.o -lm -o consumer.exe
./consumer.exe
```

Windows/Linuxで、元入力なしの移動・再利用、独立CRC参照、1MiB超、エラー後の正常呼出し、
返却した所有バッファの保持、2つの名前空間、WindowsのUnicodeファイルとimport参照を確認しました。
nm/objcopyの実体をhash固定して前後で照合します。生成ランタイム自身のlongjmpと、
archiveで選択された外部ジャンプを区別します。未選択の危険メンバは取り込みません。
資源登録数ゼロ、libc内部の残留、RSS改善、速度改善はこの機能検査からは証明しません。

Windows・Linuxで各4新検査と既存18検査が成功しました。独立zlib参照との1MiB超を含む全出力、
元入力削除後のAILライブラリ経由・移動後の再利用、循環参照、未使用メンバの除外、
archive内容変更による識別子変更、不正入力の拒否を確認しました。公開構築例も両OSで4入力が一致しました。
機能追加であり、速度改善の測定や採用ではありません。

### C単体とAILからの再利用を比較する

`c_headers_workflow/prepare.py` は、同じCRCヘッダーを使うC単体版とAIL+C版を、既存の候補生成・
独立検査・資源測定・採否・配布検証へつなぐ契約を作ります。高速化を前提とするレシピではありません。

```powershell
py -3 -B language_examples/c_headers_workflow/prepare.py .\crc-source --bytes 4194304
py -3 -B workflow/vibe/vibe.py build --contract .\crc-source\command.json --selector workflow/selector --mode speed --max-memory-mib 64 --budget-seconds 300 --out .\crc-result
Get-Content .\crc-source\request.txt | py -3 -B workflow/vibe/vibe.py run .\crc-result\app\result.json
```

出力先は未作成の別ディレクトリーを指定します。LinuxではPythonの呼出しを `python3` に替え、
最後は `printf 'workload.bin\n' | python3 -B workflow/vibe/vibe.py run crc-result/app/result.json` で実行できます。
準備する仕事は、標準入力のUTF-8パス1行（前後空白なし）で指定したファイルを読み、
CRC値を1行出力するものです。読めないファイルは終了3。測定入力の大きさは1～16MiBに限定します。
16MiBは測定用ファイルの生成上限で、コマンド自体に実装したサイズ上限ではありません。
コンパイラーPythonソースと宣言ヘッダーを固定コピーし、元版と候補の出力は別のzlib検査器で照合します。
Windows/Linuxで候補生成・両実装の資格検査・移動後検証を実行し、空入力だけ一致する誤実装の拒否も確認しました。

Linuxで4MiB・64MiBメモリ上限・交互12対を実行した結果はC単体版を維持しました。
候補は機能検査に通りますが、速度改善は確認できずRSSも増えました。生の資源値・前後A/A校正・費用・
移動後14ケースの検査結果は `c_headers_workflow/comparison_blocking_wait_linux_20261001.json` に保存しています。
記録中の一時パスと生成物hashは実行当時のもので、測定後に一時コピーを解放しています。
この仕事・機械の比較であり、工程別割合・ハードウェア上限・全用途最適性の根拠ではありません。

複数Cソース版を比較する場合、準備コマンドへ `--layout sources` を追加します。
`crc.c` と `detail/update.c` をC単体版とAIL+C版の両方に使い、共通ヘッダー・型JSON・
コンパイラーを含めて固定コピーします。独立検査器は同じzlib参照です。
比較から移動後検証まで実行し、一時ビルドを残さず結果JSONだけ保存するには次を使います。

```bash
python3 -B language_examples/c_headers_workflow/compare.py --layout sources --bytes 4194304 --out crc-comparison.json
```

出力先の親ディレクトリーは作成済みで、JSONは未作成にしてください。実行前に出力先を確保し、
既存ファイルを上書きしません。通常の実行失敗も `status: failed` として保存します。
実行の中断やディスク障害まで結果保存を保証するものではありません。
R294のLinux・4MiB・交互12対はC単体版を維持しました。wall中央値38.664ms対40.844ms、
最大RSS中央値4,736KiB対8,960KiB。前後A/Aのwall雑音8.045%に対して改善の条件を満たしません。
準備・ビルド・資格検査・比較・配布・移動後検証・一時解放まで26.539秒でした。
起動前後の事前読込み・hash取得、報告保存、編集、先行検査、モデルの費用は含みません。
生の結果は `c_headers_workflow/comparison_sources_linux_20261001.json` に保存しています。
レポート中の一時パスとソースhashは実行当時のものです。出力先の事前確保はこの計測後に追加し、
両環境の境界検査で確認しました。全仕事への速度優位や費用回収は確認していません。

最初の `comparison_linux_20261001.json` は診断用です。Linux単一プロセス計測器に、
`wait(timeout)` の終了確認と資源ファイル読込みをwallへ含める問題が見つかったため、速度根拠から除外しました。
修正版は終了通知で待機し、資源読込み前に時計を止めます。timeout/中断では自身のプロセス群を回収します。
wallの範囲はアプリとGNU timeの起動～終了で、検査・資源ファイル解析を含みません。
同じ旧計測器による過去のwall比較も、性能の根拠にする場合は再測定が必要です。

この例の工程計測（Linux）は次で実行します。

```bash
python3 -B language_examples/c_headers_workflow/profile.py --bytes 4194304 --cycles 6
```

R292の `c_headers_workflow/phases_linux_20261001.json` は、独立zlib参照と全24回の出力を照合した記録です。
計測版の転送（確保・コピー・解放）はwallの中央値7.18%、すべて除去できると仮定したAmdahl上限は1.077倍でした。
コピー単体は5.95%、独立したlibc memcpy参照に対する達成速度は約106.2%で、同程度です。
この参照は物理的なメモリ帯域上限ではありません。原版同士の揺れは最大20.5%であり、速度改善は判断できません。
CRC本体は計測版wallの約78.8%ですが、この小さなCRC例の割合を他のソフトウェアへ一般化できません。
時計の追加自体も測定へ影響します。最適化候補は構築・採用していません。
コピー省略はポインタの別名関係や所有権に関わるため、先に明示した借用契約が必要です。
保存した6対の計測後、工程合計がwall以下である検査を追加しました。保存済み6レコードの事後検査と、
検査追加後のLinux 2対の実行は成功しています。記録のソースhashは計測時のものを保持しています。

R327では、上記のC単体と通常コピー接続に、明示借用接続の第三候補を追加できます。

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/compare.py --borrowed-bytes --bytes 4194304 --out NEW.json
```

ヘッダー版が既定です。複数Cソース版には `--layout sources` を加えます。準備だけ行う場合も
`prepare.py NEW_DIRECTORY --borrowed-bytes` を使えます。生成した `checksum_borrowed.json` は、
元のC関数の `bytes` 引数だけを `borrowed_bytes` へ変えた宣言で、構築用hashに含めます。
Cは呼出し中だけ読む契約を守る必要があります。通常コピー接続とC単体の経路は維持します。
両レイアウト・両OSで3候補の構築、個別配布と移動後実行を検証しました。

独立zlib検査は旧14ケースから20ケースへ拡張し、1MiB前後・4MiB・16MiB・16MiB+1も照合します。
全有効入力の不変を検査し、小さい入力だけ正しい候補や入力改変を拒否します。16MiB+1は成功です。
配布CLIの検査では固定入力を変更せず照合します。さらに大きい入力や各OSのfile-size幅上限は未資格です。

R327の4MiB・速度優先比較は両OSでC単体を維持しました。全3候補が20ケースを通り、
原本・構築場所・資格場所を元パスで参照不能にした移動後検証も成功しました。
借用対Cのwall中央値はLinux54.287対53.495ms、Windows80.146対73.186msで、安定した改善は未確認です。
AIL接続のRSS/peak working set中央値はコピー/借用がLinux8960/4864KiB、Windows17720/13680KiBでした。
候補ごとに異なる交互測定を行っているため、このコピー/借用の時間比を直接の速度改善とは扱いません。
借用対Cの順序別wall savingQ1は-10.5421%/-17.3017%、A/A noise7.8856%/21.0613%。採用条件を満たしません。
比較総費用はLinux85.452秒/Windows141.390秒。物理roof、通常版の工程割合、速度予測は未証明のままです。
記録は `c_headers_workflow/comparison_borrowed_linux_20261001_r327.json` とWindows同名記録です。
従来のR292/R294記録は測定当時のコードhashとして保持します。コンパイラ選択は共通の選択関数を使い、
実際のパスと識別情報、Cソース/ヘッダー/コンパイラソースの前後一致も検査しています。

### CRCのファイル読込みを診断する

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/read_profile.py --out NEW.json
```

R329の診断は借用接続の4MiB CRCを通常版・計測版時計OFF/ON・C参照時計OFF/ONで実行します。
各経路の独立20ケース、順序均衡測定、前後A/A、全出力と入力不変を検査します。
read_bytesの容量・拡張回数・累積要求と工程時間を記録する機能で、最適化の採用は行いません。
容量境界ではEOF確認の前に4MiBから8MiBへ拡張していました。累積要求は同時使用量ではありません。
計測版の読込み関連割合はLinux8.1982%/Windows5.0899%、全除去の条件付き上限1.08930/1.05363倍。
同量のC参照に対するfread達成率は94.0166%/67.2718%でした。一部の時計校正が失敗したため、
通常版の工程割合・物理上限・速度改善は未証明です。参照の窓の違い、資源値、費用は
[現行説明書のR329](README_AUTO_ENTRY_JA.md)と `c_headers_workflow/read_profile_*_20261001_r329.json` を参照。
既存結果を上書きせず、一時実行ファイルは解放します。読み取りエラーで成功記録を捏造しません。

### EOF前の不要な容量拡張を比較する

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/compare.py --eof-reader --mode balanced --bytes 4194304 --out NEW.json
```

現行AILと、満杯時にEOFを先に確認するAIL候補を、両方とも借用CRC接続で比較します。
独立20ケース、交互測定、前後A/A、資源判定、ソースを隠した移動後検証を行います。
既定コンパイラは変更せず、比較した用途の実行物だけを選択します。新しい出力パスを指定してください。
R330の4MiB入力ではWindowsのピークメモリ中央値が13680から9592KiBとなり、最終確認で候補を選択しました。
Linuxは4864KiBで差がなく現行を維持しました。速度優位は未証明です。
容量境界、0xff、エラー、複数読込みの独立性は実バイト列で確認しています。
測定範囲・費用・採否は[現行説明書のR330](README_AUTO_ENTRY_JA.md)と
`c_headers_workflow/comparison_eof_*_20261001_r330.json` を参照してください。

### CRCの計算工程を値付けする

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/crc_profile.py --out NEW.json
```

通常の借用CRC、同じ計測実行物の時計OFF/ON、独立zlib参照を実行します。最適化は採用しません。
R331の4MiBでは計測版native割合がLinux85.6624%/Windows65.2181%、全除去の条件付き上限6.97464/2.87506倍。
同量zlibの達成済み処理量に対する比は2.5869%/6.0891%でした。物理上限や通常版の正確な割合、速度予測は未証明です。
この診断を根拠に、R332で機械語に残る8回ループの展開候補を比較しました。
LinuxはC11 UTC時計、WindowsはQPCで、計測窓・参照process・cache状態が異なります。
校正・境界・費用・失敗記録は[現行説明書のR331](README_AUTO_ENTRY_JA.md)を参照してください。

生成された機械語を確認し、CRCの固定8回ループを展開する候補も比較できます。

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/compare.py --crc-unroll --mode balanced --bytes 4194304 --out NEW.json
```

R332の4MiB実例は独立zlib照合・交互測定・A/A・移動後検証を通り、
速度比の中央値がLinux1.43062倍、Windows1.33054倍でした。メモリ中央値は変わりません。
現行AILの借用CRCからの比較で、EOF候補との合算結果ではありません。
`--layout sources` なら分割Cソース版も検査できます。`--eof-reader` との同時指定は拒否します。
コピーした候補を変更し、生成された実行ファイルのCRC命令列を記録します。
保存するのは結果JSONと再構築用コードで、比較中の一時appは検証後にcleanupします。
既定コンパイラや任意の機械語を一括変更する機能ではありません。
対象機械・入力で再測定してください。費用と適用範囲は[現行説明書のR332](README_AUTO_ENTRY_JA.md)を参照してください。

ループ展開版を基準として、固定256要素のCRCテーブル版も比較できます。

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/crc_profile.py --crc-unroll --out PRICE.json
py -3 -X utf8 -B language_examples/c_headers_workflow/compare.py --crc-table --mode balanced --bytes 4194304 --out NEW.json
```

R333は計算工程を再測定してから実装し、4MiBの最終速度比中央値はLinux1.92589倍、Windows1.46625倍でした。
前回のループ展開版との比較で、R332の倍率を掛け合わせません。出力は独立zlib参照と一致し、
両布局の資格と移動後実行も確認しています。性能比較はheaders版のみです。
Windowsは観測noiseが大きく、wall基準は通過しましたがCPU改善の校正とメモリ改善は未確認です。
物理上限・全用途の速度優位は未証明です。`--crc-unroll` / `--eof-reader` との同時指定は拒否します。
原本と既定compilerは維持し、比較中の一時appは検証後cleanupします。費用と適用範囲は
[現行説明書のR333](README_AUTO_ENTRY_JA.md)を参照してください。

テーブル版を基準に、8バイト処理候補も独立に比較できます（R336/R337）。

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/crc_profile.py --crc-table --out PRICE.json
py -3 -X utf8 -B language_examples/c_headers_workflow/compare.py --crc-slicing --mode balanced --bytes 4194304 --out NEW.json
```

Linuxの計測版では計算が約52%、全除去の条件付き上限2.084倍、zlib参照の処理量比10.65%でした。
Windowsは工程時計の校正が失敗し、通常版の内訳へ推定していません。物理上限や速度予測は置いていません。
この診断から実装した候補は、表容量1→8KiBの交換条件があります。
4MiB/header比較の速度比中央値はLinux1.88652倍、Windows1.35896倍。
Linuxの選択処理は候補を採用。Windowsはworking set中央値が13644→13652KiBに増えたため前回版を維持しました。
原本、既定compiler、次節のCRCライブラリは変更しません。速度比を過去の結果と掛け合わせません。
両OS・両布局の独立資格と移動後実行を確認しています。性能JSONと計算本体を含む追加機械語記録は別々に保存しました。
この性能比較コマンドは診断した4194304bytesだけを許可し、ほかの候補フラグと同時指定できません。
費用・校正・適用範囲は[現行説明書のR336/R337](README_AUTO_ENTRY_JA.md)を参照してください。

R338からCRC比較の既定値は速度優先です。独立出力一致と64MiB上限を必須にし、上限内の小さなメモリ増は許容します。
上の歴史的な比較は `--mode balanced` で再現します。現在の速度優先比較は次です。

```powershell
py -3 -X utf8 -B language_examples/c_headers_workflow/compare.py --crc-slicing --mode speed --bytes 4194304 --out NEW.json
```

Windows再測定は速度比中央値1.31448倍、working set最大13660KiBで上限内でしたが、
一方の実行順の改善下位が原版A/Aの揺れを超えず、今回は採用を見送りました。独立資格・移動後実行は成功しています。
`--mode memory --max-wall-seconds SECONDS` でwall上限内の省メモリも指定できます。性能は今回未測定です。
測定の揺れを除く条件は保持します。[現行説明書のR338](README_AUTO_ENTRY_JA.md)に基準・資源・失敗・費用を記録しました。

R340からWindows selectorは事前と各batchのCPU負荷を既定0.5 core以下に制限します。
超過時はinvalidとして生記録を残し、候補を採用しません。別上限は測定前に
`workflow/selector/select.py time SPACE.json --max-external-cpu-cores CORES` で宣言できます。
事前値は機械全体、batch値はアプリ/観測親を差し引いた外部CPUです。上限内でもA/Aと両順序の条件は必要です。
実機の事前確認は1.23403 coreで拒否し、今回速度を再測定していません。旧R338結果は保持しています。

R341から新規採用は、候補選び後に原版と候補一つを新しい24組で直接確認します。
実行順は両順序12組ずつを無作為化し、測定前に保存。各順序の改善回数を検定し、
9指標×両順序の多重比較を補正します。引き分けやA/Aノイズ以下は改善に数えません。
CLIは `workflow/selector/select.py time SPACE.json --resources --confirmation`。
auto.tuneは最終比較で自動適用し、計画のない旧結果を新基準の合格に読み替えません。
独立したblockと途中打切りなし等を前提にする、一回の確認の有意水準0.01です。
実機の誤採用率や全入力の正しさを保証する数字ではありません。
Linuxの同一プログラム対照は誤採用なし、233回の出力照合成功。
根拠・費用・未証明の条件は[現行説明書のR341](README_AUTO_ENTRY_JA.md)を参照してください。

R347は計算後の値も検証します。有限の標本でも節約四分位・A/A中央値・利用回数や
切替費用を含む予測がInfinity/NaNとなる場合は、ValueErrorで採否を拒否します。
非有限値を節約・費用回収の根拠に使いません。合成した数値境界の検査で、速度測定ではありません。
境界4検査は `workflow/selector` から `py -3 -X utf8 -B -m unittest test_overall` で確認できます。

R352では資源付きstdio比較の入力別記録を保存し、既存のblock集計と厳密に照合します。
balancedでは、一部入力のwall/CPU平均・メモリピークや入力別最大値の悪化も拒否します。
speed/memoryの事前宣言した交換条件は維持し、入力別悪化を表示します。
記録のない旧方式では入力別非悪化を未証明と表示します。実機独立性・他入力への一般化は未証明です。
新しい入力別条件は `workflow/selector` の `test_input_regression` / `test_confirmation` で検査します。

現行R362の採用判定を変更したAIコードの独立検査はv5を使います。旧v4と保存済み成績は保持します。

```powershell
py -3 -X utf8 -B language_examples/ai_coding/calibration_v5.py workflow/selector/overall.py
```

旧v4の32項目に、現行基準・補正件数・共有観測・切替費用の反例を加え、v5は全37項目合格で終了0。
全4,096符号パターンによる確率照合と候補内容不変も確認します。
欠けた事前計画/identity、11勝1引分け、偽の保存済み成功も拒否します。
旧v2/v3は過去の試行用に保持しています。信頼済みPythonの機能検査で、実機独立性や最高効率の証明ではありません。

R363以降のCLI/HTTP最終確認は、測定前に取得系列を宣言し、各実行の順序・取得区間・観測者PID・
指標・最大値を保存した採否資料へ結び付けます。記録の複写・欠落・取り違え・数値の不一致を拒否します。
記録のない旧形式の取得根拠は未証明です。整合した記録だけでも、観測の独立性や時計精度は証明しません。
取得部分は、候補の計画生成器に依存しない固定データを使う次の検査で確認します。

```powershell
py -3 -X utf8 -B -m unittest test_acquisition_evidence
```

R364の新規確認は取得版2です。入力別資源表のSHA-256を各実行で固定し、採否に使う表と照合します。
同じ合計時間を保つ表の差替えや欠落、型の変更を拒否し、取得後の表の変更へハッシュは追従しません。
familyの予約内容にも取得版を固定します。入力表のない契約・現在のHTTP要求別資源・旧版1は未証明です。
ハッシュの整合性は実行の真実性・観測の独立性・時計精度の認証ではありません。

```powershell
py -3 -X utf8 -B -m unittest test_input_acquisition
```

R365の実行器は、取得開始・終了の整数nsにアプリ時間が収まるか保存前に確認します。
CLIは平均×計測繰返しと最大round時間、HTTPは1サービスの起動＋処理＋終了を照合します。
不一致は取得区間・回数を理由に残して拒否します。秒数は厳密な整数比で比較し、許容幅を増やしません。
保存済みJSONの遡及保証や、時計精度・観測の独立性の証明ではありません。
Windows実HTTP64回と複数入力の実プロセスを確認しました。Linux実HTTPは委譲cgroupの権限不足で未検証です。

```powershell
py -3 -X utf8 -B -m unittest test_acquisition_wall
```

R369/R370の現行採用基準は3です。CLI取得版3では、比較48回に加えて前後A/A各6回の
入力別表を記録へ結合し、同じ `fsum_v1` で平均とラウンド最大を厳密に照合します。
比較だけを結合する旧版2は新規CLI採用の根拠になりません。HTTPはサービス全体の取得版2です。
Windows/Linux各60回の実プロセス取得を確認しました。機能検査であり、速度採用の証拠ではありません。
R371は保存後の採否でも、CLIの平均wall×繰返し数・ラウンド最大とHTTPの全サービスwallが
取得区間に収まるか再検査します。旧基準2の保存記録へ遡及した保証ではありません。
詳細・丸め境界・未証明範囲は[現行採用基準](README_AUTO_ENTRY_JA.md#新規採用に必要な根拠を固定するr369r371現行基準)を参照してください。

### 行番号付けのWindows参照比較（R366）

```powershell
py -3 -X utf8 -B language_examples/compare_number_stream.py -o "$env:TEMP/number-stream-fresh.json"
```

未作成の結果ファイルを指定します。公開AILと独立C参照の全byte検査後、24組確認へ進みます。
R366は8MiB級2入力の全出力が一致しましたが、事前負荷3.76コア相当が固定上限0.5を超え、
比較未実施・採用なしです。閾値を緩めて再実行していません。工程割合・Amdahl上限・roof達成率は未測定です。
file-backedバッチの入口で、pipeの逐次応答や全用途の性能を保証しません。
詳細と失敗記録は[自動入口の説明](README_AUTO_ENTRY_JA.md)を参照してください。

R372の `--verify-only` は、負荷条件を満たさなくても実行できる全出力・移動後の機能確認です。
比較計測と採用判定は実行せず、結果はverified/採用なしと保存します。

```powershell
py -3 -X utf8 -B language_examples/compare_number_stream.py --verify-only -o "$env:TEMP/number-stream-verify-fresh.json"
```

両実装の8MiB級二入力は、別cwdへ移した後も独立参照と全byte一致しました。
同じWindows実機での確認です。通常比較も現行基準3へ接続し、結果表示は採用判定へ追従します。

R373ではLinuxの通常時計/RAW時計を同じ固定算術で同時記録しました。短い診断3組は幅以内でしたが、
同じ16MiB・6周期の工程診断は実行中の時計状態変化で不合格です。価格・速度採用は未確定。
WSL一時JSONの未回収も残し、今後の失敗観測を標準出力へ追加しました。
持続する結果保存にはWindows側Tempを使えます。[時計診断と保存方法](README_AUTO_ENTRY_JA.md#linuxの時計域を同時記録するr373診断のみ)を参照してください。

R374では、入力時間を平均へ丸める前の厳密な合計も取得区間へ照合します。
固定ファイルサイズは独立標本の検定から外し、固定した整数差として判定します。
サイズ縮小の採用は維持し、変動・小数・最大値の差替えは拒否します。
詳細と適用範囲は[保存記録の厳密検査](README_AUTO_ENTRY_JA.md#保存記録の時間合計と固定サイズを厳密に扱うr374)を参照してください。

### 改善済みCRCを別のAILプログラムで使う

テーブルCRCをCオブジェクトとして構築し、AILの `crc32(data: bytes) -> int` を
別コンパイルして再利用できます。AIL_CURRENTから、新しい出力ディレクトリを使います。

```powershell
New-Item -ItemType Directory crc_build
py -3 -X utf8 -B language_examples/c_headers_workflow/build_crc_library.py --out crc_build/native_crc.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/c_headers_workflow/crc32.ail --object crc_build/native_crc.o -o crc_build/crc32.o
py -3 -X utf8 -B ailc.py language_examples/c_headers_workflow/crc_file.ail --object crc_build/crc32.o --object crc_build/native_crc.o -o crc_build/crc_file
./crc_build/crc_file.exe input.bin
```

Linuxでは`.exe`なしで実行します。標準出力はCRC-32の非負整数です。
引数不足/過剰は終了2、ファイル読込み失敗は終了3で、いずれも出力しません。
この例はファイル全体をメモリへ読みます。ストリーム処理ではありません。

両方の`.o`と対応する`.o.json`を一緒に保持すれば、元のC/ライブラリAILソースなしで
別のAILプログラムへリンクできます。同じOS・コンパイラ契約で使い、契約変更時は再生成します。
Windows/Linuxで移動後の長入力・境界・エラー処理を検証しています。
R333の速度比は以前の固定負荷の測定値で、ライブラリ化による追加速度向上は未測定です。

8バイト処理版も `--implementation slicing` で明示選択できます（R339）。
新しい出力ディレクトリで、上のnative object構築コマンドにこの指定を追加し、同じAILライブラリとconsumerをリンクします。
APIは `build(output, implementation='table')`、省略時のtableを維持します。
両OSで直接呼出し・slice・型付きライブラリの移動後実行、0～17と長入力のzlib一致を検証しています。
8KiB表の交換条件とR338のWindows速度判定失敗は維持し、今回のライブラリ化による追加速度効果は未測定です。

### 増分CRCでファイルを64KiBずつ処理する

R342の `crc32_stream.ail` は `crc32_update(previous: int, data: bytes) -> int` と
`crc32_file(path: str) -> int` を公開します。previousは0～4294967295の直前のCRCで、
初回は0を渡します。空bytesでは同じ値を返し、範囲外のpreviousは空bytesでもValueErrorです。
分割位置によらず、連結した全bytesのzlib.crc32と同じCRC-32を返します。

```powershell
New-Item -ItemType Directory crc_stream_build
py -3 -X utf8 -B language_examples/c_headers_workflow/build_crc_library.py --implementation slicing --out crc_stream_build/native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/c_headers_workflow/crc32_stream.ail --object crc_stream_build/native.o -o crc_stream_build/stream.o
py -3 -X utf8 -B ailc.py language_examples/c_headers_workflow/crc_stream_file.ail --object crc_stream_build/native.o --object crc_stream_build/stream.o -o crc_stream_build/crc_stream
./crc_stream_build/crc_stream.exe input.bin
```

Linuxでは`.exe`なしで実行します。tableを使う場合は `--implementation slicing` を省きます。
両objectとmetadataは同じOS・コンパイラ契約で移動・再利用できます。
引数不足/過剰は終了2、ファイル読込み失敗は終了3で、いずれも出力しません。

既存の範囲読込みで64KiBずつ読み、各回のbytesを関数から戻る際に回収します。
範囲ごとにファイルを開き直すため、処理中に変化しない、seek可能な通常ファイルが対象です。
単一のopenを保持するストリームや、同時変更に対する一貫したsnapshotを提供するものではありません。
Windows/Linuxで移動後の0～17bytes、64/128KiB境界、16MiB+1、CRCが0/4294967295になる入力、
複数ファイルの再呼出しと独立zlib一致を確認しました。
両翻訳単位の計測用ビルドで、3回処理後の追跡確保・ファイル・arena frame残量は0でした。
これはRSSや速度の測定ではありません。詳しい検査範囲は現行説明書のR342を参照してください。

### 整数配列をCへ渡す

JSONの引数型を `"list"` とすると、AILの平坦なint64整数列をCの読み取り専用ポインタと
要素数へ渡せます。要素数はバイト数ではありません。C側の例：

```c
int64_t lower_bound(const int64_t *values, size_t count, int64_t key);
```

配列の領域は呼出し中の借用です。C側は書き換え・解放・呼出し後の保持をしてはいけません。
空配列のポインタはNULLの場合があり、要素数0では参照しないでください。
負数・NULLと非ゼロ長・要素数からバイト数への桁あふれは、アダプターがC呼出し前に拒否します。
非NULLポインタの有効性をOSに問い合わせて検査するものではありません。
float・文字列・バイト列・行列・レコードの配列はこの入口では拒否します。
配列の一部を `ail_c_bytes_view` で返す場合は、AILが呼出しから戻る前にコピーして所有します。

`c_integer_series.c/.json/.ail` は、ファイルから整数列を読み、閾値を超える件数、
ソート後の二分探索位置、要素数を出力する実例です。二分探索関数は昇順の入力を前提とします。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_integer_series.c --interface language_examples/c_integer_series.json -o integer_native.o
py -3 -B ailc.py language_examples/c_integer_series.ail --object integer_native.o -o integer_series
./integer_series.exe ./integers.txt 7
```

ブロック構文の補助関数も `fn copied(values: list) -> list { let result = [x for x in values]; return result; }`
のように書けます。`fn pair(a: int, b: int) -> list { return [a, b]; }` や `return []` も使えます。
直接返すリストの要素は平坦なint64整数に限り、整数式と数値を返す関数呼出しを含め左から評価します。
小数を整数へ黙って変換したり、内側の配列を数値として返したりはしません。
呼出し結果をC配列引数へ直接渡す場合も一度だけ評価し、左からの引数順を保持します。
検証では空・int64端点・重複値・65,537要素までの独立Python照合、元ソースなしの
C→AILラッパー→入口という別コンパイルと移動、混合引数の評価順、入力不変を確認しました。
WindowsとLinuxで検証しています。これは機能追加であり、高速化や任意C関数の安全性の主張ではありません。
コンパイラの実装識別が変わるため、既存の再利用オブジェクトは再生成してください。

### 小数配列をAIL関数へ渡す

`fn total(values: list[float]) -> float` のように、小数配列を読み取り専用で受け取れます。
普通の関数、別コンパイル、再利用 `.o`、Cから呼ぶ `compile-library` で同じ型を使います。
配列の名前を渡し、整数配列からの暗黙変換はしません。値と長さは呼出し中の借用で、
引数の再代入、要素の変更、append/pop/sortなどの変更操作は拒否します。
別名への単純代入も未対応です。加工する場合は新しい配列へ要素をappendしてコピーします。

```ail
fn total(values: list[float]) -> float {
    let result=0.0;
    for value in values { result=result+value; }
    return result;
}
```

`float_series.ail` は合計・範囲内件数・添字取得・関数間の受渡しをまとめた実例です。
`float_series_main.ail` は空白区切りの小数ファイルを読み、範囲件数・合計・全要素数を出力します。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/float_series.ail -o float_series.o
py -3 -B ailc.py language_examples/float_series_main.ail --object float_series.o -o float_report
./float_report.exe ./floats.txt -1.5 2.25
```

`for` と `enumerate` の要素はfloatとして扱い、len/sum/min/maxや負数添字も使えます。
範囲外は `IndexError` で捕捉できます。小数配列を受けたAIL関数から、C引数型
`float_list` を持つCオブジェクトにもそのまま渡せます。
Windows/Linuxで65,537要素の実ファイル、元ソースなしの依存オブジェクトの移動、
入力不変、明示コピー、例外後の再呼出しを検証しています。演算順を変えた集計との一致は保証しません。
Python用の `compile_fn` でも `list[float]` 引数に対応し、floatのみのlist/tupleまたは
`array('d')` を受け取り、整数やboolを混ぜた列は拒否します。既存 `.o` は再生成してください。

### 小数配列を返す

`-> list[float]` を宣言すると、局所配列・借用引数・別関数の返却値をコピーして返せます。
返却後は呼出し側が配列を所有し、元配列の変更や後の呼出しから独立して保持できます。
`return []` や `return [1.25, -0.0]` も使えます。非空リテラルは全要素がfloatである必要があり、
整数との混在、行・入れ子は未対応です。R567ではfloat内包表記も使えます。

```ail
fn scaled(values: list[float], factor: float) -> list[float] {
    return [value * factor for value in values];
}
```

実例 `float_transform.ail` と `float_transform_main.ail` はファイル中の全要素を指定倍率で変換します。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/float_transform.ail -o float_transform.o
py -3 -B ailc.py language_examples/float_transform_main.ail --object float_transform.o -o float_transform
./float_transform.exe ./floats.txt -0.5
```

代入、直接return、次の関数の小数配列引数、len、添字、直接for反復に接続できます。
`values=scaled(values, factor)` は右辺の完了後に元配列を解放し、右辺が例外になれば元の値を保持します。
引数・リテラル要素は左から一度ずつ評価し、短絡条件では不要な呼出しを実行しません。
CからAILを呼ぶ場合の返却型は `名前_float_buffer` で、`名前_free` で一度解放します。
Python用 `compile_fn` でも同じ注釈の返却値をPythonリストとして受け取れます。
Windows/Linuxで65,537要素までの全出力、元ソースなしの移動後リンク、容量境界・重複領域、
既知NaN payload・無限大・負のゼロ・最小subnormalのコピーを検査しています。
これはコピーと検査入力の保証であり、丸めを伴う演算を別の順序へ変更してよいという意味ではありません。

### 小数配列をCへ渡す

Cの型宣言JSONの引数に `"float_list"` を使うと、AIL内部の小数配列を変換せずに渡せます。
Cの関数は `double total(const double *values, size_t count);` のように宣言します。
整数配列とは別の型です。引数は名前に束縛した平坦な小数配列に限り、整数列・行列・レコードは拒否します。
次のように `float` 値をappendする処理から配列型を決めます。入力0件でもこのコードの配列は小数型です。

```ail
let values=[];
for word in words { values.append(float(word)); }
print(native_total(values));
```

借用期間はCの呼出し中だけです。Cは領域を書き換え・解放・保持してはいけません。
空ならNULLの場合があり、要素数0では参照しません。負の長さ、バイト換算の桁あふれ、
NULLと非ゼロ長、不正alignmentは呼出し前に拒否します。任意のポインタの有効性を保証するものではありません。
Cが元領域をbytesのviewとして返した場合は、AILがコピーして所有します。
`float_list` はこのC接続JSON用の型名です。AIL関数側の引数・戻り値注釈は `list[float]` を使います。
小数配列を受け取りCを呼ぶAIL関数も再利用オブジェクトにできます。

`c_float_series.c/.json/.ail` は空白で区切った小数ファイルから、指定範囲内の件数、
入力順に加算した合計、全要素数を出す実例です。範囲は両端を含み、NaNは範囲判定に入りません。
合計は通常のdouble演算で、丸めとoverflowがあり、順序を変えた集計との一致は保証しません。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_float_series.c --interface language_examples/c_float_series.json -o float_native.o
py -3 -B ailc.py language_examples/c_float_series.ail --object float_native.o -o float_series
./float_series.exe ./floats.txt -1.5 2.25
```

Windows/Linuxで65,537要素まで、有限値・負のゼロ・subnormal・無限大の全ビットをPython参照と照合しました。
NaN文字列の変換ではAILとPythonの内部payloadが異なるため、分類と符号を照合します。
Cへ渡す経路では、独立して用意した既知NaN payloadもビットを保持することを確認しています。
元ソースなしでのCオブジェクトの移動・再利用、混合引数順、呼出し後に元配列を変えてもbytes戻り値が
保持されることも検証しました。速度改善の主張ではなく、既存オブジェクトは再生成が必要です。

### Cから小数配列を返す

JSONの `"result": "float_list"` に対し、C関数は生成される次の型を返します。
このtypedefをCソースに重複して書く必要はありません。

```c
typedef struct { const double *data; size_t size; } ail_c_float_view;
```

要素数で長さを指定し、コピー完了まで有効な領域を返します。自動変数へのポインタは使えません。
Cは一度だけ呼ばれ、AILがコピーして所有します。入力領域やC側のstatic領域を返す場合も、
次のC呼出しや元領域の変更・解放から独立した結果を保持します。C側の領域をAILが解放することはありません。
NULL+非ゼロ長、バイト換算の桁あふれ、不正alignmentはコピー前に拒否します。
これはポインタの指す領域自体の有効性を検査する機能ではありません。

`c_float_result.c/.json/.ail` はCの移動平均をAILから呼ぶ実例です。
最初の窓を入力順に加算し、以後は出る値を減算して入る値を加算します。
通常のdouble演算で、毎窓を再集計する計算とは丸め・NaN・infinityの扱いが異なり得ます。
窓幅が0以下または入力長を超えた場合は空配列を返します。確保失敗はエラー終了します。
Cの作業領域は明示的なrelease関数で解放し、AILはその後に保存した全結果を表示します。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_float_result.c --interface language_examples/c_float_result.json -o smoothing.o
py -3 -B ailc.py language_examples/c_float_result.ail --object smoothing.o -o smoothing
./smoothing.exe ./floats.txt 8
```

Windows/Linuxで65,537要素まで、四分の一刻みの入力と2の累乗の窓幅について、
各窓を別々に加算したPython参照と全出力を照合しました。元ソースなしの依存objectの移動、
byte引数からのコピー、既知NaN payload・負のゼロ・subnormal・最大有限値・無限大の全ビット、
次の呼出し後の所有権、容量境界と重複領域も検査しています。速度比較はしていません。

### Cから整数配列を返す

型宣言JSONを `"result": "list"` とすると、Cは `compile-c` が定義する次の型を返せます。

```c
typedef struct { const int64_t *data; size_t size; } ail_c_int_view;
```

`size` は平坦なint64配列の要素数です。C関数は一度だけ呼ばれ、アダプターが戻り値をコピーして
AIL側のリストとして所有します。入力配列の一部やCのstatic配列を返せるため、次のC呼出しで
元領域が変わっても、既に受け取ったAILのリストは変わりません。
C側の元領域はコピー終了まで有効でなければならず、関数内の自動変数へのポインタは返せません。
元領域を解放する責任はC側にあり、アダプターは元領域を解放しません。

空は `{NULL, 0}` で返せます。非ゼロ長とNULL、不正なアラインメント、int64の長さや
要素数からバイト数への変換で表せないサイズは、捕捉できないエラーで終了します。
任意の非NULL領域が実際に読めることを検査する機能ではありません。
生成アダプターを直接呼ぶ場合も、容量分の出力と全結果の退避を保ち、出力と元領域の重なりに対応します。
通常のAIL呼出しは全結果を受け取り、容量不足による切り捨てやC関数の再呼出しをしません。

`c_integer_result.c/.json/.ail` は、ファイルの整数列をソートし、指定範囲内の連続部分を
Cで選んで返す実例です。Cの二分探索は昇順入力が前提です。最初に件数、続いて全要素を出力します。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_integer_result.c --interface language_examples/c_integer_result.json -o range_native.o
py -3 -B ailc.py language_examples/c_integer_result.ail --object range_native.o -o integer_range
./integer_range.exe ./integers.txt -10 10
```

WindowsとLinuxで空・重複・int64両端・65,537要素までの全出力を独立Python参照と照合しました。
元ソースなしのC→AILラッパー→入口の別コンパイルと移動、入れ子の呼出し、元配列の変更からの独立、
出力容量0～4と前後に重なる領域、不正な型宣言・ポインタ・サイズの拒否も確認しています。
既存の再利用オブジェクトは、コンパイラの実装識別が変わるため再生成してください。

### C接続の工程時間を測る

Linuxでは、通常版と一時的な計測版を交互に実行できます。
通常のコンパイラやランタイムは変更しません。

```sh
python3 -B language_examples/profile_c_interop.py --rows 3000000 --cycles 6 --ascii-only
python3 -B language_examples/profile_c_interop.py --rows 2400000 --cycles 6
```

JSONには各実行の時間、読込み、各C呼出しの確保・UTF-8変換・計算・解放の時間、
通常版同士のA/A比較、計測の影響、入力と実装のhashを残します。
各実行の出力はPythonによる独立した位置付きバイト和と照合します。

2026-09-30のWSL/GCC 13.3・Ryzen 7 8840Uでの結果は
`language_examples/c_interop_profile_20260930.json` にあります。

| 入力 | 通常版の中央値 | 計測版の文字列受渡し割合 | その時間がゼロになった場合の上限 | A/Aの最大時間比 |
|---|---:|---:|---:|---:|
| ASCII 36,000,000バイト | 206.30 ms | 39.65% | 1.657倍 | 1.140倍 |
| 日本語・絵文字入り33,600,000バイト | 269.20 ms | 32.40% | 1.479倍 | 1.191倍 |

大入力の48実行すべてで出力が一致しました。割合と上限は計測版に対する値で、
通常版の内訳や達成済みの高速化を表すものではありません。受渡しには確保・変換・解放を含みます。
計測版/通常版の交互測定比の中央値は0.986/0.967でしたが、上記の変動があり、
計測が無負荷だった証拠にはしません。比較基準となる転送性能はまだ測っておらず、
この段階では最適化候補を追加・採用していません。

続くR244では、ASCII変換だけを一括コピーへ変更しました。事前の転送単体測定は
現行17.13ms、libc memcpy基準2.95ms（36MB・暖まった別領域・全出力照合）。
現行の基準速度到達率は17.2%で、50%へ届くと仮定した全体の見込みは約1.30倍でした。
変換だけの工程割合は約35.2%、全消去しても約1.54倍が上限です。

旧エンコーダーを固定した後、実ファイルの読込みから計算・終了まで交互に比較しました。
ASCIIの速度比中央値は1.1555倍、両実行順の中央値は1.1020/1.1686倍で、
同一版同士の変動幅1.0760倍を超えました。Unicodeは0.9904倍、変動幅1.0931倍で、
この測定で変動幅を超える悪化は検出されていません。両入力の68実行でPython参照と一致しました。
単体コピーの基準は実仕事全体の上限ではなく、想定した1.30倍は達成していません。
別の入力・機械・C関数で同じ速度比になる保証はありません。
変更後の転送単体は2.73ms、同時測定のmemcpy基準は2.84msでした。
基準速度への比は約1.04、A/Aの変動幅は約1.07で、基準と同程度です。
事前の50%という仮定を満たしても、暖まった転送単体と実ファイル処理の条件は異なり、
全体の見込み値がそのまま達成されるとは限りません。

```sh
python3 -B language_examples/bench_c_transfer.py
python3 -B language_examples/bench_c_interop.py --rows 3000000 --cycles 8
python3 -B language_examples/bench_c_interop.py --rows 2400000 --cycles 8 --unicode
```

転送単体のコマンドは実行時点のエンコーダーを測ります。旧版との実仕事の比較は
`c_interop_reference_encoder.c` に保存した旧変換を使用します。
生の結果は `c_transfer_roof_20260930.json`、`c_transfer_after_20260930.json`、
`c_interop_comparison_20260930.json` にあります。
空NULL文字列、ASCIIを含むUTF-16の部分文字列、複数引数のポインタ配置、全ASCII値、
64KiB前後、NUL/日本語/絵文字も境界検査に含みます。旧オブジェクトは再生成が必要です。

## テキストファイルを1行ずつ処理する

`for line in open(path)` または `for line in open(path, "r")` でUTF-8テキストを反復できます。
行末のLFは値に含み、CRLFと単独CRもLFに変換します。最終改行のない行も一度返します。
ファイルは反復の開始時に一度開き、完了・`break`・`return`・外側へ伝わる例外で閉じます。
ループ内で例外を捕捉して `continue` する場合は、同じファイルの次の行へ進みます。

```powershell
py -3 -B ailc.py language_examples/file_line_stats.ail -o file_stats
./file_stats.exe .\input.txt
```

実例は有効な整数行数、不正行数、合計を表示します。7、bad、-3、0の4行なら3、1、4です。
ファイル全体を一度に読む必要はありません。ただし長い1行のバッファや、自分で保存した過去の行は
メモリを使います。40万行の検査対象では、全出力がPython参照と一致し、追跡動的確保は256 KiB未満でした。
これは全プロセスのRSSや速度改善の測定ではありません。

存在しないパス・読込みエラーは `OSError`、パス内のNULは `ValueError` になります。
不正UTF-8は既存のファイル読込みと同様に終了エラーです。空ファイルではループ変数を新しく束縛せず、
前から値があれば保持します。通常ビルド・`compile-module`・Cからの呼出しでも使えます。
`rb`、キーワード引数、file objectを変数へ保存すること、`with open`、fileの `.readline()` は未対応です。
既存の `open(path).read()` は改行を変換しない全量読込みであり、この反復とは改行規則が異なります。

行を `line.strip().lower()[1:-1]` のように加工して次の反復まで保持する場合も、
元の領域を整理する前に必要な文字列を保持します（`lower()` は Python と同じ全 Unicode の大文字・小文字変換です）。
重なるスライス、UnicodeとASCIIで異なる内部幅、通常のfor／while、管理配列の拡張を検査しました。
今回の所有権修正後は、以前に作ったオブジェクトを元ソースから再生成してください。

### C・Rustとのファイル集計比較

`language_examples/bench_file_stats.py` は同じ入力をAIL、独立したC11/Rust実装、Python参照で照合します。
gcc・rustcが必要です。Windowsでは次を実行します。Linuxでは `python3 -B` を使います。

```powershell
py -3 -B language_examples/bench_file_stats.py --output "$env:TEMP\file_stats.json"
```

比較対象はASCII（`_` とU+001C～U+001Fを除く）、符号付き十進int64、CR/LF/CRLFです。
字句として不正な行は数えて飛ばし、値・合計のint64範囲外は失敗とします。
AILが扱える全UTF-8入力との比較ではありません。空入力、末尾改行なし、NUL、整数境界、
255～65,537バイトの長い行を含む13ケースと、既定200万行の全結果を確認します。
実行ファイルは移動後にも再検査します。

ビルド時間、起動を含む交互測定、同一AILの再測定（A/A）、順序差、工程計測の影響を記録します。
読取り・UTF-8変換の推定値は、異なる測定間隔、時計補正、標本数の検査を通らなければ採用しません。
固定間隔の標本には共通の偏りもあり得るため、検査成功だけで厳密な工程割合とは扱いません。
`actionable_phase_estimate: false` の結果から最適化やAmdahl上限を正当化しないでください。
記録中の参照性能はC/Rustの実測値であり、ハードウェアの限界性能ではありません。

測定はキャッシュの温まったファイルを使います。LinuxのRSSは各実装1回の別測定、WindowsのRSSは未測定です。
Rust参照はLFまで読み込んでからCRを分けるため、CRだけのファイルでは全体を保持し得ます。
速度だけでメモリ特性まで同等と扱わないでください。2026-10-01の記録は
`language_examples/file_stats_*20261001.json` に保存しています。失敗した工程推定も残しており、
この比較による本体の最適化はまだ採用していません。

所有権修正前に行った各OS測定の中央値は次のとおりです（200万行、14,110,531バイト）。
記録した版と入力での観測値であり、現行版の速度測定ではありません。両OSともA/Aと測定間隔の検査を通っていないため、
再現性のある速度比や工程比率の確定値としては使えません。

| OS | AIL | C参照 | Rust参照 |
| --- | ---: | ---: | ---: |
| Windows | 232.5ms | 172.9ms | 60.5ms |
| Linux（WSL） | 121.3ms | 54.4ms | 43.1ms |

元の計測値は `file_stats_windows_paired_clock_20261001.json` と
`file_stats_linux_paired_clock_20261001.json` にあります。Linuxは計測コードの影響検査も失敗しました。
Windows記録の後に、最低128標本を要求する検査を追加しています。

Linux x86-64では、各行へ時計を挿入せずCPU実行位置を採取する診断も使えます。
gccとaddr2lineが必要です。作業ディレクトリをAIL_CURRENTにして実行します。

```sh
python3 -B -m language_examples.profile_file_stats --output /tmp/file_stats_pc.json
```

同じ200万行を16回読み、各回の全出力を独立参照と照合します。入力ファイルを16個に複製しません。
通常版、診断器を無効にした版、1ms/7msを要求した採取版を正順・逆順で比較します。
単一スレッドのこの仕事だけが対象で、SIGPROFやtimerを自分で変更するソフトには使えません。
CPU標本にはOSで処理した時間の影響もあり、壁時計の工程割合とは異なります。
記録の `phase_wall_fraction`、`amdahl_upper`、`hardware_roof_fraction` は未確定のためnullです。

`file_stats_pc_linux_20261001.json` では計3,050標本を取得しました。`getc`と文字列領域の整理が
調査候補になりましたが、順序別では通常版との速度差と標本割合の検査が失敗しました。
全体中央値で相殺される差も検出し、`accepted_for_hotspot_investigation: false` としています。
採取後に追加した順序検査は、生の時間・PCを変えず再解析しました。採取時の `sources` と
再解析時の `analysis_sources` を区別して保存しています。最適化の採用根拠にはしていません。
現行診断器はsignal handler内の記録をlock-free atomicで行い、開始前に対応を確認します。
この変更後は境界検査と短い入力の組込み検査を確認済みです。上の長時間記録は変更前の版であり、
現行版の性能検証とは扱いません。短い記録は `file_stats_pc_atomic_smoke_20261001.json` です。
これらのCPU診断記録は文字列所有権の修正前のruntimeを使っています。
修正後のruntimeとatomic診断器による6サイクルの記録は
`file_stats_pc_r269_runtime_20261001.json` です。200万行×16反復の全出力は一致しましたが、
A/A・計測の影響・順序別の影響の検査が失敗し、最適化は未採用です。
採取時は以下のCバイト列返却の追加前です。記録したソースhashを測定版の識別に使ってください。

## バイナリファイルを扱う

`read_bytes(path)` は `str` のパスからファイル全体を `bytes` として読みます。
`read_bytes(path, offset, size)` は先頭から `offset` バイトの位置へ移動し、最大 `size` バイトを読みます。
3引数は左から一度だけ評価します。`offset` と `size` は非負の `int` です。
末尾を越えた部分は返さず、EOFでは空の `bytes`、`size == 0` でもパスを開いて位置を確認します。
負値やプラットフォームで表現できない範囲は `ValueError`、開く・位置を移動する・読む・閉じる失敗は
`OSError` です。Windowsは64bitの位置、他OSはCの `long` の範囲を扱います（検証したLinuxでは64bit）。
2引数・キーワード・小数の位置や長さは受け付けません。
`write_bytes(path, data);` は `bytes` をそのままファイルへ保存する文です。
UTF-8変換や改行変換はせず、NULや0xFFなど任意のバイトを扱えます。

```powershell
py -3 -B ailc.py language_examples/binary_copy.ail -o binary_copy
./binary_copy.exe input.bin output.bin
```

この例の本体は `write_bytes(sys.argv[2], read_bytes(sys.argv[1]));` です。
引数は左から評価し、入力の読込みが終わってから出力を開きます。
既存の出力ファイルは置き換えます。書込み中の失敗では部分的な出力が残る場合があり、
原子的な保存やロールバックは行いません。開く・読む・書く・閉じる処理の失敗は
`OSError`、パス内のNULは `ValueError` として捕捉できます。
1引数版は全体をメモリへ読みます。どちらもストリームやファイルハンドルを返しません。
既存の `open(path).read()` は引き続きUTF-8文字列を返します（`rb` 指定も同じ）。

### 標準入力のバイナリを分割して読む

`read_stdin_bytes(size)` は標準入力から `size` バイトに達するかEOFまで読み、`bytes` を返します
(Pythonの `sys.stdin.buffer.read(size)` と同じ)。`size` より短ければEOFに達しています。正のsizeで空ならEOFです。
CRLF、NUL、0x1a、非UTF-8も変換しません。負のsizeは `ValueError`、読取り失敗は `OSError`。
size 0は空を返し、入力を消費しません。引数は整数1個だけで、キーワードは使えません。

FNVの既存C/AIL接続を作り直すと、`hash_stdin(seed)` を別のAILソースから再利用できます。
R348の入力はseek不要で、ファイルのリダイレクトやパイプを扱います。AIL_CURRENTから実行します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/c_fnv_stream.c --interface language_examples/c_fnv_stream.json -o stdin_native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/c_fnv_stream_library.ail --object stdin_native.o -o stdin_library.o
py -3 -X utf8 -B ailc.py language_examples/c_fnv_stdin.ail --object stdin_native.o --object stdin_library.o -o stdin_hash
cmd /c "stdin_hash.exe 2166136261 < input.bin"
```

このWindowsの例はcmdの入力リダイレクトで実行します。
補助関数ごとに最大8,192バイトを処理し、返るとbytesを回収します。同一関数で読取りを繰り返すと
その関数の終了までbytesを保持します。
CLIはseed1引数、引数/seedのエラー終了2、OSError終了3、失敗出力なしです。
名前専用のC APIライブラリを同じ手順で再構築すると `stdin_hash` も公開します。
読み進めたstdinは巻き戻さず、EOFで再度呼ぶと初期seedのhashになります。

最初に使ったテキスト/バイナリの方式を固定します。`input()`/`sys.stdin`のテキスト読取りと
正の `read_stdin_bytes` を混在させると、反対方式の読取りを消費前に `ValueError` として拒否します。
これは別コンパイルのAILモジュールでも共通です。0/負のバイナリ要求は方式を固定しません。
共有範囲は同じruntimeで、C APIは同じnamespaceです。別namespaceや外部Cによるstdin操作は
調整しないため、呼出し側で読取り方式を混在させないでください。
返却済みbytesは次の読取りで変わりません。速度改善やRSS上限は未測定です。
新しい7検査はWindows/Linuxで成功。4MiB+17までの全byte照合、サイズ/所有権/方式拒否後の
未消費、短pipeのEOF前応答、closed stdin、FNV CLI/C API、移動後のC APIを確認しました。
EINTRの実注入とOS read回数は未検証です。

### 標準入力から標準出力へバイナリを送る

`write_stdout_bytes(data);` は `bytes` を一度評価し、そのまま標準出力へ送ります。
空なら書きません。値として使うことやキーワード引数は拒否します。
`binary_stream.ail` の `copy_stdin(size) -> int` は補助関数ごとに入力を送り、総バイト数を返します。
sizeは正の整数で、0/負は `ValueError`。このCLIは8,192バイトずつ処理します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/binary_stream.ail -o binary_stream.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/binary_pipe.ail --object binary_stream.o -o binary_pipe
cmd /c "binary_pipe.exe < input.bin > output.bin"
```

入力と出力は別のファイルにしてください。リダイレクトは実行前に出力ファイルを置き換えます。
引数なしの正常終了は0、余分な引数/ValueErrorは2、OSErrorは3です。
書込みは最大64KiBずつ、short writeは残りを続け、EINTRを再試行します。
途中のエラーでは出力の一部が残る場合があります。入力・出力とも巻き戻しません。
POSIXのbroken pipeは、既存SIGPIPEの扱いによりプロセスが終了する場合があります。

Cから再利用する場合は、専用namespaceでobjectとライブラリを構築します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/binary_stream.ail --c-api-name bstream -o bstream.o
py -3 -X utf8 -B ail_chatgpt.py compile-library language_examples/binary_stream_api.ail --name bstream --object bstream.o -o bstream_lib
```

`emit(bytes) -> void` は借用データを変更せず、`copy(size) -> int` は入力から出力へ送り総量を返します。
エラー後も副作用は残ります。C APIの戻り値/エラー引数の規約は既存と同じです。
同じruntimeの標準出力は、最初の `print` または空でないバイナリ出力で方式を固定します。
反対方式は出力前に `ValueError`。ただしprint引数の評価による副作用は先に起きます。
stderrへのprintは併用できます。外部Cや別namespaceの操作は調整しません。
全byte、4MiB+17、EOF前応答、closed fd1、移動後C API、EINTR/short/zero/途中失敗を
Windows/Linuxで検証しました。性能、RSS上限、実signalによるEINTRは未測定です。

### バイナリの各行に番号を付ける（R353）

`number_stream.ail` の `number_stdin(first_line: int, chunk_size: int) -> void` を別コンパイルで再利用します。
LFバイトだけを行の区切りとし、各行の先頭へASCIIの `番号: ` を付けます。
CR/CRLF、NUL、0x1a、非UTF-8を含む入力バイトをそのまま保ち、末尾の改行は追加しません。
空入力の出力は空です。LFだけの空行にも番号を付けますが、末尾LFの後には架空の行を追加しません。
UTF-8の `number_lines` はsplitlinesで処理する別の契約で、速度結果は共有しません。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/number_stream.ail -o number_stream.o
py -3 -X utf8 -B ail_chatgpt.py compile language_examples/number_pipe.ail --object number_stream.o -o number_pipe
cmd /c "number_pipe.exe 1 8192 < input.bin > numbered.bin"
```

入力と出力には別のファイルを指定します。引数省略時は開始番号1、chunk size 8192です。
引数はASCII十進数字だけ、1～9,223,372,036,854,775,807。先頭の0を許し、符号・空白・Unicode数字を拒否します。
桁あふれはint変換に任せず、演算前に検査します。終了0は成功、2は引数/ValueError、
3はOSError、4は行番号を使い切ったRuntimeError。通常CLIのstderrは空です。

ライブラリも開始番号/chunk sizeの0・負値を入力消費前にValueErrorで拒否します。
chunk sizeを大きくしても1 OS readは最大65,536バイトで、short readを処理します。
最大番号の行は、LF終端の後がEOFなら成功します。次の行に1バイトでもあれば、
その番号を出力する前にRuntimeErrorで拒否します。既出力と読取り済みchunkは巻き戻しません。
補助関数がchunkごとのbytes/文字列を回収します。プロセスRSSの上限や速度は未測定です。

Cから使う場合も、同じ実装を専用namespaceへ構築します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/number_stream.ail --c-api-name number_io -o number_stream_api.o
py -3 -X utf8 -B ail_chatgpt.py compile-library language_examples/number_stream_api.ail --name number_io --export number_pipe --object number_stream_api.o -o number_io_lib
gcc -std=c11 -I number_io_lib language_examples/number_stream_host.c number_io_lib/number_io.o -lm -o number_pipe_c
cmd /c "number_pipe_c.exe < input.bin > numbered-c.bin"
```

ヘッダーの `number_io_number_pipe(first_line, chunk_size, &error)` だけを公開します。
成功0、引数拒否1、I/O失敗6、番号使い切り7。実例hostは開始1/chunk 8192で呼び、
失敗のstatusをstderrへ表示します。C APIの同時呼出し・所有権・stdin/stdout方式は既存の規約に従います。
Windows/Linuxで独立したLF split参照との全byte一致、4MiB+17、chunk/番号の幅境界、
EOF前pipe応答、元ソースなしのobjectと移動後C API/公開限定/C hostを検証しました。
実signalによるEINTR、syscall回数、RSS、速度はこの実例では未検証です。

Linuxの読み手が消えたpipeでは、SIGPIPEの既定動作でプロセスが終了する場合があります。
R395の実CLI確認では既定ならsignal13（subprocessでは-13）、SIGPIPEを無視する継承設定なら終了3。
C APIの失敗status6も、signalで終了しない条件で返るものです。ホストのsignal設定は変更しません。

### 通常パイプの独立検証器を同梱する（R395）

開始番号1のLinux実行ファイルを、通常ファイル・速度の資格とは別に確認できます。

```bash
python3 -B language_examples/number_pipe_checker.py --program-json '["./number_pipe"]' --output new-pipe-result.json
```

実パイプを使った7入力（最大16MiB+1）の全byte、EOF前の5段階応答、閉じた入出力・
`/dev/full`・SIGPIPE既定/無視を検査します。出力は新規fileのみ、取得済み結果と失敗を保存します。
標準ライブラリだけを使うので、公開autoの `--checker` に渡して配布後も検証できます。
現行AIL/Cバッチ版をautoで構築し、日本語名へ移動・元app/inputパス退避後に同梱checkerで
7入力＋7pipe/errorケースを確認しました。配布物は約0.90MB、速度比較や採用更新は行っていません。
[構築・移動記録](language_examples/number_stream_pipe_auto_linux_r395.json)に失敗した初回CLI配置指定も残しています。
Linuxの固定first_line=1・単一プロセス契約の有限検査です。Windowsや全I/O条件への保証ではありません。

### 既存C実装をAILの一括処理ライブラリとして使う（R386）

Linuxの通常ファイル入出力向けに、既存C実装をAILから呼ぶ別の実装を用意しました。
開始番号1、readサイズ8192、LFバイトによる行区切りに固定します。
既存の `number_stdin(first_line, chunk_size)` と別の入口 `number_batch() -> int` です。

```bash
python3 -B language_examples/number_stream_batch/build.py --out number_batch_build
./number_batch_build/number_batch < input.bin > numbered.bin
```

出力ディレクトリは未作成のものを指定し、入力と出力には別のファイルを使ってください。
CLI引数は受け付けず、追加引数は出力前に終了2で拒否します。
空入力は空出力、CR/CRLF・NUL・非UTF8・末尾改行の有無をバイトのまま保持します。
実行時にPythonは不要です。

buildは既存Cソースを改変せずsnapshotし、公開 `compile-c` と `compile-module`、
AILコンパイルを順に使います。出力にはCとAILのオブジェクト、対応する `.o.json`、
実行ファイルを保持します。`native.o` / `library.o` と両metadataを一緒に移せば、
元のC・AILソースなしで次のように別のAILから再利用できます。

```ail
fn main() -> int { return number_batch(); }
```

```bash
python3 -B ailc.py consumer.ail --object number_batch_build/native.o --object number_batch_build/library.o -o consumer
./consumer < input.bin > numbered.bin
```

確認済み候補を、独立検証器・オブジェクト・実行入口付きの移動可能な成果物へ出力できます。

```bash
python3 -B language_examples/number_stream_batch/deliver.py --out number_batch_app
./number_batch_app/app/programs/number_batch < input.bin > numbered.bin
python3 -B ailc.py consumer.ail --object number_batch_app/app/programs/native.o --object number_batch_app/app/programs/library.o -o consumer
```

出力先は新規フォルダです。保存済みの採用判断と測定時の全5ファイルの内容一致を確認し、
現在の候補を独立検証してから出力します。フォルダ全体を移動でき、同梱の検証器のパスは
`number_batch_app/result.json`の`checker`にあります。詳しくは
[成果物の出力と移動後検証](README_AUTO_ENTRY_JA.md#確認済み候補を移動できる成果物へ出力するr388)を参照してください。
これは現在の正答と再利用の資格で、速度は以前の測定範囲の実績です。

Linuxで全byteの独立参照、8192/65536前後の境界、1MiB超、source-free再利用とUnicode移動を
検証しました。Windowsや既存CLIの可変引数、PIPE応答、I/O失敗の一般的同等性は今回の対象外です。
AIL runtimeの既定動作を変更していません。この明示実装を新しい96組で比較する入口は次です。

```bash
python3 -B language_examples/compare_number_stream.py --native-raw --ail-c-batch --output fresh-comparison.json
```

先行探索・失敗した試行・検査の実測費用があれば `--prior-cost-seconds 実測秒数` を渡せます。
その値は今回の実行費へ加算します。未把握の開発・AI生成費用まで含んだ総費用とは扱いません。

今回のLinux16MiB短行の新規96組では、このAIL/C実装が既存AILより速度比中央値1.169299倍でした。
最大RSSは双方640KiB、実行ファイルは799,792→786,728byte。速度優先の明示条件で採用判定を
通っています。CPU改善、別入力・別環境の速度、既存runtime全体への適用は未確認です。

保存済み比較の採否・失敗原因・不足する証拠は `workflow/selector/judge.py 結果.json` で
再判定できます。[判定入口の使い方](README_AUTO_ENTRY_JA.md#結果が判定できないとき)を参照してください。
これは元の測定記録の判定で、現在のバイナリの検証や追加測定ではありません。

### 通常のAILソースから独立検証付きの成果物へ（R390）

`.ail`を直接指定して、公開コンパイラでの構築・独立検証・移動可能な成果物の出力まで
進められます。入力と検証器、再現可能な標準入出力の仕事である宣言が必要です。

```text
python workflow/vibe/vibe.py auto main.ail --source helper.ail --object native.o --object library.o --checker oracle.py --input input.bin --repeatable-cli --mode original --out checked_app
```

追加ソースとobjectが不要なら、その引数は省きます。`use`の全依存ソースを`--source`で、
型付きobjectの全依存を`--object`で宣言してください。`.o.json`も隣に必要です。
成果物には実行ファイルと宣言したobject/metadataを保持します。出力先には新しい
ディレクトリを指定します。この`original`コマンドは動作の資格を確認し、新しい速度の採用判定はしません。
LinuxでC/AIL再リンクと移動後の検証を確認しました。
[詳しい条件と検証範囲](README_AUTO_ENTRY_JA.md#ailソースをビルド検証配布する)を参照してください。

### バイナリ行番号処理の診断（R354）

R378の新規CLI記録はschema8/number_stream_elapsed_v3です。既定は `--elapsed-clock monotonic`、別の事前宣言は
`--elapsed-clock monotonic_raw`。工程・プログラム全体・親の経過時間・書込み参照を同じ宣言時計で取得し、
A/A・前後対照を含む全sampleと工程/参照recordに時計名とversionを保存・照合します。
旧schema5/6/7や時計/versionの欠落/差替えを新しい宣言として読み替えません。
MONOTONIC括りをMONOTONIC全体区間で、RAW間隔をRAW選択時のRAW全体区間で検査します。
括り幅・同一時計の検査とCPU照合の固定1ms、固定5%のA/A・観測影響は維持します。
MONOTONICは周波数補正を受けRAWは受けないため、両時計へ等速一致を要求する前提はR377で修正しました。
両時計の比率は診断表示です。総診断費用は別のperf_counter時計です。
R378ではRAWのfreq/tick/offset変化を保存・診断し、RAW速度変化としての一律拒否を修正しました。
clocksource変化は両時計で拒否、MONOTONICは補正値の変化も拒否します。CPU会計の1ms検査と未証明範囲は維持します。
固定5%は整数の交差積で判定し、floatの丸めで5%直外が通る問題を修正しました。
[現行R378の条件と根拠](README_AUTO_ENTRY_JA.md#raw補正情報とcpu会計を分け5を整数で判定するr378診断のみ)を確認してください。
R378の新規実測は全217runで短行/長行の全byte一致・時計/CPU会計・source不変を確認しました。
ただし両入力のA/A/観測影響が固定5%を超え、価格付け不可・adopt=falseです。
CLIのexit0は診断取得の完了を表し、性能採用を表しません。原記録と保存後の拒否再現は保存済みです。
RAWの物理精度・速度改善・最適化採用を保証する選択ではありません。
R376の16MiB実診断は境界25件が通り、短行の出力も一致しましたが、RAW約500.10ms/対応する
MONOTONIC約479.47msの時計不一致でexit1です。前後の時計設定が同じでも価格付け不可でした。
R376の長行・A/A・paired測定は未実行、原記録は保存済みです。
R377の新規v2実測は、正常118run（境界25、短行6組と前後対照、warmup、A/A途中まで）と、
出力一致した失敗観測1runを保存。実行前後のtick/freq変化でexit1です。
後A/A不足・長行未実行のため有効な価格付けと採用は得ていません。再判定も不足を拒否しました。
[現行時計契約と根拠](README_AUTO_ENTRY_JA.md#時計域の速度差を等速の不一致と扱わないr377診断のみ)を確認してください。
[時計宣言とR376失敗記録](README_AUTO_ENTRY_JA.md#工程と参照の時計域を事前固定するr376診断のみ)を確認してください。

R358でOSの時計補正状態を記録し、変化した場合の価格付けを拒否します。Linuxに既存Cコンパイラがある環境で、
固定開始番号1/chunk 8192の診断を実行できます。
出力先は未作成のファイルを指定します。Windowsでは診断の判定検査だけを実行できます。

```sh
python3 -B language_examples/profile_number_stream.py --mib 16 --cycles 6 --output fresh-diagnostic.json
python3 -B language_examples/cpu_accounting_control.py --output fresh-cpu-control.json
python3 -B -m unittest test_number_stream_profile
```

最初のコマンドは16MiBの短いバイナリ行と16MiB+1の長い行を用意し、公開AIL版・通常版・計測版・
独立C参照・書込み専用参照を6組、両順序で実行します。各arm2回のwarmup、前後A/Aと5境界入力も
含め、非公開armの各実行前後にも公開版を実行するため、予定全217出力を独立期待値へbyte単位で照合します。
失敗で中断すれば、取得済み記録と失敗を保存します。入力・AIL/Python実装・実コンパイラ・
生成C/実行ファイルのhashを記録します。公開コンパイラのCをそのまま捕捉した通常版が公開CLI版と
全byteで一致することが必要です。計測版も別コンパイルの境界と同じflagsを保ちます。
同一バイナリ同士でも時間の差が固定幅を超えれば棄却します。
実行時間には親の供給/収集・子の起動/終了を含みます。
親CPUはLinux SELF差分、子CPUは所有pidのwait4から取得します。経過時間はCPU取得区間も囲みます。
各processのCPUが経過+固定1msを超えれば停止します。この幅はOS精度の保証ではありません。
親子CPUの重複は許し、経過時間から子CPUを引いてI/O待ちと断定しません。
CPython POSIXの互換待機フックと子usageを必要とし、欠落なら拒否します。
途中対照・前後A/AのCPU欠落や不正は拒否し、ゼロ値での価格付けも拒否します。
親のprocess/thread CPU時計、raw時計の前後を囲む通常単調時計の区間も記録します。
CPUの取得方法同士と、同じ区間のraw/通常時計を固定1msで照合します。
区間の不確かさが1msを超える場合、型/幅/逆転/時計の欠落や価格付け時のゼロ値も拒否します。
取得時のthread数は1を要求しますが、途中のthread不在・時計の独立性/正確さを証明したものではありません。
各run前後にclocksourceとadjtimex modes0を読取り専用でqueryします。queryはwall/CPU区間外で、
OS設定は変更しませんが、追加起動による後続runへの影響はあり得ます。
query失敗・型/幅/欠落は拒否します。clocksource/freq/offset/tickがrun内または比較全体で変われば価格を出しません。
状態未計測でも価格不可です。前後が同じでも途中変化の不在や時計の絶対精度は保証しません。

read/write/十進変換と残りを分けます。残りには走査・割当て・結合・UTF-8変換・解放・
時計測定の費用が含まれ、走査だけの時間とは呼びません。呼出し回数はOS syscall回数と別です。
全体の独立C参照は物理的roofや工程の基準ではありません。書込み専用参照は独立して全出力を
準備してから64KiB以下のPOSIX書込みを測り、読取り・番号整形・割当ての準備費を除外します。
入力32MiB+1/出力64MiBを超える参照入力は拒否します。基準の到達率は計測版のwriteとの比率で、
新候補がこの到達率や準備費を実現する証拠ではありません。

前後A/A、計測器の影響、公開ビルドとの差が事前固定5%幅を各blockで通ることが必要です。
失敗しても許容幅を変更せず、生記録を残します。この幅は統計的な保証ではありません。
独立期待値と全blockの同一性、整数時間/回数の幅、工程和も検査します。
`valid_phase_diagnostic` と `valid_for_pricing` は別です。全gate、公開バイナリ同一性と工程参照、
時計の空測定64回の観測最大の100倍超を通った場合だけwriteの価格付けを出します。
参照50%を事前仮定、他工程の費用不変という条件付きで、採用は常にfalseです。
診断のexit 0は候補の合格・採用を意味しません。通常例のC API/引数/短pipe/I/Oエラーの
全契約をこの固定C参照で置き換えたものでもありません。

R358の実走は正常記録71runと一致した失敗run1回を保持し、CPU会計でexit1です。
失敗run周辺のqueryでtick10000→9167µs、freq_scaled_ppm0→-2184533の変化を記録しました。
wall504.102ms/子CPU508.243ms、raw516.157ms/対応する通常時計約504.001msでした。
長行未到達・予定217run未完了・価格なし・採用falseです。因果関係の完全な証明ではありません。
状態変化を拒否する最終版の全診断は未実測で、判定検査はLinux23成功/Windows20成功・3skipです。
[R358の説明・失敗記録・検証境界](README_AUTO_ENTRY_JA.md#osの時計補正状態の変化を拒否するr358)を確認してください。
R357の対応区間付き実走では正常記録73runと一致した失敗run1回を保持しましたが、時計不一致でexit1です。
raw392.595msに対し、対応する通常単調時計は382.720909～382.723479msでした。
CPU取得方法同士は約382.05msで揃っており、このrunをCPU超過とは分類しません。
長行未到達・全診断/価格未完了・採用なしです。最終版の全診断も未実測です。
[R357の説明・失敗記録・検証境界](README_AUTO_ENTRY_JA.md#cpuの取得方法と時計の対応区間を照合するr357)を確認してください。
R356の旧Linux実走はCPU会計で中断し、全診断・価格付けは未完了です。
wait4版の失敗runは全byte一致ですが、経過456.883msに対し親CPU471.683ms・子CPU482.140msでした。
最終版はその後に待機フックとCPU区間を修正したもので、全診断未実測です。
二乗和の固定対照は全6答えと時計会計が一致しましたが、pipe負荷の超過原因は未特定です。
[R356の説明・失敗記録・検証境界](README_AUTO_ENTRY_JA.md#実行途中の対照とcpu会計を検査するr356)を確認してください。
R355の旧Linux結果は全121出力一致、診断/価格付けは両方不合格、予測nullでした。
短行は前後A/Aが幅内でも途中の同一バイナリ比較が不合格で、前後A/Aだけでは拾えない揺れを検出しました。
公開ビルドへの工程割合の転用、RSS/CPU改善、未知入力の同値性は未認定です。
[R355生記録](language_examples/number_stream_diagnostic_linux_r355.json)と
[現行説明](README_AUTO_ENTRY_JA.md#公開ビルドをそのまま測り書込み参照を分けるr355)を確認してください。
R354の8MiB/全84実行は[旧生記録](language_examples/number_stream_diagnostic_linux_r354.json)として保持しています。

### バイナリを追記する

`append_bytes(path, data);` は既存の内容を残して末尾へ `bytes` を追加します。
ファイルがなければ作成し、空の `bytes` でも開いて閉じます。パスは `str`、データは
`bytes` の2引数を左から一度だけ評価し、両方の評価が終わってから出力を開きます。
引数評価が失敗した場合は出力を開きません。キーワード引数や値としての使用は拒否します。
変換をせず、書込みとcloseの失敗は `OSError`、パス内NULは `ValueError` です。
途中で失敗すると一部が追記済みの場合があります。複数の書込み元のレコード単位の
原子性、ロールバック、電源断に耐える保存は保証しません。

`binary_log.ail` は `バイト長:ペイロード` を1レコードとして追記する再利用ライブラリです。
長さはUTF-8文字数ではなくバイト数なので、NULや改行を含むペイロードも長さで区切れます。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/binary_log.ail -o binary_log.o
py -3 -B ailc.py language_examples/binary_log_main.ail --object binary_log.o -o binary_log
./binary_log.exe events.bin hello
./binary_log.exe events.bin 世界
```

新規ファイルなら内容はUTF-8で `5:hello6:世界` になります。既存ファイルへは続けて追加します。
Cから使う場合は同じソースを次のように公開できます。

```powershell
py -3 -B ail_chatgpt.py compile-library language_examples/binary_log.ail --name blog -o blog_lib
```

生成ヘッダーの `blog_append_record(blog_view path, blog_view payload, blog_error *error)` は
成功時0、失敗時にエラー番号を返します。`path` はUTF-8、`payload` は任意のバイト列です。
元ソースなし・移動後にC/AIL双方から利用し、129件の8193バイトレコード、空レコード、
Unicode、失敗後の復帰を検証しました。
範囲読込みを補助関数で行って追記する検査では、約16MiBの全出力が独立参照と一致し、
追跡する動的割当のピークは32KiB未満でした。RSSや速度の測定ではありません。

### 範囲ごとに読み込んでCへ渡す

`language_examples/c_fnv_file_ranges.ail` は8192バイトごとに別の関数で読込み、Cの更新関数へ渡します。
上の `stream_native.o`・`stream_library.o` を作成した後にビルドできます。

```powershell
py -3 -B ailc.py language_examples/c_fnv_file_ranges.ail --object stream_native.o --object stream_library.o -o range_hash
./range_hash.exe input.bin 2166136261
```

この例は補助関数が戻るたびに読んだ `bytes` を解放します。同じ関数内で読込みを繰り返す場合は、
その関数が戻るまで保持されるため、範囲読込みだけでメモリの上限が決まるわけではありません。
毎回ファイルを開き直すので、処理中に入力を変更しないでください。更新中ファイルの一貫したsnapshotは保証しません。
速度改善の主張や既存実装の置換はしていません。

### 全体読込みと範囲読込みを比較する

`file_range_workflow.py` は上の2つのAIL+C実例を、固定した入力に対する候補比較へ接続します。
メモリを優先し、実行時間0.5秒・ピークRSS 64MiBを上限として、既存selectorの12組の交互測定、
前後のA/A検査、順序別検査で採否を決めます。Python整数演算による14ケースの独立照合には
4MiBの全出力、分割境界、空ファイル、日本語パス、読込み失敗を含みます。

```sh
python3 -B language_examples/file_range_workflow.py --out ranges-result.json
```

出力先は未作成のファイルを指定します。コンパイラとソースを一時領域へ固定し、両版のビルド、
候補判定、実行ファイルの書出し、移動後の独立検証まで実施します。一時ビルド・入力・bundleは終了時に解放し、
JSONへ結果とハッシュを残します。利用する実行ファイルは上のビルド例で作成できます。
基準版ビルドの失敗診断も上限6000文字で保持します。

`file_ranges_linux_20261001.json` はLinux x86_64の4MiB入力で範囲版を選び、移動後の14ケースも通過しました。

| 指標（中央値） | 全体読込み | 範囲読込み |
| --- | ---: | ---: |
| ピークRSS | 4,864 KiB | 640 KiB |
| 実行時間 | 8.687 ms | 8.402 ms |

この条件ではRSSが86.84%減りました。メモリのA/A差は0で、両方の実行順序でも改善を確認しました。
時間のA/A差は5.22%あり、時間差を高速化の根拠にはしていません。CPU時間は短い実行に対する
測定分解能のため0秒と記録され、CPU負荷がないことを意味しません。電力・物理的性能上限は未測定です。
工程は実行全体（100%）で、内部工程の割合や有限のAmdahl上限を求めた記録ではありません。

準備・両版のビルド・検査・測定・移動後検証・一時領域の解放に45.24秒を要しました。
編集、先行テスト、モデル使用量はこの値に含みません。想定利用回数が未指定のため費用回収は未判定です。
採用はこの比較のメモリ優先方針に限ります。他の仕事やハードウェアへ自動適用はしません。
測定は基準版ビルドの失敗ログ/プロセス管理修正前のものです。記録のソースhashをそのまま保持し、
修正後はWindows/Linuxで失敗診断と通常ビルド・移動後検証を通しています。性能測定は再実行していません。

R299ではLinuxの単一プロセス測定を、小さなC親プロセスによる `wait4` へ変更しました。
GNU timeのCPU出力（小数点以下2桁）による丸めを避け、user/system時間を小数点以下6桁で記録します。
これは出力の精度であり、OSの実際の計測分解能を保証するものではありません。
約4msの仕事をプロセス内の `CLOCK_PROCESS_CPUTIME_ID` と照合し、RSSへのPython観測器の混入も検査しています。
Pythonから直接wait4する試行は、この環境では観測器由来のRSSが13,312KiBとして混ざったため採用しませんでした。

初回にインストール済みCコンパイラで計測器を一時ビルドします。ビルドと結果解析・検査をアプリのwallから除外し、
アプリとC親の起動～終了を測ります。ビルド費は比較全体の費用には含めます。計測器は終了時に解放し、
Cソース・コンパイラの内容が変われば再ビルド、Pythonソースが変われば再読込みします。
Cソースもselectorの証拠ハッシュへ含めます。コンパイラがない場合は測定を停止し、旧方式へ黙って戻しません。
複数プロセスは引き続き別の `job_tree` 契約を使います。古い測定記録を新方式の結果には書き換えません。

新方式による `file_ranges_wait4_linux_20261001.json` も4MiB入力・メモリ優先方針で範囲版を選びました。

| 指標（中央値） | 全体読込み | 範囲読込み |
| --- | ---: | ---: |
| ピークRSS | 4,864 KiB | 640 KiB |
| CPU時間 | 6.423 ms | 6.037 ms |
| 実行時間 | 9.098 ms | 8.648 ms |

14ケースの独立照合と移動後検証に成功。12組の交互測定でメモリのA/A差は0でした。
wallのA/A差5.19%、CPUは12.00%で、弱い順序のQ1改善率1.74%/0.29%を上回っています。
したがって時間改善は主張しません。準備から一時領域解放まで56.98秒で、費用の除外範囲は上の記録と同じです。
以上の2記録はそれぞれ別の測定器によるものです。異なる方式の時間値を直接比較して高速化の根拠にはしません。

### UTF-8文字列とバイト列を変換する

`text.encode()` は `str` からUTF-8の `bytes`、`data.decode()` はUTF-8の `bytes` から `str` を作ります。
どちらも既定はUTF-8・厳密な検査です。`"utf-8"`・`"utf8"`（大文字小文字と `_` の違いも可）を
文字列リテラルで指定でき、`encoding=` と `errors="strict"` も使えます。
他の文字コード、`ignore`・`replace`、変数で渡す文字コードはビルド時に拒否します。

```powershell
py -3 -B ailc.py language_examples/utf8_roundtrip.ail -o utf8_roundtrip
./utf8_roundtrip.exe input.bin output.bin
```

この例はファイルをバイト列で読み、文字列へ変換してから再びUTF-8で保存し、バイト数を出力します。
NUL・改行・日本語・絵文字を保持し、BOMの追加や除去、改行やUnicodeの正規化はしません。
不正UTF-8や単独サロゲートの文字列は、変換時に捕捉できないエラーで実行を終了します。
例では変換が保存先を開く前に終わるため、この変換エラーでは既存の保存先を書き換えません。
一般的な書込み失敗のロールバックを保証するものではありません。
変換結果は独立した領域を持ち、`-> str`・`-> bytes` の再利用ライブラリでも返せます。
全体を変換する方式で、保持する結果の量に応じてメモリを使います。

### ファイル内の文字列を置換する

`text.replace(old, replacement)` は一致する箇所を左から重ならないように置換します。
3番目の整数引数、または `count=` で最大回数を指定できます。0は置換なし、負数は回数制限なしです。
`old` と `replacement` は文字列の位置引数です。正規表現ではありません。
空の `old` は各文字の間と両端に挿入します。例えば `"😀".replace("", "_")` は `_😀_` です。
絵文字の途中には挿入せず、改行・NUL・Unicodeの表記を正規化しません。

```powershell
py -3 -B ailc.py language_examples/replace_text.ail -o replace_text
./replace_text.exe input.txt output.txt "日本" "日本語" -1
```

この例はUTF-8ファイルを読み、変換と置換が終わってから保存先を開きます。
ファイル全体と結果をメモリに持ち、保存先の既存内容は上書きします。
書込み途中の失敗では部分的な出力が残り得ます。
`replace_text` 関数をライブラリ用ファイルへ切り出すと、`compile-module` で再利用できます。
receiver・検索文字列・置換文字列・回数を左から一度ずつ評価し、実行しない分岐の引数は評価しません。
この機能について速度改善は測定していません。

Cへ渡してバイト数とチェック値を計算する例もあります。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_interop.c --interface language_examples/c_binary.json -o c_binary.o
py -3 -B ailc.py language_examples/c_binary.ail --object c_binary.o -o c_binary
./c_binary.exe input.bin
```

`c_binary.json` は引数を `bytes` と宣言します。関数は通常のAILオブジェクトからも呼べます。
Cへ渡す一時領域には `bytes` の生データと `str` のUTF-8表現を順番にコピーし、
通常の戻りで解放します。C側は内容を書き換えず、ポインタを保持・解放しないでください。
バイナリ入力・保存の追加は機能拡張であり、新しい速度改善の主張はありません。

### C標準ライブラリでバイトを検索する（R359）

`language_examples/byte_search_core.ail` の `find_byte(data, value, start, end)` は、
Cの `memchr` で最初の一致位置を返す再利用モジュールです。見つからなければ `-1` です。
`value` は0～255の整数で、範囲外は捕捉できる `ValueError` になります。
`start` は含み、`end` は含まない位置です。負の位置は末尾から数え、末尾を超える終了位置は丸めます。
開始位置が末尾以降、または検索範囲が空なら `-1` です。位置は符号付き64ビットです。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/byte_search.c --interface language_examples/byte_search.json -o byte_native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/byte_search_core.ail --object byte_native.o -o byte_core.o
py -3 -X utf8 -B ailc.py language_examples/byte_search.ail --object byte_native.o --object byte_core.o -o byte_search
./byte_search.exe input.bin 0
```

CLIはファイル全体を読み、指定バイトの位置を1行出力します。引数不足/過剰は終了2、
整数の書式不正/0～255外のバイトは3、読取り失敗は4でstderrに理由を表示します。
整数変換で符号付き64ビットを超える値は、既存のAIL規約により捕捉できず終了1の `integer overflow` になります。
省略した開始位置は0、終了位置はINT64_MAXです。不正バイトはファイルを読む前に拒否します。
NULや非UTF-8もそのまま検索します。JSONの `borrowed_bytes` は入力を変更せず借用し、Cはポインタを保持しません。
ネイティブ関数はINT64_MAXまたはPTRDIFF_MAXを超える長さを拒否します。

このCLIは二つのオブジェクトをリンクします。
元ソースを除去した後も `--object byte_native.o --object byte_core.o` で利用できます。
それぞれの `.o.json` も保持してください。このCコードとAILモジュールの追加は機能拡張で、速度改善の測定ではありません。

R360から、AILの補助ソースを `use` で読み、C部分だけオブジェクトをリンクする形も使えます。
例えば同じフォルダに次のソースを置き、`--object byte_native.o` でビルドできます。

```ail
use byte_search_core;
fn main() -> int {
    if len(sys.argv) != 2 { return 2; }
    let data = read_bytes(sys.argv[1]);
    print(find_byte(data, 0, 0, len(data)));
    return 0;
}
```

`use` の推移的依存と明示 `--module` は既存のソース検査を通し、オブジェクトの型・ABI・hash・完全な依存も照合します。
定義名・定数・引数・局所変数がオブジェクトの公開名を隠す場合は拒否します。
通常オブジェクトとC API専用オブジェクトの区別は維持します。R361から `compile-module` 自体も `use` に対応します。

### 整数リストからバイナリを作る

`bytes(values)` は平坦な整数リストの変数/引数を、変更できない `bytes` へコピーします。
`bytes([])` や `bytes([0, 1, 255])` も使えます。値は0～255で、範囲外は `ValueError` です。
リストの各式は左から一度評価され、全要素の値域検査後にバイト列を作ります。
作成後に元リストの値を変更しても、作成済みのバイト列は変わりません。

```ail
fn payload(values: list) -> bytes { return bytes(values); }
```

小数・文字列・bytes要素・入れ子のリストは拒否します。
R444からゼロ埋めの整数指定とbytes式の複製にも対応します。任意のiterableや整数リストを返す関数呼出しは対象外です。
整数リストと結果を同時に保持するため、大きさは空きメモリにも制限されます。

### 整数を固定幅のバイナリへ変換する（R400）

`language_examples/binary_numbers.ail` は、整数の読み書きを再利用できるモジュールです。
各組にlittle-endianの `_le` とbig-endianの `_be` があります。

| 整数 | 書き込み / 読み取り | 値の範囲 | バイト数 |
| --- | --- | --- | --- |
| 符号なし16ビット | `pack_u16_le` / `unpack_u16_le` | 0～65,535 | 2 |
| 符号なし32ビット | `pack_u32_le` / `unpack_u32_le` | 0～4,294,967,295 | 4 |
| 符号付き64ビット | `pack_i64_le` / `unpack_i64_le` | −2⁶³～2⁶³−1 | 8 |

ソースから使う場合は `use binary_numbers;` を宣言します。同梱部品はコピーせず取り込めます。
別途コンパイルして使う場合は、次のobjectと隣接する `.o.json` を保持します。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/binary_numbers.ail -o binary_numbers.o
```

利用側を `--object binary_numbers.o` でビルドすれば、元モジュールのソースなしで呼べます。
例えば `pack_i64_be(-1)` は8個の `FF`、`unpack_u16_be(b"\x01\x02")` は258です。
書き込みの範囲外や、読み取りで指定幅と異なる長さは `ValueError` です。
共通関数 `binary_encode_integer(value, width, reverse)` と
`binary_decode_integer(data, width, reverse)` のwidthは2/4/8、reverseは0/1です。
幅8は符号付きです。符号なし64ビットや可変幅整数は扱いません。

Windows/Linuxで、u16全65,536値、u32の73値、i64の133値をPythonの
`int.to_bytes` と整数の期待値へ照合し、529,712バイトの全出力を確認しました。
不正範囲・長さ・幅・方向89件と、例外後の正常呼出しも確認しています。
元ソースを削除し、日本語名へ移したobjectを使って検査しました。
これは有限入力の機能検証で、u32/i64全域の証明や速度改善の主張ではありません。
[実行記録](language_examples/binary_numbers_r400.json)に初回のテスト構文・指定名の誤りも残しています。

### 64ビット浮動小数点をバイナリへ変換する（R406）

`binary_float.ail` とC実装の組は、IEEE binary64の数値を固定8バイトで読み書きします。
Windows/Linuxの検証済みx86_64環境で、little-endianの `_le` とbig-endianの `_be` を使えます。

| 関数 | 入力 | 出力 |
| --- | --- | --- |
| `pack_f64_le` / `pack_f64_be` | `float` | 独立した所有コピーの `bytes` |
| `unpack_f64_le` / `unpack_f64_be` | 長さ8の `bytes` | `float` |
| `binary_encode_float(value, reverse)` | `float`、0/1 | little/big-endianの `bytes` |
| `binary_decode_float(data, reverse)` | 長さ8の `bytes`、0/1 | `float` |

有限値・正負のゼロ・無限大はビット表現を保ちます。NaNはNaNであることを保ちますが、
符号・ペイロード・signalling状態の一致を保証しません。NaNの生ビットを運ぶ用途では元の `bytes` を保持してください。
長さが8と違う入力や、方向が0/1以外ならAIL関数が `ValueError` を投げます。
直接のCアダプタは不正入力を空bytes/0.0へ戻すため、値域検査付きの上記AIL関数を使います。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/binary_float.c --interface language_examples/binary_float.json -o binary_float_native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/binary_float.ail --object binary_float_native.o -o binary_float.o
py -3 -X utf8 -B ailc.py language_examples/binary_float_main.ail --object binary_float.o --object binary_float_native.o -o binary_float_convert
.\binary_float_convert.exe input-le.bin output-be.bin 1
```

Linuxでは先頭を `python3 -B`、実行を `./binary_float_convert` に替えます。
例はlittle-endian数値列を指定方向へ保存します。ファイル長は8の倍数、方向0/1が必要です。
不正な長さ・方向・引数数なら終了2で、既存出力ファイルを変更しません。通常のI/O失敗や
原子的な書込み・永続化の保証は既存runtimeの範囲です。
両 `.o` と両 `.o.json` を一式保持すれば、元のC・AILソースなしでリンクして再利用できます。
他のOS/アーキテクチャやAIL runtime全体の並行実行は未検証です。

Windows/Linuxで9,326入力レコード（NaN 261件を含む）、74,608バイトの入力から
373,040バイトの全出力を独立Python `struct` へ照合しました。18不正呼出し、負ゼロでの回復、
引数不足・過剰・変換失敗時の出力保持、ソースなし・日本語パスへ移した依存一式の再利用も確認しました。
速度改善や全ビットパターンの証明ではありません。[実行記録](language_examples/binary_float_r406.json)。

### バイナリファイルの必要な位置を読む（R409）

`binary_ranges.ail` とC実装を組み合わせると、`read_binary_range(path, offset, count)` で
必要な位置の最大65,536バイトだけを取得できます。位置は非負の64ビット整数、長さは0～65,536です。
EOFでは短い `bytes` または空の `bytes` を返します。0バイトの要求もファイルを開いてseekします。
引数の値域違反・空パス・パス内NULは `ValueError`、open/seek/read/closeや割当の失敗は `OSError` です。
大きな位置がOSのseek範囲を超える場合も `OSError` になります。

```powershell
py -3 -X utf8 -B ail_chatgpt.py compile-c language_examples/binary_ranges.c --interface language_examples/binary_ranges.json -o binary_ranges_native.o
py -3 -X utf8 -B ail_chatgpt.py compile-module language_examples/binary_ranges.ail --object binary_ranges_native.o -o binary_ranges.o
py -3 -X utf8 -B ailc.py language_examples/binary_float_range_main.ail --object binary_ranges.o --object binary_ranges_native.o --object binary_float.o --object binary_float_native.o -o binary_float_range
.\binary_float_range.exe input-le.bin selected-be.bin 2 1
```

前節のbinary64 object一式を使います。例は0から数えた2番目の8バイトをlittle-endian数値として読み、
big-endianで保存します。元ファイル全体の長さは8の倍数でなくても構いませんが、選んだレコードは8バイト必要です。
NaNには前節の数値プロファイルが適用されます。引数不足・過剰・変換不能・負のindex・
位置の乗算が64ビットを超えるindex・不正な方向・短いレコードは終了2、通常のI/O失敗は終了3です。
読取りや引数の失敗では既存出力を保持します。成功時には出力を置き換えます。
出力の原子的置換・永続化は保証しません。

各読取りでファイルを開き直すため、別の呼出しの間にファイルが変わると異なる内容を読みます。
通常のseek可能なファイルが対象で、PIPE・ソケット・一貫したsnapshotのAPIではありません。
Cの借用bufferを既存アダプタが所有コピーにするため、後続呼出し後にも以前の結果を保持できます。
WindowsのUnicodeパスにはUTF-16のファイルAPIを使います。objectと各 `.o.json` を一式保管すれば、
元ソースなしで移動・リンク・再利用できます。

Windows/Linuxで16,777,480バイトの独立入力に対する10区間と保持済み区間、実行ファイル移動前後の
262,155バイトの全出力、C側とAIL側の拒否・I/O失敗後の回復を確認しました。
実Cの割当失敗はWindowsの2箇所、Linuxの1箇所へ注入し、次の呼出しで回復することも検証しました。
検査器の初回注入範囲の誤りと修正を含む[実行記録](language_examples/binary_ranges_r409.json)に境界を記載しています。
これは機能検証で、速度・RSSの改善、全OS・全入力・runtime全体の並行実行の保証ではありません。

### バイナリを返すライブラリ

`fn pack_record(payload: bytes) -> bytes` のように、バイナリを返す関数を別途コンパイルできます。
次の例は `AIL1`、4バイトのlittle-endian長さ、入力データを連結したレコードを保存します。
同じライブラリの `unpack_record` はヘッダーと長さを検査して元のデータを返します。

```powershell
py -3 -B ail_chatgpt.py compile-module language_examples/binary_record.ail -o binary_record.o
py -3 -B ailc.py language_examples/binary_record_main.ail --object binary_record.o -o binary_record
./binary_record.exe input.bin record.bin
```

標準出力は復元後のバイト数です。長さは0～4,294,967,295を形式上の範囲とし、
実際に処理できるサイズは空きメモリに制限されます。全体をコピーする方式です。
`bytes` 戻り値は呼出し側の関数が終了するまで保持され、別のAIL/C関数へ渡せます。
R396から `const RECORD_MAGIC = b"AIL1";` のような `bytes` 公開定数にも対応しました。
空・NUL・非UTF-8を保持し、読み取り・比較・slice・関数への引数・返却に使えます。
再代入や要素の書換えは拒否します。定数だけのモジュールも別途コンパイルできます。
オブジェクトの `.o.json` は小文字・偶数桁・空白なしのhexを保存し、変更はABI照合で拒否します。
利用側には定数値を複製するため、大きい定数の無コピー共有を保証する機能ではありません。
現行 `binary_record.ail` はこの公開定数を使い、保存するレコード形式は従来と同じです。
R400から長さの読み書きに `binary_numbers.ail` を使います。ソースから再構築する場合は
同モジュールも隣へ置いてください。公開Cライブラリ用builderは依存をまとめて構築します。
コンパイラ識別が変わったため、リンクする既存オブジェクトはソースから再生成してください。

### CからAILのレコードライブラリを使う（R397）

`language_examples/binary_record_c/build.py` は、Cの `native_tail` とAILの
`binary_record.ail` を名前空間付きobjectにし、Cから呼べる一つのライブラリへまとめます。
出力は `records.h`・`records.o`・`library.json` の3ファイルです。元のAIL/Cソースや
構築時の依存objectを持たずにCへリンクできます。対象OS・compilerに合わせて構築してください。

```powershell
py -3 -X utf8 -B language_examples/binary_record_c/build.py --out records_library
Copy-Item language_examples/binary_record_c/example.c records_library/example.c
Push-Location records_library
gcc -std=c11 example.c records.o -lm -o example.exe
./example.exe
Pop-Location
```

出力先は新規にしてください。Windowsでこのサンプルの構築と終了0を確認しました。
Windows MinGWでは日本語を含むobject絶対パスをリンカーへ渡すと失敗したため、
上のようにライブラリのディレクトリから `records.o` を相対パスで指定します。
OSの文字コード設定を変える必要はありません。

| 関数 | 処理 |
|---|---|
| `records_pack_tail(view, skip, &out, &error)` | Cで先頭skip byteを除き、AIL1＋uint32 little-endian長さ＋残りを返す |
| `records_unpack(view, &out, &error)` | マジック値と長さを検査してpayloadを返す |
| `records_magic(&out, &error)` | 公開bytes定数AIL1の所有コピーを返す |
| `records_free(out.data)` | 成功時の所有bufferを解放する |

入力は借用の `records_view`、成功時の出力は所有する `records_buffer` です。
開始位置が負・末尾以上なら空payloadのレコードになります。返却bufferは後続呼出しやエラー後も
保持でき、自分で解放します。status0が成功、形式不正は1、NULL＋長さ正などの不正C引数は9です。
失敗時のoutは変更せず、次の正常呼出しでerrorをリセットします。ポインタの有効性は呼出し側の責任です。
レコードの長さはuint32範囲、実際の処理量は空きメモリにも制限され、全体コピー方式です。

Linux/Windowsで各60実行をPython独立参照へ全byte照合し、移動後のリンク、所有buffer保持/解放、
短いheader・不正magic・長さ不一致・不正view後の回復、入力とライブラリの不変性を確認しました。
Windows配布物は25,391byte。速度・メモリ優位や全入力同値性の主張ではありません。
[実行記録](language_examples/binary_record_c/qualification_r397.json)に初回Windowsリンク失敗も残しています。

### Cからバイナリを返す

型宣言JSONの戻り値を `"result": "bytes"` にすると、C関数は次の型を返します。
この型は `compile-c` がCソースの前に定義するので、自分で再定義する必要はありません。

```c
typedef struct { const unsigned char *data; size_t size; } ail_c_bytes_view;
```

`data` は、戻った直後にAILがコピーし終えるまで読み取れる領域を指してください。
Cの静的領域や渡された入力の一部分を返せます。入力用の一時領域は返却値をコピーした後で解放します。
AILはコピーを所有し、C側の元領域を解放しません。C側で確保した領域の管理はC側の責任です。
`{NULL, 0}` は空の値、NULLで長さが正、または長さがint64上限を超える値は実行時に失敗します。
任意のポインタの有効性は検査できません。ローカル配列など寿命が終わる領域は返せません。
UTF-8を `str` として受け取る場合は、次の文字列返却を使います。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_bytes_result.c --interface language_examples/c_bytes_result.json -o tail.o
py -3 -B ailc.py language_examples/c_bytes_result.ail --object tail.o -o tail
./tail.exe input.bin output.bin 4
```

この例は先頭4バイトを除いた部分を保存し、保存した長さを出力します。
負の位置、末尾以降の位置では空になります。AILのラッパーを別途コンパイルした後も利用できます。
元のCソースなしで再利用する場合は、オブジェクトと対応する `.o.json` を一緒に保持してください。

### Cから文字列を返す

型宣言を `"result": "str"` にすると、Cは `compile-c` が定義する次の型を返します。

```c
typedef struct { const unsigned char *data; size_t size; } ail_c_utf8_view;
```

`size` はUTF-8のバイト数です。終端NULは不要で、範囲内のNULは文字列の一部として保持します。
借用期間とC側の所有権はバイナリ返却と同じです。AILは入力用一時領域を解放する前に
厳密なUTF-8検査と変換を行い、呼出し側が所有する文字列を返します。
不正UTF-8は `C result is not valid UTF-8` で実行を終了します。置換や黙った切り捨てはせず、
このエラーは `try` で捕捉できません。NULL/正の長さやint64上限超過も実行を終了します。

```powershell
py -3 -B ail_chatgpt.py compile-c language_examples/c_text_result.c --interface language_examples/c_text_result.json -o text.o
py -3 -B ailc.py language_examples/c_text_result.ail --object text.o -o text_value
./text_value.exe input.txt
```

この例はUTF-8ファイルの最初の `=` の後をCで選び、AILの文字列として出力します。
`名前=日本語😀` なら `日本語😀` を出力し、`=` がなければ空です。
改行やNULを含む残り全体を返すので、1行単位の設定ファイル解析とは異なります。
同じCオブジェクトに数値・バイト列・文字列の返却関数を混在させられます。
既存オブジェクトはコンパイラ実装が変わったため再生成してください。

## 標準入力と実行環境

標準入力を使うプログラムも書けます。

```powershell
py -3 -B ailc.py language_examples/stdin_sum.ail -o stdin_sum
1,2,3 | ./stdin_sum.exe
```

この例は `6` を出力します。
生成した実行ファイルの実行時にはPythonは不要です。既存の出力ファイルは上書きしません。

従来の表層構文はPythonに似ています。整数は符号付き64ビットで、算術オーバーフローは
エラーになります。範囲外の整数リテラルはコンパイル時に拒否します。
対応する構文と意味は `python/pkg-v12/SEMANTICS.md`、実装は
`python/pkg-v12/` が正本です。対応外の構文はコンパイル時に拒否されます。

`native/examples/ai_exchange/` の古い `.ail` は短縮命令形式で、この入口の表層言語とは
別です。従来の命令形式は `native/ail.py` の経路で扱います。C相当の標準ライブラリ、
自己ホスト、全用途の速度優位は未達です。

## 明示したC/C++/Rust修正版を比較する（R401）

AILの候補比較基盤へ、修正したネイティブソースも直接渡せます。

```text
python workflow/vibe/vibe.py auto main.c --candidate-source rewritten.c --checker oracle.py --input workload.bin --repeatable-cli --mode balanced --out fresh-native-result
```

`.cpp`・`.C`・`.rs` も同じ入口です。原版と修正版は同じ言語にし、
標準入出力・副作用なし・単一プロセス・繰り返し可能な仕事を宣言します。
原版と従来O3/Os候補を保持し、修正版だけを同じO2で構築します。
Rustはedition 2021/opt-level=2です。両版に同じ引数を渡します。
独立検査に失敗した修正版やコンパイル失敗は採用候補から除外し、結果へ保存します。

C/C++の `--source`・`--header` は共有依存を宣言します。修正版は原版と同じ親へ置き、
ローカル依存を全て宣言してください。Rustの別ファイルmod/includeやCMake/Cargoの
構成変更はこの単独入口の対象外です。`--mode original` で候補を指定する形は拒否します。
例えば共有実装と入れ子ヘッダは、両入口を同じフォルダへ置いて次のように指定します。

```text
python workflow/vibe/vibe.py auto main.c --source counters.c --header include/counters.h --header include/detail/types.h --candidate-source rewritten.c --checker oracle.py --input workload.bin --repeatable-cli --mode balanced --out fresh-shared-result
```

共有依存も全て固定・コピーして両版へ渡します。候補ごとに実装やヘッダを変える場合は、
R407から `--candidate-unit`・`--candidate-header` で候補の全依存を宣言できます。
例えば `candidate/main.c` とその親の `counters.c`・`include/counters.h`・
`include/detail/types.h` を候補とする形です。

```text
python workflow/vibe/vibe.py auto main.c --source counters.c --header include/counters.h --header include/detail/types.h --candidate-source candidate/main.c --candidate-unit counters.c --candidate-header include/counters.h --candidate-header include/detail/types.h --checker oracle.py --input workload.bin --repeatable-cli --mode balanced --out fresh-separate-result
```

候補のunit/headerのどちらかを指定すると、候補側の完全な依存宣言になります。
候補の親を基準に別の `candidate-project/` へコピーし、原版の依存は補いません。
両版の相対名が同じでも別内容を保持できます。この保存先と原版の宣言パスの衝突は拒否します。
入れ子ヘッダの未宣言、言語違い、親の外のパス、重複、source/header/checker/inputの
不正な共用や構築前後の書換えも拒否します。system headersとcompilerは外部依存です。
別依存版のLinux C++は4実装の独立7入力、資源比較、原版保持、移動後7入力で確認しています。
Linux Cの正常版は独立検査まで成功し、比較中の外部負荷で無効になりました。
内側の候補ヘッダだけを誤らせたC版は終了0でも除外し、正常3実装の原版保持・配布・移動を確認。
Windows/Linuxの実C/C++構築でも候補固有のヘッダが使われ、ソース一式とビルド元がなくても移動実行できました。
この実構築検査は資源比較・仕事全体の資格検査を代替しません。Windowsの別依存版資源比較は未実行です。
[別依存版の実記録](language_examples/native_source_candidates/qualification_r407.json)へ成功・失敗・未取得範囲を保存しています。

生成済み提案をJSONで渡す場合は、R408の `--candidate-patch` を使えます。
原版の宣言済み入口・全source/headerのSHA256と、変更するファイルの全文を分けます。
例えば `main.c` と `include/api.h` が宣言されたプロジェクトの形式は次です。
`<SHA256>` は各原版ファイルの生バイトのハッシュへ置き換えてください。

```json
{
  "base_sha256": {"main.c": "<SHA256>", "include/api.h": "<SHA256>"},
  "files": {"include/api.h": "#define VALUE (1 - 1)\n"}
}
```

```text
python workflow/vibe/vibe.py auto main.c --header include/api.h --candidate-patch proposal.json --checker oracle.py --input workload.bin --repeatable-cli --mode balanced --out fresh-patch-result
```

`files` は変更後の全文です。未変更のファイルも `base_sha256` に必要で、
`files` には変更する宣言済みファイルだけを書きます。検査器・入力や新規依存は編集対象にできません。
候補用の木を生成し、原版と候補を独立検査へ渡します。JSON/原版/生成候補の構築前後の変更も拒否します。
提案8MiB・編集128件の上限、重複キー、空の変更、古いハッシュ、不正なパスを検査します。
Rust `.rs` とNode `.cjs` も単独入口のパッチを同じ方法で渡せます。
この入口は生成済み提案の受渡しで、AIの提案理由を正解や速度の証拠には使いません。
実処理系の長い独立7入力と候補の移動はWindows全4言語、Linux C/C++/Rustで確認済み。
R408のLinux Node試行はPATH上のruntime欠落でskipでした。
R411では既存NodeのPATHを検証プロセス内に設定し、応答取り込み後の長入力と移動後の一致を確認しました。
全言語・全OSの資源比較やネイティブAI生成の実試行は未完了です。
[R408記録](language_examples/native_source_candidates/qualification_r408.json)へ実試行・費用・拒否・skipを保存しています。

R411の `prepare-source-proposal` / `accept-source-proposal` を使うと、原版全体・依頼文・
生成用prompt/schemaを固定し、既存のJSON応答からこのパッチを作れます。
準備時の `context_sha256` を応答取得前に独立保存し、取り込み時に渡してください。
応答形式は `edits`（宣言済みpathと変更後のsource全文）・`rationale` です。
取り込み時は未検証で、モデル呼出し・性能案の根拠審査・総AI費用の取得は行いません。
[コマンドと上限](README_AUTO_ENTRY_JA.md#生成用の文脈を固定し応答を取り込むr411)と
[両OSの段階検証記録](language_examples/native_source_candidates/proposal_qualification_r411.json)を参照してください。
AIL専用のcandidate-module/object/separateは使いません。
配布物には選択した実行物を残します。これは修正版の比較入口で、一般的なコード生成や
任意プログラムの同値性を証明する機能ではありません。
[再現例](language_examples/native_source_candidates/README.md)ではC/C++のLinux比較・原版保持・
移動後検証と、誤答/構築失敗の拒否が通りました。Rustは構築と独立検証まで通り、
比較は外部CPU負荷で無効です。Windows Cも負荷で停止しています。未完了項目を成功扱いしません。
R402のLinux共有C/C++版も4実装の資格・資源比較・原版保持・移動後7ケースに合格しました。
空入力前の長さ0の関数呼出し、共有実装と2段ヘッダの不変性、配布物23pinsの不変性を確認しています。
[共有版記録](language_examples/native_source_candidates/qualification_r402.json)に全観測を保存しています。
Windows共有版は未実行で、この実例を一般同値性・速度改善・全資源取得へ拡張しません。

## 明示したNode修正版を比較する（R399）

AILの候補比較基盤は、既存の単独CommonJSソースにも修正版を渡せます。
両方とも組込みモジュールを直接読み込む、標準入出力・単一プロセスの仕事を宣言します。
R460では単独CommonJSも`require('fs')`・`require('crypto')`などの通常表記を扱います。
`node:`付き表記との混在も可能です。実際のNodeの`isBuiltin`照合を通してからコピーします。
検証器は別のPythonファイルを指定し、ソース・検証器・入力は別々のファイルにしてください。

```text
python workflow/vibe/vibe.py auto app.cjs --candidate-source tuned.cjs --checker oracle.py --input workload.bin --repeatable-cli --mode balanced --confirmation-pairs 24 --out fresh-node-result
```

原版・修正版を独立検証してから資源比較し、採用条件を満たさなければ原版を配布します。
候補のsource/module/object指定はAILとNodeで区別し、Nodeには `--candidate-source` だけ使えます。
任意JavaScriptの書換え生成や同値性の証明は含みません。
Linuxの16MiB超・探索12組比較・誤実装拒否・移動後検証は[Node実例](language_examples/node_stream/README.md#明示したnode修正版を比較するr399)にあります。

R460は既存の構文検査を単独CommonJSにも使い、相対読込みには`--source`での宣言を求めます。
npmパッケージ、別名・動的ローダー、不確かな構文は引き続き明示契約が必要です。
これは対応する入口の追加で、新しい高速化の採用結果ではありません。

## 既存HTTPソフトのメモリを診断する

AILの候補比較基盤には既存Node.jsソフトの実例もあります。Node.jsが入っている環境で、
AIL_CURRENTから次を実行すると、固定入力の事前変換＋cache版を通常/計測ありで8回起動します。

```powershell
py -3 -X utf8 -B language_examples/node_http/packed_memory_profile.py --output 新規診断.json
```

20,480応答を独立期待値と照合し、全プロセス資源・入力/ソース不変とメモリの記録点を確認します。
結果の出力先は新規ファイルにします。診断失敗でも取得済み結果を保存し、採否は変更しません。
Windowsで実行済み、Linuxの現在のWSLはNode.js不在で実HTTP未検証です。
これはNode.js実例の診断で、AIL言語のHTTP標準ライブラリではありません。
数値・制限・必要な資源計測環境は[実例の説明書](language_examples/node_http/README.md)を参照してください。

## AILソースの候補比較

原版と、別に作ったAIL候補を公開コンパイラで構築し、独立検証・実測・採否判断・配布物検証へ渡せます。

```text
python workflow/vibe/vibe.py auto main.ail --candidate-source candidate/main.ail --checker oracle.py --input workload.bin --repeatable-cli --mode speed --max-memory-mib 64 --minimum-saving-fraction 0 --confirmation-pairs 96 --out comparison
```

原版の追加ソースは`--source`、候補の追加ソースは候補入口の親を基準に`--candidate-module`で宣言します。
再利用objectは原版が`--object`、候補が`--candidate-object`です。各`.o`の隣接`.o.json`と依存closure全体を用意します。
コピーは原版と候補で分離し、候補には固定した公開コンパイラを使います。Python/Cコンパイラも構築前後に内容照合します。
誤答候補を除外し、構文・ABI・objectのhashが不正な候補は失敗を保存して原版を比較対象に残します。
元/コピーの改変は全体の失敗です。原版のみのモードには候補を渡せません。

確認へ進む候補の96組は両順序48組ずつの新規確認です。確認組数は実行前に予約し、前後A/A・資源上限・全出力照合と探索費用を既存基準で検査します。
メモリ64MiBは例なので実際の仕事に合わせて指定してください。結果の`optimization_status`とselectionの判定を確認します。
対応は宣言したsingle-process stdin/stdout仕事の範囲です。候補自動生成、無限入力の同値性、全用途最速を証明する機能ではありません。
[入口の詳細](README_AUTO_ENTRY_JA.md)に候補module/object付きコマンドと費用の範囲があります。

複数回の確認は事前に作った枠を`--confirmation-family`で共有します。失敗・中断の枠も残します。
WSLの実測では出力先のファイルシステムを固定し、Linux永続領域を使ってください。
今回の16MiB入力では共有領域への出力で資格タイムアウトし、`/tmp`の結果は再起動で消失しました。
これらを成功測定へ読み替えません。小さい配布物はWindowsへ移して再検証できます。

R391は行番号付けの型付き原版と既存C接続候補でこの入口を実行しました。
固定16MiBのLinux実例では、96組・現行基準の最小改善率0で候補採用、中央値比1.19394です。
成果物を日本語名の別フォルダへ移し、7入力の全出力一致を再確認しました。
A/A最大揺れ42.65%、CPU効率の確認は未達、未知の入力や統計前提の保証もありません。
失敗・消失・検査を含む既知費用の下限856.72秒と生データを[保存結果](language_examples/number_stream_batch_auto_linux_r391.json)へ保持しています。
これは限定したLinux仕事の実例です。Windows native資格・全用途速度優位・総AI効率の達成ではありません。

## Linux HTTPの同時タスク数を確認する（R398）

既存の `language_examples/node_http/verify.py --output 新規JSON` で、所有cgroupとkernelの
`pids.current` / `pids.peak` が使える場合に `resources.task_peak_status` が `verified` となります。
`peak_cgroup_tasks` はスレッドを含む生存期間中の最大同時数、`tasks_current` は終了後0です。
両interfaceがそろわなければ取得不可を記録します。CPU・メモリの取得可否は別に確認してください。
累計プロセス数や全機械のタスク数ではなく、この値だけで高速化を採用するものでもありません。
Linux実例と比較時の検査範囲は[HTTP実例の説明](language_examples/node_http/README.md#linuxの最大同時タスク数r3982026-10-03)にあります。

## HTTP候補を現行基準で確認する

8MiBの固定データも全本文を確認する場合は、先に次を実行します（R461）。

```powershell
py -3 -X utf8 -B language_examples/node_http/verify.py --workload manifest-heavy --include-data --rounds 2 --concurrency 1 --connection-mode keep_alive --output fresh-full-data.json
```

19要求（データ9・manifest9・404）を各基準実行で2巡します。本文上限はこの指定で8MiB、
通常の既定は4MiB、期待本文の合計上限は16MiBです。`include_data`、`effective_max_body_bytes`、
各runの`request_body_limit_bytes`と`resource_verification_status`を確認してください。
比較のmanifest-heavy負荷はmanifest中心の10要求で、全本文検証とは別です。

既存Node.jsサービスのpacked＋cache候補を、現行の24組確認で比較できます。
Node.jsと全プロセスの資源を検証できる環境で、AIL_CURRENTから実行します。
出力先はそれぞれ未作成のディレクトリにしてください。

```powershell
py -3 -X utf8 -B language_examples/node_http/prepare_cache.py --packed --confirmation -o fresh-inputs --prior-cost-seconds 0
py -3 -X utf8 -B ail_chatgpt.py build-http fresh-inputs/seed/comparison.json --recipe fresh-inputs/recipe/recipe.json -o fresh-build --compare
```

`--prior-cost-seconds 0` は例です。既知の先行開発・検証費があれば実測秒数を渡してください。
生成設定は `confirmation: true` / `pairs: 24`。両順序12組ずつの計画を初回起動前に保存し、
前後A/Aとwarmupを含む64起動を検証します。比較完了のexit 0と採用推奨は別で、
比較結果JSONの `status: "complete"` と `assessment.adopt` を確認してください。旧8組診断からは採用しません。

R346のWindows実測では163,976応答と9入力資産の全byteが独立期待値に一致し、
移動・元入力削除後も検証できました。固定負荷で時間1.729倍、CPU時間3.265倍、
Jobピークコミット31.42%減の採用推奨を得ています。R346時点ではLinux Nodeは未検証でした。
R394では既存Node v24.14.1/Linux WSLの固定負荷で24組を確認し、時間1.767倍、CPU時間3.697倍、
cgroup peak約41.3%減の条件付き採用推奨と移動後検証を得ました。Windows commitとは別の資源です。
Linuxの工程価格・比較・費用の原記録は[実例の説明書](language_examples/node_http/README.md#linuxでの事前評価と候補比較r3942026-10-03)にあります。
全用途の保証や総開発費の回収を示す数値ではありません。
[保存結果](language_examples/node_http/packed_confirmation_windows_20261002_r346.json)と
[実例の説明書](language_examples/node_http/README.md)に計画・生データ・再実行失敗の境界があります。

## AILからC解析部品を使うログ集計（R421）

R423では、通常の公開`compile-c`/`compile`で、文字列入力のコピー契約に基づく行ごとの解放を生成します。
元ソースのないC objectとAIL wrapperの再利用、前行・別名の保持、固定100万行の出力一致を確認しました。
通常ビルド版のピークRSSは640KiBでした。[構築方法と実行物](language_examples/access_log/README.md#r423--通常のc連携で行データを解放する)を参照してください。
R424で通常版の工程を測りました。C呼出しが計測版の約53〜58%、読込みが約29〜37%です。
計測の負荷と達成可能な読込み参照を含む[次の改善価格](language_examples/access_log/README.md#r424--公開ビルド版の工程と次の改善価格)を確認してください。新しい速度の採用資格ではありません。
R425でLinuxの所有ファイル読込みを公開ビルドへ反映しました。固定ログ2入力の96組で壁時間中央値11.24%短縮、RSS512→640KiBです。
CPU改善は未認定です。[採用範囲・実行物・再利用](language_examples/access_log/README.md#r425--公開ビルドの所有ファイル読込みを改善する)を参照してください。

採用目的と交換条件は[用途ごとの採用基準](README_AUTO_ENTRY_JA.md#用途ごとの採用目的と交換条件r422)を参照してください。
速度重視では上限回復だけで遅い候補を採用しません。`balanced` は測定一回の悪化も認めない厳格な選択肢です。

`language_examples/access_log/native_parser.c`と型宣言JSONから作るオブジェクトを、`native_main.ail`から呼べます。Linux/Windowsの公開ビルドと、元Cソースのない再リンクを検証しました。Linuxの専用実行物は、採用済み版との固定比較でログ2入力合計の中央値22.8%短縮、RSS最大768KiBでした。この入口に限定した行ごとの寿命処理を含み、一般C接続の自動最適化を意味しません。実行方法・再ビルド・適用条件は[ログ集計の説明](language_examples/access_log/README.md)を参照してください。

### BYTEARRAYを直接ファイルへ書く（R627）

write_bytes(path, data) と append_bytes(path, data) はbytesとbytearrayを受け付けます。

~~~ail
let output = bytearray(b"hello\n");
write_bytes("output.bin", output);
append_bytes("output.bin", bytearray(b"!"));
~~~

bytearrayを直接渡すと、同期書き込みが返るまで保持し、その内容を書き込みます。
bytes(output)を渡す形は従来どおり独立コピーを作ります。
## 整数の16進表記と小数リストの並べ替え（R821）

`hex(value:int)` は小文字の `0x` / `-0x` 表記を返します。符号付き64ビット整数の全範囲に対応し、返る文字列は独立した値です。

```text
fn main()->int {
    print(hex(-9223372036854775808));
    let values:list[float]=[3.5,-1.0,2.0];
    values.sort();
    print(values[0]);
    return 0;
}
```

所有するローカルの `list[float]` は、引数なしの `sort()` 文で昇順に並べ替えられます。無限大も扱い、NaNがあれば変更前にValueErrorを返します。正負のゼロは同値として扱い、同値間の順序は保証しません。借用引数を並べ替える場合は `let owned=values.copy(); owned.sort();` とします。

初期値付き `list[tuple[int,int]]`、`list[tuple[float,float]]`、`list[tuple[int,bytes]]` は上記の固定幅レコードの契約に従います。通常の `list[int]` / `list[float]` にtupleを混ぜることはできません。
## 文字列の評価順とcodecの値条件（R825）

`strip(chars)` / `lstrip(chars)` / `rstrip(chars)` は、元の文字列、削る文字列の順に一度ずつ評価します。後の評価が元の構造体フィールドを書き換えても、処理する元の値は保持します。例外時も通常のfinallyと解放が働きます。

`api-builtin str.lstrip` / `str.rstrip` で、引数なしとstr 1引数の署名を取得できます。integer/float64 codecの問い合わせには、幅、符号、byteorder、長さの整列、空入力でも検査する条件を含めます。整数codecは幅1/2/4が符号なし、8が符号付き64ビットです。byteorderは0がlittle endian、1がbig endianです。