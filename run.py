"""启动脚本 — 一键拉起 Agent API 服务

使用方式:
    python run.py              # 开发模式（热重载）
    python run.py --prod       # 生产模式（无热重载，多 worker）
"""
import sys

import uvicorn

from src.config.settings import settings


def main() -> None:
    """启动 TrafficGraph Agent API 服务。"""
    host = settings.api.host
    port = settings.api.port
    is_prod = "--prod" in sys.argv

    print(f"🚀 TrafficGraph Agent API 启动中...")
    print(f"   地址: http://{host}:{port}")
    print(f"   指挥台: http://{host}:{port}/")
    print(f"   文档: http://{host}:{port}/docs")
    print(f"   模式: {'生产' if is_prod else '开发（热重载）'}")
    if settings.api.api_key:
        print(f"   鉴权: ✅ 已启用 Bearer Token")
    else:
        print(f"   鉴权: ⚠️  未启用（开发模式）")
    print(f"   CORS: {settings.api.cors_origins}")

    uvicorn.run(
        "src.services.api:app",
        host=host,
        port=port,
        reload=not is_prod,
        workers=4 if is_prod else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
