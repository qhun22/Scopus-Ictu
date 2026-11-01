# G01 — Protected-tree hash scope clarification

Date: 2026-10-29 (Asia/Bangkok). Documentation addendum to the independently accepted G01 fix; no G01 code or tests were changed or re-executed for this clarification. Original `G01_HANDOVER.md`, `G01_IMPLEMENTATION.diff`, `TEST_RESULTS.txt`, `VALIDATION.json` and `MANIFEST.sha256` remain byte-identical.

The `integrity.protected_tree_checks` values in the original `VALIDATION.json` are **hashes of protected subsets, not complete backend trees**. The capture excluded the two deliberately modified paths globally, and excluded files under any `__pycache__` directory:

| Root | Deliberately excluded modified path | Included files | Protected-subset SHA-256 |
|---|---|---|---|
| `backend/app` | `backend/app/services/lecturer_dataset/known_publication_ingestion.py` | 138 | `e2d446218c8a632fc51233270337cf8d217a404cc00d6d56b16d69ca4af97c87` |
| `backend/tests` | `backend/tests/unit/test_known_publication_ingestion.py` | 78 | `90620d8e5c11fb115e6579eca8fe311dd54324d4e145bce2bf55c2d15dbd0654` |

Before and after were captured across the G01 implementation with these same exclusions, not both at an identical post-change point. At the start of the G02 task, before changing affiliation code, recalculating the documented subsets reproduced both original hashes exactly. That recalculation corroborates the inclusion/exclusion method; it does not recreate a historical full-tree before state.

Algorithm: sort relative `Path` objects for included files; produce `(path.as_posix(), SHA256(file_bytes))` entries; hash `json.dumps(entries, separators=(',', ':')).encode()` using Python's default JSON settings. The original root labels should have stated these exclusions explicitly.

These unchanged hashes establish preservation **only of included files**. They must not be cited as proof that all application/test source was unmodified. The exact two-file diff, its SHA-256 `41c07e0f91f2cbf139525b7051ff75171c71e6f81611bfeb1f3de9710c19e343`, and the two changed-file hashes in the original validation report establish the intended change scope.

No migration, database query, import or identity action accompanies this clarification. G01 remains accepted at its stated unit-tested scope. G02 artifacts use explicit exclusion metadata and separate before/after hashes for changed source files to avoid repeating this ambiguity.
