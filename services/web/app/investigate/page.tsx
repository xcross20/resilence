import Link from "next/link";
import {
  DEMO_WORKFLOW_ID,
  type CaseRow,
  type EvaluationRow,
  type WorkflowPayload,
  apiGet,
} from "@/lib/api";
import { formatAttemptCost, projectAttemptCosts, type AttemptCost, type AttemptEvidence } from "@/lib/attempt-cost";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

function parseOffset(value: string | undefined): number {
  if (!value || !/^\d+$/.test(value)) return 0;
  return Number(value) - (Number(value) % PAGE_SIZE);
}

function investigateHref(evaluationId: string, offset: number, caseId?: string): string {
  const params = new URLSearchParams();
  if (evaluationId) params.set("evaluation", evaluationId);
  if (offset > 0) params.set("offset", String(offset));
  if (caseId) params.set("case", caseId);
  const query = params.toString();
  return query ? `/investigate?${query}` : "/investigate";
}

async function loadCases(evaluationId: string, offset: number): Promise<CaseRow[]> {
  const payload = await apiGet<{ cases: CaseRow[] }>(
    `/api/v1/evaluations/${evaluationId}/cases?limit=${PAGE_SIZE}&offset=${offset}`,
  );
  return payload.cases;
}

async function offsetForCase(evaluationId: string, caseId: string, caseCount: number): Promise<number | null> {
  for (let offset = 0; offset < caseCount; offset += PAGE_SIZE) {
    const rows = await loadCases(evaluationId, offset);
    if (rows.some((row) => row.case_id === caseId)) return offset;
    if (rows.length < PAGE_SIZE) return null;
  }
  return null;
}

async function readAttemptCosts(runId: string, side: AttemptCost["side"]): Promise<AttemptCost[]> {
  const evidence = await apiGet<AttemptEvidence>(`/api/v1/executions/${runId}/evidence`);
  return projectAttemptCosts(side, {
    decisions: evidence.decisions,
    attempts: evidence.attempts,
    costs: evidence.costs,
  });
}

export default async function InvestigatePage({
  searchParams,
}: {
  searchParams: Promise<{ evaluation?: string; case?: string; offset?: string }>;
}) {
  const params = await searchParams;
  let error = "";
  let workflow: WorkflowPayload | null = null;
  let evaluations: EvaluationRow[] = [];
  let cases: CaseRow[] = [];
  let offset = parseOffset(params.offset);
  let attemptRows: AttemptCost[] = [];
  let attemptError = "";
  try {
    workflow = await apiGet<WorkflowPayload>(`/api/v1/workflows/${DEMO_WORKFLOW_ID}`);
    evaluations = (await apiGet<{ evaluations: EvaluationRow[] }>(`/api/v1/evaluations?workflow_id=${DEMO_WORKFLOW_ID}`)).evaluations;
    const selected = params.evaluation ?? evaluations[0]?.evaluation_id;
    const caseCount = evaluations.find((row) => row.evaluation_id === selected)?.case_count ?? 0;
    if (selected) {
      if (params.case) {
        const firstPage = await loadCases(selected, offset);
        if (!firstPage.some((row) => row.case_id === params.case)) {
          const located = await offsetForCase(selected, params.case, caseCount);
          if (located !== null) offset = located;
        }
      }
      cases = await loadCases(selected, offset);
    }
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "The API did not respond.";
  }
  const selectedId = params.evaluation ?? evaluations[0]?.evaluation_id ?? "";
  const caseCount = evaluations.find((row) => row.evaluation_id === selectedId)?.case_count ?? cases.length;
  const selectedCase = params.case ? cases.find((row) => row.case_id === params.case) : cases[0];
  if (selectedCase) {
    try {
      const [baseline, candidate] = await Promise.all([
        readAttemptCosts(selectedCase.baseline_run_id, "baseline"),
        readAttemptCosts(selectedCase.candidate_run_id, "candidate"),
      ]);
      attemptRows = [...baseline, ...candidate];
    } catch (caught) {
      attemptError = caught instanceof Error ? caught.message : "The attempt record did not load.";
    }
  }
  const nodes = workflow?.graph?.nodes ?? [];
  const pageEnd = offset + cases.length;
  return (
    <>
      <h1>Investigate</h1>
      <p className="lede">The graph is the stored workflow. Case rows show observed category, verdicts, and cost delta. The selected case lists each stored attempt’s step, method, and cost. Reference labels are not on this read model.</p>
      {error ? <p className="fail">{error}</p> : null}
      <div className="steps">
        {nodes.map((node) => <span className="step" key={node.step_id}>{node.name}</span>)}
      </div>
      <nav className="pager" aria-label="Cases">
        {offset > 0 ? <Link href={investigateHref(selectedId, offset - PAGE_SIZE)}>Previous 50</Link> : <span>Previous 50</span>}
        <span>Cases {cases.length === 0 ? 0 : offset + 1}–{pageEnd} of {caseCount}</span>
        {pageEnd < caseCount ? <Link href={investigateHref(selectedId, offset + PAGE_SIZE)}>Next 50</Link> : <span>Next 50</span>}
      </nav>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Case</th><th>Observed</th><th>Baseline verdict</th><th>Candidate verdict</th><th>Cost delta µUSD</th></tr></thead>
          <tbody>
            {cases.map((row) => (
              <tr key={row.case_id} className={selectedCase?.case_id === row.case_id ? "selected" : ""}>
                <td><Link href={investigateHref(selectedId, offset, row.case_id)}>{row.case_id}</Link></td>
                <td>{row.observed_category ?? "missing"}</td>
                <td>{row.baseline_verdict}</td>
                <td className={row.candidate_critical_violation ? "fail" : ""}>{row.candidate_verdict}</td>
                <td>{row.execution_cost_delta_micro_usd}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedCase ? (
        <section className="detail">
          <small>Selected case</small>
          <h2>{selectedCase.case_id}</h2>
          <p>Observed category {selectedCase.observed_category ?? "missing"}. Route changed: {selectedCase.route_changed ? "yes" : "no"}.</p>
          <p>Baseline {selectedCase.baseline_verdict} ({selectedCase.baseline_reason_code}). Candidate {selectedCase.candidate_verdict} ({selectedCase.candidate_reason_code}).</p>
          <p>Critical candidate violation: {selectedCase.candidate_critical_violation ? "yes" : "no"}.</p>
          {attemptError ? <p className="fail">{attemptError}</p> : null}
          <h3>Attempts</h3>
          <table>
            <thead><tr><th>Side</th><th>Step</th><th>Method</th><th>Cost</th></tr></thead>
            <tbody>
              {attemptRows.map((row) => (
                <tr key={`${row.side}-${row.attemptOrdinal}`}>
                  <td>{row.side}</td>
                  <td>{row.stepId}</td>
                  <td>{row.selectedMethod}</td>
                  <td>{formatAttemptCost(row.amountMicroUsd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {attemptRows.length === 0 && !attemptError ? <p>No attempts are stored for this case.</p> : null}
        </section>
      ) : <p>{error ? null : params.case ? `${params.case} is not in this evaluation.` : "No persisted evaluation cases are available for this workflow."}</p>}
    </>
  );
}
