# Next

1. Independent reviewer inspects the IMP-003 commit in a separate session, on a clean tree, and re-runs the suite.
2. Accept only if blocked, inconclusive, and ineligible evaluations are denied, generation stays unchanged, overlap is disclosed, an injected regression is visible, restoration of a recorded prior replays once, and `release_event` rejects update.
3. If that verdict is IMP-003 ACCEPTED, stop the activation success path until a human approves a gate policy. IMP-004 may show denial. It must not invent an eligible activation.
4. If the verdict is REPAIR_REQUIRED, repair only the cited defect.

Human approval still required before any numerical quality, latency, noninferiority, or minimum-evidence gate can grant eligibility.
