# M0 · 可行性 Spike 报告（自动生成）

- 执行时间：2026-10-18T15:02:26.534Z
- 模式：正常 GPU
- Electron：`F:\Deepseek_harness\blockbench\vendor\blockbench\node_modules\electron\dist\electron.exe`
- 结论：**Go**（exit=0）
- selftest.ok：true；show/hide 后仍可渲染：true

## 渲染校验

| view | ok | size | alpha_ratio | luminance_variance |
|---|---|---|---|---|
| front | true | 768x768 | 0.195 | 2677.699 |
| back | true | 768x768 | 0.195 | 3363.825 |
| left | true | 768x768 | 0.135 | 1405.639 |
| right | true | 768x768 | 0.135 | 1302.02 |
| iso_fr | true | 768x768 | 0.200 | 2543.069 |

## 渲染器指标

```json
{
  "load_ms": 396,
  "render_views_ms": 48,
  "loop_50": {
    "count": 50,
    "p50_ms": 5,
    "p95_ms": 5,
    "max_ms": 6
  },
  "show_hide_ms": 516,
  "total_ms": 1385
}
```

## WebGL

```json
{
  "version": "WebGL 2.0 (OpenGL ES 3.0 Chromium)",
  "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 Laptop GPU (0x000027A0) Direct3D11 vs_5_0 ps_5_0, D3D11)",
  "vendor": "Google Inc. (NVIDIA)",
  "antialias": true
}
```

## Project

```json
{
  "bones": 64,
  "cubes": 172,
  "textures": 1,
  "texture_size": [
    128,
    128
  ],
  "animations": 0,
  "bounds": {
    "center": [
      0,
      21.649999618530273,
      1.4355185966939739
    ],
    "size": [
      19.035741180302054,
      43.29999923706055,
      13.271037193387947
    ]
  }
}
```

日志：`F:\Deepseek_harness\blockbench\workspace\_m0\logs\m0-electron.log`
产物：`F:\Deepseek_harness\blockbench\workspace\_m0\artifacts\m0`
