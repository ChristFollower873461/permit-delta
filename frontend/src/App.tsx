import { useState, useEffect, useRef } from 'react';
import {
  Search,
  AlertTriangle,
  BookOpen,
  Download,
  FileText,
  ChevronRight
} from 'lucide-react';

// Interfaces mapping Python FastAPI types
interface Scenario {
  id: number;
  name: string;
  description: string;
  expected_state: string;
  baseline: Record<string, any>;
  revised: Record<string, any>;
  differences: string[];
}

interface SourceEvidence {
  title: string;
  url: string;
  authority_class: string;
  query_purpose_category: string;
  retrieval_time: string;
  excerpt: string;
  provider_response_id: string;
  latency_ms: number;
}

interface AppReadiness {
  parallel_configured: boolean;
  vertex_ai_configured: boolean;
  google_genai_use_vertexai: boolean;
  configured_mode: string;
  runtime_revision: string;
}

interface SearchMetadata {
  status: string; // "observed", "failed", "skipped"
  provider_response_id: string;
  latency_ms: number;
  retained_source_count: number;
}

interface ModelMetadata {
  configured_model: string;
  provider_version: string;
  latency_ms: number;
  is_vertex_ai: boolean;
  status: string; // "validated", "safety_rejected", "failed", "skipped", "fallback"
  output_used: boolean;
}

const modelRunWasObserved = (metadata: ModelMetadata) =>
  metadata.status === 'validated' || metadata.status === 'safety_rejected';

interface ReviewResult {
  correlation_id: string;
  partner_mode: 'live' | 'controlled_replay_off';
  state: string;
  explanation: string;
  destination: string;
  next_action: string;
  sources: SourceEvidence[];
  source_freshness: string;
  uncertainty_rating: string;
  readiness: AppReadiness;
  search_metadata: SearchMetadata;
  model_metadata: ModelMetadata;
  timestamp: string;
}

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null);
  const [partnerMode, setPartnerMode] = useState<'live' | 'controlled_replay_off'>('live');
  const [loading, setLoading] = useState<boolean>(false);
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
  const [readiness, setReadiness] = useState<AppReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultsRef = useRef<HTMLDivElement | null>(null);

  // Load scenarios and readiness statuses on mount
  useEffect(() => {
    async function initData() {
      try {
        const scenariosRes = await fetch('/api/scenarios');
        if (!scenariosRes.ok) throw new Error("Failed to load scenarios");
        const scenariosData = await scenariosRes.json();
        setScenarios(scenariosData);
        if (scenariosData.length > 0) {
          const defaultScen = scenariosData.find((s: Scenario) => s.id === 2) || scenariosData[0];
          setSelectedScenarioId(defaultScen.id);
        }

        const readinessRes = await fetch('/api/readiness');
        if (readinessRes.ok) {
          const readinessData = await readinessRes.json();
          setReadiness(readinessData);
        }
      } catch (err: any) {
        console.error(err);
        setError("Unable to communicate with Permit Delta backend service.");
      }
    }
    initData();
  }, []);

  const triggerReview = async (scenarioId: number) => {
    setLoading(true);
    setReviewResult(null);
    setError(null);
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId, partner_mode: partnerMode })
      });
      if (!response.ok) {
        throw new Error(`Review endpoint failed with code ${response.status}`);
      }
      const data: ReviewResult = await response.json();
      setReviewResult(data);
      if (data.readiness) {
        setReadiness(data.readiness);
      }
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 60);
    } catch (err: any) {
      console.error(err);
      setError("Operational review execution failed. Ensure local API container is active.");
    } finally {
      setLoading(false);
    }
  };

  const selectedScenario = scenarios.find(s => s.id === selectedScenarioId);

  // Determines background class for current state banner
  const getStateBannerClass = (state: string) => {
    if (state.includes("OWNER REVIEW")) return "state-banner state-owner-review";
    if (state.includes("HOLD")) return "state-banner state-hold";
    return "state-banner state-unknown";
  };

  // Helper to determine if a specific permit field changed
  const hasFieldChanged = (key: string) => {
    if (!selectedScenario) return false;
    const baseVal = selectedScenario.baseline[key];
    const revVal = selectedScenario.revised[key];
    return baseVal !== revVal;
  };

  const getObservedExecutionLabel = () => {
    if (!reviewResult) {
      if (!readiness) return 'Ready';
      if (partnerMode === 'controlled_replay_off') return 'Controlled Outage Replay';
      if (readiness.configured_mode.includes('Live Mode Configured')) return 'Live Partners Configured';
      return 'Offline Safety Fallback';
    }
    if (reviewResult.partner_mode === 'controlled_replay_off') {
      return 'Controlled Outage Replay';
    }
    if (reviewResult.search_metadata.status === 'observed' || reviewResult.model_metadata.status === 'validated') {
      return 'Live Partners (Observed)';
    }
    return 'Offline Fallback (Live Requested)';
  };

  const handleDownloadTxtBrief = () => {
    if (!reviewResult || !selectedScenario) return;
    const changedKeys = Object.keys(selectedScenario.revised).filter(
      k => selectedScenario.baseline[k] !== selectedScenario.revised[k]
    );

    const lines: string[] = [
      '================================================================',
      'PERMIT DELTA — OPERATIONAL CHANGE REVIEW HANDOFF BRIEF',
      '================================================================',
      `Correlation ID:       ${reviewResult.correlation_id}`,
      `Timestamp:            ${reviewResult.timestamp}`,
      `Production Name:      ${selectedScenario.baseline.production_name || 'Sunset Tide'}`,
      `Location:             ${selectedScenario.baseline.location}`,
      `Permit Baseline ID:   ${selectedScenario.baseline.permit_id}`,
      `Requested Mode:       ${reviewResult.partner_mode === 'live' ? 'Live partners' : 'Controlled replay'}`,
      `Observed Execution:   ${getObservedExecutionLabel()}`,
      `Configured Mode:      ${reviewResult.readiness.configured_mode}`,
      `Runtime Revision:     ${reviewResult.readiness.runtime_revision}`,
      `Search Status:        ${reviewResult.search_metadata.status.toUpperCase()} (${reviewResult.search_metadata.retained_source_count} retained)`,
      `Model Status:         ${reviewResult.model_metadata.status.toUpperCase()}`,
      '',
      '----------------------------------------------------------------',
      'DECISION SUPPORT ROUTING (NOT LEGAL ADVICE)',
      '----------------------------------------------------------------',
      `Routing State:        ${reviewResult.state}`,
      `Review Destination:   ${reviewResult.destination}`,
      `Next Human Action:    ${reviewResult.next_action}`,
      `Applicability Note:   Retrieved evidence does not prove permit applicability. Manual review required.`,
      '',
      '----------------------------------------------------------------',
      'CHANGED PRODUCTION FIELDS',
      '----------------------------------------------------------------',
      ...(changedKeys.length === 0
        ? ['  No field deltas detected.']
        : changedKeys.map(k => `  * ${k.toUpperCase()}:\n      Baseline: ${selectedScenario.baseline[k]}\n      Revised:  ${selectedScenario.revised[k]}`)),
      '',
      '----------------------------------------------------------------',
      'SYNTHESIZED EXPLANATION',
      '----------------------------------------------------------------',
      reviewResult.explanation,
      '',
      '----------------------------------------------------------------',
      'RETAINED SOURCE EVIDENCE',
      '----------------------------------------------------------------',
      ...(reviewResult.sources.length === 0
        ? ['  No authority source evidence retained under this execution.']
        : reviewResult.sources.map((s, i) =>
            `[Source ${i+1}] ${s.title}\n  Authority: ${s.authority_class}\n  URL:       ${s.url}\n  Retrieved: ${s.retrieval_time}\n  Excerpt:   "${s.excerpt}"\n`
          )),
      '================================================================',
      'SYNTHETIC COMPLIANCE RECORD — DECISION SUPPORT INSTRUMENT ONLY',
      '================================================================'
    ];

    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `permit-delta-brief-${reviewResult.correlation_id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadBrief = () => {
    if (!reviewResult || !selectedScenario) return;
    const changedKeys = Object.keys(selectedScenario.revised).filter(
      k => selectedScenario.baseline[k] !== selectedScenario.revised[k]
    );
    const brief = {
      correlation_id: reviewResult.correlation_id,
      timestamp: reviewResult.timestamp,
      production_name: selectedScenario.baseline.production_name || 'Sunset Tide',
      location: selectedScenario.baseline.location,
      requested_mode: reviewResult.partner_mode,
      observed_execution: getObservedExecutionLabel(),
      readiness: reviewResult.readiness,
      search_metadata: reviewResult.search_metadata,
      model_metadata: reviewResult.model_metadata,
      state: reviewResult.state,
      destination: reviewResult.destination,
      next_action: reviewResult.next_action,
      applicability_note: "Retrieved authority sources do not prove permit applicability. Qualified coordinator manual review required.",
      changed_fields: changedKeys.map(k => ({
        field: k,
        baseline: selectedScenario.baseline[k],
        revised: selectedScenario.revised[k]
      })),
      explanation: reviewResult.explanation,
      baseline: selectedScenario.baseline,
      revised: selectedScenario.revised,
      sources: reviewResult.sources
    };
    const blob = new Blob([JSON.stringify(brief, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `permit-delta-technical-${reviewResult.correlation_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container">
      <header className="header-instrument">
        <div className="header-title-container">
          <h1>Permit Delta</h1>
          <div className="header-sub-row">
            <span className="production-tag">Production: <strong>Sunset Tide</strong></span>
            <span className="separator-bullet">•</span>
            <span className="location-tag">Location: <strong>Leo Carrillo State Park (Sector 1)</strong></span>
          </div>
        </div>
        <div className="execution-status-badge">
          <span className="status-label">Observed Mode:</span>
          <span className="status-value">{getObservedExecutionLabel()}</span>
        </div>
      </header>

      <div className="synthetic-warning">
        <strong>SYNTHETIC COMPLIANCE SCOPE:</strong> This demonstration workspace contains fixed synthetic test scenarios. It does not provide legal advice, policy approvals, or regulatory permits.
      </div>

      {error && (
        <div className="error-alert">
          <strong>CONNECTION ERROR:</strong> {error}
        </div>
      )}

      <main className="main-workspace">
        {/* 1. Primary Action & Execution Controls Bar (In Top Viewport) */}
        <div className="primary-action-bar">
          <div className="action-bar-left">
            <button
              onClick={() => triggerReview(selectedScenarioId!)}
              disabled={loading || selectedScenarioId === null}
              className="run-review-button"
            >
              {loading ? 'Running Operational Review...' : 'Run Operational Review'}
            </button>
            <div className="mode-selector-group">
              <label htmlFor="partner-mode-select" className="mode-label">Requested Partner Mode:</label>
              <select
                id="partner-mode-select"
                value={partnerMode}
                onChange={(e) => {
                  setPartnerMode(e.target.value as 'live' | 'controlled_replay_off');
                  setReviewResult(null);
                  setError(null);
                }}
                disabled={loading}
                className="mode-select"
              >
                <option value="live">Live Partners (Search & Gemini)</option>
                <option value="controlled_replay_off">Controlled Outage Replay (Offline)</option>
              </select>
            </div>
          </div>
          <div className="action-bar-right">
            <button
              onClick={handleDownloadTxtBrief}
              disabled={loading || !reviewResult}
              className="download-button"
              title="Download human-readable handoff brief for coordinators"
            >
              <FileText size={14} /> Coordinator Brief (.txt)
            </button>
            <button
              onClick={handleDownloadBrief}
              disabled={loading || !reviewResult}
              className="download-button-secondary"
              title="Download structured JSON technical export"
            >
              <Download size={14} /> Technical JSON
            </button>
          </div>
        </div>

        {/* 2. Scenario Selection (Neutral full names) */}
        <div className="scenario-nav-band">
          <span className="scenario-nav-title">Change Case:</span>
          <div className="scenario-tabs" role="tablist">
            {scenarios.map((sc) => (
              <button
                key={sc.id}
                role="tab"
                aria-selected={selectedScenarioId === sc.id}
                onClick={() => {
                  if (selectedScenarioId !== sc.id) {
                    setSelectedScenarioId(sc.id);
                    setReviewResult(null);
                    setError(null);
                  }
                }}
                className={`scenario-tab ${selectedScenarioId === sc.id ? 'selected' : ''}`}
                disabled={loading}
              >
                {sc.name}
              </button>
            ))}
          </div>
        </div>

        {/* 3. Baseline vs Revision Parameter Comparison */}
        {selectedScenario && (
          <div className="content-band comparison-band">
            <div className="comparison-header-wrap">
              <h2 className="band-title">
                {selectedScenario.name}
              </h2>
              <p className="band-subtitle">{selectedScenario.description}</p>
            </div>
            <div className="table-scroll-container">
              <table className="parameter-table">
                <thead>
                  <tr>
                    <th style={{ width: '22%' }}>Parameter</th>
                    <th style={{ width: '39%' }}>Issued Permit Baseline</th>
                    <th style={{ width: '39%' }}>Revised Production Plan</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="param-name">Permit ID</td>
                    <td className="param-baseline">{selectedScenario.baseline.permit_id}</td>
                    <td className={`param-revised ${hasFieldChanged('permit_id') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.permit_id}
                    </td>
                  </tr>
                  <tr>
                    <td className="param-name">Film Date</td>
                    <td className="param-baseline">{selectedScenario.baseline.film_date}</td>
                    <td className={`param-revised ${hasFieldChanged('film_date') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.film_date}
                    </td>
                  </tr>
                  <tr>
                    <td className="param-name">Location</td>
                    <td className="param-baseline">{selectedScenario.baseline.location}</td>
                    <td className={`param-revised ${hasFieldChanged('location') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.location}
                    </td>
                  </tr>
                  <tr>
                    <td className="param-name">Crew Size</td>
                    <td className="param-baseline">{selectedScenario.baseline.crew_size}</td>
                    <td className={`param-revised ${hasFieldChanged('crew_size') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.crew_size}
                    </td>
                  </tr>
                  <tr>
                    <td className="param-name">Generator</td>
                    <td className="param-baseline">{selectedScenario.baseline.generator}</td>
                    <td className={`param-revised ${hasFieldChanged('generator') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.generator}
                    </td>
                  </tr>
                  <tr>
                    <td className="param-name">UAS / Drone</td>
                    <td className="param-baseline">{selectedScenario.baseline.drone}</td>
                    <td className={`param-revised ${hasFieldChanged('drone') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.drone}
                    </td>
                  </tr>
                  <tr>
                    <td className="param-name">Description</td>
                    <td className="param-baseline">{selectedScenario.baseline.description}</td>
                    <td className={`param-revised ${hasFieldChanged('description') ? 'highlight' : ''}`}>
                      {selectedScenario.revised.description}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 4. Results Area */}
        {loading ? (
          <div className="loading-overlay">
            <div className="spinner" />
            <p style={{ fontFamily: 'ui-monospace, Consolas, monospace', fontSize: '14px', color: '#4b5563' }}>Evaluating selected plan revision...</p>
          </div>
        ) : reviewResult && selectedScenario ? (
          <div className="results-container" ref={resultsRef}>
            {/* State Banner */}
            <div className={getStateBannerClass(reviewResult.state)}>
              <div className="state-label-container">
                <span className="state-title">{reviewResult.state}</span>
                <span className="state-badge">Deterministic Local Routing</span>
              </div>
            </div>

            {/* Destination & Action */}
            <div className="destinations-actions-grid">
              <div className="destination-box">
                <div className="dest-action-label">Human Review Destination</div>
                <div className="dest-action-value">{reviewResult.destination}</div>
              </div>
              <div className="action-box">
                <div className="dest-action-label">Next Human Action</div>
                <div className="dest-action-value">{reviewResult.next_action}</div>
              </div>
            </div>

            {/* Persistent Human Applicability Boundary Note */}
            <div className="applicability-persistent-note">
              <AlertTriangle size={16} className="note-icon" />
              <div className="note-body">
                <strong>HUMAN APPLICABILITY BOUNDARY:</strong> Retrieved reference evidence does not prove permit applicability or confer regulatory clearance. The internal coordinator or designated park officer must independently verify physical and jurisdictional requirements before call-sheet release.
              </div>
            </div>

            {/* Explanation Band */}
            <div className="content-band narrative-band">
              <h3 className="band-title"><BookOpen size={16} /> Reasoning & Operational Synthesis</h3>
              <div className="explanation-text">
                {reviewResult.explanation.split('\n\n').map((paragraph, index) => {
                  if (paragraph.startsWith('**DECISION SUPPORT NOTICE**')) {
                    return (
                      <div key={index} className="decision-support-callout">
                        <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                        <div>{paragraph.replace('**DECISION SUPPORT NOTICE**:', '')}</div>
                      </div>
                    );
                  }
                  return <p key={index}>{paragraph}</p>;
                })}
              </div>
            </div>

            {/* Reference Sources Band */}
            <div className="content-band sources-band">
              <div className="sources-header-row">
                <h3 className="band-title"><Search size={16} /> Authoritative Reference Sources</h3>
                <div className="retrieval-status-pill">
                  <span className="pill-label">Retrieval status:</span>
                  <span className={`pill-value ${reviewResult.source_freshness.includes('pending') ? 'status-amber' : 'status-muted'}`}>
                    {reviewResult.source_freshness}
                  </span>
                </div>
              </div>

              {reviewResult.sources.length === 0 ? (
                <p className="no-sources-text">
                  No authority evidence was retained under this execution mode.
                </p>
              ) : (
                <div className="sources-list">
                  {reviewResult.sources.map((source, idx) => (
                    <div key={idx} className="source-item">
                      <div className="source-meta">
                        <span className="source-authority">{source.authority_class}</span>
                        <span className="source-time">Retrieved: {new Date(source.retrieval_time).toLocaleString()}</span>
                      </div>
                      <div className="source-heading">
                        {source.title} — <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-url">{source.url}</a>
                      </div>
                      <div className="source-excerpt">
                        "{source.excerpt}"
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}

        {/* 5. Technical Disclosure */}
        <details className="technical-disclosure">
          <summary><ChevronRight size={14} /> Technical Disclosure & Configuration</summary>
          <div className="disclosure-content">
            <div className="header-status-container" style={{ marginBottom: '16px' }}>
              <div className="meta-status-pill">
                Parallel key: {readiness?.parallel_configured ? 'Present' : 'Not set'}
              </div>
              <div className="meta-status-pill">
                Vertex project: {readiness?.vertex_ai_configured ? 'Set' : 'Not set'}
              </div>
              <div className="meta-status-pill" style={{ fontStyle: 'italic', fontWeight: 'bold' }}>
                Config Mode: {readiness?.configured_mode || 'Loading...'}
              </div>
            </div>
            {reviewResult && (
              <div className="receipt-box">
                <div className="receipt-title">Review Receipt</div>
                <div className="receipt-row">
                  <span>Correlation ID:</span>
                  <span style={{ fontWeight: 'bold' }}>{reviewResult.correlation_id}</span>
                </div>
                <div className="receipt-row">
                  <span>Timestamp:</span>
                  <span>{reviewResult.timestamp}</span>
                </div>
                <div className="receipt-row">
                  <span>Reviewer State:</span>
                  <span style={{ textTransform: 'uppercase', fontWeight: 'bold' }}>
                    {reviewResult.state}
                  </span>
                </div>
                <div className="receipt-row">
                  <span>Destination:</span>
                  <span>{reviewResult.destination}</span>
                </div>
                <div className="receipt-row">
                  <span>Requested Mode:</span>
                  <span>{reviewResult.partner_mode === 'live' ? 'LIVE PARTNERS' : 'CONTROLLED OUTAGE REPLAY'}</span>
                </div>
                <div className="receipt-row">
                  <span>Observed Execution:</span>
                  <span style={{ fontWeight: 'bold' }}>{getObservedExecutionLabel().toUpperCase()}</span>
                </div>
                <div className="receipt-row">
                  <span>Search Status:</span>
                  <span>
                    {reviewResult.search_metadata.status === 'observed'
                      ? `OBSERVED (${reviewResult.search_metadata.latency_ms}ms)`
                      : reviewResult.search_metadata.status === 'failed'
                        ? 'FAILED (EXECUTION DID NOT COMPLETE)'
                        : `${reviewResult.search_metadata.status.toUpperCase()} (NOT RUN)`}
                  </span>
                </div>
                <div className="receipt-row">
                  <span>Search ID:</span>
                  <span>{reviewResult.search_metadata.status === 'observed' ? reviewResult.search_metadata.provider_response_id : 'NOT OBSERVED'}</span>
                </div>
                <div className="receipt-row">
                  <span>Sources Retained:</span>
                  <span>{reviewResult.search_metadata.retained_source_count}</span>
                </div>
                <div className="receipt-row">
                  <span>Model Status:</span>
                  <span>
                    {reviewResult.model_metadata.status === 'validated'
                      ? `VALIDATED (${reviewResult.model_metadata.latency_ms}ms)`
                      : reviewResult.model_metadata.status === 'safety_rejected'
                        ? `REJECTED BY SAFETY GATE (${reviewResult.model_metadata.latency_ms}ms)`
                      : reviewResult.model_metadata.status === 'failed'
                        ? 'FAILED (EXECUTION DID NOT COMPLETE)'
                        : `${reviewResult.model_metadata.status.toUpperCase()} (NOT RUN)`}
                  </span>
                </div>
                <div className="receipt-row">
                  <span>Configured Model:</span>
                  <span>{modelRunWasObserved(reviewResult.model_metadata) ? reviewResult.model_metadata.configured_model : `${reviewResult.model_metadata.configured_model} (Requested)`}</span>
                </div>
                <div className="receipt-row">
                  <span>Provider Version:</span>
                  <span>{modelRunWasObserved(reviewResult.model_metadata) ? reviewResult.model_metadata.provider_version : 'NOT OBSERVED'}</span>
                </div>
                <div className="receipt-row">
                  <span>Observed Vertex:</span>
                  <span>{reviewResult.model_metadata.is_vertex_ai ? "TRUE" : "NOT OBSERVED"}</span>
                </div>
                <div className="receipt-row">
                  <span>Model Output Used:</span>
                  <span>{reviewResult.model_metadata.output_used ? 'YES' : 'NO'}</span>
                </div>
                <div className="receipt-row">
                  <span>Runtime Revision:</span>
                  <span>{reviewResult.readiness.runtime_revision}</span>
                </div>
              </div>
            )}
          </div>
        </details>
      </main>

      <footer className="footer-credits">
        Permit Delta Decision Support System © 2026 // Integrations: Google Gemini on Vertex AI + Parallel Web Search.
      </footer>
    </div>
  );
}
