# Visa module — Standard Visitor

## Route

UK **Standard Visitor** visa — tourism, visiting family/friends, short business activity, up to 6 months. Scope: main applicant, applying from outside the UK. (Longer-term/multiple-entry variants and dependants out of MVP scope.)

> **Provenance rule:** every requirement below carries a `req_id`. Production values must be re-verified against current gov.uk guidance (source cited + accessed date) before use. Figures here are illustrative for the spec and the harness fixtures.

## RequirementSet — required documents

| req_id | Document | Mandatory | Format / validity | Notes |
|---|---|---|---|---|
| `visitor.passport` | Passport | yes | valid for entire intended stay | — |
| `visitor.travel_plan` | Travel itinerary / bookings | recommended | consistent dates | flights not strictly required; itinerary suffices |
| `visitor.accommodation` | Proof of accommodation | yes | hotel booking or host invitation + address | host invitation must name inviter/invitee |
| `visitor.funds` | Proof of funds | yes | recent (≤28 days) bank statements | no fixed minimum; must show self-support |
| `visitor.income` | Evidence of income/employment | recommended | employer letter or payslips | supports "genuine visitor" |
| `visitor.home_ties` | Evidence of ties to home country | recommended | employment, property, family | **refusal-risk sensitive** |
| `visitor.invitation` | Invitation letter (if visiting someone) | conditional | inviter details + relationship + purpose | required when staying with a private host |

## Financial requirements

- **No fixed threshold.** The applicant must demonstrate they can fund the trip and return **without working or accessing public funds**.
- Evidence: recent bank statements showing available funds; income evidence to show the funds are genuine and sustainable.

## Applicability (exemptions)

- `visitor.invitation` applies only when staying with a private individual (not a hotel).
- `visitor.income` / `visitor.home_ties` are "recommended, not mandatory" — but both feed the **genuine-visitor** assessment, so a case missing both should be flagged `refusal_risk` for human review even though no `MISSING` fires.

## Refusal-risk factors (→ trigger `refusal_risk` escalation)

- No evidence of ties to home country (weak return incentive)
- Unclear purpose of visit or purpose inconsistent with documents
- Funds insufficient for the stated trip length, or funds appear recently deposited without explanation
- History of overstay / prior refusals (if disclosed)

## Cover letter template

```
Dear Entry Clearance Officer,

I am applying for a Standard Visitor visa to [purpose] from [start] to [end].

[Verified facts only — itinerary dates, accommodation, fund source. Every figure
 must trace to an extracted Document field; unverified claims are blocked by
 gate.provenance.]

Yours faithfully,
[applicant name — from passport]
```

## Assembled checklist (deliverable)

1. Passport (valid for stay) — `visitor.passport`
2. Itinerary / bookings — `visitor.travel_plan`
3. Accommodation evidence — `visitor.accommodation`
4. Bank statements (≤28 days) — `visitor.funds`
5. Income evidence — `visitor.income`
6. Home-ties evidence — `visitor.home_ties`
7. Invitation letter (if applicable) — `visitor.invitation`

## Provenance / maintenance

- Each `req_id` must cite its gov.uk source and accessed date in the module data file.
- Changing a rule (e.g. a validity window) updates the module **and** its `evals/fixtures/gap/` fixture in the same change.
