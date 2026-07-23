import json

def test_log_ask_event_roundtrip(storage):
    storage.log_ask_event(
        query="show me notes about my morning routine",
        input_type="text",
        intent="browse",
        time_filter="this_week",
        category_filter="journal",
        k=0,
        retrieved_note_ids=["id1", "id2"],
        answer=None,
        result_count=2,
        analyzer_model="openai:gpt-4o-mini",
        generator_model=None,          # browse → no generation, consistent with answer=None
        analyzer_ms=812,
        retrieval_ms=143,
        generation_ms=None,
    )
    
    with storage._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ask_log"
        ).fetchall()
    
    assert len(rows)==1

    row = rows[0]
    assert row["intent"]== "browse"
    assert row["time_filter"] == "this_week"
    assert row["category_filter"] == "journal"
    assert row["k"] == 0
    assert json.loads(row["retrieved_note_ids"]) == ["id1","id2"]

    assert row["analyzer_model"] == "openai:gpt-4o-mini"
    assert row["generator_model"] is None
    assert row["analyzer_ms"] == 812
    assert row["retrieval_ms"] == 143
    assert row["generation_ms"] is None

    assert row["error"] is None
    assert row["created_at"] is not None

