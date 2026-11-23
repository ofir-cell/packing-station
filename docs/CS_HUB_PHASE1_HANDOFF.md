# CS Hub — Phase 1 handoff (for the AI Chief of Staff)

What's live now in GETWHATNOT, how to connect, and the exact API. Built on the same bearer-key +
audit pattern the Returns module already uses. Everything here is code-complete and tested; nothing
depends on a TikTok/Whatnot API scope.

## What it is
One shared ticket queue per account (HERA / 5SEC / Peach). You (the AI) create a ticket for every
customer message / return / refund request you see in the seller dashboards, auto-filled with the
buyer, order, show, tracking, delivery status, packing video, linked return case, buyer history and
a risk score. You add a Hebrew summary + an English draft reply. A human on the team takes the
ticket and decides. You then execute that decision in the seller dashboard and write back the
result. The ticket closes.

## Hard rules (enforced server-side, not just UI)
- **You can never set a decision.** `PATCH` with a `decision` from the API key → `403`. A human
  decides; you execute exactly what they decided.
- **Money is owner/manager only.** Refund / reship / cancel or any amount > 0 → only an owner or
  manager can set it. CS staff can approve non-money replies (send reply, ask for photo, reject).
- **You can't move a ticket into every status.** Allowed for the AI: `ai_ready`, `waiting_customer`,
  `on_hold`, `customer_replied`, `done`.
- **Auto lane is off (Phase 3).** `lane:"auto"` → `403`. Everything is Team/Owner for now.
- Every change you make is written to the audit log as the actor `AI:<key label>`.

## Auth
Bearer API key, one per account, scoped and revocable. The owner mints it in the app
(`/api/apikeys`) and gives you the raw key once.

```
Authorization: Bearer ghk_xxxxxxxx…
```
Scopes you'll get: `tickets:read`, `tickets:write`, `customers:read`. (Never `money`/`send`.)
A key is bound to one org, so you act only on that account's data. The owner can revoke it in one
call at any time.

## Endpoints

### Create (or reopen) a ticket
`POST /api/tickets`
```json
{
  "platform": "whatnot",
  "account": "HERA",
  "username": "mizzwiglover",
  "platform_order_no": "1542736924",
  "tracking": "9400xxxxxxxxxxxx",
  "type": "refund_return",
  "inbound_text": "Got the wrong shade, I'd like a refund",
  "inbound_photos": ["https://…"],
  "platform_conversation_key": "wn:hera:mizzwiglover:1542736924",
  "last_customer_msg_at": "2026-11-23T14:05:00"
}
```
- `type` ∈ `refund_return | where_order | damaged_missing | question | cancel`.
- The server auto-fills `customer_name`, `shipment_id`, `order_id`, `import_label` (show), `deadline`
  and `return_case_id` from the matched outbound shipment — you only need what you saw.
- **Reopen-on-reply:** always send a stable `platform_conversation_key`
  (`platform:account:username[:order]`). If the customer writes again, post the same key and the
  server appends the message and reopens the existing ticket (`"reopened": true`) instead of making
  a duplicate.
- Response: `{ "ok": true, "id": 123, "reopened": false, "risk": "amber" }`

### List (inbox) + counters
`GET /api/tickets?status=&platform=&type=&assigned=&updated_since=&limit=`
- `updated_since` (ISO) → only tickets changed since; poll cheaply, or rely on the webhook below.
- Returns `{ ok, tickets:[…], counters:{ new, waiting_ai, needs_owner, deadline_today } }`.

### One ticket (full)
`GET /api/tickets/<id>` → ticket + `messages[]` + `log[]` + `warnings[]` + buyer box (flag, tags,
notes). `warnings[]` are server-computed policy flags (e.g. "RTS buyer not refunded — don't
message", "no acceptance scan — don't share tracking", "live sales final on Whatnot").

### Search
`GET /api/tickets/search?q=` — username, name, platform order no., internal order id.

### Update
`PATCH /api/tickets/<id>`
- **AI may write:** `ai_summary_he`, `ai_recommendation`, `ai_amount`, `draft_reply_en`,
  `final_reply_en`, `execution_result`, `executed_at`, `type`, `platform_order_no`, `order_id`,
  `shipment_id`, `deadline`, `last_customer_msg_at`, and `status` (within the allowed set).
- **AI may NOT write:** `decision`, `decision_amount`, `assigned_to`, `lane:auto`.
- Typical AI flow:
  1. After creating: `PATCH {ai_summary_he, ai_recommendation, ai_amount, draft_reply_en, status:"ai_ready"}`.
  2. Human decides in the app → ticket becomes `decided_wait_ai` and you get a webhook (below).
  3. You execute in the seller dashboard, then
     `PATCH {execution_result:"refunded $3.00 on Whatnot", final_reply_en:"…", executed_at:"…", status:"done"}`.

### Messages
`POST /api/tickets/<id>/messages` `{ "direction":"in|out|internal", "body":"…", "photos":[…] }`
- `in` = a new customer message (also reopens → `customer_replied`); `out` = a reply you sent;
  `internal` = a team note.

### Customer context (read)
`GET /api/customers/<username>` — full order history, totals, addresses, packing recordings. Buyer
notes/flags come back inside `GET /api/tickets/<id>`.

## The decision → webhook loop (no polling needed)
When a human sets a decision, the ticket moves to `decided_wait_ai` and the server POSTs to
`TICKETS_WEBHOOK_URL`:
```
POST <your endpoint>
X-GWN-Event: ticket.decided
X-GWN-Signature: <hex HMAC-SHA256 of the raw body, key = TICKETS_WEBHOOK_SECRET>
{ "event":"ticket.decided", "org":"hera", "ticket": { …full ticket incl. decision, decision_amount, final_reply_en, instruction_to_ai… } }
```
Verify the signature, read `decision` + `final_reply_en` + `instruction_to_ai`, execute it in the
dashboard, then `PATCH` the result and set `status:"done"`. (You can also poll
`GET /api/tickets?status=decided_wait_ai&updated_since=…` as a fallback.)

## Risk score (so you know when to escalate)
Each ticket carries `risk` = green / amber / red with `risk_reasons`. Thresholds (per account):
- **Red:** 3+ refunds/returns in 60d · a missing/damaged claim on an order whose packing video shows
  all items · blocked buyer · refunds > 30% of lifetime spend.
- **Amber:** 1–2 refunds in 60d · first-time buyer with a claim · 1+ RTS · on watch list.
- Red risk or any money action → the ticket needs owner/manager; surface it, don't act on money.

## What the owner sets up (once, in Railway)
1. Mint your key: `POST /api/apikeys {label, org, scopes}` → copy the `ghk_…` key (shown once).
2. `TICKETS_WEBHOOK_URL` = your endpoint; `TICKETS_WEBHOOK_SECRET` = a shared secret.

## Phase boundaries
- **Phase 1 (now):** tickets created by you (from dashboard activity) + manually + from returns; you
  draft; a human decides; you execute in the dashboard and record it. Per-account.
- **Phase 2:** direct TikTok/Whatnot API sync (returns/refunds, messages) if/when scopes are
  approved — not required for the above to work.
- **Phase 3:** Auto lane (you decide routine tickets within owner-set caps). Off by default.

## Try it (demo)
Open `cshub-demo.html` to see the Inbox exactly as the team sees it — risk dots, platform, buyer,
issue, status, who's handling it, deadline badges, and the "Take it" button. The ticket page adds
the Hebrew AI box, the decision buttons (money ones locked for CS), the instruction-to-AI box, the
editable English reply, the conversation thread and the timeline.
