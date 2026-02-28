"""多語系訊息定義模組。

使用 ``@dataclass(frozen=True)`` 集中管理所有 UI 字串，
確保新增語系時不會遺漏任何欄位（建構時即強制檢查）。

語系偵測優先順序：

1. CLI 參數 ``--lang zh_TW``（最高優先）
2. 環境變數 ``LANG``、``LC_ALL``（例如 ``zh_TW.UTF-8`` → ``zh_TW``）
3. 預設值 ``"en"``（英文）

支援的語系代碼：

- ``en`` — English
- ``zh_TW`` — 繁體中文
- ``zh_CN`` — 简体中文
- ``ja`` — 日本語
- ``ko`` — 한국어

新增語系步驟：

1. 在 :class:`Messages` 的每個欄位補上翻譯
2. 建立新的模組級實例（例如 ``FR = Messages(...)``）
3. 在 :data:`_REGISTRY` 中註冊語系代碼
"""

from __future__ import annotations

import locale
import os
from dataclasses import dataclass


# ==========================================================
# 訊息資料模型
# ==========================================================
@dataclass(frozen=True)
class Messages:
    """所有 UI 字串的集中定義。

    使用 ``frozen=True`` 確保實例建立後不可修改，
    避免執行期間意外覆寫翻譯文字。

    欄位命名規則：``{模組}_{用途}``，例如 ``token_cost`` 表示
    Token 面板中 Cost 指標的標籤文字。
    """

    # -- Token 面板：面板標題 ------------------------------------
    token_panel_title: str
    token_panel_no_session: str
    token_panel_cumulative: str

    # -- Token 面板：上半部指標標籤 ------------------------------
    token_cost: str
    token_tokens: str
    token_messages: str

    # -- Token 面板：下半部區塊標題 ------------------------------
    token_models: str
    token_burn_rate: str
    token_cost_rate: str
    token_reset_in: str
    token_predictions: str
    token_exhaust: str
    token_limit_resets: str

    # -- Token 面板：超限警告 ------------------------------------
    token_cost_exceeded: str
    token_tokens_exceeded: str
    token_messages_exceeded: str

    # -- Agent 面板：面板標題與狀態 ------------------------------
    agent_panel_title: str
    agent_no_sessions: str
    agent_sessions_subtitle: str

    # -- Agent 狀態標籤 ------------------------------------------
    state_working: str
    state_thinking: str
    state_permission: str
    state_input: str
    state_idle: str

    # -- Agent 狀態描述 ------------------------------------------
    status_waiting_input: str
    status_responding: str
    status_thinking: str

    # -- 工具顯示格式 --------------------------------------------
    tool_reading: str
    tool_editing: str
    tool_writing: str
    tool_running: str
    tool_searching: str
    tool_sub_agent: str
    tool_browsing_web: str
    tool_fetching_web: str
    tool_updating_todos: str

    # -- 時間距離格式 --------------------------------------------
    time_seconds_ago: str
    time_minutes_ago: str
    time_hours_ago: str

    # -- App 頁尾 ------------------------------------------------
    app_footer: str


# ==========================================================
# English
# ==========================================================
EN = Messages(
    # Token 面板
    token_panel_title="Token Usage",
    token_panel_no_session="No active session",
    token_panel_cumulative="Cumulative: {tokens} tokens · ${cost}",
    token_cost="Cost",
    token_tokens="Tokens",
    token_messages="Messages",
    token_models="Models",
    token_burn_rate="Burn Rate",
    token_cost_rate="Cost Rate",
    token_reset_in="Reset In",
    token_predictions="Predictions",
    token_exhaust="Tokens exhausted",
    token_limit_resets="Limit resets",
    token_cost_exceeded="Cost limit exceeded!",
    token_tokens_exceeded="Token limit exceeded!",
    token_messages_exceeded="Message limit exceeded!",
    # Agent 面板
    agent_panel_title="Active Agents",
    agent_no_sessions="No active Claude sessions found",
    agent_sessions_subtitle="{total} sessions | {active} active",
    # Agent 狀態
    state_working="Working",
    state_thinking="Thinking",
    state_permission="Permission",
    state_input="Input",
    state_idle="Idle",
    # 狀態描述
    status_waiting_input="Waiting for input",
    status_responding="Responding...",
    status_thinking="Thinking...",
    # 工具顯示
    tool_reading="Reading: {}",
    tool_editing="Editing: {}",
    tool_writing="Writing: {}",
    tool_running="Running: {}",
    tool_searching="Searching: {}",
    tool_sub_agent="Sub-agent: {}",
    tool_browsing_web="Browsing web",
    tool_fetching_web="Fetching web",
    tool_updating_todos="Updating todos",
    # 時間距離
    time_seconds_ago="{}s ago",
    time_minutes_ago="{}m ago",
    time_hours_ago="{}h ago",
    # App 頁尾
    app_footer="Ctrl+C to exit | Data refresh: {}s",
)


# ==========================================================
# 繁體中文
# ==========================================================
ZH_TW = Messages(
    # Token 面板
    token_panel_title="Token 用量",
    token_panel_no_session="沒有活躍的工作階段",
    token_panel_cumulative="累計：{tokens} Tokens · ${cost}",
    token_cost="費用",
    token_tokens="Token 數",
    token_messages="訊息數",
    token_models="模型分布",
    token_burn_rate="消耗速率",
    token_cost_rate="費用速率",
    token_reset_in="重置倒數",
    token_predictions="預測",
    token_exhaust="Token 耗盡",
    token_limit_resets="額度重置",
    token_cost_exceeded="費用已超過上限！",
    token_tokens_exceeded="Token 已超過上限！",
    token_messages_exceeded="訊息數已超過上限！",
    # Agent 面板
    agent_panel_title="活躍 Agent",
    agent_no_sessions="未偵測到活躍的 Claude 工作階段",
    agent_sessions_subtitle="{total} 個工作階段 | {active} 個活躍",
    # Agent 狀態
    state_working="工作中",
    state_thinking="思考中",
    state_permission="等待授權",
    state_input="等待輸入",
    state_idle="閒置",
    # 狀態描述
    status_waiting_input="等待使用者輸入",
    status_responding="回應中…",
    status_thinking="思考中…",
    # 工具顯示
    tool_reading="讀取：{}",
    tool_editing="編輯：{}",
    tool_writing="寫入：{}",
    tool_running="執行：{}",
    tool_searching="搜尋：{}",
    tool_sub_agent="子代理：{}",
    tool_browsing_web="瀏覽網頁",
    tool_fetching_web="擷取網頁",
    tool_updating_todos="更新待辦事項",
    # 時間距離
    time_seconds_ago="{}秒前",
    time_minutes_ago="{}分鐘前",
    time_hours_ago="{}小時前",
    # App 頁尾
    app_footer="Ctrl+C 離開 | 資料刷新間隔：{}秒",
)


# ==========================================================
# 简体中文
# ==========================================================
ZH_CN = Messages(
    # Token 面板
    token_panel_title="Token 用量",
    token_panel_no_session="没有活跃的工作会话",
    token_panel_cumulative="累计：{tokens} Tokens · ${cost}",
    token_cost="费用",
    token_tokens="Token 数",
    token_messages="消息数",
    token_models="模型分布",
    token_burn_rate="消耗速率",
    token_cost_rate="费用速率",
    token_reset_in="重置倒计时",
    token_predictions="预测",
    token_exhaust="Token 耗尽",
    token_limit_resets="额度重置",
    token_cost_exceeded="费用已超过上限！",
    token_tokens_exceeded="Token 已超过上限！",
    token_messages_exceeded="消息数已超过上限！",
    # Agent 面板
    agent_panel_title="活跃 Agent",
    agent_no_sessions="未检测到活跃的 Claude 工作会话",
    agent_sessions_subtitle="{total} 个会话 | {active} 个活跃",
    # Agent 状态
    state_working="工作中",
    state_thinking="思考中",
    state_permission="等待授权",
    state_input="等待输入",
    state_idle="空闲",
    # 状态描述
    status_waiting_input="等待用户输入",
    status_responding="回应中…",
    status_thinking="思考中…",
    # 工具显示
    tool_reading="读取：{}",
    tool_editing="编辑：{}",
    tool_writing="写入：{}",
    tool_running="执行：{}",
    tool_searching="搜索：{}",
    tool_sub_agent="子代理：{}",
    tool_browsing_web="浏览网页",
    tool_fetching_web="获取网页",
    tool_updating_todos="更新待办事项",
    # 时间距离
    time_seconds_ago="{}秒前",
    time_minutes_ago="{}分钟前",
    time_hours_ago="{}小时前",
    # App 页脚
    app_footer="Ctrl+C 退出 | 数据刷新间隔：{}秒",
)


# ==========================================================
# 日本語
# ==========================================================
JA = Messages(
    # Token パネル
    token_panel_title="トークン使用量",
    token_panel_no_session="アクティブなセッションなし",
    token_panel_cumulative="累計：{tokens} トークン · ${cost}",
    token_cost="コスト",
    token_tokens="トークン数",
    token_messages="メッセージ数",
    token_models="モデル分布",
    token_burn_rate="消費レート",
    token_cost_rate="コストレート",
    token_reset_in="リセットまで",
    token_predictions="予測",
    token_exhaust="トークン不足",
    token_limit_resets="上限リセット",
    token_cost_exceeded="コスト上限を超過しました！",
    token_tokens_exceeded="トークン上限を超過しました！",
    token_messages_exceeded="メッセージ上限を超過しました！",
    # Agent パネル
    agent_panel_title="アクティブエージェント",
    agent_no_sessions="アクティブな Claude セッションが見つかりません",
    agent_sessions_subtitle="{total} セッション | {active} アクティブ",
    # Agent 状態
    state_working="作業中",
    state_thinking="思考中",
    state_permission="承認待ち",
    state_input="入力待ち",
    state_idle="アイドル",
    # 状態説明
    status_waiting_input="ユーザー入力待ち",
    status_responding="応答中…",
    status_thinking="思考中…",
    # ツール表示
    tool_reading="読込：{}",
    tool_editing="編集：{}",
    tool_writing="書込：{}",
    tool_running="実行：{}",
    tool_searching="検索：{}",
    tool_sub_agent="サブエージェント：{}",
    tool_browsing_web="Web 閲覧",
    tool_fetching_web="Web 取得",
    tool_updating_todos="ToDo 更新",
    # 時間距離
    time_seconds_ago="{}秒前",
    time_minutes_ago="{}分前",
    time_hours_ago="{}時間前",
    # App フッター
    app_footer="Ctrl+C で終了 | データ更新間隔：{}秒",
)


# ==========================================================
# 한국어
# ==========================================================
KO = Messages(
    # Token 패널
    token_panel_title="토큰 사용량",
    token_panel_no_session="활성 세션 없음",
    token_panel_cumulative="누적: {tokens} 토큰 · ${cost}",
    token_cost="비용",
    token_tokens="토큰 수",
    token_messages="메시지 수",
    token_models="모델 분포",
    token_burn_rate="소모율",
    token_cost_rate="비용률",
    token_reset_in="리셋까지",
    token_predictions="예측",
    token_exhaust="토큰 소진",
    token_limit_resets="한도 리셋",
    token_cost_exceeded="비용 한도를 초과했습니다!",
    token_tokens_exceeded="토큰 한도를 초과했습니다!",
    token_messages_exceeded="메시지 한도를 초과했습니다!",
    # Agent 패널
    agent_panel_title="활성 에이전트",
    agent_no_sessions="활성 Claude 세션을 찾을 수 없습니다",
    agent_sessions_subtitle="{total}개 세션 | {active}개 활성",
    # Agent 상태
    state_working="작업 중",
    state_thinking="생각 중",
    state_permission="승인 대기",
    state_input="입력 대기",
    state_idle="유휴",
    # 상태 설명
    status_waiting_input="사용자 입력 대기 중",
    status_responding="응답 중…",
    status_thinking="생각 중…",
    # 도구 표시
    tool_reading="읽기: {}",
    tool_editing="편집: {}",
    tool_writing="쓰기: {}",
    tool_running="실행: {}",
    tool_searching="검색: {}",
    tool_sub_agent="서브 에이전트: {}",
    tool_browsing_web="웹 탐색",
    tool_fetching_web="웹 가져오기",
    tool_updating_todos="할 일 업데이트",
    # 시간 거리
    time_seconds_ago="{}초 전",
    time_minutes_ago="{}분 전",
    time_hours_ago="{}시간 전",
    # App 푸터
    app_footer="Ctrl+C로 종료 | 데이터 갱신 간격: {}초",
)


# ==========================================================
# 語系註冊表與偵測
# ==========================================================
_REGISTRY: dict[str, Messages] = {
    "en": EN,
    "zh_TW": ZH_TW,
    "zh_CN": ZH_CN,
    "ja": JA,
    "ko": KO,
}
"""已註冊的語系代碼 → Messages 實例對應表。"""

# 語系別名：將常見的 locale 前綴映射到完整語系代碼
_ALIASES: dict[str, str] = {
    "zh": "zh_TW",     # 「zh」預設對應繁體中文
    "ja_JP": "ja",
    "ko_KR": "ko",
    "en_US": "en",
    "en_GB": "en",
}
"""語系別名對應表。將簡寫或帶地區碼的 locale 映射到 _REGISTRY 中的語系代碼。"""


def detect_lang() -> str:
    """自動偵測使用者語系。

    偵測順序：

    1. 環境變數 ``LC_ALL`` 或 ``LANG``（例如 ``zh_TW.UTF-8`` → ``"zh_TW"``）
    2. Python ``locale.getlocale()`` 的語系代碼
    3. 預設回傳 ``"en"``

    解析邏輯：先取 ``"zh_TW.UTF-8"`` → ``"zh_TW"``（去掉 ``.`` 後綴），
    然後依序嘗試完整代碼（``zh_TW``）、別名（``zh``）、語言前綴（``zh``）。

    Returns:
        語系代碼字串（``"en"``、``"zh_TW"``、``"zh_CN"``、``"ja"``、``"ko"``）。
    """
    for env_key in ("LC_ALL", "LANG"):
        val: str = os.environ.get(env_key, "")
        if val:
            resolved = _resolve_locale(val)
            if resolved:
                return resolved

    # 回退到 Python locale 偵測
    try:
        loc: str = locale.getlocale()[0] or ""
        if loc:
            resolved = _resolve_locale(loc)
            if resolved:
                return resolved
    except Exception:
        pass

    return "en"


def _resolve_locale(raw: str) -> str | None:
    """將原始 locale 字串解析為已註冊的語系代碼。

    嘗試順序：完整代碼 → 別名 → 語言前綴。

    Args:
        raw: 原始 locale 字串（例如 ``"zh_TW.UTF-8"``、``"ja_JP"``、``"ko"``）。

    Returns:
        已註冊的語系代碼，或 ``None``（無法辨識時）。
    """
    # 去掉 encoding 後綴（例如 ".UTF-8"）
    code: str = raw.split(".")[0]

    # 1. 完整代碼直接命中（例如 "zh_TW"、"en"、"ja"）
    if code in _REGISTRY:
        return code

    # 2. 別名命中（例如 "zh" → "zh_TW"、"ja_JP" → "ja"）
    if code in _ALIASES:
        return _ALIASES[code]

    # 3. 語言前綴命中（例如 "zh_HK" → 前綴 "zh" → 別名 "zh_TW"）
    prefix: str = code.split("_")[0]
    if prefix in _REGISTRY:
        return prefix
    if prefix in _ALIASES:
        return _ALIASES[prefix]

    return None


def get_messages(lang: str = "auto") -> Messages:
    """取得指定語系的 Messages 實例。

    Args:
        lang: 語系代碼（``"en"``、``"zh_TW"``、``"zh_CN"``、``"ja"``、``"ko"``）
              或 ``"auto"``（自動偵測）。

    Returns:
        對應語系的 :class:`Messages` 實例。無法辨識時回傳英文。
    """
    if lang == "auto":
        lang = detect_lang()
    # 支援直接傳入別名（例如 "zh"）
    if lang in _ALIASES:
        lang = _ALIASES[lang]
    return _REGISTRY.get(lang, EN)
