# Resume prompt

First message of the fresh session. Attach or point at `STATE.md` and the patch
script.

---

```
This continues earlier work. Read STATE.md first — it is the handoff note, and
it is authoritative over anything you infer from the files.

Rules for this session:

- Read ONLY the files STATE.md lists as relevant. It also names files not to
  read; respect that, they're large and nothing needs them.
- Don't re-derive what's under "Ruled out". If you think something there
  deserves another look, say why before spending anything on it.
- All edits go through the patch script, extending it rather than editing
  output files directly. It must keep running cleanly from the pristine input.
- Batch checks into one command. Print the tail.
- Update STATE.md as you go, not at the end.

Start by telling me, in a few lines:
  1. what you understand the current state to be,
  2. what you plan to do first,
  3. anything in STATE.md that is ambiguous or looks wrong.

Don't start work until I confirm.
```

---

## The confirmation step is not politeness

It is the cheapest possible test of whether the checkpoint survived. If the
fresh session's summary of "current state" doesn't match yours, you have found
a gap in `STATE.md` for the price of three lines — instead of finding it later,
after work has been built on the misunderstanding.

If the summary is wrong, fix `STATE.md` rather than correcting it in chat. The
next session will read the file, not this conversation.
