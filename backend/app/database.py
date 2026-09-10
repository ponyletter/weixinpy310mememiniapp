import os
import sqlite3
import datetime
import time
import uuid
from typing import Optional, List, Dict, Any
from app.config import settings

def get_db():
    db_path = settings.DATABASE_PATH
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                openid TEXT PRIMARY KEY,
                nickname TEXT DEFAULT '微信用户',
                avatar_url TEXT DEFAULT '',
                session_key TEXT DEFAULT '',
                free_quota INTEGER DEFAULT 10,
                purchased_quota INTEGER DEFAULT 0,
                total_generated INTEGER DEFAULT 0,
                invite_code TEXT UNIQUE,
                invited_by TEXT DEFAULT '',
                last_checkin_date TEXT DEFAULT '',
                is_vip INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. 道具/充值档位包表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS packages (
                package_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                quota INTEGER NOT NULL,
                is_vip INTEGER DEFAULT 0,
                badge_text TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # 3. 订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                openid TEXT NOT NULL,
                package_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                quota_reward INTEGER NOT NULL,
                status TEXT DEFAULT 'PENDING',
                wx_order_id TEXT DEFAULT '',
                pay_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 4. 兑换码表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                reward_quota INTEGER NOT NULL,
                used_count INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 999999,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # 5. 用户兑换记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coupon_redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openid TEXT NOT NULL,
                code TEXT NOT NULL,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(openid, code)
            )
        ''')

        # 6. 表情包生成任务记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meme_tasks (
                task_id TEXT PRIMARY KEY,
                openid TEXT DEFAULT '',
                prompt TEXT DEFAULT '',
                preset_key TEXT DEFAULT '',
                text_bottom TEXT DEFAULT '',
                fps INTEGER DEFAULT 8,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                gif_url TEXT DEFAULT '',
                sprite_url TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 7. 表情包合集表 (支持微信群分享与分类管理)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                collection_id TEXT PRIMARY KEY,
                openid TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                cover_url TEXT DEFAULT '',
                is_public INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 8. 合集条目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id TEXT NOT NULL,
                gif_url TEXT NOT NULL,
                title TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 预置三大极简黄金道具 (低同行80%以上)
        default_packages = [
            ("item_100", "动图制作尝鲜包1元", "尝鲜包 (20次)", 100, 20, 0, "超低破冰", 1),
            ("item_500", "动图制作超值包5元", "超值包 (120次)", 500, 120, 0, "爆款推荐", 2),
            ("item_990", "动图制作尊享包9元9", "尊享包 (300次/VIP)", 990, 300, 1, "年度特惠", 3),
        ]
        for pkg_id, title, name, price, quota, is_vip, badge, sort_order in default_packages:
            cursor.execute('''
                INSERT INTO packages (package_id, title, name, price, quota, is_vip, badge_text, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET
                    title=excluded.title,
                    name=excluded.name,
                    price=excluded.price,
                    quota=excluded.quota,
                    is_vip=excluded.is_vip,
                    badge_text=excluded.badge_text,
                    sort_order=excluded.sort_order
            ''', (pkg_id, title, name, price, quota, is_vip, badge, sort_order))

        # 预置默认兑换码
        default_coupons = [
            ("MEME888", "创作者起航大礼包 (送10次生成额度)", 10),
            ("VIP2026", "年度VIP专属福利包 (送50次生成额度)", 50),
            ("FREE2026", "公测无门槛特惠包 (送5次生成额度)", 5),
        ]
        for code, title, reward in default_coupons:
            cursor.execute('''
                INSERT INTO coupons (code, title, reward_quota)
                VALUES (?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    title=excluded.title,
                    reward_quota=excluded.reward_quota
            ''', (code, title, reward))

        conn.commit()

# --- 用户管理 ---

def get_or_create_user(openid: str, session_key: str = "", inviter_code: str = "") -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        if not row:
            invite_code = f"M{uuid.uuid4().hex[:7].upper()}"
            invited_by = ""
            if inviter_code:
                cursor.execute("SELECT openid FROM users WHERE invite_code = ?", (inviter_code,))
                inviter = cursor.fetchone()
                if inviter and inviter[0] != openid:
                    invited_by = inviter[0]
                    # 给邀请人增加 5 次分享奖励
                    cursor.execute("UPDATE users SET free_quota = free_quota + 5 WHERE openid = ?", (inviter[0],))

            cursor.execute('''
                INSERT INTO users (openid, session_key, invite_code, invited_by, free_quota, last_login)
                VALUES (?, ?, ?, ?, 10, CURRENT_TIMESTAMP)
            ''', (openid, session_key, invite_code, invited_by))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE openid = ?", (openid,))
            row = cursor.fetchone()
        else:
            updates = ["last_login = CURRENT_TIMESTAMP"]
            params = []
            if session_key:
                updates.append("session_key = ?")
                params.append(session_key)
            params.append(openid)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE openid = ?", params)
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE openid = ?", (openid,))
            row = cursor.fetchone()

        return dict(row)

def get_user(openid: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_session_key(openid: str) -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_key FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        return row[0] if row and row[0] else ""

def update_user_profile(openid: str, nickname: str, avatar_url: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET nickname = ?, avatar_url = ? WHERE openid = ?", (nickname, avatar_url, openid))
        conn.commit()
        return cursor.rowcount > 0

def user_daily_checkin(openid: str) -> Dict[str, Any]:
    """每日签到领取 3 次生成额度"""
    today_str = datetime.date.today().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_checkin_date, free_quota, purchased_quota FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "用户不存在"}
        last_date = row[0]
        if last_date == today_str:
            return {
                "success": False, 
                "error": "今日已完成签到，明天再来领取吧！",
                "remaining_quota": (row[1] + row[2])
            }
        
        cursor.execute('''
            UPDATE users SET 
                free_quota = free_quota + 3,
                last_checkin_date = ?
            WHERE openid = ?
        ''', (today_str, openid))
        conn.commit()
        return {
            "success": True,
            "reward": 3,
            "message": "签到成功，已到账 3 次动图制作额度！",
            "remaining_quota": (row[1] + row[2] + 3)
        }

def redeem_coupon(openid: str, code: str) -> Dict[str, Any]:
    code = code.strip().upper()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM coupons WHERE code = ? AND is_active = 1", (code,))
        coupon = cursor.fetchone()
        if not coupon:
            return {"success": False, "error": "兑换码不存在或已失效"}
        
        cursor.execute("SELECT id FROM coupon_redemptions WHERE openid = ? AND code = ?", (openid, code))
        if cursor.fetchone():
            return {"success": False, "error": "您已经兑换过此兑换码，不可重复使用"}

        reward = coupon['reward_quota']
        cursor.execute("INSERT INTO coupon_redemptions (openid, code) VALUES (?, ?)", (openid, code))
        cursor.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = ?", (code,))
        cursor.execute("UPDATE users SET purchased_quota = purchased_quota + ? WHERE openid = ?", (reward, openid))
        conn.commit()

        user = get_user(openid)
        total = (user['free_quota'] + user['purchased_quota']) if user else reward
        return {
            "success": True,
            "reward_quota": reward,
            "message": f"兑换成功！已获得 {reward} 次生成额度",
            "remaining_quota": total
        }

def check_and_deduct_quota(openid: str) -> Dict[str, Any]:
    """扣减 1 次制作额度 (优先扣免费，再扣购买)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT free_quota, purchased_quota, is_vip, total_generated FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        if not row:
            # 临时/未登录用户默认允许生成（开发模式兼容）
            return {"allowed": True, "remaining_quota": 999}
        
        free_q, paid_q, is_vip, total_gen = row[0], row[1], row[2], row[3]
        if is_vip:
            cursor.execute("UPDATE users SET total_generated = total_generated + 1 WHERE openid = ?", (openid,))
            conn.commit()
            return {"allowed": True, "is_vip": True, "remaining_quota": 999}

        if free_q > 0:
            cursor.execute("UPDATE users SET free_quota = free_quota - 1, total_generated = total_generated + 1 WHERE openid = ?", (openid,))
            conn.commit()
            return {"allowed": True, "remaining_quota": (free_q - 1 + paid_q)}
        elif paid_q > 0:
            cursor.execute("UPDATE users SET purchased_quota = purchased_quota - 1, total_generated = total_generated + 1 WHERE openid = ?", (openid,))
            conn.commit()
            return {"allowed": True, "remaining_quota": (paid_q - 1)}
        else:
            return {"allowed": False, "remaining_quota": 0, "error": "可用制作次数已耗尽，请签到领取或开通超值尝鲜包！"}

def refund_quota(openid: str):
    """若生成失败，自动返还 1 次额度"""
    if not openid:
        return
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET free_quota = free_quota + 1 WHERE openid = ?", (openid,))
        conn.commit()

# --- 道具与订单 ---

def get_packages() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packages WHERE is_active = 1 ORDER BY sort_order ASC")
        return [dict(r) for r in cursor.fetchall()]

def get_package_by_id(pkg_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packages WHERE package_id = ?", (pkg_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_order_record(order_id: str, openid: str, package_id: str, amount: int, quota_reward: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (order_id, openid, package_id, amount, quota_reward, status)
            VALUES (?, ?, ?, ?, ?, 'PENDING')
        ''', (order_id, openid, package_id, amount, quota_reward))
        conn.commit()

def mark_order_paid(order_id: str, wx_order_id: str = "") -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            return False
        if order['status'] == 'PAID':
            return True

        cursor.execute('''
            UPDATE orders SET status = 'PAID', wx_order_id = ?, pay_time = CURRENT_TIMESTAMP
            WHERE order_id = ?
        ''', (wx_order_id, order_id))

        openid = order['openid']
        quota_reward = order['quota_reward']
        pkg_id = order['package_id']
        is_vip_pkg = 1 if pkg_id == 'item_990' else 0

        cursor.execute('''
            UPDATE users SET 
                purchased_quota = purchased_quota + ?,
                is_vip = CASE WHEN ? = 1 THEN 1 ELSE is_vip END
            WHERE openid = ?
        ''', (quota_reward, is_vip_pkg, openid))

        conn.commit()
        return True

def get_user_orders(openid: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, p.title as package_title
            FROM orders o
            LEFT JOIN packages p ON o.package_id = p.package_id
            WHERE o.openid = ?
            ORDER BY o.created_at DESC
        ''', (openid,))
        return [dict(r) for r in cursor.fetchall()]

# --- 表情包合集管理 (Collections) ---

def create_collection(openid: str, title: str, description: str = "", cover_url: str = "") -> Dict[str, Any]:
    collection_id = f"col_{uuid.uuid4().hex[:8]}"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO collections (collection_id, openid, title, description, cover_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (collection_id, openid, title, description, cover_url))
        conn.commit()
    return get_collection_detail(collection_id)

def add_item_to_collection(collection_id: str, gif_url: str, title: str = "") -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO collection_items (collection_id, gif_url, title)
            VALUES (?, ?, ?)
        ''', (collection_id, gif_url, title))
        item_id = cursor.lastrowid
        # 若合集尚未设置封面，自动将首个表情包设为封面
        cursor.execute('''
            UPDATE collections 
            SET cover_url = CASE WHEN cover_url = '' THEN ? ELSE cover_url END
            WHERE collection_id = ?
        ''', (gif_url, collection_id))
        conn.commit()
    return {"id": item_id, "collection_id": collection_id, "gif_url": gif_url, "title": title}

def get_collection_detail(collection_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        # 增加浏览次数
        cursor.execute("UPDATE collections SET view_count = view_count + 1 WHERE collection_id = ?", (collection_id,))
        conn.commit()
        
        cursor.execute("SELECT * FROM collections WHERE collection_id = ?", (collection_id,))
        col_row = cursor.fetchone()
        if not col_row:
            return None
        col = dict(col_row)

        cursor.execute("SELECT id, gif_url, title, sort_order, created_at FROM collection_items WHERE collection_id = ? ORDER BY sort_order ASC, id ASC", (collection_id,))
        items = [dict(r) for r in cursor.fetchall()]
        col["items"] = items
        col["item_count"] = len(items)
        return col

def get_user_collections(openid: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, COUNT(ci.id) as item_count
            FROM collections c
            LEFT JOIN collection_items ci ON c.collection_id = ci.collection_id
            WHERE c.openid = ?
            GROUP BY c.collection_id
            ORDER BY c.created_at DESC
        ''', (openid,))
        return [dict(r) for r in cursor.fetchall()]

def get_public_collections(limit: int = 15) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, COUNT(ci.id) as item_count
            FROM collections c
            LEFT JOIN collection_items ci ON c.collection_id = ci.collection_id
            WHERE c.is_public = 1
            GROUP BY c.collection_id
            ORDER BY c.view_count DESC, c.created_at DESC
            LIMIT ?
        ''', (limit,))
        return [dict(r) for r in cursor.fetchall()]
