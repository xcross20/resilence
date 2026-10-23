# Release readiness

Final status: **BLOCKED**

This is not a production release. UO-001 is not accepted. The builder does not accept the user outcome.

## Accepted

| Milestone | Status | Commit |
| --- | --- | --- |
| IMP-001 | Independently accepted | `040d5a9086e6faf54985fd482815588318f0f9a5` |
| IMP-002 | Independently accepted | `c35d1c8a1cc6b2d23f5413408224fc32a2c8201d` |
| IMP-003 | Independently accepted | `f9716cb2f2490213ddd7013feff0e30c1d29a893` |

## Blocked

| Milestone | Why |
| --- | --- |
| IMP-004 | The required browser journey includes evaluating an eligible strategy and activating it with confirmation. No approved gate policy can make a strategy eligible. Inventing a margin, a sample size, or a client eligibility flag would change the contract. |
| IMP-005 | Integrated user-outcome acceptance depends on the workbench journey and on eligible activation. Outcome Verification still has no approved UO-AC commands. |

## Human decision required

Approve a versioned gate policy that names the quality, latency, noninferiority, and minimum-evidence thresholds, or explicitly keep activation denied. Until that policy exists and is added to `APPROVED_ACTIVATION_POLICIES`, IMP-004 must not demonstrate a successful activation.

## Not done

No merge to `main`. No production deploy. No real-provider spend. No change to Railway networking.
