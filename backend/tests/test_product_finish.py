import pytest
from app.router import determine_routing_state
from app.models import SourceEvidence
from datetime import datetime, timezone

def test_drone_escalation_reason():
    """
    Verifies that Scenario 3 (Drone Addition) deterministically routes to UNKNOWN
    due to predetermined manual authority review, not a fabricated source conflict.
    """
    dummy_source = SourceEvidence(
        title="Valid Parks Guide",
        url="https://parks.ca.gov/rules",
        authority_class="California State Parks",
        query_purpose_category="Verify lead time",
        retrieval_time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        excerpt="Drone rules.",
        provider_response_id="search-123",
        latency_ms=50
    )
    dummy_source_2 = dummy_source.model_copy(update={
        "url": "https://film.ca.gov/rules",
        "authority_class": "California Film Commission"
    })
    
    state, destination, next_action, _, _ = determine_routing_state(
        scenario_id=3,
        sources=[dummy_source, dummy_source_2],
        live_partners_enabled=True
    )
    
    assert state == "UNKNOWN: ESCALATION FOR MANUAL REVIEW"
    assert "manual authority review" in next_action.lower()

@pytest.mark.anyio
async def test_truthful_source_recency_metadata():
    """
    Verifies that the API returns truthful source recency and applicability metadata,
    avoiding overclaims of 'Current/Fresh'.
    """
    from app.api import run_review
    from app.models import ReviewRequest
    from unittest.mock import patch, AsyncMock
    
    with patch("app.api.execute_authority_search", new_callable=AsyncMock) as mock_search, \
         patch("app.api.generate_explanation", new_callable=AsyncMock) as mock_gemini, \
         patch("app.api.config") as mock_config:
         
        mock_config.LIVE_PARTNERS = True
        mock_config.PARALLEL_API_KEY = "test-key"
        mock_config.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_config.GOOGLE_GENAI_USE_VERTEXAI = True
        mock_config.RUNTIME_REVISION = "test-revision-1.0"
        
        dummy_source = SourceEvidence(
            title="Valid Parks Guide",
            url="https://parks.ca.gov/rules",
            authority_class="California State Parks",
            query_purpose_category="Verify lead time",
            retrieval_time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            excerpt="Drone rules.",
            provider_response_id="search-123",
            latency_ms=50
        )
        dummy_source_2 = dummy_source.model_copy(update={
            "url": "https://film.ca.gov/rules",
            "authority_class": "California Film Commission"
        })
        
        mock_search.return_value = ([dummy_source, dummy_source_2], "search-123", 50, "observed")
        mock_gemini.return_value = ("Explanation", {"configured_model": "gemini-3.7-flash", "provider_version": "v1", "latency_ms": 100, "is_vertex_ai": True, "status": "validated", "output_used": True})
        
        request = ReviewRequest(scenario_id=1, partner_mode="live")
        result = await run_review(request)
        
        assert result.source_freshness == "Retrieved at request time; applicability pending review"
