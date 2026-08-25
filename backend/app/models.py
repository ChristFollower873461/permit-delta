from pydantic import BaseModel, Field
from typing import List, Literal

class SourceEvidence(BaseModel):
    title: str = Field(..., max_length=200)
    url: str = Field(..., max_length=500)
    authority_class: Literal["California State Parks", "California Film Commission", "FAA"]
    query_purpose_category: str = Field(..., max_length=100)
    retrieval_time: str = Field(..., max_length=50)
    excerpt: str = Field(..., max_length=1500)
    provider_response_id: str = Field(..., max_length=100)
    latency_ms: int = Field(..., ge=0)

class ReviewRequest(BaseModel):
    scenario_id: Literal[1, 2, 3] = Field(..., description="ID of the scenario: 1 (Control), 2 (Material), or 3 (Conflict)")

class AppReadiness(BaseModel):
    parallel_configured: bool
    vertex_ai_configured: bool
    google_genai_use_vertexai: bool
    configured_mode: Literal["Live Mode Configured (Unverified)", "Live Mode Requested (Credentials Incomplete)", "Offline Safety Fallback"]
    runtime_revision: str = Field(default="local", max_length=100)

class SearchMetadata(BaseModel):
    status: Literal["observed", "failed", "skipped"]
    provider_response_id: str = Field(..., max_length=100)  # actual ID or "unavailable"
    latency_ms: int = Field(..., ge=0)
    retained_source_count: int = Field(..., ge=0)

class ModelMetadata(BaseModel):
    configured_model: Literal["gemini-3.7-flash"]
    provider_version: str = Field(..., max_length=100)  # actual version or "unavailable"
    latency_ms: int = Field(..., ge=0)
    is_vertex_ai: bool
    status: Literal["validated", "failed", "skipped", "fallback"]

class ReviewResult(BaseModel):
    correlation_id: str = Field(..., max_length=100)
    state: Literal[
        "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED", 
        "HOLD: MATERIAL DELTA; CONTACT PARK/CFC", 
        "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY"
    ]
    explanation: str
    destination: str = Field(..., max_length=200)
    next_action: str = Field(..., max_length=500)
    sources: List[SourceEvidence]
    source_freshness: Literal["Current/Fresh", "Unavailable: no retained current evidence"]
    uncertainty_rating: Literal["Low", "Medium", "High", "UNAVAILABLE"]
    readiness: AppReadiness
    search_metadata: SearchMetadata
    model_metadata: ModelMetadata
    timestamp: str = Field(..., max_length=50)
