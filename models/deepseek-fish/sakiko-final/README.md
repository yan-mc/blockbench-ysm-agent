# 丰川祥子 · YSM 皮肤模型（sakiko-final）

> 由 AI 通过 `bb_*` 工具在**无头 Blockbench** 中从零迭代生成，全程用渲染图自我校验。
> 生成环境：DSH × Blockbench Agent v0.4.0 + 视口实时反馈 v1.2（眼睛 A+B）。

---

## 1. 成品

| 项 | 值 |
|---|---|
| 交付包 | [`sakiko-final-release.zip`](../sakiko-final-release.zip)（≈477 KB，38 文件） |
| 包名 | `sakiko` |
| 骨骼 / 方块 | **56 bones / 196 cubes**（YSM 上限 64/∞） |
| 贴图 | 128×128 `/textures/default.png` |
| 动画 | 303 条（沿用 YSM 默认动作库） |
| 校验 | `bb_validate` **0 error**（11 个可选定位组缺失为有意取舍，见 §5） |
| 渲染 | 8 视角 + 特写，见 `screenshots/` |

## 2. 外观特征

| 部位 | 实现 |
|---|---|
| 发型 | 深蓝黑长直发，多层次发丝（24 个 hair cube + 长发片） |
| **眼睛** | **紫红虹膜 + 白眼球 + 深色瞳孔 + 高光**，分层 cube 叠加 |
| 面部 | 肤色 + **腮红** + 细眉 |
| 发饰 | **红色蝴蝶结**（可经 YSM 配置 `v.red_bow_headdress` 开关） |
| 呆毛 | 头顶翘起呆毛（Ahoge） |
| 制服 | 藏青水手服外套 + **金色双排扣** + 黑色腰带 + 银色带扣 |
| 内衬 | 白色衬衫领 + 黑色 Y 形领结 + 白色袖口 |
| 下装 | 深色格纹短裙（及膝上方） |
| 腿部 | 白色过膝长袜 |
| 鞋 | 深棕色皮鞋 |

## 3. 构建方法（AI 工作流）

本模型由 AI 自主完成，**没有任何人工建模**。关键流程：

1. **以成品为底本**：从仓库内精修过的模板模型派生，继承其分层几何与贴图技法，
   再删除不属于该角色的特征（鲸鱼鳍/尾、饭碗、围裙）。
2. **按部位精确改色**：解析模型 JSON 建立"贴图像素 → 所属骨骼 + 世界高度"映射，
   再分区映射配色（头发压暗为蓝黑、外套藏青、领结改红、眼睛改紫红）。
3. **每步渲染自检**：每次改动后自动附一张 `front + iso` 拼图；
   用 `bb_orbit` 8 角度检查穿模；用 `bb_look({focus})` 做头部特写校对。
4. **迭代修正**：转台发现裙摆过短→加长主裙；特写发现眉毛过粗→柔化；
   背部发现浅灰→压低头发明度上限。

### 用到的 bb_* 能力

- `bb_apply_model_patch`（add/update/delete/命名方块与骨骼）
- `bb_texture_import_png`（整张贴图替换）+ `bb_texture_read`（像素级读色）
- `bb_look` / `bb_orbit` / `bb_render_views`（多角度与特写渲染）
- `bb_validate` / `bb_save_project` / `bb_export_ysm`

## 4. 截图

| 文件 | 内容 |
|---|---|
| `screenshots/_sheet_8views.png` | 8 视角总览（front/right/back/left + 4 iso） |
| `screenshots/closeup.png` | 头部特写（正面 + 斜侧） |
| `screenshots/front_640.png` 等 | 各视角原图 640×640 |

## 5. 已知取舍

- **11 个可选定位组（Locator）未添加**：加上会超出 YSM 的 64 骨骼上限
  （当前 56 + 11 = 67）。这些仅用于武器/背包等配件挂载，不影响角色本体显示。
  若需要挂载武器，可删减其他骨骼或另做配件模型。
- **贴图分辨率 128×128**：YSM 默认规格。眼部为 2×2 像素的极限像素画。
- **头顶呆毛两侧有 1.2 单位的装饰方块**，继承自底本头冠，保留作为发饰。
- 造型为**月之森制服风格**的二次元 Q 版比例（YSM 标准），非写实比例。

## 6. 安装

1. 解压 `sakiko-final-release.zip` 到
   `config/yes_steve_model/custom/` 下（保持 `sakiko/` 目录）
2. 游戏内 `/ysm model reload`
3. `/ysm model set @s sakiko`（或通过界面选择）

> 依赖：Yes Steve Model 模组（YSM 2.x，spec 2）。

## 7. 仓库内保留范围

为免与模板重复，本目录**只提交角色真正差异的部分**：

| 提交 | 说明 |
|---|---|
| `models/main.json` | 模型几何（56 骨 / 196 方块） |
| `models/arm.json` | 第一人称手臂 |
| `textures/default.png` | 128×128 主贴图 |
| `ysm.json` | YSM 元数据（名称 sakiko、默认贴图、GUI） |
| `screenshots/` | 8 视角 + 特写效果图 |
| `../sakiko-final-release.zip` | **完整可分发包**（含全部动画/控制器/子模型） |

`animations/`、`controller/`、`lang/`、`avatar/` 以及
`arrow/boat/minecart/fishing_bobber` 子模型与 [`../pack/`](../pack/) **逐字节相同**，
故不进仓库；需要完整工作副本时解压 release zip 即可。

## 8. 来源与许可

- 骨架/动画/贴图基础：本仓库内 YSM 默认模板（官方标注 CC 0）与精修测试模型。
- 角色「丰川祥子」版权归原作者；本模型为**技术验证用途的同人二次创作**，
  不用于商业分发。
- 生成脚本与渲染管线见本仓库 `packages/`、`docs/07-视口实时反馈方案-冻结.md`。
