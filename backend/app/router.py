import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from urllib.parse import urlparse
from app.models import SourceEvidence
from app.scenarios import SCENARIOS

logger = logging.getLogger("permit_delta.router")

ALLOWED_HOSTS = [
    "film.ca.gov",
    "parks.ca.gov",
    "www.parks.ca.gov",
    "faa.gov",
    "www.faa.gov"
]

def get_verified_authority_class(url: str) -> str | None:
    """
    Validates URL scheme, parsed host against our strict allowlist,
    and returns the exact authorized class mapping. Do NOT trust caller-provided labels.
    """
    if not url or not isinstance(url, str):
        return None
    if not url.startswith("https://"):
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host not in ALLOWED_HOSTS:
            return None
        if "film.ca.gov" in host:
            return "California Film Commission"
        elif "parks.ca.gov" in host:
            return "California State Parks"
        elif "faa.gov" in host:
            return "FAA"
    except Exception:
        pass
    return None

def is_valid_fresh_timestamp(ts_str: str) -> bool:
    """
    Enforces that the ISO-8601 UTC timestamp is valid,
    not in the future (skew tolerance 5 mins), and not older than 24 hours.
    """
    if not ts_str or not isinstance(ts_str, str):
        return False
    try:
        normalized = ts_str.replace("Z", "+00:00")
        ts = datetime.fromisoformat(normalized)
        now = datetime.now(timezone.utc)
        
        # Max age: 24 hours
        if now - ts > timedelta(hours=24):
            return False
        # Future skew tolerance: 5 minutes
        if ts - now > timedelta(minutes=5):
            return False
        return True
    except Exception:
        return False

def determine_routing_state(
    scenario_id: int, 
    sources: List[SourceEvidence], 
    live_partners_enabled: bool
) -> Tuple[str, str, str, str, List[SourceEvidence]]:
    """
    Applies deterministic routing rules based on verified, diverse source evidence.
    Returns a Tuple: (state, destination, next_action, uncertainty_rating, verified_sources)
    """
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        logger.warning(f"Undefined scenario {scenario_id}. Failing closed.")
        return (
            "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY",
            "Lead Permit Officer (Escalated Review)",
            "Contact your lead permit officer immediately as the requested scenario is undefined in system memory.",
            "High",
            []
        )

    # Calculate and store the generator HOLD invariant immediately after scenario lookup, before source validation.
    baseline = scenario["baseline"]
    revised = scenario["revised"]
    generator_added = (baseline.get("generator") == "None" or not baseline.get("generator")) and \
                      (revised.get("generator") != "None" and revised.get("generator"))

    # 1. On-The-Fly Source Evidence Validation & Revalidation inside a per-source try/except
    verified_sources: List[SourceEvidence] = []
    
    for s in sources:
        try:
            url = str(s.url).strip()
            excerpt = str(s.excerpt).strip()
            provider_id = str(s.provider_response_id).strip()
            ts_str = str(s.retrieval_time).strip()
            
            # Discard invalid links, blank excerpts, or blank provider IDs
            if not url or not excerpt or not provider_id:
                continue
                
            verified_class = get_verified_authority_class(url)
            if not verified_class:
                continue
                
            # Ensure timestamp is current and within 24h
            if not is_valid_fresh_timestamp(ts_str):
                continue
                
            verified_sources.append(
                SourceEvidence(
                    title=s.title,
                    url=s.url,
                    authority_class=verified_class,
                    query_purpose_category=s.query_purpose_category,
                    retrieval_time=s.retrieval_time,
                    excerpt=s.excerpt,
                    provider_response_id=s.provider_response_id,
                    latency_ms=s.latency_ms
                )
            )
        except Exception:
            logger.warning("Discarded malformed source evidence due to parsing or validation exception.")
            continue

    # Return the pre-established HOLD state with any verified display sources after validation.
    # No malformed evidence can ever cause HOLD to become UNKNOWN.
    if generator_added:
        logger.info("Deterministic route trigger: Generator added. HOLD state verified first.")
        return (
            "HOLD: MATERIAL DELTA; CONTACT PARK/CFC",
            scenario["expected_destination"],
            scenario["expected_next_action"],
            scenario["uncertainty_rating"],
            verified_sources
        )

    # 3. Fail-closed partner / diversity check for non-hold scenarios:
    # 3a. Partner-off mode check
    if not live_partners_enabled:
        return (
            "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY",
            "Lead Permit Officer (Escalated Review)",
            "Run live partner search to establish real-time authority guidelines. Static fallbacks are unverified.",
            "High",
            []
        )
        
    # 3b. Empty verified sources check
    if not verified_sources:
        return (
            "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY",
            "Lead Permit Officer (Escalated Review)",
            "Authority search returned empty or unverified sources. Local fallback options are unverified.",
            "High",
            []
        )

    # 3c. Hard Invariant: Evidence Diversity Check (At least two distinct valid hosts & mapped authority classes)
    distinct_classes = {s.authority_class for s in verified_sources}
    distinct_hosts = set()
    for s in verified_sources:
        try:
            parsed = urlparse(s.url)
            distinct_hosts.add(parsed.hostname)
        except Exception:
            pass
            
    if len(distinct_classes) < 2 or len(distinct_hosts) < 2:
        logger.warning(
            f"Evidence diversity invariant failed. "
            f"Found {len(distinct_classes)} distinct classes and {len(distinct_hosts)} distinct hosts."
        )
        return (
            "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY",
            "Lead Permit Officer (Escalated Review)",
            "Authority evidence lacks sufficient diversity. At least two distinct authoritative classes and hosts are required.",
            "High",
            verified_sources
        )

    # 4. Check for Drone Conflict scenario
    drone_added = (baseline.get("drone") == "None" or not baseline.get("drone")) and \
                  (revised.get("drone") != "None" and revised.get("drone"))
                  
    if drone_added:
        logger.info("Deterministic route trigger: Short-notice drone added. Status set to UNKNOWN.")
        return (
            "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY",
            scenario["expected_destination"],
            scenario["expected_next_action"],
            scenario["uncertainty_rating"],
            verified_sources
        )

    # 5. Control Scenario (Scenario 1) with fresh, valid, diverse sources
    logger.info("Deterministic route trigger: Control change with verified diverse sources. Status set to OWNER REVIEW.")
    return (
        "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED",
        scenario["expected_destination"],
        scenario["expected_next_action"],
        scenario["uncertainty_rating"],
        verified_sources
    )
