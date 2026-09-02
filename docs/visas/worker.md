# Visa module — Skilled Worker

## Route

UK **Skilled Worker** visa — sponsored employment in an eligible skilled role. Scope: main applicant, applying from outside the UK. (Dependants and Health & Care Worker route out of MVP scope.)

> **Provenance rule:** every requirement below carries a `req_id`. Production values must be re-verified against current gov.uk guidance. Salary thresholds and maintenance amounts here are illustrative and MUST be re-sourced before production.

## RequirementSet — required documents

| req_id | Document | Mandatory | Format / validity | Notes |
|---|---|---|---|---|
| `worker.passport` | Passport | yes | valid for stay | — |
| `worker.cos` | CoS (Certificate of Sponsorship) | yes | reference number, issued by licensed sponsor | number must match; check job/role/salary |
| `worker.english` | English language evidence | yes | B1 (SELT) or degree taught in English | — |
| `worker.funds` | Maintenance funds | conditional | £1,270 held 28 days (illustrative) | waived if sponsor certifies maintenance |
| `worker.tb` | TB test certificate | conditional | approved clinic, ≤6 months | listed countries only |
| `worker.criminal` | Criminal record certificate | conditional | — | only for specified occupations (e.g. education, healthcare) |
| `worker.quals` | Qualifications / professional registration | conditional | — | where the occupation requires |

## Financial requirements

- **Maintenance:** £1,270 (illustrative — verify) held for **28 consecutive days**, ending within **31 days** of application — **unless** the sponsor certifies maintenance on the CoS (then `worker.funds` is not applicable).
- **Salary (on the CoS, checked for consistency, not a client-supplied doc):** must be at least the higher of the general threshold or the going rate for the occupation code. Verify current figures.

## Applicability (exemptions)

- `worker.funds` — waived when sponsor certifies maintenance on the CoS.
- `worker.tb` — listed countries of residence only.
- `worker.criminal` — specified occupations only.
- `worker.quals` — occupations requiring registration/qualifications only.

## Refusal-risk factors

- CoS reference mismatch, or CoS issued by a non-licensed sponsor
- CoS salary below general threshold or going rate for the occupation code
- Maintenance funds not held 28 consecutive days (when not sponsor-certified)
- English evidence below B1

## Cover letter template

```
Dear Entry Clearance Officer,

I am applying for a Skilled Worker visa sponsored by [sponsor] for the role
of [role], CoS reference [cos_number], start date [start].

[Verified facts only — CoS number, sponsor, role, salary. Every figure must
 trace to an extracted CoS/Document field; unverified claims are blocked by
 gate.provenance.]

Yours faithfully,
[applicant name — from passport]
```

## Assembled checklist (deliverable)

1. Passport — `worker.passport`
2. CoS — `worker.cos`
3. English evidence — `worker.english`
4. Maintenance funds (if not sponsor-certified) — `worker.funds`
5. TB certificate (if required) — `worker.tb`
6. Criminal record certificate (if required) — `worker.criminal`
7. Qualifications/registration (if required) — `worker.quals`

## Provenance / maintenance

- Each `req_id` cites its gov.uk source + accessed date in the module data file.
- Salary thresholds and the £1,270 maintenance figure are change-prone: when re-sourced, update module data + `evals/fixtures/gap/` in the same change.
