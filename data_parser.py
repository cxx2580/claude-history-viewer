"""Claude Code 会话数据解析模块"""

import json
import os
from collections import Counter, defaultdict


def get_claude_dir():
    return os.path.join(os.path.expanduser("~"), ".claude")


def build_session_index(claude_dir=None):
    """构建会话索引。返回 {sessionId: {...}} 字典。"""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    projects_dir = os.path.join(claude_dir, "projects")
    history_path = os.path.join(claude_dir, "history.jsonl")

    # 从 history.jsonl 获取消息计数和项目路径映射
    msg_counts = Counter()
    session_projects = {}  # sessionId -> original project path
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    sid = obj.get("sessionId")
                    if sid:
                        msg_counts[sid] += 1
                        if sid not in session_projects:
                            session_projects[sid] = obj.get("project", "")
                except json.JSONDecodeError:
                    continue

    # 获取活跃会话
    active_sessions = get_active_sessions(claude_dir)
    active_sids = {s["sessionId"] for s in active_sessions}

    # 扫描 projects 目录下的所有会话文件
    sessions = {}
    if not os.path.isdir(projects_dir):
        return sessions

    for encoded_name in os.listdir(projects_dir):
        project_path = os.path.join(projects_dir, encoded_name)
        if not os.path.isdir(project_path):
            continue

        for fname in os.listdir(project_path):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(project_path, fname)
            meta = _extract_session_meta(fpath)
            if meta.get("sessionId"):
                sid = meta["sessionId"]
                # 优先用 history.jsonl 里的原始路径
                real_path = session_projects.get(sid, "")
                if not real_path:
                    real_path = meta.get("cwd", encoded_name)

                sessions[sid] = {
                    "sessionId": sid,
                    "project": os.path.basename(real_path) if real_path else encoded_name,
                    "projectPath": real_path,
                    "projectEncoded": encoded_name,
                    "title": meta.get("title", "（无标题）"),
                    "timestamp": meta.get("timestamp"),
                    "model": meta.get("model"),
                    "version": meta.get("version"),
                    "filePath": fpath,
                    "msgCount": msg_counts.get(sid, 0),
                    "isActive": sid in active_sids,
                }

    return sessions


def _extract_session_meta(jsonl_path):
    """从 JSONL 文件前 20 行提取元数据。"""
    meta = {}
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 20:
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not meta.get("sessionId") and obj.get("sessionId"):
                    meta["sessionId"] = obj["sessionId"]
                if not meta.get("timestamp") and obj.get("timestamp"):
                    meta["timestamp"] = obj["timestamp"]
                if not meta.get("cwd") and obj.get("cwd"):
                    meta["cwd"] = obj["cwd"]
                if not meta.get("version") and obj.get("version"):
                    meta["version"] = obj["version"]

                if obj.get("type") == "user":
                    content = obj.get("message", {}).get("content")
                    if isinstance(content, str) and content.strip():
                        if not meta.get("title"):
                            meta["title"] = content[:80].replace("\n", " ")
                        if not meta.get("timestamp"):
                            meta["timestamp"] = obj.get("timestamp")

                if obj.get("type") == "assistant":
                    model = obj.get("message", {}).get("model")
                    if model and not meta.get("model"):
                        meta["model"] = model
    except (OSError, IOError):
        pass
    return meta


def parse_session_transcript(jsonl_path):
    """解析完整会话记录，返回消息列表。"""
    messages = []
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("isSidechain"):
                    continue

                msg_type = obj.get("type")
                ts = obj.get("timestamp")
                uuid = obj.get("uuid")

                if msg_type == "user":
                    content = obj.get("message", {}).get("content")
                    if isinstance(content, str) and content.strip():
                        messages.append({
                            "role": "user",
                            "content": content,
                            "timestamp": ts,
                            "uuid": uuid,
                        })
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_result":
                                result_content = item.get("content", "")
                                if isinstance(result_content, list):
                                    result_content = "\n".join(
                                        c.get("text", "") for c in result_content if isinstance(c, dict)
                                    )
                                messages.append({
                                    "role": "tool_result",
                                    "content": str(result_content),
                                    "toolUseId": item.get("tool_use_id"),
                                    "isError": item.get("is_error", False),
                                    "timestamp": ts,
                                    "uuid": uuid,
                                })

                elif msg_type == "assistant":
                    msg = obj.get("message", {})
                    content_items = msg.get("content", [])
                    model = msg.get("model")
                    usage = msg.get("usage")

                    for item in content_items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "text" and item.get("text", "").strip():
                            messages.append({
                                "role": "assistant",
                                "content": item["text"],
                                "timestamp": ts,
                                "uuid": uuid,
                                "model": model,
                                "usage": usage,
                            })
                        elif item.get("type") == "thinking" and item.get("thinking", "").strip():
                            messages.append({
                                "role": "thinking",
                                "content": item["thinking"],
                                "timestamp": ts,
                                "uuid": uuid,
                            })
                        elif item.get("type") == "tool_use":
                            messages.append({
                                "role": "tool_use",
                                "toolName": item.get("name", "unknown"),
                                "toolInput": _summarize_tool_input(item.get("name", ""), item.get("input", {})),
                                "toolId": item.get("id"),
                                "timestamp": ts,
                                "uuid": uuid,
                            })

                elif msg_type == "attachment":
                    pass  # skip
    except (OSError, IOError):
        pass

    return messages


def _summarize_tool_input(tool_name, tool_input):
    """为 tool 输入生成简短摘要。"""
    if not isinstance(tool_input, dict):
        return str(tool_input)[:200]

    if tool_name == "Bash":
        return tool_input.get("command", "")[:200]
    elif tool_name in ("Read", "Edit", "Write"):
        return tool_input.get("file_path", "")[:200]
    elif tool_name == "Grep":
        return tool_input.get("pattern", "")[:200]
    elif tool_name == "Glob":
        return tool_input.get("pattern", "")[:200]
    elif tool_name == "Agent":
        return tool_input.get("description", "")[:200]
    else:
        # 通用：取第一个字符串值
        for v in tool_input.values():
            if isinstance(v, str):
                return v[:200]
        return json.dumps(tool_input, ensure_ascii=False)[:200]


def search_sessions(query, claude_dir=None):
    """搜索会话。返回匹配的会话列表。"""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    query_lower = query.lower()
    results = []
    history_path = os.path.join(claude_dir, "history.jsonl")

    if not os.path.exists(history_path):
        return results

    # 从 history.jsonl 搜索
    seen_sessions = set()
    with open(history_path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            display = obj.get("display", "")
            sid = obj.get("sessionId")
            if sid and sid not in seen_sessions and query_lower in display.lower():
                seen_sessions.add(sid)
                # 截取匹配的上下文
                idx = display.lower().find(query_lower)
                start = max(0, idx - 30)
                end = min(len(display), idx + len(query) + 30)
                snippet = display[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(display):
                    snippet = snippet + "..."

                results.append({
                    "sessionId": sid,
                    "project": obj.get("project", ""),
                    "timestamp": obj.get("timestamp"),
                    "title": display[:80].replace("\n", " "),
                    "snippet": snippet,
                })

    return results


def get_stats(claude_dir=None):
    """获取使用统计。"""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    stats_path = os.path.join(claude_dir, "stats-cache.json")
    if os.path.exists(stats_path):
        try:
            with open(stats_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def get_active_sessions(claude_dir=None):
    """获取活跃会话列表。"""
    if claude_dir is None:
        claude_dir = get_claude_dir()

    sessions_dir = os.path.join(claude_dir, "sessions")
    active = []
    if not os.path.isdir(sessions_dir):
        return active

    for fname in os.listdir(sessions_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(sessions_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            active.append({
                "pid": data.get("pid"),
                "sessionId": data.get("sessionId"),
                "cwd": data.get("cwd"),
                "startedAt": data.get("startedAt"),
                "version": data.get("version"),
                "status": data.get("status"),
            })
        except (json.JSONDecodeError, OSError):
            continue

    return active


def get_projects_summary(sessions):
    """将会话按项目分组，返回项目列表。"""
    projects = defaultdict(list)
    for sid, info in sessions.items():
        key = info.get("projectPath") or info.get("project", "未知项目")
        projects[key].append(info)

    result = []
    for project_path, session_list in projects.items():
        session_list.sort(key=lambda s: s.get("timestamp") or "", reverse=True)
        result.append({
            "projectPath": project_path,
            "projectName": os.path.basename(project_path) if project_path else "未知项目",
            "sessions": session_list,
            "sessionCount": len(session_list),
        })

    result.sort(key=lambda p: p["sessions"][0].get("timestamp") or "" if p["sessions"] else "", reverse=True)
    return result
