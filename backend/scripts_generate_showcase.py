import asyncio
import io
import base64
import os
import sys
from pathlib import Path
from PIL import Image
import httpx

# 添加 backend 目录到 path
sys.path.insert(0, "/root/02project/weixinpy310mememiniapp/backend")

from app.config import settings
from app.core.sprite_processor import SpriteProcessor
from app.api.meme import PROMPT_TEMPLATES
from app.database import get_db

SHOWCASE_TASKS = [
    # 1. 飞吻示爱
    {
        "col_id": "col_tpl_kiss",
        "task_id": "showcase_kiss_1",
        "action_type": "kiss",
        "char_desc": "超萌粉发双马尾Q版美少女",
        "caption": "么么哒",
        "ref_image": "storage/samples/ref_kiss.png",
        "custom_action": ""
    },
    {
        "col_id": "col_tpl_kiss",
        "task_id": "showcase_kiss_2",
        "action_type": "kiss",
        "char_desc": "超萌粉发双马尾Q版美少女",
        "caption": "想你了",
        "ref_image": "storage/samples/ref_kiss.png",
        "custom_action": ""
    },
    # 2. Q版战斗暴击
    {
        "col_id": "col_tpl_battle",
        "task_id": "showcase_battle_1",
        "action_type": "battle_chibi",
        "char_desc": "热血空手道格斗少年街机少年",
        "caption": "吃我一拳",
        "ref_image": "storage/samples/ref_battle.png",
        "custom_action": ""
    },
    {
        "col_id": "col_tpl_battle",
        "task_id": "showcase_battle_2",
        "action_type": "battle_chibi",
        "char_desc": "热血空手道格斗少年街机少年",
        "caption": "重拳出击",
        "ref_image": "storage/samples/ref_battle.png",
        "custom_action": ""
    },
    # 3. 打工人摸鱼
    {
        "col_id": "col_tpl_worker",
        "task_id": "showcase_worker_1",
        "action_type": "slack_worker",
        "char_desc": "戴眼镜打领带的可爱上班族橘猫",
        "caption": "疯狂敲键盘",
        "ref_image": "storage/samples/ref_worker.png",
        "custom_action": ""
    },
    {
        "col_id": "col_tpl_worker",
        "task_id": "showcase_worker_2",
        "action_type": "slack_worker",
        "char_desc": "戴眼镜打领带的可爱上班族橘猫",
        "caption": "准点下班",
        "ref_image": "storage/samples/ref_worker.png",
        "custom_action": ""
    },
    # 4. 萌宠呆萌待机
    {
        "col_id": "col_tpl_pet",
        "task_id": "showcase_pet_1",
        "action_type": "pet_idle",
        "char_desc": "纯白毛茸茸蓝眼睛小奶猫",
        "caption": "乖巧等待",
        "ref_image": "storage/samples/ref_pet.png",
        "custom_action": ""
    },
    {
        "col_id": "col_tpl_pet",
        "task_id": "showcase_pet_2",
        "action_type": "pet_idle",
        "char_desc": "纯白毛茸茸蓝眼睛小奶猫",
        "caption": "求抱抱",
        "ref_image": "storage/samples/ref_pet.png",
        "custom_action": ""
    },
    # 5. 魔性比心摇摆
    {
        "col_id": "col_tpl_dance",
        "task_id": "showcase_dance_1",
        "action_type": "heart_dance",
        "char_desc": "戴墨镜穿红球鞋的搞怪小黄鸭",
        "caption": "魔性比心",
        "ref_image": "storage/samples/ref_dance.png",
        "custom_action": ""
    },
    {
        "col_id": "col_tpl_dance",
        "task_id": "showcase_dance_2",
        "action_type": "heart_dance",
        "char_desc": "戴墨镜穿红球鞋的搞怪小黄鸭",
        "caption": "快乐摇摆",
        "ref_image": "storage/samples/ref_dance.png",
        "custom_action": ""
    },
    # 6. 自由创意自定义动作
    {
        "col_id": "col_tpl_custom",
        "task_id": "showcase_custom_1",
        "action_type": "custom",
        "char_desc": "头顶小橘子的呆萌治愈水豚卡皮巴拉",
        "caption": "心如止水",
        "ref_image": "storage/samples/ref_custom.png",
        "custom_action": "悠闲地泡在热气腾腾的温泉里，头顶小橘子微笑着闭目养神"
    },
    {
        "col_id": "col_tpl_custom",
        "task_id": "showcase_custom_2",
        "action_type": "custom",
        "char_desc": "头顶小橘子的呆萌治愈水豚卡皮巴拉",
        "caption": "疯狂比赞",
        "ref_image": "storage/samples/ref_custom.png",
        "custom_action": "两只小爪爪竖起大拇指疯狂点赞并冒出开心小星星"
    }
]

async def generate_single_showcase(item_cfg: dict, sem: asyncio.Semaphore):
    async with sem:
        task_id = item_cfg["task_id"]
        out_dir = settings.OUTPUT_DIR / task_id
        gif_file = out_dir / "meme_result.gif"
        thumb_file = out_dir / "thumb.jpg"

        if gif_file.exists() and thumb_file.exists() and gif_file.stat().st_size > 10000:
            print(f"[{task_id}] Already exists, skipping generation.")
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{task_id}] Starting generation: {item_cfg['action_type']} - {item_cfg['caption']}...")

        tpl = next(t for t in PROMPT_TEMPLATES if t["id"] == item_cfg["action_type"])
        ref_path = Path("/root/02project/weixinpy310mememiniapp/backend") / item_cfg["ref_image"]
        has_ref = ref_path.exists()
        prompt = tpl["prompt_builder"](item_cfg["char_desc"], item_cfg["caption"], has_ref, False, item_cfg.get("custom_action", ""))

        headers = {"Authorization": f"Bearer {settings.CPA_API_KEY}"}

        source_image = None
        input_sprite_file = out_dir / "input_sprite.png"
        if input_sprite_file.exists() and input_sprite_file.stat().st_size > 50000:
            print(f"[{task_id}] Found existing input_sprite.png, slicing directly...")
            source_image = Image.open(input_sprite_file).convert("RGB")
        else:
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=150.0) as client:
                        if has_ref:
                            ref_im = Image.open(ref_path).convert("RGBA")
                            buf = io.BytesIO()
                            ref_im.save(buf, format="PNG")
                            buf.seek(0)
                            files = {"image": ("character.png", buf.getvalue(), "image/png")}
                            data = {
                                "model": settings.CPA_IMAGE_MODEL,
                                "prompt": prompt,
                                "n": "1",
                                "size": "1024x1024"
                            }
                            resp = await client.post(f"{settings.CPA_API_BASE}/images/edits", headers=headers, data=data, files=files)
                        else:
                            payload = {
                                "model": settings.CPA_IMAGE_MODEL,
                                "prompt": prompt,
                                "n": 1,
                                "size": "1024x1024"
                            }
                            resp = await client.post(f"{settings.CPA_API_BASE}/images/generations", headers={**headers, "Content-Type": "application/json"}, json=payload)

                        if resp.status_code == 200:
                            res_json = resp.json()
                            item = res_json.get("data", [{}])[0]
                            if "b64_json" in item:
                                img_bytes = base64.b64decode(item["b64_json"])
                                source_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                                break
                            elif "url" in item:
                                img_res = await client.get(item["url"])
                                source_image = Image.open(io.BytesIO(img_res.content)).convert("RGB")
                                break
                        else:
                            print(f"[{task_id}] Attempt {attempt+1} failed: {resp.status_code} {resp.text[:100]}")
                            await asyncio.sleep(2)
                except Exception as e:
                    print(f"[{task_id}] Attempt {attempt+1} exception: {e}")
                    await asyncio.sleep(2)

        if source_image is None:
            print(f"[{task_id}] Generation failed after 3 attempts!")
            return

        # 保存原始 16 宫格大图
        source_image.save(out_dir / "input_sprite.png", format="PNG")

        # 切片提取 16 帧
        frames = SpriteProcessor.slice_grid(source_image, 4, 4, padding_percent=2.5)
        frames_dir = out_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        for idx, f in enumerate(frames, 1):
            f_clean = SpriteProcessor.remove_white_bg(f)
            f_clean.save(frames_dir / f"frame_{idx:02d}.png", format="PNG")

        # 打包 zip
        SpriteProcessor.package_zip(frames, str(out_dir / "frames_pack.zip"), make_transparent=True)

        # 合成最终透明动图 GIF
        SpriteProcessor.assemble_gif(frames, str(gif_file), fps=8, make_transparent=True)

        # 生成 7KB 极速缩略图 thumb.jpg
        frames[0].convert("RGB").resize((160, 160), Image.Resampling.LANCZOS).save(thumb_file, format="JPEG", quality=80)
        print(f"[{task_id}] Successfully generated GIF ({round(gif_file.stat().st_size/1024, 1)} KB) and thumbnail!")

async def main():
    sem = asyncio.Semaphore(2)  # 并发限制为 2
    tasks = [generate_single_showcase(item, sem) for item in SHOWCASE_TASKS]
    await asyncio.gather(*tasks)

    # 全部生成完成后，更新数据库官方合集
    print("\nUpdating database official collections...")
    collections_data = [
        (
            "col_tpl_kiss",
            "official",
            "💖 飞吻示爱 · 甜心萌动合集",
            "基于模板【飞吻示爱】专属动作拆解，超甜飞吻、爱心波波连贯动图",
            "/outputs/showcase_kiss_1/thumb.jpg",
            1,
            [
                ("/outputs/showcase_kiss_1/meme_result.gif", "么么哒"),
                ("/outputs/showcase_kiss_2/meme_result.gif", "想你了")
            ]
        ),
        (
            "col_tpl_battle",
            "official",
            "⚡ Q版暴击 · 连击热血合集",
            "基于模板【Q版战斗暴击】街机风动作拆解，蓄力重拳与打击感动图",
            "/outputs/showcase_battle_1/thumb.jpg",
            1,
            [
                ("/outputs/showcase_battle_1/meme_result.gif", "吃我一拳"),
                ("/outputs/showcase_battle_2/meme_result.gif", "重拳出击")
            ]
        ),
        (
            "col_tpl_worker",
            "official",
            "💼 职场摸鱼 · 打工人神图合集",
            "基于模板【打工人摸鱼日常】职场共鸣动作拆解，疯狂敲键盘与偷闲神作",
            "/outputs/showcase_worker_1/thumb.jpg",
            1,
            [
                ("/outputs/showcase_worker_1/meme_result.gif", "疯狂敲键盘"),
                ("/outputs/showcase_worker_2/meme_result.gif", "准点下班")
            ]
        ),
        (
            "col_tpl_pet",
            "official",
            "🐾 治愈萌宠 · 呆萌待机合集",
            "基于模板【萌宠呆萌待机】无缝呼吸微动图，眨眼晃耳朵萌翻全场",
            "/outputs/showcase_pet_1/thumb.jpg",
            1,
            [
                ("/outputs/showcase_pet_1/meme_result.gif", "乖巧等待"),
                ("/outputs/showcase_pet_2/meme_result.gif", "求抱抱")
            ]
        ),
        (
            "col_tpl_dance",
            "official",
            "🕺 魔性摇摆 · 比心蹦迪合集",
            "基于模板【魔性比心摇摆舞】左右律动魔性变出爱心，聊天斗图炸场",
            "/outputs/showcase_dance_1/thumb.jpg",
            1,
            [
                ("/outputs/showcase_dance_1/meme_result.gif", "魔性比心"),
                ("/outputs/showcase_dance_2/meme_result.gif", "快乐摇摆")
            ]
        ),
        (
            "col_tpl_custom",
            "official",
            "✨ 自由创意 · 自定义动作合集",
            "使用【自定义动作模板】生成的专属个性创意动图",
            "/outputs/showcase_custom_1/thumb.jpg",
            1,
            [
                ("/outputs/showcase_custom_1/meme_result.gif", "心如止水"),
                ("/outputs/showcase_custom_2/meme_result.gif", "疯狂比赞")
            ]
        )
    ]

    with get_db() as conn:
        c = conn.cursor()
        for col_id, openid, title, desc, cover, is_pub, items in collections_data:
            c.execute('''
                INSERT INTO collections (collection_id, openid, title, description, cover_url, is_public)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    cover_url=excluded.cover_url,
                    is_public=excluded.is_public
            ''', (col_id, openid, title, desc, cover, is_pub))

            c.execute("DELETE FROM collection_items WHERE collection_id = ?", (col_id,))
            for idx, (gif_url, item_title) in enumerate(items, 1):
                c.execute('''
                    INSERT INTO collection_items (collection_id, gif_url, title, sort_order)
                    VALUES (?, ?, ?, ?)
                ''', (col_id, gif_url, item_title, idx))

        conn.commit()
    print("\n✅ All 6 official collections refreshed in SQLite with at least 2 memes each!")

if __name__ == "__main__":
    asyncio.run(main())
