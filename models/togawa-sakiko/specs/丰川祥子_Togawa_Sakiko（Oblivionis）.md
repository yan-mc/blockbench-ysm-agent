# 建模规格：丰川祥子 / Togawa Sakiko（Oblivionis）
> 来源：明日方舟 × BanG Dream! Ave Mujica 联动 6★领主近卫；皮肤「旋律的主人 / Master of Melodia」

- 方块总数 **240**（语料中位 306）
- 头部区域占比 **49.6%**（语料中位 33.2%）
- 贴图 **512px**

## 配色
| 色号 | 颜色 | 用途 |
|---|---|---|
| hair_light | `#cfd8ee` | 头发亮部 |
| hair_mid | `#b3c2e2` | 头发中间调 |
| hair_shadow | `#8fa0c8` | 头发暗部 |
| hair_deep | `#6f7fa8` | 头发深暗/内层 |
| skin | `#f6e7e7` | 皮肤 |
| skin_shadow | `#e4c9d1` | 皮肤阴影 |
| dress_black | `#24212a` | 演出服黑主体 |
| dress_dark | `#17151c` | 演出服最深 |
| dress_fold | `#332f3a` | 黑布褶/亮边 |
| frill_white | `#eef2fa` | 荷叶边/衬裙亮部 |
| frill_shadow | `#c9d4e6` | 荷叶边阴影 |
| silver | `#dfe4ee` | 银饰边/扣 |
| silver_dark | `#a9b3c6` | 银饰暗部 |
| horn_light | `#5c5c68` | 角脊棱亮部 |
| horn_mid | `#3f3f4a` | 角主体 |
| horn_dark | `#2a2a32` | 角暗部/根部 |
| eye_amber | `#e2b04a` | 琥珀金虹膜 |
| eye_amber_dark | `#8f6a1e` | 虹膜暗圈 |
| pupil_dark | `#2a1d0c` | 瞳孔/睫毛 |
| white | `#ffffff` | 高光/眼白 |
| gem_blue | `#69b4e6` | 蓝宝石发饰/胸针 |
| gem_blue_dark | `#3d7fb8` | 蓝宝石暗部 |
| tight_black | `#211e27` | 黑丝袜 |
| boot_black | `#1b1920` | 短靴黑皮 |
| boot_panel | `#8ba0bb` | 靴筒蓝灰面板 |
| lace_silver | `#cfd6e2` | 靴带/蕾丝银线 |

## 部位与构建顺序
| 顺序 | 部位 | 骨骼 | 父级 | 方块 | 区域 | 形状 | 参考图 |
|---|---|---|---|---|---|---|---|
| 1 | torso | UpperBody | UpBody | 24 | torso | 黑银演出服上身：高领、肩披鼓袖、胸口浅蓝灰荷叶边、银链胸针、束腰 | #0 #1 #3 |
| 2 | chest | Breast | UpperBody | 4 | torso | 胸部起伏（被服装覆盖） | #3 |
| 3 | legs | LeftLeg | DownBody | 6 | leg | 黑丝袜（星光纹理降级到贴图） | #4 |
| 4 | boots | LeftFoot | DownBody | 8 | leg | 黑银系带高跟短靴、蓝灰靴筒面板 | #4 |
| 5 | arms | LeftArm | UpBody | 12 | arm | 黑色鼓袖+肩披蕾丝层 | #3 |
| 6 | forearms | LeftForeArm | UpBody | 6 | arm | 黑蕾丝长手套+袖口 | #3 |
| 7 | head | Head | AllHead | 14 | head | 7宽头骨+下颌收窄+耳朵+颊侧斜块 | #1 #2 |
| 8 | eyes | Eyelid | AllHead | 14 | head | 纯色方块叠层眼：眼睑板/眼白/虹膜/瞳孔/高光/眉毛 | #2 |
| 9 | accessory | AllHead | UpBody | 9 | head | 蓝水晶发饰、金饰、蓝宝石胸针、浅蓝腰结 | #0 #1 #3 |
| 10 | hair_main | Hair | Head | 26 | hair | 头顶+后发体积，银蓝灰长卷发 | #0 #1 |
| 11 | hair_bangs | front_h1 | Head | 14 | hair | 刘海8-12撮压眉、侧发贴颊 | #2 |
| 12 | hair_side | corner_h1 | Head | 12 | hair | 鬓发+侧发内收吃掉脸方角 | #0 #1 |
| 13 | hair_long | hl_m | Head | 20 | hair | 后长发4-6束多段（等粗长条+每块微转） | #0 |
| 14 | hair_long_side | hl_side | Head | 10 | hair | 两侧长发束/低双马尾（前列肩前） | #0 #2 |
| 15 | skirt | Skirt | DownBody | 12 | skirt | 黑色多层荷叶短裙+白蓝衬裙边 | #0 #4 |
| 16 | skirt_front | FrontSkirt | DownBody | 16 | skirt | 前后左右裙片+背后大黑蝴蝶结+长拖尾 | #0 #4 |
| 17 | ribbon | Ribbon | Head | 8 | accessory | 黑蝴蝶结发饰+低双马尾系带 | #1 #2 |
| 18 | collar | Collar | Root | 5 | other | 黑色高领+蕾丝边 | #1 #3 |
| 19 | horns | Horn_R_01 | Root | 20 | other | 双大角：每侧3段弯曲（向上→外张→前勾下弯），深炭灰带脊棱 | #0 #1 |

## 参考图判读
| # | 角度 | 类型 | 备注 |
|---|---|---|---|
| 0 | three_quarter | fullbody | 官方皮肤「旋律的主人」立绘 2176²（sakiko_skin1.png）：坐姿3/4正面，主参考（发色/瞳色/双角/黑银服装/黑丝/短靴） |
| 1 | front | screenshot | 头部+双大角裁切 crop_head.png（来自#0）：角形弯曲方向、发饰、领口 |
| 2 | front | screenshot | 面部放大 crop_face.png（来自#0）：琥珀金瞳、刘海分束、低双马尾黑蝴蝶结 |
| 3 | three_quarter | screenshot | 上身服装 crop_horn_hair.png（来自#0）：黑高领/鼓袖/浅蓝灰荷叶边胸饰/蓝宝石胸针/黑蕾丝手套 |
| 4 | side | screenshot | 裙/腿/靴裁切 crop_body.png+crop_legs.png（来自#0）：多层黑裙/白蓝衬裙边/黑丝/黑银系带高跟短靴 |
| 5 | front | fullbody | E2 立绘 sakiko_e2.png（非本皮肤，仅站姿比例参考） |
| 6 | front | fullbody | E0 校服立绘 sakiko_e0.png（非本皮肤，仅7头身比例参考） |

## 信息缺口（必须告知用户）
- 缺背面参考：官方皮肤立绘为坐姿3/4正面，无背面/正侧图；背面发型、裙摆与拖尾按对称+长发推断
- 缺直立侧面参考：角在侧视的弯曲平面、身体厚度按3/4视角推断
- 坐姿遮挡下半身：腿长/靴高按站姿 E2/E0 与 YSM 模板比例推断
- 皮肤立绘中的古典钢琴/留声机/螺旋阶梯/高塔为背景元素，明确不建模
- 角的具体脊棱数量、瞳孔细节、布料蕾丝纹样在方块尺度下做简化/贴图降级

## 备注
锁定 skin1=「旋律的主人」黑银演出服（E0=校服、E2=红黑舞台服均非目标皮肤）。骨架沿用 YSM 模板并新增角骨链；保留模板 303 个动画以避免动画层返工。
