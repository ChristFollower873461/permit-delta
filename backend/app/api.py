import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from app.config import config
from app.models import ReviewRequest, ReviewResult, AppReadiness, ModelMetadata, SearchMetadata
from app.scenarios import SCENARIOS
from app.search import execute_authority_search
from app.router import determine_routing_state
from app.gemini import generate_explanation, get_fallback_explanation, UnsafeModelResponseError

logger = logging.getLogger("permit_delta.api")
api_router = APIRouter(prefix="/api")

@api_router.get("/scenarios")
def get_scenarios():
    """
    Returns the three synthetic scenarios for user selection.
    """
    logger.info("Fetching available controlled scenarios.")
    return list(SCENARIOS.values())

@api_router.get("/readiness", response_model=AppReadiness)
def get_readiness():
    """
    Returns the readiness of application configuration.
    Describes configuration, never claims live connection or execution before it is observed.
    """
    parallel_configured = bool(config.PARALLEL_API_KEY)
    vertex_ai_configured = bool(config.GOOGLE_CLOUD_PROJECT)
    vertex_enabled = bool(config.GOOGLE_GENAI_USE_VERTEXAI)
    
    # Requirement: Require all four: LIVE_PARTNERS, Parallel key, project, and GOOGLE_GENAI_USE_VERTEXAI=True
    if config.LIVE_PARTNERS and parallel_configured and vertex_ai_configured and vertex_enabled:
        configured_mode = "Live Mode Configured (Unverified)"
    elif config.LIVE_PARTNERS:
        configured_mode = "Live Mode Requested (Credentials Incomplete)"
    else:
        configured_mode = "Offline Safety Fallback"
        
    return AppReadiness(
        parallel_configured=parallel_configured,
        vertex_ai_configured=vertex_ai_configured,
        google_genai_use_vertexai=vertex_enabled,
        configured_mode=configured_mode,
        runtime_revision=config.RUNTIME_REVISION
    )

@api_router.post("/review", response_model=ReviewResult)
async def run_review(payload: ReviewRequest):
    """
    Performs the operational permit review for a selected scenario.
    """
    correlation_id = str(uuid.uuid4())
    logger.info(f"[{correlation_id}] Starting operational permit review for scenario {payload.scenario_id}")
    
    # 1. Fetch Selected Scenario Dataset
    scenario = SCENARIOS.get(payload.scenario_id)
    if not scenario:
        logger.error(f"[{correlation_id}] Invalid scenario ID requested: {payload.scenario_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario ID {payload.scenario_id} is not valid."
        )
        
    # 2. Retrieve Authority Evidence via Search (Exactly 1 bounded call)
    query_category = ""
    if payload.scenario_id == 1:
        query_category = "administrative film permit schedule changes"
    elif payload.scenario_id == 2:
        query_category = "state park portable generator fire safety rules"
    elif payload.scenario_id == 3:
        query_category = "California State Parks drone lead times and FAA waivers"
        
    raw_sources = []
    search_id = "unavailable"
    search_latency = 0
    search_status = "skipped"
    
    try:
        raw_sources, search_id, search_latency, search_status = await execute_authority_search(payload.scenario_id, query_category)
    except Exception:
        logger.error(f"[{correlation_id}] Search execution encountered an error.")
        raw_sources = []
        search_id = "unavailable"
        search_status = "failed"

    # 3. Apply Deterministic Local Routing Engine (filters raw_sources -> verified_sources)
    try:
        state, destination, next_action, uncertainty, verified_sources = determine_routing_state(
            payload.scenario_id,
            raw_sources,
            live_partners_enabled=config.LIVE_PARTNERS
        )
    except Exception:
        logger.critical(f"[{correlation_id}] Routing engine encountered an error.")
        state = "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
        destination = "Lead Permit Officer (Escalated Review)"
        next_action = "Contact Lead Permit Officer immediately. Critical routing engine failure."
        uncertainty = "High"
        verified_sources = []

    # Requirement: Construct/update search_metadata AFTER determine_routing_state
    # and set retained_source_count = len(verified_sources)
    search_metadata = SearchMetadata(
        status=search_status,
        provider_response_id=search_id,
        latency_ms=search_latency,
        retained_source_count=len(verified_sources)
    )

    # 4. Generate Safety-Neutral Explanation via Gemini 3.7 Flash
    gemini_failed = False
    model_metadata = ModelMetadata(
        configured_model="gemini-3.7-flash",
        provider_version="unavailable",
        latency_ms=0,
        is_vertex_ai=False,
        status="fallback"
    )
    
    # Strict validation 1: Missing Vertex AI configuration while LIVE_PARTNERS is True is a raised model failure
    # Require all Vertex configurations for live mode
    if config.LIVE_PARTNERS and (not config.GOOGLE_GENAI_USE_VERTEXAI or not config.GOOGLE_CLOUD_PROJECT):
        logger.error(f"[{correlation_id}] Vertex AI unconfigured while LIVE_PARTNERS=True. Forcing model failure.")
        gemini_failed = True
        explanation = get_fallback_explanation(payload.scenario_id, "UNKNOWN", "Lead Permit Officer (Escalated Review)")
        model_metadata.status = "failed"
    # Strict validation 2: If no sources are retained, we skip model execution entirely (prevent spending model inference)
    elif not verified_sources:
        logger.info(f"[{correlation_id}] Skipping model execution because no sources were retained.")
        explanation = get_fallback_explanation(payload.scenario_id, state, destination)
        model_metadata.status = "skipped"
    else:
        try:
            explanation, metadata_dict = await generate_explanation(
                scenario_id=payload.scenario_id,
                state=state,
                destination=destination,
                differences=scenario["differences"],
                sources=verified_sources
            )
            model_metadata = ModelMetadata(
                configured_model=metadata_dict.get("configured_model", "gemini-3.7-flash"),
                provider_version=metadata_dict.get("provider_version", "unavailable"),
                latency_ms=metadata_dict.get("latency_ms", 0),
                is_vertex_ai=metadata_dict.get("is_vertex_ai", False),
                status=metadata_dict.get("status", "fallback")
            )
        except UnsafeModelResponseError:
            logger.error(f"[{correlation_id}] Safety Check Failed: Model output contains authorizing language. Forcing model failure.")
            gemini_failed = True
            explanation = get_fallback_explanation(payload.scenario_id, "UNKNOWN", "Lead Permit Officer (Escalated Review)")
            model_metadata.status = "failed"
        except Exception:
            logger.error(f"[{correlation_id}] Gemini/ADK inference failed or malformed.")
            gemini_failed = True
            explanation = get_fallback_explanation(payload.scenario_id, state, destination)
            model_metadata.status = "failed"

    # 5. Fail-closed model safety override logic:
    # A missing/empty/malformed/unsafe model response must fail the control scenario (Scenario 1) to UNKNOWN;
    # it may not leave an OWNER REVIEW state usable. HOLD may remain HOLD.
    if gemini_failed:
        if state == "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED":
            logger.warning(f"[{correlation_id}] Failing-closed OWNER REVIEW state to UNKNOWN due to unsafe/failed model response.")
            state = "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
            destination = "Lead Permit Officer (Escalated Review)"
            next_action = "Escalate review. AI model response failed safety scanning guidelines or is unconfigured."
            uncertainty = "High"

    # 6. Evaluate Source Freshness truthfully
    if not verified_sources:
        source_freshness = "Unavailable: no retained current evidence"
    else:
        source_freshness = "Current/Fresh"

    logger.info(
        f"[{correlation_id}] Review Completed. State: '{state}', "
        f"Destination: '{destination}', Sources Retrieved: {len(verified_sources)}, "
        f"Freshness: {source_freshness}, Uncertainty: {uncertainty}"
    )

    parallel_configured = bool(config.PARALLEL_API_KEY)
    vertex_ai_configured = bool(config.GOOGLE_CLOUD_PROJECT)
    vertex_enabled = bool(config.GOOGLE_GENAI_USE_VERTEXAI)
    
    if config.LIVE_PARTNERS and parallel_configured and vertex_ai_configured and vertex_enabled:
        configured_mode = "Live Mode Configured (Unverified)"
    elif config.LIVE_PARTNERS:
        configured_mode = "Live Mode Requested (Credentials Incomplete)"
    else:
        configured_mode = "Offline Safety Fallback"
        
    readiness = AppReadiness(
        parallel_configured=parallel_configured,
        vertex_ai_configured=vertex_ai_configured,
        google_genai_use_vertexai=vertex_enabled,
        configured_mode=configured_mode,
        runtime_revision=config.RUNTIME_REVISION
    )

    return ReviewResult(
        correlation_id=correlation_id,
        state=state,
        explanation=explanation,
        destination=destination,
        next_action=next_action,
        sources=verified_sources,
        source_freshness=source_freshness,
        uncertainty_rating=uncertainty,
        readiness=readiness,
        search_metadata=search_metadata,
        model_metadata=model_metadata,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
