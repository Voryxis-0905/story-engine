"""Runtime routes."""
from fastapi import APIRouter, HTTPException

from app.storage import _VALID_ROLES, read_runtime_config, write_runtime_config, read_world_runtime_override, write_world_runtime_override, build_runtime_config_status, _sanitize_and_preserve_fallback_chain, require_world
from app.engine import test_llm_connection
from app.models import RuntimeConfigUpdate

try:
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()


def _resolve_api_key_action(req: RuntimeConfigUpdate) -> str:
    """Resolve a runtime key write into keep / replace / delete.

    A blank or masked value means "keep" so the UI can save a model without
    resending the secret (which it never receives back from GET).
    """
    if req.api_key_action in ("keep", "replace", "delete"):
        return req.api_key_action
    raw = req.api_key if req.api_key is not None else req.openrouter_api_key
    if raw is None:
        return "keep"
    text = str(raw).strip()
    if text == "" or "\u2026" in text or "*" in text:
        return "keep"
    return "replace"


def _sync_single_chain_node(chain, *, api_key: str = None, model: str = None):
    """Update the world-owned single-node chain in place, keeping everything else.

    Only touches a chain that is exactly one node (the effective single config).
    A multi-node chain is left as the user configured it; a missing chain stays
    missing so it is rebuilt from the top-level key/model.
    """
    if not isinstance(chain, list) or len(chain) != 1 or not isinstance(chain[0], dict):
        return chain if isinstance(chain, list) else []
    node = dict(chain[0])
    if api_key is not None:
        node["api_key"] = api_key
    if model is not None:
        node["model"] = model
    return [node]



@router.get("/runtime-config")
def get_runtime_config():
    return build_runtime_config_status()


@router.put("/runtime-config")
def update_runtime_config(req: RuntimeConfigUpdate):
    cfg = read_runtime_config()
    key_action = _resolve_api_key_action(req)
    raw_key = req.api_key if req.api_key is not None else req.openrouter_api_key

    if key_action == "delete":
        cfg["openrouter_api_key"] = ""
        cfg["api_key"] = ""
        cfg["fallback_chain"] = []
    elif key_action == "replace":
        key_val = (raw_key or "").strip()
        cfg["openrouter_api_key"] = key_val
        cfg["api_key"] = key_val
    # key_action == "keep": leave the stored secret untouched

    model_val = req.model_name if req.model_name is not None else req.openrouter_model
    if model_val is not None:
        cfg["openrouter_model"] = model_val.strip()
        cfg["model_name"] = model_val.strip()

    if req.llm_provider is not None:
        cfg["llm_provider"] = req.llm_provider.strip()

    if req.base_url is not None:
        cfg["base_url"] = req.base_url.strip()

    if req.temperature is not None:
        cfg["temperature"] = req.temperature
    # Keep fallback_chain in sync with top-level key/model/provider
    eff_key = cfg.get("api_key") or cfg.get("openrouter_api_key") or ""
    eff_model = cfg.get("model_name") or cfg.get("openrouter_model") or ""
    eff_provider = cfg.get("llm_provider", "openrouter")
    eff_base_url = cfg.get("base_url", "")

    if req.fallback_chain is not None:
        cfg["fallback_chain"] = _sanitize_and_preserve_fallback_chain(req.fallback_chain, cfg.get("fallback_chain", []))
    elif key_action == "replace" and eff_key:
        cfg["fallback_chain"] = [{
            "provider": eff_provider,
            "model": eff_model,
            "api_key": eff_key,
            "base_url": eff_base_url
        }]
    else:
        # The single stored node is the effective provider target. Keep its secret
        # but follow model/provider/base-url changes, otherwise the LLM client
        # (which reads the chain first) would keep using the old target.
        # A user-configured multi-node chain is left untouched.
        existing_chain = cfg.get("fallback_chain")
        if isinstance(existing_chain, list) and len(existing_chain) == 1 and isinstance(existing_chain[0], dict):
            node = dict(existing_chain[0])
            node["provider"] = eff_provider or node.get("provider", "openrouter")
            if eff_model:
                node["model"] = eff_model
            node["base_url"] = eff_base_url
            node["api_key"] = node.get("api_key", "") or eff_key
            cfg["fallback_chain"] = [node]
    if req.creator_mode_enabled is not None:
        cfg["creator_mode_enabled"] = req.creator_mode_enabled
    if req.role_assignments is not None:
        invalid_keys = [k for k in req.role_assignments if k not in _VALID_ROLES]
        if invalid_keys:
            raise HTTPException(status_code=400, detail=f"role_assignments chi nhan key: planner, writer, extractor, editor, checker, summarizer. Key khong hop le: {invalid_keys}")
        invalid_vals = [k for k, v in req.role_assignments.items() if v is not None and (not isinstance(v, int) or v < 0)]
        if invalid_vals:
            raise HTTPException(status_code=400, detail=f"role_assignments value phai la null hoac int >= 0. Key loi: {invalid_vals}")
        existing_ra = cfg.get("role_assignments", {"planner": None, "writer": None, "extractor": None, "editor": None, "checker": None, "summarizer": None})
        existing_ra.update(req.role_assignments)
        cfg["role_assignments"] = existing_ra
    if req.editor_enabled is not None:
        cfg["editor_enabled"] = req.editor_enabled
    if req.enable_extractor_cross_check is not None:
        cfg["enable_extractor_cross_check"] = req.enable_extractor_cross_check
    write_runtime_config(cfg)
    return build_runtime_config_status()


@router.delete("/runtime-config/api-key")
def clear_runtime_api_key():
    cfg = read_runtime_config()
    cfg["api_key"] = ""
    cfg["openrouter_api_key"] = ""
    cfg["fallback_chain"] = []
    write_runtime_config(cfg)
    return build_runtime_config_status()


@router.post("/runtime-config/test-connection")
@router.post("/test-llm-connection")
def runtime_config_test_connection(node_index: int = 0):
    return test_llm_connection(node_index=node_index)


@router.get("/worlds/{world_name}/runtime-config")
def get_world_runtime_config(world_name: str):
    require_world(world_name)
    return build_runtime_config_status(world_name)


@router.put("/worlds/{world_name}/runtime-config")
def update_world_runtime_config(world_name: str, req: RuntimeConfigUpdate):
    require_world(world_name)
    cfg = read_world_runtime_override(world_name)
    key_action = _resolve_api_key_action(req)
    raw_key = req.api_key if req.api_key is not None else req.openrouter_api_key
    if key_action == "delete":
        cfg["openrouter_api_key"] = ""
        cfg["fallback_chain"] = []
    elif key_action == "replace":
        new_key = (raw_key or "").strip()
        cfg["openrouter_api_key"] = new_key
        # A world-owned single-node chain must not shadow the freshly stored key.
        cfg["fallback_chain"] = _sync_single_chain_node(cfg.get("fallback_chain"), api_key=new_key)
    if req.openrouter_model is not None:
        cfg["openrouter_model"] = req.openrouter_model.strip()
        # Only the world's own model is updated here; provider/base_url of a
        # world-owned chain must never be taken from the app config just because
        # an unrelated field (e.g. editor_enabled) was saved.
        cfg["fallback_chain"] = _sync_single_chain_node(
            cfg.get("fallback_chain"), model=req.openrouter_model.strip()
        )
    if req.fallback_chain is not None:
        cfg["fallback_chain"] = _sanitize_and_preserve_fallback_chain(req.fallback_chain, cfg.get("fallback_chain", []))
    if req.role_assignments is not None:
        invalid_keys = [k for k in req.role_assignments if k not in _VALID_ROLES]
        if invalid_keys:
            raise HTTPException(status_code=400, detail=f"role_assignments chi nhan key: planner, writer, extractor, editor, checker, summarizer. Key khong hop le: {invalid_keys}")
        invalid_vals = [k for k, v in req.role_assignments.items() if v is not None and (not isinstance(v, int) or v < 0)]
        if invalid_vals:
            raise HTTPException(status_code=400, detail=f"role_assignments value phai la null hoac int >= 0. Key loi: {invalid_vals}")
        existing_ra = cfg.get("role_assignments", {"planner": None, "writer": None, "extractor": None, "editor": None, "checker": None, "summarizer": None})
        existing_ra.update(req.role_assignments)
        cfg["role_assignments"] = existing_ra
    if req.editor_enabled is not None:
        cfg["editor_enabled"] = req.editor_enabled
    if req.enable_extractor_cross_check is not None:
        cfg["enable_extractor_cross_check"] = req.enable_extractor_cross_check
    write_world_runtime_override(world_name, cfg)
    return build_runtime_config_status(world_name)


@router.delete("/worlds/{world_name}/runtime-config/api-key")
def clear_world_runtime_api_key(world_name: str):
    require_world(world_name)
    cfg = read_world_runtime_override(world_name)
    cfg["openrouter_api_key"] = ""
    cfg["fallback_chain"] = []
    write_world_runtime_override(world_name, cfg)
    return build_runtime_config_status(world_name)


@router.post("/worlds/{world_name}/runtime-config/test-connection")
def world_runtime_config_test_connection(world_name: str, node_index: int = 0):
    require_world(world_name)
    return test_llm_connection(world_name, node_index=node_index)
