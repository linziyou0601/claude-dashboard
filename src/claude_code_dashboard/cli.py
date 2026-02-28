"""命令列介面（CLI）引數解析模組。

負責定義與解析 ``claude-dash`` 指令的所有 CLI 參數，
包括方案類型、時區、顯示面板、刷新頻率等選項。

使用範例::

    claude-dash --plan max5 --view all
    claude-dash --view agents --no-sprites
"""

from __future__ import annotations

import argparse
import sys

from claude_code_dashboard import __version__
from claude_code_dashboard.constants import (
    DEFAULT_IDLE_TIMEOUT_MIN,
    DEFAULT_LANG,
    DEFAULT_PLAN,
    DEFAULT_REFRESH_S,
    DEFAULT_TIME_FORMAT,
    DEFAULT_TIMEZONE,
    DEFAULT_TOKEN_THEME,
    DEFAULT_VIEW,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令列參數並回傳 Namespace 物件。

    Args:
        argv: 命令列引數清單。若為 ``None`` 則使用 ``sys.argv[1:]``。

    Returns:
        解析後的 ``argparse.Namespace``，包含所有使用者指定的選項值。
    """
    p = argparse.ArgumentParser(
        prog="claude-dash",
        description="Claude Code 終端儀表板：Token 用量 + Agent 狀態即時監控",
    )
    p.add_argument("--version", action="version", version=f"claude-dash {__version__}")
    p.add_argument(
        "--plan",
        default=DEFAULT_PLAN,
        choices=["pro", "max5", "max20", "custom"],
        help="Token 方案等級（預設：%(default)s）",
    )
    p.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help="IANA 時區名稱（預設：%(default)s）",
    )
    p.add_argument(
        "--view",
        default=DEFAULT_VIEW,
        choices=["all", "tokens", "agents"],
        help="要顯示的面板（預設：%(default)s）",
    )
    p.add_argument(
        "--refresh",
        type=int,
        default=DEFAULT_REFRESH_S,
        help="資料刷新間隔秒數（預設：%(default)s）",
    )
    p.add_argument(
        "--idle-timeout",
        type=int,
        default=DEFAULT_IDLE_TIMEOUT_MIN,
        help="隱藏閒置超過 N 分鐘的 Agent（預設：%(default)s）",
    )
    p.add_argument(
        "--max-agents",
        type=int,
        default=0,
        help="最多顯示的 Agent 卡片數量（0=不限制）",
    )
    p.add_argument(
        "--show-all",
        action="store_true",
        help="顯示 30 分鐘內的所有工作階段",
    )
    p.add_argument(
        "--no-sprites",
        action="store_true",
        help="停用像素精靈，改用純文字模式",
    )
    p.add_argument(
        "--token-theme",
        default=DEFAULT_TOKEN_THEME,
        choices=["default", "ccm"],
        help="Token 面板主題：default=預設介面，ccm=claude-monitor 原版介面（預設：%(default)s）",
    )
    p.add_argument(
        "--time-format",
        default=DEFAULT_TIME_FORMAT,
        choices=["12h", "24h"],
        help="時間顯示格式：24h=24 小時制，12h=12 小時制（上午/下午）（預設：%(default)s）",
    )
    p.add_argument(
        "--lang",
        default=DEFAULT_LANG,
        choices=["auto", "en", "zh_TW", "zh_CN", "ja", "ko"],
        help="介面語系：auto=自動偵測，en=English，zh_TW=繁體中文，zh_CN=简体中文，ja=日本語，ko=한국어（預設：%(default)s）",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI 主進入點。解析引數後啟動儀表板主迴圈。

    Args:
        argv: 命令列引數清單。若為 ``None`` 則使用 ``sys.argv[1:]``。
    """
    args = parse_args(argv)

    # 延遲載入 app 模組，避免在解析引數失敗時做不必要的初始化
    from claude_code_dashboard.app import run

    try:
        run(args)
    except KeyboardInterrupt:
        sys.exit(0)
