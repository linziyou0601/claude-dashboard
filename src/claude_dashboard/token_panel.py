"""Token 面板模組 — 封裝 ccm（claude-monitor）的顯示控制器。

直接匯入 ccm 的 :class:`DisplayController` 以產生 Token 用量介面，
確保顯示效果與 ``ccm --view realtime`` 完全一致，無需重新造輪子。

.. note::
    ``claude-monitor``（ccm）是透過 ``uv tool install claude-monitor`` 安裝的
    獨立工具。本模組會在執行時期動態匯入 ccm 的內部模組。
    若 ccm 未安裝，會優雅地顯示錯誤提示。
"""

from __future__ import annotations

import argparse

from rich.console import RenderableType
from rich.text import Text


def create_token_display(plan: str, timezone: str) -> RenderableType:
    """建立 Token 用量顯示面板（透過 ccm 的 DisplayController）。

    此函式會：

    1. 匯入 ccm 的 ``DisplayController``、``analyze_usage``、``get_token_limit``
    2. 呼叫 ``analyze_usage()`` 取得最近 192 小時的用量資料
    3. 呼叫 ``DisplayController.create_data_display()`` 產生 Rich 可渲染物件

    Args:
        plan: Token 方案等級（``"pro"`` / ``"max5"`` / ``"max20"`` / ``"custom"``）。
        timezone: IANA 時區名稱（例如 ``"Asia/Taipei"``）。

    Returns:
        Rich 可渲染物件。正常情況下為 ccm 的完整 Token 用量面板；
        若 ccm 未安裝或發生錯誤，則回傳紅色錯誤提示文字。
    """
    try:
        # 延遲匯入：僅在需要時才載入 ccm 模組（避免啟動時失敗）
        from claude_monitor.ui.display_controller import DisplayController
        from claude_monitor.data.analysis import analyze_usage
        from claude_monitor.core.plans import get_token_limit

        dc = DisplayController()
        data: dict = analyze_usage(hours_back=192, use_cache=True)
        token_limit: int = get_token_limit(plan)

        # 建構 ccm 的 DisplayController 所需的最小 args 物件
        args = argparse.Namespace(
            plan=plan,
            timezone=timezone,
            custom_limit_tokens=None,
            time_format="auto",
        )

        return dc.create_data_display(data, args, token_limit)

    except ImportError:
        return Text(
            "[!] claude-monitor 未安裝。請執行：pip install claude-monitor",
            style="bold red",
        )
    except Exception as e:
        return Text(f"[!] Token 面板錯誤：{e}", style="bold red")
