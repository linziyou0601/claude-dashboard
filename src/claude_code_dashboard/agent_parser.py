"""JSONL 紀錄檔解析模組 — 推斷 Agent 目前狀態。

讀取 JSONL 紀錄檔的尾端（最後 32KB），分析最近的訊息紀錄以推斷：

- 目前正在使用什麼工具（Read、Edit、Bash 等）
- Agent 處於哪種狀態（工作中、思考中、等待授權、等待輸入、閒置）

判斷邏輯（依優先順序）：

1. 有尚未回傳結果的工具呼叫 → **工作中**（或等待授權）
2. 最後一則助手訊息為純文字 → **思考中**（或等待輸入）
3. 以上皆非 → **閒置**

核心套件說明：

- **dataclasses.dataclass**: Python 3.7+ 的裝飾器，自動產生 ``__init__``、
  ``__repr__``、``__eq__`` 等方法。欄位以類別變數語法宣告，
  支援型別標註與預設值，大幅減少樣板程式碼。
- **pathlib.Path**: Python 3.4+ 的物件導向路徑操作 API，
  比 ``os.path`` 更直覺。``Path.stat()`` 取得檔案資訊、
  ``Path.name`` 取得檔名、``Path.stem`` 取得不含副檔名的檔名。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from claude_code_dashboard.constants import (
    BASH_CMD_MAX_LEN,
    IDLE_THRESHOLD_S,
    INPUT_WAIT_TIMER_S,
    PERMISSION_TIMER_S,
    STATE_IDLE,
    STATE_THINKING,
    STATE_WAITING_INPUT,
    STATE_WAITING_PERMISSION,
    STATE_WORKING,
    TOOL_DISPLAY,
)


# ==========================================================
# 資料模型
# ==========================================================
@dataclass
class AgentState:
    """單一 Agent 的目前狀態資料。

    使用 ``@dataclass`` 裝飾器自動產生 ``__init__`` 方法，
    每個欄位都有預設值，因此可以用 ``AgentState()`` 建立空白狀態，
    也可以用 ``AgentState(state="working", tool_name="Read")`` 指定部分欄位。

    Attributes:
        state: 狀態字串，對應 :data:`constants.STATE_*` 常數之一。
        tool_name: 目前正在使用的工具名稱（若有），例如 ``"Read"``、``"Bash"``。
        status_text: 用於顯示在卡片上的狀態描述文字。
        last_update: JSONL 檔案的最後修改時間（Unix 時間戳記）。
        model: 使用中的模型名稱（例如 ``"opus"``、``"sonnet"``）。
    """
    state: str = STATE_IDLE
    tool_name: str = ""
    status_text: str = ""
    last_update: float = 0.0
    model: str = ""


# ==========================================================
# 常數
# ==========================================================
# 不需要使用者授權的工具（自動核准），這些工具在 Claude Code 中
# 被標記為安全工具，執行時不會彈出確認視窗
_EXEMPT_TOOLS: set[str] = {"Read", "Glob", "Grep", "TodoWrite", "WebSearch", "WebFetch"}

# 從 JSONL 尾端讀取的位元組數。
# 32KB 通常足以涵蓋最近 5~10 則訊息，避免載入整個可能數 MB 的紀錄檔
_TAIL_BYTES: int = 32768


# ==========================================================
# 主要解析函式
# ==========================================================
def parse_agent_state(jsonl_path: Path) -> AgentState:
    """解析 JSONL 紀錄檔並回傳 Agent 的目前狀態。

    演算法概要：

    1. 讀取 JSONL 檔案最後 32KB 的內容（使用 ``file.seek()`` 跳到尾端）
    2. 從最新到最舊逐行解析 JSON 物件（``reversed(lines)``）
    3. 記錄所有「已完成」的工具呼叫（user 訊息中的 ``tool_result``）
    4. 記錄所有「進行中」的工具呼叫（assistant 訊息中的 ``tool_use``
       且 ID 不在已完成集合中）
    5. 根據進行中工具、純文字回覆、更新時間等條件判斷狀態

    .. note::
        JSONL 格式為每行一筆獨立的 JSON 物件（不是 JSON 陣列）。
        Claude Code 的 JSONL 結構為::

            {"type": "user",      "message": {"content": [...]}}
            {"type": "assistant", "message": {"content": [...], "model": "..."}}

        ``content`` 陣列中的每個元素可能是 ``{"type": "text", "text": "..."}``
        或 ``{"type": "tool_use", "id": "...", "name": "Read", "input": {...}}``。

    Args:
        jsonl_path: JSONL 紀錄檔的路徑（``pathlib.Path`` 物件）。

    Returns:
        :class:`AgentState` 物件，描述 Agent 的目前狀態。
    """
    try:
        # Path.stat() 回傳 os.stat_result，包含 st_size（檔案大小）和 st_mtime（修改時間）
        file_size: int = jsonl_path.stat().st_size
        mtime: float = jsonl_path.stat().st_mtime
    except OSError:
        return AgentState()

    # 若檔案太久沒更新，直接判定為閒置（跳過昂貴的檔案讀取）
    age: float = time.time() - mtime
    if age > IDLE_THRESHOLD_S:
        return AgentState(
            state=STATE_IDLE,
            status_text=_format_age(age),
            last_update=mtime,
        )

    # 讀取檔案尾端的文字行
    lines: list[str] = _read_tail_lines(jsonl_path, file_size)
    if not lines:
        return AgentState(state=STATE_IDLE, last_update=mtime)

    # ----------------------------------------------------------
    # 從最新到最舊逐行解析，追蹤工具呼叫狀態
    # ----------------------------------------------------------
    active_tool_ids: set[str] = set()      # 進行中（尚無結果）的工具呼叫 ID
    completed_tool_ids: set[str] = set()   # 已回傳結果的工具呼叫 ID
    last_assistant_has_text: bool = False   # 最後一則助手訊息是否包含純文字
    last_tool_name: str = ""               # 最後一個進行中工具的名稱
    last_tool_status: str = ""             # 最後一個進行中工具的狀態描述
    model: str = ""                        # 從 JSONL 萃取的模型名稱

    for line in reversed(lines):
        try:
            # json.loads() 將單行 JSON 字串解析為 Python dict
            obj: dict = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue  # 跳過格式錯誤的行（可能是被截斷的第一行）

        msg_type: str = obj.get("type", "")

        # -- user 類型訊息 → 檢查是否有 tool_result（代表工具已完成） ----------------
        if msg_type == "user":
            message: dict = obj.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        # tool_use_id 是 Claude 在發起工具呼叫時產生的唯一 ID
                        completed_tool_ids.add(block.get("tool_use_id", ""))

        # -- assistant 類型訊息 → 檢查 tool_use 或 text -------------------
        elif msg_type == "assistant":
            message = obj.get("message", {})
            content = message.get("content", [])

            # 從最近的 assistant 訊息萃取模型名稱（只取第一個找到的）
            if not model:
                msg_model: str = message.get("model", "")
                if msg_model:
                    # 標準化模型名稱（完整名稱可能是 "claude-opus-4-6" 等）
                    if "opus" in msg_model:
                        model = "opus"
                    elif "sonnet" in msg_model:
                        model = "sonnet"
                    elif "haiku" in msg_model:
                        model = "haiku"
                    else:
                        model = msg_model

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    if block.get("type") == "tool_use":
                        tool_id: str = block.get("id", "")
                        if tool_id not in completed_tool_ids:
                            # 此工具呼叫尚未有對應的 tool_result → 視為進行中
                            active_tool_ids.add(tool_id)
                            name: str = block.get("name", "")
                            if not last_tool_name:
                                last_tool_name = name
                                last_tool_status = _format_tool_status(
                                    name, block.get("input", {}),
                                )

                    elif block.get("type") == "text":
                        # 只有在沒有進行中工具時，才標記「有純文字回覆」
                        if not last_tool_name and not active_tool_ids:
                            last_assistant_has_text = True

            # 找到足夠的資訊後即停止向前解析（效能最佳化）
            if active_tool_ids or last_assistant_has_text:
                break

    # ----------------------------------------------------------
    # 根據解析結果決定狀態
    # ----------------------------------------------------------
    now: float = time.time()
    time_since_update: float = now - mtime

    if active_tool_ids:
        # 有進行中的工具呼叫
        if last_tool_name not in _EXEMPT_TOOLS and time_since_update > PERMISSION_TIMER_S:
            # 非豁免工具且超過 7 秒無結果 → 可能在等待使用者授權
            return AgentState(
                state=STATE_WAITING_PERMISSION,
                tool_name=last_tool_name,
                status_text=last_tool_status or last_tool_name,
                last_update=mtime,
                model=model,
            )
        # 工具正在執行中
        return AgentState(
            state=STATE_WORKING,
            tool_name=last_tool_name,
            status_text=last_tool_status or last_tool_name,
            last_update=mtime,
            model=model,
        )

    if last_assistant_has_text:
        if time_since_update > INPUT_WAIT_TIMER_S:
            # 純文字回覆後超過 5 秒無新動作 → 等待使用者輸入
            return AgentState(
                state=STATE_WAITING_INPUT,
                status_text="Waiting for input",
                last_update=mtime,
                model=model,
            )
        # 純文字回覆剛完成 → 仍在回應中
        return AgentState(
            state=STATE_THINKING,
            status_text="Responding...",
            last_update=mtime,
            model=model,
        )

    # 沒有進行中工具、沒有純文字回覆
    if time_since_update < 3:
        # 3 秒內有更新 → 可能正在思考（API 正在串流回應中）
        return AgentState(
            state=STATE_THINKING,
            status_text="Thinking...",
            last_update=mtime,
            model=model,
        )

    # 以上皆非 → 閒置
    return AgentState(
        state=STATE_IDLE,
        status_text=_format_age(time_since_update),
        last_update=mtime,
        model=model,
    )


# ==========================================================
# 內部輔助函式
# ==========================================================
def _read_tail_lines(path: Path, file_size: int) -> list[str]:
    """讀取檔案尾端的 N 個位元組並回傳完整的文字行。

    以二進位模式開啟檔案（``"rb"``），使用 ``file.seek()`` 跳到
    尾端前 N 位元組的位置開始讀取，避免載入整個大檔案。

    ``file.seek(offset)`` 是 Python 檔案物件的方法，
    將讀取游標移動到指定的位元組位置（從檔案開頭計算）。

    Args:
        path: 檔案路徑。
        file_size: 檔案總大小（位元組）。

    Returns:
        文字行清單。若從檔案中段開始讀取，會跳過可能不完整的第一行。
    """
    read_size: int = min(_TAIL_BYTES, file_size)
    if read_size <= 0:
        return []

    try:
        with open(path, "rb") as f:
            # 跳到檔案尾端前 read_size 位元組的位置
            f.seek(max(0, file_size - read_size))
            data: bytes = f.read(read_size)

        # 將位元組解碼為 UTF-8 文字（遇到無法解碼的位元組用替代字元取代）
        text: str = data.decode("utf-8", errors="replace")
        lines: list[str] = text.strip().splitlines()

        # 若不是從檔案開頭讀取，第一行可能不完整（被截斷），跳過它
        if file_size > read_size and lines:
            lines = lines[1:]
        return lines
    except OSError:
        return []


def _format_tool_status(tool_name: str, tool_input: dict) -> str:
    """將工具呼叫格式化為人類可讀的狀態文字。

    根據工具類型從輸入參數中萃取關鍵資訊，
    搭配 ``TOOL_DISPLAY`` 中的範本字串，組合成簡短的描述。

    範例輸出：``"Reading: Utils.java"``、``"Running: npm test"``、``"Searching: TODO"``

    Args:
        tool_name: 工具名稱（例如 ``"Read"``、``"Bash"``）。
        tool_input: 工具的輸入參數字典（來自 JSONL 中的 ``tool_use.input``）。

    Returns:
        格式化後的狀態描述文字。
    """
    template: str = TOOL_DISPLAY.get(tool_name, "")
    if not template:
        return tool_name

    # -- 檔案操作類工具：顯示檔名 ------------------------------------------
    if tool_name in ("Read", "Edit", "Write"):
        path: str = tool_input.get("file_path", "") or tool_input.get("path", "")
        if path:
            name: str = Path(path).name  # Path.name 取得路徑的最後一段（檔名）
            return template.format(name)
        return template.format("...")

    # -- Bash 工具：顯示指令（截斷過長的部分） ---------------------------------
    if tool_name == "Bash":
        cmd: str = tool_input.get("command", "")
        if len(cmd) > BASH_CMD_MAX_LEN:
            cmd = cmd[:BASH_CMD_MAX_LEN] + "..."
        return template.format(cmd)

    # -- 搜尋類工具：顯示搜尋模式 ------------------------------------------
    if tool_name in ("Grep", "Glob"):
        pattern: str = tool_input.get("pattern", "")
        return template.format(pattern or "...")

    # -- 子代理工具：顯示任務描述 ------------------------------------------
    if tool_name == "Task":
        desc: str = tool_input.get("description", "")
        return template.format(desc or "task")

    # -- 其他有佔位符的範本 ---------------------------------------------
    if "{}" in template:
        return template.format("")
    return template


def _format_age(seconds: float) -> str:
    """將秒數格式化為人類可讀的時間距離字串。

    Args:
        seconds: 距今的秒數。

    Returns:
        格式化字串，例如 ``"30s ago"``、``"5m ago"``、``"2h ago"``。
    """
    if seconds < 60:
        return f"{int(seconds)}s ago"
    minutes: int = int(seconds / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours: int = int(minutes / 60)
    return f"{hours}h ago"
