import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import SourceEvidence, ReviewRequest
from app.router import determine_routing_state
from app.search import is_valid_production_host, execute_authority_search
from app.gemini import is_unsafe_text, generate_explanation, UnsafeModelResponseError

# ==========================================
# Fixtures for Router Tests
# ==========================================

@pytest.fixture
def source_state_parks():
    return SourceEvidence(
        title="Valid Parks Guide",
        url="https://parks.ca.gov/rules",
        authority_class="California State Parks",
        query_purpose_category="Verify lead time",
        retrieval_time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        excerpt="Administrative updates do not trigger a material permit delta.",
        provider_response_id="search-12345",
        latency_ms=50
    )

@pytest.fixture
def source_cfc():
    return SourceEvidence(
        title="Valid CFC Handbook",
        url="https://film.ca.gov/handbook",
        authority_class="California Film Commission",
        query_purpose_category="Verify scene changes",
        retrieval_time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        excerpt="Administrative scene updates are on file.",
        provider_response_id="search-12345",
        latency_ms=40
    )

@pytest.fixture
def stale_source():
    return SourceEvidence(
        title="Stale Source",
        url="https://film.ca.gov/handbook",  # Distinct host to pass diversity invariant
        authority_class="California Film Commission",  # Distinct class
        query_purpose_category="Verification",
        retrieval_time=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat().replace("+00:00", "Z"),  # Stale timestamp
        excerpt="Old instructions",
        provider_response_id="search-12345",
        latency_ms=50
    )

# ==========================================
# Deterministic Router Unit Tests (Invariant F)
# ==========================================

def test_scenario_1_control_flow_requires_two_diverse_sources(source_state_parks, source_cfc):
    """
    Scenario 1 with fresh, diverse sources (two distinct hosts/classes)
    must successfully resolve to OWNER REVIEW.
    """
    state, destination, next_action, uncertainty, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks, source_cfc],
        live_partners_enabled=True
    )
    assert state == "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED"
    assert destination == "Internal Production Coordinator"
    assert "human review" in next_action
    assert uncertainty == "Low"
    assert len(verified) == 2

def test_insufficient_sources_fail_closed_to_unknown(source_state_parks):
    """
    If only one source is passed, the evidence diversity invariant fails,
    and routing must fail closed to UNKNOWN.
    """
    state, destination, next_action, uncertainty, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks],
        live_partners_enabled=True
    )
    assert state == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert "diversity" in next_action.lower()
    assert uncertainty == "High"

def test_duplicate_host_sources_fail_closed_to_unknown(source_state_parks):
    """
    If multiple sources belong to the same host/class, diversity is insufficient,
    and routing must resolve to UNKNOWN.
    """
    duplicate_source = source_state_parks.model_copy(update={"title": "Duplicate Parks Source"})
    state, destination, next_action, uncertainty, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks, duplicate_source],
        live_partners_enabled=True
    )
    assert state == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert "diversity" in next_action.lower()

def test_scenario_2_retains_hold_even_with_one_source(source_state_parks):
    """
    Scenario 2 (Generator Addition) is a physical hazard delta and must retain its
    HOLD state deterministically even if sources are insufficient.
    """
    state, destination, next_action, _, verified = determine_routing_state(
        scenario_id=2,
        sources=[source_state_parks],
        live_partners_enabled=True
    )
    assert state == "HOLD: MATERIAL DELTA; CONTACT PARK/CFC"
    assert "Pause the revised call-sheet handoff" in next_action
    assert "Do NOT film" not in next_action

def test_stale_source_causes_unknown_routing(source_state_parks, stale_source):
    """
    Any stale source (older than 24 hours) in a non-hold scenario forces UNKNOWN status,
    provided it passes the host/class diversity check.
    """
    state, _, next_action, _, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks, stale_source],
        live_partners_enabled=True
    )
    assert state == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert len(verified) == 1  # Stale source is discarded during revalidation

# ==========================================
# Focused Spoofed, Missing, and Future Evidence Tests (Routing Boundary)
# ==========================================

def test_spoofed_host_authority_class(source_state_parks, source_cfc):
    """
    Revalidates the authority class on-the-fly and overrides caller-provided labels
    if they do not match the parsed host.
    """
    spoofed_source = source_state_parks.model_copy(update={
        "url": "https://film.ca.gov/rules",  # Actually film.ca.gov host
        "authority_class": "California State Parks"  # Spoofed class label
    })

    state, _, _, _, verified = determine_routing_state(
        scenario_id=1,
        sources=[spoofed_source, source_state_parks],  # Re-validated spoofed host makes both hosts parks.ca.gov
        live_partners_enabled=True
    )
    assert state == "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED"
    assert verified[0].authority_class == "California Film Commission"  # Revalidated correctly!

def test_missing_provider_id_discarded(source_state_parks, source_cfc):
    """
    If a source has a blank provider response ID, the router discards it.
    """
    bad_source = source_cfc.model_copy(update={"provider_response_id": " "})
    state, _, next_action, _, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks, bad_source],
        live_partners_enabled=True
    )
    assert state == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert "diversity" in next_action or "insufficient" in next_action or "lacks" in next_action
    assert len(verified) == 1

def test_missing_excerpt_discarded(source_state_parks, source_cfc):
    """
    If a source has a blank excerpt, the router discards it.
    """
    bad_source = source_cfc.model_copy(update={"excerpt": ""})
    state, _, _, _, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks, bad_source],
        live_partners_enabled=True
    )
    assert state == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert len(verified) == 1

def test_future_timestamp_evidence_rejected(source_state_parks, source_cfc):
    """
    Verifies that evidence with a future timestamp beyond a small clock skew (e.g., 5 minutes)
    is rejected and causes the route to fail closed to UNKNOWN.
    """
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    future_source = source_cfc.model_copy(update={"retrieval_time": future_time})

    state, _, _, _, verified = determine_routing_state(
        scenario_id=1,
        sources=[source_state_parks, future_source],
        live_partners_enabled=True
    )
    assert state == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert len(verified) == 1

# ==========================================
# Exact Production Host Allowlist Tests
# ==========================================

def test_exact_production_host_allowlist():
    # Valid exact hosts
    assert is_valid_production_host("https://film.ca.gov/state-permits") is True
    assert is_valid_production_host("https://parks.ca.gov/rules") is True
    assert is_valid_production_host("https://www.parks.ca.gov/?page_id=29243") is True
    assert is_valid_production_host("https://faa.gov/uas") is True
    assert is_valid_production_host("https://www.faa.gov/uas") is True

    # Invalid hosts/subdomains/spoofing (must be rejected)
    assert is_valid_production_host("http://film.ca.gov/state-permits") is False
    assert is_valid_production_host("https://test.film.ca.gov") is False
    assert is_valid_production_host("https://staging.parks.ca.gov") is False
    assert is_valid_production_host("https://arbitrary.com/film.ca.gov") is False

# ==========================================
# Unsafe Content Denylist Tests (Requirement C)
# ==========================================

def test_denylist_authorizing_language():
    # Unsafe texts containing forbidden words
    assert is_unsafe_text("This plan is approved and safe to proceed.") is True
    assert is_unsafe_text("Rangers allowed the drone. It is compliant.") is True
    assert is_unsafe_text("The production is exempt and cleared.") is True

    # Case insensitive
    assert is_unsafe_text("THIS IS APPROVED.") is True

    # Whole-word validation: substrings like "unsafe" or "safety" or "safely" are safe and MUST NOT trigger denylist!
    assert is_unsafe_text("This plan is unsafe and has several safety gaps.") is False
    assert is_unsafe_text("Rangers safely recorded the scene order.") is False

# ==========================================
# Focused Parallel 1.3.0 & ADK 2.7.1 API Mocks (Requirement G)
# ==========================================

@pytest.mark.anyio
@patch("app.search.config")
async def test_exactly_one_async_parallel_call_and_parsing(mock_config):
    """
    Verifies that execute_authority_search executes exactly one call to AsyncParallel,
    correctly parses response fields, and rejects invalid URLs.
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.PARALLEL_API_KEY = "test-key"

    # Mocking Parallel 1.3.0 Response signature
    mock_result_1 = MagicMock()
    mock_result_1.url = "https://film.ca.gov/permitted-areas"
    mock_result_1.title = "CFC Areas"
    mock_result_1.excerpts = ["Line 1 of instructions.", "Line 2 of instructions."]
    mock_result_1.publish_date = "2026-08-20"

    mock_result_2 = MagicMock()
    mock_result_2.url = "https://test.film.ca.gov/unauthorized"  # Rejected url
    mock_result_2.title = "Spoof"
    mock_result_2.excerpts = ["Bad"]
    mock_result_2.publish_date = "2026-08-20"

    mock_response = MagicMock()
    mock_response.search_id = "test-search-id-abc"
    mock_response.session_id = "session-id-123"
    mock_response.results = [mock_result_1, mock_result_2]

    # Create mock AsyncParallel client with mock Callable 'search'
    mock_client_instance = MagicMock()
    mock_client_instance.search = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("parallel.AsyncParallel", return_value=mock_client_instance) as mock_class:
        sources, search_id, latency, status = await execute_authority_search(scenario_id=1, query_purpose_category="administrative guidelines")

        # Verify the AsyncParallel constructor is called exactly once with api_key="test-key" and max_retries=0
        mock_class.assert_called_once_with(api_key="test-key", max_retries=0)

        # Verify exactly one call to the search callable is made
        mock_client_instance.search.assert_called_once()

        # Verify complete exact client.search kwargs (no unsupported keys passed)
        called_kwargs = mock_client_instance.search.call_args[1]
        assert called_kwargs["mode"] == "basic"
        assert called_kwargs["max_chars_total"] == 10000
        assert called_kwargs["advanced_settings"] == {
            "max_results": 5,
            "excerpt_settings": {
                "max_chars_per_result": 500
            },
            "source_policy": {
                "include_domains": ["film.ca.gov", "parks.ca.gov", "faa.gov"]
            }
        }

        # Verify only allowlisted URL is retained
        assert len(sources) == 1
        assert sources[0].provider_response_id == "test-search-id-abc"
        assert sources[0].excerpt == "Line 1 of instructions. Line 2 of instructions."

        # Verify context manager was entered and exited correctly
        mock_client_instance.__aenter__.assert_called_once()
        mock_client_instance.__aexit__.assert_called_once_with(None, None, None)

@pytest.mark.anyio
@patch("app.search.config")
async def test_async_parallel_lifecycle_on_exception(mock_config):
    """
    Verifies that if search raises an exception, the AsyncParallel client
    is still entered and exited/closed cleanly, and the exception is processed.
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.PARALLEL_API_KEY = "test-key"

    mock_client_instance = MagicMock()
    mock_client_instance.search = AsyncMock(side_effect=ValueError("Search error"))
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("parallel.AsyncParallel", return_value=mock_client_instance) as mock_class:
        sources, search_id, latency, status = await execute_authority_search(scenario_id=1, query_purpose_category="administrative guidelines")

        # Verify it fails cleanly and returns empty source list
        assert sources == []
        assert status == "failed"

        # Verify context manager entry and exit occurred
        mock_client_instance.__aenter__.assert_called_once()
        mock_client_instance.__aexit__.assert_called_once()
        # Verify __aexit__ was called with an exception (ValueError)
        args, kwargs = mock_client_instance.__aexit__.call_args
        assert issubclass(args[0], ValueError)

@pytest.mark.anyio
@patch("app.search.config")
async def test_controlled_replay_override_skips_parallel_even_when_configured(mock_config):
    mock_config.LIVE_PARTNERS = True
    mock_config.PARALLEL_API_KEY = "test-key"

    with patch("parallel.AsyncParallel", side_effect=AssertionError("Parallel must not be constructed")) as mock_class:
        sources, search_id, latency, search_status = await execute_authority_search(
            1,
            "administrative film permit schedule changes",
            live_partners_enabled=False
        )

    assert sources == []
    assert search_id == "unavailable"
    assert latency == 0
    assert search_status == "skipped"
    mock_class.assert_not_called()

@pytest.mark.anyio
@patch("app.gemini.config")
async def test_adk_271_runner_execution_and_safety_checks(mock_config):
    """
    Verifies that generate_explanation follows the ADK 2.7.1 execution path,
    including output schemas, InMemoryRunner initialization, session creation,
    and event.is_final_response() checking, and raises UnsafeModelResponseError
    if the denylist is violated.
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.GOOGLE_CLOUD_PROJECT = "test-project"
    mock_config.GOOGLE_CLOUD_LOCATION = "global"
    mock_config.GOOGLE_GENAI_USE_VERTEXAI = True

    # Mock InMemoryRunner and run_async generator stream
    mock_event = MagicMock()
    mock_event.is_final_response = MagicMock(return_value=True)
    mock_event.model_version = "gemini-3.7-flash-v1.0"
    mock_event.error_code = False
    mock_event.error_message = ""

    # Structured Pydantic Output representation inside ADK event
    from pydantic import BaseModel as TestBaseModel
    class MockOutput(TestBaseModel):
        explanation: str = "This is an unreviewed summary. No forbidden words."
    mock_event.output = MockOutput()
    mock_event.content = None

    mock_session_service = AsyncMock()
    mock_runner_instance = MagicMock()
    mock_runner_instance.app_name = "permit_delta"
    mock_runner_instance.session_service = mock_session_service
    mock_runner_instance.__aenter__ = AsyncMock(return_value=mock_runner_instance)
    mock_runner_instance.__aexit__ = AsyncMock(return_value=None)

    # Async generator for run_async
    async def mock_generator(*args, **kwargs):
        yield mock_event

    mock_runner_instance.run_async = mock_generator

    with patch("google.adk.runners.InMemoryRunner", return_value=mock_runner_instance), \
         patch("google.adk.models.Gemini"), \
         patch("google.adk.agents.Agent"):

        explanation, metadata = await generate_explanation(
            scenario_id=1,
            state="OWNER REVIEW",
            destination="Coordinator",
            differences=["Scene schedule ordering changed."],
            sources=[MagicMock()] # Pass a dummy source so generate_explanation doesn't skip
        )

        assert explanation == "This is an unreviewed summary. No forbidden words."
        assert metadata["provider_version"] == "gemini-3.7-flash-v1.0"
        assert metadata["status"] == "validated"

        # Test Unsafe response denylist trigger
        class UnsafeOutput(TestBaseModel):
            explanation: str = "This plan is approved and safe to proceed."
        mock_event.output = UnsafeOutput()

        with pytest.raises(UnsafeModelResponseError):
            await generate_explanation(
                scenario_id=1,
                state="OWNER REVIEW",
                destination="Coordinator",
                differences=["Scene schedule ordering changed."],
                sources=[MagicMock()]
            )

        # Test empty or whitespace output rejection
        class EmptyOutput(TestBaseModel):
            explanation: str = "   "
        mock_event.output = EmptyOutput()

        with pytest.raises(ValueError):
            await generate_explanation(
                scenario_id=1,
                state="OWNER REVIEW",
                destination="Coordinator",
                differences=["Scene schedule ordering changed."],
                sources=[MagicMock()]
            )

        # Verify context manager was entered and exited correctly
        assert mock_runner_instance.__aenter__.call_count == 3
        assert mock_runner_instance.__aexit__.call_count == 3

@pytest.mark.anyio
@patch("app.gemini.config")
async def test_in_memory_runner_lifecycle_on_exception(mock_config):
    """
    Verifies that if an exception is raised during generate_explanation
    (such as a run_async error or denylist violation), InMemoryRunner is still entered
    and exited/closed correctly, and the exception is propagated.
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.GOOGLE_CLOUD_PROJECT = "test-project"
    mock_config.GOOGLE_CLOUD_LOCATION = "global"
    mock_config.GOOGLE_GENAI_USE_VERTEXAI = True

    mock_event = MagicMock()
    mock_event.is_final_response = MagicMock(return_value=True)
    mock_event.model_version = "gemini-3.7-flash-v1.0"
    mock_event.error_code = False
    mock_event.output = "Plain text which fails schema validation"
    mock_event.content = None

    mock_session_service = AsyncMock()
    mock_runner_instance = MagicMock()
    mock_runner_instance.app_name = "permit_delta"
    mock_runner_instance.session_service = mock_session_service
    mock_runner_instance.__aenter__ = AsyncMock(return_value=mock_runner_instance)
    mock_runner_instance.__aexit__ = AsyncMock(return_value=None)

    async def mock_generator(*args, **kwargs):
        yield mock_event
    mock_runner_instance.run_async = mock_generator

    with patch("google.adk.runners.InMemoryRunner", return_value=mock_runner_instance), \
         patch("google.adk.models.Gemini"), \
         patch("google.adk.agents.Agent"):

        # This will raise a ValueError due to output format being unsupported string
        with pytest.raises(ValueError):
            await generate_explanation(
                scenario_id=1,
                state="OWNER REVIEW",
                destination="Coordinator",
                differences=["Scene schedule ordering changed."],
                sources=[MagicMock()]
            )

        # Verify context manager entry and exit occurred
        mock_runner_instance.__aenter__.assert_called_once()
        mock_runner_instance.__aexit__.assert_called_once()

        # Verify __aexit__ was called with an exception (ValueError)
        args, kwargs = mock_runner_instance.__aexit__.call_args
        assert issubclass(args[0], ValueError)

@pytest.mark.anyio
@pytest.mark.parametrize(
    "output_data, should_raise",
    [
        ({"explanation": "This is a clean dictionary output. No bad keywords."}, False),
        ('{"explanation": "This is a clean correct JSON string output."}', False),
        ("Plain unformatted final narrative text representing explanation.", True), # Raises schema match failure because it is string but not dictionary JSON
        (None, True), # Malformed / None raises failure
        ("   ", True), # Whitespace raises failure
        ('{"bad": "JSON without explanation field."}', True) # Invalid schema raises failure
    ]
)
@patch("app.gemini.config")
async def test_adk_event_output_robust_parsing(mock_config, output_data, should_raise):
    """
    Requirement 5: Test robust parsing of event.output.
    Verifies that dictionary outputs, valid JSON string outputs are accepted,
    while unsupported non-object strings, empty values, or schema mismatches raise failures.
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.GOOGLE_CLOUD_PROJECT = "test-project"
    mock_config.GOOGLE_CLOUD_LOCATION = "global"
    mock_config.GOOGLE_GENAI_USE_VERTEXAI = True

    mock_event = MagicMock()
    mock_event.is_final_response = MagicMock(return_value=True)
    mock_event.model_version = "gemini-3.7-flash-v1"
    mock_event.error_code = False
    mock_event.error_message = ""
    mock_event.output = output_data
    mock_event.content = None

    mock_session_service = AsyncMock()
    mock_runner_instance = MagicMock()
    mock_runner_instance.app_name = "permit_delta"
    mock_runner_instance.session_service = mock_session_service
    mock_runner_instance.__aenter__ = AsyncMock(return_value=mock_runner_instance)
    mock_runner_instance.__aexit__ = AsyncMock(return_value=None)

    async def mock_generator(*args, **kwargs):
        yield mock_event
    mock_runner_instance.run_async = mock_generator

    with patch("google.adk.runners.InMemoryRunner", return_value=mock_runner_instance), \
         patch("google.adk.models.Gemini"), \
         patch("google.adk.agents.Agent"):

        if should_raise:
            with pytest.raises(ValueError):
                await generate_explanation(
                    scenario_id=1,
                    state="OWNER REVIEW",
                    destination="Coordinator",
                    differences=["Scene schedule order."],
                    sources=[MagicMock()]
                )
        else:
            explanation, metadata = await generate_explanation(
                scenario_id=1,
                state="OWNER REVIEW",
                destination="Coordinator",
                differences=["Scene schedule order."],
                sources=[MagicMock()]
            )
            assert "explanation" in metadata["configured_model"] or metadata["status"] == "validated"

        # Verify context manager entry and exit occurred correctly
        mock_runner_instance.__aenter__.assert_called_once()
        mock_runner_instance.__aexit__.assert_called_once()

# ==========================================
# FastAPI Endpoints Integration / Mock Tests
# ==========================================

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_readiness_endpoint():
    """
    Truthfully checks the readiness API endpoint config state.
    """
    response = client.get("/api/readiness")
    assert response.status_code == 200
    data = response.json()
    assert "parallel_configured" in data
    assert "vertex_ai_configured" in data
    assert "configured_mode" in data

@patch("app.api.config")
def test_api_readiness_incomplete_when_vertex_disabled(mock_config):
    """
    Requirement 2: Proves that a false Vertex flag yields "Credentials Incomplete".
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.PARALLEL_API_KEY = "present"
    mock_config.GOOGLE_CLOUD_PROJECT = "present"
    mock_config.GOOGLE_GENAI_USE_VERTEXAI = False  # False Vertex AI flag
    mock_config.RUNTIME_REVISION = "local"

    response = client.get("/api/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["configured_mode"] == "Live Mode Requested (Credentials Incomplete)"

@patch("app.api.execute_authority_search", new_callable=AsyncMock)
@patch("app.api.generate_explanation", new_callable=AsyncMock)
@patch("app.api.config")
def test_api_review_success_control_flow(mock_config, mock_gemini, mock_search, source_state_parks, source_cfc):
    """
    Verifies that the FastAPI review endpoint successfully routes Scenario 1
    when diverse, fresh evidence and safe model responses are observed.
    """
    mock_config.LIVE_PARTNERS = True  # Patch config live partners state to True for this endpoint run
    mock_config.RUNTIME_REVISION = "local"
    mock_search.return_value = ([source_state_parks, source_cfc], "search-id-abc", 15, "observed")
    mock_gemini.return_value = ("Safe explanation.", {"configured_model": "gemini-3.7-flash", "provider_version": "v1.0-mock", "latency_ms": 12, "is_vertex_ai": True, "status": "validated"})

    response = client.post("/api/review", json={"scenario_id": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED"
    assert data["model_metadata"]["status"] == "validated"
    assert data["model_metadata"]["provider_version"] == "v1.0-mock"
    assert data["partner_mode"] == "live"

    # Requirement 3: Assert that retained_source_count == len(sources)
    assert data["search_metadata"]["retained_source_count"] == len(data["sources"])

@patch("app.api.execute_authority_search", new_callable=AsyncMock)
@patch("app.api.generate_explanation", new_callable=AsyncMock)
@patch("app.api.config")
def test_api_controlled_replay_skips_live_model_path(mock_config, mock_gemini, mock_search):
    mock_config.LIVE_PARTNERS = True
    mock_config.PARALLEL_API_KEY = "present"
    mock_config.GOOGLE_CLOUD_PROJECT = "present"
    mock_config.GOOGLE_GENAI_USE_VERTEXAI = True
    mock_config.RUNTIME_REVISION = "test-revision"
    mock_search.return_value = ([], "unavailable", 0, "skipped")

    response = client.post(
        "/api/review",
        json={"scenario_id": 1, "partner_mode": "controlled_replay_off"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["partner_mode"] == "controlled_replay_off"
    assert data["state"] == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert data["sources"] == []
    assert data["search_metadata"]["status"] == "skipped"
    assert data["model_metadata"]["status"] == "skipped"
    mock_search.assert_awaited_once_with(
        1,
        "administrative film permit schedule changes",
        live_partners_enabled=False
    )
    mock_gemini.assert_not_awaited()

@patch("app.api.execute_authority_search", new_callable=AsyncMock)
@patch("app.api.generate_explanation", new_callable=AsyncMock)
@patch("app.api.config")
def test_api_review_gemini_failure_fail_closed(mock_config, mock_gemini, mock_search, source_state_parks, source_cfc):
    """
    Verifies that if Gemini fails or output is unsafe, the FastAPI endpoint
    overrides the OWNER REVIEW state and fails closed to UNKNOWN.
    """
    mock_config.LIVE_PARTNERS = True
    mock_config.RUNTIME_REVISION = "local"
    mock_search.return_value = ([source_state_parks, source_cfc], "search-id-abc", 15, "observed")
    # Simulate safety exception
    mock_gemini.side_effect = UnsafeModelResponseError("Forbidden word hit.")

    response = client.post("/api/review", json={"scenario_id": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    assert data["destination"] == "Lead Permit Officer (Escalated Review)"
    assert data["model_metadata"]["status"] == "failed"
