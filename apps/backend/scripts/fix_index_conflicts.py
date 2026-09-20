"""Repair index option drift that forces init_beanie into skip_indexes=True.

Usage:
    python3 scripts/fix_index_conflicts.py            # dry run, changes nothing
    python3 scripts/fix_index_conflicts.py --confirm  # apply
    python3 scripts/fix_index_conflicts.py --stale-index COLLECTION DECLARED LIVE

MongoDB will not change an existing index's options via createIndex — if a
model redefines an index that already exists (same name, different unique /
partialFilterExpression / sparse / TTL / key spec), creation fails with
IndexOptionsConflict (85) or IndexKeySpecsConflict (86). That single failure
makes the app fall back to skip_indexes=True, which disables index sync for
every model, not just the one that conflicted (see app/core/database.py).

Unlike fix_ttl_indexes.py (which only compares expireAfterSeconds), this
compares the full set of index-defining options, so it also catches cases
like a unique index gaining a partialFilterExpression (e.g. Candidate.email
becoming optional) that the TTL-only script doesn't detect.

This always drops and recreates (no in-place collMod path) since option
changes beyond TTL generally aren't collMod-able. For a unique index there is
a brief window with no uniqueness constraint enforced — acceptable for a
one-off repair, called out here so it isn't run blindly during peak traffic.
"""

import argparse
import pathlib
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.core.config import settings  # noqa: E402

# Option keys that define an index's behavior (as opposed to bookkeeping
# fields like 'v' or 'ns' that Mongo adds to the live listing). Deliberately
# excludes 'key' — that's compared separately in diff() and must never reach
# create_index() as a kwarg (it's a positional arg there, not an option).
COMPARABLE_KEYS = [
    "unique",
    "sparse",
    "partialFilterExpression",
    "expireAfterSeconds",
    "collation",
]


class StaleIndexSelectionRequired(ValueError):
    """Raised when a stale same-key index cannot be selected safely."""

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        super().__init__("stale index selection required")


def _describe_uri(uri: str) -> str:
    """A connection string with any embedded credentials stripped, safe to print.

    mongodb:// URIs can carry a username:password same as mongodb+srv://, so
    this sanitizes both rather than only special-casing Atlas.
    """
    parts = urlsplit(uri)
    host = parts.hostname or "?"
    if parts.port:
        host = f"{host}:{parts.port}"
    label = "ATLAS (production)" if parts.scheme == "mongodb+srv" else host
    return f"{label} [{parts.scheme}]"


def declared_indexes() -> list[tuple[str, dict]]:
    """(collection, index document) for every index declared on a Beanie model."""
    from beanie import Document

    from app.core.database import init_db  # noqa: F401  (ensures model modules import)

    def walk(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from walk(sub)

    out = []
    for model in walk(Document):
        st = getattr(model, "Settings", None)
        coll = getattr(st, "name", None)
        for im in getattr(st, "indexes", None) or []:
            if not coll:
                continue
            # Settings.indexes may also hold a bare field name or a
            # [(field, direction), ...] list per Beanie's docs — only
            # IndexModel has .document. Every index in this codebase is
            # declared as IndexModel today; fail loudly with the model name
            # rather than silently skipping if that ever changes, since a
            # skipped index here reads as "already correct".
            if not hasattr(im, "document"):
                raise TypeError(
                    f"{model.__name__}.Settings.indexes has a non-IndexModel entry "
                    f"({im!r}) — this script only supports IndexModel-declared indexes."
                )
            out.append((coll, im.document))
    return out


def _key_items(index: dict) -> list:
    """An index's key spec as a comparable list of (field, direction) pairs."""
    return list((index.get("key") or {}).items())


def find_same_key_index(
    live: dict[str, dict], want: dict, explicit_name: str | None = None
) -> str | None:
    """Find the unambiguous same-key, same-options index under another name.

    MongoDB refuses createIndex when the requested key pattern already exists
    under another name — IndexOptionsConflict (85), "Index already exists with
    a different name". Renaming an index is not a thing, so the only repair is
    to drop the old one and create the declared one.

    This is the case matching purely on name misses, and it misses it in the
    worst possible direction: the declared name is absent, so the index reads
    as "not created yet, init_beanie will make it on the next boot" — while
    every boot fails on precisely this conflict and degrades to skip_indexes.
    Candidate's brand_id+email index is the live example: it gained a
    partialFilterExpression and an explicit name when email became optional,
    and the original auto-named brand_id_1_email_1 was never dropped.

    A key pattern alone is not enough to choose an index to delete: MongoDB can
    expose multiple same-key definitions whose behavior differs by uniqueness,
    sparsity, partial filter, TTL, or collation. Only select automatically when
    exactly one candidate also matches every declared option. Option drift or
    otherwise indistinguishable candidates require an explicit operator choice.
    """
    want_key = _key_items(want)
    candidates = {
        name: live_index
        for name, live_index in live.items()
        if name not in {"_id_", want.get("name")} and _key_items(live_index) == want_key
    }
    if explicit_name is not None:
        if explicit_name not in candidates:
            raise StaleIndexSelectionRequired(list(candidates))
        return explicit_name

    if not candidates:
        return None

    option_matches = [
        name
        for name, live_index in candidates.items()
        if all(live_index.get(key) == want.get(key) for key in COMPARABLE_KEYS)
    ]
    if len(option_matches) == 1:
        return option_matches[0]
    raise StaleIndexSelectionRequired(list(candidates))


def diff(live: dict, want: dict) -> dict:
    """Option and key-spec drift between a live index and its declared definition.

    Key spec (which fields, and in what order/direction) is compared
    separately from COMPARABLE_KEYS: it can't collMod, it can't be passed to
    create_index() as a kwarg (that call takes it positionally), but drift in
    it is exactly the kind of thing this script exists to catch — a model
    that quietly gained or reordered a compound-index field previously read
    as "already correct" because only unique/sparse/etc were compared.
    """
    changed = {}
    live_key, want_key = _key_items(live), _key_items(want)
    if live_key != want_key:
        changed["key"] = (live_key, want_key)
    for key in COMPARABLE_KEYS:
        have, need = live.get(key), want.get(key)
        if have != need:
            changed[key] = (have, need)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the changes")
    ap.add_argument(
        "--stale-index",
        action="append",
        nargs=3,
        default=[],
        metavar=("COLLECTION", "DECLARED", "LIVE"),
        help="explicitly choose the live index to replace for an ambiguous declared index",
    )
    args = ap.parse_args()

    explicit_stale = {}
    for coll, declared_name, live_name in args.stale_index:
        key = (coll, declared_name)
        if key in explicit_stale and explicit_stale[key] != live_name:
            ap.error(f"conflicting --stale-index selections for {coll}.{declared_name}")
        explicit_stale[key] = live_name

    uri = settings.MONGODB_URI
    print(f"cluster : {_describe_uri(uri)}")
    print(f"database: {settings.MONGODB_DB_NAME}")
    print(f"mode    : {'APPLY' if args.confirm else 'dry run (nothing will change)'}\n")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGODB_DB_NAME]

    todo = []
    selection_errors = False
    used_explicit = set()
    for coll, want in declared_indexes():
        if coll not in db.list_collection_names():
            continue
        live = {i["name"]: i for i in db[coll].list_indexes()}
        name = want.get("name")
        if name not in live:
            selection_key = (coll, name)
            explicit_name = explicit_stale.get(selection_key)
            if explicit_name is not None:
                used_explicit.add(selection_key)
            try:
                stale = find_same_key_index(live, want, explicit_name)
            except StaleIndexSelectionRequired as exc:
                candidates = ", ".join(repr(candidate) for candidate in exc.candidates)
                print(f"  {coll}.{name}: same-key indexes need explicit selection: {candidates}")
                print(f"      use --stale-index {coll!r} {name!r} <LIVE_INDEX>")
                selection_errors = True
                continue
            if stale is None:
                print(f"  {coll}.{name}: absent — init_beanie will create it on next boot")
                continue
            # Not absent: the same keys are already indexed under another name,
            # which is what makes createIndex fail with 85 on every boot.
            print(f"  {coll}.{name}: key spec already indexed as {stale!r}")
            print(f"      {_key_items(want)} — drop {stale!r}, create {name!r}")
            todo.append((coll, want, stale))
            continue
        changed = diff(live[name], want)
        if not changed:
            print(f"  {coll}.{name}: already correct")
            continue
        print(f"  {coll}.{name}: option drift")
        for key, (have, need) in changed.items():
            print(f"      {key}: {have!r} -> {need!r}")
        todo.append((coll, want, name))

    for coll, declared_name in explicit_stale.keys() - used_explicit:
        print(f"  {coll}.{declared_name}: unused --stale-index selection")
        selection_errors = True

    if selection_errors:
        print("\nNo indexes changed; resolve stale-index selections and re-run.")
        client.close()
        return 2

    if not todo:
        print("\nNothing to repair.")
        client.close()
        return 0

    if not args.confirm:
        print("\nDry run. Re-run with --confirm to apply.")
        client.close()
        return 0

    print()
    failures = []
    for coll, want, drop_name in todo:
        name = want["name"]
        key = list(want["key"].items())
        kwargs = {k: want[k] for k in COMPARABLE_KEYS if k in want}
        # drop_name is the index that currently holds this key spec. It is the
        # declared name for ordinary option drift, and the old auto-generated
        # name when the declaration gained an explicit one.
        db[coll].drop_index(drop_name)
        try:
            db[coll].create_index(key, name=name, **kwargs)
        except Exception as exc:  # noqa: BLE001
            # The old index is already gone at this point — that constraint
            # (often uniqueness) is unenforced until this is re-run and
            # succeeds. Reported explicitly rather than left to a stack trace,
            # since which index is in that state matters for what to do next.
            print(
                f"  FAILED {coll}.{name}: dropped {drop_name!r} but recreate failed ({exc}) "
                f"— re-run to retry. If this is a duplicate-key error the collection holds "
                f"rows the new constraint forbids; resolve those first."
            )
            failures.append((coll, name))
            continue
        print(f"  recreated {coll}.{name}")

    if failures:
        print(f"\n{len(failures)} index(es) failed to recreate — see FAILED lines above.")

    print("\nVerifying:")
    ok = True
    for coll, want, _drop_name in todo:
        name = want["name"]
        live = {i["name"]: i for i in db[coll].list_indexes()}
        changed = diff(live.get(name, {}), want)
        good = name in live and not changed
        ok = ok and good
        print(f"  {'OK  ' if good else 'FAIL'} {coll}.{name}")

    print("\nRestart the backend; init_beanie should now sync indexes without falling back.")
    client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
