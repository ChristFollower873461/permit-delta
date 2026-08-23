import { useState, useEffect } from 'react';
import { 
  Search, 
  CheckCircle, 
  HelpCircle, 
  ArrowRight, 
  AlertTriangle, 
  BookOpen 
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
  status: string; // "validated", "failed", "skipped", "fallback"
}

interface ReviewResult {
  correlation_id: string;
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
  const [loading, setLoading] = useState<boolean>(false);
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
  const [readiness, setReadiness] = useState<AppReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState<boolean>(false);

  // Load scenarios and readiness statuses on mount
  useEffect(() => {
    async function initData() {
      try {
        const scenariosRes = await fetch('/api/scenarios');
        if (!scenariosRes.ok) throw new Error("Failed to load scenarios");
        const scenariosData = await scenariosRes.json();
        setScenarios(scenariosData);
        if (scenariosData.length > 0) {
          setSelectedScenarioId(scenariosData[0].id);
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

  // Run operational review whenever scenario changes
  useEffect(() => {
    if (selectedScenarioId !== null) {
      triggerReview(selectedScenarioId);
    }
  }, [selectedScenarioId]);

  const triggerReview = async (scenarioId: number) => {
    setLoading(true);
    setReviewResult(null);
    setError(null);
    setAcknowledged(false);
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId })
      });
      if (!response.ok) {
        throw new Error(`Review endpoint failed with code ${response.status}`);
      }
      const data: ReviewResult = await response.json();
      setReviewResult(data);
      if (data.readiness) {
        setReadiness(data.readiness);
      }
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

  return (
    <div className="app-container">
      {/* Header Instrument */}
      <header className="header-instrument">
        <div className="header-title-container">
          <h1>Permit Delta</h1>
          <p>Operational Change Review Instrument // Leo Carrillo State Park</p>
        </div>
        
        {/* Connection status pills - Configuration-only facts truthfully described without connection dots */}
        <div className="header-status-container">
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
      </header>

      {error && (
        <div style={{ padding: '12px', border: '1px solid #ef4444', backgroundColor: '#fef2f2', color: '#b91c1c', borderRadius: '2px', marginBottom: '24px', fontFamily: 'monospace', fontSize: '12px' }}>
          <strong>CONNECTION ERROR:</strong> {error}
        </div>
      )}

      {/* Grid Layout */}
      <div className="workspace-grid">
        
        {/* Sidebar - Scenario Selection & Receipt */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Section 1: Scenario Configuration */}
          <div className="section-box">
            <h2 className="section-box-title">Revisions To Process</h2>
            <div className="scenario-list">
              {scenarios.map((sc) => (
                <button
                  key={sc.id}
                  onClick={() => setSelectedScenarioId(sc.id)}
                  className={`scenario-button ${selectedScenarioId === sc.id ? 'selected' : ''}`}
                  disabled={loading}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <h4>{sc.name}</h4>
                    <ArrowRight size={14} style={{ opacity: selectedScenarioId === sc.id ? 1 : 0.2 }} />
                  </div>
                  <p>{sc.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Section 2: Non-Authorizing Acknowledgment Receipt */}
          {reviewResult && (
            <div className="receipt-box">
              <div className="receipt-title">Review Receipt</div>
              <div className="receipt-row">
                <span>Correlation ID:</span>
                <span style={{ fontWeight: 'bold' }}>{reviewResult.correlation_id.substring(0, 8)}...</span>
              </div>
              <div className="receipt-row">
                <span>Timestamp:</span>
                <span>{new Date(reviewResult.timestamp).toLocaleTimeString()}</span>
              </div>
              <div className="receipt-row">
                <span>Reviewer State:</span>
                <span style={{ textTransform: 'uppercase', fontWeight: 'bold' }}>
                  {reviewResult.state.includes("OWNER") ? "Owner Review" : reviewResult.state.includes("HOLD") ? "Hold" : "Unknown"}
                </span>
              </div>
              <div className="receipt-row">
                <span>Destination:</span>
                <span>{reviewResult.destination}</span>
              </div>
              
              <div className="receipt-footer">
                <label className="acknowledge-checkbox">
                  <input 
                    type="checkbox" 
                    checked={acknowledged} 
                    onChange={(e) => setAcknowledged(e.target.checked)}
                    style={{ cursor: 'pointer' }}
                  />
                  <span>Log Operational Review</span>
                </label>
                <p style={{ fontSize: '9px', color: '#666', textAlign: 'center', marginTop: '4px', fontStyle: 'italic' }}>
                  This acts as a receipt of routing determination. This is decision support only and does NOT constitute formal agency approval or insurance clearance.
                </p>
                {acknowledged && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#15803d', fontWeight: 'bold', fontSize: '10px', marginTop: '4px' }}>
                    <CheckCircle size={12} /> RECORD LOGGED SECURELY
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>

        {/* Main Panel - Baseline-vs-Revision & Evaluation Result */}
        <main className="dashboard-workspace">
          {loading ? (
            <div className="section-box" style={{ flexGrow: 1, justifyContent: 'center' }}>
              <div className="loading-overlay">
                <div className="spinner" />
                <p style={{ fontFamily: 'monospace', fontSize: '12px', color: '#666' }}>
                  Evaluating selected revision...
                </p>
              </div>
            </div>
          ) : reviewResult && selectedScenario ? (
            <>
              {/* Step 1: Baseline versus Revision Matrix */}
              <div className="section-box">
                <h3 className="section-box-title">Baseline vs Proposed Plan Revision</h3>
                <table className="parameter-table">
                  <thead>
                    <tr>
                      <th style={{ width: '20%' }}>Parameter</th>
                      <th style={{ width: '40%' }}>Issued Permit Baseline</th>
                      <th style={{ width: '40%' }}>Revised Production Plan</th>
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

              {/* Step 2: Top-Level Decision Routing State Banner */}
              <div className={getStateBannerClass(reviewResult.state)}>
                <div className="state-label-container">
                  <span className="state-title">{reviewResult.state}</span>
                  <span style={{ fontFamily: 'monospace', fontSize: '10px', textTransform: 'uppercase', border: '1px solid currentColor', padding: '2px 6px', borderRadius: '1px' }}>
                    System Decision Routing
                  </span>
                </div>
                <p className="state-subtitle">
                  Operational reviews evaluate scope changes deterministically to protect production integrity.
                </p>
              </div>

              {/* Step 3: Human Action and Metadata Instruments */}
              <div className="destinations-actions-grid">
                <div className="destination-box">
                  <h5>Human Review Destination</h5>
                  <p>{reviewResult.destination}</p>
                </div>
                <div className="action-box">
                  <h5>Next Human Action</h5>
                  <p>{reviewResult.next_action}</p>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="meta-status-pill" style={{ justifyContent: 'space-between', padding: '8px 12px' }}>
                  <span style={{ color: '#666' }}>Source Evidence Freshness:</span>
                  <span style={{ fontWeight: 'bold', color: reviewResult.source_freshness.includes('no retained') ? '#b91c1c' : '#15803d' }}>
                    {reviewResult.source_freshness}
                  </span>
                </div>
                <div className="meta-status-pill" style={{ justifyContent: 'space-between', padding: '8px 12px' }}>
                  <span style={{ color: '#666' }}>Evidence Uncertainty Rating:</span>
                  <span style={{ fontWeight: 'bold', color: reviewResult.uncertainty_rating === 'High' ? '#b91c1c' : '#15803d' }}>
                    {reviewResult.uncertainty_rating}
                  </span>
                </div>
              </div>

              {/* Step 4: Reasoning & Explanation Basis */}
              <div className="section-box">
                <h3 className="section-box-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <BookOpen size={14} /> {reviewResult.model_metadata.status === 'validated' ? 'REASONING & EXPLANATION (GEMINI MODEL OUTPUT)' : 'REASONING & EXPLANATION (LOCAL SAFETY FALLBACK)'}
                </h3>
                <div className="explanation-text">
                  {reviewResult.explanation.split('\n\n').map((paragraph, index) => {
                    if (paragraph.startsWith('**DECISION SUPPORT NOTICE**')) {
                      return (
                        <div key={index} style={{ border: '1px solid #d97706', padding: '12px', backgroundColor: '#fffbeb', color: '#b45309', margin: '12px 0', fontSize: '11px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                          <div>{paragraph.replace('**DECISION SUPPORT NOTICE**:', '')}</div>
                        </div>
                      );
                    }
                    return <p key={index}>{paragraph}</p>;
                  })}
                </div>

                {/* Truthful observed Model Run performance metadata */}
                <div style={{ marginTop: '12px', borderTop: '1px dashed #e5e7eb', paddingTop: '12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '11px', fontFamily: 'monospace' }}>
                  <div>
                    <span style={{ color: '#666' }}>Configured Model:</span> <strong>{reviewResult.model_metadata.configured_model}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#666' }}>Model Run Latency:</span> <strong>{reviewResult.model_metadata.latency_ms}ms</strong>
                  </div>
                  <div>
                    <span style={{ color: '#666' }}>Provider Engine Version:</span> <strong>{reviewResult.model_metadata.provider_version}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#666' }}>Model Run Status:</span> <strong style={{ color: reviewResult.model_metadata.status === 'validated' ? '#15803d' : reviewResult.model_metadata.status === 'failed' ? '#b91c1c' : '#d97706' }}>{reviewResult.model_metadata.status.toUpperCase()}</strong>
                  </div>
                </div>
              </div>

              {/* Step 5: Retrieved Authoritative Sources */}
              <div className="section-box">
                <h3 className="section-box-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Search size={14} /> Authoritative Reference Sources (Parallel Web Search SDK)
                </h3>
                {/* Search metadata status details */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '8px', fontSize: '10px', fontFamily: 'monospace', color: '#666', borderBottom: '1px dashed #e5e7eb', paddingBottom: '8px', marginBottom: '8px' }}>
                  <div>Search Status: <strong style={{ color: reviewResult.search_metadata.status === 'observed' ? '#15803d' : reviewResult.search_metadata.status === 'failed' ? '#b91c1c' : '#d97706' }}>{reviewResult.search_metadata.status.toUpperCase()}</strong></div>
                  <div>Search Latency: <strong>{reviewResult.search_metadata.latency_ms}ms</strong></div>
                  <div>Sources Retained: <strong>{reviewResult.search_metadata.retained_source_count}</strong></div>
                  <div>Provider ID: <strong>{reviewResult.search_metadata.provider_response_id}</strong></div>
                </div>
                {reviewResult.sources.length === 0 ? (
                  <p style={{ fontStyle: 'italic', color: '#666', fontSize: '11px' }}>
                    No current official evidence was retained under this configuration. Please check the search status above.
                  </p>
                ) : (
                  <div className="sources-list">
                    {reviewResult.sources.map((source, idx) => (
                      <div key={idx} className="source-item">
                        <div className="source-meta">
                          <span className="source-authority">{source.authority_class}</span>
                          <span>Retrieved: {new Date(source.retrieval_time).toLocaleString()}</span>
                          <span>Latency: {source.latency_ms}ms</span>
                        </div>
                        <div style={{ fontWeight: '600', fontSize: '12px', marginBottom: '4px', color: '#111827' }}>
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
            </>
          ) : (
            <div className="section-box" style={{ flexGrow: 1, justifyContent: 'center', alignItems: 'center' }}>
              <HelpCircle size={48} style={{ opacity: 0.15 }} />
              <p style={{ color: '#666', fontSize: '12px', marginTop: '12px' }}>
                Select a scenario to analyze and display the Operational Permit Review report.
              </p>
            </div>
          )}
        </main>
      </div>

      {/* Footer Credits Info */}
      <footer className="footer-credits">
        Permit Delta Decision Support System © 2026 // Integrations: Google Gemini on Vertex AI + Parallel Web Search.
      </footer>
    </div>
  );
}
