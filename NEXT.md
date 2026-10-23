# Next

1. Independent reviewer inspects the IMP-002 commit in a separate session, on a clean tree, and re-runs the suite.
2. Accept only if paired evidence, label isolation, fail-closed gates, replay, conflict, and the concurrent same-key evaluation hold.
3. If that verdict is IMP-002 ACCEPTED, start IMP-003 denial and audit behavior. Do not store an eligible activation while D-10 thresholds are unapproved.
4. If the verdict is REPAIR_REQUIRED, repair only the cited defect.

Human approval still required before any numerical quality, latency, noninferiority, or minimum-evidence gate can grant eligibility.
