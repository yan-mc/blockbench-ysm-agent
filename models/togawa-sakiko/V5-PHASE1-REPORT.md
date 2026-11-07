# v5 Phase 1 完成报告（服装 + 下肢）

> 角色：丰川祥子「旋律的主人」 · 参考：T3 turnaround / breakdown / t3-clothing-detail / 官方 ref_000
> 工程：`pack`（main.json revision 19） · 检查点：`checkpoints/r0016.bbmodel`(v5-phase1)、`r0019.bbmodel`(v5-phase1-final)

## 实测数字（真相源 = bb_validate / main.json）

| 项 | 值 |
|---|---|
| 骨骼（main） | **70**（68 → +2：`Cape`、`CapeLow`，挂 DownBody） |
| 方块（main） | **791**（原 511；删除旧长裙 59 + 旧腿/脚/手臂 60，新增 ~400） |
| validate | **0 error**；warn 3 条：`TEXTURE_SIZE`×2（512 贴图，可接受）+ `ViewLocator`（可选定位组） |
| main.json | revision 19，252 KB，已 save |
| 未导出 / 未改动画 / 未 git | ✅ |

## 逐项完成

1. **贴图污染修复**：`artifacts/v4/texture-backup/default.png` 回灌 → 洋红像素全库 **0**（PIL 实测），眼睛恢复金色。新增 swatch 独立行 y=224（22 格 16×16）+ 32×32 星空格 (320,256)，不与发色/眼睛行混。
2. **旧长裙清除**：BackSkirt 29 / FrontSkirt 7 / LeftSkirt 2 / RightSkirt 2 / Skirt 19 = **59 块删除**，骨骼全保留。
3. **三层短裙**：waist 3.2 → 黑上层 4.02 → 黑下层 4.58 → 黑荷叶 4.86（18 片锯齿 ±0.6）→ 浅蓝 4.74 → 蓝紫 4.98 → 蓝荷叶 5.12（18 片）。前片抬高到 y21.0（黑白高-low），前中挖 45° 开口露出大腿/吊袜带；后腰 5 片 bustle。层数按方位分派给 Skirt/FrontSkirt/BackSkirt/LeftSkirt/RightSkirt（保留动画引用）。
4. **腿**：每腿 6 环 × 8 板（裸露大腿/袜口宽边/大腿袜/膝/小腿/踝），交替 k1/k1l 做罗纹；袜口 16.6–18.15、吊袜带 18.15–19.75 两根 + 银十字扣 ×4；左腿另加 5 节银链 + 3 颗蓝坠（T3 D3）。
5. **靴**：蓝灰筒（bt1/bt2 侧板、黑后跟）+ 3 组 X 蓝鞋带 + 4 银气眼 + 黑鞋头 + 厚黑底（平台 2.0）+ 独立后跟块，正/侧/背/鞋底可辨（isolate 已核）。
6. **上装**：保留 corset 主体 40 块；新增两侧蓝交叉绑带各 2 组 X + 竖撑、off-shoulder 椭圆蕾丝领圈 12 片、胸口蓝蝴蝶结（2 环 + 结）；删除旧洋红/浅蓝腰带块 1 块，重着色 6 根亮白骨线。
7. **袖/手**：泡泡袖 3.7×2.6 + 45° 星形块 + 上下蕾丝环（8/6 片）；前臂裸露肤色；腕部黑手套 + 蕾丝袖口暗台阶（k2→k3）。
8. **披风**：`Cape`/`CapeLow` 各 6 片半透明星空片（alpha≈0.82 + 稀疏星点），腰后挂、下摆到小腿，侧/背可见。

## 诚实偏差

- **手套是腕套 + 蕾丝袖口，前臂裸露**：T3 [C1/C2] 与官方图都是"泡泡袖→裸前臂→腕部黑手套"，任务书里写的"前臂长手套"与参考冲突，按参考做。
- **披风挂点在腰后**（T3 breakdown B4 是腰部系带），不是肩后；半透明在透明背景下会偏灰，已调成 alpha 0.82 的深海军蓝。
- **corset 蓝交叉绑带在两侧**（T3 侧视可见），正面是蝴蝶结 + 门襟；正面正视只能看到腰侧一点蓝。
- **前中 45° 开口**导致死正面看蓝层像"两片侧裙"；T3 也是前开，但我的开口略大。
- 浅蓝层偏白（pw1/pw2/l1 组合），比 T3 的蓝紫稍淡。
- 头发/角/脸/动画未动（Phase 2 范围）。

## 渲染产物（2400²，ssaa）

- `artifacts/v5/phase1-front-2400.png` / `-left-` / `-back-` / `-iso-`
- `artifacts/v5/phase1-legs-front-1600.png` / `-legs-left-1600.png`（腿+靴特写）
- 原始：`artifacts/renders/r0019/`

## 预算

- 显式渲染 **9** 次（另 ~10 次 open 自动预览）；`bb_apply_model_patch` **0** 次
- 几何走脚本：`tools/v5/{common,build_skirt,build_body}.py`，共 8 轮 rebuild（幂等：`v5*` 前缀自动清理 + 重开工程）
- checkpoint 2 次、validate 2 次、save 2 次
