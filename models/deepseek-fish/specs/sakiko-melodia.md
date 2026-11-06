# 建模规格：丰川祥子（明日方舟联动皮肤「旋律的主人」）
> 来源：《明日方舟》×《BanG Dream! Ave Mujica》联动 SideStory「无忧梦呓」2025-09-04 — CROSSOVER 系列时装「旋律的主人」(Master of Melodia)；干员丰川祥子 6★ 近卫·领主 / 萨卡兹（角为种族体征）

- 方块总数 **370**（语料中位 306）
- 头部区域占比 **27.6%**（语料中位 33.2%）
- 贴图 **512px**

## 配色
| 色号 | 颜色 | 用途 |
|---|---|---|
| hair_hi | `#EDF1FA` | 头发顶级高光/银白 |
| hair_light | `#D5DDF2` | 头发受光面 |
| hair_base | `#B7C3E2` | 头发主色（银蓝） |
| hair_mid | `#9AA7CC` | 头发过渡/发缝 |
| hair_shadow | `#7885AE` | 头发暗面 |
| hair_deep | `#5A6690` | 头发最深处/发梢 |
| skin | `#FBEEEA` | 脸/颈/耳/肩/手 |
| skin_shadow | `#F0D2CB` | 下巴/颈部/锁骨阴影 |
| skin_blush | `#F5C0BA` | 腮红 |
| mouth_rose | `#C98C86` | 嘴唇 |
| eye_iris | `#D9A93F` | 虹膜主色（琥珀金） |
| eye_iris_light | `#F2D180` | 虹膜内圈亮金 |
| eye_ring | `#6B4A1E` | 虹膜外圈深褐 |
| eye_lash | `#221A18` | 上眼睑/睫线 |
| eye_white | `#FDFBF7` | 眼白/高光 |
| ink_0 | `#0C0D12` | 最深黑：蕾丝阴影/裙内衬 |
| ink_1 | `#161822` | 裙装主黑 |
| ink_2 | `#20232F` | 黑色中调/分片 |
| ink_3 | `#2C3040` | 黑色受光亮面 |
| ink_4 | `#3D4256` | 黑色边缘高光 |
| blue_deep | `#16245E` | 宝蓝最暗 |
| blue_main | `#2B4FB8` | 宝蓝荷叶边主色 |
| blue_hi | `#4C78E0` | 宝蓝受光/缎带 |
| blue_pale | `#8FB4F2` | 浅蓝高光/宝石边 |
| blue_black | `#101833` | 黑蓝过渡面 |
| lilac | `#9C90C4` | 丁香紫荷叶边 |
| lilac_shadow | `#6E6491` | 丁香紫阴影 |
| frill_white | `#EFEEF5` | 银白荷叶底边 |
| frill_shadow | `#C4C2D3` | 银白荷叶阴影 |
| horn_base | `#191A26` | 角根部深色 |
| horn_mid | `#272939` | 角主体 |
| horn_ridge | `#464A63` | 角棱纹高光 |
| horn_glow | `#BFD6F2` | 角根内侧蓝白高光 |
| gem_blue | `#A8D6F6` | 胸前方形宝石 |
| gem_hi | `#EAF7FF` | 宝石高光 |
| gold | `#C6A85E` | 宝石镶框/十字发夹/剑护手 |
| gold_hi | `#E6CF92` | 金色高光 |
| steel | `#B9C5DA` | 剑身 |
| steel_shadow | `#7C879E` | 剑身暗面 |
| boot_black | `#0F1016` | 靴身 |
| boot_hi | `#24262F` | 靴高光/扣带 |

## 部位与构建顺序
| 顺序 | 部位 | 骨骼 | 父级 | 方块 | 区域 | 形状 | 参考图 |
|---|---|---|---|---|---|---|---|
| 1 | chest_bow | ChestBow | UpperBody | 14 | torso | 胸前大蝴蝶结：两翼黑白细条纹+结心，中心浅蓝方形宝石（金框） | #13 #5 |
| 2 | bodice | UpperBody | UpBody | 18 | torso | 黑色胸衣：胸口浅色竖条纹胸襟、露肩、胸下丁香紫荷叶边一圈、腰收窄 | #13 #5 |
| 3 | breast | Breast | UpperBody | 4 | torso | 胸部体块，被胸衣包住 | #13 |
| 4 | waist_ribbon | WaistRibbon | UpperBody | 6 | torso | 腰间宝蓝缎带+垂带，正面偏左打结 | #13 #0 |
| 5 | legs | LeftLeg/LeftLowerLeg/RightLeg/RightLowerLeg | DownBody | 6 | leg | 黑色半透丝袜包整条腿 | #13 #0 |
| 6 | leg_acc | LeftLeg/RightLeg | DownBody | 4 | leg | 大腿处蓝色环带（Q 版小人可辨） | #0 |
| 7 | boots | LeftFoot/RightFoot | DownBody | 26 | leg | 黑厚底扣带短靴：靴筒+靴身+鞋头+厚底+2 道扣带+小金属扣 | #13 #0 |
| 8 | arms | LeftArm/LeftForeArm/RightArm/RightForeArm | UpBody | 12 | arm | 裸露上臂/前臂（皮肤），袖口环在肘上 | #13 |
| 9 | gloves | LeftHand/RightHand | UpBody | 12 | arm | 黑色蕾丝露指手套：手背+掌心+腕口翻边，指尖露肤 | #13 |
| 10 | head | Head | AllHead | 4 | head | 8x8x8 头壳（前面板 UV 放大到更大画布重绘脸）+ 颈节 | #5 #13 |
| 11 | eyes | LeftEyelid/LeftEyesBase/LeftPupil/LeftEyeHi/RightEyelid/RightEyesBase/RightPupil/RightEyeHi | AllHead | 8 | head | 四层眼：Eyelid(上睫线)→EyesBase(眼白)→Pupil(琥珀金虹膜+深褐外圈)→EyeHi(高光点)；左右各 4 块 | #5 #8 |
| 12 | eyebrows | LeftEyebrow/RightEyebrow | AllHead | 2 | head | 细长淡银蓝眉，略平缓 | #5 |
| 13 | mouth | Mouth | AllHead | 2 | head | 小嘴：唇线+下唇，微张 | #5 #8 |
| 14 | head_acc | HeadAcc | AllHead | 8 | head | 额顶金/蓝十字小发夹、两侧深藏青细发带、耳侧细饰 | #13 #5 |
| 15 | hair_front | HairFront | Head | 22 | hair | 刘海：中偏分发缝，5-6 缕不等长贴合发片，两侧过眉眼，不做蓬松团 | #5 #13 |
| 16 | hair_side | HairSideL/HairSideR | Head | 20 | hair | 两鬓侧发：沿脸侧垂到锁骨，耳前一片较薄，耳后一片较厚 | #13 #8 |
| 17 | hair_back | HairBack | Head | 28 | hair | 后发大团：贴后脑包裹，向下延长到腰际，分层 3 段（上包/中段/发梢） | #13 #8 |
| 18 | hair_detail | HairTop | Head | 8 | hair | 头顶发束/发缝分界线/两侧碎发，压低体量使头型贴合 | #5 #13 |
| 19 | skirt_outer | SkirtOuter | DownBody | 34 | skirt | 黑蕾丝外层大摆裙：前/左/右/后 4 组裙片×2 层错落，下缘做不规则蕾丝齿边 | #13 #0 |
| 20 | skirt_inner | SkirtInner | DownBody | 22 | skirt | 宝蓝色荷叶边衬裙：从黑外裙下缘露出，两层荷叶，层间有蓝色深浅差 | #13 #0 |
| 21 | skirt_frill | SkirtFrill | DownBody | 14 | skirt | 银白色最底层荷叶边，只在裙底缘露出一圈 | #13 |
| 22 | skirt_train | SkirtTrain | DownBody | 12 | skirt | 后侧不对称黑纱拖尾（立绘里向画面左侧拖出很长），半透明黑纱质感靠贴图灰阶表现 | #13 |
| 23 | twintail | LeftTwinTail/RightTwinTail | Root | 22 | other | 耳侧低位双马尾，垂到胸前/腰际，末端微卷；马尾根部有深藏青细带扎结 | #13 #5 |
| 24 | horns | LeftHorn/RightHorn | Root | 26 | other | 萨卡兹羊角：每侧 13 块分 5 节，自头顶两侧颞部起、向外下卷再向前上翘；深藏青近黑+横向棱纹；角根内侧蓝白高光。挂 Head，不进 Eyelid/Face，保证表情不变形 | #8 #0 #13 |
| 25 | collar | Collar | Root | 8 | other | 黑色蕾丝高立领（包住颈），前中开口，边缘细齿 | #13 #5 |
| 26 | shoulder_puff | LeftShoulderPuff/RightShoulderPuff | Root | 10 | other | 黑色泡泡短袖，肩头圆鼓、下缘收紧成袖口环 | #13 |
| 27 | sword | Sword | Root | 18 | other | 细长刺剑（挂右手）：剑身+护手+握柄+配重球+蓝色宝石；护手取音符母题。立绘未持剑，剑来自 Q 版小人，属战斗形态道具 | #0 |

## 参考图判读
| # | 角度 | 类型 | 备注 |
|---|---|---|---|
| 0 | three_quarter | render | ★游戏内 Q 版小人站姿（458x458，白底）。站姿结构最好用：角从头顶两侧向外后卷、粗壮；黑外裙+宝蓝荷叶衬裙；胸口蓝色菱形宝石吊坠；腰蓝缎带；黑腿+蓝大腿环；黑厚底靴+蓝缀；双手各持一把细长刺剑。Q 版比例不用于量身高，只用结构/配色/武器。 |
| 1 | front | fullbody | 排除：校服（灰西装+绿格裙+乐福鞋），非本皮肤。仅旁证发色为银蓝、瞳为琥珀金。 |
| 2 | front | fanart | 排除：表情包 meme（蓝发+橙色色块脸），零结构信息。 |
| 3 | side | screenshot | 弱参考：暗场钢琴旁截图，服装看不清（疑为基地制服），不入结构依据。 |
| 4 | front | fullbody | 排除：便服全身（白衬衫+灰菱格裙+粉短裤+黑玛丽珍）。仅确认发色银蓝、瞳琥珀金、发带为黑色。 |
| 5 | front | closeup | ★皮肤脸部特写（1920x1440）。确认：琥珀金大眼、深色上睫线、银蓝发+刘海、深藏青铆钉发带、黑白细条纹大蝴蝶结+浅蓝方形宝石、丁香紫荷叶边（在胸下）。眼睛与胸口配饰只信这张。 |
| 6 | front | fanart | 排除：同人「被驯服的祥」带面具图，非官方，不作结构依据。 |
| 7 | front | sheet | 排除：Ave Mujica 原版绯红舞台插画（红色调、玫瑰、翅膀）。任务书明确要求不得用原版演出服顶替本皮肤。 |
| 8 | three_quarter | screenshot | ★角形态最佳参考（1920x1080 剧情 CG，3/4 站姿）。两只粗大羊角：深藏青近黑、有横向棱纹、从头顶两侧向外下卷再上翘，角根内侧有蓝白高光；琥珀金瞳；银蓝长直发过腰、发梢微飘；侧发深蓝细带。注意：这套是基地制服（黑夹克+RHODES ISLAND 臂章+青色肩饰），服装部分不采用。 |
| 9 | front | screenshot | 弱参考：暗景双人拥抱，发色/氛围辅助，无结构价值。 |
| 10 | front | fullbody | 排除：校服全身（灰马甲+白衬衫+绿格裙），非本皮肤。 |
| 11 | front | screenshot | 排除：校服坐姿，非本皮肤。 |
| 12 | front | poster | 弱参考：活动竖版海报（浅色/校服造型），非本皮肤。 |
| 13 | three_quarter | sheet | ★★官方皮肤立绘「旋律的主人」原图 2176x2176（唯一最高清官方来源）。核心信息：黑蕾丝高领；胸前黑白细条纹大蝴蝶结+浅蓝方形宝石；宝蓝色缎带；黑蕾丝露指手套；多层大摆裙=黑蕾丝外裙(含不对称长拖尾)+宝蓝荷叶边衬裙+银白荷叶底边；黑色半透丝袜；黑厚底扣带短靴；银蓝长发两侧低双马尾垂至胸前+额顶金/蓝十字小发夹；粗大黑色弯角带棱纹；琥珀金瞳。构图坐于黑沙发旁（留声机+琴键楼梯+高音谱号音符）——坐姿，不入比例依据，只入造型/配色/层次。 |
| 14 | front | poster | 弱参考：活动宣传图（校服），非本皮肤。 |
| 15 | front | poster | 弱参考：竖版宣传长图（校服/便服），非本皮肤。 |

## 信息缺口（必须告知用户）
- 缺背面参考：16 张候选里没有任何一张背面视图。后发走势（是否中分、发量厚度）、裙后摆层次与拖尾长度只能按对称+立绘 3/4 推测。
- 缺正侧面参考：只有 ref_015 坐姿立绘与 ref_010 的 3/4 剧情立绘，身体前后厚度、裙撑前后径、角的前后弯曲角度均为推测。
- 官方高清立绘直链全部失败：arknights.wiki.gg 全部 404、media.prts.wiki 超时、static.tvtropes 403、wiki.gg API 403。最终只能用萌娘百科 skin1 原图（ref_015，2176x2176）作为最高清官方来源，已足够读结构。
- 皮肤官方立绘是坐姿，站立全身比例无法从官方图量测；改用 Q 版小人 ref_000 的结构 + YSM 语料人体比例（脚底 Y=0、头顶约 Y=40）确定竖向分布。
- 面具未纳入：皮肤部署动画有「落地摘面具」，但立绘中未佩戴；静态模型做可摘面具会破坏头部轮廓，故不做。
- ref_007/ref_013(原序号) 为 Ave Mujica 原版绯红演出服，按任务书要求明确排除，未参与任何造型取值。
- 剑属战斗形态：官方皮肤立绘 ref_015 未持剑，剑只见于 Q 版小人 ref_000（双手各一把）。本模型只做一把细长剑挂右手，并与任务书「角/裙」主线保持一致；如需严格立绘形态可删除 Sword 骨。

## 备注
与同工程旧的 sakiko-final（196 方块/贴图 128）相比，本次为全新模型：方块 370、贴图 512、新增角/双马尾/三层裙/武器等骨骼。骨架沿用 YSM 标准模板，新增 SkirtOuter/SkirtInner/SkirtFrill/SkirtTrain/WaistRibbon/HairFront/HairTop/HairBack/LeftTwinTail/RightTwinTail/LeftHorn/RightHorn/HeadAcc/ChestBow/Collar/LeftShoulderPuff/RightShoulderPuff/Sword 等语义骨骼。
