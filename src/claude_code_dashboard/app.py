"""主應用程式模組 — Rich Live 即時刷新迴圈。

負責組合 Token 面板與 Agent 面板，透過 Rich 的 ``Live`` 功能
在終端機中持續刷新顯示。整體畫面架構如下::

    ┌─────────────────────────────────┐
    │  Token 面板（來自 ccm）           │
    ├─────────────────────────────────┤
    │  Agent 面板（像素精靈卡片）        │
    ├─────────────────────────────────┤
    │  頁尾（快捷鍵提示）                │
    └─────────────────────────────────┘

.. note::
    迴圈以 :data:`constants.SPRITE_FRAME_INTERVAL_S`（0.5 秒）為節拍，
    資料刷新則依使用者指定的 ``--refresh`` 間隔執行。
    這樣動畫可以流暢播放，同時避免過度頻繁地掃描檔案系統。

核心套件說明：

- **rich.live.Live**: Rich 的即時更新元件。用 ``with Live(...) as live:``
  進入上下文後，每次呼叫 ``live.update(renderable)`` 就會原地重繪終端畫面，
  無需清屏（Rich 透過 ANSI 跳脫序列實現差異更新）。
- **rich.console.Group**: 將多個 Rich 可渲染物件（Panel、Text 等）
  垂直串接成單一物件，方便一次性傳入 ``live.update()``。
"""

from __future__ import annotations

import argparse
import time

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.text import Text

from claude_code_dashboard.agent_panel import create_agent_display
from claude_code_dashboard.agent_scanner import SessionInfo, scan_sessions
from claude_code_dashboard.constants import DISPLAY_REFRESH_HZ, SPRITE_FRAME_INTERVAL_S
from claude_code_dashboard.token_panel import create_token_display


def _get_themed_console() -> Console:
    """嘗試取得 ccm 的自適應主題 Console，失敗則回傳預設 Console。

    ccm（claude-monitor）有一套自適應主題系統，能自動偵測終端背景色
    （深色或淺色），並選擇對應的前景色與進度條顏色。

    ``get_themed_console()`` 內部會呼叫:
    ``Console(theme=theme.rich_theme, force_terminal=True)``

    - ``force_terminal=True``: 強制 Rich 將 stdout 視為終端機，
      確保顏色輸出不被停用（即使 stdout 被重導向也一樣）。
    - ``theme=theme.rich_theme``: 載入 ccm 定義的自訂樣式名稱，
      這些樣式會被 ``create_data_display()`` 回傳的 renderable 使用。

    若 ccm 未安裝或主題模組不可用，退回使用預設的
    ``Console(force_terminal=True)``，此時 Token 面板會顯示安裝提示。

    Returns:
        已套用 ccm 主題的 Rich Console 物件（或預設 Console）。
    """
    try:
        from claude_monitor.terminal.themes import get_themed_console
        return get_themed_console()
    except ImportError:
        return Console(force_terminal=True)


def run(args: argparse.Namespace) -> None:
    """啟動儀表板主迴圈。

    建立 Rich Console 與 Live 即時更新環境，
    在無限迴圈中交替進行資料刷新與畫面渲染。

    ``argparse.Namespace`` 是 Python 標準函式庫 ``argparse`` 的回傳型別，
    行為類似字典但以屬性（attribute）存取，例如 ``args.plan``、``args.refresh``。

    Args:
        args: 由 :func:`cli.parse_args` 解析後的命令列參數物件，
              包含 ``plan``、``timezone``、``view``、``refresh`` 等屬性。

    Raises:
        KeyboardInterrupt: 使用者按下 Ctrl+C 時結束迴圈（由 cli.main 攔截）。
    """
    # 使用 ccm 的自適應主題 Console，確保 Token 面板顏色與 ccm 一致
    console: Console = _get_themed_console()

    frame: int = 0  # 動畫畫格計數器（每次迴圈 +1）
    last_data_refresh: float = 0.0  # 上次資料刷新的 Unix 時間戳記
    sessions: list[SessionInfo] = []  # 快取的工作階段清單（避免每幀都掃描）

    # Live 的 refresh_per_second 控制的是「畫面重繪頻率」，
    # 與迴圈中的 time.sleep() 是獨立的兩個節奏
    with Live(
        console=console,
        refresh_per_second=DISPLAY_REFRESH_HZ,
        vertical_overflow="visible",  # 內容超過終端高度時仍顯示（不截斷）
    ) as live:
        while True:
            now: float = time.time()

            # 判斷是否需要重新掃描工作階段資料
            needs_data_refresh: bool = (now - last_data_refresh) >= args.refresh

            # 組合所有可渲染元件（由上到下）
            renderables: list[RenderableType] = []

            # -- Token 面板 -----------------------------------------
            if args.view in ("all", "tokens"):
                token_display = create_token_display(
                    args.plan,
                    args.timezone,
                    theme=args.token_theme,
                    time_format=args.time_format,
                )
                renderables.append(token_display)

            # -- Agent 面板 -----------------------------------------
            if args.view in ("all", "agents"):
                if needs_data_refresh:
                    sessions = scan_sessions(
                        idle_timeout_min=args.idle_timeout,
                        show_all=args.show_all,
                    )
                    last_data_refresh = now

                agent_display = create_agent_display(
                    sessions=sessions,
                    frame=frame,
                    max_agents=args.max_agents,
                    no_sprites=args.no_sprites,
                    console_width=console.width,
                )
                renderables.append(agent_display)

            # -- 頁尾提示 -------------------------------------------
            renderables.append(Text(
                f"  Ctrl+C to exit | Data refresh: {args.refresh}s",
                style="dim",
            ))

            # Group() 將多個 renderable 垂直堆疊成一個，傳入 live.update()
            live.update(Group(*renderables))

            # 等待下一個動畫畫格（這裡同時控制了迴圈的最小間隔）
            time.sleep(SPRITE_FRAME_INTERVAL_S)
            frame += 1
