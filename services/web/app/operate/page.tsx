import Link from "next/link";
import {
  DEMO_WORKFLOW_ID,
  SERVICE_DESK_WORKFLOW_ID,
  type EvaluationRow,
  type ReleasePointer,
  type WorkflowPayload,
  apiGet,
  microUsd,
  shortRevision,
} from "@/lib/api";

export const dynamic = "force-dynamic";

function countStatus(rows: EvaluationRow[], status: string): number {
  return rows.filter((row) => row.status === status).length;
}

export default async function OperatePage() {
  let workflow: WorkflowPayload | null = null;
  let evaluations: EvaluationRow[] = [];
  let pointer: ReleasePointer | null = null;
  let serviceDesk: string = "not loaded";
  let error = "";
  try {
    workflow = await apiGet<WorkflowPayload>(`/api/v1/workflows/${DEMO_WORKFLOW_ID}`);
    const listed = await apiGet<{ evaluations: EvaluationRow[] }>(`/api/v1/evaluations?workflow_id=${DEMO_WORKFLOW_ID}`);
    evaluations = listed.evaluations;
    pointer = await apiGet<ReleasePointer>(`/api/v1/releases/${DEMO_WORKFLOW_ID}`);
    try {
      const other = await apiGet<WorkflowPayload>(`/api/v1/workflows/${SERVICE_DESK_WORKFLOW_ID}`);
      serviceDesk = other.active_policy ? `generation ${other.active_policy.generation}` : "generation 0";
    } catch (caught) {
      serviceDesk = caught instanceof Error ? caught.message : "unavailable";
    }
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "The API did not respond.";
  }
  const attention = evaluations.filter((row) => row.status !== "completed_eligible");
  return (
    <>
      <h1>Operate</h1>
      <p className="lede">Attention comes from stored evaluations on the synthetic-demo workflow. Counts are the rows returned by the API, not a separate scoreboard.</p>
      {error ? <p className="fail">{error}</p> : null}
      <div className="grid">
        <article className="card"><small>Active demo revision</small><strong>{shortRevision(pointer?.active_revision)}</strong></article>
        <article className="card"><small>Demo generation</small><strong>{pointer?.generation ?? 0}</strong></article>
        <article className="card"><small>Stored evaluations</small><strong>{evaluations.length}</strong></article>
        <article className="card"><small>Service-desk pointer</small><strong>{serviceDesk}</strong></article>
      </div>
      <div className="grid">
        <article className="card"><small>Eligible</small><strong>{countStatus(evaluations, "completed_eligible")}</strong></article>
        <article className="card"><small>Blocked</small><strong>{countStatus(evaluations, "completed_blocked")}</strong></article>
        <article className="card"><small>Inconclusive</small><strong>{countStatus(evaluations, "inconclusive")}</strong></article>
        <article className="card"><small>Ineligible</small><strong>{countStatus(evaluations, "completed_ineligible")}</strong></article>
      </div>
      <p>Workflow version {workflow?.version ?? "unknown"}. Fixture comparisons on this page are synthetic records. They are not measured savings.</p>
      <h2>Eligible stored comparisons</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Cohort</th><th>Baseline cost</th><th>Candidate cost</th><th>Candidate verified</th><th>Quality gate</th></tr></thead>
          <tbody>
            {evaluations.filter((row) => row.eligible).map((row) => {
              const quality = row.gates.find((gate) => gate.gate_id === "quality");
              return (
                <tr key={row.evaluation_id}>
                  <td><Link href={`/strategies`}>{row.cohort_id}</Link></td>
                  <td>{microUsd(row.economics.baseline.execution_cost_micro_usd)}</td>
                  <td>{microUsd(row.economics.candidate.execution_cost_micro_usd)}</td>
                  <td>{row.economics.candidate.verified_success_count}</td>
                  <td>{quality ? `${quality.status} / ${quality.reason_code}` : "missing"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Evaluation</th><th>Cohort</th><th>Status</th><th>Server eligible</th><th>Blocked gate</th></tr></thead>
          <tbody>
            {attention.map((row) => {
              const blocked = row.gates.find((gate) => gate.status !== "pass");
              return (
                <tr key={row.evaluation_id}>
                  <td><Link href={`/investigate?evaluation=${row.evaluation_id}`}>{row.evaluation_id}</Link></td>
                  <td>{row.cohort_id}</td>
                  <td>{row.status}</td>
                  <td>{row.eligible ? "true" : "false"}</td>
                  <td>{blocked ? `${blocked.gate_id}: ${blocked.reason_code}` : "none stored"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
