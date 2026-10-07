# Matching Reference Dataset

## Purpose

This directory contains the ground-truth reference contract for evaluating
the quality of the lecturer ↔ Scopus author candidate retrieval system.

## File: `reference_template.csv`

The template defines the required schema.  **It contains the header only.**
No fabricated or inferred reference labels are provided in this file.

Actual reference data must be populated from verified, external sources
(e.g. supervisor confirmation, official institutional records) as part of
a separate labeling task (C3-A2).

## Column Definitions

| Column | Required | Description |
|--------|----------|-------------|
| `lecturer_source_id` | Yes | The URL/identifier from the ICTU DSpace repository that identifies this lecturer in the official source dataset. This is the **primary reference key**. It corresponds to `source_id` in `data/lecturers/ictu_lecturers.json` and to `Lecturer.repository_profile_url` in the database. |
| `institutional_email` | Optional | ICTU institutional email — used as a cross-check display field only. Not required to be unique. |
| `lecturer_full_name` | Yes | Human-readable full name from the source dataset. Used for cross-check and display only. |
| `decision` | Yes | One of `MATCH` or `NO_MATCH` (exact, case-sensitive). |
| `expected_scopus_id` | Conditional | The confirmed Scopus author ID. **Required when `decision=MATCH`. Must be empty when `decision=NO_MATCH`.** |
| `confirmation_source` | Yes | Non-empty description of who/what confirmed this label (e.g. "Supervisor review 2026-10-01", "ICTU HR database"). |
| `confirmed_at` | Yes | ISO-8601 UTC timestamp of when this label was confirmed. |
| `notes` | Optional | Free-text notes. May be empty. |

## Decision Contract

### `MATCH`

The lecturer has exactly one confirmed Scopus author match. The
`expected_scopus_id` field must contain the Scopus author ID string (not
a UUID — this is the external Scopus identifier from the `scopus_id` column
of the `scopus_authors` table).

### `NO_MATCH`

No Scopus author match has been confirmed for this lecturer. The
`expected_scopus_id` field must be empty.

## Primary Key: `lecturer_source_id`

`staff_code` is intentionally **not** the reference primary key. The current
official ICTU source dataset (410 lecturers) has zero `staff_code` coverage.
Using `lecturer_source_id` (the profile URL from the DSpace repository) avoids
this gap and directly links reference rows to the canonical source record.

## Subset Policy

Reference rows represent a **human/externally confirmed subset** of the 410
lecturers. The evaluator does not require all 410 lecturers to be labeled.
Evaluation metrics are computed only over labeled rows.

## No Automated Inference

Reference labels **must never** be:

- Inferred from candidate-generator output
- Derived from fuzzy name similarity scores
- Derived from existing matching rules or algorithm output
- Self-referentially generated from the evaluator's own predictions

Doing so would contaminate evaluation with the very predictions being
measured, producing unreliable precision/recall/F1 figures.

## Cross-Check

Each `lecturer_source_id` must correspond to exactly one record in
`data/lecturers/ictu_lecturers.json` (matched via `source_id`). The
`lecturer_full_name` and `institutional_email` (when provided) are
cross-checked for consistency against the official dataset.

## Next Step

After C3-A1 (scaffold), the next task is **C3-A2**: populate this template
with supervisor-confirmed reference labels and run the evaluator against the
live database to obtain real precision/recall/F1 measurements.
