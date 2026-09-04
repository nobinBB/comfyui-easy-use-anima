# ComfyUI Torn Edge Lines

添付画像のような、白い破れ紙風の上下2本線を手続き生成するノードです
追加ライブラリは不要です

## 導入

このノードは`comfyui-easy-use-anima`に同梱されています。リポジトリを更新してComfyUIを再起動します。

```text
C:\ComfyUI_windows_portable\ComfyUI\custom_nodes\comfyui-easy-use-anima
```

## ノード

`Torn Edge Lines / 破れ線ランダム生成`

|項目|内容|
|---|---|
|width|完成画像の横幅|
|height|完成画像の高さ|
|top_y_percent|上線の中心位置 0〜100%|
|bottom_y_percent|下線の中心位置 0〜100%|
|top_thickness|上線の太さ px|
|bottom_thickness|下線の太さ px|
|roughness|破れ線の上下変動量 大きいほど波が大きい|
|seed|形状を決める値 Randomizeで毎回変更|

## 出力

- `line_image` 白線＋黒背景のIMAGE
- `line_mask` 白線部分だけのMASK

## 初期値

添付画像 1536×1024 の見た目を基準にしています

- width 1536
- height 1024
- top_y_percent 27
- bottom_y_percent 77
- top_thickness 34
- bottom_thickness 42
- roughness 90
