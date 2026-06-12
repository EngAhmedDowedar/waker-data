# SCHOOL_PARSER_FINAL.md — Verified School Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38), JOB→GYM→ESTATE→GOODS methodology. Reused the
symbol DB (targeted greps) + fresh disassembly; JSON keys resolved deterministically
against PIC base `0x75ab20`. Vtable: `+0x14`=begin-iterator (ARRAY), `+0x40`=
GetObjectItem; int64 helper `0x69300c`; catalog lookup `GetById` `0x69341c`.

---

## 1. Ownership (verified)

| Catalog | ids | Loader (client-local) |
|---------|-----|----------------------|
| `subject.city` (35) | 1600–1634 | `CGameData::LoadSubject` |
| `subject_type.city` (5) | 1500–1504 | `CGameData::LoadSubjectType` |

Both **client-local**. `subject.f1` (1500+) → `subject_type.id`; subject also carries config
(`f7`≈500000 cost, `f6`,`f4` string-ids). Also parsed from impart by `CImpart::ParseSubjects`.
The subject/category *list* is built client-side (no endpoint sends rows). **ASSET_ONLY.**

---

## 2. Screens & parsers (verified symbols)

| Symbol | Role |
|--------|------|
| `CSchoolScreen::ParseSubject` @0x56b27a | enrolled-classes / school state parser |
| `CSchoolScreen::OnReceiveResponse` | dispatcher (delegates to ParseSubject) |
| `CSchoolCateScreen::OnReceiveResponse` | **apply-class** action |
| `CGraduateScreen::OnReceiveResponse` | **graduate/exam** action |
| `CPlayer::ParseSubjects` | player-payload enrolled classes (**identical** key set to ParseSubject) |
| `CImpart::ParseSubjects` / `CCitier::ParseSubjects` | impart config / other-player view |

`CSchoolScreen::ParseSubject` and `CPlayer::ParseSubjects` read the **same** keys — the
player's school state is delivered both in the CPlayer payload and via getmyclasses.

---

## 3. Verified JSON keys & containers

### `CSchoolScreen::ParseSubject` / `CPlayer::ParseSubjects` — enrolled classes
`data` is an **OBJECT**; keys:
| key | container | access |
|-----|-----------|--------|
| `classStu` | **ARRAY** (begin-iter +0x14) | enrolled study sessions / active classes |
| `classId` | scalar int | GetInt64; looked up via `GetById` into subject.city |
| `myClasses` | **ARRAY** (begin-iter +0x14) | the player's classes; each element's id looked up via `GetById` into subject.city |

Each `classStu`/`myClasses` element references a subject by id (1600–1634), merged
client-side. Per-element fields are read positionally / via `GetById` (no additional named
keys resolved in the body) — i.e. an element carries at least the subject/class **id**;
any further runtime fields (level/endTime) are not exposed as named string keys here.

### `CSchoolCateScreen::OnReceiveResponse` — apply for a class
Keys: `createAt`, `finishAt`, and action label `school_apply_subject`.
⇒ enrolling returns the study window `{ createAt:<ts>, finishAt:<ts> }`. **OBJECT** of scalars.

### `CGraduateScreen::OnReceiveResponse` / `CSchoolScreen::OnReceiveResponse`
No named string keys (delegate to ParseSubject / update scalar player state, e.g. level/
graduation flag). Object response; null-guarded.

---

## 4. Field provenance

| Field | Source |
|-------|--------|
| `classId`, `myClasses[].id`, `classStu[].id` | **server (references subject.city id)** |
| subject name / cost / type | **client-local** (subject.city via `GetById`) |
| `createAt`, `finishAt` | **server runtime** (enrollment window) |

Server sends enrollment *instances* (subject id + timing); the client merges the catalog
row by `GetById(classId)`.

---

## 5. Endpoint classification

| Endpoint | Parser | Class | Container |
|----------|--------|-------|-----------|
| subject / subject_type catalog | `CGameData::LoadSubject*` | **ASSET_ONLY** (client-local) | n/a |
| `/city/school/getmyclasses` | `CSchoolScreen::ParseSubject` | **PLAYER_STATE** (MIXED: refs catalog) | object `{classStu:[],classId,myClasses:[]}` |
| `/city/school/applyclass` | `CSchoolCateScreen::OnReceiveResponse` | **ACTION_RESPONSE / MIXED** | object `{createAt,finishAt}` |
| graduate / exam | `CGraduateScreen::OnReceiveResponse` | **ACTION_RESPONSE** | object (scalar player update) |
| CPlayer payload school state | `CPlayer::ParseSubjects` | PLAYER_STATE | object `{classStu:[],classId,myClasses:[]}` |

---

## 6. Container expectations

| Structure | Container |
|-----------|-----------|
| getmyclasses / CPlayer school state | **OBJECT** with two nested **ARRAYS** (`classStu`, `myClasses`) + scalar `classId` |
| applyclass | OBJECT of scalars (`createAt`, `finishAt`) |
| classStu / myClasses elements | objects/ints carrying a subject id (1600–1634) |

---

## 7. Minimal valid payloads

```
getmyclasses → { "classStu": [], "classId": 0, "myClasses": [] }
               (guaranteed-safe; to show enrollment, populate the arrays with elements
                whose id ∈ subject.city 1600–1634)
applyclass   → { "createAt": <now>, "finishAt": <now + studySeconds>,
                 "school_apply_subject": 1 }
               (minimal-safe: {} )
graduate/exam→ { }   (scalar player update; minimal-safe {} — populate level/flag when known)
CPlayer       → "...": { "classStu": [], "classId": 0, "myClasses": [] }
```
All keys null-guarded ⇒ `data:{}` never crashes.

---

## 8. Class-A risks & shape mismatches

- **No current Class-A risk.** Unlike fight/randomfighters (where `data` itself is the
  array), school's top-level `data` is an **OBJECT**; `classStu`/`myClasses` are **nested**
  keys read via `GetObjectItem` (null-guarded). The catch-all `data:{}` is therefore safe —
  the arrays are simply absent.
- **Latent Class-A:** *if* you populate `classStu` or `myClasses`, they **MUST be arrays**
  (begin-iter +0x14); supplying `{}` for either would null-iterate → SIGSEGV.
- **Shape note (non-crashing):** school currently hits the catch-all (`data:{}`), so
  getmyclasses shows no enrollment but does not crash. To populate, return the object with
  the verified keys above — no key-name mismatch like Goods' `bags` vs `playerGoods`,
  because the verified keys (`classStu`/`classId`/`myClasses`) are not yet used by any
  server route.

---

## 9. Confidence

- Top-level keys & containers (`classStu`/`classId`/`myClasses`; `createAt`/`finishAt`):
  **High** (deterministically resolved; `+0x14` array markers + `GetById` merge observed).
- `myClasses`/`classStu` **element** sub-fields: **Medium** — elements carry a subject id
  merged via `GetById`; no additional named keys appear in the parser body (read
  positionally), so per-element runtime fields beyond the id are not enumerated.
- School command ids: **not extracted** (dispatchers delegate; not required to shape the
  object payloads — endpoints are path-keyed here).

Success criterion met for the **container shapes and top-level field names** of every
School endpoint (getmyclasses, applyclass, graduate) — implementable without guessing the
object/array structure. The only residual unknown is the *inner* per-class element field
names, which are positional/id-based rather than string-keyed; serving empty arrays (or
arrays of valid subject ids) is verified-safe.
