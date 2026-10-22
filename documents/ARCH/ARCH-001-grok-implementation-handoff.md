# ARCH-001 — Grok Coding Agent Handoff

**Status:** Ready for bounded reconnaissance + first vertical slice after contract review.
**Repository:** xcross20/resilence
**Branch recommendation:** feat/imp-001-evidence-foundation (create from main after contracts accepted).
**Approved choices:** FastAPI modular monolith, PostgreSQL, deterministic synthetic first, human-controlled release with backend-enforced gates.

## Role
You are the implementation engineer, not the product owner or autonomous architecture authority. Preserve UO-001 locked mission and RE-001 v0.6.4 approved behavior. Treat ARCH-001 documents as **proposed contracts** unless a decision explicitly says APPROVED. Report discrepancies and stop at consequential design forks.

## First: repository reconnaissance (no coding)
1. Inspect actual tree, dependencies, tests, branches and existing prototypes. Do not assume the ZIP is committed; prototype README may exist without binary.
2. Read documents/UO-001-user-outcome.md and documents/ARCH/ARCH-001-*.md (from docs/arch-001-contracts).
3. Locate reusable evidence/routing/evaluation logic and identify synthetic shortcuts, client-authoritative eligibility, and missing deterministic-replacement path.
4. Return a short architecture gap report and precise first-slice plan with files to create/modify.
5. Surface decisions requiring approval. **Stop for approval of schema/grammar/metric gates before irreversible implementation.**

## IMP-001 — First approved vertical slice (after checkpoint)
Deliver **one persisted case-level evidence chain**:
- FastAPI app factory, Pydantic strict DTOs, SQLAlchemy/Alembic PostgreSQL models.
- Versioned synthetic fixture loader with distinct observed vs reference-label inputs.
- Canonical SHA-256 strategy revision and bounded first-match routing evaluator.
- Execute one synthetic service-desk case and persist run, decision, attempt, execution cost entry and independent assessment.
- GET evidence endpoint reconstructs case, observed inputs, matched rule, selected method, attempt, cost, outcome and provenance.
- Domain tests and DB integration tests; deterministic seed and README commands.
- A deterministic code replacement candidate must be designed and tested by subsequent slice to satisfy UO-AC-03.

## Subsequent bounded slices
IMP-002: matched cohort evaluation, paired records, independent assessments, gate engine.
IMP-003: reconciled cost economics, exact revision release CAS, verification and restoration.
IMP-004: Next.js v0.6.4 workbench integration against backend read models, Playwright proof.

## Required proof per slice
- Commands, test counts, and exit codes; clean install/build if frontend touched.
- Evidence samples with stable IDs and provenance; SQL migrations.
- Demonstrate failure tests (label leakage, mismatched revision, unsafe activation).
- Diff and exact changed files; known limitations; next decision.
- Do not claim browser QA or provider measurements without running them.

## Out of scope
No universal model gateway, new queue, Kafka, Kubernetes, autonomous self-optimization, real credentials, production integration, multitenancy, new UI redesign, or expanded business domain.

## First reply format
1. Repository findings (cite paths).
2. Current vs target architecture gap table.
3. Proposed modules/files and API/data contracts.
4. Risks and rejected alternatives.
5. Test strategy.
6. Approval questions.
7. Explicit STOP state until architecture checkpoint accepted.
