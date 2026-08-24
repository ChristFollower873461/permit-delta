import time
import logging
from datetime import datetime, timezone
from typing import List, Tuple
from urllib.parse import urlparse
from app.config import config
from app.models import SourceEvidence

logger = logging.getLogger("permit_delta.search")

# Exact production hosts allowlist
ALLOWED_HOSTS = [
    "film.ca.gov",
    "parks.ca.gov",
    "www.parks.ca.gov",
    "faa.gov",
    "www.faa.gov"
]

def is_valid_production_host(url: str) -> bool:
    """
    Enforces application-side validation that the URL belongs to an approved
    exact production host allowlist and uses HTTPS.
    """
    if not url or not isinstance(url, str):
        return False
    if not url.startswith("https://"):
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return host in ALLOWED_HOSTS
    except Exception:
        return False

async def execute_authority_search(scenario_id: int, query_purpose_category: str) -> Tuple[List[SourceEvidence], str, int, str]:
    """
    Executes a web search for film permit authority rules.
    If LIVE_PARTNERS=True and keys are present, uses Parallel.ai AsyncParallel SDK.
    Otherwise, returns empty list [], status="skipped", search_id="unavailable", and latency=0.

    Returns a Tuple: (validated_sources, search_id, latency_ms, status)
    """
    start_time = time.time()

    # Bounded query metadata logging (Never log the full query)
    logger.info(
        f"Initiating bounded authority search. "
        f"Scenario ID: {scenario_id}, Query length: {len(query_purpose_category)}"
    )

    if config.LIVE_PARTNERS and config.PARALLEL_API_KEY:
        try:
            from parallel import AsyncParallel

            async with AsyncParallel(api_key=config.PARALLEL_API_KEY, max_retries=0) as client:
                # Formulate query using domain constraints inside domain-restricted query text (safe)
                search_query = f"{query_purpose_category} (site:film.ca.gov OR site:parks.ca.gov OR site:faa.gov)"

                # Exactly one bounded search call using basic mode and valid excerpt settings
                response = await client.search(
                    search_queries=[search_query],
                    objective="Identify film permit guidelines, lead times, and regulations",
                    mode="basic",
                    max_chars_total=10000,
                    advanced_settings={
                        "max_results": 5,
                        "excerpt_settings": {
                            "max_chars_per_result": 500
                        },
                        "source_policy": {
                            "include_domains": ["film.ca.gov", "parks.ca.gov", "faa.gov"]
                        }
                    }
                )

                latency_ms = int((time.time() - start_time) * 1000)
                now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

                # Verify and preserve actual provider response search_id
                search_id = getattr(response, "search_id", "")
                if not search_id or not str(search_id).strip():
                    logger.error("Parallel Search response missing valid search_id. Failing closed with empty results.")
                    return [], "unavailable", latency_ms, "failed"

                search_id = str(search_id).strip()
                validated_sources: List[SourceEvidence] = []

                results = getattr(response, "results", None)
                if results is None:
                    results = []

                for index, item in enumerate(results):
                    if item is None:
                        continue

                    url = getattr(item, "url", "")
                    if url is None:
                        url = ""
                    url = str(url).strip()

                    # Strict host allowlist validation
                    if not is_valid_production_host(url):
                        logger.warning(f"Result {index} filtered out: URL host invalid")
                        continue

                    # Build the excerpt only from stripped, nonblank string elements.
                    # A None/non-string element must be ignored, not fail the whole call.
                    excerpts_list = getattr(item, "excerpts", [])
                    if excerpts_list is None:
                        excerpts_list = []

                    if isinstance(excerpts_list, list):
                        clean_excerpts = []
                        for elem in excerpts_list:
                            if isinstance(elem, str):
                                stripped_elem = elem.strip()
                                if stripped_elem:
                                    clean_excerpts.append(stripped_elem)
                        full_excerpt = " ".join(clean_excerpts)
                    elif isinstance(excerpts_list, str):
                        full_excerpt = excerpts_list.strip()
                    else:
                        full_excerpt = ""

                    if not full_excerpt:
                        logger.warning(f"Result {index} skipped: excerpt is blank")
                        continue

                    # Normalize title with nonempty fallback and truncate (no "None" string literal fallback)
                    title = getattr(item, "title", "")
                    if title is None:
                        title = ""
                    title = str(title).strip()
                    if not title or title.lower() == "none":
                        title = "Official Reference"
                    title = title[:200]

                    # Determine exact authority class based on validated host
                    parsed = urlparse(url)
                    host = parsed.hostname or ""
                    if "parks.ca.gov" in host:
                        auth_class = "California State Parks"
                    elif "film.ca.gov" in host:
                        auth_class = "California Film Commission"
                    elif "faa.gov" in host:
                        auth_class = "FAA"
                    else:
                        continue

                    validated_sources.append(
                        SourceEvidence(
                            title=title,
                            url=url[:500],
                            authority_class=auth_class,
                            query_purpose_category=query_purpose_category[:100],
                            retrieval_time=now_iso,
                            excerpt=full_excerpt[:1500],
                            provider_response_id=search_id,
                            latency_ms=latency_ms  # Use total observed search latency consistently
                        )
                    )

                return validated_sources, search_id, latency_ms, "observed"

        except Exception:
            logger.error("Error during live AsyncParallel search execution.")
            return [], "unavailable", int((time.time() - start_time) * 1000), "failed"

    # Partner-off or missing credentials: return empty search result cleanly.
    return [], "unavailable", 0, "skipped"
