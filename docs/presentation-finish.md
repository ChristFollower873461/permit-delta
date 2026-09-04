# Permit Delta: Operational Change Review Instrument

## Devpost Story
**Inspiration:** Film production plan revisions happen under tight deadlines. When a call sheet changes at the last minute—such as adding a 75kW generator or a drone—a coordinator needs an immediate, deterministic check to catch material parameter deltas before call-sheet release.
**What it does:** Permit Delta compares issued permit baselines with revised production plans for the synthetic *Sunset Tide* shoot at Leo Carrillo State Park. It uses deterministic local routing to route changes to human owners, retrieves official guidelines from California State Parks and the California Film Commission via Parallel Web Search, and uses Gemini 3.7 Flash via Google's Agent Development Kit (ADK 2.7.1) to synthesize a neutral operational explanation. Retrieved authority evidence is labeled with explicit applicability limits—it never issues autonomous approvals or legal determinations.
**How we built it:** FastAPI backend running Python 3.12, paired with a clean React/TypeScript instrument view. Deterministic local safety invariants enforce hard evidence diversity, fail-closed scanning for authorizing language, and zero-call offline replay.
**Fixed Synthetic Scope & Verification:** Tested against three synthetic controlled test scenarios. Live candidate execution on the newest revision remains subject to post-deploy verification.

## Demo Script (Contiguous ~110s)
*(0:00 - 0:18) Scene: Default view showing synthetic production Sunset Tide at Leo Carrillo State Park with Added Generator selected.*
**Narrator:** "In film production, plan changes happen fast. On this synthetic Sunset Tide shoot at Leo Carrillo State Park, the revised plan adds a 75kW generator to the tide pool sector. We run the operational review right from the top viewport."
*(0:18 - 0:38) Scene: Review completes, view reveals red HOLD banner with State Park Special Events Office destination and Next Human Action.*
**Narrator:** "The system flags the generator delta and routes the handoff to the State Park Special Events Office and the California Film Commission. The human coordinator pauses call-sheet release to submit fire-safety placement plans. The model cannot downgrade this safety route."
*(0:38 - 0:56) Scene: Operator selects 'Contact and schedule' scenario and runs review. Green OWNER REVIEW state appears.*
**Narrator:** "Next, we switch to a non-material contact and schedule reorder. When live partners are available, Parallel retrieves reference guidelines from both state park and film commission domains, and Gemini synthesizes an operational explanation routed to the internal coordinator."
*(0:56 - 1:14) Scene: Focus on Authoritative Reference Sources band showing 'Retrieval status: Retrieved at request time; applicability pending review' and persistent disclaimer.*
**Narrator:** "Notice the honest boundary: retrieval status confirms retrieval at request time, but applicability remains pending human review. Reference citations never confer autonomous legal clearance."
*(1:14 - 1:32) Scene: Operator switches Requested Mode to 'Controlled Outage Replay (Offline)' and runs 'Short-notice drone'. Amber UNKNOWN state appears.*
**Narrator:** "Under a short-notice drone change or an offline partner boundary, the system fails closed to an UNKNOWN state. It displays zero retained sources rather than inventing citations, and routes escalation to the lead permit officer."
*(1:32 - 1:50) Scene: Operator clicks 'Coordinator Brief (.txt)'. The handoff text file opens.*
**Narrator:** "Finally, the coordinator exports a readable handoff brief containing every changed field, routing destination, and source citation for the compliance file. Permit Delta keeps decision ownership with qualified human operators."

## Screenshot Captions
1. **Decision-First Viewport:** Immediate parameter comparison for *Sunset Tide* at Leo Carrillo State Park with primary review actions in the top viewport.
2. **Deterministic Safety Route:** The added 75kW generator delta routes to State Parks Special Events with explicit next human actions.
3. **Honest Retrieval Boundaries:** Retrieved reference sources clearly display 'Retrieval status: applicability pending review' alongside persistent coordinator review notices.
4. **Controlled Outage Fail-Closed:** Selecting outage replay safely fails closed to UNKNOWN with zero fabricated citations.
5. **Coordinator Handoff Export:** Plaintext and JSON exports package changed fields, routing states, and all retained authority excerpts.