# easy-use-anima

Anima専用のモデル／CLIP／VAE Loader、EasyKSamplerラッパー、画像メタデータ保存ノード、動的な複数テキスト入力ノード、倍率指定VAE latentアップスケールを提供するComfyUI拡張です。

[English README](README.md) | 日本語


### 必要環境

- Animaへネイティブ対応した新しいComfyUI
- 任意: [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use)。未導入の場合はComfyUI標準サンプリングへ自動的に切り替わります。
- 任意: [ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control)。**PC: Schedule LoRAs Plus**を使う場合だけ必要です。
- Pythonパッケージ `piexif`
- Anima diffusion model、対応テキストエンコーダ、16チャンネルQwen Image VAE

モデルファイルは同梱せず、自動ダウンロードも行いません。

### インストール

1. ComfyUIをインストールまたは更新します。ComfyUI-Easy-Useは任意です。
2. このリポジトリを`ComfyUI/custom_nodes/easy-use-anima`へcloneまたはコピーします。
3. 未導入の場合は`piexif`をインストールします。

   ```bash
   pip install piexif
   ```

   Windows portable版:

   ```powershell
   python_embeded\python.exe -m pip install piexif
   ```

4. モデルを対応フォルダへ配置します。

   ```text
   ComfyUI/models/
   ├─ diffusion_models/your_anima_model.safetensors
   ├─ text_encoders/qwen_3_06b_base.safetensors
   └─ vae/qwen_image_vae.safetensors
   ```

5. ComfyUIを再起動します。

### ノード一覧

| ノード | カテゴリ | 用途 |
|---|---|---|
| **EasyLoader (Full) - Anima** | `EasyUse-Anima/Loaders` | Animaモデル、テキストエンコーダ、VAE、空latentを読み込み、Easy-Use互換pipeを作成します。 |
| **EasyKSampler (Full) - Anima** | `EasyUse-Anima/Sampler` | Easy-UseがあればFull sampler、なければComfyUI標準samplerを使用し、モデルとsampler情報を出力します。 |
| **Anima Prompt Saver** | `EasyUse-Anima` | A1111形式の生成パラメータとAnimaモデル情報を画像へ保存します。 |
| **Dynamic Text Hub** | `EasyUse-Anima/Text` | 1～20個の複数行textboxを動的に表示し、改行または任意delimiterで結合し、`{a|b|c}`の候補選択を自動適用します。 |
| **PC: Schedule LoRAs Plus** | `EasyUse-Anima/Text` | 2段の複数行textboxをまとめてPrompt ControlのLoRAスケジュールへ渡し、結合済みtextも出力します。 |
| **Latent Upscale with VAE (By)** | `EasyUse-Anima/Latent` | latentをVAE decodeし、倍率でリサイズして再encodeする処理を1ノードで行います。 |

### EasyLoader (Full) - Anima

次の3ファイルを独立して選択します。

- `model_name`: `models/diffusion_models`内のAnimaモデル
- `clip_name`: `models/text_encoders`内のAnima用Qwen3 0.6Bテキストエンコーダ
- `vae_name`: `models/vae`内の16チャンネルQwen Image VAE

| 出力 | 型 | 内容 |
|---|---|---|
| `pipe` | `PIPE_LINE` | Easy-Use互換パイプライン |
| `model` | `MODEL` | 読み込んだAnima diffusion model |
| `vae` | `VAE` | 読み込んだQwen Image VAE |
| `clip` | `CLIP` | 読み込んだAnimaテキストエンコーダ |
| `latent` | `LATENT` | 選択解像度とbatch sizeの空latent |
| `model_name` | COMBO | Anima Prompt Saverへ接続するモデル名 |
| `vae_name` | COMBO | Anima Prompt Saverへ接続するVAE名 |

解像度一覧はComfyUI-Easy-Useの`BASE_RESOLUTIONS`を読み込みます。取得できない場合は同一内容の31項目を使用します。

Animaとして認識されないmodel／CLIPはエラーで停止します。4チャンネルSD用VAEもサンプリング前に拒否します。Animaには16チャンネルQwen Image VAEが必要です。

モデルCOMBOの判定はフォルダ名・ファイル名に依存しません。Safetensorsのヘッダーだけを読み、Anima固有の構造キーを持つモデルを表示します。そのため、名前を変更したファイルや`diffusion_models`配下の任意のサブフォルダでも使用できます。Safetensors以外の形式と、ヘッダーから構造を判定できないファイルは表示しません。二重の安全対策として、実行時のモデル種別検証も残しています。

#### プロンプトconditioning

このLoaderにはpositive／negativeプロンプト入力欄と出力スロットがありません。`PIPE_LINE`内の`positive`／`negative`は`None`です。

`clip`を任意のAnima対応テキストエンコードノードへ接続し、その`CONDITIONING`出力を **EasyKSampler (Full) - Anima** のoptional `positive`／`negative`へ接続してください。

### EasyKSampler (Full) - Anima

ComfyUI-Easy-Useがある場合は、本家の **EasyKSampler (Full)** へ処理を委譲して本家の動作とoptional入力を維持します。Easy-Useがない場合は、ComfyUI標準の`common_ksampler`、VAE decode、Preview Image、Save Imageへ自動的に切り替わります。

次の3点を追加しています。

1. optional `model`で差し替えた実使用モデルを`pipe["model"]`と`model`出力へ反映します。本家では元pipeのモデルが出力へ残る場合があります。
2. `sampler_name`と`scheduler`をCOMBO型で出力し、**Anima Prompt Saver**へ接続できます。
3. `steps`と`cfg`を`seed`の直前に出力し、メタデータ用に直接接続できます。

COMBO一覧は標準`KSampler`から動的に取得するため、別の拡張機能が登録したsampler／schedulerも反映されます。

単独モードでは、主要なFull sampler入力、model／conditioning／latentのoverride、img2img用VAE encode、tiled VAE decode、Hide／Preview／Save出力を使用できます。XY Plot、Layer Diffusion、Easy-Use専用schedulerなどはComfyUI-Easy-Use導入時のみ利用できます。

### Dynamic Text Hub

ノード下部の矢印付き個数欄で、1～20個のテキスト入力欄を選択します。個数を変えると、複数行入力欄と対応する個別出力スロットが同時に増減します。

- `mode = line_by_line`: 使用中の入力を1欄ずつ改行して結合。`delimiter`は非表示になり使用しません
- `mode = join_with_delimiter`: 指定した`delimiter`を間に入れて横並びに結合
- 選択グループは自動適用：`{red hair|green eyes|black dress}`があると、実行ごとに候補から1つをランダム選択します。どちらのmodeでも動作し、同じ選択結果を`text_all`と個別の`text_n`へ反映します。`|`を含まない波括弧は変更しません
- `clean_whitespace`: 有効にすると、各入力の前後空白を削除し、連続する空白・タブ・改行を1個の半角スペースへ整理
- `text_all`: 選択したmodeで使用中の入力を結合した`STRING`
- `text_1`～`text_20`: 各入力欄の個別`STRING`出力。使用中のスロットだけを表示

空白整理は各個別出力にも適用されます。個数を減らしたときは、非表示になる出力の接続を自動的に解除します。再び増やすと、対応する空欄または入力済みの内容を復元します。

### PC: Schedule LoRAs Plus

[ComfyUI Prompt Control](https://github.com/asagi4/comfyui-prompt-control)の **PC: Schedule LoRAs** を2段textbox化したラッパーです。`model`と`clip`を接続し、`text_1`と`text_2`へプロンプト／LoRAスケジュールを書きます。空でない欄を改行で結合し、そのままPrompt Controlへ渡します。

スケジュール適用後の`model`、`clip`に加えて、結合済みの`text`を出力します。同じ文章をLoRAスケジュールとconditioningの両方へ使う場合は、`text`を対応するテキストエンコードノードへ接続してください。このノードだけはComfyUI Prompt Controlが必要ですが、未導入でもeasy-use-animaの他ノードは使用できます。

### Latent Upscale with VAE (By)

`LatentUpscaleWithVAE.json`で使用していた画像サイズ取得、幅・高さの倍率計算、`LatentUpscaleWithVAE`を1ノードへまとめたものです。

1. 元の`LATENT`と、そのlatentに使用するVAEを接続します。
2. `scale_by`へ倍率（例: `1.25`）を指定します。
3. `lanczos`または`bislerp`を選択します。初期値の`lanczos`は参照ワークフローと同じです。
4. `bislerp`時は`bislerp_ratio`を`0.00～1.00`、`0.01`刻みで調整します。`0.00`はLanczosのみ、`1.00`はbislerpのみ、中間値は両方の結果を混合します。Lanczos時はこの入力欄を非表示にします。

互換性目的の古い補間方式は意図的に除外しています。内部でlatentをdecodeし、画像サイズを取得してComfyUI標準`common_upscale`で拡大し、VAEで`LATENT`へ再encodeします。画像サイズ入力、Mathノード、RES4LYF、ComfyUI-Easy-Useは不要です。

### Anima Prompt Saver

[ComfyUI Prompt Reader Node](https://github.com/receyuki/comfyui-prompt-reader-node)の`SD Prompt Saver`をAnima向けに変更したノードです。

- `checkpoints`ではなく`diffusion_models`からモデル名とハッシュを取得
- 標準`KSampler`と同じsampler／scheduler一覧を使用
- A1111形式の`parameters`を保存
- PNGへworkflow情報、JPEG／WebPへEXIFコメントを保存
- リソースハッシュと任意のメタデータtxtに対応
- `%date`、`%time`、`%seed`、`%steps`、`%cfg`、`%width`、`%height`、`%model`、`%sampler`、`%scheduler`、`%counter`などの変数に対応

Loaderの`model_name`／`vae_name`をSaverの同名入力へ接続します。Samplerの`image`、`steps`、`cfg`、`seed`、`sampler_name`、`scheduler`も接続します。保存したい場合は`width`、`height`、プロンプト文字列も設定または接続してください。

### 推奨ワークフロー

```text
EasyLoader (Full) - Anima
  ├─ pipe ────────────────────────────────> EasyKSampler (Full) - Anima: pipe
  ├─ clip ─> positive text encoder ───────> EasyKSampler (Full) - Anima: positive
  ├─ clip ─> negative text encoder ───────> EasyKSampler (Full) - Anima: negative
  ├─ model_name ──────────────────────────> Anima Prompt Saver: model_name
  └─ vae_name ────────────────────────────> Anima Prompt Saver: vae_name

EasyKSampler (Full) - Anima
  ├─ image ───────────────────────────────> Anima Prompt Saver: images
  ├─ steps ───────────────────────────────> Anima Prompt Saver: steps
  ├─ cfg ─────────────────────────────────> Anima Prompt Saver: cfg
  ├─ seed ────────────────────────────────> Anima Prompt Saver: seed
  ├─ sampler_name ────────────────────────> Anima Prompt Saver: sampler_name
  └─ scheduler ───────────────────────────> Anima Prompt Saver: scheduler
```

### 元ノードとの違い

#### EasyLoader (Full)との違い

- SD用`checkpoints`ではなく`diffusion_models`からモデルを読み込み
- Anima用CLIPを`text_encoders`から、VAEを`vae`から個別選択
- `CheckpointLoader`、`clip_override`、`clip_skip`、A1111プロンプト重み解釈を不使用
- LoRA stack入力とLoader内蔵LoRA読み込みを不使用
- positive／negativeプロンプト欄とconditioning出力を不使用
- `model_name`／`vae_name` COMBO出力を追加
- 非Anima構成と非互換SD VAEを実行前に拒否

#### EasyKSampler (Full)との違い

- model override使用時に正しいモデルを出力pipeへ反映
- `steps`／`cfg`を`seed`の直前に出力
- `sampler_name`／`scheduler` COMBO出力を追加

#### SD Prompt Saverとの違い

- モデル一覧とハッシュに`diffusion_models`を使用
- ノード名を **Anima Prompt Saver**へ変更
- Anima／Easy-Useワークフロー向けに同梱
- A1111形式メタデータ、画像形式、ファイル名変数、workflow埋め込み、リソースハッシュは維持

### 旧easy-use-animaからの更新

旧ウィジェット位置の誤適用を防ぐため、Loaderの内部IDは`easy animaLoaderV2`です。

更新後はComfyUIを再起動し、保存済みワークフローの旧Loaderを削除して **EasyLoader (Full) - Anima** を追加し直してください。conditioningも外部テキストエンコードノード経由で再接続します。

バージョン0.7.0ではSamplerの`seed`出力より前に`steps`と`cfg`を追加しています。古い出力番号が残らないように **EasyKSampler (Full) - Anima** も削除して追加し直し、`steps`、`cfg`、`seed`、`sampler_name`、`scheduler`を再接続してください。

### クレジットとライセンス

本プロジェクト全体は **GPL-3.0-only** で配布します。

- [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use) — GPL-3.0。Loader／pipe設計とFull sampler連携のベースです。
- [ComfyUI Prompt Reader Node](https://github.com/receyuki/comfyui-prompt-reader-node) — MIT、Copyright © 2023 Rhys Yang。Anima Prompt Saverは同プロジェクトの`SD Prompt Saver`をベースにしています。

MIT由来部分は著作権表示とライセンス表示を保持したうえでGPLプロジェクトへ組み込んでいます。[LICENSE](LICENSE)と[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を確認してください。

モデルファイルには本リポジトリのライセンスは適用されません。使用・再配布前に各モデルのライセンスを確認してください。本拡張は独立したコミュニティプロジェクトであり、参照元の公式拡張ではありません。
