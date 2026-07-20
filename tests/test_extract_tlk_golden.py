"""Golden 對照測試：把本專案的 `extract_tlk` 產出與上游 `../u4-cht/dumps/talk_bilingual.json`
的 `en` 欄位比對，確保 byte-for-byte 一致。

雙 gated：
- 需要環境變數 `U4CHT_TLK_DIR` 指向 16 個 `.TLK` 檔的資料夾（版權，不入庫）
- 需要 `../u4-cht/dumps/talk_bilingual.json` 存在（上游 sibling repo）

若條件不齊，測試自動 skip。CI 上通常會 skip；開發者本機備妥 `.TLK` 後才會實跑。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from u4cht.extract.tlk import build_bilingual, extract_tlk_dir

# `../u4-cht/dumps/talk_bilingual.json` 相對本 repo 根目錄
REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_GOLDEN = REPO_ROOT.parent / "u4-cht" / "dumps" / "talk_bilingual.json"


def _tlk_dir() -> Path | None:
    env = os.environ.get("U4CHT_TLK_DIR")
    if not env:
        return None
    path = Path(env)
    return path if path.is_dir() else None


pytestmark = pytest.mark.skipif(
    _tlk_dir() is None or not UPSTREAM_GOLDEN.exists(),
    reason=(
        "Golden 對照需要 (a) 環境變數 U4CHT_TLK_DIR 指向 .TLK 資料夾，"
        "以及 (b) ../u4-cht/dumps/talk_bilingual.json 存在。"
    ),
)


@pytest.fixture(scope="module")
def our_bilingual() -> list[dict]:
    tlk_dir = _tlk_dir()
    assert tlk_dir is not None
    records = extract_tlk_dir(tlk_dir)
    bilingual, _ = build_bilingual(records, talk_json_data=None)
    return bilingual


@pytest.fixture(scope="module")
def upstream_npcs() -> list[dict]:
    with UPSTREAM_GOLDEN.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload["npcs"]


def test_npc_count_matches(our_bilingual: list[dict], upstream_npcs: list[dict]) -> None:
    assert len(our_bilingual) == len(upstream_npcs) == 256


def test_en_fields_match_byte_for_byte(
    our_bilingual: list[dict], upstream_npcs: list[dict]
) -> None:
    """每個 NPC 的每個 fields.<f>.en 都要與上游一致。"""
    mismatches: list[str] = []
    for ours, theirs in zip(our_bilingual, upstream_npcs, strict=True):
        loc = f"{ours['tlk_file']}#{ours['conv_index']}({ours['name']})"
        for field_name, our_val in ours["fields"].items():
            their_val = theirs["fields"][field_name]
            if our_val["en"] != their_val["en"]:
                mismatches.append(
                    f"{loc} field={field_name}\n"
                    f"  ours  : {our_val['en']!r}\n"
                    f"  golden: {their_val['en']!r}"
                )
    assert not mismatches, "en 欄位有 " + str(len(mismatches)) + " 筆不一致：\n" + "\n".join(
        mismatches[:10]
    )


def test_header_fields_match(our_bilingual: list[dict], upstream_npcs: list[dict]) -> None:
    for ours, theirs in zip(our_bilingual, upstream_npcs, strict=True):
        assert ours["header"] == theirs["header"], f"{ours['name']} header differs"


def test_ordering_matches(our_bilingual: list[dict], upstream_npcs: list[dict]) -> None:
    ours_seq = [(n["tlk_file"], n["conv_index"], n["name"]) for n in our_bilingual]
    theirs_seq = [(n["tlk_file"], n["conv_index"], n["name"]) for n in upstream_npcs]
    assert ours_seq == theirs_seq
