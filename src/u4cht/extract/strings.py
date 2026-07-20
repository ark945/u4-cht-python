"""DOS Ultima IV `title.exe` / `avatar.exe` stringtable 抽字。

上游對應：`../u4-cht/tools/extract_stringtable.py`
機制依 xu4 `src/u4file.cpp:u4read_stringtable`：從指定 offset 讀 N 個
null-terminated 字串（`latin-1`）。

**關鍵陷阱**：`title.exe` 三段（intro_questions / intro_text / intro_gypsy）
是**順序讀** — 對應 xu4 中 `offset == -1` 語意「沿用檔案游標接續前一段」。
Python 端以 `offset=None` 表達，讀取時共用同一個 file handle。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

# ---- 規格常數 -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """單一 stringtable 區段規格。"""

    name: str
    filename: str          # "title.exe" or "avatar.exe"
    offset: int | None     # None = 沿用檔案游標接續前一段
    count: int
    description: str


# 依 xu4 src/{intro,codex,shrine}.cpp 抽取
SPECS: tuple[SectionSpec, ...] = (
    # title.exe — intro / 角色創建（順序讀）
    SectionSpec(
        name="intro_questions",
        filename="title.exe",
        offset=17445 - 1,
        count=28,
        description="intro.cpp:101 角色創建美德問題（gypsy 抽牌題目）",
    ),
    SectionSpec(
        name="intro_text",
        filename="title.exe",
        offset=None,
        count=24,
        description="intro.cpp:102 開場故事字幕",
    ),
    SectionSpec(
        name="intro_gypsy",
        filename="title.exe",
        offset=None,
        count=15,
        description="intro.cpp:103 gypsy 抽牌旁白",
    ),
    # avatar.exe — codex / endgame / shrine
    SectionSpec(
        name="codex_virtue_questions",
        filename="avatar.exe",
        offset=0x0FC7B,
        count=11,
        description="codex.cpp:43 知識寶典美德問答",
    ),
    SectionSpec(
        name="endgame_text1",
        filename="avatar.exe",
        offset=0x0FEE4,
        count=7,
        description="codex.cpp:44 結局文字 1",
    ),
    SectionSpec(
        name="endgame_text2",
        filename="avatar.exe",
        offset=0x10187,
        count=5,
        description="codex.cpp:45 結局文字 2",
    ),
    SectionSpec(
        name="shrine_advice",
        filename="avatar.exe",
        offset=93682,
        count=24,
        description="shrine.cpp:54 聖壇冥想建議",
    ),
)


# ---- 純函式 -------------------------------------------------------------


def read_strings(fh: BinaryIO, offset: int | None, count: int) -> list[str]:
    """從 `fh` 讀 `count` 個 null-terminated 字串（`latin-1`）。

    - `offset is None` → 沿用檔案目前游標
    - `offset is not None` → `fh.seek(offset)` 後再讀
    """
    if offset is not None:
        fh.seek(offset)
    out: list[str] = []
    for _ in range(count):
        buf = bytearray()
        while True:
            c = fh.read(1)
            if c in (b"\x00", b""):
                break
            buf += c
        out.append(buf.decode("latin-1"))
    return out


def _source_label(offset: int | None) -> str:
    """給報告用的 offset 字樣。"""
    if offset is None:
        return "continue"
    if offset > 0xFFF:
        return hex(offset)
    return str(offset)


# ---- 主抽取流程 ----------------------------------------------------------


def extract_stringtable(data_dir: Path) -> dict[str, Any]:
    """從 `data_dir` 抽全部 7 個 section，回傳完整 sections dict。

    File handle 對每個檔名共用，以支援 `offset=None` 的順序讀語意。
    """
    handles: dict[str, BinaryIO] = {}
    sections: dict[str, dict[str, Any]] = {}
    try:
        for spec in SPECS:
            fh = handles.get(spec.filename)
            if fh is None:
                fh = handles[spec.filename] = (data_dir / spec.filename).open("rb")
            strings = read_strings(fh, spec.offset, spec.count)
            sections[spec.name] = {
                "source": f"{spec.filename} @ {_source_label(spec.offset)}",
                "desc": spec.description,
                "count": len(strings),
                "entries": [
                    {"idx": i, "en": s, "zh": ""} for i, s in enumerate(strings)
                ],
            }
    finally:
        for fh in handles.values():
            fh.close()
    return sections


def build_output_json(sections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """組出最終 JSON dict（含 `_meta` + `sections`），格式與上游相容。"""
    total = sum(s["count"] for s in sections.values())
    return {
        "_meta": {
            "sources": ["title.exe", "avatar.exe"],
            "mechanism": "u4read_stringtable (xu4 src/u4file.cpp:578)",
            "total_strings": total,
            "note": (
                "en = DOS exe 原文（= H8/codex/shrine hook 的 lookup key）；zh 待填。"
                "title.exe 三段為順序讀。vendor 文字不在此（走 Boron module 腳本）。"
            ),
        },
        "sections": sections,
    }


def render_report(sections: dict[str, dict[str, Any]]) -> str:
    """把抽取結果轉成 Markdown 報告。"""
    total = sum(s["count"] for s in sections.values())
    lines: list[str] = [
        "# u4read_stringtable 字串抽取報告",
        "",
        "> 自動產生 by `u4cht extract-strings`（純資料抽取，不改引擎）",
        "",
        "## 摘要",
        "",
        "- 來源：`title.exe`、`avatar.exe`（`ultima4.zip`，Origin © 1985，不入庫）",
        "- 機制：`u4read_stringtable`（`src/u4file.cpp:578`）",
        f"- 抽出字串總數：**{total}**",
        "",
        "| section | 來源 | 數量 | 說明 |",
        "|---|---|---|---|",
    ]
    for spec in SPECS:
        s = sections[spec.name]
        lines.append(
            f"| `{spec.name}` | {s['source']} | {s['count']} | {spec.description} |"
        )
    lines.extend(["", "## 各段首句樣本", ""])
    for spec in SPECS:
        s = sections[spec.name]
        sample = (s["entries"][0]["en"] if s["entries"] else "").replace("\n", " ")
        lines.append(f"- **{spec.name}**：`{sample[:90]}`")
    lines.extend(
        [
            "",
            "## 尚未涵蓋（後續純資料項）",
            "",
            "- **vendor 文字**：xu4 不走 `u4read_stringtable`，在 Boron module 腳本"
            "（`module/Ultima-IV/*.b` / `script_boron.cpp`）。見 `extract-vendor`。",
            "- **硬編 `screenMessage` 字面**：見 `extract-hardcoded`。",
        ]
    )
    return "\n".join(lines)


# ---- 高階 API（CLI 用） --------------------------------------------------


def run_extract(
    data_dir: Path,
    out_bilingual: Path,
    out_report: Path | None = None,
) -> dict[str, int]:
    """完整抽取流程。回傳統計 dict（供 CLI 印訊息）。"""
    sections = extract_stringtable(data_dir)
    payload = build_output_json(sections)

    out_bilingual.parent.mkdir(parents=True, exist_ok=True)
    with out_bilingual.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    if out_report is not None:
        out_report.parent.mkdir(parents=True, exist_ok=True)
        out_report.write_text(render_report(sections), encoding="utf-8")

    return {
        "total": payload["_meta"]["total_strings"],
        **{spec.name: sections[spec.name]["count"] for spec in SPECS},
    }
