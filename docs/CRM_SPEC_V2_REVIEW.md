# CS Hub — Spec v2 review (against the current system)

Review of `crm_spec_v2.md` before any build. Grounded in the code as it stands on `feature/responsive-pass`. Three parts: what maps cleanly onto what we already have, what's genuinely new, and the risks / open decisions that must be settled before Phase 1.

---

## 1. What maps cleanly (reuse, don't rebuild)

**Auto-fill (flow step 2) is almost free.** Everything the ticket needs already exists:
- buyer + history + addresses → `/api/customers/<username>`
- order / show / items / tracking → `shipments` + `shipment_items`, matched by `_resolve_shipment_by_code`
- delivery status + last scan → USPS v3 sync (`delivery_status`, `delivery_detail`, `delivered_at`)
- packing video → `packing_log.csv` → presigned R2 URL (same pattern as return photos)
- linked return case + photos → `return_cases` already links by tracking

**The whole AI-key + audit + human-gate pattern is already proven** in the Returns module. The CS Hub should be built as a direct clone of it, not a new paradigm:
- `_returns_actor()` → bearer key labels the actor "AI", every write audited → becomes the ticket actor model.
- Per-field human gate (AI sets `decision`/notes, humans do money/sent) → exactly the ticket rule "AI cannot decide."
- `updated_since` filter → the AI reads cheaply; prefer the webhook over polling.

**Roles already fit.** `admin`, `manager`, `cs`, `worker` all exist and are enforced server-side. "Warehouse sees only Returns" is already expressible through Access Management (`access.json` + PAGES registry) — no new permission engine needed.

**Search + buyer page** largely exist (`/api/search`, `/customers`, `/api/customers/<username>`). The buyer page (screen 3) is mostly a re-skin of `/customers` plus notes/tags.

Net: screens 1–3 are ~60% assembled from existing data; the new work is the `tickets` table, the inbox/assignment layer, and the scoped key.

---

## 2. What's genuinely new (Phase 1, all code, no platform approval)

1. **Scoped, revocable API keys** — replace the single global `RETURNS_AI_KEY` with an `api_keys` table (key hash, label, scopes[], revoked, created_by). Scopes like `tickets:write`, `customers:read`, `tickets:draft`, **never** `money:*` or `send:*`. Build this first — it's the security spine for everything the AI touches.
2. **`tickets` + `ticket_messages` + `customer_notes`** tables (the spec's data model is good; keep `org` on every row).
3. **Inbox** with filters, counters, take/assign, soft "viewing" lock.
4. **Ticket page** (auto-fill + AI box + decision block + internal notes + timeline).
5. **Webhook out** when a ticket hits "Decided – waiting for AI" (we only consume webhooks today; this is our first outbound one — sign it like the inbound ones, fire-and-forget with a timeout).
6. **Dashboard** (counts by status/person, deadlines, refunds/week, risky buyers).

None of these are blocked on TikTok or Whatnot approvals.

---

## 3. Risks and open decisions (settle before building)

### A. Money + the "Auto lane" is the highest risk in the spec
v2.1 has the AI **autonomously executing refunds up to 50%** and sending offers. Two hard constraints:
- **The AI must never move money on its own.** Even with platform scopes, a refund/offer is a human-approved action. The server must enforce this per field — the AI can *draft* and *queue* a refund; a human (owner/manager above the limit) confirms it, exactly as Returns gates `decision`.
- **Auto lane should ship OFF and come last (Phase 3), not now.** When it does ship it needs hard, server-side guardrails: per-ticket cap, **daily $ cap**, kill switch, "buyer with 2+ refunds in 30d or flagged → never Auto," and every auto action logged with the evidence it used. These are in the spec — good — but they're load-bearing, so they belong in their own phase with its own tests, not bundled into Phase 1.

Recommendation: **Phase 1 money limit = 0 (owner/manager only), Auto lane not built yet.**

### B. "AI executes on the platform" is gated on approvals we don't have
Flow steps 1, 3, 5 assume the AI can **read customer messages** and **send replies / make offers** on TikTok and Whatnot. Today:
- **No TikTok messaging scope** authorized (no IM/conversation endpoints called).
- **No TikTok return/refund (Reverse) scope** authorized.
- **No Whatnot message access** at all, and the Whatnot account isn't PII-approved.

So "AI creates a ticket for every new message" and "AI sends the approved reply on the platform" **cannot run until those scopes are granted** (a platform-review step, not code). Phase 1 must therefore be:
- tickets created **manually** + **from return cases** (not from platform messages yet),
- AI **drafts** the reply; a **human copies/sends** it on the platform (or marks it sent),
- no on-platform execution.

This is still very useful — one shared queue, auto-filled context, AI-prepared Hebrew summary + English draft — it just doesn't close the loop automatically until scopes land. **Confirm this is an acceptable first slice.**

### C. "One inbox for everyone" vs. "keep each account separate" — pick one
The spec says both. HERA + 5SEC + Peach are **separate orgs = separate databases** (tenant isolation is a hard invariant: a user of one org can't read another). So a single inbox spanning all three **breaks that isolation** unless we build a deliberate cross-org CS aggregation in `platform.db` with its own access rules. Decision needed:
- **(i)** One inbox **per account** (cleanest, respects isolation), with a fast account switcher, **or**
- **(ii)** One cross-account inbox → extra work (L) and a new shared store + access model.

My lean: start **(i) per-account** for Phase 1; add a cross-account roll-up view later if the team wants it.

### D. Concurrency — the lock and "Take it" must be DB-based
We run several gunicorn workers with **no shared in-process state** (invariant). So "Dana is viewing" and "Take it" can't be in-memory:
- assignment = atomic `UPDATE tickets SET assigned_to=? WHERE id=? AND assigned_to IS NULL` (so two people can't both take it),
- "viewing" = a soft heartbeat row with a timestamp, shown as advisory only.

### E. Risk score needs a concrete definition
"risk dot / red risk → Needs owner" drives money gating, so it can't be vague. We can compute it from existing data: order count, # past refunds/returns, RTS count, cancellation rate. Define green/amber/red thresholds explicitly before it gates anything.

### F. Reopen-on-reply needs a conversation key
"Same ticket reopens on customer reply" requires matching an inbound message to an existing ticket. Today there's no conversation id (no message API). Once messages flow, store the platform `conversation_id` on the ticket and match on it. Until then, reopen is manual.

### G. Smaller notes
- **Hebrew instructions/summaries**: fine to store, but keep the output-escaping invariant (all HTML escaped) and UTF-8.
- **inbound_photos / attachments**: reuse R2 + presigned URLs, same as return photos.
- **Audit**: route ticket changes, money actions, and AI actions through the shared `audit_log` (plus the per-ticket timeline), not a ticket-only log.
- **The four warning rules** (live sales final, RTS-not-refunded, no acceptance scan → no tracking, >50% → owner) are good and should be **server-side checks**, surfaced as warnings — not just UI text.

---

## 4. Recommended build cut

**Phase 1 — shippable now, no platform approval, money always human:**
scoped API keys → `tickets`/`ticket_messages`/`customer_notes` → Inbox + Ticket page + Buyer page → atomic take/assign + soft viewing lock → internal notes → auto-fill from existing customer/order/tracking/video data → dashboard → outbound webhook on "Decided – waiting for AI." AI drafts; humans approve and send. Per-account inbox.

**Phase 2 — needs platform approval:**
auto-create tickets from TikTok messages; TikTok return/refund (Reverse) sync into tickets; AI sends the approved reply / makes the approved offer on-platform (still human-approved).

**Phase 3 — Auto lane (off by default):**
per-rule toggles, per-ticket + daily $ caps, kill switch, daily AI report, "never Auto" for flagged/repeat-refund buyers, every action logged with evidence.

---

## 5. Decisions I need from you before Phase 1
1. **Per-account inbox** (recommended) or one cross-account inbox?
2. Confirm **Auto lane is deferred** (Phase 3) and **all money stays human** in Phase 1.
3. Confirm Phase 1 works as **manual + returns-driven tickets, AI drafts, human sends** (since message/refund APIs aren't approved yet).
4. Default money limit for CS staff = **0** (owner/manager only)?
