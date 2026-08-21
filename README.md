# easy-use-anima

An Anima-focused extension for [ComfyUI](https://github.com/comfyanonymous/ComfyUI), built around the `PIPE_LINE` workflow of [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use).

It provides a separate Anima model/CLIP/VAE loader, an Anima-aware `EasyKSampler (Full)` wrapper, and an Anima version of `SD Prompt Saver`.

[English](#english) | [日本語版 README](README_JA.md)

---

## English

### Requirements

- A recent ComfyUI version with native Anima support
- Optional: [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use). When absent, the included sampler uses ComfyUI core sampling automatically.
- Python package `piexif`
- An Anima diffusion model, compatible text encoder, and 16-channel Qwen Image VAE

This extension does not include or download model files.

### Installation

1. Install or update ComfyUI. ComfyUI-Easy-Use is optional.
2. Clone or copy this repository to `ComfyUI/custom_nodes/easy-use-anima`.
3. Install `piexif` if it is not already available:

   ```bash
   pip install piexif
   ```

   Windows portable build:

   ```powershell
   python_embeded\python.exe -m pip install piexif
   ```

4. Place the model files in the corresponding folders:

   ```text
   ComfyUI/models/
   ├─ diffusion_models/your_anima_model.safetensors
   ├─ text_encoders/qwen_3_06b_base.safetensors
   └─ vae/qwen_image_vae.safetensors
   ```

5. Restart ComfyUI.

### Included nodes

| Node | Category | Purpose |
|---|---|---|
| **EasyLoader (Full) - Anima** | `EasyUse-Anima/Loaders` | Loads the Anima model, text encoder, VAE, and empty latent, then creates an Easy-Use-compatible pipe. |
| **EasyKSampler (Full) - Anima** | `EasyUse-Anima/Sampler` | Uses Easy-Use Full sampling when available or ComfyUI core sampling in standalone mode, while preserving model and sampler metadata. |
| **Anima Prompt Saver** | `EasyUse-Anima` | Saves images with A1111-style parameters and Anima model metadata. |

### EasyLoader (Full) - Anima

The loader selects three independent files:

- `model_name`: Anima model from `models/diffusion_models`
- `clip_name`: Anima Qwen3 0.6B text encoder from `models/text_encoders`
- `vae_name`: 16-channel Qwen Image VAE from `models/vae`

| Output | Type | Description |
|---|---|---|
| `pipe` | `PIPE_LINE` | Easy-Use-compatible pipeline. |
| `model` | `MODEL` | Loaded Anima diffusion model. |
| `vae` | `VAE` | Loaded Qwen Image VAE. |
| `clip` | `CLIP` | Loaded Anima text encoder. |
| `latent` | `LATENT` | Empty latent for the selected resolution and batch size. |
| `model_name` | COMBO | Selected diffusion model name for Anima Prompt Saver. |
| `vae_name` | COMBO | Selected VAE name for Anima Prompt Saver. |

The resolution list is read from the installed ComfyUI-Easy-Use `BASE_RESOLUTIONS`. A matching built-in 31-entry list is used if the upstream configuration cannot be found.

The loader rejects a model or text encoder that is not recognized as Anima. It also rejects a 4-channel SD VAE before sampling; Anima requires a 16-channel Qwen Image VAE.

The model COMBO does not depend on a folder or file name. It reads only the Safetensors header and shows files whose architecture keys match Anima, so renamed files and arbitrary subfolders under `diffusion_models` work normally. Non-Safetensors files and files whose architecture cannot be identified from the header are not shown. Runtime model-family validation remains enabled as a second safety check.

#### Prompt conditioning

This loader intentionally has no positive/negative prompt widgets and no positive/negative output sockets. Its `PIPE_LINE` contains `positive=None` and `negative=None`.

Connect `clip` to your preferred Anima-compatible text-encoding nodes, then connect their `CONDITIONING` outputs to the optional `positive` and `negative` inputs of **EasyKSampler (Full) - Anima**.

### EasyKSampler (Full) - Anima

When ComfyUI-Easy-Use is installed, sampling is delegated to its **EasyKSampler (Full)** to retain the upstream behavior and optional inputs. Without Easy-Use, this node automatically uses ComfyUI's core `common_ksampler`, VAE decoding, Preview Image, and Save Image implementations.

This wrapper adds two changes:

1. When optional `model` overrides the sampling model, the actual model is written to both `pipe["model"]` and the `model` output. The upstream node can otherwise leave the old model in the output pipe.
2. `sampler_name` and `scheduler` are exposed as COMBO outputs for **Anima Prompt Saver**.

These COMBO lists are resolved dynamically from ComfyUI's standard `KSampler`, including samplers and schedulers registered by other extensions.

Standalone mode supports the main full-sampler inputs, model/conditioning/latent overrides, image-to-image VAE encoding, tiled VAE decoding, and Hide/Preview/Save output modes. Easy-Use-specific features such as XY Plot, Layer Diffusion, and Easy-Use-only schedulers require ComfyUI-Easy-Use.

### Anima Prompt Saver

This is the Anima counterpart of `SD Prompt Saver` from [ComfyUI Prompt Reader Node](https://github.com/receyuki/comfyui-prompt-reader-node).

- Reads `model_name` from `models/diffusion_models`, not `models/checkpoints`
- Calculates the model hash from the selected diffusion model
- Uses the standard ComfyUI `KSampler` sampler/scheduler lists
- Saves A1111-style `parameters` metadata
- Embeds workflow metadata in PNG
- Writes EXIF comments to JPEG and WebP
- Supports resource hashes and an optional metadata text file
- Supports variables including `%date`, `%time`, `%seed`, `%steps`, `%cfg`, `%width`, `%height`, `%model`, `%sampler`, `%scheduler`, and `%counter`

Connect the loader's `model_name` and `vae_name` outputs to the matching saver inputs. Connect the sampler's `image`, `seed`, `sampler_name`, and `scheduler` outputs to the saver. Set or connect `steps`, `cfg`, `width`, `height`, and prompt text when those values should be included in metadata.

### Recommended workflow

```text
EasyLoader (Full) - Anima
  ├─ pipe ────────────────────────────────> EasyKSampler (Full) - Anima: pipe
  ├─ clip ─> positive text encoder ───────> EasyKSampler (Full) - Anima: positive
  ├─ clip ─> negative text encoder ───────> EasyKSampler (Full) - Anima: negative
  ├─ model_name ──────────────────────────> Anima Prompt Saver: model_name
  └─ vae_name ────────────────────────────> Anima Prompt Saver: vae_name

EasyKSampler (Full) - Anima
  ├─ image ───────────────────────────────> Anima Prompt Saver: images
  ├─ seed ────────────────────────────────> Anima Prompt Saver: seed
  ├─ sampler_name ────────────────────────> Anima Prompt Saver: sampler_name
  └─ scheduler ───────────────────────────> Anima Prompt Saver: scheduler
```

### Differences from the original nodes

#### Compared with EasyLoader (Full)

- Loads from `diffusion_models` instead of SD `checkpoints`
- Selects the Anima text encoder from `text_encoders` and the VAE separately
- Does not use `CheckpointLoader`, `clip_override`, `clip_skip`, or A1111 prompt-weight parsing
- Does not include a LoRA stack input or built-in LoRA loading
- Does not include positive/negative prompt widgets or conditioning outputs
- Adds `model_name` and `vae_name` COMBO outputs for metadata
- Rejects non-Anima model/CLIP combinations and incompatible SD VAEs before sampling

#### Compared with EasyKSampler (Full)

- Corrects the model stored in the output pipe when model override is used
- Adds standard-KSampler-compatible `sampler_name` and `scheduler` COMBO outputs

#### Compared with SD Prompt Saver

- Uses `diffusion_models` for the model list and hash
- Uses the name **Anima Prompt Saver**
- Is packaged for this Anima/Easy-Use workflow
- Retains A1111-style metadata, image formats, filename variables, workflow embedding, and resource hashes

### Updating from an older easy-use-anima build

The loader uses internal node ID `easy animaLoaderV2` so old widget positions are not applied to the new input layout.

After updating, restart ComfyUI, remove the old loader from saved workflows, add **EasyLoader (Full) - Anima** again, and reconnect conditioning through external text-encoding nodes.

### Credits and license

This project is distributed under **GPL-3.0-only**.

- [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use) — GPL-3.0. The loader/pipe design and full sampler integration are based on this project.
- [ComfyUI Prompt Reader Node](https://github.com/receyuki/comfyui-prompt-reader-node) — MIT, Copyright © 2023 Rhys Yang. Anima Prompt Saver is adapted from its `SD Prompt Saver` node.

MIT-licensed material may be combined into this GPL project while retaining its copyright and license notice. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Model files are not covered by this repository's license. Check each model's license before use or redistribution. This is an independent community extension and is not affiliated with the upstream projects.

---

## 日本語

### 必要環境

- Animaへネイティブ対応した新しいComfyUI
- 任意: [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use)。未導入の場合はComfyUI標準サンプリングへ自動的に切り替わります。
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

次の2点を追加しています。

1. optional `model`で差し替えた実使用モデルを`pipe["model"]`と`model`出力へ反映します。本家では元pipeのモデルが出力へ残る場合があります。
2. `sampler_name`と`scheduler`をCOMBO型で出力し、**Anima Prompt Saver**へ接続できます。

COMBO一覧は標準`KSampler`から動的に取得するため、別の拡張機能が登録したsampler／schedulerも反映されます。

単独モードでは、主要なFull sampler入力、model／conditioning／latentのoverride、img2img用VAE encode、tiled VAE decode、Hide／Preview／Save出力を使用できます。XY Plot、Layer Diffusion、Easy-Use専用schedulerなどはComfyUI-Easy-Use導入時のみ利用できます。

### Anima Prompt Saver

[ComfyUI Prompt Reader Node](https://github.com/receyuki/comfyui-prompt-reader-node)の`SD Prompt Saver`をAnima向けに変更したノードです。

- `checkpoints`ではなく`diffusion_models`からモデル名とハッシュを取得
- 標準`KSampler`と同じsampler／scheduler一覧を使用
- A1111形式の`parameters`を保存
- PNGへworkflow情報、JPEG／WebPへEXIFコメントを保存
- リソースハッシュと任意のメタデータtxtに対応
- `%date`、`%time`、`%seed`、`%steps`、`%cfg`、`%width`、`%height`、`%model`、`%sampler`、`%scheduler`、`%counter`などの変数に対応

Loaderの`model_name`／`vae_name`をSaverの同名入力へ接続します。Samplerの`image`、`seed`、`sampler_name`、`scheduler`も接続します。保存したい場合は`steps`、`cfg`、`width`、`height`、プロンプト文字列も設定または接続してください。

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
- `sampler_name`／`scheduler` COMBO出力を追加

#### SD Prompt Saverとの違い

- モデル一覧とハッシュに`diffusion_models`を使用
- ノード名を **Anima Prompt Saver**へ変更
- Anima／Easy-Useワークフロー向けに同梱
- A1111形式メタデータ、画像形式、ファイル名変数、workflow埋め込み、リソースハッシュは維持

### 旧easy-use-animaからの更新

旧ウィジェット位置の誤適用を防ぐため、Loaderの内部IDは`easy animaLoaderV2`です。

更新後はComfyUIを再起動し、保存済みワークフローの旧Loaderを削除して **EasyLoader (Full) - Anima** を追加し直してください。conditioningも外部テキストエンコードノード経由で再接続します。

### クレジットとライセンス

本プロジェクト全体は **GPL-3.0-only** で配布します。

- [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use) — GPL-3.0。Loader／pipe設計とFull sampler連携のベースです。
- [ComfyUI Prompt Reader Node](https://github.com/receyuki/comfyui-prompt-reader-node) — MIT、Copyright © 2023 Rhys Yang。Anima Prompt Saverは同プロジェクトの`SD Prompt Saver`をベースにしています。

MIT由来部分は著作権表示とライセンス表示を保持したうえでGPLプロジェクトへ組み込んでいます。[LICENSE](LICENSE)と[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を確認してください。

モデルファイルには本リポジトリのライセンスは適用されません。使用・再配布前に各モデルのライセンスを確認してください。本拡張は独立したコミュニティプロジェクトであり、参照元の公式拡張ではありません。
