"""Unit tests for :mod:`u4cht.extract.vendor`.

以合成 Boron 片段驗證：`^` escape、`"..."` / `{...}` 字面、巢狀大括號、
`{{...}}` 剝殼、註解跳過、`'` char 前綴、is_text 過濾、佔位符判斷、排序。
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from u4cht.cli import main
from u4cht.extract.vendor import (
    BoronLiteral,
    build_output_json,
    decode_caret,
    dedupe,
    extract_boron_strings,
    extract_vendor,
    has_placeholder,
    is_text,
    render_report,
)

# ── decode_caret ────────────────────────────────────────────────────────────

def test_decode_caret_basic() -> None:
    assert decode_caret("hello^/world") == "hello\nworld"


def test_decode_caret_all_known() -> None:
    assert decode_caret("^/^-^\"^^^{^}^(^)") == '\n\t"^{}()'


def test_decode_caret_unknown_falls_through() -> None:
    # `^x` 未定義 → 原樣輸出 x
    assert decode_caret("^x") == "x"


def test_decode_caret_trailing_caret_kept() -> None:
    # 尾巴落單 ^（無下一字）應原樣保留
    assert decode_caret("abc^") == "abc^"


# ── extract_boron_strings：quote / brace ────────────────────────────────────

def test_extract_quote_string() -> None:
    res = extract_boron_strings('print "hello"')
    assert res == [(1, "quote", "hello")]


def test_extract_quote_string_with_caret_escape() -> None:
    res = extract_boron_strings('"line1^/line2"')
    assert res == [(1, "quote", "line1\nline2")]


def test_extract_brace_string() -> None:
    res = extract_boron_strings("desc {a wooden torch}")
    assert res == [(1, "brace", "a wooden torch")]


def test_extract_brace_multiline_line_tracking() -> None:
    src = "one\n{alpha\nbeta}\nafter"
    res = extract_boron_strings(src)
    assert res == [(2, "brace", "alpha\nbeta")]


def test_extract_brace_nested_depth() -> None:
    # {outer {inner} tail}：巢狀大括號應保留內層
    res = extract_boron_strings("{outer {inner} tail}")
    assert res == [(1, "brace", "outer {inner} tail")]


def test_extract_brace_double_brace_unwraps() -> None:
    # Boron {{...}} 特例：解碼後外殼被剝掉
    res = extract_boron_strings("{{payload}}")
    assert res == [(1, "brace", "payload")]


def test_extract_brace_escape_kept_via_caret() -> None:
    # ^{ 於大括號內是 escape → decode 後成 {
    res = extract_boron_strings("{a^{b}")
    assert res == [(1, "brace", "a{b")]


# ── extract_boron_strings：註解 / char 跳過 ─────────────────────────────────

def test_line_comment_skipped() -> None:
    src = '; this is comment "not string"\n"real"'
    res = extract_boron_strings(src)
    assert res == [(2, "quote", "real")]


def test_block_comment_skipped_multiline() -> None:
    src = '/* block\ncomment\nwith "fake" */\n"real"'
    res = extract_boron_strings(src)
    assert res == [(4, "quote", "real")]


def test_char_prefix_apostrophe_consumed() -> None:
    # 'foo 是 Boron lit-word；'x' 也不應被當成字串
    res = extract_boron_strings("'foo \"bar\"")
    assert res == [(1, "quote", "bar")]


def test_multiple_literals_in_one_file() -> None:
    src = '"first"\n{second}\n"third"'
    res = extract_boron_strings(src)
    assert res == [
        (1, "quote", "first"),
        (2, "brace", "second"),
        (3, "quote", "third"),
    ]


# ── is_text / has_placeholder ───────────────────────────────────────────────

def test_is_text_requires_letter() -> None:
    assert is_text("hello") is True
    assert is_text("$#@=") is False
    assert is_text("   \n") is False
    assert is_text("123") is False
    assert is_text("$5 gold") is True  # 有字母


def test_has_placeholder_detects_all() -> None:
    assert has_placeholder("@") is True
    assert has_placeholder("%") is True
    assert has_placeholder("$") is True
    assert has_placeholder("#") is True
    assert has_placeholder("=") is True
    assert has_placeholder("costs $gp") is True
    assert has_placeholder("plain text") is False


# ── extract_vendor / dedupe / build_output_json ─────────────────────────────

def _make_vendor_file(tmp_path: Path) -> Path:
    """合成一個 Boron 檔用於整合測試。"""
    text = (
        '; comment\n'                          # line 1
        '"Welcome to @"\n'                     # line 2 (has_placeholder)
        '"Welcome to @"\n'                     # line 3 (dup)
        '{How many =s would you like?}\n'      # line 4 (brace, has =)
        '"Fine!"\n'                            # line 5
        '{{block payload}}\n'                  # line 6 (brace, {{...}} unwrap)
        '"   "\n'                              # line 7 (control: no letters)
        '"$#@="\n'                             # line 8 (control: no letters)
        "'foo\n"                               # line 9 ('foo skipped)
    )
    path = tmp_path / "vendors.b"
    path.write_text(text, encoding="utf-8")
    return path


def test_extract_vendor_end_to_end(tmp_path: Path) -> None:
    path = _make_vendor_file(tmp_path)
    raw = extract_vendor([path])

    # 7 字面：3 個 "Welcome to @" 副本、"How many..."、"Fine!"、"{block payload}"、"   "、"$#@="
    # 實際數：line2,3,4,5,6,7,8 → 7 條
    assert len(raw) == 7
    kinds = [lit.kind for lit in raw]
    assert kinds.count("quote") == 5
    assert kinds.count("brace") == 2
    assert all(lit.file == "vendors.b" for lit in raw)


def test_dedupe_control_and_placeholder(tmp_path: Path) -> None:
    path = _make_vendor_file(tmp_path)
    raw = extract_vendor([path])
    entries, control = dedupe(raw)

    ens = {e.en for e in entries}
    # control 略過：純空白、純符號
    assert "   " not in ens
    assert "$#@=" not in ens
    assert control == 2

    # 應含：Welcome to @, How many =s..., Fine!, block payload
    assert "Welcome to @" in ens
    assert "Fine!" in ens
    assert any("How many =s" in e for e in ens)
    assert "block payload" in ens

    # 「Welcome to @」出現 2 次 → 排最前
    assert entries[0].en == "Welcome to @"
    assert len(entries[0].occurrences) == 2

    # placeholder 檢查
    welcome = next(e for e in entries if e.en == "Welcome to @")
    assert welcome.has_placeholder is True
    fine = next(e for e in entries if e.en == "Fine!")
    assert fine.has_placeholder is False


def test_dedupe_orders_by_freq_then_name() -> None:
    raw = [
        BoronLiteral("v.b", 1, "quote", "beta"),
        BoronLiteral("v.b", 2, "quote", "alpha"),
        BoronLiteral("v.b", 3, "quote", "alpha"),
    ]
    entries, _ = dedupe(raw)
    assert [e.en for e in entries] == ["alpha", "beta"]


def test_build_output_json_shape(tmp_path: Path) -> None:
    path = _make_vendor_file(tmp_path)
    raw = extract_vendor([path])
    entries, control = dedupe(raw)
    payload = build_output_json([path], raw, entries, control)

    assert set(payload.keys()) == {"_meta", "strings"}
    meta = payload["_meta"]
    assert meta["sources"] == ["vendors.b"]
    assert meta["raw_literals"] == 7
    assert meta["control_skipped"] == 2
    assert meta["unique_text_strings"] == 4
    assert set(meta["placeholders"].keys()) == {"@", "%", "$", "#", "=", "$gp", "^/"}


def test_render_report_contains_summary(tmp_path: Path) -> None:
    path = _make_vendor_file(tmp_path)
    raw = extract_vendor([path])
    entries, control = dedupe(raw)
    text = render_report([path], raw, entries, control)
    assert "vendor Boron" in text
    assert "vendors.b" in text
    assert "佔位符對照" in text


# ── CLI ─────────────────────────────────────────────────────────────────────

def test_cli_extract_vendor(tmp_path: Path) -> None:
    path = _make_vendor_file(tmp_path)
    out_json = tmp_path / "vendor.json"
    out_report = tmp_path / "vendor.md"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "extract-vendor",
            "--file",
            str(path),
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
    assert payload["_meta"]["unique_text_strings"] == 4
    assert payload["_meta"]["sources"] == ["vendors.b"]
