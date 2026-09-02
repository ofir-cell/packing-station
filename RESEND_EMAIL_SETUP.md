# Invite emails — easiest reliable setup (Resend)

Railway blocks the normal email ports (SMTP), which is why "Send invite email"
was timing out. The fix is to send through **Resend**, which sends over regular
web (HTTPS) and always gets through. Replies still come back to **your** inbox.

Total time: ~5 minutes.

## Step 1 — Create a Resend account
1. Go to **resend.com** → Sign up (free plan = 3,000 emails/month, plenty).

## Step 2 — Add & verify your domain
1. In Resend, open **Domains → Add Domain**.
2. Enter a domain you own (e.g. `peachbeauty.com`).
3. Resend shows a few **DNS records** (SPF / DKIM). Add them at your domain
   registrar (GoDaddy, Namecheap, Cloudflare, wherever you bought the domain).
   - If you're not sure how, send the Resend screen to whoever manages your
     domain — it's copy-paste of 2–3 TXT records.
4. Back in Resend, click **Verify**. It goes green in a few minutes to a few hours.

> No domain? You can still test immediately: Resend lets you send from
> `onboarding@resend.dev`, but only to your **own** email. For real hires you
> need a verified domain.

## Step 3 — Create an API key
1. Resend → **API Keys → Create API Key** → copy it (starts with `re_...`).

## Step 4 — Add 2 variables in Railway
Railway → your project → **Variables** → add:

| Variable | Value |
|---|---|
| `RESEND_API_KEY` | the `re_...` key from Step 3 |
| `RESEND_FROM` | `Peach Beauty <noreply@peachbeauty.com>` (use your verified domain) |

Optional (so replies go to a specific inbox):

| Variable | Value |
|---|---|
| `SMTP_REPLY_TO` | `ofirrashtty@gmail.com` (or your support inbox) |

Then **redeploy** (Railway does this automatically after saving variables).

## Step 5 — Test it
1. Open the **Hires** admin screen → **📧 Test email** → send yourself one.
2. If it arrives, you're done. New-hire invites now send automatically.

---

### How it works now
- The system sends via **Resend** (HTTPS) — never blocked.
- The **From** is your verified domain; the **Reply-To** is your inbox, so if a
  hire replies, it lands with you.
- If you ever also set the old `SMTP_*` variables, they're kept as an automatic
  fallback — but Resend is all you need.
- No email set up? The **Copy** button on the invite link still works — send it
  via WhatsApp / SMS / email yourself.
