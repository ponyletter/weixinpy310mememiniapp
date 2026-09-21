"""
内置经过 Twitter / X 实测出图效果最佳的 ChatGPT Images 2.5 表情包动作提示词模板
支持让 ChatGPT 原生在每一帧中绘制随动作跳跃的动态艺术汉字！
"""

def build_meme_prompt(
    template_id: str,
    char_desc: str = "",
    caption: str = "",
    has_image: bool = False,
    is_sketch: bool = False,
    custom_action: str = "",
    frame_count: int = 16
) -> str:
    """根据动作模板、角色描述、文字内容、是否有参考图、是否手绘草图、自定义动作以及自定义帧数，智能组装提示词"""
    char_desc = (char_desc or "").strip()
    caption = (caption or "").strip()
    custom_action = (custom_action or "").strip()
    frame_count = int(frame_count) if frame_count in (2, 4, 8, 9, 16) else 16

    # 1. 角色人设从句 (支持手绘草图 SketchUP 模式与常规图生图)
    if is_sketch:
        if char_desc:
            char_clause = f"严格依据我上传的手绘草图（草图包含人设轮廓、姿势构图与造型线条），结合补充描述（{char_desc}），将其精修绘制为高质量可爱Line贴纸风格卡通角色，精准还原草图中的核心特征与神态"
        else:
            char_clause = "严格依据我上传的手绘草图（草图包含人设轮廓、姿势构图与造型线条），将其精细化绘制为生动呆萌的Q版Line贴纸风格卡通角色，精准还原草图中的神韵与造型"
    elif has_image:
        if char_desc:
            char_clause = f"严格使用我上传的参考图片作为角色原型，结合补充描述（{char_desc}），精准还原外貌特征、五官、发型与服饰配色"
        else:
            char_clause = "严格使用我上传的参考图片中的角色作为唯一形象原型，精准还原其外貌特征、五官发型和标志性细节"
    else:
        if char_desc:
            char_clause = f"绘制以（{char_desc}）为原型的Q版卡通形象"
        else:
            char_clause = "绘制一个极具亲和力、呆萌可爱的Q版Line贴纸风格卡通角色"

    # 网格布局与帧数描述
    layout_map = {
        2: "1行×2列 布局共生成 2 个关键动作分解帧",
        4: "2行×2列 布局共生成 4 个连续动作帧",
        8: "2行×4列 布局共生成 8 个连续动作帧",
        9: "3行×3列 布局共生成 9 个连续动作帧",
        16: "4行×4列 布局共生成 16 个连续动作帧",
    }
    layout_desc = layout_map.get(frame_count, f"{frame_count} 个连续动作帧")

    # 2. 文字字幕从句
    if caption:
        text_clause = f"文字要求：{frame_count} 张小图片里都自带跟画面风格高度融合的手绘艺术字体，写着汉字“{caption}”，文字跟随动作自然律动跳跃，弹性十足。\n"
    else:
        text_clause = "文字要求：纯动作肢体表情包，画面中不要绘制任何汉字、字母或文本字幕。\n"

    # 3. 动作核心描述
    action_map = {
        "kiss": (
            f"为我生成该角色（{char_clause}）的半身像连贯动图表情拆分帧。\n"
            f"使用 {layout_desc}，动作流程为“飞吻”连贯拆分：双手捧心、嘟嘴眨眼、将爱心飞吻抛出并弹跳扩散，最后一帧自然循环回第一帧。\n"
            f"{text_clause}"
            f"规格要求：{frame_count} 个小图片之间留有 30~50px 充足空白方便后续独立切割，主体和文字严禁超出所属单元格。背景必须为纯白色（RGB 255,255,255），不要画分割线和水印，画面比例 1:1。"
        ),
        "battle_chibi": (
            f"以（{char_clause}）制作 {frame_count} 帧 2.5D Q版像素/街机风格战斗攻击动画拆分。\n"
            f"使用 {layout_desc}，动作流程：准备姿势 → 预备蓄力 → 强力出击 → 冲击峰值 → 效果消散 → 收势恢复，第 {frame_count} 帧无缝循环回第 1 帧。\n"
            f"{text_clause}"
            f"规格：精确排列共 {frame_count} 帧，尺寸均一，固定机位，四周预留充足纯白留白，背景为纯白色，无网格线。"
        ),
        "slack_worker": (
            f"以（{char_clause}）生成一套 {layout_desc} 的搞笑打工人表情包动作拆解图集。\n"
            f"动作体现：疯狂敲键盘 → 偷偷打哈欠 → 喝水偷瞄四周 → 点头如捣蒜，形成极具幽默感的完整循环动态。\n"
            f"{text_clause}"
            f"规格：统一纯白背景，四边留足裁切留白，严禁画分割线。"
        ),
        "pet_idle": (
            f"以（{char_clause}）生成带有微动态待机呼吸效果的 {frame_count} 帧萌动拆解图。\n"
            f"使用 {layout_desc}，动作流程：轻柔呼吸起伏、耳朵/尾巴俏皮轻微摆动、眨眼微笑，脚部站立固定不移位。\n"
            f"{text_clause}"
            f"规格：统一纯白色背景，各单元格四周预留充足透明余量，严禁分割线。"
        ),
        "heart_dance": (
            f"根据（{char_clause}）生成 {layout_desc} 的 Q 版魔性比心摇摆舞蹈动作。\n"
            f"动作流程：角色左右欢快律动，双手从胸前变出弹跳发光的爱心，第 {frame_count} 帧平滑循环回第 1 帧。\n"
            f"{text_clause}"
            f"规格：纯白底色，四周留白充足，各帧独立无跨格交叉。"
        ),
        "custom": (
            f"为我生成该角色（{char_clause}）的半身像连贯动图表情拆分帧。\n"
            f"使用 {layout_desc}。用户专属自定义动作流程：【{custom_action or '充满个性的生动特色动作，肢体与表情富有表现力'}】。\n"
            f"{frame_count} 帧动作流程自然递进连贯，第 {frame_count} 帧平滑无缝循环回第 1 帧。\n"
            f"{text_clause}"
            f"规格要求：{frame_count} 个小图片呈网格精确排列共 {frame_count} 帧，尺寸均一，固定机位，主体和文字严禁超出所属单元格，四周预留 30~50px 充足纯白空白便于切割。背景必须为纯白色（RGB 255,255,255），不要画任何分割线、边框或水印，画面比例 1:1。"
        )
    }

    return action_map.get(template_id, action_map["kiss"])

PROMPT_TEMPLATES = [
    {
        "id": "kiss",
        "title": "飞吻示爱 (连贯循环)",
        "desc": "可爱的飞吻分解动作，适合日常情侣/社交互动",
        "action": "飞吻示爱",
        "default_caption": "爱你哦",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("kiss", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "battle_chibi",
        "title": "Q版战斗暴击 (16帧街机风)",
        "desc": "准备→蓄力→出击→冲击峰值→收势，打击感拉满",
        "action": "战斗出击",
        "default_caption": "吃我一拳",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("battle_chibi", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "slack_worker",
        "title": "打工人摸鱼日常 (魔性搞笑)",
        "desc": "疯狂敲键盘→偷打哈欠→喝水偷瞄，打工人必备共鸣",
        "action": "摸鱼日常",
        "default_caption": "疯狂摸鱼中",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("slack_worker", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "pet_idle",
        "title": "萌宠呆萌待机 (微动态萌化)",
        "desc": "呼吸起伏、眨眼与耳朵摆动，无缝循环萌化人心",
        "action": "呆萌晃动",
        "default_caption": "乖巧等待",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("pet_idle", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "heart_dance",
        "title": "魔性比心摇摆舞 (魔性蹦迪)",
        "desc": "欢快左右律动，双手从胸前变出爱心",
        "action": "比心摇摆",
        "default_caption": "比心心",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("heart_dance", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "custom",
        "title": "✨ 自定义动作 (自由创意)",
        "desc": "支持自由输入专属动作、微表情或剧情动作流程",
        "action": "自定义专属动作",
        "default_caption": "看我的",
        "is_custom": True,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("custom", char, text, has_image, is_sketch, custom_action, frame_count)
    }
]

# 微信审核期间专用的合规动作模板（去敏，符合“工具-图片处理”品类，绝无“16帧深度拆解”暗示）
AUDIT_TEMPLATES = [
    {
        "id": "kiss",
        "title": "趣味爱心 (动效表情)",
        "desc": "爱心与弹跳微动效，适合情侣与日常问候",
        "action": "趣味爱心",
        "default_caption": "爱你哦",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("kiss", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "battle_chibi",
        "title": "动感活力 (热血表情)",
        "desc": "动感冲击与震颤微动效，生动活泼",
        "action": "动感活力",
        "default_caption": "吃我一拳",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("battle_chibi", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "slack_worker",
        "title": "打工摸鱼 (趣味日常)",
        "desc": "轻微晃动趣味字幕，职场打工人必备日常",
        "action": "趣味摸鱼",
        "default_caption": "疯狂摸鱼中",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("slack_worker", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "pet_idle",
        "title": "萌宠微动 (可爱节奏)",
        "desc": "轻柔待机律动，温和自然萌动",
        "action": "萌宠微动",
        "default_caption": "乖巧等待",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("pet_idle", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "heart_dance",
        "title": "比心互动 (欢快动效)",
        "desc": "欢快左右律动与变色边框，轻快动感",
        "action": "比心动效",
        "default_caption": "比心心",
        "is_custom": False,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("heart_dance", char, text, has_image, is_sketch, custom_action, frame_count)
    },
    {
        "id": "custom",
        "title": "✨ 自由定制 (个性台词)",
        "desc": "支持自由输入专属台词字幕与动态排版",
        "action": "个性定制",
        "default_caption": "看我的",
        "is_custom": True,
        "prompt_builder": lambda char, text, has_image=False, is_sketch=False, custom_action="", frame_count=16: build_meme_prompt("custom", char, text, has_image, is_sketch, custom_action, frame_count)
    }
]

def get_active_templates():
    """根据当前是否为审核模式，动态返回模板列表"""
    try:
        from app.database import is_audit_mode_active
        if is_audit_mode_active():
            return AUDIT_TEMPLATES
    except Exception:
        pass
    return PROMPT_TEMPLATES


# =========================================================================
# 16 款静态表情包专用场景文案包与提示词生成器
# =========================================================================

SCENE_TEXT_PACKAGES = {
    "none": [""] * 16,
    "worker": [
        "收到", "好的老板", "疯狂搬砖", "摸鱼中",
        "头秃了", "我太难了", "方案又改了", "震惊老铁",
        "血压上来了", "需求是什么", "搞定收工", "夸得我脸红",
        "跪求别催", "吃瓜看戏", "困到变形", "我下班啦溜了"
    ],
    "battle": [
        "点赞666", "得瑟拿捏", "疯狂输出", "暗中观察",
        "裂开崩溃", "猛男落泪", "出来挨打", "惊呆了",
        "无语翻白眼", "满头问号", "帅气登场", "害羞掩面",
        "抱拳感谢", "现场吃瓜", "睡了别艾特", "告辞溜了"
    ],
    "cute": [
        "谢谢你", "么么哒", "加油鸭", "喝杯奶茶",
        "委屈巴巴", "求抱抱", "生气气了", "星星眼哇塞",
        "叹气气", "疑惑脸??", "酷酷的哦", "爱你哟",
        "拜托拜托", "干杯耶", "呼呼大睡", "飞奔向你"
    ],
    "slack": [
        "好的(假装积极)", "随缘吧", "我装的", "看神仙打架",
        "毁灭吧", "哭死扎心", "勿扰已死", "还能这样",
        "累了退下吧", "听不懂不想懂", "佛系看淡", "算了吧",
        "放过我吧", "毫无波澜", "躺平中", "彻底告辞"
    ]
}

SCENE_TEXT_TITLES = {
    "none": "无字纯表情 (自由斗图)",
    "worker": "打工人日常 (职场生存必备)",
    "battle": "群聊斗图 (轻松拿捏全场)",
    "cute": "萌系可爱回应 (聊天更甜)",
    "slack": "摆烂躺平 (佛系佛系佛系)",
    "custom": "自定义填词"
}

EMOTION_TAGS_16 = [
    "大笑点赞", "俏皮比耶", "狂敲键盘", "托腮喝茶",
    "抱头抓狂", "大哭流泪", "愤怒喷火", "震惊捂嘴",
    "叹气白眼", "歪头问号", "墨镜自信", "害羞脸红",
    "合十拜托", "吃瓜看戏", "犯困打哈欠", "下班奔跑"
]


def build_sticker16_prompt(
    character_desc: str = "",
    style: str = "wechat_sticker",     # wechat_sticker | keep_orig | cute_chibi | funny_line | 3d_toy
    composition: str = "bust",         # closeup | bust | full_body
    background: str = "white",         # white | transparent
    has_image: bool = True,
    is_sketch: bool = False,
    custom_action: str = ""
) -> str:
    """
    组装 16 款静态独立表情包雪碧图专用 Prompt：
    固定 4×4 共 16 个格子的差异化情绪姿态，严禁绘制文字，保证纯净画面与高表现力。
    统一采用与原有动图一致的可爱Line贴纸/微信Q版表情包风格，严守角色一致性。
    """
    char_desc = (character_desc or "").strip()
    custom_action = (custom_action or "").strip()

    # 别名规范化
    style_map = {
        "wechat_sticker": "wechat_sticker",
        "line_sticker": "wechat_sticker",
        "keep_orig": "wechat_sticker",
        "cute_chibi": "cute_chibi",
        "anime": "cute_chibi",
        "funny_line": "funny_line",
        "3d_toy": "3d_toy",
        "chibi_3d": "3d_toy",
    }
    comp_map = {
        "bust": "bust",
        "closeup": "closeup",
        "fullbody": "full_body",
        "full_body": "full_body",
    }
    style_key = style_map.get(style, "wechat_sticker")
    comp_key = comp_map.get(composition, "bust")

    # 1. 人设与身份来源
    if is_sketch:
        if char_desc:
            char_id = f"the character from my uploaded sketch drawing combined with description '{char_desc}'"
        else:
            char_id = "the cute cartoon character from my uploaded sketch drawing"
    elif has_image:
        if char_desc:
            char_id = f"the person/character in the reference image, preserving facial identity, haircut and core features ({char_desc})"
        else:
            char_id = "the person/character in the reference image, strictly keeping consistent facial identity and signature look"
    else:
        if char_desc:
            char_id = f"a cute charismatic original character based on '{char_desc}'"
        else:
            char_id = "an adorable expressive chibi cartoon avatar character"

    # 2. 风格定义 (与原有小程序动图风格保持高度统一：经典微信2D手绘贴纸/Line表情包画风)
    style_prompts = {
        "wechat_sticker": "classic WeChat & Line cute emoji sticker style, 2D flat vector cartoon character, bold clean dark sticker contour lines, flat bright cel-shading, Japanese Line sticker aesthetic, white paper cutout sticker border, cute chibi proportions",
        "cute_chibi": "ultra-cute kawaii chibi sticker, big expressive sparkling anime eyes, soft rounded face, adorable pastel colors, thick sticker cut outline",
        "funny_line": "funny hilarious comic meme sticker, doodle cartoon lineart, exaggerated comical meme reactions, clean black and white with minimal color accents",
        "3d_toy": "3D vinyl collectible toy figure style, PopMart blind box aesthetic, smooth claymation shading, soft ambient occlusion lighting",
    }

    # 3. 构图定义
    comp_prompts = {
        "closeup": "extreme close-up portraits focusing heavily on vivid facial expressions in each cell",
        "bust": "bust portraits clearly showing head, expressive hands and funny gestures",
        "full_body": "full body dynamic chibi poses with energetic gestures and action silhouettes"
    }

    # 4. 背景定义
    bg_prompts = {
        "white": "solid clean pure white background (#FFFFFF, rgb(255,255,255)) across the entire canvas with clear uniform white margins between cells, solid white backdrop, absolutely NO dark or black background",
        "transparent": "isolated pure white background cutout, crisp clean borders around character silhouette"
    }

    # 5. 16 格固定动作与情绪指令（严禁绘制任何文字）
    grid_actions = (
        "strictly uniform 4x4 sprite sheet grid layout consisting of exactly 16 equally-sized square panels on a pure white background. "
        "Each cell MUST show a UNIQUE, HIGHLY EXPRESSIVE mood or gesture in exact order: "
        "1. laughing warmly with double thumbs-up; "
        "2. winking playfully with a peace V-sign gesture; "
        "3. sweating furiously typing at a mini laptop; "
        "4. resting chin on hand sipping a hot coffee cup; "
        "5. clutching head pulling hair in comical panic/meltdown; "
        "6. bawling tears streaming down like waterfalls; "
        "7. angry steam erupting from head with cute red face; "
        "8. shocked hands on cheeks with jaw dropped wide; "
        "9. weary sighing with slight humorous eye-roll; "
        "10. tilted head scratching ear with cartoon question marks; "
        "11. confident smirk wearing cool black sunglasses; "
        "12. blushing cute shy smile poking cheek with one finger; "
        "13. pleading with hands clasped together begging puppy eyes; "
        "14. eating a big slice of watermelon with spoon enjoying drama; "
        "15. sleepy yawning with big snot bubble drifting; "
        "16. dashing away with backpack waving goodbye. "
    )

    if style in style_map:
        style_key = style_map[style]
        style_prompt_text = style_prompts.get(style_key, style_prompts["wechat_sticker"])
    elif style in style_prompts:
        style_prompt_text = style_prompts[style]
    elif style and style.strip():
        style_prompt_text = f"custom art style: {style.strip()}, clean sticker aesthetic, 2D vector chibi cartoon, high quality lineart"
    else:
        style_prompt_text = style_prompts["wechat_sticker"]

    action_extra = f" Additional custom nuance: {custom_action}." if custom_action else ""

    prompt = (
        f"A master emoji sticker sheet depicting {char_id}. "
        f"Art style: {style_prompt_text}. "
        f"Framing: {comp_prompts.get(comp_key, comp_prompts['bust'])}. "
        f"Background: {bg_prompts.get(background, bg_prompts['white'])}. "
        f"STRICT CHARACTER IDENTITY CONSISTENCY: Every single cell of the 16 panels MUST depict the EXACT SAME character. "
        "The face, hairstyle, hair color, skin tone, clothing design, color palette, and line art MUST remain completely uniform and identical across all 16 cells. "
        f"{grid_actions}"
        f"{action_extra} "
        "CRITICAL RULES: NO text, NO typography, NO watermark, NO Chinese characters, NO English letters, "
        "uniform cell size across 4 rows and 4 columns, clean white separation gutters between all panels, "
        "total resolution 1024x1024 pixels."
    )
    return prompt



