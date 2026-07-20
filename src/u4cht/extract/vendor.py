"""靜態抽取 xu4 Boron module 腳本（預設 `vendors.b`）內的字面字串。

複刻 `../u4-cht/tools/extract_vendor_boron.py` 的行為（純文字抽取，不執行 Boron）：

**Boron 字面語法**

- 引號字串 `"..."`：escape 字元為 `^`（非 `\\`）
- 大括號字串 `{...}`：可跨行、可**巢狀**；`^{ ^}` 為 escape
- 註解：`;` 行註解、``/* */`` 區塊註解
- Char/lit-word 前綴 `'`：吞掉一個字元（Boron `'foo` 是 lit-word）

**^ escape 對照表**（CARET）

| 序列 | 解碼 |
|------|------|
| `^/` | `\\n` |
| `^-` | `\\t` |
| `^"` | `"`  |
| `^^` | `^`  |
| `^{` / `^}` | `{` / `}` |
| `^(` / `^)` | `(` / `)` |
| 其他 `^x` | `x`（原樣） |

**過濾規則**

- `is_text(s)`：僅保留含 `[A-Za-z]` 的字面，其餘標為 control 略過
- 佔位符判斷：`\\$gp|[@%#=]|\\$` — vendor 保留符號 `@` 店名、`%` 店主、
  `$` 價格、`#` 數量、`=` 物品名、`$gp` 價格+gp
- 排序：出現次數 desc、en asc

**Boron `{{...}}` 特例**

上游 tokenizer 的巢狀處理會讓 `{{foo}}` 解碼後殘留一層外括號 `{foo}`；
若解碼結果整體被 `{...}` 包住，剝掉最外一層。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

# ── 常數 ────────────────────────────────────────────────────────────────────

CARET: dict[str, str] = {
    "/": "\n", "-": "\t", '"': '"', "^": "^",
    "{": "{", "}": "}", "(": "(", ")": ")",
}

PLACEHOLDER_RE = re.compile(r"\$gp|[@%#=]|\$")
_HAS_LETTER_RE = re.compile(r"[A-Za-z]")


# ── 資料模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BoronLiteral:
    """單一 Boron 字面 raw 記錄。"""

    file: str
    line: int  # 1-based
    kind: str  # "quote" | "brace"
    en: str    # decoded


@dataclass(slots=True)
class VendorEntry:
    """去重後的翻譯條目。"""

    en: str
    zh: str = ""
    kind: str = "quote"
    has_placeholder: bool = False
    occurrences: list[str] = field(default_factory=list)


# ── 純函式 tokenizer ────────────────────────────────────────────────────────

def decode_caret(s: str) -> str:
    """解 Boron `^` escape。"""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "^" and i + 1 < n:
            out.append(CARET.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def extract_boron_strings(text: str) -> list[tuple[int, str, str]]:
    """掃描 Boron 原始碼文字，回傳 `[(line, kind, decoded), ...]`。"""
    result: list[tuple[int, str, str]] = []
    i = 0
    n = len(text)
    line = 1

    while i < n:
        c = text[i]

        if c == "\n":
            line += 1
            i += 1
            continue

        # 行註解 ;
        if c == ";":
            while i < n and text[i] != "\n":
                i += 1
            continue

        # 區塊註解 /* */
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                if text[i] == "\n":
                    line += 1
                i += 1
            i += 2
            continue

        # ' char / lit-word 前綴：吞一格
        if c == "'":
            i += 1
            continue

        # "..." 引號字串
        if c == '"':
            start_line = line
            i += 1
            buf: list[str] = []
            while i < n and text[i] != '"':
                if text[i] == "^" and i + 1 < n:
                    buf.append(text[i])
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if text[i] == "\n":
                    line += 1
                buf.append(text[i])
                i += 1
            i += 1  # 收尾 "
            result.append((start_line, "quote", decode_caret("".join(buf))))
            continue

        # {...} 大括號字串（巢狀）
        if c == "{":
            start_line = line
            depth = 0
            buf = []
            while i < n:
                ch = text[i]
                if ch == "^" and i + 1 < n:
                    buf.append(ch)
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if ch == "{":
                    depth += 1
                    if depth > 1:
                        buf.append(ch)
                    i += 1
                    continue
                if ch == "}":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                    buf.append(ch)
                    i += 1
                    continue
                if ch == "\n":
                    line += 1
                buf.append(ch)
                i += 1
            dec = decode_caret("".join(buf))
            # Boron 雙括號 {{…}} → 剝一層
            st = dec.strip()
            if st.startswith("{") and st.endswith("}"):
                dec = st[1:-1]
            result.append((start_line, "brace", dec))
            continue

        i += 1

    return result


# ── 檔案掃描 + 去重 ─────────────────────────────────────────────────────────

def is_text(s: str) -> bool:
    """僅含字母才視為需要翻譯的真文字。"""
    return bool(_HAS_LETTER_RE.search(s))


def has_placeholder(s: str) -> bool:
    """字串是否含 vendor 佔位符（@ % $ # = $gp）。"""
    return bool(PLACEHOLDER_RE.search(s))


def extract_vendor(files: Sequence[Path]) -> list[BoronLiteral]:
    """掃指定 Boron 檔案清單，回傳所有字面（未過濾、未去重）。"""
    raw: list[BoronLiteral] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line, kind, dec in extract_boron_strings(text):
            raw.append(BoronLiteral(file=path.name, line=line, kind=kind, en=dec))
    return raw


def dedupe(raw: Iterable[BoronLiteral]) -> tuple[list[VendorEntry], int]:
    """依 `en` 去重；回傳 `(entries, control_skipped)`。

    - 非 `is_text` 者列為 control，不入翻譯表
    - 同一 `en` 的 kind 取首次出現值
    """
    uniq: dict[str, VendorEntry] = {}
    control = 0
    for lit in raw:
        if not is_text(lit.en):
            control += 1
            continue
        entry = uniq.get(lit.en)
        if entry is None:
            entry = VendorEntry(
                en=lit.en,
                zh="",
                kind=lit.kind,
                has_placeholder=has_placeholder(lit.en),
                occurrences=[],
            )
            uniq[lit.en] = entry
        entry.occurrences.append(f"{lit.file}:{lit.line}")
    entries = sorted(uniq.values(), key=lambda e: (-len(e.occurrences), e.en))
    return entries, control


# ── 匯出 ────────────────────────────────────────────────────────────────────

def build_output_json(
    files: Sequence[Path],
    raw: Sequence[BoronLiteral],
    entries: Sequence[VendorEntry],
    control_skipped: int,
) -> dict:
    """組上游相容 payload。"""
    ph = sum(1 for e in entries if e.has_placeholder)
    return {
        "_meta": {
            "sources": [p.name for p in files],
            "mechanism": "Boron module 腳本字面(非 u4read_stringtable / 非硬編 C 字面)",
            "raw_literals": len(raw),
            "control_skipped": control_skipped,
            "unique_text_strings": len(entries),
            "with_placeholder": ph,
            "placeholders": {
                "@": "店名", "%": "店主", "$": "價格",
                "#": "數量", "=": "物品名", "$gp": "價格gp",
                "^/": "換行(已解為 \\n)",
            },
            "note": (
                "en = Boron 字面解碼後文字;zh 待填。"
                "佔位符 @ % $ # = $gp 翻譯時保留。"
            ),
        },
        "strings": [
            {
                "en": e.en,
                "zh": e.zh,
                "kind": e.kind,
                "has_placeholder": e.has_placeholder,
                "occurrences": e.occurrences,
            }
            for e in entries
        ],
    }


def render_report(
    files: Sequence[Path],
    raw: Sequence[BoronLiteral],
    entries: Sequence[VendorEntry],
    control_skipped: int,
) -> str:
    """產出 Markdown 報告文字。"""
    ph = sum(1 for e in entries if e.has_placeholder)
    braces = sum(1 for e in entries if e.kind == "brace")

    lines: list[str] = [
        "# vendor Boron 腳本字串抽取報告\n",
        "> 自動產生 by `u4cht extract-vendor`(純文字抽取,不改引擎、不執行 Boron)\n",
        "## 摘要\n",
        f"- 來源:{', '.join(p.name for p in files)}",
        f"- 抽出字面總數:{len(raw)}(含純佔位/空白 control {control_skipped} 筆,不入翻譯表)",
        f"- 唯一真文字字串:**{len(entries)}**(其中大括號多行 {braces} 筆)",
        f"- 含佔位符(`@ % $ # = $gp`,翻譯保留):**{ph}**\n",
        "## 佔位符對照\n",
        "| 符號 | 意義 |", "|---|---|",
        "| `@` | 店名 |", "| `%` | 店主 |", "| `$` | 價格 |",
        "| `#` | 數量 |", "| `=` | 物品名 |", "| `$gp` | 價格 + gp |",
        "\n## 樣本(前 25 唯一字串)\n",
        "| 次數 | kind | 佔位? | 字串 |", "|---|---|---|---|",
    ]
    for e in entries[:25]:
        disp = e.en.replace("\n", "\\n").strip()
        mark = "是" if e.has_placeholder else ""
        lines.append(f"| {len(e.occurrences)} | {e.kind} | {mark} | `{disp[:70]}` |")
    return "\n".join(lines)


# ── CLI 入口 ────────────────────────────────────────────────────────────────

def run_extract(
    files: Sequence[Path],
    out_json: Path,
    report: Path | None = None,
    log: TextIO | None = None,
) -> dict:
    """指令實作：掃 Boron 檔案清單、寫 JSON、（選填）寫報告，回傳 payload。"""
    raw = extract_vendor(files)
    entries, control = dedupe(raw)
    payload = build_output_json(files, raw, entries, control)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(render_report(files, raw, entries, control), encoding="utf-8")

    if log is not None:
        meta = payload["_meta"]
        braces = sum(1 for e in entries if e.kind == "brace")
        print(
            f"raw 字面: {meta['raw_literals']}  "
            f"control: {meta['control_skipped']}  "
            f"唯一真文字: {meta['unique_text_strings']}  "
            f"含佔位: {meta['with_placeholder']}  "
            f"braced: {braces}",
            file=log,
        )
        print(f"→ {out_json}", file=log)
        if report is not None:
            print(f"→ {report}", file=log)

    return payload
