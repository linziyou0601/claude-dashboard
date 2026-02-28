"""Token 面板模組 — Token 用量、費用、訊息數的即時監控面板。

從 claude-monitor 取得用量資料，以全寬進度條、燃燒率、模型分布與
重置時間預測呈現當前 Token 使用狀態。可透過 ``--token-theme ccm``
切換為 claude-monitor 原版介面。

資料來源：

- ``claude_monitor.data.analysis.analyze_usage`` — 掃描 JSONL 產出用量 dict
- ``claude_monitor.core.plans.Plans`` — 方案上限（token / cost / message）

面板佈局：

1. 使用量指標（Cost / Tokens / Messages）— 標頭對齊、全寬進度條在下
2. 雙欄區塊（Models + Rates | Reset In + Predictions），窄螢幕自動轉單欄
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone as _tz
from typing import Any

from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]


# ==========================================================
# 常數
# ==========================================================
_FILLED: str = "█"
"""進度條已填充區段的字元。"""

_EMPTY: str = "░"
"""進度條未填充區段的字元。"""

_BAR_INDENT: int = 0
"""上半部進度條的左側縮排字元數。0 表示與面板內容齊左。"""

_GRID_BREAKPOINT: int = 70
"""雙欄佈局的最小內容寬度（字元）。低於此值自動轉為單欄。"""

_MODEL_COLORS: dict[str, str] = {
    "opus": "#f97316",
    "sonnet": "#4a9eff",
    "haiku": "#22c55e",
}
"""模型系列 → 堆疊色條顏色對應表。"""


# ==========================================================
# 色彩與格式化工具
# ==========================================================
def _severity_color(ratio: float) -> str:
    """依使用比例回傳 Rich 顏色名稱。

    Args:
        ratio: 使用量佔上限的比例（0.0–1.0）。

    Returns:
        Rich 顏色名稱：綠色 (< 50 %)、黃色 (50–80 %)、紅色 (≥ 80 %)。
    """
    if ratio >= 0.8:
        return "red"
    if ratio >= 0.5:
        return "yellow"
    return "green"


def _pct(ratio: float) -> str:
    """將比例格式化為百分比字串，例如 ``0.627`` → ``"62.7%"``。

    Args:
        ratio: 比例值（0.0–1.0）。

    Returns:
        百分比字串（保留一位小數）。
    """
    return f"{ratio * 100:.1f}%"


def _format_time(dt: datetime, tz_info: Any, fmt: str) -> str:
    """將 UTC datetime 轉換為使用者時區並格式化為時間字串。

    Args:
        dt: UTC datetime 物件。
        tz_info: 目標時區（``ZoneInfo`` 或 ``timezone`` 物件）。
        fmt: 時間格式，``"24h"``（例如 ``"14:30"``）或
             ``"12h"``（例如 ``"2:30 PM"``）。

    Returns:
        格式化後的時間字串。
    """
    local = dt.astimezone(tz_info)
    if fmt == "24h":
        return local.strftime("%H:%M")
    return local.strftime("%I:%M %p").lstrip("0")


def _model_family(name: str) -> str:
    """從模型全名擷取系列代號（``"opus"`` / ``"sonnet"`` / ``"haiku"``）。

    Args:
        name: 模型全名（例如 ``"claude-opus-4-6"``）。

    Returns:
        系列代號字串。無法辨識時預設回傳 ``"sonnet"``。
    """
    lower = name.lower()
    for key in ("opus", "sonnet", "haiku"):
        if key in lower:
            return key
    return "sonnet"


def _short_model(name: str) -> str:
    """將模型全名縮寫為顯示名（``"Opus"`` / ``"Sonnet"`` / ``"Haiku"``）。

    Args:
        name: 模型全名（例如 ``"claude-opus-4-6"``）。

    Returns:
        簡短的模型顯示名稱。
    """
    lower = name.lower()
    if "opus" in lower:
        return "Opus"
    if "haiku" in lower:
        return "Haiku"
    return "Sonnet"


# ==========================================================
# 自適應寬度進度條
# ==========================================================
class _AdaptiveBar:
    """上半部使用的自適應寬度進度條，支援左側縮排。

    透過實作 ``__rich_console__`` 協議，在 Rich 渲染時取得
    ``options.max_width``（可用寬度），動態計算填充量。

    Attributes:
        ratio: 填充比例（0.0–1.0），會在建構時限制在有效範圍。
        color: Rich 顏色名稱，用於已填充區段。
    """

    def __init__(self, ratio: float, color: str) -> None:
        self.ratio = max(0.0, min(ratio, 1.0))
        self.color = color

    def __rich_console__(
        self, console: Console, options: ConsoleOptions,
    ) -> RenderResult:
        """Rich 渲染協議：產生一行含左側縮排的進度條。"""
        width = max(1, options.max_width - _BAR_INDENT)   # 扣除縮排後的可用寬度
        filled = int(self.ratio * width)                  # 已填充的字元數
        t = Text()
        t.append(" " * _BAR_INDENT)                       # 左側縮排空白
        t.append(_FILLED * filled, style=self.color)      # 已填充區段（帶顏色）
        t.append(_EMPTY * (width - filled), style="dim")  # 未填充區段（暗色）
        yield t


class _FullWidthBar:
    """全寬自適應進度條（無左側縮排），用於雙欄格線內。

    Attributes:
        ratio: 填充比例（0.0–1.0）。
        color: Rich 顏色名稱。
    """

    def __init__(self, ratio: float, color: str) -> None:
        self.ratio = max(0.0, min(ratio, 1.0))
        self.color = color

    def __rich_console__(
        self, console: Console, options: ConsoleOptions,
    ) -> RenderResult:
        """Rich 渲染協議：產生一行全寬進度條。"""
        width = max(1, options.max_width)                 # 使用全部可用寬度（無縮排）
        filled = int(self.ratio * width)                  # 已填充的字元數
        t = Text()
        t.append(_FILLED * filled, style=self.color)      # 已填充區段（帶顏色）
        t.append(_EMPTY * (width - filled), style="dim")  # 未填充區段（暗色）
        yield t


class _FullWidthStackedBar:
    """全寬堆疊色條，用於模型分布視覺化。

    將多個區段（各有獨立比例與顏色）依序繪製，
    剩餘空間以暗色填充。

    Attributes:
        segments: ``(ratio, color)`` 清單，依比例由大到小排列。
    """

    def __init__(self, segments: list[tuple[float, str]]) -> None:
        self.segments = segments

    def __rich_console__(
        self, console: Console, options: ConsoleOptions,
    ) -> RenderResult:
        """Rich 渲染協議：產生一行堆疊色條。"""
        width = max(1, options.max_width)
        t = Text()
        remaining = width
        for ratio, color in self.segments:
            w = max(1, round(ratio * width))  # 每段至少 1 字元，確保可見
            if w > remaining:
                w = remaining                 # 防止超出總寬度
            t.append(_FILLED * w, style=color)
            remaining -= w
        if remaining > 0:
            t.append(_EMPTY * remaining, style="dim")  # 剩餘空間以暗色填充
        yield t


# ==========================================================
# 響應式雙欄格線
# ==========================================================
class _ResponsiveGrid:
    """依據可用寬度自動選擇雙欄或單欄排版。

    寬度 ≥ ``_GRID_BREAKPOINT`` 時，左右並排（各佔一半，中間 2 字元間隔）；
    否則左上右下垂直堆疊。

    使用 Rich Table 的三欄配置（左欄 + 間隔欄 + 右欄）搭配明確的
    ``width`` 設定，確保左右欄的子元件能取得精確的可用寬度。

    Attributes:
        left: 左欄的 Rich 可渲染物件清單。
        right: 右欄的 Rich 可渲染物件清單。
    """

    def __init__(
        self,
        left: list[RenderableType],
        right: list[RenderableType],
    ) -> None:
        self.left = left
        self.right = right

    def __rich_console__(
        self, console: Console, options: ConsoleOptions,
    ) -> RenderResult:
        """Rich 渲染協議：依寬度產生雙欄或單欄佈局。"""
        has_left = bool(self.left)
        has_right = bool(self.right)

        # 雙欄模式：寬度足夠且左右欄皆有內容
        if options.max_width >= _GRID_BREAKPOINT and has_left and has_right:
            gap = 2  # 左右欄之間的間隔寬度（字元）
            right_w = (options.max_width - gap) // 2
            left_w = options.max_width - gap - right_w

            # 用三欄 Table 模擬 CSS grid：[左欄 | gap | 右欄]
            tbl = Table(
                show_header=False,  # 隱藏欄位標題列
                show_edge=False,    # 隱藏表格外框
                box=None,           # 無邊框樣式
                expand=True,        # 展開至父容器寬度（類似 width: 100%）
                padding=0,          # 儲存格內距為 0（類似 padding: 0）
            )
            # 用明確的 width 鎖定欄寬，確保子元件的 max_width 精確
            tbl.add_column(width=left_w)   # 左欄：固定寬度
            tbl.add_column(width=gap)      # 中欄：間隔（純空白）
            tbl.add_column(width=right_w)  # 右欄：固定寬度
            # Group() 將清單中的多個 renderable 垂直堆疊成一個
            tbl.add_row(Group(*self.left), Text(""), Group(*self.right))
            yield tbl
        else:
            # 單欄模式：垂直堆疊（窄螢幕 fallback）
            if has_left:
                yield Group(*self.left)
            if has_left and has_right:
                yield Text("")  # 左右區塊之間的空行間隔
            if has_right:
                yield Group(*self.right)


# ==========================================================
# 元件建構
# ==========================================================
def _metric_header(
    icon: str,
    label: str,
    current: str,
    limit: str,
    ratio: float,
) -> Table:
    """建立指標標頭列（用於上半部三列指標）。

    三欄佈局：

    - 左欄（``ratio=1``）：icon + label，自動填滿剩餘空間
    - 中欄（``min_width=20``）：``current / limit`` 靠右對齊
    - 右欄（``width=8``）：百分比靠右對齊，顏色依嚴重程度變化

    Args:
        icon: 指標圖示（emoji）。
        label: 指標名稱（例如 ``"Cost"``）。
        current: 目前值的格式化字串（例如 ``"$12.50"``）。
        limit: 上限值的格式化字串（例如 ``"$35.00"``）。
        ratio: 使用比例，用於決定百分比文字的顏色。

    Returns:
        Rich Table 物件（單行三欄）。
    """
    color = _severity_color(ratio)

    # 三欄佈局：[icon+label (彈性) | current/limit (靠右) | 百分比 (靠右固定寬)]
    tbl = Table(
        show_header=False,  # 隱藏欄位標題列
        show_edge=False,    # 隱藏表格外框
        box=None,           # 無邊框樣式
        padding=0,          # 儲存格內距為 0
        expand=True,        # 展開至父容器寬度
    )
    tbl.add_column("label", no_wrap=True, ratio=1)                        # 彈性寬度，填滿剩餘空間（類似 flex: 1）
    tbl.add_column("value", no_wrap=True, justify="right", min_width=20)  # 靠右對齊，最小 20 字元
    tbl.add_column("pct", no_wrap=True, justify="right", width=8)         # 固定 8 字元寬

    tbl.add_row(
        Text.from_markup(f"{icon} [bold]{label}[/bold]"),
        Text(f"{current} / {limit}"),
        Text(_pct(ratio), style=f"bold {color}"),
    )
    return tbl


def _model_labels(per_model: dict[str, dict], total: int) -> Table:
    """建立模型分布標籤列（堆疊色條下方的文字說明）。

    第一個模型靠左、其餘靠右，各附帶彩色圓點與百分比。

    Args:
        per_model: 模型名稱 → 統計資料字典（含 ``input_tokens``、``output_tokens``）。
        total: 所有模型 Token 總數（用於計算百分比）。

    Returns:
        Rich Table 物件（單行兩欄：左側主要模型、右側其他模型）。
    """
    models = sorted(
        per_model.items(),
        key=lambda kv: kv[1].get("input_tokens", 0) + kv[1].get("output_tokens", 0),
        reverse=True,
    )

    # 兩欄佈局：[主要模型 (靠左) | 其他模型 (靠右)]
    tbl = Table(
        show_header=False,  # 隱藏欄位標題列
        show_edge=False,    # 隱藏表格外框
        box=None,           # 無邊框樣式
        padding=0,          # 儲存格內距為 0
        expand=True,        # 展開至父容器寬度
    )
    tbl.add_column("left", no_wrap=True)                   # 左欄：佔比最高的模型
    tbl.add_column("right", no_wrap=True, justify="right") # 右欄：其餘模型靠右排列

    parts_left: list[str] = []
    parts_right: list[str] = []

    for i, (model_name, stats) in enumerate(models):
        mt = stats.get("input_tokens", 0) + stats.get("output_tokens", 0)
        mp = mt / total * 100 if total else 0
        family = _model_family(model_name)
        color = _MODEL_COLORS.get(family, "#4a9eff")
        # 格式：彩色圓點 + 模型名 + 百分比（例如 "● Opus 72.3%"）
        entry = f"[{color}]●[/] {_short_model(model_name)} {mp:.1f}%"
        if i == 0:
            parts_left.append(entry)   # 第一個（佔比最高）放左側
        else:
            parts_right.append(entry)  # 其餘放右側

    tbl.add_row(
        Text.from_markup("  ".join(parts_left) if parts_left else ""),
        Text.from_markup("  ".join(parts_right) if parts_right else ""),
    )
    return tbl


def _kv_table(rows: list[tuple[str, str, Text]]) -> Table:
    """建立 key-value 表格（用於 Burn Rate、Predictions 等區塊）。

    兩欄佈局：

    - 左欄（``min_width=18``）：icon + label
    - 右欄：value（自適應寬度）

    Args:
        rows: ``(icon, label, value_text)`` 三元組清單。
              ``icon`` 為 emoji 圖示，``label`` 為粗體標籤名，
              ``value_text`` 為已設定樣式的 Rich Text。

    Returns:
        Rich Table 物件。
    """
    # 兩欄佈局：[icon+label (固定最小寬) | value (自適應)]
    tbl = Table(
        show_header=False,   # 隱藏欄位標題列
        show_edge=False,     # 隱藏表格外框
        box=None,            # 無邊框樣式
        padding=(0, 1),      # 上下 0、左右 1 字元內距（類似 padding: 0 1ch）
        pad_edge=False,      # 最外側欄位不加額外邊距
        expand=True,         # 展開至父容器寬度
    )
    tbl.add_column("key", no_wrap=True, min_width=18)   # 標籤欄：最小 18 字元，確保對齊
    tbl.add_column("value", no_wrap=True)               # 值欄：自適應剩餘寬度

    for icon, label, val in rows:
        tbl.add_row(
            Text.from_markup(f"{icon} [bold]{label}[/bold]"),
            val,
        )
    return tbl


# ==========================================================
# 面板建構
# ==========================================================
def _create_default_token_display(
    data: dict[str, Any],
    plan: str,
    user_tz: str,
    time_fmt: str,
) -> RenderableType:
    """組裝預設主題的 Token 用量面板。

    面板分為上下兩部分：

    - **上半部**：Cost / Tokens / Messages 三列指標，各含標頭列與全寬進度條
    - **下半部**：響應式雙欄格線

      - 左欄：Models（堆疊色條 + 標籤）+ Burn Rate / Cost Rate
      - 右欄：Reset In（倒數計時進度條）+ Predictions（Token exhaust / Limit resets）

    Args:
        data: ``analyze_usage()`` 回傳的用量資料字典。
        plan: Token 方案等級（``"pro"`` / ``"max5"`` / ``"max20"`` / ``"custom"``）。
        user_tz: IANA 時區名稱（例如 ``"Asia/Taipei"``）。
        time_fmt: 時間格式（``"24h"`` 或 ``"12h"``）。

    Returns:
        Rich Panel 物件，可直接傳入 ``live.update()``。
    """
    from claude_monitor.core.plans import Plans, get_token_limit

    # 取得方案上限
    token_limit: int = get_token_limit(plan)
    cost_limit: float = Plans.get_cost_limit(plan)
    message_limit: int = Plans.get_message_limit(plan)

    # 從用量資料中取出活躍區塊（isActive=True 的那筆）
    blocks: list[dict] = data.get("blocks") or []
    active: dict | None = next((b for b in blocks if b.get("isActive")), None)
    subtitle = f"[dim]{plan} · {user_tz}[/]"

    # -- 無活躍工作階段：顯示累計數據 ----------------------------
    if active is None:
        tot_t = data.get("total_tokens", 0)
        tot_c = data.get("total_cost", 0.0)
        body = Text()
        body.append("No active session\n\n", style="dim italic")
        body.append(f"Cumulative: {tot_t:,} tokens · ${tot_c:.2f}", style="dim")
        return Panel(
            body,
            title="[bold bright_blue]💎 Token Usage[/]",
            subtitle=subtitle,
            border_style="bright_blue",
        )

    # -- 擷取活躍區塊資料 ----------------------------------------
    total_tokens: int = active.get("totalTokens", 0)
    total_cost: float = active.get("costUSD", 0.0)
    sent_messages: int = active.get("sentMessagesCount", 0)
    per_model: dict = active.get("perModelStats") or {}

    burn: dict = active.get("burnRate") or {}
    tokens_per_min: float | None = burn.get("tokensPerMinute")
    cost_per_hour: float | None = burn.get("costPerHour")

    proj: dict = active.get("projection") or {}
    remaining_min: float | None = proj.get("remainingMinutes")

    # -- 時區與重置時間 ------------------------------------------
    try:
        tz_info = ZoneInfo(user_tz)
    except Exception:
        tz_info = _tz.utc  # type: ignore[assignment]

    now = datetime.now(_tz.utc)

    # 解析工作階段的起始與結束時間（ISO 8601 字串 → datetime）
    start_dt_resolved: datetime | None = None
    end_dt_resolved: datetime | None = None
    reset_remain: float | None = None

    start_s: str | None = active.get("startTime")
    end_s: str | None = active.get("endTime")

    if start_s:
        try:
            sdt = datetime.fromisoformat(start_s)
            if sdt.tzinfo is None:
                sdt = sdt.replace(tzinfo=_tz.utc)
            start_dt_resolved = sdt
        except Exception:
            pass

    if end_s:
        try:
            edt = datetime.fromisoformat(end_s)
            if edt.tzinfo is None:
                edt = edt.replace(tzinfo=_tz.utc)
            reset_remain = max(0.0, (edt - now).total_seconds() / 60)
            end_dt_resolved = edt
        except Exception:
            pass

    # ==========================================================
    # 上半部：使用量指標（標頭 + 全寬進度條）
    # ==========================================================
    parts: list[RenderableType] = []

    # 計算三項指標的使用比例
    cost_ratio: float = total_cost / cost_limit if cost_limit else 0
    token_ratio: float = total_tokens / token_limit if token_limit else 0
    msg_ratio: float = sent_messages / message_limit if message_limit else 0

    # 逐一建立標頭 + 進度條 + 空行（每組指標佔 3 行）
    for icon, label, ratio, cur, lim in [
        ("💰", "Cost", cost_ratio, f"${total_cost:.2f}", f"${cost_limit:.2f}"),
        ("📊", "Tokens", token_ratio, f"{total_tokens:,}", f"{token_limit:,}"),
        ("📨", "Messages", msg_ratio, f"{sent_messages:,}", f"{message_limit:,}"),
    ]:
        color = _severity_color(ratio)
        parts.append(_metric_header(icon, label, cur, lim, ratio))   # 第 1 行：標頭（label | value | %）
        parts.append(_AdaptiveBar(ratio, color))                     # 第 2 行：全寬進度條
        parts.append(Text(""))                                       # 第 3 行：空行間隔

    # ==========================================================
    # 下半部：雙欄格線（Models + Rates | Reset In + Predictions）
    # ==========================================================
    # 預先計算：以目前燃燒率推算，在重置前是否會超過費用上限
    cost_will_exceed: bool = bool(
        cost_per_hour is not None
        and reset_remain is not None
        and cost_limit
        and total_cost < cost_limit
        and total_cost + (cost_per_hour / 60 * reset_remain) >= cost_limit
    )

    # -- 左欄：Models + Rates ------------------------------------
    left_col: list[RenderableType] = []

    # 模型分布區塊：堆疊色條 + 標籤
    if per_model:
        total_m: int = sum(
            s.get("input_tokens", 0) + s.get("output_tokens", 0)
            for s in per_model.values()
        )
        if total_m > 0:
            # 依 Token 數由大到小排序，計算各模型的比例與顏色
            models_sorted = sorted(
                per_model.items(),
                key=lambda kv: (
                    kv[1].get("input_tokens", 0) + kv[1].get("output_tokens", 0)
                ),
                reverse=True,
            )
            segments: list[tuple[float, str]] = []
            for model_name, stats in models_sorted:
                mt = stats.get("input_tokens", 0) + stats.get("output_tokens", 0)
                family = _model_family(model_name)
                color = _MODEL_COLORS.get(family, "#4a9eff")
                segments.append((mt / total_m, color))

            left_col.append(Text.from_markup("🤖 [bold]Models[/]"))       # 區塊標題
            left_col.append(_FullWidthStackedBar(segments))               # 堆疊色條（各模型比例）
            left_col.append(_model_labels(per_model, total_m))            # 色條下方的文字標籤

    # 燃燒率區塊：Burn Rate + Cost Rate
    rate_rows: list[tuple[str, str, Text]] = []
    if tokens_per_min is not None:
        # 依速度選擇對應的 emoji 指示器
        velocity: str = (
            "🐌" if tokens_per_min < 50
            else "🚶" if tokens_per_min < 150
            else "🚀" if tokens_per_min < 300
            else "⚡"
        )
        rate_rows.append((
            "🔥", "Burn Rate",
            Text(f"{tokens_per_min:,.0f} tokens/min {velocity}", style="bright_yellow"),
        ))
    if cost_per_hour is not None:
        rate_rows.append((
            "💲", "Cost Rate",
            Text(f"${cost_per_hour / 60:.4f} /min"),
        ))

    if rate_rows:
        if left_col:
            left_col.append(Text(""))       # 與上方 Models 區塊的間隔
        left_col.append(_kv_table(rate_rows))

    # -- 右欄：Reset In + Predictions ----------------------------
    right_col: list[RenderableType] = []

    # Reset In 區塊：倒數計時標頭 + 進度條
    if start_dt_resolved and end_dt_resolved:
        total_s: float = (end_dt_resolved - start_dt_resolved).total_seconds()
        elapsed_s: float = (now - start_dt_resolved).total_seconds()
        reset_ratio: float = elapsed_s / total_s if total_s > 0 else 0
        reset_color: str = _severity_color(reset_ratio)
        h: int = int((reset_remain or 0) // 60)
        m: int = int((reset_remain or 0) % 60)

        # 標頭列：兩欄佈局 [標題 (彈性) | 倒數時間 (靠右)]
        hdr = Table(
            show_header=False, show_edge=False, box=None,  # 無標題、無外框、無邊框
            padding=0, expand=True,                        # 無內距、展開至全寬
        )
        hdr.add_column(ratio=1, no_wrap=True)            # 左欄：彈性填滿（flex: 1）
        hdr.add_column(justify="right", no_wrap=True)    # 右欄：靠右對齊
        hdr.add_row(
            Text.from_markup("🕐 [bold]Reset In[/]"),
            Text(f"{h}h {m:02d}m"),
        )
        right_col.append(hdr)                                       # Reset In 標頭列
        right_col.append(_FullWidthBar(reset_ratio, reset_color))   # 已用時間進度條

    # Predictions 區塊：Token exhaust 預估時間 + Limit resets 時間
    has_exhaust: bool = remaining_min is not None and remaining_min > 0
    has_reset: bool = end_dt_resolved is not None

    if has_exhaust or has_reset:
        pred_rows: list[tuple[str, str, Text]] = []

        # Token 耗盡預估時間
        if has_exhaust:
            exhaust_dt = now + timedelta(minutes=remaining_min)  # type: ignore[arg-type]
            exhaust_str: str = _format_time(exhaust_dt, tz_info, time_fmt)
            exhaust_val = Text()
            exhaust_val.append(exhaust_str, style="red")
            if cost_will_exceed:
                exhaust_val.append("  🚨", style="bold red")
            pred_rows.append(("🔮", "Token exhaust", exhaust_val))

        # 用量上限重置時間
        if has_reset:
            reset_str: str = _format_time(end_dt_resolved, tz_info, time_fmt)  # type: ignore[arg-type]
            pred_rows.append((
                "⏰", "Limit resets",
                Text(reset_str, style="green"),
            ))

        if right_col:
            right_col.append(Text(""))  # 與上方 Reset In 區塊的間隔
        right_col.append(Text.from_markup("🔮 [bold]Predictions[/]"))   # 區塊標題
        right_col.append(_kv_table(pred_rows))                          # 預測資訊表格

    # -- 組合格線 ------------------------------------------------
    # 將左右欄包入響應式格線（寬螢幕並排、窄螢幕堆疊）
    if left_col or right_col:
        parts.append(_ResponsiveGrid(left_col, right_col))

    # -- 嚴重警告（已超限）----------------------------------------
    severe: list[str] = []
    if cost_limit and total_cost >= cost_limit:
        severe.append("🚨  Cost limit exceeded!")
    if token_limit and total_tokens >= token_limit:
        severe.append("🚨  Token limit exceeded!")
    if message_limit and sent_messages >= message_limit:
        severe.append("🚨  Message limit exceeded!")

    if severe:
        parts.append(Text(""))  # 與上方內容的間隔
        for w in severe:
            parts.append(Text(w, style="bold red"))

    # 最外層 Panel：帶標題的邊框容器（類似 CSS border + title）
    return Panel(
        Group(*parts),                                   # 垂直堆疊所有子元件
        title="[bold bright_blue]💎 Token Usage[/]",     # 面板標題（上方居中）
        subtitle=subtitle,                               # 面板副標題（下方居中）
        border_style="bright_blue",                      # 邊框顏色
    )


# ==========================================================
# 公開介面
# ==========================================================
def create_token_display(
    plan: str,
    timezone: str,
    theme: str = "default",
    time_format: str = "24h",
) -> RenderableType:
    """建立 Token 用量顯示面板（本模組的唯一公開函式）。

    根據 ``theme`` 參數選擇面板實作方式：

    - ``"default"``：使用本模組預設的進度條 + 雙欄佈局
    - ``"ccm"``：委託 claude-monitor 的 ``DisplayController`` 渲染原版介面

    Args:
        plan: Token 方案等級（``"pro"`` / ``"max5"`` / ``"max20"`` / ``"custom"``）。
        timezone: IANA 時區名稱（例如 ``"Asia/Taipei"``）。
        theme: 面板主題，``"default"`` 或 ``"ccm"``。
        time_format: 時間格式，``"24h"`` 或 ``"12h"``。

    Returns:
        Rich 可渲染物件（Panel 或 Text）。
    """
    # 嘗試匯入 claude-monitor 的資料分析模組
    try:
        from claude_monitor.data.analysis import analyze_usage
    except ImportError:
        return Text(
            "[!] claude-monitor 未安裝。請執行：pip install claude-monitor",
            style="bold red",
        )

    # 取得用量資料（向前查詢 192 小時，啟用快取避免重複掃描）
    try:
        data: dict = analyze_usage(hours_back=192, use_cache=True)
    except Exception as e:
        return Text(f"[!] Token 資料錯誤：{e}", style="bold red")

    # 預設主題：使用本模組的預設面板
    if theme == "default":
        return _create_default_token_display(data, plan, timezone, time_format)

    # ccm 原版介面：委託 DisplayController 渲染（效果等同 `ccm --view realtime`）
    try:
        from claude_monitor.core.plans import get_token_limit
        from claude_monitor.ui.display_controller import DisplayController

        token_limit: int = get_token_limit(plan)
        dc = DisplayController()
        # 模擬 ccm CLI 的 argparse.Namespace 傳入 DisplayController
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
        return Text(f"[!] ccm 介面錯誤：{e}", style="bold red")
