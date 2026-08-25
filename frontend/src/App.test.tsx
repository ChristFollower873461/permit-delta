import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { vi, describe, beforeEach, afterEach, test, expect } from 'vitest';

const mockScenarios = [
  {
    id: 1,
    name: "Scenario 1",
    description: "Desc 1",
    expected_state: "OWNER REVIEW",
    baseline: { permit_id: "123", generator: "None" },
    revised: { permit_id: "123", generator: "None" },
    differences: []
  },
  {
    id: 2,
    name: "Scenario 2",
    description: "Desc 2",
    expected_state: "HOLD",
    baseline: { permit_id: "123", generator: "None" },
    revised: { permit_id: "123", generator: "75 kW Generator" },
    differences: []
  }
];

const mockReadiness = {
  parallel_configured: false,
  vertex_ai_configured: false,
  google_genai_use_vertexai: false,
  configured_mode: "Offline Safety Fallback",
  runtime_revision: "local"
};

const mockReviewResult = {
  correlation_id: "abc-123",
  state: "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED",
  explanation: "Test explanation",
  destination: "Internal Coordinator",
  next_action: "Log it",
  sources: [],
  source_freshness: "Unavailable: no retained current evidence",
  uncertainty_rating: "UNAVAILABLE",
  readiness: mockReadiness,
  search_metadata: {
    status: "skipped",
    provider_response_id: "unavailable",
    latency_ms: 0,
    retained_source_count: 0
  },
  model_metadata: {
    configured_model: "gemini-3.7-flash",
    provider_version: "unavailable",
    latency_ms: 0,
    is_vertex_ai: false,
    status: "skipped"
  },
  timestamp: "2026-08-24T00:00:00Z"
};

describe('Permit Delta App', () => {
  beforeEach(() => {
    global.fetch = vi.fn((url) => {
      if (url === '/api/scenarios') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockScenarios)
        });
      }
      if (url === '/api/readiness') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadiness)
        });
      }
      if (url === '/api/review') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReviewResult)
        });
      }
      return Promise.reject(new Error('not found'));
    }) as any;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('1. Fresh render fetches scenarios and readiness but does not call POST /api/review', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());

    const fetchCalls = (global.fetch as any).mock.calls;
    const postCalls = fetchCalls.filter((call: any) => call[1]?.method === 'POST');
    expect(postCalls.length).toBe(0);
  });

  test('2. Selecting a scenario updates the comparison but does not call POST /api/review', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());
    expect(screen.getByText('Baseline vs Proposed Plan Revision')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Scenario 2'));
    expect(screen.getByText('75 kW Generator')).toBeInTheDocument();

    const fetchCalls = (global.fetch as any).mock.calls;
    const postCalls = fetchCalls.filter((call: any) => call[1]?.method === 'POST');
    expect(postCalls.length).toBe(0);
  });

  test('3. One explicit Run Review activation issues exactly one POST and disables duplicate activation', async () => {
    let resolveReview: (value: any) => void = () => {};
    const reviewPromise = new Promise((resolve) => {
      resolveReview = resolve;
    });

    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/review') {
        return reviewPromise.then((data) => ({
          ok: true,
          json: () => Promise.resolve(data)
        }));
      }
      if (url === '/api/scenarios') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockScenarios) });
      if (url === '/api/readiness') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockReadiness) });
      return Promise.reject(new Error('not found'));
    });

    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());

    const runBtn = screen.getByRole('button', { name: /Run Review/i });
    await user.click(runBtn);

    expect(runBtn).toBeDisabled();
    await user.click(runBtn);

    const fetchCalls = (global.fetch as any).mock.calls;
    const postCalls = fetchCalls.filter((call: any) => call[1]?.method === 'POST');
    expect(postCalls.length).toBe(1);

    resolveReview(mockReviewResult);
    await waitFor(() => expect(screen.getByText(/Review Receipt/i)).toBeInTheDocument());
  });

  test('4. The visible package is labeled synthetic and contains no real permit or customer file claim', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());
    expect(screen.getByText(/SYNTHETIC DEMONSTRATION DATA/i)).toBeInTheDocument();
    expect(screen.getByText(/no real permit or customer file/i)).toBeInTheDocument();
  });

  test('5. Offline/skipped metadata cannot claim observed Vertex, model, Parallel, or persisted receipt execution', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());

    const runBtn = screen.getByRole('button', { name: /Run Review/i });
    await user.click(runBtn);

    await waitFor(() => expect(screen.getByText(/Review Receipt/i)).toBeInTheDocument());

    expect(screen.getAllByText(/NOT OBSERVED/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/NOT RUN/i).length).toBeGreaterThan(0);
  });

  test('6. The receipt says session-only/not stored and contains no secure-log claim', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());

    const runBtn = screen.getByRole('button', { name: /Run Review/i });
    await user.click(runBtn);

    await waitFor(() => expect(screen.getByText(/Review Receipt/i)).toBeInTheDocument());

    expect(screen.getByText(/session display only and is not stored/i)).toBeInTheDocument();
    expect(screen.queryByText(/RECORD LOGGED SECURELY/i)).not.toBeInTheDocument();
  });

  test('7. Scenario 2 distinguishes deterministic HOLD routing from unavailable external evidence', async () => {
    const holdResult = { ...mockReviewResult, state: "HOLD: MATERIAL DELTA; CONTACT PARK/CFC", uncertainty_rating: "UNAVAILABLE" };
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/review') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(holdResult) });
      }
      if (url === '/api/scenarios') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockScenarios) });
      if (url === '/api/readiness') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockReadiness) });
      return Promise.reject(new Error('not found'));
    });

    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 2')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Scenario 2'));
    const runBtn = screen.getByRole('button', { name: /Run Review/i });
    await user.click(runBtn);

    await waitFor(() => expect(screen.getAllByText(/HOLD: MATERIAL DELTA/i).length).toBeGreaterThan(0));
    expect(screen.getByText('UNAVAILABLE')).toHaveStyle({ color: '#b45309' });
  });

  test('8. Selected-scenario and loading/result accessibility semantics are present', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());

    const listbox = screen.getByRole('listbox');
    expect(listbox).toBeInTheDocument();

    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('aria-live', 'polite');
  });

  test('9. Failed provider paths never contradict themselves with a NOT RUN label', async () => {
    const failedResult = {
      ...mockReviewResult,
      search_metadata: {
        ...mockReviewResult.search_metadata,
        status: 'failed',
        latency_ms: 12
      },
      model_metadata: {
        ...mockReviewResult.model_metadata,
        status: 'failed'
      }
    };

    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/review') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(failedResult) });
      }
      if (url === '/api/scenarios') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockScenarios) });
      if (url === '/api/readiness') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockReadiness) });
      return Promise.reject(new Error('not found'));
    });

    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /Run Review/i }));
    await waitFor(() => expect(screen.getByText(/Review Receipt/i)).toBeInTheDocument());

    expect(screen.queryByText(/FAILED \(NOT RUN\)/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/FAILED \(EXECUTION DID NOT COMPLETE\)/i)).toHaveLength(2);
    expect(screen.getByText('12ms')).toBeInTheDocument();
  });

  test('10. Selecting a different scenario clears the prior state and receipt before another run', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByText('Scenario 1')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /Run Review/i }));
    await waitFor(() => expect(screen.getByText(/Review Receipt/i)).toBeInTheDocument());
    expect(screen.getAllByText(/OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED/i).length).toBeGreaterThan(0);

    await user.click(screen.getByText('Scenario 2'));

    expect(screen.queryByText(/Review Receipt/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED/i)).not.toBeInTheDocument();
    expect(screen.getByText('75 kW Generator')).toBeInTheDocument();

    const fetchCalls = (global.fetch as any).mock.calls;
    const postCalls = fetchCalls.filter((call: any) => call[1]?.method === 'POST');
    expect(postCalls.length).toBe(1);
  });
});
