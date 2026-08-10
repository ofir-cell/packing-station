# Invite emails from @5secbeauty.com — Google, no DNS

You have Google Workspace on **5secbeauty.com**, so this is the easiest path:
a tiny **Google Apps Script** sends the mail through your Workspace account.
Emails go out **from an @5secbeauty.com address**, replies come back **to you**,
and there is **no domain verification or DNS to touch**.

Total time: ~5 minutes. You only do this once.

> Important: sign in to Google with your **@5secbeauty.com** account before you
> start — the account you build the script under is the one that sends the mail.

## Step 1 — Create the script
1. Signed in as **@5secbeauty.com**, go to **script.google.com** → **New project**.
2. Delete whatever is there and paste this in:

```javascript
function doPost(e){
  try{
    var p = JSON.parse(e.postData.contents);
    if (p.secret !== 'CHANGE-ME-TO-A-SECRET') {
      return ContentService.createTextOutput('bad secret');
    }
    var opts = {
      htmlBody: p.html,
      replyTo:  p.replyTo  || '',
      name:     p.fromName || '5 Sec Beauty'
    };
    if (p.from) opts.from = p.from;   // e.g. noreply@5secbeauty.com (send-as alias)
    MailApp.sendEmail(p.to, p.subject, '', opts);
    return ContentService.createTextOutput('ok');
  } catch (err) {
    return ContentService.createTextOutput('error: ' + err);
  }
}
```

3. Change `CHANGE-ME-TO-A-SECRET` to any password you make up (e.g.
   `5sec-2026-xyz`). Remember it — you'll paste it into Railway in Step 4.

## Step 2 — Deploy it as a Web App
1. Top right → **Deploy → New deployment**.
2. Click the gear ⚙️ → choose **Web app**.
3. Set:
   - **Execute as:** Me (your email)
   - **Who has access:** **Anyone**  ← required so the system can reach it
4. Click **Deploy**.

## Step 3 — Authorize (one time)
1. Google asks you to **Authorize access** → pick your Google account.
2. You may see "Google hasn't verified this app" → click **Advanced → Go to
   (project name) → Allow**. (It's your own script — this is safe.)
3. Copy the **Web app URL** it gives you. It ends in **`/exec`**.

## Step 4 — Add the variables in Railway
Railway → your project → **Variables** → add:

| Variable | Value |
|---|---|
| `GAS_EMAIL_URL` | the Web app URL from Step 3 (ends in `/exec`) |
| `GAS_EMAIL_SECRET` | the secret you set in Step 1 |

Optional but recommended for a clean look:

| Variable | Value |
|---|---|
| `GAS_EMAIL_FROM` | `noreply@5secbeauty.com` — the address recipients see. Leave blank to use the account you deployed under. Must be that account's address or a "Send mail as" alias on it. |
| `SMTP_FROM_NAME` | `5 Sec Beauty` — the sender name shown |
| `SMTP_REPLY_TO` | `hr@5secbeauty.com` (or wherever you want replies) |

> Using `noreply@5secbeauty.com`? In Gmail on the 5secbeauty.com account go to
> **Settings → Accounts → Send mail as → Add another email address**, add
> `noreply@5secbeauty.com`, and verify it. If you'd rather not, just leave
> `GAS_EMAIL_FROM` blank and it sends from your normal @5secbeauty.com address.

Save → Railway redeploys automatically.

## Step 5 — Test
1. Open the **Hires** screen → **📧 Test email** → send yourself one.
2. If it arrives, you're done. Invites now send from **@5secbeauty.com**.

---

### Good to know
- **Limits:** Google Workspace sends up to ~1,500 emails/day. Plenty for invites.
- **From address:** your @5secbeauty.com. **Replies:** come straight to you.
- **Security:** `Anyone` access is fine because the secret blocks anyone who
  doesn't know it. Keep the secret private.
- If you ever set up Resend or SMTP too, the system prefers Resend, then Google,
  then SMTP — but you only need this one.
- No email at all? The **Copy** button on the invite link always works — send it
  via WhatsApp / SMS yourself.
