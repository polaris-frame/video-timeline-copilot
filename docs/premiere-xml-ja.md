# Premiere Pro用XML出力：日本語の使い方（Windows）

このガイドでは、動画の無音部分をカットして、Premiere Proで続きを編集できるシーケンスを作る手順を説明します。すでに編集内容の `edl.json` がある場合は、[XMLを出力する](#5-premiere用xmlを出力する)から始められます。

この機能は `feat/premiere-xmeml` ブランチにあります。未マージの間は、以下のブランチ指定付きコマンドでインストールしてください。

## 目次

- [できることと出力ファイル](#1-できることと出力ファイル)
- [初回の準備・インストール](#2-初回の準備インストール)
- [素材フォルダを用意する](#3-素材フォルダを用意する)
- [無音カットの編集内容を作る](#4-無音カットの編集内容を作る)
- [Premiere用XMLを出力する](#5-premiere用xmlを出力する)
- [Premiereで読み込む](#6-premiereで読み込む)
- [無音カットを調整する](#7-無音カットを調整する)
- [文字起こし・字幕を追加する](#8-文字起こし字幕を追加する任意)
- [カットを指定する・複数素材を使う](#9-カットを指定する複数素材を使う)
- [再編集・更新の流れ](#10-再編集更新の流れ)
- [トラブル対処](#11-トラブル対処)
- [対応範囲と確認状況](#12-対応範囲と確認状況)

## 1. できることと出力ファイル

処理の流れは次のとおりです。

```text
元動画 → 素材情報の取得 → 編集内容（edl.json） → Premiere用XML → Premiereで読み込み
```

| ファイル | 役割 |
| --- | --- |
| `edit/media_index.json` | 素材の長さ、解像度、FPS、音声チャンネル数、音声サンプルレートなど |
| `edit/edl.json` | どの素材の何秒から何秒までを、どの順番で置くかという編集内容 |
| `edit/<プロジェクト名>.premiere.xml` | Premiereへ読み込むカット済みシーケンス |
| `edit/subtitles/*.srt` | 任意で作成する字幕。XMLとは別に読み込みます |

XMLは元動画を参照します。動画データをXMLの中に埋め込む機能ではありません。元動画はそのまま保存し、XML出力後も同じ場所に置いてください。

## 2. 初回の準備・インストール

以下のコマンドは **WindowsのPowerShell** で実行します。Premiereのパネル内に入力するものではありません。スタートメニューで「PowerShell」を検索して開いてください。

### 2-1. 必要なもの

- Adobe Premiere Pro：生成したXMLを読み込むときに使います。
- Git：GitHubからこの機能を取得するために使います。
- uv：PythonとCLIの実行環境を管理します。
- FFmpeg／FFprobe：素材情報の取得、無音検出、プレビューに使います。

すでに使えるものは再インストール不要です。確認用コマンド：

```powershell
git --version
uv --version
ffmpeg -version
ffprobe -version
```

### 2-2. Gitとuvを準備する

Gitがない場合は [Git公式のWindows向け案内](https://git-scm.com/downloads/win)からインストールしてください。

uvがない場合、WinGetを使える環境では次のコマンドでインストールできます。

```powershell
winget install --id=astral-sh.uv -e
```

別のインストール方法は [uv公式ドキュメント](https://docs.astral.sh/uv/getting-started/installation/)にあります。インストール後はPowerShellを開き直して、`uv --version` を確認します。

### 2-3. FFmpeg／FFprobeを準備する

[FFmpeg公式ダウンロードページ](https://ffmpeg.org/download.html)のWindows向けビルド案内から取得します。展開したフォルダの `bin` に `ffmpeg.exe` と `ffprobe.exe` があることを確認してください。

たとえば `C:\Tools\ffmpeg\bin` に置いた場合、現在のPowerShellだけで使えるようにするには：

```powershell
$env:Path = "C:\Tools\ffmpeg\bin;" + $env:Path
ffmpeg -version
ffprobe -version
```

この設定はそのPowerShellを閉じると元に戻ります。毎回設定したくない場合は、Windowsの「環境変数」画面でユーザーの `Path` に実際の `bin` フォルダを追加し、PowerShellを開き直します。

### 2-4. Premiere対応版をインストールする

```powershell
uv tool install --force --python 3.12 "video-timeline-copilot @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
```

初回は必要に応じてPythonの取得が行われます。インターネット接続が必要です。

```powershell
vtc --help
vtc export-premiere-xml --help
```

`vtc` が見つからない場合は、次を実行してからPowerShellを開き直します。

```powershell
uv tool update-shell
```

`export-premiere-xml` がヘルプに表示されれば準備完了です。この手順はCLIをインストールします。Codex用スキルの登録は別の操作です。以下のPowerShellでの操作にはスキル登録は不要です。

## 3. 素材フォルダを用意する

このガイドでは次のフォルダを使います。自分の保存場所やファイル名に置き換えてください。

```text
C:\Videos\my-video\
  raw\
    interview.mp4
  edit\
```

エクスプローラーで `raw` フォルダを作り、元動画を入れます。`edit` はコマンド実行時に作成されます。1つの編集につき1つの `my-video` 相当のフォルダを使うと管理しやすくなります。

素材情報を取得します。

```powershell
vtc inventory "C:\Videos\my-video"
```

`C:\Videos\my-video\edit\media_index.json` ができます。素材フォルダ全体を指定し、`edit` フォルダだけを指定しないでください。

ファイル名に日本語や空白があっても、パス全体を `"..."` で囲めば指定できます。素材は `my-video` の内側に置いてください。

## 4. 無音カットの編集内容を作る

最初は次の設定を使ってください。

```powershell
vtc draft-silence-cut "C:\Videos\my-video\raw\interview.mp4" --edit-dir "C:\Videos\my-video\edit" --style documentary
```

無音検出で残す区間を選び、`edit/edl.json` を作ります。音量にもとづく下書きなので、話の意味を理解してハイライトを選ぶ処理ではありません。BGMが鳴り続けている動画は、話していない部分も残る場合があります。

音声の語尾や語頭を切りすぎないように、必要なら次を実行します。

```powershell
vtc refine-audio-cuts "C:\Videos\my-video\edit\edl.json"
```

このコマンドは元のEDLを残し、`edit/edl.audio-refined.json` と検証レポートを作成します。結果を使う場合は、次の章でこのファイルを指定します。元の `edl.json` を直接更新したい場合だけ `--replace` を付けてください。

**実行結果にエラーが出た場合は、その内容を解決してから次へ進みます。** 全コマンドを一度に貼り付けず、1つずつ確認してください。

## 5. Premiere用XMLを出力する

通常のEDLから出力する場合：

```powershell
vtc export-premiere-xml "C:\Videos\my-video\edit\edl.json"
```

音声境界を調整したEDLを使う場合：

```powershell
vtc export-premiere-xml "C:\Videos\my-video\edit\edl.audio-refined.json"
```

出力先を固定すると、探しやすくなります。

```powershell
vtc export-premiere-xml "C:\Videos\my-video\edit\edl.json" --out "C:\Videos\my-video\edit\cut.xml"
```

標準のファイル名はEDLの `project_name` から作られます。日本語などはファイル名用に置き換えられるため、実行結果の `Premiere XML -> ...` に表示されたパスを確認してください。`--out` で既存ファイルを指定すると、正常な生成が完了した後に上書きします。

Premiere用のコマンドは **`export-premiere-xml`** です。`export-fcpxml` が作る `.fcpxml` は別形式です。

## 6. Premiereで読み込む

1. Premiere Proを開き、新しいプロジェクトを作るか既存プロジェクトを開きます。
2. **「ファイル → 読み込み」**（Windowsでは通常 `Ctrl + I`）を選びます。
3. 生成した `cut.xml` または `.premiere.xml` を選びます。
4. プロジェクトパネルに読み込まれたシーケンスを開きます。EDLに複数のタイムラインがあれば、それぞれのシーケンスが入ります。
5. 下記の項目を確認し、そのままテロップ、色、音量、トランジションなどを編集します。
6. 最後にPremiereのプロジェクト（`.prproj`）として保存します。

### 読み込み直後の確認

- 「シーケンス設定」の解像度とFPSが意図どおりか。
- 選んだ区間だけが、意図した順番で置かれているか。
- 最初と最後を再生して、口の動きと音が合っているか。
- 「リンク選択」が有効な状態で、映像を選ぶと対応する音声も選ばれるか。
- モノラル／ステレオ／多チャンネル素材で、必要な音が存在するか。ステレオの左右とミキサーの出力先も確認してください。
- カットの前後で言葉が欠けたり、不自然な間になったりしていないか。

XMLには元素材のパスが入っています。素材がオフラインになる場合は [トラブル対処](#11-トラブル対処)を参照してください。

## 7. 無音カットを調整する

### プリセット

| `--style` | 用途の目安 | 無音の最短長さ | 前後の余白 |
| --- | --- | --- | --- |
| `documentary` | 初回・インタビュー | 0.7秒 | 0.25秒 |
| `social` | テンポを速めたいとき | 0.35秒 | 0.12秒 |
| `highlight` | やや短い間を目指す下書き | 0.5秒 | 0.18秒 |
| `longform` | 長尺・間を多めに残す | 0.9秒 | 0.35秒 |

`highlight` も無音カットの設定名です。内容の重要度にもとづくハイライト選択は行いません。

### 主な設定

| オプション | 意味 | 調整例 |
| --- | --- | --- |
| `--noise=-35dB` | この音量より小さい音を無音候補にする | `-40dB` は静かな声を残しやすく、`-30dB` は無音候補を増やしやすい |
| `--min-silence 0.7` | カット候補にする無音の最短秒数 | 大きくすると短い間を残す |
| `--padding 0.25` | 残す音声の前後につける余白 | 語尾が欠ける場合は増やす |
| `--merge-gap 0.35` | 近い区間をまとめる間隔 | 大きくすると細かいカットを減らす |
| `--min-segment 0.8` | 残す区間の最短秒数 | 0.8秒未満には設定できない |

たとえば、話し始め・語尾と間を多めに残す設定：

```powershell
vtc draft-silence-cut "C:\Videos\my-video\raw\interview.mp4" --edit-dir "C:\Videos\my-video\edit" --noise=-40dB --min-silence 0.9 --padding 0.35 --merge-gap 0.4
```

この処理を再実行すると `edl.json` は上書きされます。手動で直したEDLを残す場合は、先に別名で保存するか `--out` を使います。

```powershell
vtc draft-silence-cut "C:\Videos\my-video\raw\interview.mp4" --edit-dir "C:\Videos\my-video\edit" --out "C:\Videos\my-video\edit\edl.try2.json" --style longform
vtc export-premiere-xml "C:\Videos\my-video\edit\edl.try2.json" --out "C:\Videos\my-video\edit\cut.try2.xml"
```

## 8. 文字起こし・字幕を追加する（任意）

この章は会話のある動画向けです。無音カットとXML出力だけなら不要です。

### 8-1. 文字起こし対応版をインストール

```powershell
uv tool install --force --python 3.12 "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
```

### 8-2. 日本語の文字起こし

まずはGPU設定に依存しにくいCPU設定で実行します。

```powershell
vtc transcribe "C:\Videos\my-video\raw\interview.mp4" --edit-dir "C:\Videos\my-video\edit" --language ja --device cpu --compute-type int8
```

初回は音声認識モデルのダウンロードが発生することがあります。結果は `edit/transcripts/interview.json` に保存されます。既存の同名ファイルがある場合はキャッシュが使われます。

文字起こしを無音カットにも使いたい場合は、この処理を **無音カットの前** に実行します。すでにEDLを作った場合は、手動編集内容を保存してから無音カットを作り直してください。文字起こしがあると、単語の時刻を使って境界を調整します。

### 8-3. 字幕を出力

最終的にXMLに使ったものと同じEDLを指定します。

```powershell
vtc export-srt "C:\Videos\my-video\edit\edl.json"
```

音声調整済みEDLを使うなら：

```powershell
vtc export-srt "C:\Videos\my-video\edit\edl.audio-refined.json"
```

生成した `.srt` をPremiereに読み込み、シーケンスの先頭へ置きます。字幕はXMLに含まれません。文字起こし結果がない状態では字幕の内容を生成できません。日本語の誤認識や字幕の区切りはPremiereで確認・修正してください。

## 9. カットを指定する・複数素材を使う

`draft-silence-cut` は1つの動画から下書きを作ります。複数素材を組み合わせる場合や、残す時間を手動で決める場合は、`edit/edl.json` を作成・編集します。

以下は、`raw/interview.mp4` の10〜15秒と、`raw/broll.mp4` の2〜5秒を続けて並べる例です。各素材が指定区間以上の長さを持つことを確認してください。メモ帳などで **UTF-8の `edl.json`** として保存します。拡張子が `.json.txt` にならないよう注意します。

```json
{
  "version": 1,
  "project_name": "My_Edit",
  "fps": 29.97,
  "timelines": [
    {
      "name": "Main",
      "resolution": [1920, 1080],
      "sources": {
        "A001": "raw/interview.mp4",
        "B001": "raw/broll.mp4"
      },
      "ranges": [
        {
          "source": "A001",
          "source_start": 10.0,
          "source_end": 15.0,
          "record_start": 0.0
        },
        {
          "source": "B001",
          "source_start": 2.0,
          "source_end": 5.0,
          "record_start": 5.0
        }
      ]
    }
  ]
}
```

| 項目 | 意味 |
| --- | --- |
| `fps` | 出力シーケンスのFPS。23.976／29.97／59.94も指定可能 |
| `resolution` | 出力シーケンスの幅・高さ。素材の解像度とは別 |
| `sources` | 素材IDとファイルの対応。相対パスの基準は `my-video` |
| `source` | このカットに使う素材ID |
| `source_start`／`source_end` | 元動画の先頭からの秒数。埋め込みタイムコードの表示値ではない |
| `record_start` | 出力シーケンスの先頭からの秒数 |

普通の速度ならカットの長さは `source_end - source_start` です。上の例では1つ目が5秒なので、2つ目の `record_start` は5秒です。空白や重なりを作らず、連続して並べてください。`record_start` を全区間で省略し、配列の順番に自動で並べることもできます。

EDLの `fps` と `resolution` を変更しても、元動画ファイルは変換されません。素材ごとのFPS・解像度・音声情報は `media_index.json` またはFFprobeから取得されます。Premiereで最終的な見え方を確認してください。

素材を追加したら再度 `inventory` を実行し、XMLを出力します。

```powershell
vtc inventory "C:\Videos\my-video"
vtc export-premiere-xml "C:\Videos\my-video\edit\edl.json" --out "C:\Videos\my-video\edit\cut.xml"
```

## 10. 再編集・更新の流れ

### EDL側でカットを変更したとき

1. `edl.json` の残す区間・順番を変更します。
2. 同じEDLからXMLと、必要ならSRTを再出力します。
3. Premiereで新しいXMLを読み込み、前のシーケンスと区別して開きます。

**XMLを上書きしても、Premiereに読み込み済みのシーケンスは自動更新されません。** 新しいXMLの読み込みは別のシーケンスとして扱ってください。Premiere側で追加したテロップや色調整を、新しいシーケンスへ自動で移す機能はありません。

### 素材を移動・差し替えたとき

EDLの `sources` を新しい場所に合わせて更新し、`inventory` → XML出力をやり直します。XMLには絶対パスが入るため、別PCに渡すときも素材を渡し、Premiere側で必要に応じて再リンクします。

### このツールを更新するとき

ブランチの更新を取り直す場合：

```powershell
uv tool install --force --reinstall --refresh --python 3.12 "video-timeline-copilot @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
```

文字起こし機能も使う場合はパッケージ名を `video-timeline-copilot[transcribe]` にしてください。

## 11. トラブル対処

| 症状・エラー | 確認・対処 |
| --- | --- |
| `uv`／`git` が見つからない | インストール後にPowerShellを開き直す。各 `--version` を確認 |
| `vtc` が見つからない | `uv tool list` でインストールを確認。`uv tool update-shell` 後にPowerShellを開き直す |
| `unknown command: export-premiere-xml` | 元リポジトリの `main` 版などを使っている可能性。2-4のブランチ指定付きコマンドで入れ直す |
| FFmpeg／FFprobeが見つからない | 2-3を確認。`bin` の場所を `Path` に追加し、両方の `-version` を確認 |
| `source not found`／`does not exist` | 素材の名前・拡張子・場所を確認。空白を含むパスは引用符で囲む |
| `path escapes workspace` | 素材を `my-video` の内側へ置く。`edit/edl.json` の1つ上のフォルダが素材ルート |
| JSONの読み取りエラー | 余分なカンマ・コメント・全角引用符がないか確認。UTF-8で保存 |
| `Invalid media metadata` | `inventory` を再実行し、該当素材の `error`、FPS、長さなどを確認 |
| `outside media duration` | 指定した終了秒数が素材の長さを超えていないか確認。素材差し替え後は再inventory |
| `contiguous`／gap／overlap | `record_start` を前のカットの終了位置に合わせる。長さは終了秒−開始秒 |
| `shorter than the minimum` | 区間を通常0.8秒以上にする。EDLでより長い最短時間を設定している場合はその値に従う |
| `retimed ranges` | 速度変更を外す。速度変更は読み込み後にPremiereで行う |
| transforms／visual layers／audio overrides | 該当するEDL指定を外すか、Premiereで実施する |
| `video track 1 only` | この出力は単一映像トラック用。追加映像トラックはPremiereで作る |
| XMLが見つからない | 実行結果のパスを確認するか、`--out` で `cut.xml` に固定 |
| Premiereでメディアがオフライン | 元素材の位置を確認。「メディアをリンク」で素材を選ぶか、正しいパスでXMLを再生成 |
| 映像を選んでも音声が選ばれない | Premiereの「リンク選択」を確認。素材に音声があるか、音声クリップが読み込まれたか確認 |
| 語頭・語尾が欠ける | `--padding` を増やし、`refine-audio-cuts` を試す。カット前後を実際に再生して調整 |
| 無音がほとんど削除されない | BGM・環境音が無音判定を妨げていないか確認。`--noise`／`--min-silence` を調整 |
| 字幕が空／足りない | 対応する素材名の文字起こしJSONが `edit/transcripts` にあるか確認 |
| GPUのDLLエラー | 文字起こしを `--device cpu --compute-type int8` で実行 |
| 長いNTSC編集で通常の `validate-edl` が1フレームの重なりを報告する | 既存検証には別丸めの制約がある。Premiere exporterは正確なFPSで独自に時刻を検証する。exporter自体のエラーは解決が必要 |

困った場合は、実行したコマンドとエラーメッセージ、素材のFPS・解像度・音声チャンネル数、Premiereのバージョンを添えて状況を確認してください。

## 12. 対応範囲と確認状況

### 対応しているもの

- 通常速度・連続したカット、映像トラック1。
- 23.976／29.97／59.94などのFPS。素材FPSとシーケンスFPSが違う場合のフレーム換算。
- 素材ごとの解像度、音声チャンネル数、音声サンプルレートの取得。
- 映像と対応する音声チャンネルのリンク。無音声素材は映像のみ。
- 素材の埋め込みタイムコード。EDLの秒数は素材の先頭を0秒として指定。
- 日本語・空白を含むWindowsパス、複数シーケンス。

シーケンスの音声は48kHz設定です。元素材の44.1kHzなどの情報は素材メタデータとして保持します。

### 現在の制限

- 速度変更、ズーム・位置・クロップなどの変形、画面合成、追加映像トラック、音声オーバーライドは未対応です。該当する指定はエラーになります。
- 字幕は別のSRTです。編集メモ・マーカーはXMLに出力しません。
- 素材情報取得は最初の映像ストリーム・最初の音声ストリームが対象です。独立した音声ストリームを複数持つ素材は、使いたい音声を選んだ素材に整えてください。
- 可変フレームレート（VFR）は正確な読み込みを保証しません。必要に応じて固定フレームレート（CFR）素材へ変換します。
- Premiereで編集した内容を、このFCP7 XMLからEDLに戻す機能はありません。既存の `import-fcpxml` は別のFCPXML形式用です。

Windowsで237件の自動テストが通っています。添付の `test.xml` の25カットと `C0019.xml` のステレオ構造を回帰テストに追加しました。修正後の **Premiere本体での読み込み・再生確認は未実施** です。

### 実機での再検証

1. 更新版をインストールし、以前と同じ設定で `draft-silence-cut` を再実行してEDLを作り直します。新しいEDLは `record_start` を省略し、各exporterが順次配置します。
2. `vtc validate-edl "C:\video\vtc-test\edit\edl.json"` を実行します。
3. `vtc export-premiere-xml "C:\video\vtc-test\edit\edl.json" --out "C:\video\vtc-test\edit\test-fixed.xml"` を実行します。
4. Premiereの新規プロジェクトに `test-fixed.xml` を読み込みます。ステレオ素材がV1＋A1（L/Rステレオ）の形で配置されるか確認します。
5. カット数、映像と音声のリンク、全接続点のgap/overlap、左右の音声、冒頭と終盤の音ズレを確認します。
6. 最終クリップの最後のフレームまでコマ送りし、黒い斜線が出ないことを確認します。元の25カットのin/outを使った再現テストでは最後のクリップは47fです。無音検出の設定を変えた場合はカット数や長さも変わります。

同じFPSでは素材のin/outのフレーム数から配置長を決めるため、各クリップで `end-start == out-in` になります。FPSが異なる場合は素材フレーム長を有理数で換算します。モノラルとステレオが混在する場合は別のトラック群になります。

技術仕様は [英語の仕様説明](premiere-xml.md)、変更内容は [PR #1](https://github.com/polaris-frame/video-timeline-copilot/pull/1)を参照してください。
