import Link from "next/link";
import {
  DEMO_WORKFLOW_ID,
  type EvaluationRow,
  type RevisionRow,
  apiGet,
  microUsd,
  shortRevision,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function StrategiesPage() {
  let error = "";
  let evaluations: EvaluationRow[] = [];
  let revisions: RevisionRow[] = [];
  try {
    evaluations = (await apiGet<{ evaluations: EvaluationRow[] }>(`/api/v1/evaluations?workflow_id=${DEMO_WORKFLOW_ID}`)).evaluations;
    revisions = (await apiGet<{ revisions: RevisionRow[] }>(`/api/v1/strategies/revisions?workflow_id=${DEMO_WORKFLOW_ID}`)).revisions;
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "The API did not respond.";
  }
  return (
    <>
      <h1>Strategies</h1>
      <p className="lede">Each row is a stored revision or a stored evaluation. Eligible is the server field. This screen does not decide it. Synthetic comparisons are not a savings claim.</p>
      {error ? <p className="fail">{error}</p> : null}
      <h2>Stored revisions</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Revision</th><th>Rules</th><th>Fallback</th></tr></thead>
          <tbody>
            {revisions.map((revision) => (
              <tr key={revision.revision_sha256}>
                <td>{shortRevision(revision.revision_sha256)}</td>
                <td>{(revision.document.rules ?? []).map((rule) => `${rule.method} for ${(rule.when?.observed_category_in ?? []).join(", ")}`).join("; ")}</td>
                <td>{revision.document.fallback_method ?? revision.document.default_method ?? "unset"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2>Stored evaluations</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Evaluation</th><th>Status</th><th>Eligible</th><th>Authoritative</th><th>Candidate cost / verified</th><th>Gates</th></tr></thead>
          <tbody>
            {evaluations.map((row) => (
              <tr key={row.evaluation_id}>
                <td><Link href={`/investigate?evaluation=${row.evaluation_id}`}>{row.cohort_id}</Link></td>
                <td>{row.status}</td>
                <td>{String(row.eligible)}</td>
                <td>{String(row.eligibility_authoritative)}</td>
                <td>{microUsd(row.economics.candidate.cost_per_verified_success_micro_usd)}</td>
                <td>{row.gates.map((gate) => `${gate.gate_id}:${gate.status}`).join(" ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
