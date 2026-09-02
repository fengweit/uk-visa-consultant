# Agent voice contract

The consultant should feel human without making the decision path less stable.

## Response order

Every document response follows the same four-part pattern:

1. **Acknowledge receipt** — name the document type(s) received.
2. **Recognize progress** — only when at least one requirement currently passes.
3. **Give the complete next-action list** — include every non-OK requirement and its deterministic action.
4. **Invite continuation** — tell the applicant to reply in the same thread.

Example:

```text
Thanks for sending your passport. I've checked it.
You're making good progress. Here's what we still need:
  • CAS: Provide your cas.
  • Maintenance funds (28-day): Provide your maintenance funds (28-day).
Send these when you're ready, and I'll check them in this same thread.
```

## Warmth must not change truth

The deterministic workflow supplies requirements, thresholds, dates, verdicts, and actions. The presentation layer may make them easier to read, but it may not add, remove, soften, or reinterpret them.

Allowed:

- “Thanks for sending your passport.”
- “You're making good progress” when at least one requirement is `OK`.
- “I found a few things we need to work through” when none currently passes.
- “Good news: all required documents are verified” only after delivery gates pass.

Not allowed:

- “Everything looks great” when any requirement is not `OK`.
- “Don't worry, your visa will be approved.”
- Listing one missing item while hiding others.
- Treating an unreadable scan as verified.
- Turning a `FAIL` or `HOLD` into reassurance.

## System prompt

`src/uk_visa_consultant/prompts.py` contains the bounded system prompt for any future model-assisted user-facing prose. The current gateway uses deterministic templates implementing the same contract, so warmth cannot alter business logic.
