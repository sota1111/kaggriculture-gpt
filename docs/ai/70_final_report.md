# Final Report — SOT-2905

## Summary

The three-child external-solution transfer chain completed. The first current-public divergence was the step-0 market family; an independently reimplemented five-WHEAT product order passed disjoint same-seed/both-seat screen and confirm and is enabled in the champion. The parent submitted the rebuilt verified artifact through the guarded control-plane path as Kaggle submission `55669739`.

## Changed Files

- `docs/ai/experiment_ledger.jsonl` — parent aggregation, effective configuration, and submission identity
- `docs/ai/linear/SOT-2905.md` — issue lifecycle record
- `docs/ai/70_final_report.md` — final acceptance record
- `docs/ai/65_worker_solo_report.md` — solo report contract
- `submission.tar.gz` — deterministic source rebuild used for submission

## Verification

- Child issues SOT-2906, SOT-2907, SOT-2908: Done
- Submission entrypoint contract: PASS
- Python unit tests: 135/135 PASS
- Sealed screen: mean margin +2214.25, lower-tail/worst +7, firing 4/4
- Sealed confirm: mean/lower-tail/worst +8, firing 4/4
- Runtime: <=1.01x; invalid actions/contract violations: 0
- Guarded Kaggle submit: ref `55669739` COMPLETE, public score `600.0`; archive SHA-256 `cc66155ba75e67bd875864567191a9254e3a4108613899f150c1266a9cb45f9f`

## Acceptance

All issue criteria are satisfied. Public `600.0` is non-contradictory, but remains a sparse follow-up signal because this competition is marked `cv_representative=false`.

## Acceptance: PASS
