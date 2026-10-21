/**
 * RE-001 deterministic synthetic evidence engine.
 * All currency uses integer micro-USD to avoid floating-point accounting drift.
 * This is NOT measured provider output or production savings.
 */
export const DATASET_VERSION = "acceptance-v1";
export const CONTRACT_VERSION = "AC-1";
export const POLICY_VERSION = "it-access-v3";
export const EVALUATOR_VERSION = "fixture-evaluator-v1";
export const MICRO_USD = 1_000_000;
export const strategies = Object.freeze({
  S0: Object.freeze({ id: "S0", name: "Premium default", revision: 1, draft: false, route: "premium" }),
  C1: Object.freeze({ id: "C1-r1", name: "Economy for all requests", revision: 1, draft: false, route: "economy" }),
  C2: Object.freeze({ id: "C2-r1", name: "Bounded routine routing", revision: 1, draft: false, route: "conditional" }),
});
const categories = ["routine", "ambiguous", "privileged"];
export const cases = Object.freeze(Array.from({ length: 100 }, (_, index) => {
  const category = index < 70 ? categories[0] : index < 90 ? categories[1] : categories[2];
  return Object.freeze({
    id: `SD-${String(index + 1).padStart(3, "0")}`,
    category,
    policyVersion: POLICY_VERSION,
    referenceDisposition: index < 80 ? "automated" : "escalated",
    critical: category === "privileged",
    evidenceOrigin: "synthetic-fixture",
  });
}));

// Synthetic target charges are allocated to cases, not pasted into aggregate UI cards.
// They are illustrative totals, not a claim about the listed model rate card.
const TARGET_CHARGES_MICRO = Object.freeze({ S0: 1_980_000, C1: 876_000, C2: 1_207_200 });
const incorrectC1 = new Set([80, 81, 82, 83, 84, 85, 90, 91]);
const criticalC1 = new Set([80, 81, 90, 91]);

function routeFor(strategyKey, item) {
  if (strategyKey === "S0") return "premium";
  if (strategyKey === "C1") return "economy";
  if (strategyKey === "C2") return item.category === "routine" ? "economy" : "premium";
  throw new Error("Unknown strategy");
}

function outcomeFor(strategyKey, index) {
  if (strategyKey === "C1" && incorrectC1.has(index)) return "incorrect-completion";
  if (strategyKey === "C2" && index === 80) return "verified-automated";
  if (strategyKey === "C2" && index === 79) return "correct-escalation";
  return index < 80 ? "verified-automated" : "correct-escalation";
}

export function buildLedger(strategyKey) {
  if (!Object.hasOwn(strategies, strategyKey)) throw new Error("Unknown strategy");
  const total = TARGET_CHARGES_MICRO[strategyKey];
  const perCase = Math.floor(total / cases.length);
  const remainder = total - perCase * cases.length;
  return cases.map((item, index) => {
    const outcome = outcomeFor(strategyKey, index);
    return Object.freeze({
      caseId: item.id,
      category: item.category,
      referenceDisposition: item.referenceDisposition,
      policyVersion: item.policyVersion,
      strategyRevisionId: strategies[strategyKey].id,
      datasetVersion: DATASET_VERSION,
      evaluatorVersion: EVALUATOR_VERSION,
      origin: "synthetic-fixture",
      route: routeFor(strategyKey, item),
      outcome,
      criticalViolation: strategyKey === "C1" && criticalC1.has(index),
      executionCostMicroUsd: perCase + (index < remainder ? 1 : 0),
      modeledLaborMicroUsd: outcome === "correct-escalation" ? 2 * MICRO_USD : 0,
      // This is an illustrative fixture, not observed execution timing.
      latencyMs: 3000 + (index % 10) * 250,
      attempts: 1,
    });
  });
}

export function summarizeLedger(ledger) {
  const summary = {
    cases: ledger.length, verifiedAutomated: 0, correctEscalations: 0,
    incorrectCompletions: 0, criticalViolations: 0, correctDispositions: 0,
    executionCostMicroUsd: 0, modeledLaborMicroUsd: 0, modeledTotalMicroUsd: 0,
    costPerVerifiedAutomatedMicroUsd: null, p95LatencyMs: null,
  };
  for (const row of ledger) {
    if (row.outcome === "verified-automated") summary.verifiedAutomated++;
    if (row.outcome === "correct-escalation") summary.correctEscalations++;
    if (row.outcome === "incorrect-completion") summary.incorrectCompletions++;
    if (row.criticalViolation) summary.criticalViolations++;
    summary.executionCostMicroUsd += row.executionCostMicroUsd;
    summary.modeledLaborMicroUsd += row.modeledLaborMicroUsd;
  }
  summary.correctDispositions = summary.verifiedAutomated + summary.correctEscalations;
  summary.modeledTotalMicroUsd = summary.executionCostMicroUsd + summary.modeledLaborMicroUsd;
  if (summary.verifiedAutomated) {
    summary.costPerVerifiedAutomatedMicroUsd =
      Math.round(summary.modeledTotalMicroUsd / summary.verifiedAutomated);
  }
  if (ledger.length) {
    const latencies = ledger.map(x => x.latencyMs).sort((a, b) => a - b);
    summary.p95LatencyMs = latencies[Math.ceil(0.95 * latencies.length) - 1];
  }
  return summary;
}

export function evaluate(strategyKey, options = {}) {
  const ledger = buildLedger(strategyKey);
  const baseline = buildLedger("S0");
  const stats = summarizeLedger(ledger);
  const baseStats = summarizeLedger(baseline);
  const coverageComplete = ledger.length === cases.length &&
    new Set(ledger.map(x => x.caseId)).size === cases.length &&
    ledger.every(x => x.datasetVersion === DATASET_VERSION &&
      x.policyVersion === POLICY_VERSION && x.evaluatorVersion === EVALUATOR_VERSION &&
      x.origin === "synthetic-fixture" && Number.isInteger(x.executionCostMicroUsd));
  const paired = baseline.every((row, i) => row.caseId === ledger[i].caseId);
  const gates = {
    comparableCoverage: coverageComplete && paired && !options.missingEvidence,
    noCriticalViolations: stats.criticalViolations === 0,
    noIncorrectCompletions: stats.incorrectCompletions === 0,
    automatedMinimum: stats.verifiedAutomated >= 80,
    privilegedEscalation: ledger.filter(x => x.category === "privileged")
      .every(x => x.outcome === "correct-escalation"),
    latencyP95: stats.p95LatencyMs !== null && stats.p95LatencyMs <= 6500,
    unitCostImproves: stats.costPerVerifiedAutomatedMicroUsd !== null &&
      stats.costPerVerifiedAutomatedMicroUsd < baseStats.costPerVerifiedAutomatedMicroUsd,
    revisionUnchanged: !options.editedAfterEvaluation,
  };
  const decision = !gates.comparableCoverage || !gates.revisionUnchanged
    ? "INCONCLUSIVE"
    : Object.values(gates).every(Boolean) ? "ELIGIBLE" : "BLOCKED";
  return Object.freeze({
    id: `eval-${strategies[strategyKey].id}-${DATASET_VERSION}`,
    strategyRevisionId: strategies[strategyKey].id,
    baselineRevisionId: strategies.S0.id,
    datasetVersion: DATASET_VERSION,
    evaluatorVersion: EVALUATOR_VERSION,
    acceptanceContractVersion: CONTRACT_VERSION,
    evidenceOrigin: "synthetic-fixture",
    decision, gates, summary: stats, baselineSummary: baseStats, ledger,
  });
}

export function canActivate(revisionId, evaluation) {
  return Boolean(evaluation && evaluation.strategyRevisionId === revisionId &&
    evaluation.acceptanceContractVersion === CONTRACT_VERSION &&
    evaluation.datasetVersion === DATASET_VERSION &&
    evaluation.evaluatorVersion === EVALUATOR_VERSION &&
    evaluation.decision === "ELIGIBLE" &&
    Object.values(evaluation.gates).every(Boolean));
}
