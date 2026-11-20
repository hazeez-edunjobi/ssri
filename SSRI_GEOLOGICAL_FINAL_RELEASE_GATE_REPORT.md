# SSRI — Geological Final Release Gate Report

**Mode:** READ-ONLY final release assessment  
**Date:** 2026-11-20  
**Branch:** `main`  
**HEAD (initial = final):** `28908383555136d63dc7d15283472850e1a456c8`  
**Only file created:** this report  

---

## Overall verdict

**PASS WITH LIMITATIONS**

Geological ingestion, remediation, and acceptance hardening are functionally verified: full backend suite **813 passed / 3 skipped / 0 failed**, frontend typecheck/lint/31 tests/build **PASS**, production 13-channel isolation **intact**, Phase 6 remains **BLOCKED**.

Limitations that prevent an unqualified PASS:

1. Trusted `allow_direct_target_root` escape hatch remains (HTTP cannot set it; misuse possible from in-process scripts).
2. JSONL lock is **local-filesystem only**; **POSIX `fcntl` path was not executed** on this Windows gate host (code present; untested here).
3. Crash after partial stack write but **before** a PASS apply report still cannot be marked successful (by design).
4. Implementation remains **uncommitted local work** — not yet a release commit/tag.

---

## 1. Trusted path escape hatch (`allow_direct_target_root`)

Repo-wide search hits (code + tests; docs omitted from caller table):

| Location | Function / context | Trusted? | User-controlled flag? | HTTP can set flag? |
|----------|--------------------|----------|----------------------|--------------------|
| `geological/apply.py` | `apply_geological_to_offline_dataset` (parameter, default `False`) | Definition | N/A | No — not on `ApplyBody` |
| `api/routes/geological.py` | `apply_offline` — hardcoded `True` **after** `resolve_offline_apply_target` | Yes — path already confined | No — constant in server code | **No** — clients cannot pass the flag; they may send `target_dataset_id` / optional matching `target_dataset_root` only |
| `tests/test_geological_acceptance_hardening.py` | pixel / crash / offset apply helpers | Yes — pytest | No | No |
| `tests/test_geological_ingest.py` | offline apply / depth-fail cases | Yes — pytest | No | No |
| `tests/test_geological_remediation.py` | F2/F5 apply helpers | Yes — pytest | No | No |

**Unreviewed production/ops scripts:** none found calling `allow_direct_target_root`. No `poc/` or CLI scripts reference it.

**Verified:** HTTP request bodies cannot enable the flag. Destination for HTTP is always the resolved registered training dataset root.

**Limitation:** Any future in-process caller that sets `allow_direct_target_root=True` with an arbitrary path bypasses TrainingStorage confinement. Documented; not an HTTP defect.

---

## 2. JSONL lock reliability (`geological/ledger_lock.py`)

### Verified from source

| Property | Evidence |
|----------|----------|
| Windows acquire | `msvcrt.locking(..., LK_NBLCK, 1)` with retry until `timeout_s` |
| POSIX acquire | `fcntl.flock(..., LOCK_EX \| LOCK_NB)` with same retry |
| Exception-safe release | `__exit__` → `_release()`; unlock then `close()` in `finally` |
| No unlocked append path | Sole append is inside `GeologicalStorage.record_feature_application` → `with JsonlAppendLock(...):` then open JSONL |
| Dedup under lock | Identity check + append both inside the lock |
| Lock file creation | Parent mkdir; open `a+b`; seed one `\0` byte on Windows if empty |
| Permissions | OS default umask/ACLs — no explicit chmod (acceptable for local service FS) |

### Unexpected process exit

**Assumption (not crash-tested in this gate):** when the process dies, the OS releases the file lock held by the closed handle (Windows and POSIX advisory/mandatory byte locks). Stale lock **files** may remain on disk but do not block new lockers once the previous handle is gone. **Not verified by kill-signal experiments in this gate.**

### Concurrent writers

**Verified on this host (Win32):** `test_f5_concurrent_ledger_appends` in acceptance hardening — 8 parallel unique writes + duplicate-identity stress; included in full suite green run.

### Platform not tested here

- **POSIX `fcntl` branch:** not executed (gate host `Win32NT`).
- Distributed/network filesystems: out of scope; lock is explicitly local-FS only.

---

## 3. Full backend regression

```text
Working directory: C:\Users\LENOVO\Documents\MrBusoye\ssri\model
Command: poetry run pytest -q --tb=line
Exit status: 0
Result: 813 passed, 3 skipped, 0 failed, 0 xfailed
Duration: ~299 s
```

No failures. Skips include OS-limited symlink coverage (and any pre-existing skips). **No silent retries** were performed for this suite.

---

## 4. Frontend regression

Working directory: `C:\Users\LENOVO\Documents\MrBusoye\ssri\frontend`

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | 0 | PASS |
| `npm run lint` | 0 | PASS |
| `npm test` | 0 | **31 passed**, 0 failed |
| `npm run build` | 0 | PASS (includes `/geological`, `/geological/[id]`) |

Environment noise only: npm `devdir` config warnings; Next `metadataBase` warnings — not test failures.

---

## 5. Production isolation

| Check | Result |
|-------|--------|
| `assess.py` vs HEAD | **Unchanged** (no git diff) |
| `inference/safety.py` vs HEAD | **Unchanged**; still requires `CHANNEL_COUNT` for model `in_channels` |
| `architecture/config.py` vs HEAD | **Unchanged**; default `in_channels=CHANNEL_COUNT` |
| Production channel count | **13** (`CHANNEL_COUNT = len(CHANNEL_NAMES)`) |
| Hazards | `LabelClass`: **subsidence**, **landslide**, **sinkhole** via `SUPPORTED_LABELS` |
| Live AOI ↔ geological catalogue | `acquisition.py` has **no** geological imports |
| Catalogue activation → live tensors | **Not wired** |
| Offline apply `used_in_inference` | Forced **`false`** in apply report, ledger normalize, recovery |

Phase 6 live 16-channel inference: **still BLOCKED** (no gate claim otherwise).

---

## 6. Git preservation

### Initial

- HEAD: `28908383555136d63dc7d15283472850e1a456c8`
- `main...origin/main` (even)
- Modified: PlatformShell, api/app.py, validator.py, inspect_client_csv.py
- Untracked: geological package/UI/tests/docs (including prior audit/remediation/hardening reports)
- Cached diff: empty

### Final

- HEAD: **unchanged** `2890838…`
- Working tree: same modified/untracked set **plus** this gate report as untracked
- `git diff --stat` (tracked): 4 files, +58 / −248 (pre-existing tracked geological-related edits)
- `git diff --cached --stat`: empty
- **No** stage, commit, push, reset, rebase, amend, or cleanup

---

## Verified findings vs untested assumptions

### Verified

- Full backend + frontend green on this machine.
- HTTP cannot set `allow_direct_target_root`; destinations confined via `resolve_offline_apply_target` before trusted apply.
- Ledger appends always take the lock on the write path; concurrent Windows test passed inside full suite.
- Production triad and live acquisition isolation hold.
- Three hazards remain the Stage 2.5 contract.

### Untested / limitations (not defects proven in this gate)

- POSIX flock behaviour on Linux/macOS.
- Process-kill mid-lock behaviour (OS-assumed release).
- Network/shared filesystem locking.
- Crash between stack mutation and PASS report (by design non-recoverable as success).
- Multi-tenant ACL (intentionally single-tenant).
- Scientific validity of client geological measurements / Phase 6 checkpoint (out of scope; BLOCKED).

---

## Summary for operators

1. **Report:** `SSRI_GEOLOGICAL_FINAL_RELEASE_GATE_REPORT.md`  
2. **Verdict:** **PASS WITH LIMITATIONS**  
3. **Backend:** 813 passed, 3 skipped  
4. **Frontend:** typecheck/lint/31 tests/build all pass  
5. **Production isolation:** confirmed; Phase 6 **BLOCKED**  
6. **Git:** HEAD `2890838`; local geological work preserved; nothing committed or pushed  

Await approval before commit, push, or deployment.
