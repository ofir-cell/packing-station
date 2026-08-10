# Invite emails the easy way — Google (no domain, no DNS)

Railway blocks the normal email ports, so "Send invite email" timed out. This
method sends through a tiny **Google Apps Script** that lives in your own Google
account. Emails go out **from your Gmail**, replies come back **to you**, and
there is **no domain or DNS to set up**.

Total time: ~5 minutes. You only do this once.

## Step 1 — Create the script
1. Go to **script.google.com** → **New project**.
2. Delete whatever is there and paste this in:

```javascript
function doPost(e){
  try{
    var p = JSON.parse(e.postData.contents);
    if (p.secret !== 'CHANGE-ME-TO-A-SECRET') {
      return ContentService.createTextOutput('bad secret');
    }
    MailApp.sendEmail({
      to: p.to,
      subject: p.subject,
      htmlBody: p.html,
      replyTo: p.replyTo || '',
      name: 'Peach Beauty'
    });
    return ContentService.createTextOutput('ok');
  } catch (err) {
    return ContentService.createTextOutput('error: ' + err);
  }
}
```

3. Change `CHANGE-ME-TO-A-SECRET` to any password you make up (e.g.
   `peach-2026-xyz`). Remember it — you'll paste it into Railway in Step 4.
4. (Optional) change `name: 'Peach Beauty'` to whatever name you want recipients
   to see.

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

## Step 4 — Add 2 variables in Railway
Railway → your project → **Variables** → add:

| Variable | Value |
|---|---|
| `GAS_EMAIL_URL` | the Web app URL from Step 3 (ends in `/exec`) |
| `GAS_EMAIL_SECRET` | the secret you set in Step 1 |

Optional — where replies should land (defaults to your Gmail anyway):

| Variable | Value |
|---|---|
| `SMTP_REPLY_TO` | `ofirrashtty@gmail.com` |

Save → Railway redeploys automatically.

## Step 5 — Test
1. Open the **Hires** screen → **📧 Test email** → send yourself one.
2. If it arrives, you're done. New-hire invites now send from your Gmail.

---

### Good to know
- **Limits:** a normal Gmail sends up to ~100 emails/day; Google Workspace up to
  ~1,500/day. Plenty for hire invites.
- **From address:** your own Gmail. **Replies:** come straight to you.
- **Security:** the `Anyone` access is fine because the secret blocks anyone who
  doesn't know it. Keep the secret private.
- If you ever set up Resend or SMTP too, the system prefers Resend, then Google,
  then SMTP — but you only need this one.
- No email at all? The **Copy** button on the invite link always works — send it
  via WhatsApp / SMS yourself.
