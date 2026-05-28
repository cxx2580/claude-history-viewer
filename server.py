"""HTTP 服务器模块"""

import json
import os
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import data_parser
import launcher

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 缓存
_session_index = None
_projects_cache = None


def _get_session_index():
    global _session_index, _projects_cache
    if _session_index is None:
        _session_index = data_parser.build_session_index()
        _projects_cache = data_parser.get_projects_summary(_session_index)
    return _session_index


def _refresh_cache():
    global _session_index, _projects_cache
    _session_index = None
    _projects_cache = None
    return _get_session_index()


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默日志

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, filepath):
        try:
            with open(filepath, encoding="utf-8") as f:
                body = f.read().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self._send_json({"error": "文件未找到"}, 404)

    def _send_static(self, filepath):
        full_path = os.path.join(BASE_DIR, filepath.lstrip("/"))
        try:
            with open(full_path, "rb") as f:
                body = f.read()
            content_type, _ = mimetypes.guess_type(full_path)
            if content_type is None:
                content_type = "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self._send_json({"error": "静态文件未找到"}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self._send_html(os.path.join(BASE_DIR, "templates", "index.html"))

        elif path.startswith("/static/"):
            self._send_static(path)

        elif path == "/api/projects":
            idx = _get_session_index()
            projects = data_parser.get_projects_summary(idx)
            self._send_json(projects)

        elif path.startswith("/api/session/"):
            sid = path.split("/")[-1]
            idx = _get_session_index()
            session_info = idx.get(sid)
            if not session_info:
                self._send_json({"error": "会话未找到"}, 404)
                return
            transcript = data_parser.parse_session_transcript(session_info["filePath"])
            self._send_json({
                "session": session_info,
                "messages": transcript,
            })

        elif path == "/api/search":
            q = query.get("q", [""])[0]
            if not q.strip():
                self._send_json([])
                return
            results = data_parser.search_sessions(q)
            # 补充会话索引信息
            idx = _get_session_index()
            for r in results:
                info = idx.get(r["sessionId"])
                if info:
                    r["projectName"] = info.get("project", "")
                    r["model"] = info.get("model")
            self._send_json(results)

        elif path == "/api/stats":
            stats = data_parser.get_stats()
            self._send_json(stats)

        elif path == "/api/active":
            active = data_parser.get_active_sessions()
            self._send_json(active)

        elif path == "/api/refresh":
            idx = _refresh_cache()
            projects = data_parser.get_projects_summary(idx)
            self._send_json({"sessionCount": len(idx), "projectCount": len(projects)})

        else:
            self._send_json({"error": "未找到"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/resume/"):
            sid = path.split("/")[-1]
            idx = _get_session_index()
            session_info = idx.get(sid)
            if not session_info:
                self._send_json({"error": "会话未找到"}, 404)
                return
            result = launcher.resume_session(sid, session_info.get("projectPath", ""))
            self._send_json(result)

        else:
            self._send_json({"error": "未找到"}, 404)


def create_server(port=8686):
    """创建并返回 HTTP 服务器。"""
    for p in range(port, port + 10):
        try:
            server = HTTPServer(("127.0.0.1", p), RequestHandler)
            return server, p
        except OSError:
            continue
    raise RuntimeError(f"无法在端口 {port}-{port+9} 启动服务器")
