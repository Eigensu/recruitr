"""Every Beanie Document is registered, in both of the places that register them.

A model missing from `core/database.py`'s `document_models` does not fail at
startup. It fails the first time something queries it, as
`CollectionWasNotInitialized` — an error that points at Beanie rather than at
the list you forgot. `tests/conftest.py` keeps a second copy of that list, so a
model can equally be registered in the app and missing from the tests, where the
same failure appears only in whichever test happens to touch it first.

Both lists are read out of the source with `ast` rather than imported, because
each is a local inside a function (`init_db`, and the autouse fixture) and
neither is reachable any other way.
"""

import ast
import pathlib

from beanie import Document

from app.modules.recruitment import models as recruitment_models

_BACKEND = pathlib.Path(__file__).resolve().parents[2]


def _registered_models(relative_path: str) -> set[str]:
    """Names in the `document_models` list of one file, however it is written."""
    tree = ast.parse((_BACKEND / relative_path).read_text())
    names: set[str] = set()

    for node in ast.walk(tree):
        # `document_models = [...]` in core/database.py
        if (
            isinstance(node, ast.Assign)
            and any(getattr(target, "id", None) == "document_models" for target in node.targets)
            or isinstance(node, ast.keyword)
            and node.arg == "document_models"
        ):
            value = node.value
        else:
            continue

        if isinstance(value, ast.List):
            names |= {element.id for element in value.elts if isinstance(element, ast.Name)}

    return names


def _recruitment_documents() -> set[str]:
    return {
        name
        for name, obj in vars(recruitment_models).items()
        if isinstance(obj, type)
        and issubclass(obj, Document)
        and obj is not Document
        and obj.__module__ == recruitment_models.__name__
    }


def test_every_recruitment_document_is_registered_with_the_app():
    missing = _recruitment_documents() - _registered_models("app/core/database.py")

    assert not missing, (
        f"Not in core/database.py's document_models: {sorted(missing)}. "
        "They will raise CollectionWasNotInitialized on first query."
    )


def test_the_test_fixture_registers_the_same_models_as_the_app():
    app_models = _registered_models("app/core/database.py")
    test_models = _registered_models("tests/conftest.py")

    assert app_models == test_models, (
        f"Only in the app: {sorted(app_models - test_models)}. "
        f"Only in the tests: {sorted(test_models - app_models)}."
    )


def test_the_lists_were_actually_found():
    # Both readers depend on the shape of code they do not control; finding
    # nothing would make every assertion above vacuously true.
    assert len(_registered_models("app/core/database.py")) > 20
    assert len(_recruitment_documents()) > 15
