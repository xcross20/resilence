"use client";

import { useActionState, useState } from "react";
import { activateRelease, restoreRelease, verifyRelease, type ActionResult } from "./actions";
import type { EvaluationRow, WorkflowPayload } from "@/lib/api";

function Result({ state }: { state: ActionResult | null }) {
  if (!state) return null;
  return <pre>{JSON.stringify(state, null, 2)}</pre>;
}

export function ReleaseForms({
  workflowId,
  generation,
  activeRevision,
  priorRevision,
  evaluations,
  cohorts,
}: {
  workflowId: string;
  generation: number;
  activeRevision: string | null;
  priorRevision: string | null;
  evaluations: EvaluationRow[];
  cohorts: WorkflowPayload["cohorts"];
}) {
  const [activateState, activateAction, activatePending] = useActionState(activateRelease, null);
  const [verifyState, verifyAction, verifyPending] = useActionState(verifyRelease, null);
  const [restoreState, restoreAction, restorePending] = useActionState(restoreRelease, null);
  const [activateKey, setActivateKey] = useState(() => crypto.randomUUID());
  const [verifyKey, setVerifyKey] = useState(() => crypto.randomUUID());
  const [restoreKey, setRestoreKey] = useState(() => crypto.randomUUID());
  const [evaluationId, setEvaluationId] = useState(evaluations.find((row) => row.eligible)?.evaluation_id ?? evaluations[0]?.evaluation_id ?? "");
  const selected = evaluations.find((row) => row.evaluation_id === evaluationId) ?? evaluations[0];
  const verificationCohorts = cohorts.filter((cohort) => cohort.purpose === "verification");
  const [cohortId, setCohortId] = useState(verificationCohorts[0]?.cohort_id ?? "");
  const selectedCohort = verificationCohorts.find((cohort) => cohort.cohort_id === cohortId) ?? verificationCohorts[0];
  return (
    <>
      <form action={activateAction}>
        <strong>Activate a stored evaluation</strong>
        <input type="hidden" name="workflow_id" value={workflowId} />
        <input type="hidden" name="idempotency_key" value={activateKey} />
        <input type="hidden" name="expected_generation" value={generation} />
        <input type="hidden" name="expected_prior_revision" value={activeRevision ?? ""} />
        <label>Evaluation
          <select name="evaluation_id" value={evaluationId} onChange={(event) => setEvaluationId(event.target.value)}>
            {evaluations.map((row) => (
              <option key={row.evaluation_id} value={row.evaluation_id}>
                {row.cohort_id} · stored eligible {String(row.eligible)} · {row.status}
              </option>
            ))}
          </select>
        </label>
        <input type="hidden" name="candidate_revision" value={selected?.candidate_revision ?? ""} />
        <p>Candidate revision {selected?.candidate_revision ?? "none"} comes from the stored evaluation.</p>
        <label>Type the confirmation
          <input name="confirmation" placeholder="activate_synthetic_revision" autoComplete="off" onChange={() => setActivateKey(crypto.randomUUID())} />
        </label>
        <button type="submit" disabled={activatePending}>Submit activation</button>
        <Result state={activateState} />
      </form>
      <form action={verifyAction}>
        <strong>Verify the active revision</strong>
        <input type="hidden" name="workflow_id" value={workflowId} />
        <input type="hidden" name="idempotency_key" value={verifyKey} />
        <input type="hidden" name="expected_generation" value={generation} />
        <input type="hidden" name="expected_active_revision" value={activeRevision ?? ""} />
        <label>Verification cohort
          <select
            name="cohort_id"
            value={selectedCohort?.cohort_id ?? ""}
            onChange={(event) => {
              setCohortId(event.target.value);
              setVerifyKey(crypto.randomUUID());
            }}
          >
            {verificationCohorts.map((cohort) => <option key={cohort.cohort_id} value={cohort.cohort_id}>{cohort.cohort_id}</option>)}
          </select>
        </label>
        <label>Manifest
          <input name="expected_manifest_sha256" value={selectedCohort?.manifest_sha256 ?? ""} readOnly />
        </label>
        <label>Fixture version
          <input name="expected_fixture_version" value={selectedCohort?.fixture_version ?? ""} readOnly />
        </label>
        <button type="submit" disabled={verifyPending}>Submit verification</button>
        <Result state={verifyState} />
      </form>
      <form action={restoreAction}>
        <strong>Restore the recorded prior</strong>
        <p>Prior revision {priorRevision ?? "none"}.</p>
        <input type="hidden" name="workflow_id" value={workflowId} />
        <input type="hidden" name="idempotency_key" value={restoreKey} />
        <input type="hidden" name="expected_generation" value={generation} />
        <label>Type the confirmation
          <input name="confirmation" placeholder="restore_prior_revision" autoComplete="off" onChange={() => setRestoreKey(crypto.randomUUID())} />
        </label>
        <button type="submit" disabled={restorePending}>Submit restore</button>
        <Result state={restoreState} />
      </form>
    </>
  );
}
