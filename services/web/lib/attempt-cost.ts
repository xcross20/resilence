export type AttemptCost = {
  side: "baseline" | "candidate";
  attemptOrdinal: number;
  stepId: string;
  selectedMethod: string;
  amountMicroUsd: number | null;
};

type DecisionRow = { decision_id: string; step_id: string; selected_method: string };
type AttemptRow = { attempt_id: string; decision_id: string; attempt_ordinal: number };
type CostRow = { attempt_id: string; amount_micro_usd: number };

export type AttemptEvidence = {
  decisions?: DecisionRow[];
  attempts?: AttemptRow[];
  costs?: CostRow[];
};

export function projectAttemptCosts(side: AttemptCost["side"], evidence: AttemptEvidence): AttemptCost[] {
  const decisions = new Map((evidence.decisions ?? []).map((row) => [row.decision_id, row]));
  const amounts = new Map((evidence.costs ?? []).map((row) => [row.attempt_id, row.amount_micro_usd]));
  return [...(evidence.attempts ?? [])]
    .sort((left, right) => left.attempt_ordinal - right.attempt_ordinal)
    .map((attempt) => {
      const decision = decisions.get(attempt.decision_id);
      const amount = amounts.get(attempt.attempt_id);
      return {
        side,
        attemptOrdinal: attempt.attempt_ordinal,
        stepId: decision?.step_id ?? "missing",
        selectedMethod: decision?.selected_method ?? "missing",
        amountMicroUsd: amount === undefined ? null : amount,
      };
    });
}

export function formatAttemptCost(amountMicroUsd: number | null): string {
  if (amountMicroUsd === null) return "missing";
  return `${amountMicroUsd.toLocaleString("en-US")} µUSD`;
}
