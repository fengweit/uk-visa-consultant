# Spec — Reminder & follow-up

## Purpose

A **functional** scheduler (no model in the hot path) that keeps the case moving: it reminds the client about deadlines and outstanding gaps, and flags cases at risk of stalling. It is deliberately simple and deterministic — the "just works" module.

## Position in pipeline

```
Case (deadlines + GapReport) ──► scheduler tick ──► due/follow-up events ──► comms layer
```

## Canonical type

```jsonc
// Deadline (stored on the Case, derived from RequirementSet + Documents)
{
  "deadline_id": "dl_0001",
  "kind": "biometrics | funds_window_expiry | document_expiry | gap_outstanding | submission_target",
  "due": "2026-09-15T00:00:00Z",
  "state": "pending | notified | overdue | resolved",
  "reminder_cadence": "1d",            // how often to re-nudge before due
  "message_template": "reminder.biometrics.v1"
}
```

## Behavior

1. **Derive deadlines** from the case: document expiry dates, funds-hold windows, any biometrics appointment, and the client's stated target submission date.
2. **Tick** (scheduled job, e.g. every hour): find deadlines that are due or overdue, and outstanding `MISSING`/`INVALID` gap items.
3. **Emit** a reminder message through the comms layer using a fixed template; a `notified` state prevents duplicate nudges within the cadence.
4. **Escalate** a case to human-in-the-loop when a deadline is overdue beyond a grace period or the case has been silent for a set duration — the reminder module flags; it does not itself take any document/application action.

## Message templates

Fixed, versioned, channel-agnostic text (rendered per-channel by the comms layer). Example:

```
reminder.gap_outstanding.v1:
"Hi {name}, you still need: {missing_list}. Reply here or attach the document
 and I'll check it against your {visa_route} requirements."
```

Templates are data (`reminders/templates.yaml`), keyed by id; the scheduler only selects the id and substitutes fields.

## Stability measures

- **Deterministic triggers:** pure time/state logic — identical state produces identical notifications.
- **Idempotent notification:** `notified` state + `last_notified_at` dedupe; a re-run of the same tick emits nothing twice.
- **No autonomous action beyond messaging:** the module cannot modify documents, form data, or ship anything. It only reminds and flags.
- **Failure handling:** a failed send returns the deadline to `pending` for retry; no notification is silently lost.

## Example

```
Case has: funds_window_expiry due 2026-09-10, state pending
Tick on 2026-09-09 (within 1d cadence):
  → emit reminder.funds_window_expiry.v1 → comms.send()
  → state → notified, last_notified_at = now
Next tick: no duplicate (within cadence)
Tick on 2026-09-12 (overdue > grace):
  → flag case for human-in-the-loop
```

## Test plan

1. Deadline due within cadence → exactly one reminder; repeat tick → no duplicate.
2. Overdue beyond grace → case flagged for HITL.
3. Failed send → deadline back to `pending`, retried next tick.
4. Template substitution renders `{name}` and `{missing_list}` correctly.
5. Scheduler never mutates documents or form data (assert no writes to those stores).

## Open questions

- Notification channel preference per client (WhatsApp vs email vs both)? Recommend: same channel the client last used, overridable in profile.
- Timezone handling for "due" dates — store absolute UTC + client timezone; render local.
