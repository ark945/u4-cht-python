"""DOS Ultima IV `.TLK` NPC 對話抽字。

上游對應：`../u4-cht/tools/extract_tlk.py`
資料格式依 xu4 `src/discourse_tlk.cpp` U4Talk_load：

    每個 `.TLK` = 16 record × 288 byte
    每個 record：
        byte 0   askAfter
        byte 1   questionHumility
        byte 2   turnAway
        byte 3+  12 個 null-terminated 字串：
                 name, pronoun, look, job, health,
                 response1, response2,
                 question, yes, no,
                 topic1, topic2

本模組同時複刻 xu4 U4Talk_load 對 `look`（description）的**執行時修飾**：
小寫首字 → `\\n` 換空白 → 補句點 → 特定角色補 "a " —— 使 `en` 值等於
引擎實際輸出（即 H1 lookup 的 key）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---- 常數 ---------------------------------------------------------------

TLK_SIZE = 288
RECORDS_PER_FILE = 16

# DOS `.TLK` 欄位 → talk.json 欄位對應
FIELD_MAP: list[tuple[str, str]] = [
    ("name", "name"),
    ("pronoun", "pronoun"),
    ("look", "description"),
    ("job", "job"),
    ("health", "health"),
    ("response1", "keyword_response_1"),
    ("response2", "keyword_response_2"),
    ("question", "question"),
    ("yes", "question_yes_answer"),
    ("no", "question_no_answer"),
    ("topic1", "keyword_1"),
    ("topic2", "keyword_2"),
]
STRING_FIELDS: list[str] = [t for t, _ in FIELD_MAP]

# 需補 "a " 冠詞的角色（對齊 xu4 U4Talk_load EDIT_A）
_ARTICLE_NAMES: frozenset[str] = frozenset({"Iolo", "Tracie", "Dupre", "Traveling Dan"})


# ---- 資料結構 -----------------------------------------------------------


@dataclass(slots=True)
class TlkRecord:
    """從 `.TLK` 解析出的單一 NPC record（含 header + 12 個字串欄位 + 來源標記）。"""

    tlk_file: str
    conv_index: int
    ask_after: int
    question_humility: int
    turn_away: int
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.fields.get("name", "")


# ---- 純函式 -------------------------------------------------------------


def edit_look(look: str, name: str) -> str:
    """複製 xu4 U4Talk_load 對 look 的執行時修飾。

    - 小寫首字
    - `\\n` 換空白
    - 若末字元非 `.,!?;:` 則補 `.`
    - 若 name 屬 EDIT_A 名單則前綴 "a "

    範例：
        >>> edit_look("A charming bard", "Iolo")
        'a a charming bard.'
        >>> edit_look("Wise mage", "Joshua")
        'wise mage.'
        >>> edit_look("Old man\\nof forest", "Anon")
        'old man of forest.'
    """
    if not look:
        return look
    s = look[0].lower() + look[1:]
    s = s.replace("\n", " ")
    if s and s[-1] not in ".,!?;:":
        s = s + "."
    if name in _ARTICLE_NAMES:
        s = "a " + s
    return s


def parse_record(buf: bytes, tlk_file: str, conv_index: int) -> TlkRecord | None:
    """解一個 288-byte record。回傳 `None` 代表空槽（name 空白）。"""
    if len(buf) < TLK_SIZE:
        return None
    ask_after, question_humility, turn_away = buf[0], buf[1], buf[2]
    body = buf[3:]
    parts = body.split(b"\x00")
    # 取前 12 段以 latin-1 解（原版單位元組）；trail 不足補空字串
    vals: list[str] = []
    for i in range(12):
        raw = parts[i] if i < len(parts) else b""
        vals.append(raw.decode("latin-1"))
    fields_dict = dict(zip(STRING_FIELDS, vals, strict=True))
    if not fields_dict["name"].strip():
        return None
    fields_dict["look"] = edit_look(fields_dict["look"], fields_dict["name"])
    return TlkRecord(
        tlk_file=tlk_file,
        conv_index=conv_index,
        ask_after=ask_after,
        question_humility=question_humility,
        turn_away=turn_away,
        fields=fields_dict,
    )


def parse_tlk_bytes(data: bytes, tlk_file: str) -> list[TlkRecord]:
    """解一整個 `.TLK` 檔案（4608 bytes 通常）。"""
    out: list[TlkRecord] = []
    for idx in range(RECORDS_PER_FILE):
        off = idx * TLK_SIZE
        chunk = data[off : off + TLK_SIZE]
        if len(chunk) < TLK_SIZE:
            break
        rec = parse_record(chunk, tlk_file, idx)
        if rec is not None:
            out.append(rec)
    return out


def norm(s: str) -> str:
    """寬鬆比對：壓平空白、去頭尾、小寫。"""
    return re.sub(r"\s+", " ", s or "").strip().lower()


# ---- 主抽取流程 ----------------------------------------------------------


def extract_tlk_dir(tlk_dir: Path) -> list[TlkRecord]:
    """讀入資料夾內所有 `*.tlk`（含大小寫），依檔名排序抽 NPC。"""
    out: list[TlkRecord] = []
    for path in sorted(tlk_dir.iterdir()):
        if path.suffix.lower() != ".tlk":
            continue
        town = path.stem.upper()
        data = path.read_bytes()
        out.extend(parse_tlk_bytes(data, town))
    return out


def build_bilingual(
    records: list[TlkRecord],
    talk_json_data: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """依 name 對齊 `talk.json`（若提供），產出雙語表 + 對齊報告。

    - `records`：`extract_tlk_dir` 產物
    - `talk_json_data`：`u4remastered/src/talk/talk.json` 內容；`None` 代表不做對齊，
      所有 NPC `talk_json_matched=False`

    回傳 `(bilingual_entries, report_dict)`。輸出結構與上游 `talk_bilingual.json`
    的 `npcs` 陣列完全相同（zh 欄位為空字串，等待翻譯）。
    """
    by_name: dict[str, list[dict[str, Any]]] = {}
    if talk_json_data:
        for entry in talk_json_data:
            key = norm(str(entry.get("name", "")))
            if key:
                by_name.setdefault(key, []).append(entry)

    used_ids: set[int] = set()
    bilingual: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "matched": 0,
        "no_match": 0,
        "text_diffs": [],
        "no_match_list": [],
    }

    for rec in records:
        key = norm(rec.name)
        match: dict[str, Any] | None = None
        for cand in by_name.get(key, []):
            if id(cand) not in used_ids:
                match = cand
                used_ids.add(id(cand))
                break

        entry_fields: dict[str, dict[str, str]] = {}
        diffs: list[dict[str, str]] = []
        for tlk_f, tj_f in FIELD_MAP:
            en = rec.fields[tlk_f]
            entry_fields[tj_f] = {"en": en, "zh": ""}
            if match is not None:
                tj_val = str(match.get(tj_f, ""))
                if norm(en) != norm(tj_val):
                    diffs.append({"field": tj_f, "tlk_en": en, "talk_json": tj_val})

        bilingual.append(
            {
                "tlk_file": rec.tlk_file,
                "conv_index": rec.conv_index,
                "name": rec.name,
                "talk_json_matched": match is not None,
                "header": {
                    "askAfter": rec.ask_after,
                    "questionHumility": rec.question_humility,
                    "turnAway": rec.turn_away,
                },
                "fields": entry_fields,
            }
        )

        if match is not None:
            report["matched"] += 1
            if diffs:
                report["text_diffs"].append(
                    {"name": rec.name, "tlk_file": rec.tlk_file, "diffs": diffs}
                )
        else:
            report["no_match"] += 1
            report["no_match_list"].append(
                {
                    "tlk_file": rec.tlk_file,
                    "conv_index": rec.conv_index,
                    "name_field": rec.name,
                    "job": rec.fields.get("job", ""),
                }
            )

    return bilingual, report


def build_output_json(
    bilingual: list[dict[str, Any]],
    talk_json_ref: str | None = None,
) -> dict[str, Any]:
    """組出最終 JSON dict（含 `_meta` + `npcs`），格式與上游相容。"""
    return {
        "_meta": {
            "source_tlk": "DOS Ultima IV .TLK (ultima4.zip)",
            "reference": talk_json_ref or "(not provided)",
            "npc_count": len(bilingual),
            "field_map": dict(FIELD_MAP),
            "note": (
                "en = DOS .TLK 原文（引擎實際輸出，翻譯 key）；zh 待填。"
                "keyword（topic）預設不譯。"
            ),
        },
        "npcs": bilingual,
    }


def render_report(
    report: dict[str, Any],
    tlk_n: int,
    talk_n: int,
) -> str:
    """把對齊報告 dict 轉成 Markdown。"""
    lines: list[str] = [
        "# .TLK ↔ talk.json 對齊報告",
        "",
        "> 自動產生 by `u4cht extract-tlk`",
        "",
        "## 摘要",
        "",
        f"- DOS `.TLK` 抽出 NPC：**{tlk_n}**",
        f"- 參考 `talk.json` 條目：**{talk_n}**",
        f"- 以 name 對齊成功：**{report['matched']}**",
        f"- 找不到對應（僅 .TLK 有）：**{report['no_match']}**",
        f"- 英文內容有差異的 NPC：**{len(report['text_diffs'])}**",
        "",
    ]
    if report["no_match_list"]:
        lines.extend(
            [
                "## 無對應 NPC",
                "",
                "| TLK | idx | name 欄位（原始） | job |",
                "|---|---|---|---|",
            ]
        )
        for m in report["no_match_list"]:
            nf = re.sub(r"\s+", " ", m["name_field"]).strip()
            jb = re.sub(r"\s+", " ", m["job"]).strip()
            lines.append(f"| {m['tlk_file']} | {m['conv_index']} | `{nf}` | `{jb[:40]}` |")
        lines.append("")
    lines.append("## 英文差異明細（前 40 筆）")
    lines.append("")
    for d in report["text_diffs"][:40]:
        lines.append(f"### {d['name']} ({d['tlk_file']})")
        for x in d["diffs"]:
            tlk = re.sub(r"\s+", " ", x["tlk_en"]).strip()
            tj = re.sub(r"\s+", " ", str(x["talk_json"])).strip()
            lines.append(f"- `{x['field']}`:")
            lines.append(f"    - TLK:  `{tlk[:120]}`")
            lines.append(f"    - JSON: `{tj[:120]}`")
        lines.append("")
    return "\n".join(lines)


# ---- 高階 API（CLI 用） --------------------------------------------------


def run_extract(
    tlk_dir: Path,
    out_bilingual: Path,
    out_report: Path | None = None,
    talk_json_path: Path | None = None,
) -> dict[str, int]:
    """完整抽取流程。回傳統計 dict（供 CLI 印訊息）。"""
    records = extract_tlk_dir(tlk_dir)

    talk_json_data: list[dict[str, Any]] | None = None
    if talk_json_path is not None:
        with talk_json_path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        talk_json_data = [e for e in raw if str(e.get("name", "")).strip()]

    bilingual, report = build_bilingual(records, talk_json_data)
    payload = build_output_json(
        bilingual,
        talk_json_ref=str(talk_json_path) if talk_json_path else None,
    )

    out_bilingual.parent.mkdir(parents=True, exist_ok=True)
    with out_bilingual.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    if out_report is not None:
        out_report.parent.mkdir(parents=True, exist_ok=True)
        md = render_report(
            report,
            tlk_n=len(records),
            talk_n=len(talk_json_data or []),
        )
        out_report.write_text(md, encoding="utf-8")

    return {
        "npc_count": len(records),
        "matched": report["matched"],
        "no_match": report["no_match"],
        "text_diffs": len(report["text_diffs"]),
    }
