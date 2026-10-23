export const DEMO_WORKFLOW_ID = "service-desk-synthetic-demo";
export const SERVICE_DESK_WORKFLOW_ID = "service-desk";

export type GateRow = { gate_id: string; status: string; reason_code: string };

export type EvaluationRow = {
  evaluation_id: string;
  cohort_id: string;
  status: string;
  eligible: boolean;
  eligibility_authoritative: boolean;
  production_authority: boolean;
  gate_policy_version: string;
  baseline_revision: string;
  candidate_revision: string;
  case_count: number;
  created_at: string;
  economics: {
    baseline: {
      verified_success_count: number;
      execution_cost_micro_usd: number;
      cost_per_verified_success_micro_usd: number | null;
    };
    candidate: {
      verified_success_count: number;
      execution_cost_micro_usd: number;
      cost_per_verified_success_micro_usd: number | null;
    };
  };
  gates: GateRow[];
};

export type WorkflowPayload = {
  workflow_id: string;
  version: string;
  graph: { nodes?: { step_id: string; name: string }[]; edges?: unknown[] };
  cohorts: {
    cohort_id: string;
    version: string;
    purpose: string;
    fixture_version: string;
    manifest_sha256: string;
    case_ids: string[] | string;
  }[];
  active_policy: { revision_sha256: string; generation: number } | null;
};

export type ReleasePointer = {
  workflow_id: string;
  generation: number;
  active_revision: string | null;
  prior_revision: string | null;
  evaluation_id: string | null;
};

export type ReleaseEvent = {
  event_seq: number;
  event_id: string;
  event_type: string;
  reason_code: string;
  resulting_generation: number;
  target_revision: string | null;
  occurred_at: string;
};

export type CaseRow = {
  case_id: string;
  case_ordinal: number;
  observed_category: string | null;
  route_changed: boolean;
  verdict_changed: boolean;
  execution_cost_delta_micro_usd: number;
  baseline_verdict: string;
  candidate_verdict: string;
  baseline_reason_code: string;
  candidate_reason_code: string;
  candidate_critical_violation: boolean;
  baseline_run_id: string;
  candidate_run_id: string;
};

export type RevisionRow = {
  revision_sha256: string;
  schema_version: string;
  document: {
    rules?: { rule_id: string; priority: number; method: string; when?: { observed_category_in?: string[] } }[];
    default_method?: string;
    fallback_method?: string;
  };
};

function apiBase(): string {
  return process.env.EXECUTION_OPTIMIZER_API_URL ?? "http://127.0.0.1:8000";
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
  const body = await response.json();
  if (!response.ok) {
    const code = typeof body?.code === "string" ? body.code : "request_failed";
    throw new Error(`${response.status} ${code}`);
  }
  return body as T;
}

export async function apiSend(path: string, payload: unknown, idempotencyKey: string): Promise<{ status: number; body: unknown }> {
  const response = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  return { status: response.status, body: await response.json() };
}

export function shortRevision(value: string | null | undefined): string {
  if (!value) return "none";
  return value.slice(0, 18);
}

export function microUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "no quotient";
  return `${value.toLocaleString("en-US")} µUSD`;
}
