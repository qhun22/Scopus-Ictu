# ICTU Lecturer Dataset — Reports

## Source

- Source: ICTU official DSpace repository — lecturer archive (Vietnamese)
- URL: https://repository.ictu.edu.vn/giang-vien/
- System: `ictu_dspace_archive`
- Raw snapshot: `data\lecturers\raw\ictu_lecturers_archive_snapshot.html`
- Raw snapshot SHA-256: `9d7efb39505c3e082e82895b6c52e31c15748096203ec06c4f6f32d83e9ec4c3`
- Retrieved at: `2026-10-02T02:24:04.342391+00:00`

## Record count

- Source records (after dedup): **410**
- Unique records: **410**
- Valid records: **410**
- Invalid records: **0**
- Duplicate candidates: **9**
- Expected in directive: **410**
- Expected in builder: **410**
- Count matches expected (builder): **True**
- Final status: **DATASET_COUNT_PASS**
- Reason: DSpace archive published exactly 410 lecturer cards; matches the directive's expected 410 count.

- Dataset SHA-256: `a2c326f98b5eaf4a690f4719110fda69470f62031363a4c47a90517a3258f1b9`

## Field coverage (percentage of records with a non-null value)

| Field | Count | % |
|---|---:|---:|
| `staff_code` | 0 | 0.0% |
| `institutional_email` | 410 | 100.0% |
| `tel` | 0 | 0.0% |
| `academic_degree` | 360 | 87.8% |
| `academic_rank` | 8 | 2.0% |
| `position` | 4 | 1.0% |
| `faculty` | 0 | 0.0% |
| `department` | 0 | 0.0% |
| `profile_url` | 410 | 100.0% |
| `orcid` | 0 | 0.0% |

## Privacy / security

- No password, password_hash, token, secret, citizen ID, or home address fields are stored.
- Only public professional data captured from the official ICTU DSpace archive is included.

## How to rebuild

```
cd backend
python -m scripts.build_ictu_lecturer_dataset
```

With a fresh fetch from the live ICTU DSpace archive:

```
python -m scripts.build_ictu_lecturer_dataset --refresh
```

Strict-count acceptance (exits non-zero if record count != expected):

```
python -m scripts.build_ictu_lecturer_dataset --expected-count 410
```

## Important notes for the project defense

- The lecturer master dataset is **not** a user-account table. Importing this dataset does NOT create user accounts.
- The dataset is a **derived snapshot** of publicly-available ICTU institutional data and is fully reproducible from the raw HTML snapshot committed under `data/lecturers/raw/`.
- All entries carry provenance (source URL, parser version, retrieved timestamp) so the import is traceable end-to-end.
- Generated at: `2026-10-02T02:30:35+00:00`
