# DeepSeek 鲸鱼娘 · 问题与 Bug 记录

本轮以模型制作为主；下面按时间记录遇到/修复/待修的问题，便于后续回归。

## A. 工程侧（本轮之前已修复，留档）

| # | 现象 | 原因 | 处理 |
|---|---|---|---|
| A1 | 反复热重载插件后会出现多组 BAE Electron 进程 | 旧插件实例的 restart timer / 失败激活未清理 | 重启 dsh 或重载到新 workspace；已记录待做“单实例/孤儿进程清理” |
| A2 | 渲染第二帧偶尔 `changed_any=true` 但视觉一致 | GPU 抗锯齿/PNG 编码抖动，sha256 逐字节比较误报 | 改为 64×64 像素差分（阈值 0.5%），已修 |
| A3 | restore 后 `project.save` 报 `no project open` | 关闭旧 tab 排队的 `selectNoProject` 覆盖了恢复项目 | 延迟 50ms 重选 + ensureProject 自动恢复，已修 |
| A4 | `bb_render_views` 传 `focus` 时插件激活失败 | 参数对象缺 `additionalProperties` | 补 schema，已修 |
| A5 | `bb_texture_pbr list` 把基础 color 贴图也列出来 | 过滤条件把 `pbr_channel='color'` 当真 PBR | 过滤 color，已修 |
| A6 | Host 端 `nativeImage` 不可用，512 缩略图失效 | dsh Host 无 Electron API | 改由 renderer 生成 `_attach512.png`，已修 |
| A7 | 游戏内验证环境搭建：PCL 启动脚本 Java 路径过期、JavaWrapper 缺失、重复 width 参数 | 本地环境差异 | 改装 Java 17.0.19 + ATM9 JavaWrapper + 清理重复参数，已修（脚本在 `game-test/`） |
| A8 | 旧 workspace 308MB 杂乱 | 历史 demo/证据混在 default | 归档到 `workspace/_archive/`，新工程独立到 `projects/deepseek-fish` |

## B. 本轮模型制作

（随建模过程追加：现象 / 复现 / 根因 / 处理 / 状态）

| # | 现象 | 根因 | 处理 | 状态 |
|---|---|---|---|---|
| B1 | 用 `bb_restore` 回滚检查点后，贴图回到原始粉/红色，新几何变成透明/细线 | 检查点 `.bbmodel` 只含模型结构；恢复后贴图从 pack 磁盘读取，未保存的 texture 编辑丢失 | 先 `bb_save_project` 再 checkpoint；本轮已重放 recolor + 调色板 UV 区域。后续应让 checkpoint 包含贴图快照 | 已规避，工具待修 |
| B2 | 重导整张贴图后，新几何的 UV 区又变回原图内容（透明/杂色） | `bb_texture_import_png` 整图覆盖会冲掉手工分配的调色板区域 | 调色板区域改为重导后立即重绘；脚本化 `recolor_texture.py` + texture_patch | 已知，按顺序执行 |
| B3 | 模板脸部 UV 只有 7×7，直接画大眼会糊 | 默认 YSM 模型脸很小，靠 3D 五官层 | 用白色眼白/蓝色虹膜/高光/睫毛小方块分层叠在脸前 | 已实现 |
| B4 | `add_cube` 自动 UV 会占用已有纹理区 | 新 cube 默认 autoUV，没有空 UV | 每次 add 后用 `set_uv` 指向保留的空闲 UV 色块 | 已规避 |
| B5 | `set_uv` 的 uv_size 由 cube 尺寸推导，不能把 6×6 眼睛设计图拉伸到 1.8×1.8 的脸 | 工具不支持自定义 uv_size | 改用多层纯色小方块；记录为工具增强项 | 已规避 |
| B6 | `update_bone` 传 `bone_id` 报 `bone not found: undefined` | handler 只读 `op.bone ?? op.id`，与 `update_cube` 的 `cube_id` 命名不一致 | 改传 `id`；建议统一 API 别名 | 已规避，API 待统一 |
| B7 | 想给鲸鳍/尾巴加圆角/倾斜，`update_cube` 支持 rotation/pivot 但 `add_cube` 没有 inflate/rotation | 工具参数缺失 | 用 pivot+rotation 拼角度；inflate 未支持 | 待增强 |
| B8 | 删除 10 个可选 locator 后，`validate` 报 11 条 `YSM_LOCATOR_OPTIONAL_MISSING` warning | 为腾出骨骼槽删了可选定位器 | 不影响加载/动画；记录，后续可选恢复 ViewLocator 等 | 接受 |
| B9 | 尾巴用轴对齐方块很难做出鲸尾曲线，前几版像“翅膀/横杠” | 只有 cubes、且 add 不支持旋转 | 用 pivot+rotation 做 V 形双叶，转身旋转 30° 露到身侧；继续手工调 | 进行中 |
| B10 | 游戏内加载 | 独立 `game-test` 环境 | 复制 pack 到 `config/yes_steve_model/custom/deepseek_fish`，`ingame.ps1 -PackName deepseek_fish`；日志确认 `[YSM] Set 'deepseek_fish' models` | 已通过 |
| B11 | `ingame.ps1` 在 `powershell` 5.1 下启动游戏：Java 报 `InvalidPathException ... jarF:\...jar`，classpath 分号丢失；在 `pwsh` 7 下正常 | Windows PowerShell 5.1 处理 `Start-Process -ArgumentList` 的引号/分号行为与 pwsh 不同 | 统一用 `pwsh` 运行 `ingame.ps1`；记录到 SETUP | 已规避 |
| B12 | 游戏截图只拍到窗口一部分，后面是 DSH 界面 | 游戏窗口被 DSH 窗口遮挡，`SetForegroundWindow` 无效 | 截图前 `MoveWindow(0,0,1280,720)` + `SetWindowPos(HWND_TOPMOST)` | 已修 |
| B13 | 游戏截图分辨率 320×240 太小 | 脚本默认 resolution 320×240 | 改为 1280×720 后重跑 | 已修 |
