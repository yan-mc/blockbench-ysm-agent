# DeepSeek 鲸鱼娘 · YSM 模型工程

> 目标：把 DeepSeek 的拟人形象「蓝色大肥鱼 / 鲸鱼娘（DeepSeek娘）」做成可进游戏加载的 YSM 模型，并用无头渲染迭代细节。
> 工程工作区：本目录（plugin workspace = `projects/deepseek-fish`）；原始素材与截图也都在本目录下。

## 角色设定（参考社区共识）

- 蓝色渐变长发（发根深海军蓝 → 发梢浅青蓝）、长呆毛
- 鲸类头鳍（耳位薄片状鳍，深蓝外壳/浅色内面）
- 蓝色大眼睛、Q 版、软萌
- 深蓝 + 白色女仆长裙/围裙，白色荷叶边头饰，胸前小领结
- 大型鲸尾（深蓝、宽尾鳍）
- 标志性道具：白米饭碗（“吃白饭的蓝色大肥鱼”）
- 性格梗：傲娇、摸鱼、干饭；不进入模型本身，仅作配色/道具灵感

## 调色板（初版）

| 用途 | Hex |
|---|---|
| 发根/深海军蓝 | `#1b2a52` |
| 头发中段 | `#2f5a9e` |
| 发梢/浅青蓝 | `#6fb7e8` |
| 鲸鳍外/尾外 | `#22335f` |
| 鲸鳍内/腹部浅色 | `#bcd8ee` |
| 裙装深蓝 | `#24345f` |
| 围裙/荷叶边 | `#f4f7fb` |
| 眼睛蓝 | `#3d7fd6` / 高光 `#dff2ff` |
| 皮肤 | 沿用模板肤色 |
| 米饭碗 | `#ffffff` + 蓝纹 |

## 模型规格

- YSM spec 2，main 64 bones 上限；纹理 128×128
- 在默认模板基础上：保留标准骨骼/动画，删除非必需 locator 腾出骨骼槽
- 新增骨骼：`WhaleFin_L/R`、`WhaleTail`、`Ahoge`、`Headdress`、`Apron`（按需）
- 贴图：重绘默认贴图（蓝白配色），新几何用透明 UV 区域平涂
- 渲染：front / iso_fr / back / closeup，至少 3 轮返工
- 导出：`pack/` 工作副本 + `release/deepseek-fish-<stamp>.zip`，最后安装到 `game-test` 做游戏内加载验证

## 目录

```
projects/deepseek-fish/
  README.md            本文件
  BUGS.md              本轮遇到的问题与 bug 记录
  reference/           参考图（社区 fan art，仅内部参考，不随发布）
  notes/               迭代记录/截图
  pack/                YSM 工作副本（由插件生成）
  screenshots/         关键渲染/游戏内截图
  release/             导出的 zip
```

## 参考来源

- 萌娘百科 DeepSeek娘、维基百科草稿（蓝色渐变发、呆毛、鲸鳍、蓝眼、鲸尾、深蓝白女仆装）
- 社区表情包与图标（参考图仅内部使用；角色形象版权归原作者/社区）

## 当前状态（v0.1）

- ✅ 已完成建模：61 bones / 222 cubes（64 骨骼上限内），蓝发 + 鲸耳鳍 + 大鲸尾 + 女仆头饰/围裙 + 分层大眼 + 围裙小鲸鱼 logo
- ✅ 已通过 `bb_validate`（仅 11 条 optional locator warning；required bones/texture/ysm.json/UV bounds 全 pass）
- ✅ 已导出 zip：`dist/deepseek-fish-v0.1.zip`（32 文件，482,901 bytes）
- ✅ 已在隔离 `game-test`（Forge 1.20.1-47.3.20 + YSM 2.6.5）加载：日志 `[YSM] Set 'deepseek_fish' models for player 'AgentTester'`，无 YSM/模型报错
- 🖼 截图：`screenshots/render-*.png`（Blockbench 无头渲染）、`screenshots/ingame-*.png`（游戏内 1280×720）

## 已知不足 / 下一轮

1. 尾巴目前是“扁平 V 形尾叶 + yaw 30°”，从侧后方看仍偏薄；下一轮改为多段厚度/曲面拼接。
2. 鲸耳鳍是方块拼的，缺少软骨弧度；可加 2-3 个过渡 cube。
3. 头饰白荷叶边偏方块感；可用更小 cube 环 + 贴图花边。
4. 模板动画不含新骨骼（鲸鳍/尾/头饰），它们只跟随父骨骼；可加 idle 摆动骨骼动画。
5. 可选 locator 删了 10 个，换取骨骼槽；若后续要挂武器/背包/视角定位，需要恢复或改用其它空骨骼。
6. 游戏内截图里角色出现在屋顶/空中是当前测试世界位置，不是模型悬浮 bug。

问题记录见 [BUGS.md](./BUGS.md)，迭代过程见 [notes/iterations.md](./notes/iterations.md)。

