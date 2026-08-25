# Permit Delta

Permit Delta is a compact, high-trust operational change review and decision support instrument for film production location managers and coordinators. The application compares issued location permit parameters with real-time plan modifications, retrieves official authority guidelines using Parallel at runtime, enforces deterministic local routing safety rules, and uses Gemini 3.7 Flash via Google's ADK (Agent Development Kit) 2.7.1 session runners to explain the resulting operational state and next review destination.

This is a decision support tool. **It does not provide legal advice or autonomous regulatory approval.** It never states or implies that a production plan is allowed, compliant, valid, approved, insured, safe, or exempt from review.

---

## Controlled Scenarios

The workspace includes three synthetic demo scenarios representing common production change patterns:

1. **Scenario 1: Control Change**
   - *Delta:* Alters scene schedule order and updates an internal, non-permit contact number.
   - *Deterministic Route:* `OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED` (Requires at least two valid, fresh, diverse sources and a safety-validated model explanation to pass to OWNER REVIEW).
   - *Destination:* Internal Production Coordinator.

2. **Scenario 2: Material Change**
   - *Delta:* Adds exactly one 75kW diesel towable generator to a state park tide-pool location.
   - *Deterministic Route:* `HOLD: MATERIAL DELTA; CONTACT PARK/CFC` (Model fallbacks and scenario data are synthetic).
   - *Destination:* State Park Special Events Office & CFC.

3. **Scenario 3: Authority Conflict (Short Notice)**
   - *Delta:* Adds a commercial drone (UAS) tracking shot exactly 5 business days before filming.
   - *Deterministic Route:* `UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY` (Model fallbacks and scenario data are synthetic).
   - *Destination:* Lead Permit Officer.

---

## Architectural & Safety Mandates

1. **Deterministic Decision Control**: Top-level states are completely owned by local deterministic application routing logic. The Gemini model generates safety-neutral explanation narratives but may never create, weaken, or upgrade a decision state.
2. **Hard Evidence Diversity Invariant**: For non-hold scenarios (Scenario 1 & 3), deterministic routing strictly requires **at least two distinct, allowed production-authority hosts and classes** (e.g., California State Parks and California Film Commission). If evidence is insufficient, it immediately fails closed to `UNKNOWN`.
3. **Fail-Closed Model Safety Scanning**: If the model output contains authorizing language (including `allowed`, `compliant`, `valid`, `approved`, `insured`, `safe`, `exempt`, `proceed`, `cleared`, `authorized`, `permitted`, `lawful`, `no further submission`, `does not require`, `go ahead`, or `meets requirements`), or if generation fails, Scenario 1 immediately fails closed from `OWNER REVIEW` to `UNKNOWN`.
4. **Partner-Off Clean Hand**: When `LIVE_PARTNERS=False`, the application returns **zero** retrieved sources (`[]`). It does not invent or present fabricated mock sources as if they were retrieved. Non-hold scenarios (1 & 3) route directly to `UNKNOWN`, while Scenario 2 preserves its deterministic `HOLD` state for the added generator.
5. **Authoritative Domain Restrictions**: Live Parallel Web Search is filtered strictly to HTTPS domains for California Film Commission (`film.ca.gov`), California State Parks (`parks.ca.gov`), and the FAA (`faa.gov`).
6. **No Secrets/Credentials in Source**: The application does not use API keys for Gemini. Production and local live inference use Google Cloud Application Default Credentials (ADC) with `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`.

---

## Technical Stack

- **Backend**: Python 3.12 + FastAPI 0.141.1.
- **Inference**: Google ADK 2.7.1 and Google GenAI 2.19.0.
- **Search**: Parallel Python SDK 1.3.0 (`AsyncParallel` callable).
- **Frontend**: React 18, TypeScript, Vite. Served statically from FastAPI in production.

---

## Local Setup & Execution

### Prerequisites
- Python 3.12 (standard venv)
- Node.js 20+

### 1. Environment Configuration
Copy the template to create a `.env` file:
```bash
cp .env.template .env
```
To run in **Live Mode**, configure Vertex AI Application Default Credentials and configure `.env` as follows:
```ini
GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=True
PARALLEL_API_KEY=your-parallel-api-key-here
LIVE_PARTNERS=True
```
If `LIVE_PARTNERS=False` (default), the tool operates in **Offline Safety Fallback** mode, displaying zero retrieved sources and failing closed non-hold scenarios to `UNKNOWN` to truthfully represent lack of live evidence.

### 2. Run Backend
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
The FastAPI server runs at `http://127.0.0.1:8000`.

### 3. Run Frontend (Development)
Open a separate terminal window:
```bash
cd frontend
npm install
npm run dev
```
The Vite dev server runs at `http://localhost:3000` and proxies `/api` calls to the FastAPI backend.

---

## Production Build & Containerization

To run the unified, same-container production build locally:

### 1. Build Docker Container
```bash
docker build -t permit-delta .
```

### 2. Run Docker Container
```bash
docker run -p 8000:8000 \
  -e LIVE_PARTNERS=False \
  permit-delta
```
Visit `http://localhost:8000` to interact with the production bundle served directly by FastAPI.

---

## Testing & Verification

Focused unit and mock integration tests verify routing logic, exact-match hosts, denylist checks, Parallel response structures, Google ADK session runner states, explicit review activation, truthful offline/failed metadata, and frontend accessibility semantics.

Run pytest inside the `backend` folder:
```bash
cd backend
python -m pytest tests/ -v
```

Run the focused frontend tests inside the `frontend` folder:
```bash
cd frontend
npm test
```

---

## Verification Status

For this release candidate:
- **Local Tests and Build:** Observed and fully verified (25 focused backend tests and 10 focused frontend tests pass; the frontend production build compiles successfully).
- **Bounded Local Live Canary:** One explicit Scenario 1 application run completed against Parallel Search and Vertex AI. It retained three allowed official sources, rejected returned sources outside the configured allowlist, and recorded the provider-returned `gemini-3.7-flash` model version. This proves the combined local application path only; it is not hosted-runtime evidence.
- **Python 3.12 Container Target:** Not executed because the local Docker daemon was unavailable.
- **Hosted Cloud Run Execution:** **NOT RUN**. Private deployment and hosted replay remain separate release gates.
