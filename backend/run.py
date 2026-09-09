import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"🚀 正在启动 {settings.PROJECT_NAME}...")
    print(f"📡 本地访问地址: http://127.0.0.1:{settings.PORT}")
    print(f"🌍 局域网/公网监听: http://{settings.HOST}:{settings.PORT}")
    print(f"📂 存储目录: {settings.STORAGE_DIR}")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
