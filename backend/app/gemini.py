import time
import logging
import uuid
import json
import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field, ValidationError, field_validator
from app.config import config
from app.models import SourceEvidence

logger = logging.getLogger("permit_delta.gemini")

# Authorizing language denylist to prevent liability or false assurances
DENYLIST_WORDS = [
    "allowed", "compliant", "valid", "approved",
    "insured", "safe", "exempt", "proceed", "cleared"
]

class UnsafeModelResponseError(ValueError):
    """Raised when the Gemini model includes forbidden authorizing language."""
    pass

class GeminiExplanationSchema(BaseModel):
    explanation: str = Field(..., max_length=2000, description="The comprehensive, safety-neutral review explanation narrative.")

    @field_validator("explanation", mode="after")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """
        Enforces that the explanation is not empty or whitespace-only after stripping.
        """
        if not v or not v.strip():
            raise ValueError("Explanation cannot be empty or whitespace only.")
        return v

def is_unsafe_text(text: str) -> bool:
    """
    Scans generated text for any forbidden authorizing keywords using whole-word,
    case-insensitive matching to prevent false positives (like 'unsafe' or 'safety').
    """
    lower_text = text.lower()
    for word in DENYLIST_WORDS:
        # Enforce whole-word boundary matches
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, lower_text):
            return True
    return False

def get_fallback_explanation(scenario_id: int, state: str, destination: str) -> str:
    """
    Returns high-quality, pre-calculated, safety-compliant fallback explanations
    when Gemini API is not used, offline, or skipped.
    Contains absolutely zero policy claims or forbidden authorizing words.
    """
    if "OWNER REVIEW" in state:
        return (
            f"Permit Delta has processed a local non-material change. "
            f"Deterministic routing is {state}. "
            f"This review is routed to the {destination} for local logging. "
            f"This represents decision support only."
        )
    elif "HOLD" in state:
        return (
            f"Permit Delta has processed a local plan change introducing a generator. "
            f"Deterministic routing is {state}. "
            f"This introduction is routed to the {destination} for coordination. "
            f"This represents decision support only."
        )
    else:  # UNKNOWN
        if scenario_id == 3:
            return (
                f"Permit Delta has processed a short-notice drone plan change. "
                f"Deterministic routing is {state}. "
                f"This change is routed to the {destination} for immediate review. "
                f"This represents decision support only."
            )
        else:
            return (
                f"Permit Delta could not complete live authority search or model inference. "
                f"Deterministic routing is {state}. "
                f"This review is routed to the {destination} for manual coordination. "
                f"This represents decision support only."
            )

async def generate_explanation(
    scenario_id: int,
    state: str,
    destination: str,
    differences: List[str],
    sources: List[SourceEvidence]
) -> Tuple[str, Dict[str, Any]]:
    """
    Asks Gemini 3.7 Flash to explain the deterministic state and human review destination.
    Uses google-adk and google-genai single-agent setup configured for Vertex AI.
    Enforces the authorizing language denylist on model outputs.

    Returns a Tuple: (explanation_text, metadata)
    """
    logger.info(f"Generating explanation for state: '{state}' (Scenario {scenario_id})")

    metadata = {
        "configured_model": "gemini-3.7-flash",
        "provider_version": "unavailable",
        "latency_ms": 0,
        "is_vertex_ai": config.GOOGLE_GENAI_USE_VERTEXAI,
        "status": "fallback"
    }

    # Validation constraint 1: Do not call Gemini when there is no retained evidence
    if not sources:
        logger.info("No retained source evidence available. Skipping model execution completely.")
        metadata["status"] = "skipped"
        return get_fallback_explanation(scenario_id, state, destination), metadata

    # Validation constraint 2: When LIVE_PARTNERS=True, require Vertex AI project and use-flag to be configured
    if config.LIVE_PARTNERS:
        if not config.GOOGLE_GENAI_USE_VERTEXAI or not config.GOOGLE_CLOUD_PROJECT:
            logger.error("LIVE_PARTNERS is True but Vertex AI is not requested or configured. Failing closed before constructing agent.")
            raise ValueError("Vertex AI requested configurations are missing. Live inference cannot be initialized.")

        try:
            import google.adk.models
            from google.genai import types
            from google.adk.runners import InMemoryRunner
            from google.adk.agents import Agent

            diffs_str = "\n".join([f"- {d}" for d in differences])
            sources_str = "\n\n".join([
                f"Source: {s.title} ({s.url})\nAuthority: {s.authority_class}\nExcerpt: \"{s.excerpt}\""
                for s in sources
            ])

            system_instruction = (
                "You are an expert film production permit compliance assistant. "
                "Your job is to write a highly precise, neutral explanation of the permit state and the next human review destination. "
                "CRITICAL MANDATES:\n"
                "1. This is decision support only, NEVER legal advice or autonomous approval.\n"
                "2. NEVER use authorizing language such as: allowed, compliant, valid, approved, insured, safe, exempt, proceed, or cleared.\n"
                "3. Frame everything as a recommendation for human review and coordination.\n"
                "4. Restrict all conclusions to the provided authoritative source evidence. Do not hallucinate external policies.\n"
                "5. Start the response with a clear summary of the delta and why the specific state applies."
            )

            prompt = (
                f"The Permit Delta System has determined the following deterministic status for the revised production plan:\n\n"
                f"DETERMINISTIC STATE: {state}\n"
                f"HUMAN REVIEW DESTINATION: {destination}\n\n"
                f"PROPOSED REVISION DIFFERENCES:\n"
                f"{diffs_str}\n\n"
                f"RETRIEVED AUTHORITATIVE SOURCES:\n"
                f"{sources_str}\n\n"
                f"Please explain this state, why it applies based on the retrieved sources, and detail the actions "
                f"the production coordinator must take at the destination: {destination}. "
                f"Do not include any forbidden authorizing keywords. Return your response under the explanation field."
            )

            logger.info("Configuring single-agent path via Google ADK 2.7.1 & GenAI Client...")

            agent = Agent(
                name="permit_delta_agent",
                model=google.adk.models.Gemini(
                    model="gemini-3.7-flash",
                    client_kwargs={
                        "vertexai": config.GOOGLE_GENAI_USE_VERTEXAI,
                        "project": config.GOOGLE_CLOUD_PROJECT,
                        "location": config.GOOGLE_CLOUD_LOCATION
                    }
                ),
                instruction=system_instruction,
                output_schema=GeminiExplanationSchema,
                generate_content_config=types.GenerateContentConfig(
                    max_output_tokens=1000,
                    temperature=0.1
                )
            )

            async with InMemoryRunner(agent=agent, app_name="permit_delta") as runner:

                # Use a collision-resistant session ID
                user_id = "coordinator"
                session_id = f"session-{uuid.uuid4()}"

                await runner.session_service.create_session(
                    app_name=runner.app_name,
                    user_id=user_id,
                    session_id=session_id
                )

                start_time = time.time()
                raw_output_text = ""
                provider_version = "unavailable"

                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
                ):
                    # Reject error events without logging verbatim messages
                    if hasattr(event, "error_code") and event.error_code:
                        logger.error("ADK runner flagged an error.")
                        raise ValueError("ADK Runner Error: execution flagged error code.")

                    if event.is_final_response():
                        # Parse event.output robustly, rejecting unsupported types
                        if hasattr(event, "output") and event.output is not None:
                            if isinstance(event.output, BaseModel):
                                raw_output_text = getattr(event.output, "explanation", "")
                            elif isinstance(event.output, dict):
                                raw_output_text = event.output.get("explanation", "")
                            elif isinstance(event.output, str):
                                # Requirement 5: For event.output str, require valid JSON object with explanation or raise
                                try:
                                    parsed_json = json.loads(event.output)
                                    if isinstance(parsed_json, dict) and "explanation" in parsed_json:
                                        raw_output_text = parsed_json.get("explanation", "")
                                    else:
                                        raise ValueError("event.output string must be a JSON object with an explanation field.")
                                except Exception as e:
                                    raise ValueError("event.output string must be a valid JSON object.") from e
                            else:
                                # Reject other unsupported types
                                raise ValueError(f"ADK returned unsupported output structure: {type(event.output)}")
                        elif event.content and event.content.parts:
                            # Fallback parsing on raw content text
                            raw_text = "".join([p.text or "" for p in event.content.parts]).strip()
                            try:
                                # Attempt to parse json block if ADK dumped JSON string
                                parsed_json = json.loads(raw_text)
                                if isinstance(parsed_json, dict):
                                    raw_output_text = parsed_json.get("explanation", "")
                                else:
                                    raw_output_text = raw_text
                            except Exception:
                                raw_output_text = raw_text

                        # Extract model version truthfully if exposed
                        if hasattr(event, "model_version") and event.model_version:
                            provider_version = str(event.model_version).strip() or "unavailable"

                latency_ms = int((time.time() - start_time) * 1000)
                metadata["latency_ms"] = latency_ms
                metadata["provider_version"] = provider_version

                # Enforce validation through Pydantic schema (validates max_length & non-emptiness)
                try:
                    validated_data = GeminiExplanationSchema(explanation=raw_output_text)
                    final_text = validated_data.explanation
                except ValidationError:
                    logger.error("Pydantic output schema validation failed.")
                    raise ValueError("Model output did not match GeminiExplanationSchema.")

                # Scan for denylisted authorizing language using word boundaries
                if is_unsafe_text(final_text):
                    logger.error("Safety violation: Gemini model generated forbidden authorizing language.")
                    raise UnsafeModelResponseError("Model response contains forbidden authorizing language.")

                # Enforce final character bound and truncate
                final_text = final_text.strip()[:2000]
                metadata["status"] = "validated"
                return final_text, metadata

        except Exception:
            logger.error("Error during live Vertex AI ADK runner execution.")
            raise

    # Fallback to pre-defined safety-compliant explanation when partners are offline.
    return get_fallback_explanation(scenario_id, state, destination), metadata
