"""Agent 面板模組 — 渲染帶有像素精靈的 Agent 狀態卡片。

負責將 :mod:`agent_scanner` 偵測到的工作階段與
:mod:`agent_parser` 解析出的狀態，組合成可在終端機顯示的
Rich Panel 卡片。每張卡片為**橫向長方形**排版：

- 左側：像素精靈動畫（可透過 ``--no-sprites`` 停用）
- 右側：專案名稱、狀態標籤、工具使用細節、模型名稱

核心套件說明：

- **rich.panel.Panel**: 帶邊框的面板元件，可設定標題、副標題、框線顏色、固定寬高。
  ``Panel(content, border_style="green", width=36)`` 會建立一個綠色邊框的面板。
- **rich.columns.Columns**: 將多個元件水平排列（類似 CSS flexbox）。
  ``Columns(cards, padding=(0, 0))`` 會將卡片並排顯示。
- **rich.text.Text**: Rich 的文字元件，支援逐段設定不同樣式。
  ``text.append("hello", style="bold green")`` 可以在同一行中混合多種顏色。
- **rich.table.Table**: Rich 的表格元件，用於精靈與文字的左右排版。
  ``Table(show_header=False, box=None)`` 建立無框線、無標頭的隱形表格。
"""

from __future__ import annotations

from rich.columns import Columns
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from claude_code_dashboard.agent_parser import AgentState, parse_agent_state
from claude_code_dashboard.agent_scanner import SessionInfo
from claude_code_dashboard.constants import (
    ACTIVE_THRESHOLD_S,
    AGENT_CARD_HEIGHT,
    AGENT_CARD_MIN_WIDTH,
    AGENT_CARD_MAX_WIDTH,
    RECENT_THRESHOLD_S,
    STATE_DISPLAY,
    STATE_IDLE,
)
from claude_code_dashboard.sprites import render_sprite


# ===================================================================
# 精靈渲染尺寸（7 字元寬 × 3 行高）
# ===================================================================

_SPRITE_DISPLAY_WIDTH: int = 9
"""精靈在卡片中佔用的欄位寬度（含左右各 1 字元留白）。"""


def _calc_card_width(num_cards: int, console_width: int) -> int:
    """依據終端機寬度與卡片數量計算最佳卡片寬度。

    策略：盡量讓所有卡片在同一行顯示，但卡片寬度不超過上限、不低於下限。
    外層面板邊框佔 4 字元（左右各 2）。

    Args:
        num_cards: 要顯示的卡片數量。
        console_width: 終端機寬度（字元數）。

    Returns:
        每張卡片的寬度（字元數）。
    """
    # 外層 Agent 面板邊框佔用 4 字元
    available: int = console_width - 4
    if num_cards <= 0:
        return AGENT_CARD_MIN_WIDTH

    # 嘗試讓所有卡片排在同一行
    width: int = available // num_cards
    # 限制在合理範圍內
    width = max(width, AGENT_CARD_MIN_WIDTH)
    width = min(width, AGENT_CARD_MAX_WIDTH)
    return width


def create_agent_display(
    sessions: list[SessionInfo],
    frame: int,
    max_agents: int = 0,
    no_sprites: bool = False,
    console_width: int = 0,
) -> RenderableType:
    """建立 Agent 面板，包含所有工作階段的精靈卡片。

    此函式負責整個 Agent 面板的組裝流程：

    1. 套用最大顯示數量限制
    2. 統計每個專案的工作階段數量（決定是否顯示編號）
    3. 逐一解析 JSONL 紀錄檔取得狀態
    4. 建立卡片並水平排列

    Args:
        sessions: 由 :func:`agent_scanner.scan_sessions` 偵測到的工作階段清單。
        frame: 動畫畫格計數器（用於精靈動畫循環）。
        max_agents: 最多顯示的卡片數量（0 表示不限制）。
        no_sprites: 若為 ``True``，停用像素精靈，僅顯示文字。
        console_width: 終端機寬度（字元數），用於動態計算卡片寬度。0 表示使用預設值。

    Returns:
        Rich 可渲染物件（``RenderableType`` 是 Rich 定義的通用型別別名，
        任何實作了 ``__rich_console__`` 方法的物件都符合）。
    """
    if not sessions:
        return Panel(
            Text("  No active Claude sessions found", style="dim"),
            title="[bold bright_blue]🤖 Agents[/]",
            border_style="dim",
        )

    # 套用最大顯示數量限制
    display_sessions: list[SessionInfo] = (
        sessions[:max_agents] if max_agents > 0 else sessions
    )

    cards: list[Panel] = []
    active_count: int = 0

    # ── 統計每個專案的工作階段數量 ─────────────────────────
    # 用於判斷是否需要為同專案的多個工作階段加上編號（#1, #2, ...）
    project_counts: dict[str, int] = {}
    for s in display_sessions:
        project_counts[s.project_name] = project_counts.get(s.project_name, 0) + 1

    # ── 計算卡片寬度 ─────────────────────────────────────
    effective_width: int = console_width if console_width > 0 else 80
    card_width: int = _calc_card_width(len(display_sessions), effective_width)

    # ── 逐一建立卡片 ─────────────────────────────────────
    project_indices: dict[str, int] = {}  # 追蹤每個專案目前的流水編號
    for s in display_sessions:
        idx: int = project_indices.get(s.project_name, 0) + 1
        project_indices[s.project_name] = idx
        # 同一專案有多個工作階段時才加上編號
        needs_number: bool = project_counts[s.project_name] > 1

        # 解析 JSONL 紀錄檔取得 Agent 狀態（讀取檔案尾端 32KB）
        agent_state: AgentState = parse_agent_state(s.jsonl_path)

        # 掃描器無模型資訊時，從 JSONL 解析結果補充
        if not s.model and agent_state.model:
            s.model = agent_state.model

        # 若工作階段已超過 10 分鐘未更新且非活躍，強制標為閒置
        if s.age_seconds > RECENT_THRESHOLD_S and not s.has_process:
            agent_state.state = STATE_IDLE
            agent_state.status_text = f"{int(s.age_seconds / 60)}m ago"

        # 統計活躍數量（30 秒內有更新 或 有對應行程）
        if s.age_seconds < ACTIVE_THRESHOLD_S or s.has_process:
            active_count += 1

        # 判斷卡片是否需要變暗顯示（視覺上區分活躍與非活躍）
        is_dim: bool = s.age_seconds > ACTIVE_THRESHOLD_S and not s.has_process

        card: Panel = _build_agent_card(
            session=s,
            state=agent_state,
            frame=frame,
            index=idx if needs_number else 0,
            is_dim=is_dim,
            no_sprites=no_sprites,
            card_width=card_width,
        )
        cards.append(card)

    # Columns 會將所有卡片水平排列，自動換行
    cols = Columns(cards, padding=(0, 0))
    subtitle: str = f"{len(display_sessions)} sessions | {active_count} active"

    return Panel(
        cols,
        title="[bold bright_blue]🤖 Active Agents[/]",
        subtitle=f"[dim]{subtitle}[/]",
        border_style="bright_blue",
    )


def _build_agent_card(
    session: SessionInfo,
    state: AgentState,
    frame: int,
    index: int,
    is_dim: bool,
    no_sprites: bool,
    card_width: int = 36,
) -> Panel:
    """建立單一 Agent 的橫向狀態卡片。

    卡片為橫向長方形排版：

    - **有精靈時**：使用 Rich Table 將精靈（左欄）與文字資訊（右欄）並排。
      精靈 3 行高 × 7 字元寬，右側放專案名稱、狀態、細節、模型。
    - **無精靈時**：純文字垂直排列。

    Args:
        session: 工作階段資訊（包含專案名稱、模型等）。
        state: Agent 目前狀態（由 agent_parser 解析而得）。
        frame: 動畫畫格計數器。
        index: 同專案工作階段的編號（0 表示不顯示編號）。
        is_dim: 是否將卡片整體變暗顯示（用於非活躍工作階段）。
        no_sprites: 是否停用像素精靈。
        card_width: 卡片寬度（字元數），由 :func:`_calc_card_width` 動態計算。

    Returns:
        Rich Panel 物件，寬度依據終端機寬度動態調整。
    """
    # STATE_DISPLAY 字典取得狀態對應的標籤文字與顏色
    label: str
    color: str
    label, color = STATE_DISPLAY.get(state.state, ("?", "white"))
    if is_dim:
        color = "dim"

    # ── 組裝專案名稱 ────────────────────────────────────
    name: str = session.project_name
    if index > 0:
        name += f" #{index}"  # 同專案多個工作階段時加上編號

    # ── 截斷狀態文字 ────────────────────────────────────
    # 右欄可用寬度 = 卡片寬度 - 精靈欄 - 邊框 - 留白
    max_status_len: int = card_width - _SPRITE_DISPLAY_WIDTH - 6
    status: str = state.status_text
    if status and len(status) > max_status_len:
        status = status[:max_status_len - 3] + "..."

    if not no_sprites:
        # ── 橫向排版：精靈（左）+ 文字（右）──────────────

        # 渲染精靈圖（Rich Text 物件，3 行高 × 7 字元寬）
        sprite: Text = render_sprite(state.state, frame)

        # 組裝右側文字資訊（逐行堆疊）
        info = Text()
        info.append(name, style="bold" if not is_dim else "dim")
        info.append("\n")
        info.append(label, style=color)
        if status:
            info.append("\n")
            info.append(status, style="dim")
        if session.model:
            info.append("\n")
            info.append(session.model, style="dim italic")

        # 使用 Rich Table 實現左右並排排版（無框線、無標頭的隱形表格）
        # Table.add_column() 定義欄位寬度
        # Table.add_row() 將精靈與文字放入同一行
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=(0, 1),
            expand=False,
        )
        table.add_column(width=7)   # 精靈欄（7 字元寬 = Braille 14px / 2）
        table.add_column()          # 文字欄（自適應寬度）
        table.add_row(sprite, info)

        return Panel(
            table,
            border_style=color,
            width=card_width,
            height=AGENT_CARD_HEIGHT,
        )

    else:
        # ── 純文字排版（無精靈）──────────────────────────
        content = Text()
        content.append(" ")
        content.append(name, style="bold" if not is_dim else "dim")
        content.append("\n ")
        content.append(label, style=color)
        if status:
            content.append("\n ")
            content.append(status, style="dim")
        if session.model:
            content.append("\n ")
            content.append(session.model, style="dim italic")

        return Panel(
            content,
            border_style=color,
            width=card_width,
            height=AGENT_CARD_HEIGHT,
        )
