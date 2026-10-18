# M0 · 可行性 Spike 报告（自动生成）

- 执行时间：2026-10-18T12:27:10.376Z
- 模式：safe-mode（禁用 GPU）
- Electron：`F:\Deepseek_harness\blockbench\vendor\blockbench\node_modules\electron\dist\electron.exe`
- 结论：**Go**（exit=0）
- selftest.ok：true；show/hide 后仍可渲染：true

## 渲染校验

| view | ok | size | alpha_ratio | luminance_variance |
|---|---|---|---|---|
| front | true | 768x768 | 0.195 | 2678.587 |
| back | true | 768x768 | 0.195 | 3366.922 |
| left | true | 768x768 | 0.135 | 1404.341 |
| right | true | 768x768 | 0.135 | 1303.482 |
| iso_fr | true | 768x768 | 0.200 | 2537.121 |

## 渲染器指标

```json
{
  "load_ms": 363,
  "render_views_ms": 108,
  "loop_50": {
    "count": 50,
    "p50_ms": 11,
    "p95_ms": 12,
    "max_ms": 12
  },
  "show_hide_ms": 597,
  "total_ms": 1841
}
```

## WebGL

```json
{
  "version": "WebGL 2.0 (OpenGL ES 3.0 Chromium)",
  "renderer": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)",
  "vendor": "Google Inc. (Google)",
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

日志：`F:\Deepseek_harness\blockbench\workspace\_m0-safe\logs\m0-electron.log`
产物：`F:\Deepseek_harness\blockbench\workspace\_m0-safe\artifacts\m0`
