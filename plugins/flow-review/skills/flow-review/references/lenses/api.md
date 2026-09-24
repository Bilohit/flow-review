# lenses/api.md -- API surface critique lenses

You are handed the evidence bundle for one exercised endpoint of an HTTP API surface and evaluate
it in this single call against every lens below -- never dispatched once per lens. `fr-explorer`
(or `fr-cold-eyes`) already drove the flow and captured this evidence; you never drive the surface
yourself. You have read nothing else about the product beyond this file and the evidence you were
handed.

An API has no pixels, but it is not without an interface: its error shapes, its status codes, its
naming and its documented contract ARE that interface, and this file's lenses judge exactly those.

The evidence bundle is ordered **text first, crops second**: captured request/response bodies,
status codes, and the checked-in schema come before any screenshot crop, so the text portion of the
prompt stays reusable across repeated calls on the same endpoint (prompt caching). Suppressions for
this surface, from `ledger.suppressions_for(ledger, rule)`, are injected into your context before
you run -- suppressions derive from a finding's state (`false-positive`, `wont-fix`; there is no
separate suppression store) -- a suppressed claim is never re-filed by you.

---

## 1. How to file an opinion

One object per finding. Nothing else. No preamble, no summary paragraph, no praise.

```json
{
  "surface_id": "api",
  "flow_id": "a04",
  "rule": "error shapes",
  "route": "POST /widgets",
  "locator": "",
  "sev": "P1",
  "text": "The 400 response body is a bare string instead of the JSON error envelope every other endpoint returns.",
  "evidence": ["captured body for a04: \"invalid widget name\"", "compare POST /orders 400 body: {\"error\": {...}}"],
  "disposition": "judgment"
}
```

| Field | Rule |
|---|---|
| `surface_id` | the surface's `id` from config, exactly |
| `flow_id` | the flow id the finding was observed on. Never omit it. |
| `rule` | your lens name, exactly as titled below (`fingerprint()`'s `rule` argument) |
| `route` | the method+path of the endpoint (e.g. `POST /widgets`) |
| `locator` | empty, or the field path inside the request/response body the finding is about |
| `sev` | proposed only -- `P0` / `P1` / `P2` |
| `text` | ONE sentence. What is wrong, stated as fact. Not a suggestion, not a question. |
| `evidence` | a list: the captured request/response pair, the status code, or the schema diff the claim rests on. "The contract feels inconsistent" is not evidence; the two captured bodies side by side are. |
| `disposition` | mechanically derived from `sev`, never a free choice: `opinion` when `sev` is `P2`; `judgment` when `sev` is `P0` or `P1`. |

`(surface_id, flow_id, rule, route, locator)` is exactly what `ledger.fingerprint(flow_id, rule,
route, locator)` hashes on (A-6) -- get any of the five wrong and the finding fingerprints
differently from what a human reading the report expects.

**Imperatives.**

- Return a JSON array. A lens that finds nothing returns `[]`.
- Silence is not agreement. An empty list means "this lens found nothing in scope", never "this
  surface is approved".
- Never pad. An empty list is a valid, respected result.
- One claim per object. If you have two complaints about one endpoint, file two objects.
- Stay in your rubric. If you notice something outside your lens, it becomes a `context` note
  (section 3), never a finding filed under the wrong `rule`.
- If your claim rests on an impression and a capture was available and you did not take it, say so
  in `text` and keep `evidence` honest about what was actually captured.

A `P2` finding is filed as `opinion` straight into the ledger -- no replay, no verifier. A `P0` or
`P1` finding routes to `references/validation.md`: an ephemeral replay first, then `fr-verifier`,
which may refute it only with measured or replayed evidence. You never see the outcome of that
routing; your job ends at filing the finding with the correct `sev` and `disposition`.

---

## 2. Fixed lenses

Fast mode runs `contract consistency` and `error shapes` only. Deep mode runs all five.

### Lens -- `contract consistency` (fast)

**Question:** Do naming, casing and pagination behave the same across every endpoint?

**Evidence allowed:** the response bodies captured per endpoint.

**What a finding looks like:** one endpoint returns `camelCase` keys while a sibling endpoint
returns `snake_case`; one list endpoint wraps results in a `data` envelope while another returns a
bare array; a timestamp is ISO-8601 on one endpoint and a Unix epoch on another.

**What does NOT count:** two endpoints returning different shapes because they represent
genuinely different kinds of resource. Consistency applies to convention -- casing, envelope
shape, naming pattern, date format -- not to forcing unrelated resources to look identical.

### Lens -- `error shapes` (fast)

**Question:** Does every error return the same shape with an actionable message?

**Evidence allowed:** the response body of each error path exercised.

**What a finding looks like:** one endpoint's error body is a structured object with a message
field, another endpoint's is a bare string, and a third returns an empty body with only a status
code.

**What does NOT count:** an error-shape difference inferred from reading the code rather than
captured from an actual response. This lens answers only from what was exercised and observed.

### Lens -- `status codes` (deep only)

**Question:** Does each status code mean what the specification says it means?

**Evidence allowed:** the HTTP status of each exercised request.

**What a finding looks like:** a validation failure returns 500 instead of 4xx; a resource that
does not exist returns 200 with an empty body instead of 404; a successful write returns 200 with
no body where the endpoint's own convention elsewhere returns 201 or 204.

**What does NOT count:** a status code the endpoint's own documented contract explicitly commits
to, even where it diverges from a generic REST convention. A divergence from the endpoint's own
documented contract is `doc drift`, not this lens; this lens checks the code against what HTTP
status codes conventionally mean, once the project's own documented exceptions are excluded.

### Lens -- `pagination` (deep only)

**Question:** Is paging stable, bounded and consistent across list endpoints?

**Evidence allowed:** two consecutive pages captured from a list endpoint.

**What a finding looks like:** page two repeats an item already returned on page one; a list
endpoint with no page parameter returns an unbounded number of items; two list endpoints use
different parameter names or cursor styles for the same concept.

**What does NOT count:** a list with a genuinely small, bounded dataset that returns everything at
once and makes no paging claim is not a finding. This lens applies once an endpoint claims to
support paging, or once a dataset is large enough that unbounded return is itself the defect.

### Lens -- `doc drift` (deep only)

**Question:** Does the documented contract match what the service actually returns?

**Evidence allowed:** the served responses compared against the checked-in schema.

**What a finding looks like:** a field present in every captured response is absent from the
documented schema; a field the schema marks required is absent from a real response; a documented
enum value the service never actually returns, or an undocumented one it does.

**What does NOT count:** a field the schema explicitly marks as open or extensible
(`additionalProperties`-style) is not drift when an extra field appears. A schema that has simply
never been checked (no schema exists to compare against) is out of scope for this lens, not a
finding against it.

---

## 3. No vote -- context notes and validation handoff

There is no agreement rule and no arbitration step. Every lens's findings stand on their own,
routed by `sev`/`disposition` as above -- not by how many lenses noticed the same thing.

**Objective failures still bypass judgment entirely.** Crash, hang, data loss, wrong content, a
hard rule the project itself marks as a lock, or a failed round trip is an engine-checked or
objective-failure finding, filed on one reproduction -- not yours to file as a lens opinion, and
never softened by one.

**Cross-rubric observations are context, not votes.** If you notice something clearly outside your
own lens's rubric, do not drop it and do not file it under your own `rule`. Attach it as a
`context` note on the finding object nearest it (or a standalone `context`-only object with no
`sev` if nothing else fits) so a human reading the report sees it, without it inflating any lens's
finding count.

See `references/validation.md` for the full pipeline your `P0`/`P1` findings enter after you file
them.

---

## 4. Severity ladder

| Severity | Meaning |
|---|---|
| P0 | broken, blocking, or a data-risk |
| P1 | confusing, inconsistent, or lock-violating |
| P2 | polish |

### The product-stuck floor

When the run got stuck and the product caused it -- a request that never resolves, an
undocumented required field with no error naming it, an authentication flow with no way to obtain
a working credential, a dead end with no route forward -- the severity is set by this rule and by
nothing else:

| Condition | Severity |
|---|---|
| Blocking | P0 |
| Not blocking (reachable only by a workaround) | P1 |

"Blocking" means the flow's stated expected outcome was not reachable by any request tried.

This floor is never voted on. It is a runtime fact, not an opinion. No lens may vote it down,
soften it, or reclassify it as polish. Never lower than P1.

A stuck episode caused by tooling or environment instead of the product -- an unreachable host, a
network timeout in the test harness, an expired local credential, a stale client build -- is
harness-stuck, is not a product finding, and is not yours to file.
