# Verification report

**Task:** `<TASK_ID>` — `<short title>`  
**Role:** verifier  
**Date:** `<YYYY-MM-DD>`

**Task type:** `repo_only` | `repo_and_deploy` | `deploy_only`  
- **`repo_only`** (no live/host acceptance): **Host** and **Live** = `not applicable` (one line each); still complete **Final verdict**.  
- **`repo_and_deploy` / `deploy_only`** or any acceptance needing host/live: **Host** and **Live** must hold **verbatim** transcripts unless the task explicitly waives a layer.

---

## 1. Repo layer

`<What was confirmed in the committed tree (paths, markers).>`  
Repo confirmation alone is **not** closure when acceptance requires host or live proof.

---

## 2. Host layer

```text
<paste exact inspection commands>
```

```text
<paste stdout/stderr — or: not applicable>
```

---

## 3. Live HTTP / operational layer

```text
<paste exact curl -v or equivalent; redact secrets>
```

```text
<paste relevant headers/body — or: not applicable>
```

---

## 4. Acceptance mapping

| Acceptance criterion | Evidence (section #) | Result (pass / fail) |
|----------------------|----------------------|----------------------|
| `<criterion 1>` | | |
| `<criterion 2>` | | |

---

## 5. Repo / host / live mismatches

`<Contradictions between layers, or: none>`

---

## 6. Final verdict

**Verdict (required):** `PASS` **or** `FAIL`

`<One sentence: verdict vs acceptance and whether evidence quality met the bar.>`

---

## 7. Recommended next status

`<verified_pass | verified_fail | blocked — verifier updates task YAML per tasks/README.md>`
