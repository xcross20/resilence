import { ReleaseForms } from "./release-forms";
import {
  DEMO_WORKFLOW_ID,
  type EvaluationRow,
  type ReleaseEvent,
  type ReleasePointer,
  type WorkflowPayload,
  apiGet,
  shortRevision,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReleasesPage() {
  let error = "";
  let pointer: ReleasePointer | null = null;
  let events: ReleaseEvent[] = [];
  let evaluations: EvaluationRow[] = [];
  let workflow: WorkflowPayload | null = null;
  try {
    pointer = await apiGet<ReleasePointer>(`/api/v1/releases/${DEMO_WORKFLOW_ID}`);
    events = (await apiGet<{ events: ReleaseEvent[] }>(`/api/v1/releases/${DEMO_WORKFLOW_ID}/events`)).events;
    evaluations = (await apiGet<{ evaluations: EvaluationRow[] }>(`/api/v1/evaluations?workflow_id=${DEMO_WORKFLOW_ID}`)).evaluations;
    workflow = await apiGet<WorkflowPayload>(`/api/v1/workflows/${DEMO_WORKFLOW_ID}`);
  } catch (caught) {
    error = caught instanceof Error ? caught.message : "The API did not respond.";
  }
  return (
    <>
      <h1>Releases</h1>
      <p className="lede">Activation, verification, and restore are sent to the API. The response is the decision. Production authority is not available on this screen.</p>
      {error ? <p className="fail">{error}</p> : null}
      <div className="grid">
        <article className="card"><small>Generation</small><strong>{pointer?.generation ?? 0}</strong></article>
        <article className="card"><small>Active</small><strong>{shortRevision(pointer?.active_revision)}</strong></article>
        <article className="card"><small>Prior</small><strong>{shortRevision(pointer?.prior_revision)}</strong></article>
        <article className="card"><small>Events</small><strong>{events.length}</strong></article>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Seq</th><th>Event</th><th>Reason</th><th>Generation</th><th>Target</th></tr></thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.event_id}>
                <td>{event.event_seq}</td>
                <td>{event.event_type}</td>
                <td>{event.reason_code}</td>
                <td>{event.resulting_generation}</td>
                <td>{shortRevision(event.target_revision)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pointer && workflow ? (
        <ReleaseForms
          workflowId={DEMO_WORKFLOW_ID}
          generation={pointer.generation}
          activeRevision={pointer.active_revision}
          priorRevision={pointer.prior_revision}
          evaluations={evaluations}
          cohorts={workflow.cohorts}
        />
      ) : null}
    </>
  );
}
