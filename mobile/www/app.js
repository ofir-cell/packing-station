// Live Ops Hub — native shell logic (Capacitor).
// Uses native plugins when running in the app; degrades gracefully in a browser.
const CAP = window.Capacitor || {};
const P = CAP.Plugins || {};
const isNative = !!(CAP.isNativePlatform && CAP.isNativePlatform());
const CONSOLE_URL = "https://www.getwhatnot.com";
const DELETE_URL = "https://www.getwhatnot.com/me"; // account page — see README: add a self-serve "Delete account" action here

function show(id) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("on"));
  document.getElementById(id).classList.add("on");
}

// ---- Navigation ----
document.getElementById("toAccount").onclick = () => show("account");
document.getElementById("toHome").onclick = () => show("home");

// ---- Barcode scan (native MLKit; falls back to prompt in a browser) ----
document.getElementById("scanBtn").onclick = async () => {
  try {
    let code = null;
    if (P.BarcodeScanner && P.BarcodeScanner.scan) {
      const perm = await P.BarcodeScanner.requestPermissions?.();
      if (perm && perm.camera === "denied") { alert("Camera access is needed to scan. Enable it in Settings."); return; }
      const res = await P.BarcodeScanner.scan();
      code = res && res.barcodes && res.barcodes[0] ? res.barcodes[0].rawValue : null;
    } else {
      code = window.prompt("Enter a barcode (native scanner runs on device):");
    }
    if (!code) return;
    document.getElementById("scanTitle").textContent = "Scanned — looking up…";
    document.getElementById("scanCode").textContent = code;
    document.getElementById("scanResult").style.display = "block";
    // Hand the scanned code to the console (keeps the authenticated web session as source of truth).
    await openConsole("/scanit?code=" + encodeURIComponent(code));
  } catch (e) {
    if (String(e).indexOf("cancel") === -1) alert("Scan failed: " + e);
  }
};

// ---- Open the operations console in an in-app browser ----
async function openConsole(path) {
  const url = CONSOLE_URL + (path || "");
  if (P.Browser && P.Browser.open) { await P.Browser.open({ url, presentationStyle: "fullscreen" }); }
  else { window.open(url, "_blank"); }
}
document.getElementById("openConsole").onclick = () => openConsole("/home");

// ---- Account ----
document.getElementById("signOut").onclick = () => openConsole("/logout");
document.getElementById("deleteAccount").onclick = async () => {
  if (!confirm("Permanently delete your account and request data deletion? This can't be undone.")) return;
  // Account deletion is completed in the authenticated web session (see README backend TODO).
  await openConsole("/me?delete=1");
};

// ---- Offline banner ----
async function initNetwork() {
  const banner = document.getElementById("offline");
  const set = (connected) => { banner.style.display = connected ? "none" : "block"; };
  try {
    if (P.Network) {
      const s = await P.Network.getStatus();
      set(s.connected);
      P.Network.addListener("networkStatusChange", (st) => set(st.connected));
    } else {
      set(navigator.onLine);
      window.addEventListener("online", () => set(true));
      window.addEventListener("offline", () => set(false));
    }
  } catch (e) { /* ignore */ }
}

// ---- Push notifications (register on launch) ----
async function initPush() {
  if (!isNative || !P.PushNotifications) return;
  try {
    const perm = await P.PushNotifications.requestPermissions();
    if (perm.receive === "granted") {
      await P.PushNotifications.register();
      P.PushNotifications.addListener("registration", (t) => console.log("[push] token", t.value));
      P.PushNotifications.addListener("pushNotificationReceived", (n) => console.log("[push] received", n));
    }
  } catch (e) { console.log("[push] init failed", e); }
}

initNetwork();
initPush();
