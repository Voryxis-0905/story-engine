"""Turn idempotency and stale-write protection.

Each player action may carry a client-generated `request_id` and the world
`revision` the client based its action on. A committed action is recorded in a
receipt so a retried request (e.g. the response was lost on the network) returns
the stored result without calling the AI again. Receipts live outside the core
state catalog so restore/branch never inherit another timeline's receipts.

This guarantees duplicate protection within one process and across restarts for
local turns. It does not promise exactly-once delivery to an external AI
provider: a crash before the receipt is written may repeat the provider call.
"""
import hashlib
import json
import os
import time

from fastapi import HTTPException

RECEIPTS_FILENAME = "turn_receipts.json"
MAX_RECEIPTS = 200


def content_hash(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_revision(world_config: dict) -> int:
    value = world_config.get("revision", 0)
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def bump_revision(world_config: dict) -> int:
    next_revision = get_revision(world_config) + 1
    world_config["revision"] = next_revision
    return next_revision


def _receipts_path(world_path: str) -> str:
    return os.path.join(world_path, RECEIPTS_FILENAME)


def load_receipts(world_path: str) -> dict:
    path = _receipts_path(world_path)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_receipts(world_path: str, receipts: dict) -> None:
    path = _receipts_path(world_path)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(receipts, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def clear_receipts(world_path: str) -> None:
    path = _receipts_path(world_path)
    if os.path.isfile(path):
        os.unlink(path)


def lookup_receipt(world_path: str, request_id: str, action_hash: str):
    """Return the stored response when this exact request already committed.

    Raises 409 when the same request_id was used for different content.
    """
    if not request_id:
        return None
    existing = load_receipts(world_path).get(request_id)
    if not existing:
        return None
    if existing.get("content_hash") != action_hash:
        raise HTTPException(status_code=409, detail={
            "reason": "request_id_conflict",
            "request_id": request_id,
            "message": "This request_id was already used for a different action.",
        })
    return existing.get("response")


def check_expected_revision(world_config: dict, expected_revision) -> int:
    current = get_revision(world_config)
    if expected_revision is not None and int(expected_revision) != current:
        raise HTTPException(status_code=409, detail={
            "reason": "stale_revision",
            "expected_revision": int(expected_revision),
            "current_revision": current,
            "message": "The world changed since this action was prepared. Reload and retry.",
        })
    return current


def build_receipts_document(world_path: str, request_id: str, action_hash: str,
                            revision_before: int, response: dict):
    """Return the receipts mapping with this turn's receipt included.

    The caller commits it together with the turn files so the receipt and the
    state it describes survive or roll back as one unit (F06).
    """
    if not request_id:
        return None
    receipts = load_receipts(world_path)
    if request_id not in receipts and len(receipts) >= MAX_RECEIPTS:
        receipts = dict(list(receipts.items())[-MAX_RECEIPTS // 2:])
    receipts[request_id] = {
        "content_hash": action_hash,
        "revision_before": revision_before,
        "revision_after": get_revision(response) if isinstance(response, dict) else revision_before,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "response": response,
    }
    return receipts


def record_receipt(world_path: str, request_id: str, action_hash: str,
                   revision_before: int, response: dict) -> None:
    receipts = build_receipts_document(world_path, request_id, action_hash, revision_before, response)
    if receipts is not None:
        save_receipts(world_path, receipts)
