/* Claude Code 会话浏览器 - 前端逻辑 */

const state = {
    projects: [],
    currentSessionId: null,
    searchTimeout: null,
};

// ========== API ==========

async function api(path) {
    const res = await fetch(path);
    return res.json();
}

async function apiPost(path) {
    const res = await fetch(path, { method: "POST" });
    return res.json();
}

// ========== 时间格式化 ==========

function formatTime(ts) {
    if (!ts) return "";
    let d;
    if (typeof ts === "number") {
        d = new Date(ts > 1e12 ? ts : ts * 1000);
    } else {
        d = new Date(ts);
    }
    if (isNaN(d)) return "";

    const now = new Date();
    const diff = now - d;
    const minute = 60 * 1000;
    const hour = 60 * minute;
    const day = 24 * hour;

    if (diff < minute) return "刚刚";
    if (diff < hour) return Math.floor(diff / minute) + "分钟前";
    if (diff < day) return Math.floor(diff / hour) + "小时前";
    if (diff < 7 * day) return Math.floor(diff / day) + "天前";

    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");

    if (y === now.getFullYear()) return `${m}-${dd} ${hh}:${mm}`;
    return `${y}-${m}-${dd} ${hh}:${mm}`;
}

function formatFullTime(ts) {
    if (!ts) return "";
    let d;
    if (typeof ts === "number") {
        d = new Date(ts > 1e12 ? ts : ts * 1000);
    } else {
        d = new Date(ts);
    }
    if (isNaN(d)) return "";
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// ========== 渲染：侧边栏 ==========

function renderSidebar(projects) {
    const el = document.getElementById("projectList");
    if (!projects.length) {
        el.innerHTML = '<div class="loading">暂无会话数据</div>';
        return;
    }

    el.innerHTML = projects.map((proj, pi) => `
        <div class="project-group">
            <div class="project-header" data-pi="${pi}">
                <span class="arrow">&#9660;</span>
                <span class="name" title="${esc(proj.projectPath)}">${esc(proj.projectName)}</span>
                <span class="count">${proj.sessionCount}</span>
            </div>
            <div class="session-list" data-pi="${pi}">
                ${proj.sessions.map(s => `
                    <div class="session-item" data-sid="${s.sessionId}" title="${esc(s.title)}">
                        <div class="session-title">
                            ${s.isActive ? '<span class="active-dot"></span>' : ''}
                            ${esc(truncate(s.title, 36))}
                        </div>
                        <div class="session-meta">
                            <span>${formatTime(s.timestamp)}</span>
                            ${s.model ? `<span>${esc(s.model.split('/').pop())}</span>` : ''}
                            ${s.msgCount ? `<span>${s.msgCount}条</span>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');

    // 绑定事件
    el.querySelectorAll(".project-header").forEach(h => {
        h.addEventListener("click", () => {
            h.classList.toggle("collapsed");
            const list = h.nextElementSibling;
            list.classList.toggle("collapsed");
        });
    });

    el.querySelectorAll(".session-item").forEach(item => {
        item.addEventListener("click", () => {
            const sid = item.dataset.sid;
            loadSession(sid);
        });
    });
}

// ========== 渲染：会话详情 ==========

async function loadSession(sid) {
    if (state.currentSessionId === sid) return;

    // 更新侧边栏选中状态
    document.querySelectorAll(".session-item").forEach(el => {
        el.classList.toggle("active", el.dataset.sid === sid);
    });

    state.currentSessionId = sid;

    const welcome = document.getElementById("welcome");
    const transcript = document.getElementById("transcript");
    const dashboard = document.getElementById("dashboard");

    welcome.classList.add("hidden");
    dashboard.classList.add("hidden");
    transcript.classList.remove("hidden");
    transcript.innerHTML = '<div class="loading"><div class="spinner"></div>加载中...</div>';

    const data = await api(`/api/session/${sid}`);
    if (data.error) {
        transcript.innerHTML = `<div class="loading">错误: ${esc(data.error)}</div>`;
        return;
    }

    renderTranscript(data.session, data.messages);
}

function renderTranscript(session, messages) {
    const el = document.getElementById("transcript");

    // 会话头部
    const header = `
        <div class="session-header">
            <h2>${esc(truncate(session.title, 60))}</h2>
            <div class="meta">
                <span>${formatFullTime(session.timestamp)}</span>
                ${session.model ? `<span>模型: ${esc(session.model)}</span>` : ''}
                ${session.version ? `<span>v${esc(session.version)}</span>` : ''}
                ${session.msgCount ? `<span>${session.msgCount} 条消息</span>` : ''}
                <span>${esc(session.projectPath || session.project)}</span>
            </div>
            <button class="btn-resume" onclick="resumeSession('${esc(session.sessionId)}')">继续会话</button>
        </div>
    `;

    // 配对 tool_use 和 tool_result
    const paired = pairToolCalls(messages);

    // 渲染消息
    const messagesHtml = paired.map(msg => renderMessage(msg)).join('');

    el.innerHTML = header + `<div class="messages">${messagesHtml}</div>`;

    // 绑定折叠事件
    el.querySelectorAll(".thinking-toggle").forEach(btn => {
        btn.addEventListener("click", () => {
            const content = btn.nextElementSibling;
            content.classList.toggle("expanded");
            btn.textContent = content.classList.contains("expanded") ? "收起思考" : "展开思考";
        });
    });

    el.querySelectorAll(".tool-header").forEach(btn => {
        btn.addEventListener("click", () => {
            const detail = btn.nextElementSibling;
            detail.classList.toggle("expanded");
        });
    });

    // 滚动到顶部
    el.scrollTop = 0;
}

function pairToolCalls(messages) {
    const resultMap = new Map();
    for (const msg of messages) {
        if (msg.role === "tool_result") {
            resultMap.set(msg.toolUseId, msg);
        }
    }

    const result = [];
    for (const msg of messages) {
        if (msg.role === "tool_use") {
            const tr = resultMap.get(msg.toolId);
            result.push({ ...msg, result: tr });
        } else if (msg.role === "tool_result") {
            // 已配对，跳过未配对的
            if (!resultMap.has(msg.toolUseId)) continue;
            // 检查是否已被配对消耗
            const last = result[result.length - 1];
            if (last && last.role === "tool_use" && last.toolId === msg.toolUseId) continue;
            // 未配对的 tool_result 也显示
            result.push(msg);
        } else {
            result.push(msg);
        }
    }
    return result;
}

function renderMessage(msg) {
    switch (msg.role) {
        case "user":
            return `
                <div class="message user">
                    <div class="message-bubble">${renderMarkdown(msg.content)}</div>
                    <div class="message-time">${formatTime(msg.timestamp)}</div>
                </div>`;

        case "assistant":
            return `
                <div class="message assistant">
                    <div class="message-bubble">${renderMarkdown(msg.content)}</div>
                    <div class="message-time">${formatTime(msg.timestamp)}</div>
                </div>`;

        case "thinking":
            return `
                <div class="thinking-block">
                    <div class="thinking-toggle">展开思考</div>
                    <div class="thinking-content">${esc(msg.content)}</div>
                </div>`;

        case "tool_use":
            return renderToolBlock(msg);

        case "tool_result":
            return `
                <div class="tool-block">
                    <div class="tool-result ${msg.isError ? 'error' : ''}">${esc(truncate(msg.content, 500))}</div>
                </div>`;

        default:
            return "";
    }
}

function renderToolBlock(msg) {
    const hasResult = !!msg.result;
    const resultHtml = hasResult
        ? `<div class="tool-result ${msg.result.isError ? 'error' : ''}">${esc(truncate(msg.result.content, 500))}</div>`
        : "";

    return `
        <div class="tool-block">
            <div class="tool-header">
                <span class="tool-icon">&#9881;</span>
                ${esc(msg.toolName)}: ${esc(truncate(msg.toolInput, 80))}
            </div>
            <div class="tool-detail">
                <div><strong>输入:</strong> ${esc(msg.toolInput)}</div>
                ${resultHtml}
            </div>
        </div>`;
}

// ========== 简易 Markdown 渲染 ==========

function renderMarkdown(text) {
    if (!text) return "";
    let html = esc(text);

    // 代码块
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code>${code}</code></pre>`;
    });

    // 行内代码
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 粗体
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // 标题
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // 链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

    // 引用
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    return html;
}

// ========== 搜索 ==========

function initSearch() {
    const input = document.getElementById("searchInput");
    const results = document.getElementById("searchResults");

    input.addEventListener("input", () => {
        clearTimeout(state.searchTimeout);
        const q = input.value.trim();
        if (!q) {
            results.classList.add("hidden");
            return;
        }
        state.searchTimeout = setTimeout(() => doSearch(q), 300);
    });

    input.addEventListener("focus", () => {
        if (input.value.trim()) {
            results.classList.remove("hidden");
        }
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".header-center")) {
            results.classList.add("hidden");
        }
    });
}

async function doSearch(q) {
    const results = document.getElementById("searchResults");
    results.innerHTML = '<div class="loading"><div class="spinner"></div>搜索中...</div>';
    results.classList.remove("hidden");

    const data = await api(`/api/search?q=${encodeURIComponent(q)}`);
    if (!data.length) {
        results.innerHTML = '<div class="search-result-item"><div class="search-result-title">无结果</div></div>';
        return;
    }

    results.innerHTML = data.slice(0, 20).map(r => `
        <div class="search-result-item" data-sid="${r.sessionId}">
            <div class="search-result-title">${esc(r.title)}</div>
            <div class="search-result-meta">
                ${esc(r.projectName || r.project || '')} · ${formatTime(r.timestamp)}
                ${r.model ? ' · ' + esc(r.model.split('/').pop()) : ''}
            </div>
            ${r.snippet ? `<div class="search-result-snippet">${esc(r.snippet)}</div>` : ''}
        </div>
    `).join('');

    results.querySelectorAll(".search-result-item").forEach(item => {
        item.addEventListener("click", () => {
            const sid = item.dataset.sid;
            if (sid) {
                results.classList.add("hidden");
                document.getElementById("searchInput").value = "";
                loadSession(sid);
            }
        });
    });
}

// ========== 仪表盘 ==========

async function loadDashboard() {
    const welcome = document.getElementById("welcome");
    const transcript = document.getElementById("transcript");
    const dashboard = document.getElementById("dashboard");

    welcome.classList.add("hidden");
    transcript.classList.add("hidden");
    dashboard.classList.remove("hidden");
    dashboard.innerHTML = '<div class="loading"><div class="spinner"></div>加载统计数据...</div>';

    // 取消侧边栏选中
    document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
    state.currentSessionId = null;

    const [stats, active] = await Promise.all([
        api("/api/stats"),
        api("/api/active"),
    ]);

    renderDashboard(stats, active);
}

function renderDashboard(stats, active) {
    const el = document.getElementById("dashboard");

    const totalSessions = stats.totalSessions || state.projects.reduce((s, p) => s + p.sessionCount, 0);
    const totalMessages = stats.totalMessages || 0;
    const firstDate = stats.firstSessionDate ? formatTime(stats.firstSessionDate) : "未知";

    // 每日活动 (可能是数组或字典)
    const dailyRaw = stats.dailyActivity || [];
    let dailyEntries;
    if (Array.isArray(dailyRaw)) {
        dailyEntries = dailyRaw.map(d => [d.date, d.messageCount || 0]).sort((a, b) => a[0].localeCompare(b[0]));
    } else {
        dailyEntries = Object.entries(dailyRaw).sort((a, b) => a[0].localeCompare(b[0]));
    }
    const maxDaily = Math.max(1, ...dailyEntries.map(e => e[1]));

    // 每日 token (可能是数组或字典)
    const tokenRaw = stats.dailyModelTokens || [];
    let tokenEntries;
    if (Array.isArray(tokenRaw)) {
        tokenEntries = tokenRaw.map(d => {
            const tokens = d.tokensByModel || {};
            const total = Object.values(tokens).reduce((s, v) => s + v, 0);
            return [d.date, total, tokens];
        }).sort((a, b) => a[0].localeCompare(b[0]));
    } else {
        tokenEntries = [];
    }

    // 模型使用 (值可能是对象或数字)
    const models = stats.modelUsage || {};
    const modelEntries = Object.entries(models).map(([name, val]) => {
        if (typeof val === 'object' && val !== null) {
            const total = (val.inputTokens || 0) + (val.outputTokens || 0);
            return [name, total, val];
        }
        return [name, val, null];
    }).sort((a, b) => b[1] - a[1]);

    // 小时分布
    const hours = stats.hourCounts || {};
    const maxHour = Math.max(1, ...Object.values(hours));

    // 活跃会话
    const activeHtml = active.length ? active.map(s => `
        <div class="active-session-item">
            <div class="info">
                <span class="active-dot"></span>
                <span>${esc(truncate(s.cwd, 40))}</span>
                <span style="color:var(--text-muted)">${esc(s.version || '')}</span>
            </div>
            <button class="btn-sm" onclick="resumeSession('${esc(s.sessionId)}')">恢复</button>
        </div>
    `).join('') : '<div style="color:var(--text-muted);font-size:12px">暂无活跃会话</div>';

    el.innerHTML = `
        <h2>仪表盘</h2>

        <div class="dash-cards">
            <div class="dash-card">
                <div class="number">${totalSessions}</div>
                <div class="label">总会话数</div>
            </div>
            <div class="dash-card">
                <div class="number">${totalMessages}</div>
                <div class="label">总消息数</div>
            </div>
            <div class="dash-card">
                <div class="number">${state.projects.length}</div>
                <div class="label">项目数</div>
            </div>
            <div class="dash-card">
                <div class="number">${firstDate}</div>
                <div class="label">首次使用</div>
            </div>
        </div>

        <div class="dash-section">
            <h3>活跃会话</h3>
            <div class="active-sessions">${activeHtml}</div>
        </div>

        ${dailyEntries.length ? `
        <div class="dash-section">
            <h3>每日活动 (最近30天)</h3>
            <div class="bar-chart">
                ${dailyEntries.slice(-30).map(([date, count]) => `
                    <div class="bar" style="height:${Math.max(2, count/maxDaily*100)}%">
                        <div class="tooltip">${date}: ${count}条</div>
                    </div>
                `).join('')}
            </div>
        </div>` : ''}

        ${modelEntries.length ? `
        <div class="dash-section">
            <h3>模型使用 (Token 数)</h3>
            ${modelEntries.map(([model, count, details]) => `
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:12px">
                    <span style="width:180px;color:var(--text-secondary)">${esc(model)}</span>
                    <div style="flex:1;height:16px;background:var(--bg-secondary);border-radius:3px;overflow:hidden">
                        <div style="height:100%;width:${Math.max(2, count/modelEntries[0][1]*100)}%;background:var(--accent);border-radius:3px"></div>
                    </div>
                    <span style="color:var(--text-muted);min-width:80px;text-align:right">${formatNumber(count)}</span>
                </div>
            `).join('')}
        </div>` : ''}

        ${Object.keys(hours).length ? `
        <div class="dash-section">
            <h3>时段分布</h3>
            <div class="bar-chart">
                ${Array.from({length:24}, (_, i) => {
                    const c = hours[i] || hours[String(i)] || 0;
                    return `<div class="bar" style="height:${Math.max(2, c/maxHour*100)}%">
                        <div class="tooltip">${i}:00 - ${c}条</div>
                    </div>`;
                }).join('')}
            </div>
        </div>` : ''}
    `;
}

// ========== 恢复会话 ==========

async function resumeSession(sid) {
    const data = await apiPost(`/api/resume/${sid}`);
    if (data.success) {
        alert("已启动新终端，正在恢复会话...");
    } else {
        alert("恢复失败: " + (data.message || "未知错误"));
    }
}

// ========== 工具函数 ==========

function esc(s) {
    if (!s) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function truncate(s, len) {
    if (!s) return "";
    s = String(s);
    return s.length > len ? s.slice(0, len) + "..." : s;
}

function formatNumber(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "K";
    return String(n);
}

// ========== 初始化 ==========

async function init() {
    initSearch();

    document.getElementById("btnDashboard").addEventListener("click", loadDashboard);
    document.getElementById("btnRefresh").addEventListener("click", async () => {
        await api("/api/refresh");
        await loadProjects();
    });

    await loadProjects();
}

async function loadProjects() {
    const sidebar = document.getElementById("projectList");
    sidebar.innerHTML = '<div class="loading"><div class="spinner"></div>加载会话列表...</div>';

    const projects = await api("/api/projects");
    state.projects = projects;
    renderSidebar(projects);

    // 显示快速统计
    const totalSessions = projects.reduce((s, p) => s + p.sessionCount, 0);
    const statsEl = document.getElementById("quickStats");
    statsEl.innerHTML = `
        <div class="stat-card">
            <div class="number">${totalSessions}</div>
            <div class="label">总会话数</div>
        </div>
        <div class="stat-card">
            <div class="number">${projects.length}</div>
            <div class="label">项目数</div>
        </div>
    `;
}

document.addEventListener("DOMContentLoaded", init);
