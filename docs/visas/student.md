# Visa module — Student Route

## Route

UK **Student Route** visa — study at a licensed student sponsor (HEI or other). Scope: main applicant, applying from outside the UK. (Dependants and extensions out of MVP scope.)

> **Provenance rule:** every requirement below carries a `req_id`. Production values must be re-verified against current gov.uk guidance. Figures here (maintenance amounts, 28-day rule) are illustrative and MUST be re-sourced before production.

## RequirementSet — required documents

| req_id | Document | Mandatory | Format / validity | Notes |
|---|---|---|---|---|
| `student.passport` | Passport | yes | valid for stay | — |
| `student.cas` | CAS (Confirmation of Acceptance for Studies) | yes | reference number, issued by licensed sponsor | number must match exactly |
| `student.funds` | Proof of maintenance funds | yes | see financial requirements (28-day rule) | may be waived by sponsor certification (see applicability) |
| `student.english` | English language evidence | conditional | SELT at required level, or degree taught in English | sponsor may confirm on CAS |
| `student.tb` | TB test certificate | conditional | from approved clinic, ≤6 months old | only for listed countries of residence |
| `student.atas` | ATAS certificate | conditional | — | only for courses requiring ATAS clearance |
| `student.consent` | Parental/guardian consent | conditional | — | under-18 applicants |
| `student.quals` | Prior qualifications / transcripts | conditional | — | as required by sponsor/CAS |

## Financial requirements (maintenance)

- Must show **course fees for the first year** (or full fees if course ≤1 year) **plus living costs**.
- Living-cost allowance (illustrative — verify current): **£1,334/month** in London, **£1,023/month** outside London, for up to **9 months**.
- **28-day rule:** the full required amount must have been held for **28 consecutive days**, ending no more than **31 days** before the application date.
- Check in `gap-analysis`: `student.funds.28day` — `min_balance ≥ required` AND `period covers 28 consecutive days` AND `period_end within 31 days of application`.

## Applicability (exemptions)

- `student.funds` waived if the sponsor certifies maintenance on the CAS.
- `student.tb` only for applicants resident in listed countries.
- `student.atas` only for courses requiring ATAS.
- `student.english` not needed if the CAS confirms the sponsor assessed English.
- `student.consent` only for under-18s.

## Refusal-risk factors

- Funds not held for the full 28 consecutive days, or dipping below the minimum on any day
- CAS reference mismatch, or CAS issued by a non-licensed sponsor
- Missing/invalid TB certificate for a listed-country applicant
- English evidence below the required level

## Cover letter template

```
Dear Entry Clearance Officer,

I am applying for a Student Route visa to study [course] at [institution],
CAS reference [cas_number], course dates [start] to [end].

[Verified facts only — CAS number, course, institution, maintenance balance.
 Every figure must trace to an extracted Document/CAS field; unverified
 claims are blocked by gate.provenance.]

Yours faithfully,
[applicant name — from passport]
```

## Assembled checklist (deliverable)

1. Passport — `student.passport`
2. CAS — `student.cas`
3. Maintenance funds (28-day) — `student.funds`
4. English evidence (if required) — `student.english`
5. TB certificate (if required) — `student.tb`
6. ATAS (if required) — `student.atas`
7. Parental consent (if under 18) — `student.consent`
8. Qualifications (if required) — `student.quals`

## Provenance / maintenance

- Each `req_id` cites its gov.uk source + accessed date in the module data file.
- The 28-day and maintenance figures are the most change-prone: when re-sourced, update module data + `evals/fixtures/gap/` in the same change.
