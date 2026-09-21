import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

MATERIALS = [
    # 1. 搞笑/熊猫头
    {
        "id": "mat_funny_01",
        "category": "funny",
        "title": "熊猫头 · 满脸问号",
        "tags": ["熊猫头", "问号", "懵逼"],
        "bg_color": (255, 255, 255, 255),
        "theme": "panda_question"
    },
    {
        "id": "mat_funny_02",
        "category": "funny",
        "title": "熊猫头 · 暗中观察",
        "tags": ["熊猫头", "偷看", "观察"],
        "bg_color": (255, 255, 255, 255),
        "theme": "panda_peek"
    },
    {
        "id": "mat_funny_03",
        "category": "funny",
        "title": "熊猫头 · 点赞大笑",
        "tags": ["熊猫头", "点赞", "好评"],
        "bg_color": (255, 255, 255, 255),
        "theme": "panda_thumb"
    },
    {
        "id": "mat_funny_04",
        "category": "funny",
        "title": "熊猫头 · 我裂开了",
        "tags": ["熊猫头", "崩溃", "裂开"],
        "bg_color": (255, 255, 255, 255),
        "theme": "panda_break"
    },
    {
        "id": "mat_funny_05",
        "category": "funny",
        "title": "熊猫头 · 战术后仰",
        "tags": ["熊猫头", "后仰", "震惊"],
        "bg_color": (255, 255, 255, 255),
        "theme": "panda_lean"
    },
    {
        "id": "mat_funny_06",
        "category": "funny",
        "title": "熊猫头 · 猛男落泪",
        "tags": ["熊猫头", "大哭", "扎心"],
        "bg_color": (255, 255, 255, 255),
        "theme": "panda_cry"
    },

    # 2. 萌宠可爱
    {
        "id": "mat_cute_01",
        "category": "cute",
        "title": "奶茶猫猫 · 咕嘟咕嘟",
        "tags": ["猫咪", "奶茶", "可爱"],
        "bg_color": (255, 255, 255, 255),
        "theme": "cat_tea"
    },
    {
        "id": "mat_cute_02",
        "category": "cute",
        "title": "歪头柴犬 · 眼神清澈",
        "tags": ["柴犬", "萌宠", "疑惑"],
        "bg_color": (255, 255, 255, 255),
        "theme": "dog_tilt"
    },
    {
        "id": "mat_cute_03",
        "category": "cute",
        "title": "贴贴小熊 · 么么哒",
        "tags": ["小熊", "比心", "贴贴"],
        "bg_color": (255, 255, 255, 255),
        "theme": "bear_heart"
    },
    {
        "id": "mat_cute_04",
        "category": "cute",
        "title": "星星眼猫咪 · 哇塞",
        "tags": ["猫咪", "崇拜", "星星眼"],
        "bg_color": (255, 255, 255, 255),
        "theme": "cat_stars"
    },

    # 3. 打工人日常
    {
        "id": "mat_worker_01",
        "category": "worker",
        "title": "疯狂搬砖 · 敲出火花",
        "tags": ["打工人", "加班", "敲键盘"],
        "bg_color": (255, 255, 255, 255),
        "theme": "worker_type"
    },
    {
        "id": "mat_worker_02",
        "category": "worker",
        "title": "摸鱼喝茶 · 心静自然凉",
        "tags": ["打工人", "摸鱼", "喝茶"],
        "bg_color": (255, 255, 255, 255),
        "theme": "worker_fish"
    },
    {
        "id": "mat_worker_03",
        "category": "worker",
        "title": "方案又改了 · 头秃抓狂",
        "tags": ["打工人", "改需求", "头秃"],
        "bg_color": (255, 255, 255, 255),
        "theme": "worker_bald"
    },
    {
        "id": "mat_worker_04",
        "category": "worker",
        "title": "准点下班 · 溜之大吉",
        "tags": ["打工人", "下班", "奔跑"],
        "bg_color": (255, 255, 255, 255),
        "theme": "worker_run"
    },

    # 4. 吐槽斗图
    {
        "id": "mat_sarcasm_01",
        "category": "sarcasm",
        "title": "无语翻白眼 · 累了毁灭吧",
        "tags": ["吐槽", "白眼", "无语"],
        "bg_color": (255, 255, 255, 255),
        "theme": "sarcasm_roll"
    },
    {
        "id": "mat_sarcasm_02",
        "category": "sarcasm",
        "title": "前排吃瓜 · 坐看神仙打架",
        "tags": ["吃瓜", "看戏", "淡定"],
        "bg_color": (255, 255, 255, 255),
        "theme": "sarcasm_melon"
    },
    {
        "id": "mat_sarcasm_03",
        "category": "sarcasm",
        "title": "满脸写着高兴 · 假笑假积极",
        "tags": ["假笑", "敷衍", "斗图"],
        "bg_color": (255, 255, 255, 255),
        "theme": "sarcasm_fakesmile"
    },

    # 5. 经典名场面
    {
        "id": "mat_classic_01",
        "category": "classic",
        "title": "真香警告 · 哎呀真香",
        "tags": ["名场面", "真香", "打脸"],
        "bg_color": (255, 255, 255, 255),
        "theme": "classic_zhenxiang"
    },
    {
        "id": "mat_classic_02",
        "category": "classic",
        "title": "抱拳感谢 · 大佬牛逼",
        "tags": ["抱拳", "感谢", "大佬"],
        "bg_color": (255, 255, 255, 255),
        "theme": "classic_salute"
    }
]


def create_material_image(item: dict, out_dir: Path, font_path: str):
    """绘制高分辨率清晰好看的表情包模板图"""
    size = (400, 400)
    img = Image.new("RGBA", size, item["bg_color"])
    draw = ImageDraw.Draw(img)

    theme = item["theme"]
    cx, cy = 200, 190

    # 默认黑线粗细
    line_w = 4
    black = (30, 30, 30, 255)
    gray = (240, 240, 240, 255)
    blush = (255, 180, 190, 220)

    try:
        font_large = ImageFont.truetype(font_path, 32)
        font_small = ImageFont.truetype(font_path, 20)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    if theme.startswith("panda_"):
        # 绘制经典熊猫头轮廓
        # 耳朵
        draw.ellipse([80, 80, 140, 140], fill=black)
        draw.ellipse([260, 80, 320, 140], fill=black)
        # 头部白底
        draw.ellipse([90, 100, 310, 300], fill=(255, 255, 255, 255), outline=black, width=line_w)

        if theme == "panda_question":
            # 疑惑眼眉毛
            draw.arc([130, 150, 175, 185], start=0, end=180, fill=black, width=line_w)
            draw.arc([225, 140, 270, 175], start=180, end=360, fill=black, width=line_w)
            draw.ellipse([145, 175, 160, 190], fill=black)
            draw.ellipse([240, 165, 255, 180], fill=black)
            # 歪嘴
            draw.arc([180, 220, 220, 250], start=0, end=180, fill=black, width=line_w)
            # 大大的问号
            draw.text((320, 90), "???", fill=(220, 50, 50, 255), font=font_large)

        elif theme == "panda_peek":
            # 眼睛向上瞅
            draw.ellipse([135, 160, 175, 195], fill=black)
            draw.ellipse([225, 160, 265, 195], fill=black)
            draw.ellipse([150, 165, 162, 177], fill=(255, 255, 255, 255))
            draw.ellipse([240, 165, 252, 177], fill=(255, 255, 255, 255))
            # 围墙下半部
            draw.rectangle([60, 250, 340, 320], fill=(230, 230, 240, 255), outline=black, width=line_w)
            draw.text((150, 265), "暗中观察", fill=black, font=font_small)

        elif theme == "panda_thumb":
            # 眯眯笑眼
            draw.arc([130, 165, 175, 195], start=180, end=360, fill=black, width=line_w)
            draw.arc([225, 165, 270, 195], start=180, end=360, fill=black, width=line_w)
            # 大笑嘴
            draw.chord([160, 205, 240, 265], start=0, end=180, fill=(230, 60, 60, 255), outline=black, width=line_w)
            # 大拇指
            draw.ellipse([300, 170, 350, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
            draw.text((310, 180), "👍", fill=black, font=font_large)

        elif theme == "panda_break":
            # 裂痕
            draw.line([(200, 100), (180, 150), (220, 190), (190, 240), (210, 300)], fill=(230, 40, 40, 255), width=line_w)
            # 抓狂白眼
            draw.ellipse([135, 165, 170, 200], fill=black)
            draw.ellipse([230, 165, 265, 200], fill=black)
            draw.text((120, 245), "我裂开了", fill=(200, 30, 30, 255), font=font_large)

        elif theme == "panda_lean":
            # 战术后仰姿态 (椭圆斜向)
            draw.ellipse([130, 160, 175, 200], fill=black)
            draw.ellipse([225, 160, 270, 200], fill=black)
            draw.text((120, 240), "战术后仰!", fill=black, font=font_large)

        elif theme == "panda_cry":
            # 瀑布泪
            draw.rectangle([140, 175, 165, 280], fill=(60, 160, 255, 220), outline=black, width=2)
            draw.rectangle([235, 175, 260, 280], fill=(60, 160, 255, 220), outline=black, width=2)
            draw.text((140, 240), "扎心了", fill=(50, 100, 200, 255), font=font_large)

    elif theme == "cat_tea":
        # 萌猫抱奶茶
        # 猫耳
        draw.polygon([(110, 140), (150, 70), (180, 130)], fill=(255, 200, 120, 255), outline=black, width=line_w)
        draw.polygon([(290, 140), (250, 70), (220, 130)], fill=(255, 200, 120, 255), outline=black, width=line_w)
        # 猫脸
        draw.ellipse([100, 100, 300, 280], fill=(255, 245, 230, 255), outline=black, width=line_w)
        # 腮红
        draw.ellipse([120, 195, 150, 215], fill=blush)
        draw.ellipse([250, 195, 280, 215], fill=blush)
        # 眯眼与猫嘴
        draw.arc([140, 165, 180, 195], start=180, end=360, fill=black, width=line_w)
        draw.arc([220, 165, 260, 195], start=180, end=360, fill=black, width=line_w)
        # 奶茶杯
        draw.rectangle([170, 220, 230, 310], fill=(240, 220, 180, 255), outline=black, width=line_w)
        draw.line([(200, 190), (200, 230)], fill=(120, 80, 40, 255), width=line_w)
        draw.text((180, 240), "🧋", fill=black, font=font_large)

    elif theme == "dog_tilt":
        # 柴犬歪头
        draw.ellipse([90, 110, 310, 290], fill=(235, 175, 95, 255), outline=black, width=line_w)
        draw.ellipse([140, 160, 260, 280], fill=(255, 255, 255, 255), outline=black, width=line_w)
        # 眼睛
        draw.ellipse([150, 170, 175, 195], fill=black)
        draw.ellipse([225, 170, 250, 195], fill=black)
        # 鼻子三角
        draw.polygon([(190, 210), (210, 210), (200, 225)], fill=black)
        # 疑惑红问号
        draw.text((310, 100), "?", fill=(240, 80, 80, 255), font=font_large)

    elif theme == "bear_heart":
        # 贴贴小熊
        draw.ellipse([80, 70, 140, 130], fill=(180, 130, 90, 255), outline=black, width=line_w)
        draw.ellipse([260, 70, 320, 130], fill=(180, 130, 90, 255), outline=black, width=line_w)
        draw.ellipse([90, 90, 310, 280], fill=(215, 170, 125, 255), outline=black, width=line_w)
        # 爱心
        draw.text((180, 210), "💖", fill=(255, 60, 100, 255), font=font_large)
        draw.text((140, 290), "贴贴么么哒", fill=black, font=font_small)

    elif theme == "cat_stars":
        # 星星眼猫咪
        draw.ellipse([100, 110, 300, 280], fill=(255, 245, 235, 255), outline=black, width=line_w)
        draw.text((140, 160), "✨", fill=(255, 200, 0, 255), font=font_large)
        draw.text((225, 160), "✨", fill=(255, 200, 0, 255), font=font_large)
        draw.text((160, 285), "崇拜哇塞", fill=black, font=font_small)

    elif theme == "worker_type":
        # 疯狂敲键盘
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((185, 140), "💻", fill=black, font=font_large)
        draw.rectangle([130, 240, 270, 300], fill=(220, 225, 235, 255), outline=black, width=line_w)
        draw.text((140, 250), "疯狂输出中", fill=(200, 30, 30, 255), font=font_small)

    elif theme == "worker_fish":
        # 摸鱼喝茶
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 130), "🍵", fill=black, font=font_large)
        draw.text((140, 260), "心静自然凉", fill=black, font=font_large)

    elif theme == "worker_bald":
        # 头秃抓狂
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        # 几根稀疏毛发
        draw.line([(200, 80), (195, 40)], fill=black, width=line_w)
        draw.line([(215, 80), (225, 45)], fill=black, width=line_w)
        draw.text((130, 260), "方案又改了?!", fill=(220, 30, 30, 255), font=font_large)

    elif theme == "worker_run":
        # 准点下班
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 130), "🏃", fill=black, font=font_large)
        draw.text((140, 260), "我下班啦溜了", fill=(0, 130, 50, 255), font=font_large)

    elif theme == "sarcasm_melon":
        # 吃瓜
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 130), "🍉", fill=black, font=font_large)
        draw.text((150, 260), "前排吃瓜", fill=black, font=font_large)

    elif theme == "classic_zhenxiang":
        # 真香
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 130), "🍚", fill=black, font=font_large)
        draw.text((140, 260), "哎呀真香!", fill=(220, 80, 0, 255), font=font_large)

    else:
        # 通用兜底
        draw.ellipse([120, 90, 280, 230], fill=(255, 255, 255, 255), outline=black, width=line_w)
        draw.text((180, 130), "✨", fill=black, font=font_large)
        draw.text((150, 260), item["title"].split("·")[-1].strip(), fill=black, font=font_large)

    # 保存图片
    file_name = f"{item['id']}.png"
    save_path = out_dir / file_name
    img.save(str(save_path), "PNG")

    # 生成缩略图
    thumb_path = out_dir / f"{item['id']}_thumb.png"
    thumb = img.resize((160, 160), Image.Resampling.LANCZOS)
    thumb.save(str(thumb_path), "PNG")

    return f"/static/materials/{file_name}", f"/static/materials/{item['id']}_thumb.png"


def main():
    out_dir = Path("backend/static/materials")
    out_dir.mkdir(parents=True, exist_ok=True)
    font_path = "backend/static/fonts/NotoSansSC-Bold.ttf"

    print(f"Generating {len(MATERIALS)} default material images...")
    for item in MATERIALS:
        url, thumb_url = create_material_image(item, out_dir, font_path)
        item["url"] = url
        item["thumb_url"] = thumb_url
        print(f"Created: {item['id']} -> {url}")

    print("All material images generated successfully.")


if __name__ == "__main__":
    main()
