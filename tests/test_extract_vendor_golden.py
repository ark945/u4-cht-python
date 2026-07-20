"""Golden 對照：本專案 `extract_vendor` 產出 vs 上游
`../u4-cht/dumps/vendor_bilingual.json` 的 `en`/計數欄位對齊。

雙 gated：
- 需要環境變數 `U4CHT_VENDORS_B` 指向 `vendors.b` 檔（或 `U4CHT_XU4_MODULE_DIR` 指向含之的資料夾）
- 需要 `../u4-cht/dumps/vendor_bilingual.json` 存在

若條件不齊，自動 skip。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from u4cht.extract.vendor import build_output_json, dedupe, extract_vendor

REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_GOLDEN = REPO_ROOT.parent / "u4-cht" / "dumps" / "vendor_bilingual.json"


def _vendors_b() -> Path | None:
    direct = os.environ.get("U4CHT_VENDORS_B")
    if direct:
        p = Path(direct)
        if p.is_file():
            return p
    module_dir = os.environ.get("U4CHT_XU4_MODULE_DIR")
    if module_dir:
        p = Path(module_dir) / "vendors.b"
        if p.is_file():
            return p
    return None


pytestmark = pytest.mark.skipif(
    _vendors_b() is None or not UPSTREAM_GOLDEN.exists(),
    reason=(
        "Golden 對照需要 (a) 環境變數 U4CHT_VENDORS_B 或 U4CHT_XU4_MODULE_DIR 指向 vendors.b，"
        "以及 (b) ../u4-cht/dumps/vendor_bilingual.json 存在。"
    ),
)


@pytest.fixture(scope="module")
def our_payload() -> dict:
    vb = _vendors_b()
    assert vb is not None
    raw = extract_vendor([vb])
    entries, control = dedupe(raw)
    return build_output_json([vb], raw, entries, control)


@pytest.fixture(scope="module")
def upstream_payload() -> dict:
    with UPSTREAM_GOLDEN.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_counts_match(our_payload: dict, upstream_payload: dict) -> None:
    ours = our_payload["_meta"]
    theirs = upstream_payload["_meta"]
    assert ours["raw_literals"] == theirs["raw_literals"]
    assert ours["control_skipped"] == theirs["control_skipped"]
    assert ours["unique_text_strings"] == theirs["unique_text_strings"]
    assert ours["with_placeholder"] == theirs["with_placeholder"]


def test_en_set_matches(our_payload: dict, upstream_payload: dict) -> None:
    our_ens = {s["en"] for s in our_payload["strings"]}
    their_ens = {s["en"] for s in upstream_payload["strings"]}
    missing = their_ens - our_ens
    extra = our_ens - their_ens
    assert not missing and not extra, (
        f"missing({len(missing)}): {list(missing)[:3]!r}  "
        f"extra({len(extra)}): {list(extra)[:3]!r}"
    )


def test_occurrence_counts_match(our_payload: dict, upstream_payload: dict) -> None:
    our_map = {s["en"]: len(s["occurrences"]) for s in our_payload["strings"]}
    their_map = {s["en"]: len(s["occurrences"]) for s in upstream_payload["strings"]}
    mismatches = [
        f"{en!r}: ours={our_map.get(en)} theirs={count}"
        for en, count in their_map.items() if our_map.get(en) != count
    ]
    assert not mismatches, f"{len(mismatches)} 筆不合：{mismatches[:3]}"
