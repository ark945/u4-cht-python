"""靜態抽取 xu4 C/C++ 原始碼內 `screenMessage()` 等文字函式的字面字串。

複刻 `../u4-cht/tools/extract_hardcoded.py` 的行為：

- 目標函式（函式名 → 字面引數 0-based 位置）：
    screenMessage        → argv[0]
    screenMessageN       → argv[0]
    screenMessageCenter  → argv[0]
    screenTextAt         → argv[2]   （x, y, fmt, …）

- 支援 C 相鄰字串自動串接：`screenMessage("a " "b")` → `"a b"`
- 解析 C escape：`\\n \\t \\r \\" \\\\ \\0 \\a \\b \\f \\v \\'` → 真實字元
- 保留 `%s`/`%d`/`%c`/`%u`/`%x`/`%X`/`%%` 等 format specifier 原樣（下游 H1 hook 才處理）
- 第一引數非字面（如變數）→ 記入 dynamic，不入翻譯表
- 掃描副檔名：`.cpp` `.c` `.h`
- 去重後以 (出現次數 desc, en asc) 排序
- `has_format` 判斷式：`%[-0-9.]*[sdcuxX%]`

純靜態分析，不執行 C 前處理器；不追蹤 `#define` / 巨集展開。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

# ── 常數 ────────────────────────────────────────────────────────────────────

FUNCS: dict[str, int] = {
    "screenMessage": 0,
    "screenMessageN": 0,
    "screenMessageCenter": 0,
    "screenTextAt": 2,
}

ESCAPES: dict[str, str] = {
    "n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\",
    "0": "\0", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "'": "'",
}

SOURCE_EXTS: tuple[str, ...] = (".cpp", ".c", ".h")

FORMAT_SPECIFIER_RE = re.compile(r"%[-0-9.]*[sdcuxX%]")

_WHITESPACE = " \t\r\n"


# ── 資料模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CallSite:
    """單一 call site 記錄。"""

    func: str
    file: str  # 相對於 src_dir
    line: int  # 1-based
    en: str


@dataclass(frozen=True, slots=True)
class DynamicSite:
    """第一引數為變數的 call site（不入翻譯表）。"""

    func: str
    file: str
    line: int


@dataclass(slots=True)
class UniqueString:
    """去重後的字串條目。"""

    en: str
    zh: str = ""
    has_format: bool = False
    occurrences: list[dict[str, str]] = field(default_factory=list)


# ── C 字面解析 ──────────────────────────────────────────────────────────────

def parse_string_literals(s: str, i: int) -> tuple[str | None, int]:
    """從 `s[i]` 起解析一或多個相鄰 C 字串字面。

    回傳 `(decoded, next_index)`；若起點非 `"` 回傳 `(None, i)`。
    自動跳過前導空白與相鄰字面之間的空白。
    """
    n = len(s)
    while i < n and s[i] in _WHITESPACE:
        i += 1
    if i >= n or s[i] != '"':
        return None, i

    out: list[str] = []
    while i < n and s[i] == '"':
        i += 1  # skip opening quote
        while i < n and s[i] != '"':
            if s[i] == "\\" and i + 1 < n:
                out.append(ESCAPES.get(s[i + 1], s[i + 1]))
                i += 2
            else:
                out.append(s[i])
                i += 1
        i += 1  # skip closing quote
        # 探測相鄰字面
        j = i
        while j < n and s[j] in _WHITESPACE:
            j += 1
        if j < n and s[j] == '"':
            i = j
        else:
            break
    return "".join(out), i


def skip_args(s: str, i: int, count: int) -> int | None:
    """從 `(` 之後跳過 `count` 個頂層引數（以逗號分隔）。

    回傳最後一個被跳過的逗號**之後**的位置；引數不足回傳 `None`。
    """
    n = len(s)
    depth = 0
    skipped = 0
    while i < n and skipped < count:
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return None
            depth -= 1
        elif c == '"':
            _, i = parse_string_literals(s, i)
            continue
        elif c == "," and depth == 0:
            skipped += 1
        i += 1
    return i


# ── 檔案掃描 ────────────────────────────────────────────────────────────────

def extract_from_text(
    text: str,
    rel_path: str,
    call_sites: list[CallSite],
    dynamic: list[DynamicSite],
) -> None:
    """對單一檔案文字掃描所有目標函式的 call site。"""
    for fname, argpos in FUNCS.items():
        pattern = re.compile(rf"\b{re.escape(fname)}\s*\(")
        for m in pattern.finditer(text):
            i = m.end()  # 位於 '(' 之後
            if argpos > 0:
                skipped = skip_args(text, i, argpos)
                if skipped is None:
                    continue
                i = skipped
            lit, _ = parse_string_literals(text, i)
            line = text.count("\n", 0, m.start()) + 1
            if lit is None:
                dynamic.append(DynamicSite(func=fname, file=rel_path, line=line))
            else:
                call_sites.append(CallSite(func=fname, file=rel_path, line=line, en=lit))


def iter_source_files(src_dir: Path) -> Iterable[Path]:
    """遞迴列出 `src_dir` 底下所有 C/C++ 原始檔（排序穩定）。"""
    files: list[Path] = []
    for path in src_dir.rglob("*"):
        if path.is_file() and path.suffix in SOURCE_EXTS:
            files.append(path)
    files.sort()
    return files


def extract_hardcoded(src_dir: Path) -> tuple[list[CallSite], list[DynamicSite]]:
    """掃描 `src_dir` 下所有 C/C++ 原始檔，回傳 (call_sites, dynamic)。"""
    call_sites: list[CallSite] = []
    dynamic: list[DynamicSite] = []
    for path in iter_source_files(src_dir):
        rel = path.relative_to(src_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        extract_from_text(text, rel, call_sites, dynamic)
    return call_sites, dynamic


# ── 去重 + 匯出 ─────────────────────────────────────────────────────────────

def dedupe(call_sites: list[CallSite]) -> list[UniqueString]:
    """以 `en` 去重，回傳依 (出現次數 desc, en asc) 排序後的清單。"""
    uniq: dict[str, UniqueString] = {}
    for cs in call_sites:
        entry = uniq.get(cs.en)
        if entry is None:
            entry = UniqueString(
                en=cs.en,
                zh="",
                has_format=bool(FORMAT_SPECIFIER_RE.search(cs.en)),
                occurrences=[],
            )
            uniq[cs.en] = entry
        entry.occurrences.append({"func": cs.func, "at": f"{cs.file}:{cs.line}"})
    return sorted(uniq.values(), key=lambda e: (-len(e.occurrences), e.en))


def build_output_json(
    call_sites: list[CallSite],
    dynamic: list[DynamicSite],
) -> dict:
    """組出與上游 `dumps/hardcoded_strings.json` 相容的 payload。"""
    entries = dedupe(call_sites)
    fmt_n = sum(1 for e in entries if e.has_format)
    return {
        "_meta": {
            "source": "xu4/src(靜態抽取 screenMessage/N/Center/TextAt 字面)",
            "total_call_sites_with_literal": len(call_sites),
            "unique_strings": len(entries),
            "with_format_specifier": fmt_n,
            "dynamic_first_arg": len(dynamic),
            "note": (
                "en = 硬編格式字串(含 %s/%d、\\n);zh 待填。"
                "含 % 者於 H1 hook 需 format-aware 處理"
                "(post-vsnprintf 比對 / fragment 替換)。"
            ),
        },
        "strings": [
            {
                "en": e.en,
                "zh": e.zh,
                "has_format": e.has_format,
                "occurrences": e.occurrences,
            }
            for e in entries
        ],
    }


def render_report(
    call_sites: list[CallSite],
    dynamic: list[DynamicSite],
) -> str:
    """產出 Markdown 報告文字（等價上游輸出）。"""
    entries = dedupe(call_sites)
    fmt_n = sum(1 for e in entries if e.has_format)

    by_func: dict[str, int] = {}
    for cs in call_sites:
        by_func[cs.func] = by_func.get(cs.func, 0) + 1

    lines: list[str] = [
        "# 硬編 screenMessage 字串抽取報告\n",
        "> 自動產生 by `u4cht extract-hardcoded`(純靜態分析,不改引擎)\n",
        "## 摘要\n",
        f"- 有字面引數的 call site:**{len(call_sites)}**",
        f"- 去重後唯一字串:**{len(entries)}**",
        f"- 含 format specifier(`%s`/`%d`…,需 format-aware hook):**{fmt_n}**",
        f"- 第一引數為變數(dynamic,不入翻譯表):**{len(dynamic)}**\n",
        "### 各函式 call site(有字面)\n",
        "| 函式 | 數 |",
        "|---|---|",
    ]
    for func, count in sorted(by_func.items(), key=lambda x: -x[1]):
        lines.append(f"| `{func}` | {count} |")

    lines.append("\n## 最高頻字串(前 25)\n")
    lines.append("| 次數 | format? | 字串(escape 顯示) |")
    lines.append("|---|---|---|")
    for e in entries[:25]:
        disp = e.en.replace("\n", "\\n").replace("\t", "\\t")
        mark = "是" if e.has_format else ""
        lines.append(f"| {len(e.occurrences)} | {mark} | `{disp[:70]}` |")

    lines.append("\n## Dynamic(第一引數為變數)前 15 筆\n")
    lines.append(
        "這些 call 的文字來自 runtime 變數(如對話 reply / 角色名),"
        "走 H1 hook 的查表 + fragment 替換,不在硬編表內。\n"
    )
    for d in dynamic[:15]:
        lines.append(f"- `{d.func}` @ {d.file}:{d.line}")

    return "\n".join(lines)


# ── CLI 入口 ────────────────────────────────────────────────────────────────

def run_extract(
    src_dir: Path,
    out_json: Path,
    report: Path | None = None,
    log: TextIO | None = None,
) -> dict:
    """指令實作：掃 `src_dir`、寫 JSON、（選填）寫報告，回傳 payload。"""
    call_sites, dynamic = extract_hardcoded(src_dir)
    payload = build_output_json(call_sites, dynamic)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(render_report(call_sites, dynamic), encoding="utf-8")

    if log is not None:
        meta = payload["_meta"]
        print(
            f"call site(字面): {meta['total_call_sites_with_literal']}  "
            f"唯一: {meta['unique_strings']}  "
            f"含 format: {meta['with_format_specifier']}  "
            f"dynamic: {meta['dynamic_first_arg']}",
            file=log,
        )
        print(f"→ {out_json}", file=log)
        if report is not None:
            print(f"→ {report}", file=log)

    return payload
