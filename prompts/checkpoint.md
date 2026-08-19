# Checkpoint prompt

Paste this at a natural boundary, **before** the limit forces the issue. The
goal is that abandoning this session costs nothing.

---

```
Let's checkpoint so a fresh session can take over. Do these in order and don't
start anything new:

1. PATCH SCRIPT
   Make sure every change we've made is captured in a single re-runnable
   script, applied to the pristine input. Run it end-to-end from the original
   file and confirm it reproduces the current state. If it doesn't, fix the
   script — not the output file.

2. STATE.md
   Write it with exactly these sections:
   - Goal: one sentence.
   - Done: what is finished and verified, with how it was verified.
   - Pending: what remains, in the order it should be attempted.
   - Ruled out: what we tried that didn't work, and WHY. This is the expensive
     part to rediscover — be specific, include the numbers.
   - Open questions: anything I need to decide.
   - Files that matter: which files a fresh session should read, and which it
     should NOT read.

3. EVIDENCE
   Save the current test/validator output to a file. Not the full log — the
   summary and any failures.

4. CLEAN UP
   Delete intermediates nothing reads any more. Move generated output into
   artifacts/. List what you deleted so I can object.

5. HANDOFF CHECK
   Read STATE.md back as if you had never seen this conversation. Tell me
   honestly what a fresh session would still not know. Then add it.

Keep STATE.md under 100 lines. If it doesn't fit, the session did too many
things and the summary should say which one matters.
```

---

## Why step 5 matters

A checkpoint written by someone with full context always reads as complete.
The only way to test it is to read it *without* that context, which is exactly
what the fresh session will do. Ask for that check explicitly — it reliably
surfaces one or two things that were only ever in the conversation.

## Then

Start a new session and open with [`resume.md`](resume.md).
