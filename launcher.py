"""会话恢复模块 - 通过 claude --resume 恢复会话"""

import subprocess
import os
import platform
import shutil
import tempfile


def _get_claude_cmd():
    """获取 claude CLI 完整路径，依次尝试多种安装方式"""
    # 1. 原生安装
    native = os.path.expandvars(r"%USERPROFILE%\.local\bin\claude.exe")
    if os.path.exists(native):
        return native

    # 2. Electron 打包版
    base = os.path.expandvars(r"%LOCALAPPDATA%\Claude-3p\claude-code")
    if os.path.isdir(base):
        versions = sorted(
            [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))],
            reverse=True,
        )
        for v in versions:
            exe = os.path.join(base, v, "claude.exe")
            if os.path.exists(exe):
                return exe

    # 3. npm 全局安装
    npm_global = os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
    if os.path.exists(npm_global):
        return npm_global

    # 4. PATH 中查找
    found = shutil.which("claude") or shutil.which("claude.cmd")
    if found:
        return found

    # 5. 回退：直接用名字（依赖 PATH）
    return "claude"


def _cleanup_old_scripts():
    """清理之前残留的临时 .ps1 文件"""
    tmpdir = tempfile.gettempdir()
    try:
        for fname in os.listdir(tmpdir):
            if fname.startswith("claude_resume_") and fname.endswith(".ps1"):
                try:
                    os.remove(os.path.join(tmpdir, fname))
                except OSError:
                    pass
    except OSError:
        pass


def resume_session(session_id, project_path):
    """在新终端窗口中恢复 Claude Code 会话。"""
    if not session_id:
        return {"success": False, "message": "缺少 sessionId"}

    try:
        system = platform.system()
        if system == "Windows":
            claude = _get_claude_cmd()

            _cleanup_old_scripts()

            lines = []
            # 如果 claude 不在 PATH 里，把它所在目录加入 PATH
            if not shutil.which("claude") and not shutil.which("claude.cmd"):
                claude_dir = os.path.dirname(os.path.abspath(claude))
                lines.append(f'$env:Path = "{claude_dir};$env:Path"')
            if project_path and os.path.isdir(project_path):
                lines.append(f'cd "{project_path}"')
            lines.append(f'claude --resume {session_id}')
            script = "\n".join(lines) + "\n"

            tmp = tempfile.NamedTemporaryFile(
                mode="w", prefix="claude_resume_", suffix=".ps1",
                delete=False, encoding="utf-8",
            )
            tmp.write(script)
            tmp.close()

            pwsh_exe = os.path.expandvars(
                r"%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe"
            )
            subprocess.Popen(
                f'start "" "{pwsh_exe}" -NoExit -File "{tmp.name}"',
                shell=True,
            )
        elif system == "Darwin":
            cmd_parts = []
            if project_path and os.path.isdir(project_path):
                cmd_parts.append(f'cd "{project_path}"')
            cmd_parts.append(f"claude --resume {session_id}")
            full_cmd = " && ".join(cmd_parts)
            subprocess.Popen(["osascript", "-e", f'tell app "Terminal" to do script "{full_cmd}"'])
        else:
            cmd_parts = []
            if project_path and os.path.isdir(project_path):
                cmd_parts.append(f'cd "{project_path}"')
            cmd_parts.append(f"claude --resume {session_id}")
            full_cmd = " && ".join(cmd_parts)
            subprocess.Popen(f"x-terminal-emulator -e bash -c '{full_cmd}'", shell=True)
        return {"success": True, "message": "已启动新终端"}
    except Exception as e:
        return {"success": False, "message": str(e)}
