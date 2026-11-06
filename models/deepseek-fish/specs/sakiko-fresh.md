# 建模规格：丰川祥子
> 来源：BanG Dream! It's MyGO!!!!! / Ave Mujica（Ave Mujica 舞台名 Oblivionis）

- 方块总数 **252**（语料中位 306）
- 头部区域占比 **40.1%**（语料中位 33.2%）
- 贴图 **128px**

## 配色
| 色号 | 颜色 | 用途 |
|---|---|---|
| hair_light | `#DCE4F7` | 头发高光（受光面） |
| hair_base | `#B6C2E8` | 头发主色 |
| hair_shadow | `#8E9BD2` | 头发暗面/发缝 |
| hair_deep | `#6E7BB4` | 头发最深处/发梢 |
| skin | `#FBE6DC` | 脸/颈/耳 |
| skin_shadow | `#EFCBBE` | 下巴/颈部阴影 |
| skin_blush | `#F3B9B0` | 腮红 |
| eye_iris | `#D9A93F` | 虹膜主色（琥珀金） |
| eye_iris_light | `#F0D07A` | 虹膜内圈亮金 |
| eye_ring | `#6B4A1E` | 虹膜外圈深褐 |
| eye_lash | `#231A17` | 上眼睑/睫线 |
| eye_white | `#FBF7F2` | 眼白/高光 |
| top_crimson | `#8E1F2B` | 绯红上衣主色 |
| top_highlight | `#A83441` | 绯红上衣亮面 |
| top_shadow | `#5E1420` | 绯红上衣暗面 |
| corset_black | `#17171B` | 束腰皮质主色 |
| cloth_black | `#1E1E23` | 黑色布料 |
| cloth_black_hi | `#2C2C33` | 黑布亮面 |
| skirt_black | `#141418` | 裙主色 |
| petticoat_cream | `#E6DECC` | 米色衬裙荷叶边 |
| petticoat_shadow | `#C9BFA8` | 衬裙褶皱阴影 |
| lace_brown | `#8B6A46` | 束腰牛皮竖系带 |
| lace_brown_hi | `#B08A5E` | 系带亮面 |
| belt_brown | `#6B4A2B` | 腰带 |
| gold_trim | `#8A7038` | 裙摆深金织带 |
| gold_trim_hi | `#C2A75E` | 织带亮面/发带金条 |
| glove_lace | `#26262B` | 黑蕾丝手套 |
| tights | `#3A3A42` | 半透黑丝袜 |
| tights_hi | `#4E4E58` | 丝袜高光 |
| boot_black | `#141416` | 靴身 |
| boot_toe_tan | `#C6AE80` | 靴米色鞋头/鞋跟 |
| ribbon_black | `#121319` | 发带蝴蝶结 |
| gem_blue | `#4A6FA8` | 胸前蓝宝石 |

## 部位与构建顺序
| 顺序 | 部位 | 骨骼 | 父级 | 方块 | 区域 | 形状 | 参考图 |
|---|---|---|---|---|---|---|---|
| 1 | torso_top | UpperBody | UpBody | 14 | torso | 绯红色上衣，肩部泡泡袖，胸口 V 形开襟 | #1 |
| 2 | corset | Corset（新增，挂 UpperBody） | UpperBody | 14 | torso | 黑色束腰罩在绯红上衣外，正面一排牛皮竖系带（梯形排布），腰部棕色皮带 | #1 |
| 3 | breast | Breast | UpperBody | 6 | torso | 胸部体块，被束腰压住 | #1 |
| 4 | petticoat | Petticoat（新增，挂 DownBody） | UpperBody | 18 | torso | 米色荷叶边衬裙，从黑裙下缘露出，前侧露出最多 | #1 |
| 5 | legs | LeftLeg/LeftLowerLeg/RightLeg/RightLowerLeg | DownBody | 4 | leg | 半透黑丝袜包住整条腿 | #1 |
| 6 | boots | LeftFoot/RightFoot | DownBody | 12 | leg | 黑色系带短靴：靴筒+鞋身+米色鞋头+小鞋跟，正面交叉鞋带 | #1 |
| 7 | arms | LeftArm/RightArm/LeftForeArm/RightForeArm | UpBody | 16 | arm | 绯红长袖，肩头蓬起，袖口收窄 | #1 |
| 8 | gloves | LeftHand/RightHand（补方块） | UpBody | 8 | arm | 黑色蕾丝手套，手腕处翻边 | #1 |
| 9 | head | Head | AllHead | 1 | head | 7x7x7 头壳；前面板 UV 从 7x7 放大到 14x14 重绘脸（脸是识别度的关键） | #1 #9 |
| 10 | eyes | RightEyelid/RightEyesBase/RightPupil/LeftEyelid/LeftEyesBase/LeftPupil | AllHead | 6 | head | 四层结构 Eyelid→EyesBase→Pupil→高光；UV 放大到 3~6px 画琥珀金虹膜+深褐外圈+睫线 | #9 |
| 11 | eyebrows | RightEyebrow/LeftEyebrow | AllHead | 4 | head | 细长浅灰蓝眉，略微上挑 | #9 |
| 12 | neck_collar | AllHead/Collar | AllHead | 8 | head | 黑色荷叶立领+黑色缎带蝴蝶结+蓝宝石胸针 | #1 |
| 13 | hair_back | Hair | Head | 24 | hair | 后发主发团，贴头壳包裹后脑 | #1 #14 |
| 14 | hair_bangs | front_h1 | Head | 13 | hair | 直刘海，中分偏额前，发缝清晰 | #1 #9 |
| 15 | hair_side | corner_h1 | Head | 16 | hair | 两鬓侧发，沿脸侧垂到锁骨 | #1 #9 |
| 16 | hair_long | hl_side/hl_m | Head | 29 | hair | 及腰长直发，前侧与后中各一束 | #1 #2 |
| 17 | skirt | Skirt/LeftSkirt/RightSkirt/FrontSkirt/BackSkirt | DownBody | 26 | skirt | 黑色多层不对称裙，前短后长（后有拖尾），裙面分层错落 | #1 |
| 18 | skirt_trim | Skirt | DownBody | 10 | skirt | 黑裙上缘一圈深金织带（参考图在胯部有明显金色饰带） | #1 |
| 19 | ribbon | Ribbon + RightRibbon（新增） | Head | 13 | accessory | 双侧黑金条纹发带蝴蝶结（模板只有左侧红蝴蝶结，改成对称黑金） | #9 |
| 20 | twintail | LeftTwinTail/RightTwinTail（新增） | Root | 10 | other | 耳侧低位双马尾，独立骨骼便于摆动 | #1 #9 #14 |

## 参考图判读
| # | 角度 | 类型 | 备注 |
|---|---|---|---|
| 0 | three_quarter | fanart | 蓝白发+花束，同人图；只用来交叉确认发色偏冷蓝，不作结构依据 |
| 1 | front | fullbody | ★主参考：白底全身立绘，Ave Mujica 舞台装。发型/服装分层/配色/靴子全部取自这张。蓝紫长发过腰、双侧低双马尾、直刘海、黑蕾丝眼罩、绯红泡泡袖上衣、黑束腰+牛皮竖系带、黑多层裙+米色荷叶衬裙+深金织带、黑蕾丝手套、半透黑丝袜、黑系带靴+米色鞋头。 |
| 2 | front | screenshot | 雨夜双人场景（动画截图），发色/氛围辅助，非结构依据 |
| 3 | front | fanart | 双人插画，非主参考 |
| 4 | front | sheet | ★排除：这是『鹿島神』（紫瞳、深蓝短波波头、水手服、生日2月3日/158cm），不是丰川祥子，属搜索噪声 |
| 5 | front | screenshot | MyGO!!!!! 五人海报，多人合影，不能作单角色比例依据 |
| 6 | front | fanart | 双人同人，非主参考 |
| 7 | front | fullbody | 小尺寸全身缩略图（校服版），比例辅助 |
| 8 | front | fanart | 同人插画带字幕，非主参考 |
| 9 | front | screenshot | ★最高价值特写：动画脸部特写。确认琥珀金色瞳孔（外圈深褐、内圈亮金）、浅蓝灰发、黑金条纹发带、极白肤色、细而淡的浅灰蓝眉。眼睛配色只信这张。 |
| 10 | front | screenshot | 舞台演出现场，非单角色参考 |
| 11 | front | screenshot | 暗场双马尾+校服，辅助确认发型轮廓 |
| 12 | front | screenshot | 校服版全身：浅灰西装+白衬衫+墨绿格裙+墨绿过膝袜。确认第二套服装，本模型采用舞台装故仅参考发型 |
| 13 | front | screenshot | 暗红舞台场景，非主参考 |
| 14 | front | fanart | 生日贺图：双手靠唇、长发+双马尾轮廓清楚，姿态参考 |

## 信息缺口（必须告知用户）
- 缺背面参考：15 张对照图里没有任何一张是背面视角（#14 是正面贺图、#10/#13 是远景舞台），后发走势与裙后摆拖尾长度只能按对称+常识推测
- 缺侧面参考：只有 #1 的 3/4 侧可推厚度，身体前后厚度、发量厚度为推测值
- 舞台黑色蕾丝眼罩（#1 有）属演出道具，会让眼睛不可见，未纳入常规形态；如需要可后续加 Eyelid 层覆盖
- 同人图比例与配色互不统一（#0/#6/#8/#14 风格差异大），一律以 #1 白底立绘 + #9 脸特写为准
- 搜索噪声已排除：cell #4 实际是『鹿島神』（紫瞳短发水手服），不是丰川祥子
- 贴图按模板保留 128x128 以避免重排 172 个 per-face UV；代价是脸部只有 7x7 逻辑像素，已用放大 UV 到 14x14 的方式把脸部实际分辨率提到 2 倍

## 备注
从零重建：环境全新安装，无任何历史缓存。骨架沿用 YSM 标准模板（64 骨），在其上重塑造型与全部贴图；新增 Petticoat/Corset/LeftTwinTail/RightTwinTail/RightRibbon 五根骨骼。
