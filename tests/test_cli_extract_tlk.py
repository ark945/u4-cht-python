"""CLI `u4cht extract-tlk` 整合測試（用合成 `.TLK` fixture 檔）。"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from u4cht.cli import main
from u4cht.extract.tlk import RECORDS_PER_FILE, TLK_SIZE


def _make_record(strings: list[str]) -> bytes:
    """組一份 288-byte record（header 全 0，尾部 pad 0）。"""
    assert len(strings) == 12
    buf = bytearray(b"\x00\x00\x00")
    for s in strings:
        buf.extend(s.encode("latin-1"))
        buf.append(0)
    buf.extend(b"\x00" * max(0, TLK_SIZE - len(buf)))
    return bytes(buf[:TLK_SIZE])


def _make_tlk_file(path: Path, npc_names: list[str]) -> None:
    """寫一個含 `npc_names` 前幾個 record、其餘空槽的 .TLK 檔。"""
    parts: list[bytes] = []
    for i in range(RECORDS_PER_FILE):
        strings = [npc_names[i]] + [""] * 11 if i < len(npc_names) else [""] * 12
        parts.append(_make_record(strings))
    path.write_bytes(b"".join(parts))


def test_cli_extract_tlk_end_to_end(tmp_path: Path) -> None:
    tlk_dir = tmp_path / "tlk"
    tlk_dir.mkdir()
    _make_tlk_file(tlk_dir / "britain.tlk", ["Iolo", "Gweno"])
    _make_tlk_file(tlk_dir / "moonglow.tlk", ["Mariah"])

    out_json = tmp_path / "out.json"
    out_report = tmp_path / "report.md"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "extract-tlk",
            "--tlk-dir",
            str(tlk_dir),
            "--out",
            str(out_json),
            "--report",
            str(out_report),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "NPC 抽出：3" in result.output
    assert out_json.exists()
    assert out_report.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["_meta"]["npc_count"] == 3
    names = [n["name"] for n in payload["npcs"]]
    assert names == ["Iolo", "Gweno", "Mariah"]
    # 檔名以 upper case 存
    assert payload["npcs"][0]["tlk_file"] == "BRITAIN"
    assert payload["npcs"][2]["tlk_file"] == "MOONGLOW"

    # 有 talk_json_matched=False（沒提供 talk.json）
    assert all(entry["talk_json_matched"] is False for entry in payload["npcs"])
