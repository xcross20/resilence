"use server";

import { apiSend } from "@/lib/api";

export type ActionResult = { status: number; body: unknown } | { status: 0; body: { code: string; message: string } };

function blankToNull(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text.length === 0 ? null : text;
}

export async function activateRelease(_previous: ActionResult | null, formData: FormData): Promise<ActionResult> {
  const key = String(formData.get("idempotency_key") ?? "").trim();
  if (!key) return { status: 0, body: { code: "validation_error", message: "Idempotency key is required" } };
  const prior = blankToNull(formData.get("expected_prior_revision"));
  const payload: Record<string, unknown> = {
    workflow_id: String(formData.get("workflow_id") ?? ""),
    evaluation_id: String(formData.get("evaluation_id") ?? ""),
    candidate_revision: String(formData.get("candidate_revision") ?? ""),
    expected_generation: Number(formData.get("expected_generation") ?? 0),
    confirmation: blankToNull(formData.get("confirmation")),
  };
  if (prior) payload.expected_prior_revision = prior;
  return apiSend("/api/v1/releases", payload, key);
}

export async function verifyRelease(_previous: ActionResult | null, formData: FormData): Promise<ActionResult> {
  const key = String(formData.get("idempotency_key") ?? "").trim();
  const workflowId = String(formData.get("workflow_id") ?? "");
  if (!key) return { status: 0, body: { code: "validation_error", message: "Idempotency key is required" } };
  return apiSend(
    `/api/v1/releases/${workflowId}/verifications`,
    {
      cohort_id: String(formData.get("cohort_id") ?? ""),
      expected_manifest_sha256: String(formData.get("expected_manifest_sha256") ?? ""),
      expected_fixture_version: String(formData.get("expected_fixture_version") ?? ""),
      expected_active_revision: blankToNull(formData.get("expected_active_revision")),
      expected_generation: Number(formData.get("expected_generation") ?? 0),
    },
    key,
  );
}

export async function restoreRelease(_previous: ActionResult | null, formData: FormData): Promise<ActionResult> {
  const key = String(formData.get("idempotency_key") ?? "").trim();
  const workflowId = String(formData.get("workflow_id") ?? "");
  if (!key) return { status: 0, body: { code: "validation_error", message: "Idempotency key is required" } };
  return apiSend(
    `/api/v1/releases/${workflowId}/restore`,
    {
      expected_generation: Number(formData.get("expected_generation") ?? 0),
      confirmation: blankToNull(formData.get("confirmation")),
    },
    key,
  );
}
