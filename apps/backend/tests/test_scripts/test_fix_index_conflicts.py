import pytest

from scripts.fix_index_conflicts import StaleIndexSelectionRequired, find_same_key_index

pytestmark = pytest.mark.no_db


def index(name: str, **options) -> dict:
    return {"name": name, "key": {"brand_id": 1, "email": 1}, **options}


def test_same_key_index_must_also_match_declared_options():
    want = index(
        "candidate_brand_email_partial",
        unique=True,
        sparse=True,
        partialFilterExpression={"email": {"$type": "string"}},
        collation={"locale": "en", "strength": 2},
    )
    live = {
        "wrong_options": index("wrong_options", unique=True),
        "right_options": index(
            "right_options",
            unique=True,
            sparse=True,
            partialFilterExpression={"email": {"$type": "string"}},
            collation={"locale": "en", "strength": 2},
        ),
    }

    assert find_same_key_index(live, want) == "right_options"


def test_option_drift_requires_explicit_stale_index_selection():
    want = index("candidate_brand_email_partial", unique=True)
    live = {"brand_id_1_email_1": index("brand_id_1_email_1")}

    with pytest.raises(StaleIndexSelectionRequired):
        find_same_key_index(live, want)

    assert find_same_key_index(live, want, "brand_id_1_email_1") == "brand_id_1_email_1"


def test_multiple_indistinguishable_indexes_require_explicit_selection():
    want = index("declared", unique=True)
    live = {
        "old_one": index("old_one", unique=True),
        "old_two": index("old_two", unique=True),
    }

    with pytest.raises(StaleIndexSelectionRequired):
        find_same_key_index(live, want)


def test_explicit_selection_must_have_the_declared_key_pattern():
    want = index("declared", unique=True)
    live = {
        "different_key": {"name": "different_key", "key": {"email": 1}},
        "same_key": index("same_key"),
    }

    with pytest.raises(StaleIndexSelectionRequired):
        find_same_key_index(live, want, "different_key")
