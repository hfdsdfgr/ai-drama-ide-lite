"""PyInstaller 打包入口：启动 FastAPI 服务，支持 --host / --port 参数。"""

import argparse

import uvicorn

from app.main import app as fastapi_app


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Drama IDE Lite backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(fastapi_app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
