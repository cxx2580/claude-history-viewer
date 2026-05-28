[README.md](https://github.com/user-attachments/files/28349293/README.md)
# Claude Code 会话历史浏览器

一个本地 Web 应用，用于浏览、搜索和管理 Claude Code 的历史会话记录。

## 功能

- **项目浏览** - 按项目分组查看所有会话，支持时间/数量/字母排序
- **会话详情** - 聊天气泡式展示完整对话，支持 thinking 折叠、tool 调用折叠
- **搜索** - 关键词搜索历史会话
- **会话恢复** - 一键恢复之前的会话（调用 `claude --resume`）
- **仪表盘** - 统计总会话数、消息数、每日活动、模型使用分布
- **活跃会话** - 显示当前正在运行的会话

## 截图

```
+--------------------------------------------------+
|  Claude Code 会话浏览器    [搜索框...]    [统计] [刷新] |
+--------------------------------------------------+
|  排序: [时间] [数量] [字母]                        |
+--------------------------------------------------+
|  左侧面板             |  右侧内容区               |
|                       |                           |
|  ▼ one (1)            |  会话标题                 |
|    当前会话 ★          |  2026-05-28 模型: xxx    |
|  ▼ syy dierbufen (4)  |  [继续会话]              |
|    扫描项目...         |                           |
|    教一下这个项目...    |  [用户] 帮我看看...       |
|    ...                |  [助手] 好的，我来...      |
|                       |    > Bash: ls -la ...     |
+--------------------------------------------------+
```

## 环境要求

- Python 3.7+
- Claude Code（需要有历史会话数据）

## 安装

无需安装任何依赖，直接下载或克隆本项目即可。

```bash
git clone <本项目地址>
cd claude-history-viewer
```

## 启动

### Windows

双击 `启动.bat`，或在命令行中运行：

```bash
py run.py
```

### macOS / Linux

```bash
bash start.sh
# 或
python3 run.py
```

启动后浏览器会自动打开 `http://localhost:8686`。

按 `Ctrl+C` 关闭服务器。

## 项目结构

```
claude-history-viewer/
├── run.py              # 入口：启动服务器 + 打开浏览器
├── server.py           # HTTP 服务器 + API 路由
├── data_parser.py      # JSONL 数据解析、会话索引、搜索
├── launcher.py         # 会话恢复（调用 claude --resume）
├── templates/
│   └── index.html      # 主页面
├── static/
│   ├── style.css       # 暗色主题样式
│   └── app.js          # 前端逻辑
├── 启动.bat            # Windows 启动脚本
├── start.sh            # macOS/Linux 启动脚本
└── README.md           # 本文件
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 获取所有项目及会话列表 |
| GET | `/api/session/<id>` | 获取会话完整对话 |
| GET | `/api/search?q=xxx` | 搜索会话 |
| GET | `/api/stats` | 获取使用统计 |
| GET | `/api/active` | 获取活跃会话 |
| GET | `/api/refresh` | 刷新数据缓存 |
| POST | `/api/resume/<id>` | 恢复会话 |

## 数据来源

本工具读取 `~/.claude/` 目录下的数据文件：

- `history.jsonl` - 用户输入历史
- `projects/<project>/<session>.jsonl` - 会话完整记录
- `stats-cache.json` - 使用统计
- `sessions/<pid>.json` - 活跃会话

不会修改任何原始数据，只做读取和展示。

## 技术栈

- **后端**: Python 标准库（`http.server`、`json`）
- **前端**: 原生 HTML / CSS / JavaScript（无框架）
- **数据**: 直接读取 JSONL 文件，无数据库

## 常见问题

**Q: 启动后浏览器没有自动打开？**
手动访问 `http://localhost:8686`

**Q: 端口被占用？**
程序会自动尝试 8686-8695 端口，查看启动日志确认实际端口。

**Q: 会话列表为空？**
确认 `~/.claude/projects/` 目录下有 JSONL 文件。

**Q: macOS 提示安全警告？**
右键 `start.sh` -> 打开方式 -> 终端。

## 许可

MIT
