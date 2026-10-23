import Link from "next/link";
import {
  DEMO_WORKFLOW_ID,
  type CaseRow,
  type EvaluationRow,
  type WorkflowPayload,
  apiGet,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function InvestigatePage({ searchParams }: { searchParams: Promise<{ evaluation?: string; case?: string }> }) {
  const params = await searchParams;
  let error = "";
  let workflow: WorkflowPayload | null = null;
  let evaluations: EvaluationRow[] = [];
  let cases: CaseRow[] = [];
  try {
    workflow = await apiGet<WorkflowPayload>(`/api/v1/workflows/${DEMO_WORKFLOW_ID}`);
    evaluations = (await apiGet<{ evaluations: EvaluationRow[] }>(`/api/v1/evaluations?workflow_id=${DEMO_WORKFLOW_ID}`)).evaluations;
    const selected = params.evaluation ?? evaluations[0]?.evaluation_id;
    if (selected) {
      cases = (await apiGet<{ cases: CaseRow[] }>(`/api/v1/evaluations/${selected}/cases?limit=50`)).cases;
    }
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "The API did not respond.";
  }
  const selectedId = params.evaluation ?? evaluations[0]?.evaluation_id ?? "";
  const selectedCase = cases.find((row) => row.case_id === params.case) ?? cases[0];
  const nodes = workflow?.graph?.nodes ?? [];
  return (
    <>
      <h1>Investigate</h1>
      <p className="lede">The graph is the stored workflow. Case rows show observed category, verdicts, and cost delta. Reference labels are not on this read model.</p>
      {error ? <p className="fail">{error}</p> : null}
      <div className="steps">
        {nodes.map((node) => <span className="step" key={node.step_id}>{node.name}</span>)}
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Case</th><th>Observed</th><th>Baseline verdict</th><th>Candidate verdict</th><th>Cost delta µUSD</th></tr></thead>
          <tbody>
            {cases.map((row) => (
              <tr key={row.case_id} className={selectedCase?.case_id === row.case_id ? "selected" : ""}>
                <td><Link href={`/investigate?evaluation=${selectedId}&case=${row.case_id}`}>{row.case_id}</Link></td>
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
        </section>
      ) : <p>No persisted evaluation cases are available for this workflow.</p>}
    </>
  );
}
