"""Golden 對照：本專案 `extract_stringtable` 產出 vs 上游
`../u4-cht/dumps/stringtable_bilingual.json` 的 `en` 欄位 byte-for-byte 一致。

雙 gated：
- 需要環境變數 `U4CHT_DATA_DIR` 指向含 `title.exe` / `avatar.exe` 的資料夾（版權，不入庫）
- 需要 `../u4-cht/dumps/stringtable_bilingual.json` 存在

若條件不齊，自動 skip。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from u4cht.extract.strings import SPECS, extract_stringtable

REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_GOLDEN = REPO_ROOT.parent / "u4-cht" / "dumps" / "stringtable_bilingual.json"


def _data_dir() -> Path | None:
    env = os.environ.get("U4CHT_DATA_DIR")
    if not env:
        return None
    path = Path(env)
    if not path.is_dir():
        return None
    if not (path / "title.exe").exists() or not (path / "avatar.exe").exists():
        return None
    return path


pytestmark = pytest.mark.skipif(
    _data_dir() is None or not UPSTREAM_GOLDEN.exists(),
    reason=(
        "Golden 對照需要 (a) 環境變數 U4CHT_DATA_DIR 指向含 title.exe/avatar.exe "
        "的資料夾，以及 (b) ../u4-cht/dumps/stringtable_bilingual.json 存在。"
    ),
)


@pytest.fixture(scope="module")
def our_sections() -> dict:
    data_dir = _data_dir()
    assert data_dir is not None
    return extract_stringtable(data_dir)


@pytest.fixture(scope="module")
def upstream_sections() -> dict:
    with UPSTREAM_GOLDEN.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload["sections"]


def test_section_names_match(our_sections: dict, upstream_sections: dict) -> None:
    assert set(our_sections.keys()) == set(upstream_sections.keys())


def test_section_counts_match(our_sections: dict, upstream_sections: dict) -> None:
    for spec in SPECS:
        assert our_sections[spec.name]["count"] == upstream_sections[spec.name]["count"]


def test_en_strings_byte_for_byte(our_sections: dict, upstream_sections: dict) -> None:
    mismatches: list[str] = []
    for spec in SPECS:
        ours = our_sections[spec.name]["entries"]
        theirs = upstream_sections[spec.name]["entries"]
        for our_entry, their_entry in zip(ours, theirs, strict=True):
            if our_entry["en"] != their_entry["en"]:
                mismatches.append(
                    f"{spec.name}#{our_entry['idx']}\n"
                    f"  ours  : {our_entry['en']!r}\n"
                    f"  golden: {their_entry['en']!r}"
                )
    assert not mismatches, f"{len(mismatches)} 筆不一致：\n" + "\n".join(mismatches[:10])
