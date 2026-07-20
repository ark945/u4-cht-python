"""`extract/tlk.py` 純函式單元測試（不需 `.TLK` 檔案）。

覆蓋：
- `edit_look` 對 xu4 U4Talk_load 執行時修飾的複刻
- `parse_record` 對 288-byte record 的解析
- `norm` 寬鬆比對
- `build_bilingual` 對齊邏輯（有/無 talk.json）
"""

from __future__ import annotations

from u4cht.extract.tlk import (
    RECORDS_PER_FILE,
    STRING_FIELDS,
    TLK_SIZE,
    build_bilingual,
    edit_look,
    norm,
    parse_record,
    parse_tlk_bytes,
)

# ---- edit_look ---------------------------------------------------------


def test_edit_look_lowercases_first_char() -> None:
    assert edit_look("Wise mage", "Joshua") == "wise mage."


def test_edit_look_replaces_newlines_with_space() -> None:
    assert edit_look("old man\nof forest", "Anon") == "old man of forest."


def test_edit_look_appends_period_when_missing() -> None:
    assert edit_look("Bard", "Anon") == "bard."


def test_edit_look_keeps_existing_punctuation() -> None:
    for term in ".", ",", "!", "?", ";", ":":
        assert edit_look(f"Sage{term}", "Anon") == f"sage{term}"


def test_edit_look_prepends_a_for_edit_a_names() -> None:
    # 對齊 xu4 EDIT_A：Iolo / Tracie / Dupre / Traveling Dan
    assert edit_look("charming bard", "Iolo") == "a charming bard."
    assert edit_look("mighty ranger", "Dupre") == "a mighty ranger."
    assert edit_look("kind healer", "Tracie") == "a kind healer."
    assert edit_look("wandering merchant", "Traveling Dan") == "a wandering merchant."


def test_edit_look_no_prepend_for_normal_names() -> None:
    assert edit_look("charming bard", "Joshua") == "charming bard."


def test_edit_look_empty_returns_empty() -> None:
    assert edit_look("", "Iolo") == ""


# ---- norm ---------------------------------------------------------------


def test_norm_collapses_whitespace() -> None:
    assert norm("  Foo   \n  Bar  ") == "foo bar"


def test_norm_handles_none_like() -> None:
    assert norm("") == ""


# ---- parse_record -------------------------------------------------------


def _build_record_bytes(
    header: tuple[int, int, int],
    strings: list[str],
    total: int = TLK_SIZE,
) -> bytes:
    """組一份符合 288-byte record 格式的 fixture。

    header = (askAfter, questionHumility, turnAway)；strings 應恰好 12 個。
    """
    assert len(strings) == 12, "TLK record 需 12 個字串欄位"
    buf = bytearray()
    buf.extend(bytes(header))
    for s in strings:
        buf.extend(s.encode("latin-1"))
        buf.append(0)
    # padding
    buf.extend(b"\x00" * max(0, total - len(buf)))
    return bytes(buf[:total])


def test_parse_record_happy_path() -> None:
    strings = [
        "Joshua",           # name
        "He",               # pronoun
        "A wise mage",      # look → 會被 edit_look 加工
        "I aid seekers.",   # job
        "Well.",            # health
        "The riddle awaits.",  # response1
        "Seek truth.",      # response2
        "Do you seek wisdom?",  # question
        "Well met!",        # yes
        "A shame.",         # no
        "RIDL",             # topic1
        "TRUE",             # topic2
    ]
    buf = _build_record_bytes((5, 2, 1), strings)
    rec = parse_record(buf, tlk_file="BRITAIN", conv_index=3)

    assert rec is not None
    assert rec.tlk_file == "BRITAIN"
    assert rec.conv_index == 3
    assert rec.ask_after == 5
    assert rec.question_humility == 2
    assert rec.turn_away == 1
    assert rec.name == "Joshua"
    # look 經 edit_look 加工
    assert rec.fields["look"] == "a wise mage."
    assert rec.fields["job"] == "I aid seekers."
    assert rec.fields["topic1"] == "RIDL"
    assert rec.fields["topic2"] == "TRUE"


def test_parse_record_edit_a_name() -> None:
    strings = ["Iolo", "He", "charming bard", *[""] * 9]
    buf = _build_record_bytes((0, 0, 0), strings)
    rec = parse_record(buf, "BRITAIN", 0)
    assert rec is not None
    assert rec.fields["look"] == "a charming bard."


def test_parse_record_empty_slot_returns_none() -> None:
    # name 空白 → 視為空槽
    strings = [""] * 12
    buf = _build_record_bytes((0, 0, 0), strings)
    assert parse_record(buf, "BRITAIN", 0) is None


def test_parse_record_short_buffer_returns_none() -> None:
    assert parse_record(b"\x00" * 100, "BRITAIN", 0) is None


def test_parse_record_all_fields_present() -> None:
    strings = [f"F{i}" for i in range(12)]
    strings[0] = "TestNPC"  # 避免空槽
    buf = _build_record_bytes((0, 0, 0), strings)
    rec = parse_record(buf, "T", 0)
    assert rec is not None
    for name in STRING_FIELDS:
        assert name in rec.fields


# ---- parse_tlk_bytes ----------------------------------------------------


def test_parse_tlk_bytes_16_records() -> None:
    """16 個 record，其中 3 個空槽應被過濾。"""
    parts: list[bytes] = []
    for i in range(RECORDS_PER_FILE):
        if i in (2, 5, 11):
            parts.append(_build_record_bytes((0, 0, 0), [""] * 12))
        else:
            names = [f"NPC{i}"] + [""] * 11
            parts.append(_build_record_bytes((0, 0, 0), names))
    data = b"".join(parts)
    records = parse_tlk_bytes(data, "TEST")
    assert len(records) == RECORDS_PER_FILE - 3
    assert records[0].conv_index == 0
    assert records[0].name == "NPC0"
    # 略過的 index 應不在結果中
    got_indices = {r.conv_index for r in records}
    assert 2 not in got_indices
    assert 5 not in got_indices
    assert 11 not in got_indices


# ---- build_bilingual ----------------------------------------------------


def _make_record(name: str, tlk_file: str = "BRITAIN", idx: int = 0):
    strings = [name] + [""] * 11
    buf = _build_record_bytes((0, 0, 0), strings)
    rec = parse_record(buf, tlk_file, idx)
    assert rec is not None
    return rec


def test_build_bilingual_without_talk_json() -> None:
    recs = [_make_record("Iolo"), _make_record("Gweno", idx=1)]
    bilingual, report = build_bilingual(recs, talk_json_data=None)

    assert len(bilingual) == 2
    assert all(entry["talk_json_matched"] is False for entry in bilingual)
    assert report["matched"] == 0
    assert report["no_match"] == 2

    # 結構檢查：與上游 golden 相容
    first = bilingual[0]
    assert set(first.keys()) == {
        "tlk_file",
        "conv_index",
        "name",
        "talk_json_matched",
        "header",
        "fields",
    }
    # 所有 12 個 talk.json field key 都在
    expected_field_keys = {
        "name",
        "pronoun",
        "description",
        "job",
        "health",
        "keyword_response_1",
        "keyword_response_2",
        "question",
        "question_yes_answer",
        "question_no_answer",
        "keyword_1",
        "keyword_2",
    }
    assert set(first["fields"].keys()) == expected_field_keys
    # 每個 field 都是 {en, zh}
    for f_val in first["fields"].values():
        assert set(f_val.keys()) == {"en", "zh"}
        assert f_val["zh"] == ""


def test_build_bilingual_with_talk_json_matches() -> None:
    recs = [_make_record("Iolo")]
    talk_json = [{"name": "Iolo", "description": "a charming bard."}]
    bilingual, report = build_bilingual(recs, talk_json_data=talk_json)

    assert len(bilingual) == 1
    assert bilingual[0]["talk_json_matched"] is True
    assert report["matched"] == 1
    assert report["no_match"] == 0


def test_build_bilingual_duplicate_names_consume_separately() -> None:
    """同名 NPC 應各配對一個 talk.json 條目（不重複用）。"""
    recs = [_make_record("Guard", idx=0), _make_record("Guard", idx=1)]
    talk_json = [
        {"name": "Guard", "description": "first guard."},
        {"name": "Guard", "description": "second guard."},
    ]
    _bilingual, report = build_bilingual(recs, talk_json_data=talk_json)
    assert report["matched"] == 2
    assert report["no_match"] == 0
