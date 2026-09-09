# Permit Delta: Operational Change Review Instrument

## Tagline
A deterministic, high-trust operational change review instrument for film production coordinators, powered by Google Cloud Vertex AI and Parallel Search.

## Devpost Story

### Inspiration
Film plans change faster than their permit packages. A generator appears on a revised call sheet, a scene moves, or a drone tracking shot is added while issued assumptions remain frozen in another document. The costly failure is not a missing paragraph; it is letting an operational package move while the people making the decision lack current, attributable authority in front of them.

Permit Delta focuses on that narrow operational moment. It helps a location manager or production coordinator catch a changed assumption, retrieve current official evidence, preserve uncertainty, and route a bounded packet to the human owner of the next decision. Every scenario and contact in the demonstration is synthetic.

### What it does
Permit Delta compares a synthetic issued filming permit baseline against a selected production-plan revision. Nothing executes until the coordinator explicitly chooses **Run Operational Review**.

A bounded Parallel Search queries configured official authority hosts. The application rejects off-domain results, checks host diversity invariants, and records source and provider execution metadata. Local deterministic routing rules then assign one of three operational states:

- **Owner Review** for a control change with no detected material permit-scope delta.
- **Material Delta Hold** when the revision adds a 75kW diesel towable generator at a tide-pool location.
- **Unknown** when current authority is missing, stale, conflicting, or fails closed.

Gemini 3.7 Flash on Vertex AI (via Google ADK 2.7.1) explains the retained evidence and names the human handoff destination. The model cannot create, weaken, or upgrade the deterministic state. A controlled outage replay disables both partner calls for one visibly labeled request and proves that the non-hold path fails closed to `UNKNOWN` with zero retained sources and skipped model execution.

### Authority Evidence and Applicability Limits
Request-time search retrieval does not establish source freshness or actual permit applicability. Official-domain pages from allowlisted state portals can contain noisy navigation text, general park rules, or guidelines intended for a different location rather than definitive legal proof for a specific shoot. Permit Delta treats retrieved pages strictly as contextual reference evidence for human evaluation, never as autonomous regulatory approvals or compliance findings.

### How we built it
The application pairs a React and TypeScript instrument view with a Python 3.12 FastAPI backend. Parallel Search (`AsyncParallel` SDK) performs bounded authority retrieval restricted strictly to California State Parks (`parks.ca.gov`), California Film Commission (`film.ca.gov`), and the FAA (`faa.gov`).

Google's Agent Development Kit (ADK 2.7.1) runs the Gemini 3.7 Flash explanation agent on Vertex AI using Application Default Credentials. The agent receives only the detected delta, retained sources, deterministic route, and named destination. A structured output schema and fail-closed safety scanner inspect generated text for forbidden authorizing terms (such as "approved", "compliant", "safe", or "exempt"), immediately forcing `UNKNOWN` if unsafe language appears.

### Challenges & Verification
The hardest engineering challenge was separating retrieval success, usable evidence, model output, and decision authority. A search provider can return results that application rules must reject, and a model can generate fluent prose that introduces unwarranted claims.

Permit Delta is deployed live at 100% traffic on Google Cloud Run (`permit-delta-public-f2a3762763`). Our live evidence verification session exercised two live operational reviews: the added generator routing to `HOLD` with State Park Special Events Office & CFC handoff, and the contact/schedule change routing to `OWNER REVIEW` for Internal Production Coordinator handoff, observing Parallel Search and `gemini-3.7-flash` on Vertex AI metadata. We then ran a controlled outage replay on the same contact/schedule scenario, verifying a zero-call fail-closed `UNKNOWN` result. The mobile layout was visually inspected at 390x844 on the live result without extra requests.

### What we learned & Next steps
We learned that agentic workflows earn trust by demonstrating what they refuse to authorize and proving that uncertainty is a valid product outcome. Parallel is load-bearing rather than decorative: removing live retrieval visibly destroys the pipeline's ability to clear a non-hold route.

Our next product steps focus on structured validation with working production coordinators and location managers, improved source relevance and text extraction to filter navigation noise, and carefully scoped new change categories within deterministic safety bounds.

## Demo Plan
1. **Initial Viewport & Added Generator Delta:** Show the synthetic Sunset Tide shoot at Leo Carrillo State Park. Select the "Added generator" scenario and run the operational review.
2. **Deterministic HOLD Routing:** Highlight the resulting red HOLD banner, routing the handoff to the State Park Special Events Office and CFC. Emphasize the next human action to pause call-sheet handoff for fire-safety placement review.
3. **Retrieval Applicability Boundary:** Point out the retained sources and the execution receipt. Note that references include general rules and do not constitute legal proof of applicability.
4. **Control Case & Owner Review:** Switch to the "Contact and schedule" scenario. Run the review to show the green OWNER REVIEW state routed to the Internal Production Coordinator.
5. **Mobile Inspection & Desktop Outage Replay:** Inspect the same live "Contact and schedule" OWNER REVIEW result in a 390x844 mobile viewport. Then restore the desktop viewport, select "Controlled Outage Replay (Offline)" for that same case, and run the review to demonstrate the fail-closed UNKNOWN state with zero retained sources and skipped model execution.
6. **Coordinator Handoff Export:** Highlight the Coordinator Brief capability (showing the earlier recorded export action on the generator result as an editorial cut) to generate a readable handoff brief, keeping decision ownership with qualified human operators.
