"""全域常數定義模組。

集中管理所有跨模組共用的常數，包括：
- 輪詢與刷新間隔
- Agent 狀態判斷門檻值
- 顯示尺寸設定
- CLI 預設值
- 工具名稱對應的顯示格式
- Agent 狀態定義與顯示樣式
"""

from __future__ import annotations


# ===================================================================
# 輪詢與刷新間隔
# ===================================================================

DISPLAY_REFRESH_HZ: float = 2.0
"""Rich Live 的畫面刷新頻率（每秒幾次）。"""

SPRITE_FRAME_INTERVAL_S: float = 0.5
"""像素精靈動畫的換幀間隔（秒）。每 0.5 秒切換一次畫格。"""


# ===================================================================
# Agent 狀態判斷門檻值（單位：秒）
# ===================================================================

ACTIVE_THRESHOLD_S: int = 30
"""距離上次更新 JSONL 幾秒內算「活躍」。超過此值卡片會變暗。"""

RECENT_THRESHOLD_S: int = 600
"""距離上次更新 JSONL 幾秒內算「近期」。超過此值強制標為閒置（10 分鐘）。"""

IDLE_THRESHOLD_S: int = 120
"""JSONL 超過此秒數未更新則視為閒置（2 分鐘）。用於 agent_parser 判斷。"""


# ===================================================================
# 啟發式計時器（參考 Pixel Agents 的邏輯）
# ===================================================================

PERMISSION_TIMER_S: float = 7.0
"""工具呼叫後若超過此秒數仍無結果，且該工具不在豁免清單中，
視為正在等待使用者授權。"""

INPUT_WAIT_TIMER_S: float = 5.0
"""最後一則訊息為純文字回覆後，若超過此秒數無新動作，
視為正在等待使用者輸入。"""


# ===================================================================
# 顯示相關設定
# ===================================================================

BASH_CMD_MAX_LEN: int = 30
"""Bash 指令在狀態文字中的最大顯示長度（字元數）。"""

AGENT_CARD_MIN_WIDTH: int = 30
"""Agent 卡片最小寬度（字元數）。確保精靈 + 文字不會被壓縮變形。"""

AGENT_CARD_MAX_WIDTH: int = 52
"""Agent 卡片最大寬度（字元數）。避免卡片過寬浪費空間。"""

AGENT_CARD_HEIGHT: int = 6
"""Agent 卡片面板高度（行數）。橫向排版：精靈 3 行 + 模型 1 行 + 框線 2 行。"""


# ===================================================================
# CLI 預設值
# ===================================================================

DEFAULT_PLAN: str = "max5"
"""預設的 Token 方案等級。"""

DEFAULT_TIMEZONE: str = "Asia/Taipei"
"""預設的 IANA 時區名稱。"""

DEFAULT_REFRESH_S: int = 10
"""預設的資料刷新間隔（秒）。"""

DEFAULT_IDLE_TIMEOUT_MIN: int = 10
"""預設的閒置逾時時間（分鐘）。超過後 Agent 不會顯示。"""

DEFAULT_VIEW: str = "all"
"""預設的顯示模式。``all`` 表示同時顯示 Token 面板與 Agent 面板。"""


# ===================================================================
# 工具名稱 → 狀態顯示格式
# ===================================================================
# ``{}`` 是 Python str.format() 的佔位符，
# 會在 agent_parser 中被替換為實際參數（檔名、指令、搜尋模式等）

TOOL_DISPLAY: dict[str, str] = {
    "Read": "Reading: {}",
    "Edit": "Editing: {}",
    "Write": "Writing: {}",
    "Bash": "Running: {}",
    "Grep": "Searching: {}",
    "Glob": "Searching: {}",
    "Task": "Sub-agent: {}",
    "WebSearch": "Browsing web",
    "WebFetch": "Fetching web",
    "TodoWrite": "Updating todos",
}


# ===================================================================
# Agent 狀態常數
# ===================================================================

STATE_WORKING: str = "working"
"""Agent 正在使用工具執行任務。"""

STATE_THINKING: str = "thinking"
"""Agent 正在思考或產生回覆中。"""

STATE_WAITING_PERMISSION: str = "waiting_permission"
"""Agent 正在等待使用者授予工具執行權限。"""

STATE_WAITING_INPUT: str = "waiting_input"
"""Agent 已回覆完畢，正在等待使用者輸入。"""

STATE_IDLE: str = "idle"
"""Agent 已閒置（無最近活動）。"""


# ─────────────────────────────────────────────────────────────────
# 狀態顯示對應：(標籤文字, Rich 框線顏色)
# ─────────────────────────────────────────────────────────────────

STATE_DISPLAY: dict[str, tuple[str, str]] = {
    STATE_WORKING: ("✍  Working", "green"),
    STATE_THINKING: ("🧠 Thinking", "yellow"),
    STATE_WAITING_PERMISSION: ("⏳ Permission", "red"),
    STATE_WAITING_INPUT: ("💬 Input", "bright_magenta"),
    STATE_IDLE: ("💤 Idle", "dim"),
}
