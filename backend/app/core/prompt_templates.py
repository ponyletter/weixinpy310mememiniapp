"""
内置经过 Twitter / X 实测出图效果最佳的 ChatGPT Images 2.5 表情包动作提示词模板
支持让 ChatGPT 原生在每一帧中绘制随动作跳跃的动态艺术汉字！
"""

def build_meme_prompt(template_id: str, char_desc: str = "", caption: str = "", has_image: bool = False) -> str:
    """根据动作模板、角色描述、文字内容及是否有参考图，智能组装提示词"""
    char_desc = (char_desc or "").strip()
    caption = (caption or "").strip()

    # 1. 角色人设从句
    if has_image:
        if char_desc:
            char_clause = f"严格使用我上传的参考图片作为角色原型，结合补充描述（{char_desc}），精准还原外貌特征、五官、发型与服饰配色"
        else:
            char_clause = "严格使用我上传的参考图片中的角色作为唯一形象原型，精准还原其外貌特征、五官发型和标志性细节"
    else:
        if char_desc:
            char_clause = f"绘制以（{char_desc}）为原型的Q版卡通形象"
        else:
            char_clause = "绘制一个极具亲和力、呆萌可爱的Q版Line贴纸风格卡通角色"

    # 2. 文字字幕从句
    if caption:
        text_clause = f"文字要求：16 张小图片里都自带跟画面风格高度融合的手绘艺术字体，写着汉字“{caption}”，文字跟随动作自然律动跳跃，弹性十足。\n"
    else:
        text_clause = "文字要求：纯动作肢体表情包，画面中不要绘制任何汉字、字母或文本字幕。\n"

    # 3. 动作核心描述
    action_map = {
        "kiss": (
            f"为我生成该角色（{char_clause}）的半身像连贯动图表情拆分帧。\n"
            f"使用 4行×4列 布局共生成 16 个连续小动作，动作流程为“飞吻”连贯拆分：双手捧心、嘟嘴眨眼、将爱心飞吻抛出并弹跳扩散，最后一帧自然循环回第一帧。\n"
            f"{text_clause}"
            f"规格要求：16 个小图片之间留有 30~50px 充足空白方便后续独立切割，主体和文字严禁超出所属单元格。背景必须为纯白色（RGB 255,255,255），不要画分割线和水印，画面比例 1:1。"
        ),
        "battle_chibi": (
            f"以（{char_clause}）制作 16 帧 2.5D Q版像素/街机风格战斗攻击动画拆分。\n"
            f"动作流程：准备姿势 → 预备蓄力 → 强力出击 → 冲击峰值 → 效果消散 → 收势恢复，第 16 帧无缝循环回第 1 帧。\n"
            f"{text_clause}"
            f"规格：4列×4行 精确排列共 16 帧，尺寸均一，固定机位，四周预留充足纯白留白，背景为纯白色，无网格线。"
        ),
        "slack_worker": (
            f"以（{char_clause}）生成一套 4行×4列 共 16 帧的搞笑打工人表情包动作拆解图集。\n"
            f"动作体现：疯狂敲键盘 → 偷偷打哈欠 → 喝水偷瞄四周 → 点头如捣蒜，形成极具幽默感的完整循环动态。\n"
            f"{text_clause}"
            f"规格：统一纯白背景，四边留足裁切留白，严禁画分割线。"
        ),
        "pet_idle": (
            f"以（{char_clause}）生成带有微动态待机呼吸效果的 16 帧萌动拆解图。\n"
            f"动作流程：轻柔呼吸起伏、耳朵/尾巴俏皮轻微摆动、眨眼微笑，脚部站立固定不移位。\n"
            f"{text_clause}"
            f"规格：排列为 4列×4行，背景统一纯白色，各单元格四周预留充足透明余量，严禁分割线。"
        ),
        "heart_dance": (
            f"根据（{char_clause}）生成 4行×4列 共 16 帧的 Q 版魔性比心摇摆舞蹈动作。\n"
            f"动作流程：角色左右欢快律动，双手从胸前变出弹跳发光的爱心，第 16 帧平滑循环回第 1 帧。\n"
            f"{text_clause}"
            f"规格：纯白底色，四周留白充足，各帧独立无跨格交叉。"
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
        "prompt_builder": lambda char, text, has_image=False: build_meme_prompt("kiss", char, text, has_image)
    },
    {
        "id": "battle_chibi",
        "title": "Q版战斗暴击 (16帧街机风)",
        "desc": "准备→蓄力→出击→冲击峰值→收势，打击感拉满",
        "action": "战斗出击",
        "default_caption": "吃我一拳",
        "prompt_builder": lambda char, text, has_image=False: build_meme_prompt("battle_chibi", char, text, has_image)
    },
    {
        "id": "slack_worker",
        "title": "打工人摸鱼日常 (魔性搞笑)",
        "desc": "疯狂敲键盘→偷打哈欠→喝水偷瞄，打工人必备共鸣",
        "action": "摸鱼",
        "default_caption": "疯狂摸鱼中",
        "prompt_builder": lambda char, text, has_image=False: build_meme_prompt("slack_worker", char, text, has_image)
    },
    {
        "id": "pet_idle",
        "title": "萌宠呆萌待机 (微动态萌化)",
        "desc": "呼吸起伏、眨眼与耳朵摆动，无缝循环萌化人心",
        "action": "呆萌晃动",
        "default_caption": "乖巧等待",
        "prompt_builder": lambda char, text, has_image=False: build_meme_prompt("pet_idle", char, text, has_image)
    },
    {
        "id": "heart_dance",
        "title": "魔性比心摇摆舞 (魔性蹦迪)",
        "desc": "欢快左右律动，双手从胸前变出爱心",
        "action": "比心摇摆",
        "default_caption": "比心心",
        "prompt_builder": lambda char, text, has_image=False: build_meme_prompt("heart_dance", char, text, has_image)
    }
]

