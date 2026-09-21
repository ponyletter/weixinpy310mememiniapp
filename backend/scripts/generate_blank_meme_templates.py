import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BLANK_MEME_TEMPLATES = [
    # 1. 经典搞笑 / 熊猫头
    {
        "id": "tpl_panda_question",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 满脸问号",
        "default_text": "你在教我做事？",
        "theme": "panda_question",
        "tags": ["熊猫头", "问号", "疑惑", "懵逼"]
    },
    {
        "id": "tpl_panda_thumb",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 点赞大笑",
        "default_text": "听懂掌声！",
        "theme": "panda_thumb",
        "tags": ["熊猫头", "点赞", "好评", "大笑"]
    },
    {
        "id": "tpl_panda_cry",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 猛男落泪",
        "default_text": "扎心了老铁",
        "theme": "panda_cry",
        "tags": ["熊猫头", "大哭", "悲伤", "扎心"]
    },
    {
        "id": "tpl_panda_peek",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 暗中观察",
        "default_text": "暗中观察.jpg",
        "theme": "panda_peek",
        "tags": ["熊猫头", "偷看", "观察", "吃瓜"]
    },
    {
        "id": "tpl_panda_lean",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 战术后仰",
        "default_text": "战术后仰！",
        "theme": "panda_lean",
        "tags": ["熊猫头", "震惊", "后仰", "害怕"]
    },
    {
        "id": "tpl_panda_break",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 我裂开了",
        "default_text": "我直接当场裂开",
        "theme": "panda_break",
        "tags": ["熊猫头", "裂开", "崩溃", "暴躁"]
    },
    {
        "id": "tpl_panda_smug",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 得意坏笑",
        "default_text": "就这？就这？",
        "theme": "panda_smug",
        "tags": ["熊猫头", "坏笑", "得意", "挑衅"]
    },
    {
        "id": "tpl_panda_shrug",
        "category": "funny",
        "category_title": "经典熊猫",
        "title": "熊猫头 · 无奈摊手",
        "default_text": "我也很绝望啊",
        "theme": "panda_shrug",
        "tags": ["熊猫头", "摊手", "无奈", "无所谓"]
    },

    # 2. 萌宠可爱
    {
        "id": "tpl_cat_tea",
        "category": "cute",
        "category_title": "萌宠可爱",
        "title": "奶茶猫猫 · 吸吸奶茶",
        "default_text": "吨吨吨！快乐水",
        "theme": "cat_tea",
        "tags": ["猫咪", "奶茶", "可爱", "快乐"]
    },
    {
        "id": "tpl_dog_tilt",
        "category": "cute",
        "category_title": "萌宠可爱",
        "title": "歪头柴犬 · 眼神清澈",
        "default_text": "真的假的？我不信",
        "theme": "dog_tilt",
        "tags": ["柴犬", "萌宠", "疑惑", "呆萌"]
    },
    {
        "id": "tpl_bear_heart",
        "category": "cute",
        "category_title": "萌宠可爱",
        "title": "贴贴小熊 · 给你小心心",
        "default_text": "爱你哟么么哒~",
        "theme": "bear_heart",
        "tags": ["小熊", "比心", "贴贴", "表白"]
    },
    {
        "id": "tpl_cat_stars",
        "category": "cute",
        "category_title": "萌宠可爱",
        "title": "星星眼猫 · 哇塞崇拜",
        "default_text": "大佬太强了吧！",
        "theme": "cat_stars",
        "tags": ["猫咪", "崇拜", "崇拜", "星星眼"]
    },
    {
        "id": "tpl_doge_smile",
        "category": "cute",
        "category_title": "萌宠可爱",
        "title": "狗头保命 · 蜜汁微笑",
        "default_text": "狗头保命 [滑稽]",
        "theme": "doge_smile",
        "tags": ["狗头", "保命", "滑稽", "微笑"]
    },

    # 3. 打工人日常
    {
        "id": "tpl_worker_type",
        "category": "worker",
        "category_title": "打工人",
        "title": "疯狂搬砖 · 键盘敲出火",
        "default_text": "打工是不可能打工的",
        "theme": "worker_type",
        "tags": ["打工人", "加班", "敲键盘", "搬砖"]
    },
    {
        "id": "tpl_worker_fish",
        "category": "worker",
        "category_title": "打工人",
        "title": "摸鱼喝茶 · 心静自然凉",
        "default_text": "今天又是摸鱼的一天",
        "theme": "worker_fish",
        "tags": ["摸鱼", "喝茶", "佛系", "打工人"]
    },
    {
        "id": "tpl_worker_bald",
        "category": "worker",
        "category_title": "打工人",
        "title": "需求又改 · 当场头秃",
        "default_text": "需求别再改了！",
        "theme": "worker_bald",
        "tags": ["改需求", "头秃", "抓狂", "程序员"]
    },
    {
        "id": "tpl_worker_run",
        "category": "worker",
        "category_title": "打工人",
        "title": "准点下班 · 溜之大吉",
        "default_text": "下班！一秒都不多待",
        "theme": "worker_run",
        "tags": ["下班", "溜了", "周五", "飞奔"]
    },

    # 4. 吐槽斗图
    {
        "id": "tpl_sarcasm_melon",
        "category": "sarcasm",
        "category_title": "吐槽斗图",
        "title": "前排吃瓜 · 坐看神仙打架",
        "default_text": "坐等吃瓜，精彩！",
        "theme": "sarcasm_melon",
        "tags": ["吃瓜", "看戏", "八卦", "围观"]
    },
    {
        "id": "tpl_sarcasm_roll",
        "category": "sarcasm",
        "category_title": "吐槽斗图",
        "title": "翻大白眼 · 累了毁灭吧",
        "default_text": "对对对，你说的都对",
        "theme": "sarcasm_roll",
        "tags": ["白眼", "无语", "敷衍", "毁灭吧"]
    },
    {
        "id": "tpl_classic_salute",
        "category": "sarcasm",
        "category_title": "吐槽斗图",
        "title": "抱拳拜谢 · 大佬牛逼",
        "default_text": "给大佬递茶！",
        "theme": "classic_salute",
        "tags": ["抱拳", "感谢", "大佬", "佩服"]
    }
]


def draw_blank_template(item: dict, out_dir: Path, font_path: str):
    """绘制底部预留充足留白的表情包底图模板 (400x400)"""
    size = (400, 400)
    img = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    line_w = 4
    black = (30, 30, 30, 255)
    blush = (255, 180, 190, 220)

    try:
        font_large = ImageFont.truetype(font_path, 34)
    except Exception:
        font_large = ImageFont.load_default()

    theme = item["theme"]

    # 1. 熊猫头系列 (上部主体位于 y=30~250)
    if theme.startswith("panda_"):
        # 耳朵
        draw.ellipse([80, 45, 140, 105], fill=black)
        draw.ellipse([260, 45, 320, 105], fill=black)
        # 头部白底
        draw.ellipse([90, 60, 310, 250], fill=(255, 255, 255, 255), outline=black, width=line_w)

        if theme == "panda_question":
            # 疑惑眼眉毛
            draw.arc([130, 115, 175, 150], start=0, end=180, fill=black, width=line_w)
            draw.arc([225, 105, 270, 140], start=180, end=360, fill=black, width=line_w)
            draw.ellipse([145, 140, 160, 155], fill=black)
            draw.ellipse([240, 130, 255, 145], fill=black)
            # 歪嘴
            draw.arc([180, 180, 220, 210], start=0, end=180, fill=black, width=line_w)
            # 头顶问号
            draw.text((315, 60), "???", fill=(225, 40, 40, 255), font=font_large)

        elif theme == "panda_thumb":
            # 眯眯笑眼
            draw.arc([130, 125, 175, 155], start=180, end=360, fill=black, width=line_w)
            draw.arc([225, 125, 270, 155], start=180, end=360, fill=black, width=line_w)
            # 腮红
            draw.ellipse([115, 155, 145, 175], fill=blush)
            draw.ellipse([255, 155, 285, 175], fill=blush)
            # 大笑嘴
            draw.chord([160, 165, 240, 225], start=0, end=180, fill=(230, 60, 60, 255), outline=black, width=line_w)
            # 竖起大拇指
            draw.ellipse([305, 130, 355, 190], fill=(255, 255, 255, 255), outline=black, width=line_w)
            draw.text((315, 140), "👍", fill=black, font=font_large)

        elif theme == "panda_cry":
            # 抓狂眉
            draw.line([(130, 130), (170, 110)], fill=black, width=line_w)
            draw.line([(230, 110), (270, 130)], fill=black, width=line_w)
            # 紧闭双眼
            draw.line([(135, 140), (165, 140)], fill=black, width=line_w)
            draw.line([(235, 140), (265, 140)], fill=black, width=line_w)
            # 瀑布泪
            draw.rectangle([140, 145, 162, 230], fill=(70, 160, 255, 220), outline=black, width=2)
            draw.rectangle([238, 145, 260, 230], fill=(70, 160, 255, 220), outline=black, width=2)
            # 倒U形哭嘴
            draw.arc([180, 190, 220, 225], start=180, end=360, fill=black, width=line_w)

        elif theme == "panda_peek":
            # 暗中观察
            draw.ellipse([135, 120, 175, 155], fill=black)
            draw.ellipse([225, 120, 265, 155], fill=black)
            draw.ellipse([150, 125, 162, 137], fill=(255, 255, 255, 255))
            draw.ellipse([240, 125, 252, 137], fill=(255, 255, 255, 255))
            # 墙体下半部
            draw.rectangle([60, 190, 340, 250], fill=(235, 238, 245, 255), outline=black, width=line_w)

        elif theme == "panda_lean":
            # 战术后仰 (圆眼震惊)
            draw.ellipse([130, 115, 175, 155], fill=black)
            draw.ellipse([225, 115, 270, 155], fill=black)
            draw.ellipse([145, 125, 160, 140], fill=(255, 255, 255, 255))
            draw.ellipse([240, 125, 255, 140], fill=(255, 255, 255, 255))
            # O形小嘴
            draw.ellipse([185, 180, 215, 215], fill=black)
            # 感叹号
            draw.text((315, 55), "!!", fill=(220, 40, 40, 255), font=font_large)

        elif theme == "panda_break":
            # 抓狂裂开
            draw.line([(200, 60), (180, 110), (220, 150), (190, 190), (210, 250)], fill=(225, 30, 30, 255), width=line_w)
            draw.ellipse([135, 125, 170, 160], fill=black)
            draw.ellipse([230, 125, 265, 160], fill=black)
            # 咬牙嘴
            draw.rectangle([165, 190, 235, 220], fill=(255, 255, 255, 255), outline=black, width=line_w)
            draw.line([(188, 190), (188, 220)], fill=black, width=2)
            draw.line([(212, 190), (212, 220)], fill=black, width=2)

        elif theme == "panda_smug":
            # 坏笑挑眉
            draw.arc([130, 115, 175, 145], start=180, end=360, fill=black, width=line_w)
            draw.arc([225, 115, 270, 145], start=180, end=360, fill=black, width=line_w)
            # 嘴角上翘
            draw.arc([165, 165, 235, 215], start=0, end=180, fill=black, width=line_w)
            draw.line([(230, 190), (245, 180)], fill=black, width=line_w)

        elif theme == "panda_shrug":
            # 摊手
            draw.arc([130, 125, 175, 155], start=0, end=180, fill=black, width=line_w)
            draw.arc([225, 125, 270, 155], start=0, end=180, fill=black, width=line_w)
            draw.line([(175, 195), (225, 195)], fill=black, width=line_w)
            # 两侧摊开的手
            draw.arc([35, 170, 85, 220], start=180, end=360, fill=black, width=line_w)
            draw.arc([315, 170, 365, 220], start=180, end=360, fill=black, width=line_w)

    elif theme == "cat_tea":
        # 奶茶猫猫
        draw.polygon([(110, 95), (145, 35), (175, 85)], fill=(255, 200, 120, 255), outline=black, width=line_w)
        draw.polygon([(290, 95), (255, 35), (225, 85)], fill=(255, 200, 120, 255), outline=black, width=line_w)
        draw.ellipse([100, 60, 300, 240], fill=(255, 245, 230, 255), outline=black, width=line_w)
        draw.ellipse([120, 145, 150, 165], fill=blush)
        draw.ellipse([250, 145, 280, 165], fill=blush)
        draw.arc([140, 120, 180, 150], start=180, end=360, fill=black, width=line_w)
        draw.arc([220, 120, 260, 150], start=180, end=360, fill=black, width=line_w)
        # 奶茶杯
        draw.rectangle([175, 170, 225, 245], fill=(240, 220, 180, 255), outline=black, width=line_w)
        draw.line([(200, 145), (200, 175)], fill=(120, 80, 40, 255), width=line_w)
        draw.text((182, 185), "🧋", fill=black, font=font_large)

    elif theme == "dog_tilt":
        # 柴犬歪头
        draw.ellipse([90, 65, 310, 245], fill=(235, 175, 95, 255), outline=black, width=line_w)
        draw.ellipse([140, 115, 260, 235], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.ellipse([150, 125, 175, 150], fill=black)
        draw.ellipse([225, 125, 250, 150], fill=black)
        draw.polygon([(190, 165), (210, 165), (200, 180)], fill=black)
        draw.text((310, 60), "?", fill=(240, 80, 80, 255), font=font_large)

    elif theme == "doge_smile":
        # 狗头微笑
        draw.ellipse([90, 65, 310, 245], fill=(235, 180, 100, 255), outline=black, width=line_w)
        draw.ellipse([135, 110, 265, 235], fill=(255, 255, 255, 255), outline=black, width=line_w)
        # 狭长笑眼斜视
        draw.arc([145, 120, 180, 150], start=180, end=360, fill=black, width=line_w)
        draw.arc([220, 120, 255, 150], start=180, end=360, fill=black, width=line_w)
        # 弯曲笑嘴
        draw.arc([165, 160, 235, 205], start=0, end=180, fill=black, width=line_w)
        draw.text((185, 80), "🐶", fill=black, font=font_large)

    elif theme == "bear_heart":
        # 小熊比心
        draw.ellipse([80, 45, 140, 105], fill=(180, 130, 90, 255), outline=black, width=line_w)
        draw.ellipse([260, 45, 320, 105], fill=(180, 130, 90, 255), outline=black, width=line_w)
        draw.ellipse([90, 65, 310, 245], fill=(215, 170, 125, 255), outline=black, width=line_w)
        draw.ellipse([140, 115, 160, 135], fill=black)
        draw.ellipse([240, 115, 260, 135], fill=black)
        # 捧爱心
        draw.text((180, 160), "💖", fill=(255, 60, 100, 255), font=font_large)

    elif theme == "cat_stars":
        # 星星眼猫咪
        draw.polygon([(110, 95), (145, 35), (175, 85)], fill=(255, 230, 210, 255), outline=black, width=line_w)
        draw.polygon([(290, 95), (255, 35), (225, 85)], fill=(255, 230, 210, 255), outline=black, width=line_w)
        draw.ellipse([100, 65, 300, 245], fill=(255, 245, 235, 255), outline=black, width=line_w)
        draw.text((135, 110), "✨", fill=(255, 190, 0, 255), font=font_large)
        draw.text((225, 110), "✨", fill=(255, 190, 0, 255), font=font_large)
        draw.arc([185, 165, 215, 195], start=0, end=180, fill=black, width=line_w)

    elif theme == "worker_type":
        # 敲键盘打工人
        draw.ellipse([120, 50, 280, 190], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((185, 95), "💻", fill=black, font=font_large)
        # 键盘与快手残影
        draw.rectangle([130, 195, 270, 250], fill=(220, 225, 235, 255), outline=black, width=line_w)
        draw.text((95, 185), "⚡", fill=(240, 160, 0, 255), font=font_large)
        draw.text((275, 185), "⚡", fill=(240, 160, 0, 255), font=font_large)

    elif theme == "worker_fish":
        # 摸鱼喝茶
        draw.ellipse([120, 50, 280, 190], fill=(255, 255, 255, 255), outline=black, width=line_w)
        # 悠哉闭目
        draw.arc([145, 105, 175, 125], start=180, end=360, fill=black, width=line_w)
        draw.arc([225, 105, 255, 125], start=180, end=360, fill=black, width=line_w)
        # 冒热气茶杯
        draw.text((180, 165), "🍵", fill=black, font=font_large)

    elif theme == "worker_bald":
        # 头秃抓狂
        draw.ellipse([120, 55, 280, 195], fill=(255, 255, 255, 255), outline=black, width=line_w)
        # 稀疏两根毛
        draw.line([(195, 50), (190, 15)], fill=black, width=line_w)
        draw.line([(210, 50), (220, 20)], fill=black, width=line_w)
        # 惊恐圆眼与张嘴
        draw.ellipse([145, 100, 175, 130], fill=black)
        draw.ellipse([225, 100, 255, 130], fill=black)
        draw.ellipse([175, 140, 225, 180], fill=black)

    elif theme == "worker_run":
        # 飞奔下班
        draw.ellipse([130, 45, 270, 175], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 80), "🏃", fill=black, font=font_large)
        # 奔跑风速线
        draw.line([(90, 110), (50, 110)], fill=(120, 140, 160, 255), width=line_w)
        draw.line([(85, 135), (40, 135)], fill=(120, 140, 160, 255), width=line_w)

    elif theme == "sarcasm_melon":
        # 前排吃瓜
        draw.ellipse([120, 50, 280, 190], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 95), "🍉", fill=black, font=font_large)
        draw.arc([145, 100, 175, 125], start=0, end=180, fill=black, width=line_w)
        draw.arc([225, 100, 255, 125], start=0, end=180, fill=black, width=line_w)

    elif theme == "sarcasm_roll":
        # 翻大白眼
        draw.ellipse([110, 50, 290, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.ellipse([135, 95, 175, 135], fill=black)
        draw.ellipse([225, 95, 265, 135], fill=black)
        # 眼珠向上翻
        draw.ellipse([145, 98, 165, 118], fill=(255, 255, 255, 255))
        draw.ellipse([235, 98, 255, 118], fill=(255, 255, 255, 255))
        # 撇嘴
        draw.arc([175, 175, 225, 210], start=180, end=360, fill=black, width=line_w)

    elif theme == "classic_salute":
        # 抱拳拜谢
        draw.ellipse([120, 50, 280, 190], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 145), "🙏", fill=black, font=font_large)

    else:
        # 通用兜底
        draw.ellipse([120, 50, 280, 190], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 95), "✨", fill=black, font=font_large)

    # 底部 y=250 ~ 390 保持绝对纯净白底，供添加自定义文字
    file_name = f"{item['id']}.png"
    save_path = out_dir / file_name
    img.save(str(save_path), "PNG")

    # 生成缩略图
    thumb_name = f"{item['id']}_thumb.png"
    thumb_path = out_dir / thumb_name
    thumb = img.resize((160, 160), Image.Resampling.LANCZOS)
    thumb.save(str(thumb_path), "PNG")

    return f"/static/meme_templates/{file_name}", f"/static/meme_templates/{thumb_name}"


def generate_all():
    out_dir = Path("backend/static/meme_templates")
    out_dir.mkdir(parents=True, exist_ok=True)
    font_path = "backend/static/fonts/NotoSansSC-Bold.ttf"

    print(f"Generating {len(BLANK_MEME_TEMPLATES)} blank meme templates...")
    for item in BLANK_MEME_TEMPLATES:
        url, thumb_url = draw_blank_template(item, out_dir, font_path)
        item["image_url"] = url
        item["thumb_url"] = thumb_url
        print(f"Created: {item['id']} -> {url}")

    # 保存元数据 json 供直接快速载入
    meta_path = out_dir / "templates.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(BLANK_MEME_TEMPLATES, f, ensure_ascii=False, indent=2)
    print(f"Saved meta to {meta_path}")


if __name__ == "__main__":
    generate_all()
