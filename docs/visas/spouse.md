# Visa module — Spouse / Partner (Family Route)

## Route

UK **Spouse/Partner** visa (Family Route) — join a partner who is British or settled in the UK. Scope: main applicant, applying from outside the UK. (Fiancé(e), civil partner, and unmarried-partner variants share most requirements; dependants out of MVP scope.)

> **Provenance rule:** every requirement below carries a `req_id`. Production values must be re-verified against current gov.uk guidance. The financial minimum is the most change-prone figure (raised in 2024 with further planned rises) — MUST be re-sourced before production.

## RequirementSet — required documents

| req_id | Document | Mandatory | Format / validity | Notes |
|---|---|---|---|---|
| `spouse.passport` | Passport(s) | yes | applicant + sponsor | — |
| `spouse.relationship` | Marriage/civil-partnership certificate | conditional | official certificate | for married/civil partners |
| `spouse.cohabitation` | 2-year cohabitation evidence | conditional | bills/correspondence across 2 years | for unmarried partners |
| `spouse.genuine` | Evidence relationship is genuine & subsisting | yes | photos, correspondence, visits, shared finances | refusal-risk sensitive |
| `spouse.financial` | Financial requirement evidence | yes | see financial requirements | sponsor income / savings / combination |
| `spouse.english` | English language evidence | yes | A1 (initial application) | — |
| `spouse.accommodation` | Adequate accommodation evidence | yes | tenancy/deed + size adequacy | — |
| `spouse.tb` | TB test certificate | conditional | approved clinic, ≤6 months | listed countries only |

## Financial requirements

- **Minimum income requirement** (illustrative — verify current): the sponsor must show income of at least **£18,600** (historical) — raised to **£29,000** from April 2024 with further planned rises to £38,700. **This is the single most important figure to re-source.**
- Evidence: sponsor's **6 months of payslips + bank statements + employer letter** (salaried employment), or self-employment accounts, or savings above a threshold, or a combination.
- Check in `gap-analysis`: `spouse.financial.income` — sponsor gross annual income ≥ threshold, evidenced across 6 months.

## Applicability (exemptions)

- `spouse.relationship` (marriage certificate) vs `spouse.cohabitation` — one applies depending on married/civil-partner vs unmarried-partner route.
- `spouse.tb` — listed countries of residence only.
- Savings route — alternative to income; different evidence set.

## Refusal-risk factors

- Sponsor income below the minimum threshold, or income not evidenced for the full 6 months
- Relationship evidence judged insufficient (genuine-and-subsisting is the most common refusal ground)
- Inadequate accommodation (overcrowding)
- English below A1

## Cover letter template

```
Dear Entry Clearance Officer,

I am applying for a Spouse/Partner visa to join my [spouse/partner],
[sponsor name], who is [British/settled] in the UK.

[Verified facts only — relationship dates, sponsor income, accommodation.
 Every figure must trace to an extracted Document field; unverified claims
 are blocked by gate.provenance.]

Yours faithfully,
[applicant name — from passport]
```

## Assembled checklist (deliverable)

1. Passport(s) — `spouse.passport`
2. Marriage certificate OR cohabitation evidence — `spouse.relationship` / `spouse.cohabitation`
3. Genuine-relationship evidence — `spouse.genuine`
4. Financial evidence — `spouse.financial`
5. English evidence — `spouse.english`
6. Accommodation evidence — `spouse.accommodation`
7. TB certificate (if required) — `spouse.tb`

## Provenance / maintenance

- Each `req_id` cites its gov.uk source + accessed date in the module data file.
- The financial minimum (£18,600 → £29,000 → £38,700) is the highest-priority re-source item; when changed, update module data + `evals/fixtures/gap/` in the same change.
