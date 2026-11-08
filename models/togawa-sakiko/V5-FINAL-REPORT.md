# v5 成品报告：按 T3 拆解图重建（2026-11-08）

> 角色：丰川祥子「旋律的主人」（明日方舟 × BanG Dream! Ave Mujica）
> 参考：T3（Nano Banana Pro / APIYI）生成的 turnaround + breakdown；官方立绘 `refs/丰川祥子/arknights-pick/ref_000.png`
> 工程：`pack`；最终 **71 骨 / 1100 块 / 2×512 贴图 / 303 动画**

## 1. 流程

1. **T3 参考**：用 5 张参考图（官方全身 + 头/上/下身局部裁切 + 官方 Q 版小人）经 APIYI 调用 `gemini-3-pro-image`，生成 2K turnaround / breakdown（各 $0.1415，约 40s）。
2. **Phase 1（服装/下肢）**：删除旧及踝长裙 59 块；重建三层短裙、corset + 蓝交叉绑带 + 胸口蝴蝶结、off-shoulder 泡泡袖 + 腕部手套、黑丝袜 + 左腿 garter/链、厚底平台短靴、半透明星空披风。
3. **Phase 2（头发/角/头部饰品）**：HairBack 55→150 块 5 层波浪；角 25→43 段/只加粗加棱环；黑蝴蝶结发带、额头金饰+蓝宝石、耳环、蕾丝 choker + 蓝钻金链。
4. **Phase 3/4（成品化精修）**：裙层花瓣/蓝荷叶、后发覆盖条、额头饰品缩小、耳环外移、角棱环高光、靴子细节。
5. **Phase 5/6（裁切错误修正）**：发现之前 T3 对照图裁切错误（见下）；用正确独立面板重查后：移除三视图中不存在的星空披风、后发加宽 33 块、背面蓝层改黑、后裙补 9 片钟形裙片（1100 块）。
6. **交付**：`bb_validate` 0 error → save → 四视图/特写 → `exports/v5-final2/` + zip 511,459 B。

## 2. 最终数字

| 项 | 值 |
|---|---|
| 骨骼 | **71**（68 + Cape / CapeLow / HairBow_R；原骨名全保留） |
| 方块 | **1100**（v4 534 → R5/R6 修正后 1100） |
| 动画 | **303**（未触碰） |
| 贴图 | 2 × 512²；洋红污染已从 v4 备份回灌清除，新增独立 swatch 行 |
| 校验 | `bb_validate` strict：**0 error**；3 warning（TEXTURE_SIZE×2 + ViewLocator 可选） |
| 导出 | `exports/v5-final2/pack/`（32 文件）+ `pack.zip` **511,459 B** + export-manifest（sha256） |

## 3. 产物

- 最终渲染：`artifacts/v5/final/final-{front,left,back,iso}-2400.png`、`final-head-front/left-1600.png`、`final-hairback-1600.png`、`final-skirt-1600.png`、`final-boots-1600.png`、`_contact-sheet.png`
- 展示图：`docs/assets/showcase/sakiko-final-4views.png`、`sakiko-t3-vs-v5.png`、`sakiko-detail-head.png`、`sakiko-t3-crop-proof.png`（裁切证明）
- 报告：`V5-PHASE1-REPORT.md`、`V5-R3-REPORT.md`、`V5-R4-REPORT.md`、本文件
- 重建脚本（可复现）：`tools/v5/`、`tools/v5r3/`、`tools/v5r4/`、`tools/final_crop.py`

## 4. 对照结论（T3 vs v5）

- 轮廓：短款三层裙 + 泡泡袖 + 腕部手套 + 厚底靴 + 星空披风 + 层叠长发 + 粗卷角，整体已从 v4 的"简版长裙"转到 T3 造型。
- 细节：corset 蓝绑带/胸口蝴蝶结、额头金饰+蓝宝石、耳环、choker、吊袜带银十字扣、靴子蓝灰面板/X 鞋带、披风星点均已落地。
- 仍不完美（诚实）：角仍偏块状、正面投影略像"钩形"；后发上半段仍偏 tile、顶视图有 0.36 旧发缝；星空披风按三视图移除（breakdown B4 是独立配件，若需要可单独再加）；背裙比 T3 钟形略小、侧裙比 T3 窄约 18%；裙花瓣是 45° 菱形块非曲面；耳环受侧发厚度只能挂发外略浮。

## 4b. 关于 T3 对照图裁切错误（诚实记录）

Lead 最初生成的 T3 对照表使用了错误的面板坐标：`front` 裁到了 `48..975`（包含 front + side），`side` 裁到 `975..1502`（包含 back + 头部细节），`back` 裁到 `1502..2046`（包含头部/服装细节）。**这是校对失误，没有先看图验证裁切结果。**

实际情况：
- **T3 原图本身始终完整、顺序正确**（front / side / back / head details / clothing details），每轮建模也同时提供了原图与单独的头部/服装细节裁切；
- 但错误的对照图会误导侧/背判断。用正确独立面板（front 20–570、side 650–1045、back 1045–1585、head 1585–2420、clothing 1585–2745，原图像素）重查后，确实发现并修正了真实偏差：移除三视图中不存在的星空披风、后发加宽、背面蓝层改黑、后裙补体积；
- 裁切证明见 `docs/assets/showcase/sakiko-t3-crop-proof.png`；对照图见 `sakiko-t3-vs-v5.png`。

**教训**：多视图参考板必须先按原图像素坐标裁成独立面板并逐张目检，才能交给下游；不能把"按比例估算的裁切"当成正确输入。

## 5. 后续可选

1. 角的"圆润化"：改用更多薄段+显式 roll，或把角做成 2–3 段大块曲线，进一步减方块感。
2. 后发顶部补 2 条覆盖条 + 顶视图发缝。
3. 披风侧视加宽/提高透明度，避免"薄边"。
4. 游戏内验证（YSM 加载）与动画抽查 `idle/walk/run`，确认新增 Cape/HairBow 骨不影响原动画。
