"""工作階段掃描模組 — 偵測所有進行中的 Claude Code 工作階段。

偵測策略：

1. 掃描 ``~/.claude/projects/`` 底下所有專案目錄中的 JSONL 檔案
2. 依據檔案修改時間（mtime）過濾出近期活躍的檔案
3. 以 mtime 新近程度判斷工作階段是否存活
4. 每個符合條件的 JSONL 檔案代表一個 Agent 工作階段

.. note::
    Claude Code 的工作階段紀錄檔格式為 JSONL（每行一筆 JSON），
    檔名即為工作階段的 UUID。同一個專案目錄下可能同時存在多個
    工作階段（例如同時開啟多個 Claude Code 終端）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from claude_code_dashboard.constants import ACTIVE_THRESHOLD_S


@dataclass
class SessionInfo:
    """代表一個已偵測到的 Claude Code 工作階段。

    Attributes:
        jsonl_path: JSONL 紀錄檔的完整路徑。
        session_id: 工作階段 UUID（即 JSONL 檔名去掉副檔名）。
        project_dir: 編碼後的專案目錄名稱，例如 ``-Users-<username>-<workspace>-myproject``。
        project_name: 人類可讀的專案名稱，例如 ``myproject``。
        mtime: JSONL 檔案的最後修改時間（Unix 時間戳記）。
        has_process: 工作階段是否被視為存活（基於 mtime 新近程度）。
        model: 使用中的模型名稱，例如 ``"opus"``、``"sonnet"``。
        age_seconds: 距離上次修改的秒數。
    """
    jsonl_path: Path
    session_id: str
    project_dir: str
    project_name: str
    mtime: float
    has_process: bool
    model: str = ""
    age_seconds: float = 0.0


def scan_sessions(
    idle_timeout_min: int = 10,
    show_all: bool = False,
) -> list[SessionInfo]:
    """掃描所有近期活躍的 Claude Code 工作階段。

    Args:
        idle_timeout_min: 隱藏閒置超過此分鐘數的工作階段。
        show_all: 若為 ``True``，顯示 30 分鐘內的所有工作階段（忽略 idle_timeout_min）。

    Returns:
        工作階段清單，依修改時間由新到舊排序。
    """
    claude_dir: Path = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return []

    now: float = time.time()
    cutoff: float = 30 * 60 if show_all else idle_timeout_min * 60

    candidates: list[SessionInfo] = []
    for project_dir in claude_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_name: str = _extract_project_name(project_dir.name)

        for jsonl_file in project_dir.glob("*.jsonl"):
            # 跳過壓縮/內部檔案（compact 是 Claude 自動產生的壓縮紀錄）
            if "compact" in jsonl_file.name:
                continue

            try:
                mtime: float = jsonl_file.stat().st_mtime
            except OSError:
                continue

            age: float = now - mtime
            if age > cutoff:
                continue

            session_id: str = jsonl_file.stem  # 檔名去掉 .jsonl 即為 UUID

            # 以 mtime 新近程度判斷存活：
            # JSONL 在 ACTIVE_THRESHOLD_S（30 秒）內被寫入 → 視為存活
            has_process: bool = age < ACTIVE_THRESHOLD_S

            candidates.append(SessionInfo(
                jsonl_path=jsonl_file,
                session_id=session_id,
                project_dir=project_dir.name,
                project_name=project_name,
                mtime=mtime,
                has_process=has_process,
                age_seconds=age,
            ))

    # 依修改時間由新到舊排序
    candidates.sort(key=lambda s: s.mtime, reverse=True)
    return candidates


def _extract_project_name(dir_name: str) -> str:
    """從編碼後的目錄名稱萃取人類可讀的專案名稱。

    Claude Code 會將專案路徑以 ``-`` 連接作為目錄名稱，
    例如 ``-Users-alice-Projects-my-app``。
    此函式取最後一段有意義的路徑片段作為顯示名稱。

    範例::

        '-Users-alice-Projects-my-app'   → 'app'
        '-Users-alice-Projects-my-lib'   → 'lib'

    Args:
        dir_name: 編碼後的目錄名稱字串。

    Returns:
        人類可讀的專案名稱。
    """
    parts: list[str] = dir_name.strip("-").split("-")
    if not parts:
        return dir_name

    # 跳過常見路徑前綴（Users, home 等），只保留有意義的片段
    skip: set[str] = {"Users", "home"}
    meaningful: list[str] = []
    for p in parts:
        if p in skip:
            meaningful = []  # 遇到前綴就重置，從下一段開始收集
            continue
        meaningful.append(p)

    return meaningful[-1] if meaningful else dir_name
