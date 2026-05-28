"""Claude Code 会话历史浏览器 - 入口"""

import sys
import os
import webbrowser
import threading
import time

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import create_server


def open_browser(port):
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")


def main():
    try:
        server, port = create_server(8686)
    except RuntimeError as e:
        print(f"错误: {e}")
        sys.exit(1)

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    print(f"  Claude Code 会话浏览器已启动")
    print(f"  地址: http://localhost:{port}")
    print(f"  按 Ctrl+C 关闭")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已关闭")
        server.shutdown()


if __name__ == "__main__":
    main()
