"""Unit tests for :mod:`u4cht.extract.hardcoded`.

以合成 C++ fixture 驗證解析器語意：C 相鄰字面串接、escape 解碼、
skip_args 邊界、dynamic 分類、format specifier 判斷、排序穩定性。
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from u4cht.cli import main
from u4cht.extract.hardcoded import (
    build_output_json,
    dedupe,
    extract_from_text,
    extract_hardcoded,
    parse_string_literals,
    render_report,
    skip_args,
)

# ── parse_string_literals ───────────────────────────────────────────────────

def test_parse_single_literal() -> None:
    text = '"hello"'
    lit, nxt = parse_string_literals(text, 0)
    assert lit == "hello"
    assert nxt == len(text)


def test_parse_adjacent_literals_concat() -> None:
    text = '"a " "b"'
    lit, _ = parse_string_literals(text, 0)
    assert lit == "a b"


def test_parse_adjacent_across_newline() -> None:
    text = '"first "\n    "second"'
    lit, _ = parse_string_literals(text, 0)
    assert lit == "first second"


def test_parse_escapes() -> None:
    text = r'"\n\t\r\"\\\0"'
    lit, _ = parse_string_literals(text, 0)
    assert lit == "\n\t\r\"\\\0"


def test_parse_preserves_format_specifiers() -> None:
    text = '"%c%s: %d gold%%"'
    lit, _ = parse_string_literals(text, 0)
    assert lit == "%c%s: %d gold%%"


def test_parse_non_literal_returns_none() -> None:
    text = "identifier"
    lit, nxt = parse_string_literals(text, 0)
    assert lit is None
    assert nxt == 0


def test_parse_skips_leading_whitespace() -> None:
    text = '   "hi"'
    lit, _ = parse_string_literals(text, 0)
    assert lit == "hi"


# ── skip_args ───────────────────────────────────────────────────────────────

def test_skip_args_zero_returns_input_position() -> None:
    # count=0 → 立刻返回，不動
    assert skip_args("x, y)", 0, 0) == 0


def test_skip_args_two_commas() -> None:
    # 模擬 screenTextAt(x, y, "fmt")：從 '(' 之後起跳過 2 個引數
    src = 'x, y, "fmt")'
    pos = skip_args(src, 0, 2)
    assert pos is not None
    assert src[pos:].lstrip() == '"fmt")'


def test_skip_args_respects_nested_parens() -> None:
    # 內含函式呼叫的頂層 skipping
    src = 'foo(a, b), "hi")'
    pos = skip_args(src, 0, 1)
    assert pos is not None
    assert src[pos:].lstrip() == '"hi")'


def test_skip_args_respects_string_with_comma() -> None:
    src = '"a, b", 42, "x")'
    pos = skip_args(src, 0, 2)
    assert pos is not None
    assert src[pos:].lstrip() == '"x")'


def test_skip_args_insufficient_returns_none() -> None:
    # 只有 1 個引數但要求跳 2 個
    assert skip_args("a)", 0, 2) is None


# ── extract_from_text ───────────────────────────────────────────────────────

def test_extract_screen_message_basic() -> None:
    src = 'void f() {\n    screenMessage("Hello, world!\\n");\n}\n'
    cs: list = []
    dyn: list = []
    extract_from_text(src, "combat.cpp", cs, dyn)
    assert len(cs) == 1
    assert cs[0].func == "screenMessage"
    assert cs[0].en == "Hello, world!\n"
    assert cs[0].line == 2
    assert cs[0].file == "combat.cpp"
    assert dyn == []


def test_extract_screen_text_at_argpos_2() -> None:
    # screenTextAt 字面在 argv[2]
    src = 'screenTextAt(3, 4, "Codex");\n'
    cs: list = []
    dyn: list = []
    extract_from_text(src, "screen.cpp", cs, dyn)
    assert len(cs) == 1
    assert cs[0].func == "screenTextAt"
    assert cs[0].en == "Codex"


def test_extract_dynamic_first_arg() -> None:
    src = "screenMessage(reply);\nscreenMessage(msg, 1);\n"
    cs: list = []
    dyn: list = []
    extract_from_text(src, "event.cpp", cs, dyn)
    assert cs == []
    assert len(dyn) == 2
    assert {d.line for d in dyn} == {1, 2}


def test_extract_ignores_lookalike_identifier() -> None:
    # 前綴匹配（如 `xscreenMessage`）不應命中
    src = 'void f() { xscreenMessage("no"); }\n'
    cs: list = []
    dyn: list = []
    extract_from_text(src, "x.cpp", cs, dyn)
    assert cs == []
    assert dyn == []


def test_extract_adjacent_literals_concat() -> None:
    src = 'screenMessage("Line1\\n"\n              "Line2\\n");\n'
    cs: list = []
    dyn: list = []
    extract_from_text(src, "game.cpp", cs, dyn)
    assert len(cs) == 1
    assert cs[0].en == "Line1\nLine2\n"


def test_extract_multiple_call_sites_line_numbers() -> None:
    src = 'screenMessage("A");\n\nscreenMessageN("B");\nscreenMessageCenter("C");\n'
    cs: list = []
    dyn: list = []
    extract_from_text(src, "combat.cpp", cs, dyn)
    assert [(c.func, c.line, c.en) for c in cs] == [
        ("screenMessage", 1, "A"),
        ("screenMessageN", 3, "B"),
        ("screenMessageCenter", 4, "C"),
    ]


def test_extract_screen_text_at_insufficient_args_skipped() -> None:
    # screenTextAt 需要至少 3 個引數；此處只有 2 個 → 應被略過
    src = "screenTextAt(1, 2);\n"
    cs: list = []
    dyn: list = []
    extract_from_text(src, "x.cpp", cs, dyn)
    assert cs == []
    assert dyn == []


# ── dedupe / build_output_json ──────────────────────────────────────────────

def _make_src_tree(tmp_path: Path) -> Path:
    """在 tmp_path 建一個小型合成 xu4/src 樹。"""
    root = tmp_path / "src"
    root.mkdir()
    (root / "combat.cpp").write_text(
        'screenMessage("\\n");\nscreenMessage("Attack!");\n',
        encoding="utf-8",
    )
    (root / "game.cpp").write_text(
        'screenMessage("\\n");\n'
        'screenMessage("%d gold");\n'
        'screenTextAt(1, 2, "Codex");\n'
        "screenMessage(reply);\n",
        encoding="utf-8",
    )
    sub = root / "sub"
    sub.mkdir()
    (sub / "event.h").write_text('screenMessageN("hi");\n', encoding="utf-8")
    return root


def test_extract_hardcoded_end_to_end(tmp_path: Path) -> None:
    src_dir = _make_src_tree(tmp_path)
    call_sites, dynamic = extract_hardcoded(src_dir)

    # combat.cpp: 2 字面（"\n", "Attack!"）
    # game.cpp: 3 字面（"\n", "%d gold", "Codex"）+ 1 dynamic（reply）
    # sub/event.h: 1 字面（"hi"）
    assert len(call_sites) == 6
    assert len(dynamic) == 1
    assert dynamic[0].func == "screenMessage"
    assert dynamic[0].file == "game.cpp"


def test_dedupe_orders_by_frequency_then_name(tmp_path: Path) -> None:
    src_dir = _make_src_tree(tmp_path)
    call_sites, _ = extract_hardcoded(src_dir)
    entries = dedupe(call_sites)

    # "\n" 出現 2 次 → 排最前
    assert entries[0].en == "\n"
    assert len(entries[0].occurrences) == 2
    # 其他字串各 1 次；按 en asc
    tail = [e.en for e in entries[1:]]
    assert tail == sorted(tail)


def test_has_format_detection() -> None:
    # 只用字面組出 CallSite 列表，繞過檔案 IO
    from u4cht.extract.hardcoded import CallSite
    cs = [
        CallSite("screenMessage", "a.cpp", 1, "%d gold"),
        CallSite("screenMessage", "a.cpp", 2, "%s says hi"),
        CallSite("screenMessage", "a.cpp", 3, "100%% done"),
        CallSite("screenMessage", "a.cpp", 4, "no fmt here"),
    ]
    entries = {e.en: e for e in dedupe(cs)}
    assert entries["%d gold"].has_format is True
    assert entries["%s says hi"].has_format is True
    assert entries["100%% done"].has_format is True
    assert entries["no fmt here"].has_format is False


def test_build_output_json_shape(tmp_path: Path) -> None:
    src_dir = _make_src_tree(tmp_path)
    call_sites, dynamic = extract_hardcoded(src_dir)
    payload = build_output_json(call_sites, dynamic)

    assert set(payload.keys()) == {"_meta", "strings"}
    meta = payload["_meta"]
    assert meta["total_call_sites_with_literal"] == 6
    assert meta["unique_strings"] == 5  # "\n" dedupe
    assert meta["dynamic_first_arg"] == 1
    assert meta["with_format_specifier"] == 1  # "%d gold"


def test_render_report_contains_summary(tmp_path: Path) -> None:
    src_dir = _make_src_tree(tmp_path)
    call_sites, dynamic = extract_hardcoded(src_dir)
    text = render_report(call_sites, dynamic)
    assert "硬編 screenMessage" in text
    assert "call site" in text
    assert "唯一字串" in text or "唯一" in text


# ── CLI ─────────────────────────────────────────────────────────────────────

def test_cli_extract_hardcoded(tmp_path: Path) -> None:
    src_dir = _make_src_tree(tmp_path)
    out_json = tmp_path / "hardcoded.json"
    out_report = tmp_path / "report.md"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "extract-hardcoded",
            "--src-dir",
            str(src_dir),
            "--out",
            str(out_json),
            "--report",
            str(out_report),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_json.exists()
    assert out_report.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["_meta"]["total_call_sites_with_literal"] == 6
    assert payload["_meta"]["unique_strings"] == 5
    # occurrences 使用 posix path (跨平台一致)
    for entry in payload["strings"]:
        for occ in entry["occurrences"]:
            assert "\\" not in occ["at"]
