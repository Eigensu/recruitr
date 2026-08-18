"""Client management endpoints.

  GET    /clients                    list clients for the brand (+ rollup counts)
  GET    /clients/{id}               one client with its counts — the detail page
  POST   /clients                    create a client — any brand user, so a recruiter can
                                     add a missing client inline while creating a position
  PATCH  /clients/{id}               edit / archive-restore — admin only
  DELETE /clients/{id}               archive (soft-delete) — admin only

  GET    /clients/{id}/users         emails authorized against this client
  POST   /clients/{id}/users         authorize an email — admin only
  DELETE /clients/{id}/users/{uid}   revoke an authorization — admin only

Renaming a client fans the new name out to Position.client_name, which is
denormalized for list rendering and would otherwise go stale.

Candidate counts join through positions rather than reading Mapping.client_id:
that field is denormalized and null on documents written before it existed.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant, get_viewer, require_admin
from app.modules.recruitment.models import Client, ClientUser, Mapping, Position
from app.modules.recruitment.repository import generate_client_code
from app.modules.recruitment.schemas import (
    ClientCreate,
    ClientResponse,
    ClientSelfUpdate,
    ClientUpdate,
    ClientUserInvite,
    ClientUserResponse,
    TenantScope,
)

router = APIRouter()

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_Viewer = Annotated[TenantScope, Depends(get_viewer)]
_IncludeArchived = Annotated[bool, Query()]
# Gate that only lets admins through; raises 403 otherwise.
_RequireAdmin = Depends(require_admin)

_ERR_NOT_FOUND = "Client not found"
_ERR_USER_NOT_FOUND = "Authorized user not found"
_CODE_RETRIES = 5

# Fields a recruiter can set on create and edit alike, so the two paths cannot
# drift apart and silently drop one of them.
_EDITABLE_TEXT = (
    "city",
    "industry",
    "website",
    "contact_person",
    "contact_email",
    "contact_phone",
)
_EDITABLE_LISTS = ("allowed_domains", "allowed_emails")


def _name_regex(name: str) -> dict:
    """Case-insensitive exact match on a client name."""
    return {"$regex": f"^{re.escape(name)}$", "$options": "i"}


def _stamp(update: dict, employee_id=None) -> dict:
    """Add the audit columns to a `$set` payload.

    Beanie's `before_event(Update)` hook fires after `.set()` has already built
    its `$set`, so the hook's `updated_at` never reaches the database — it only
    touches the in-memory copy. Anything written through `.set()` has to stamp
    the timestamp itself or the detail page reports the creation date forever.
    """
    update["updated_at"] = datetime.now(UTC)
    if employee_id is not None:
        update["updated_by_id"] = employee_id
    return update


def _writable_fields(payload: ClientCreate | ClientUpdate) -> dict:
    """Map a create/update payload onto storable values.

    Blank strings are stored as None so the UI renders a single "—" placeholder
    instead of an empty line, and lists are normalized to lowercase.
    """
    out: dict = {}
    for field in _EDITABLE_TEXT:
        value = getattr(payload, field, None)
        if value is not None:
            out[field] = value or None
    for field in _EDITABLE_LISTS:
        value = getattr(payload, field, None)
        if value is not None:
            out[field] = [v.lower() for v in value if v.strip()]
    return out


# ── Counts ─────────────────────────────────────────────────────────────────────


async def _count_active_positions(brand_id, client_id) -> int:
    return await Position.find(
        {"brand_id": brand_id, "client_id": client_id, "is_active": True}
    ).count()


async def _count_candidates(brand_id, client_id) -> int:
    """Distinct candidates mapped to any position belonging to this client."""
    position_ids = await Position.get_motor_collection().distinct(
        "_id", {"brand_id": brand_id, "client_id": client_id}
    )
    if not position_ids:
        return 0
    candidate_ids = await Mapping.get_motor_collection().distinct(
        "candidate_id", {"position_id": {"$in": position_ids}}
    )
    return len(candidate_ids)


async def _count_users(client_id) -> int:
    return await ClientUser.find({"client_id": client_id, "is_active": True}).count()


def _to_response(
    client: Client,
    position_count: int = 0,
    candidate_count: int = 0,
    user_count: int = 0,
) -> ClientResponse:
    return ClientResponse(
        id=str(client.id),
        code=client.code,
        name=client.name,
        city=client.city,
        industry=client.industry,
        website=client.website,
        contact_person=client.contact_person,
        contact_email=client.contact_email,
        contact_phone=client.contact_phone,
        allowed_domains=client.allowed_domains,
        allowed_emails=client.allowed_emails,
        is_active=client.is_active,
        position_count=position_count,
        candidate_count=candidate_count,
        user_count=user_count,
        created_by_id=str(client.created_by_id) if client.created_by_id else None,
        updated_by_id=str(client.updated_by_id) if client.updated_by_id else None,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


async def _with_counts(tenant: TenantScope, client: Client) -> ClientResponse:
    return _to_response(
        client,
        position_count=await _count_active_positions(tenant.brand_id, client.id),
        candidate_count=await _count_candidates(tenant.brand_id, client.id),
        user_count=await _count_users(client.id),
    )


async def _get_or_404(tenant: TenantScope, client_id: str) -> Client:
    oid = to_object_id(client_id, "client_id")
    doc = await Client.find_one({"_id": oid, "brand_id": tenant.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_NOT_FOUND)
    return doc


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ClientResponse])
async def list_clients(tenant: _Tenant, include_archived: _IncludeArchived = False):
    """Clients for the brand, alphabetical, each with its rollup counts."""
    match: dict = {"brand_id": tenant.brand_id}
    if not include_archived:
        match["is_active"] = True

    pipeline = [
        {"$match": match},
        {
            "$lookup": {
                "from": "positions",
                "let": {"cid": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$client_id", "$$cid"]},
                            "is_active": True,
                        }
                    },
                    {"$count": "n"},
                ],
                "as": "pos_count",
            }
        },
        # Every position, archived included: a candidate worked for this client
        # whether or not the role is still open.
        {
            "$lookup": {
                "from": "positions",
                "let": {"cid": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$client_id", "$$cid"]}}},
                    {"$project": {"_id": 1}},
                ],
                "as": "all_positions",
            }
        },
        {
            "$lookup": {
                "from": "candidate_mappings",
                "let": {"pids": "$all_positions._id"},
                "pipeline": [
                    {"$match": {"$expr": {"$in": ["$position_id", "$$pids"]}}},
                    {"$group": {"_id": "$candidate_id"}},
                    {"$count": "n"},
                ],
                "as": "cand_count",
            }
        },
        {
            "$lookup": {
                "from": "client_users",
                "let": {"cid": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$client_id", "$$cid"]},
                            "is_active": True,
                        }
                    },
                    {"$count": "n"},
                ],
                "as": "user_count_arr",
            }
        },
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
                "created_by_id": {"$toString": "$created_by_id"},
                "updated_by_id": {"$toString": "$updated_by_id"},
                "position_count": {"$ifNull": [{"$first": "$pos_count.n"}, 0]},
                "candidate_count": {"$ifNull": [{"$first": "$cand_count.n"}, 0]},
                "user_count": {"$ifNull": [{"$first": "$user_count_arr.n"}, 0]},
            }
        },
        {"$unset": ["pos_count", "cand_count", "user_count_arr", "all_positions"]},
        {"$sort": {"name": 1}},
    ]

    rows = await (await Client.get_motor_collection().aggregate(pipeline)).to_list(length=None)  # type: ignore[misc]
    return [ClientResponse.model_validate(r) for r in rows]


# ── Detail ─────────────────────────────────────────────────────────────────────


# Registered before /{client_id} so the literal wins over the path parameter —
# otherwise "me" is parsed as an id and 400s on the ObjectId conversion.
@router.get("/me", response_model=ClientResponse)
async def get_my_client(viewer: _Viewer):
    """The signed-in client's own company — the Company Profile page.

    Staff have no single company, so this is client-only rather than returning
    something arbitrary for them.
    """
    if viewer.client_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only client accounts have a company profile.",
        )
    doc = await Client.find_one({"_id": viewer.client_id, "brand_id": viewer.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_NOT_FOUND)
    return await _with_counts(viewer, doc)


@router.patch("/me", response_model=ClientResponse)
async def update_my_client(viewer: _Viewer, payload: ClientSelfUpdate):
    """Update the signed-in client's own company profile (logo and description)."""
    if viewer.client_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only client accounts can update their company profile.",
        )
    doc = await Client.find_one({"_id": viewer.client_id, "brand_id": viewer.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_NOT_FOUND)

    update_dict = payload.model_dump(exclude_unset=True)
    if "logo_url" in update_dict:
        doc.logo_url = update_dict["logo_url"]
    if "brand_description" in update_dict:
        doc.brand_description = update_dict["brand_description"]

    if update_dict:
        await doc.save()

    return await _with_counts(viewer, doc)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(tenant: _Tenant, client_id: str):
    """One client, with the same counts the list cards show."""
    return await _with_counts(tenant, await _get_or_404(tenant, client_id))


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(tenant: _Tenant, payload: ClientCreate):
    """Add a client to the brand's list.

    Not admin-gated: creating a position requires picking a client, so a recruiter
    who hits a client that isn't in the list yet has to be able to add it.
    """
    fields = _writable_fields(payload)

    existing = await Client.find_one(
        {"brand_id": tenant.brand_id, "name": _name_regex(payload.name)}
    )
    if existing:
        if existing.is_active:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f'A client named "{existing.name}" already exists'
            )
        # Reviving an archived client keeps its code and its position history
        # instead of creating a second row for the same real-world client.
        revive = {"is_active": True, **fields}
        # Only overwrite detail the caller actually supplied.
        revive.setdefault("city", existing.city)
        await existing.set(_stamp(revive, tenant.employee_id))
        return await _with_counts(tenant, existing)

    doc = Client(
        brand_id=tenant.brand_id,
        code=await generate_client_code(tenant.brand_id),
        name=payload.name,
        created_by_id=tenant.employee_id,
        updated_by_id=tenant.employee_id,
        **fields,
    )
    # The client counter can lag behind the codes already in the collection
    # (migrations write codes without touching it), so a fresh code may collide.
    # Each retry increments the counter, which walks past any existing code.
    for attempt in range(_CODE_RETRIES):
        try:
            await doc.insert()
            break
        except DuplicateKeyError:
            if attempt == _CODE_RETRIES - 1:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Could not allocate a client code — please retry"
                ) from None
            doc.code = await generate_client_code(tenant.brand_id)

    return _to_response(doc)


# ── Update ─────────────────────────────────────────────────────────────────────


@router.patch("/{client_id}", response_model=ClientResponse, dependencies=[_RequireAdmin])
async def update_client(tenant: _Tenant, client_id: str, payload: ClientUpdate):
    doc = await _get_or_404(tenant, client_id)
    update: dict = _writable_fields(payload)

    if payload.name is not None and payload.name != doc.name:
        clash = await Client.find_one(
            {
                "brand_id": tenant.brand_id,
                "name": _name_regex(payload.name),
                "_id": {"$ne": doc.id},
            }
        )
        if clash:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f'A client named "{clash.name}" already exists'
            )
        update["name"] = payload.name

    if payload.is_active is not None:
        update["is_active"] = payload.is_active

    if update:
        await doc.set(_stamp(update, tenant.employee_id))

    # client_name is denormalized onto every position for list rendering — a
    # rename that skipped this would leave the old name on screen forever.
    if "name" in update:
        await Position.get_motor_collection().update_many(
            {"brand_id": tenant.brand_id, "client_id": doc.id},
            {"$set": {"client_name": update["name"], "updated_at": datetime.now(UTC)}},
        )

    return await _with_counts(tenant, doc)


# ── Archive (soft delete) ──────────────────────────────────────────────────────


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_RequireAdmin])
async def archive_client(tenant: _Tenant, client_id: str):
    """Remove a client from the dropdowns.

    Refused while the client still has open positions: those positions would stay
    live with no client left to filter them by.
    """
    doc = await _get_or_404(tenant, client_id)

    open_positions = await _count_active_positions(tenant.brand_id, doc.id)
    if open_positions:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{doc.name} still has {open_positions} active position"
            f"{'s' if open_positions != 1 else ''}. Delete those first.",
        )

    await doc.set(_stamp({"is_active": False}, tenant.employee_id))


# ── Authorized users ───────────────────────────────────────────────────────────


def _user_status(doc: ClientUser) -> str:
    if not doc.is_active:
        return "Inactive"
    return "Active" if doc.user_id else "Pending"


def _to_user_response(doc: ClientUser) -> ClientUserResponse:
    return ClientUserResponse(
        id=str(doc.id),
        name=doc.name,
        email=doc.email,
        role=doc.role,
        status=_user_status(doc),
        last_login=doc.last_login,
        created_at=doc.created_at,
    )


def _is_authorized_address(client: Client, email: str) -> bool:
    """True if the address is covered by the client's allow-lists.

    An empty allow-list is treated as "not yet configured" rather than "deny
    everything", so an admin can authorize a contact before filling one in.
    """
    if not client.allowed_domains and not client.allowed_emails:
        return True
    if email in client.allowed_emails:
        return True
    domain = email.rsplit("@", 1)[-1]
    return any(d.lstrip("@") == domain for d in client.allowed_domains)


@router.get("/{client_id}/users", response_model=list[ClientUserResponse])
async def list_client_users(tenant: _Tenant, client_id: str):
    """Emails authorized against this client, revoked ones included."""
    client = await _get_or_404(tenant, client_id)
    docs = await ClientUser.find({"client_id": client.id}).sort("email").to_list()
    return [_to_user_response(d) for d in docs]


@router.post(
    "/{client_id}/users",
    response_model=ClientUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_RequireAdmin],
)
async def invite_client_user(tenant: _Tenant, client_id: str, payload: ClientUserInvite):
    """Authorize an email address against this client.

    This records an authorization, not a login. See ClientUser for why creating
    a User here would hand the address full agency access.
    """
    client = await _get_or_404(tenant, client_id)
    email = payload.email.lower()

    if not _is_authorized_address(client, email):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{email} does not match an authorized domain or email for {client.name}. "
            "Add it to the client's allow-list first.",
        )

    existing = await ClientUser.find_one({"client_id": client.id, "email": email})
    if existing:
        if existing.is_active:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{email} is already authorized for {client.name}"
            )
        # Re-inviting a revoked address restores the original row rather than
        # tripping the unique (client_id, email) index.
        await existing.set(_stamp({"is_active": True, "role": payload.role}))
        return _to_user_response(existing)

    doc = ClientUser(
        brand_id=tenant.brand_id,
        client_id=client.id,
        email=email,
        role=payload.role,
        invited_by_id=tenant.employee_id,
    )
    await doc.insert()
    return _to_user_response(doc)


@router.delete(
    "/{client_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_RequireAdmin],
)
async def remove_client_user(tenant: _Tenant, client_id: str, user_id: str):
    """Revoke an authorization, keeping the row so the audit trail survives."""
    client = await _get_or_404(tenant, client_id)
    oid = to_object_id(user_id, "user_id")

    doc = await ClientUser.find_one({"_id": oid, "client_id": client.id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_USER_NOT_FOUND)

    await doc.set(_stamp({"is_active": False}))
