# Implementation report

**Task:** `<TASK_ID>` — `<short title>`  
**Role:** implementer  
**Date:** `<YYYY-MM-DD>`

**Task type:** `repo_only` | `repo_and_deploy` | `deploy_only`  
- **`repo_only`:** fill **Repo** sections; set **Host** and **Live** to `not applicable` (single line each). Do not fold host/live into repo prose.  
- **`repo_and_deploy` / `deploy_only`:** **Host** and **Live** must contain real inspection commands and **verbatim** output when the task requires that evidence.

---

## 1. Repo findings

`<Paths inspected; facts from the committed tree only.>`

---

## 2. Changes made

`<path>` — `<one-line reason>`

---

## 3. Commands run

```text
<paste exact command>
```

```text
<paste stdout/stderr; if truncated, state from which line>
```

---

## 4. Tests run

```text
<paste task execution.repo_test_command or equivalent>
```

```text
<paste summary / failures>
```

If none: state why (e.g. `repo_test_command: not_applicable`).

---

## 5. Host state (deploy / install)

**Actual** packages, units, nginx config loaded, revision installed. **Not applicable** for strict `repo_only` tasks.

```text
<paste host commands and output, or: not applicable>
```

---

## 6. Live HTTP / operational checks

**Actual** URL responses or operational checks **if** the implementer ran them and the task scope allows. **Not applicable** when out of scope or `repo_only` without live acceptance.

```text
<paste curl/httpie and snippets; redact secrets — or: not applicable>
```

---

## 7. Remaining gaps or blockers

`<List honestly; if none, say none.>`

---

## 8. Recommended next status

`<e.g. verification_pending — do not self-certify resolved when live acceptance exists>`
