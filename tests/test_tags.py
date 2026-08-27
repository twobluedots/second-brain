from src.tags import extract_tag_filter, normalize_tag, normalize_tags


def test_extract_tag_filter_pulls_tag_and_leaves_remainder():
    tag, remaining = extract_tag_filter("give me some notes #python")
    assert tag == "python"
    assert remaining == "give me some notes"


def test_extract_tag_filter_no_hash_returns_none_tag():
    tag, remaining = extract_tag_filter("give me some notes python")
    assert tag is None
    assert remaining == "give me some notes python"


def test_extract_tag_filter_bare_tag_only():
    tag, remaining = extract_tag_filter("#python")
    assert tag == "python"
    assert remaining == ""


def test_extract_tag_filter_is_case_sensitive():
    tag, _ = extract_tag_filter("#Python")
    assert tag == "Python"


def test_normalize_tag_still_strips_hash():
    assert normalize_tag("#python") == "python"


def test_normalize_tags_dedupes():
    assert normalize_tags(["python", "#python", "health"]) == ["python", "health"]
