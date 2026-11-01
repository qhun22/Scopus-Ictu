# E3-P3-A temporal closeout (P3A-R1, P3A-R2): handover for independent review

Date: 2026-10-29 · Status: **CORRECTION DELIVERED — STOPPED FOR REVIEW** (P3-B not started)

Changed: `backend/app/services/source_claim_matching/bridge.py` and its test file only. Unchanged:
- the other P3-A files, all accepted E3 code (21/21), and G01–G04 (31/31);
- the matching, candidate, review and identity code (7/7 byte-equal to HEAD).

Claim deduplication and reviewer-decision semantics are untouched. There was no database connection,
migration, real data, reviewer change, frontend change, commit or push.

## P3A-R1: ordering by instant, not by string

**Defect.** Observations of one claim were sorted by the `captured_at` *string*, while presence used
datetimes. With `2026-10-29T23:00:00+07:00` (= 16:00Z) and `2026-10-29T17:00:00Z`, the older capture
supplied `is_primary_claimed` / `listed`, and `observed_in` ran in reverse.

**Fix.**
- `_instant()` parses `captured_at` into an offset-aware UTC instant. A naive or unparseable time is
  refused up front with `BridgeError("CAPTURE_TIME_INVALID")` (fail closed).
- `_sort_key()` is `(instant, str(capture_id))`. The UUID only makes **exact ties** deterministic.
- The claim group is sorted with `_sort_key`, so the latest instant supplies the flags and
  `observed_in` is chronological. The old `_moment`/`_latest` helpers are gone.

## P3A-R2: equal instants never prove withdrawal

**Defect.** `_presence` compared `(instant, UUID)` tuples, so two COMPLETE captures at the *same*
instant were ordered by UUID, and the ID missing from the "later" one was marked `WITHDRAWN`.

**Fix.** `_presence` now returns `(Presence, ambiguity)` and works on the set of captures at the latest
instant:

| Situation | Result |
|---|---|
| claim listed in **all** captures at the latest instant | `CURRENT` |
| listed in **some** (they disagree) | `NOT_OBSERVED` + finding `CAPTURE_ORDER_AMBIGUOUS` (`PRESENCE_DIFFERS`) |
| listed in none, last seen at a **strictly earlier** instant, every latest-instant capture COMPLETE, a COMPLETE capture among the last-seen ones, non-weak key | `WITHDRAWN` |
| anything else, including any PARTIAL capture at the latest instant, equal instants, weak keys | `NOT_OBSERVED` |

- Tied same-instant observations that carry **different flags** give `CAPTURE_ORDER_AMBIGUOUS`
  (`FLAGS_DIFFER`) instead of a silent UUID choice.
- Equal instants are compared as instants, so `…T17:00:00Z` equals `…T00:00:00+07:00` the next day.
- Existing guarantees are unchanged and re-tested: PARTIAL never implies withdrawal; an APPROVED
  identity stays `VERIFIED_ASSOCIATION` and nothing is revoked or flagged as withdrawn in the tie case.

## Regressions: 16 new tests (43 in the bridge file)

| Test | Covers |
|---|---|
| `test_r1_mixed_offsets_take_flags_from_the_later_instant_not_the_later_string` | the reviewer's `+07:00`/`Z` case: later instant wins the primary flag; `observed_in` chronological; the string order is the *opposite* (asserted) |
| `test_r1_listed_flag_follows_the_later_instant` | `listed` follows the later instant in both directions |
| `test_r1_ordering_is_independent_of_input_order_and_captures_listing` | 6 shuffles, identical result |
| `test_r1_naive_capture_time_is_refused` | `CAPTURE_TIME_INVALID` |
| `test_r2_equal_instants_never_prove_withdrawal` (4) | both UUID orders × the same instant written as `Z` and as `+07:00`: `NOT_OBSERVED`, never `WITHDRAWN`, one `CAPTURE_ORDER_AMBIGUOUS` |
| `test_r2_strictly_later_complete_capture_still_withdraws_whatever_the_uuids` (2) | withdrawal is still found for a strictly later instant, for both UUID orders, with no ambiguity finding |
| `test_r2_two_later_captures_at_the_same_instant_that_both_omit_the_claim_withdraw_it` | two equal-instant captures that both omit it, strictly later than the listing capture: `WITHDRAWN` |
| `test_r2_a_partial_capture_at_the_latest_instant_blocks_withdrawal` (2) | a COMPLETE + a PARTIAL capture at the latest instant: `NOT_OBSERVED`, both UUID orders |
| `test_r2_tied_listing_captures_with_different_flags_are_flagged_not_silently_chosen` | `FLAGS_DIFFER` finding |
| `test_r2_ambiguity_never_revokes_an_approved_identity` (2) | both UUID orders; decision echoed; no `SOURCE_NO_LONGER_LISTS_APPROVED_ID` |

**The tests fail against the accepted bridge.** Run on the accepted bridge (hash `0329ba2a…`, equal to
`E3P3A_VALIDATION.json`): **10 failed, 6 passed**. The 6 that pass pin behaviour that was already right
(shuffle determinism, a strictly later capture, two equal captures that both omit the claim, PARTIAL
with one UUID order). With the fix: 43/43. The log is in the test-results file.

**Mutation probes** (the old behaviour re-injected in memory):

| Probe | Failing tests |
|---|---|
| string time ordering (R1) | 2 |
| UUID as succession (R2) | 6 |
| no input validation | 3 |
| withdraw on PARTIAL | 8 |
| no claim deduplication | 5 |
| ignore negative decisions | 3 |

## Verification

| Check | Result |
|---|---|
| Bridge suite | **43 passed** (27 + 16) |
| Full offline suite (P1 + P2-A + B1 + provenance + B2 + P3-A) | **327 passed** (311 + 16) |
| Existing matching unit tests (unchanged files) | 37 passed; the 7 errors are the missing `isolated_db_engine` fixture (no test database) |
| Ruff (all E3 code and tests) | exit 0 |
| `E3P3A_CORRECTION.diff` against the accepted P3-A | `bridge.py` +51/−20, test file +157/−0; whitespace clean |
| Eleven-diff replay (P1 → … → P3-A → this correction), `--whitespace=error` | all OK; both files reproduce the workspace; reverse check OK |
| G01–G04 | 31/31 MATCH |
| `git status` | the same 17 tracked modifications |

## Remaining limitations

- Ordering relies on the capture time recorded in the source contract. The bridge has no other
  succession signal (e.g. a trusted capture sequence), so equal instants are always treated as
  unordered.
- A claim seen at the latest instant in only some tied captures is reported `NOT_OBSERVED` plus a
  finding. It is deliberately not `CURRENT`.
- PostgreSQL gate (staging migration, 4 B2 tests, G04, the candidate-persistence tests) is still
  NOT_EXECUTED. O-2 and O-7 still await formal confirmation.

## P3-B owner policy: provisional decisions (recorded, not implemented)

Source: the project owner's recommendations, confirmed by the independent review. **P3-B is not
started.**

1. **Candidate roots from declarations.** A uniquely resolved institutional Scopus declaration may
   create a **PENDING** candidate root even when name matching found none. Requirements:
   - a catalog-matched Scopus author;
   - the lecturer identified uniquely by profile URL or e-mail (the bridge's `RESOLVED_SOURCE_ID` /
     `RESOLVED_EMAIL`);
   - never auto-approve; never reopen a REJECTED/SUPERSEDED candidate or a REJECTED/REVOKED identity;
   - conflicts are never silently discarded: they stay visible to reviewers.
2. **No false promotion.** `SOURCE_CLAIM` provenance stays in the candidate evidence and in the review
   `evidence_snapshot`. It is **not** mapped to `APPROVED_ID`, `ORCID_EXACT`, `DOI_EXACT` or any other
   `IdentityEvidence` type. Any new identity-evidence type is a separate, explicit schema and product
   decision.
3. **D-2.** Institutional source evidence does **not** lift the `NAME_EVIDENCE_ONLY` reason
   requirement by itself.
4. **Tier.** `INSTITUTION_DECLARED` is a provenance tier: not reviewer verification and not a
   confidence guarantee.

Consequences already visible in the bridge: `accept_reason_required` is always true, negative
decisions get a `…REVIEWER_REOPEN_REQUIRED` reason, and APPROVED pairs are only echoed.

STOPPED after the narrow correction. P3-B not started.
