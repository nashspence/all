# Profile maintenance

The executable contract is in [state transitions](../tests/test_refresh.py),
[current authority](../tests/test_approval.py),
[original evidence](../tests/test_publish_refresh.py) and
[classification](../tests/test_refresh_collect.py). See [#69](https://github.com/nashspence/all/issues/69).

`all-policy performance` and library `run_suite` require current shared approval
before admission or candidate execution. `all-policy performance-status [PROFILE ...]`
reports that same decision. Supply a read token through `GITHUB_TOKEN` or `GH_TOKEN`
when needed; unavailable authority fails closed with no cached green fallback.
One invocation records its pinned authority/evidence snapshots before measuring.

| Profile | Weekly allocations | Availability | Qualification |
|---|---:|---|---|
| Core native API v1 | 12 | 23/24 in every consecutive pair | Two consecutive cohorts |
| Prepared ext4 v2 | 12 | 12/12 | One cohort, unchanged #66 workload |

Only complete, correct core preflight rejection can use the allowance. Every
admitted observation must pass its unchanged raw limit. Missing work, probe
errors, cancellation, malformed evidence and operation misses suspend approval.
All allocations and first attempts remain binding. Successful reruns never
replace them. Approval expires after ten days; historical gaps remain blocking.
Unpublished runs may finish for two hours before becoming incomplete. Schedules
are best effort, so consumers also enforce expiry when requesting acceptance.

The normal weekly workflows execute exact merged `main` with fixed workload and
authority pins. Material implementation or workflow changes require qualification
and review before acceptance. Documentation-only changes preserve code identity.
Core refresh runs Tuesdays at 06:37 UTC; prepared storage Mondays at 06:37 UTC.
The daily 07:53 UTC status job checks approval without repeating measurements.
GitHub may disable inactive schedules; re-enable them when resuming maintenance.

Workers have read-only repository permission. Only the trusted main publisher
appends packets, actual original job/runner identities and an index to
[`profile-evidence`](https://github.com/nashspence/all/tree/profile-evidence).
Git history retains raw packets after Actions artifacts expire. Publication uses
non-forced ancestry checks; previous runs cannot be overwritten. Later publication
retains incomplete records for earlier runs whose publishers never completed.
Consumers check recent live run inventory as well as durable historical evidence.
The recorded completion boundary is all original worker jobs, validated evidence
and its durable append. A later status-query outage is not an operation miss;
acceptance still fails while required current authority cannot be read.

## Enrollment or reinstatement

1. Merge implementation with no new approval. A material push collects two fresh
   core cohorts and one prepared-storage cohort automatically. For same-source
   reinstatement, dispatch core with `bootstrap: true` and storage with
   `qualification: true`. Collection cannot approve itself.
2. Inspect every original allocation, raw result, source/workflow identity and
   retained failure. Keep the frozen limits. Diagnose a miss before deciding
   whether a changed implementation or scope needs new qualification.
3. Review a PR editing only `.all/performance/approvals.json`: exact tested merged
   source commit, source/workflow digests, consecutive qualification run IDs and
   a disposition linking the decision and explaining any resolved suspension.
   Earlier epochs remain in Git history. No green run edits this authority.
4. Merge, then run `all-policy performance-status`. Activation requires fresh
   qualifying evidence and the current installed implementation. Consumer numerical
   contracts and required CI integration still need their own approval.

Read-only API failure is an unavailable decision, not recorded environmental
admission. The checker does not remotely rewrite older packages lacking this
protocol. A reviewed-code measurement boundary does not sandbox hostile candidates
or qualify physical persistence. #66's retained consumer engineering misses and
all project-owned failure/custody obligations remain separate.
