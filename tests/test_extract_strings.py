"""`extract/strings.py` 單元測試。

用合成 mini `title.exe` / `avatar.exe` 驗證：
- `read_strings` 從 offset 讀 null-terminated 字串
- `read_strings(offset=None)` 沿用檔案游標
- `extract_stringtable` 完整流程對 7 個 section 讀出正確筆數
- CLI end-to-end
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from click.testing import CliRunner

from u4cht.cli import main
from u4cht.extract.strings import (
    SPECS,
    build_output_json,
    extract_stringtable,
    read_strings,
)

# ---- read_strings ------------------------------------------------------


def test_read_strings_at_offset() -> None:
    data = b"AAAAA" + b"Hello\x00World\x00Foo\x00" + b"tail"
    fh = io.BytesIO(data)
    got = read_strings(fh, offset=5, count=3)
    assert got == ["Hello", "World", "Foo"]


def test_read_strings_none_continues_cursor() -> None:
    data = b"first\x00second\x00third\x00"
    fh = io.BytesIO(data)
    got1 = read_strings(fh, offset=0, count=1)
    got2 = read_strings(fh, offset=None, count=2)
    assert got1 == ["first"]
    assert got2 == ["second", "third"]


def test_read_strings_latin1() -> None:
    # bytes 0xE0..0xFF 屬 latin-1 (é=0xE9, ñ=0xF1)
    data = b"caf\xe9\x00pi\xf1ata\x00"
    fh = io.BytesIO(data)
    assert read_strings(fh, offset=0, count=2) == ["café", "piñata"]


def test_read_strings_eof_gives_empty_string() -> None:
    """檔案 EOF 時，read(1) 回 b'' → 結束該字串為空。"""
    fh = io.BytesIO(b"abc")  # 沒有 null terminator
    got = read_strings(fh, offset=0, count=2)
    assert got == ["abc", ""]


# ---- extract_stringtable end-to-end -------------------------------------


def _build_mock_exe(offsets_to_strings: dict[int, list[str]], total_size: int) -> bytes:
    """在指定 offset 放 null-terminated 字串串，其他位元組填 0xFF。"""
    buf = bytearray(b"\xff" * total_size)
    for offset, strs in offsets_to_strings.items():
        blob = b"".join(s.encode("latin-1") + b"\x00" for s in strs)
        end = offset + len(blob)
        assert end <= total_size, "offset overflow, bump total_size"
        buf[offset:end] = blob
    return bytes(buf)


def _write_mock_data(tmp_path: Path) -> Path:
    """建一份 `data/` 內含合成 `title.exe` / `avatar.exe`，回傳 data dir。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # title.exe：intro_questions (28) + intro_text (24) + intro_gypsy (15)
    # 順序讀，起點是 17444
    title_start = 17445 - 1
    qs = [f"Q{i}" for i in range(28)]
    txts = [f"T{i}" for i in range(24)]
    gyps = [f"G{i}" for i in range(15)]
    title_blob = (
        b"".join(s.encode() + b"\x00" for s in qs)
        + b"".join(s.encode() + b"\x00" for s in txts)
        + b"".join(s.encode() + b"\x00" for s in gyps)
    )
    title_bytes = bytearray(b"\xff" * (title_start + len(title_blob) + 32))
    title_bytes[title_start : title_start + len(title_blob)] = title_blob
    (data_dir / "title.exe").write_bytes(bytes(title_bytes))

    # avatar.exe：4 段各自獨立 seek
    avatar = _build_mock_exe(
        {
            0x0FC7B: [f"CV{i}" for i in range(11)],
            0x0FEE4: [f"E1_{i}" for i in range(7)],
            0x10187: [f"E2_{i}" for i in range(5)],
            93682: [f"SH{i}" for i in range(24)],
        },
        total_size=93682 + 32 * 24,
    )
    (data_dir / "avatar.exe").write_bytes(avatar)

    return data_dir


def test_extract_stringtable_end_to_end(tmp_path: Path) -> None:
    data_dir = _write_mock_data(tmp_path)
    sections = extract_stringtable(data_dir)

    # 每個 spec 對應 section 都在，count 相符
    for spec in SPECS:
        assert spec.name in sections
        assert sections[spec.name]["count"] == spec.count

    # 抽樣：intro_questions[0].en == "Q0"
    assert sections["intro_questions"]["entries"][0]["en"] == "Q0"
    assert sections["intro_text"]["entries"][0]["en"] == "T0"
    assert sections["intro_gypsy"]["entries"][14]["en"] == "G14"
    assert sections["codex_virtue_questions"]["entries"][10]["en"] == "CV10"
    assert sections["shrine_advice"]["entries"][23]["en"] == "SH23"

    # zh 全空字串
    assert all(
        entry["zh"] == ""
        for section in sections.values()
        for entry in section["entries"]
    )


def test_build_output_json_shape(tmp_path: Path) -> None:
    sections = extract_stringtable(_write_mock_data(tmp_path))
    payload = build_output_json(sections)

    assert set(payload.keys()) == {"_meta", "sections"}
    assert payload["_meta"]["total_strings"] == 28 + 24 + 15 + 11 + 7 + 5 + 24
    assert payload["_meta"]["total_strings"] == 114
    assert set(payload["_meta"]["sources"]) == {"title.exe", "avatar.exe"}


# ---- CLI ---------------------------------------------------------------


def test_cli_extract_strings(tmp_path: Path) -> None:
    data_dir = _write_mock_data(tmp_path)
    out_json = tmp_path / "out.json"
    out_report = tmp_path / "report.md"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "extract-strings",
            "--data-dir",
            str(data_dir),
            "--out",
            str(out_json),
            "--report",
            str(out_report),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "抽出字串總數：114" in result.output
    assert out_json.exists()
    assert out_report.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["_meta"]["total_strings"] == 114
    assert len(payload["sections"]) == 7
