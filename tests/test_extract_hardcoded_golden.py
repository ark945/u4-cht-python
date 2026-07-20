"""Golden 對照：本專案 `extract_hardcoded` 產出 vs 上游
`../u4-cht/dumps/hardcoded_strings.json` 的 `en`/計數欄位對齊。

雙 gated：
- 需要環境變數 `U4CHT_XU4_SRC_DIR` 指向 xu4 C/C++ 原始碼目錄
- 需要 `../u4-cht/dumps/hardcoded_strings.json` 存在

若條件不齊，自動 skip。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from u4cht.extract.hardcoded import build_output_json, extract_hardcoded

REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_GOLDEN = REPO_ROOT.parent / "u4-cht" / "dumps" / "hardcoded_strings.json"


def _src_dir() -> Path | None:
    env = os.environ.get("U4CHT_XU4_SRC_DIR")
    if not env:
        return None
    path = Path(env)
    return path if path.is_dir() else None


pytestmark = pytest.mark.skipif(
    _src_dir() is None or not UPSTREAM_GOLDEN.exists(),
    reason=(
        "Golden 對照需要 (a) 環境變數 U4CHT_XU4_SRC_DIR 指向 xu4/src，"
        "以及 (b) ../u4-cht/dumps/hardcoded_strings.json 存在。"
    ),
)


@pytest.fixture(scope="module")
def our_payload() -> dict:
    src_dir = _src_dir()
    assert src_dir is not None
    call_sites, dynamic = extract_hardcoded(src_dir)
    return build_output_json(call_sites, dynamic)


@pytest.fixture(scope="module")
def upstream_payload() -> dict:
    with UPSTREAM_GOLDEN.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_counts_match(our_payload: dict, upstream_payload: dict) -> None:
    ours = our_payload["_meta"]
    theirs = upstream_payload["_meta"]
    assert ours["total_call_sites_with_literal"] == theirs["total_call_sites_with_literal"]
    assert ours["unique_strings"] == theirs["unique_strings"]
    assert ours["with_format_specifier"] == theirs["with_format_specifier"]
    assert ours["dynamic_first_arg"] == theirs["dynamic_first_arg"]


def test_en_set_matches(our_payload: dict, upstream_payload: dict) -> None:
    our_ens = {s["en"] for s in our_payload["strings"]}
    their_ens = {s["en"] for s in upstream_payload["strings"]}
    missing = their_ens - our_ens
    extra = our_ens - their_ens
    assert not missing and not extra, (
        f"missing({len(missing)}): {list(missing)[:5]!r}  "
        f"extra({len(extra)}): {list(extra)[:5]!r}"
    )


def test_occurrence_counts_match(our_payload: dict, upstream_payload: dict) -> None:
    our_map = {s["en"]: len(s["occurrences"]) for s in our_payload["strings"]}
    their_map = {s["en"]: len(s["occurrences"]) for s in upstream_payload["strings"]}
    mismatches: list[str] = []
    for en, count in their_map.items():
        if our_map.get(en) != count:
            mismatches.append(f"{en!r}: ours={our_map.get(en)} theirs={count}")
    assert not mismatches, f"{len(mismatches)} 筆不合：{mismatches[:5]}"
