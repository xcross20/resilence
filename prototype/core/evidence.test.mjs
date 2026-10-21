import test from "node:test";
import assert from "node:assert/strict";
import { cases, buildLedger, summarizeLedger, evaluate, canActivate, MICRO_USD } from "./evidence.mjs";

test("dataset has stable cohort composition and reference labels", () => {
  assert.equal(cases.length, 100);
  assert.deepEqual([70, 20, 10], ["routine", "ambiguous", "privileged"].map(c => cases.filter(x => x.category === c).length));
  assert.equal(new Set(cases.map(x => x.id)).size, 100);
});

test("baseline costs and dispositions reconcile to case records", () => {
  const s = summarizeLedger(buildLedger("S0"));
  assert.equal(s.verifiedAutomated, 80);
  assert.equal(s.correctEscalations, 20);
  assert.equal(s.correctDispositions, 100);
  assert.equal(s.executionCostMicroUsd, 1_980_000);
  assert.equal(s.modeledLaborMicroUsd, 40 * MICRO_USD);
  assert.equal(s.modeledTotalMicroUsd, 41_980_000);
});

test("unrestricted economy is cheaper but blocked by unsafe outcomes", () => {
  const e = evaluate("C1");
  assert.equal(e.summary.verifiedAutomated, 80);
  assert.equal(e.summary.correctEscalations, 12);
  assert.equal(e.summary.incorrectCompletions, 8);
  assert.equal(e.summary.criticalViolations, 4);
  assert.equal(e.summary.modeledTotalMicroUsd, 24_876_000);
  assert.equal(e.decision, "BLOCKED");
  assert.equal(canActivate("C1-r1", e), false);
});

test("bounded routing passes the exact synthetic acceptance contract", () => {
  const e = evaluate("C2");
  assert.equal(e.summary.verifiedAutomated, 81);
  assert.equal(e.summary.correctEscalations, 19);
  assert.equal(e.summary.incorrectCompletions, 0);
  assert.equal(e.summary.modeledTotalMicroUsd, 39_207_200);
  assert.equal(e.decision, "ELIGIBLE");
  assert.equal(canActivate("C2-r1", e), true);
  assert.equal(canActivate("C2-r2", e), false);
});

test("missing evidence and edited revision never inherit eligibility", () => {
  assert.equal(evaluate("C2", { missingEvidence: true }).decision, "INCONCLUSIVE");
  assert.equal(evaluate("C2", { editedAfterEvaluation: true }).decision, "INCONCLUSIVE");
  assert.equal(canActivate("C2-r1", evaluate("C2", { missingEvidence: true })), false);
});

test("paired ledger uses the same case ordering and unique IDs", () => {
  for (const strategy of ["C1", "C2"]) {
    assert.deepEqual(buildLedger(strategy).map(x => x.caseId), buildLedger("S0").map(x => x.caseId));
  }
});

test("cost per verified automated outcome uses total modeled costs", () => {
  for (const strategy of ["S0", "C1", "C2"]) {
    const s = summarizeLedger(buildLedger(strategy));
    assert.equal(s.costPerVerifiedAutomatedMicroUsd,
      Math.round(s.modeledTotalMicroUsd / s.verifiedAutomated));
  }
});
