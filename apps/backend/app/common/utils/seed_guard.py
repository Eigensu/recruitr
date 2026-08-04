"""Refuse to run destructive seeders against anything but a local database.

The repo-root .env points MONGODB_URI at the live Atlas cluster, and the
seeders default to reset=True — dropping candidates, positions, clients,
employees and more. So the obvious invocation,

    python3 -m app.modules.recruitment.seed

would wipe production without asking. Every seeder calls
``assert_local_database()`` before its first write.
"""

import os
from urllib.parse import urlsplit

# Hosts we consider a developer's own machine.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "mongo", "mongodb"}

# Deliberate escape hatch, for the rare case of seeding a remote scratch cluster.
_OVERRIDE = "SEED_ALLOW_REMOTE_DB"


def _hosts(uri: str) -> list[str]:
    """Host names in a mongodb:// or mongodb+srv:// URI, ports stripped."""
    # urlsplit needs a scheme it recognises; mongodb+srv parses fine as-is.
    netloc = urlsplit(uri).netloc
    if "@" in netloc:  # strip credentials
        netloc = netloc.rsplit("@", 1)[1]
    out = []
    for part in netloc.split(","):
        host = part.strip()
        if host.startswith("["):  # ipv6 literal
            host = host[1 : host.find("]")] if "]" in host else host
        elif ":" in host:
            host = host.rsplit(":", 1)[0]
        if host:
            out.append(host.lower())
    return out


def is_local_database(uri: str) -> bool:
    """True only when every host in the URI is local."""
    hosts = _hosts(uri)
    return bool(hosts) and all(h in _LOCAL_HOSTS for h in hosts)


def assert_local_database(uri: str, *, action: str = "seed") -> None:
    """Raise SystemExit unless `uri` is local, or the override is set."""
    if is_local_database(uri):
        return
    if os.getenv(_OVERRIDE) == "1":
        print(f"!! {_OVERRIDE}=1 — proceeding against a non-local database: {_hosts(uri)}")
        return
    raise SystemExit(
        f"\nREFUSING TO {action.upper()}: MONGODB_URI does not point at a local database.\n"
        f"  hosts: {', '.join(_hosts(uri)) or '(unparsable)'}\n\n"
        "This seeder drops and deletes collections. The repo-root .env points at the\n"
        "live Atlas cluster, so running it as configured would destroy production data.\n\n"
        "To seed locally, override on the command line (env vars beat the .env file):\n"
        '  MONGODB_URI="mongodb://localhost:27017/recruitr" MONGODB_DB_NAME="recruitr" \\\n'
        "    python3 -m app.modules.recruitment.seed\n\n"
        f"If you genuinely mean to target a remote database, set {_OVERRIDE}=1.\n"
    )
