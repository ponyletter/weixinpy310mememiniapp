import json
from pathlib import Path
from typing import Dict, List, Any, Optional

CHINESEBQB_CDN_BASE = "https://zhaoolee.com/ChineseBQB/"

class ChineseBQBService:
    _instance = None
    _categories: List[Dict[str, Any]] = []
    _items: List[Dict[str, Any]] = []
    _loaded: bool = False

    @classmethod
    def _ensure_loaded(cls):
        if cls._loaded:
            return

        idx_path = Path(__file__).resolve().parent.parent.parent / "data" / "chinesebqb" / "catalog_index.json"
        search_path = Path(__file__).resolve().parent.parent.parent / "data" / "chinesebqb" / "catalog_search.json"

        if idx_path.exists() and search_path.exists():
            try:
                with open(idx_path, "r", encoding="utf-8") as f:
                    cat_data = json.load(f)
                with open(search_path, "r", encoding="utf-8") as f:
                    items_data = json.load(f)

                # 格式化分类
                raw_cats = cat_data.get("categories", [])
                
                # 热门精选分类置顶
                priority_slugs = [
                    "bqb-015",  # Panda金馆长熊猫
                    "collection-0230fa1082ee", # 斗图之王
                    "bqb-001",  # 滑稽大佬
                    "bqb-010",  # 是喵星人啦
                    "bqb-011",  # 狗
                    "bqb-034",  # 白色小人
                    "bqb-004",  # 假笑男孩
                    "bqb-009",  # 熊本熊
                    "bqb-024",  # 程序员
                    "bqb-021",  # 同福客栈
                    "bqb-035",  # 猫和老鼠
                ]
                
                curated = []
                other = []
                for c in raw_cats:
                    slug = c.get("slug", "")
                    cat_info = {
                        "id": slug,
                        "title": c.get("title", ""),
                        "count": c.get("count", 0),
                        "folder": c.get("folder", "")
                    }
                    if slug in priority_slugs:
                        curated.append(cat_info)
                    else:
                        other.append(cat_info)

                # 按优先级排序置顶分类
                curated.sort(key=lambda x: priority_slugs.index(x["id"]) if x["id"] in priority_slugs else 999)
                cls._categories = curated + other

                # 格式化全部表情条目
                cls._items = []
                for it in items_data:
                    src = it.get("src", "")
                    thumb = it.get("thumb", src)
                    cls._items.append({
                        "id": it.get("id", ""),
                        "title": it.get("label") or it.get("name", "").split(".")[0],
                        "name": it.get("name", ""),
                        "category_id": it.get("category", ""),
                        "category_title": it.get("categoryTitle", ""),
                        "folder": it.get("folder", ""),
                        "url": CHINESEBQB_CDN_BASE + src if not src.startswith("http") else src,
                        "thumb_url": CHINESEBQB_CDN_BASE + thumb if not thumb.startswith("http") else thumb,
                        "width": it.get("width", 256),
                        "height": it.get("height", 256),
                        "animated": it.get("animated", False)
                    })

                cls._loaded = True
                print(f"[ChineseBQB] Ingested {len(cls._categories)} categories and {len(cls._items)} memes successfully.")
            except Exception as e:
                print(f"[ChineseBQB] Failed to load data: {e}")

    @classmethod
    def get_categories(cls) -> List[Dict[str, Any]]:
        cls._ensure_loaded()
        total_count = len(cls._items)
        res = [{"id": "all", "title": "🌟 全部精选", "count": total_count}]
        res.extend(cls._categories)
        return res

    @classmethod
    def get_materials(cls, category: str = "all", page: int = 1, page_size: int = 24) -> Dict[str, Any]:
        cls._ensure_loaded()
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        if not category or category == "all":
            matched = cls._items
        else:
            matched = [it for it in cls._items if it["category_id"] == category or category in it["category_title"]]

        total = len(matched)
        start = (page - 1) * page_size
        end = start + page_size
        items = matched[start:end]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": end < total
        }

    @classmethod
    def search_materials(cls, query: str, category: Optional[str] = None, page: int = 1, page_size: int = 24) -> Dict[str, Any]:
        cls._ensure_loaded()
        q = (query or "").strip().lower()
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        if not q:
            return cls.get_materials(category or "all", page, page_size)

        matched = []
        for it in cls._items:
            if category and category != "all":
                if it["category_id"] != category and category not in it["category_title"]:
                    continue
            # 匹配分类名、标签、文件夹或文件标题
            if (q in it["title"].lower() or 
                q in it["category_title"].lower() or 
                q in it["folder"].lower() or 
                q in it["name"].lower()):
                matched.append(it)

        total = len(matched)
        start = (page - 1) * page_size
        end = start + page_size
        items = matched[start:end]

        return {
            "query": query,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": end < total
        }
