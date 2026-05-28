"""会话恢复模块 - 通过 claude --resume 恢复会话"""

import subprocess
import os
import platform


def resume_session(session_id, project_path):
    """在新终端窗口中恢复 Claude Code 会话。"""
    if not session_id:
        return {"success": False, "message": "缺少 sessionId"}

    cmd_parts = []
    if project_path and os.path.isdir(project_path):
        cmd_parts.append(f'cd "{project_path}"')

    cmd_parts.append(f"claude --resume {session_id}")
    full_cmd = " && ".join(cmd_parts)

    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True)
        elif system == "Darwin":  # macOS
            subprocess.Popen(['osascript', '-e', f'tell app "Terminal" to do script "{full_cmd}"'])
        else:  # Linux
            subprocess.Popen(f'x-terminal-emulator -e bash -c "{full_cmd}"', shell=True)
        return {"success": True, "message": "已启动新终端"}
    except Exception as e:
        return {"success": False, "message": str(e)}
