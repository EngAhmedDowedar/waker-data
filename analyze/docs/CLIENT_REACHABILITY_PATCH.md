# Client Patch — NGReachability LDPlayer "Not connected" bypass (2026-06-12)

## Why
On LDPlayer, `ConnectivityManager.getActiveNetworkInfo()` returns **null** even though
sockets work. `NGReachability.updateStatus()` maps null → **0 (offline)**, which drives
`NGReachability.onNetworkStatusChange(0)` → native `ngReachabilityAndroid::OnStatus(0)` →
`ngReachability::OnStatusChange(DISCONNECTED)` → `CLoadingMnger::OnStatusChange(DISCONNECTED)`,
which shows the **"Not connected to the network"** dialog and halts the boot **before**
`/city/impart` is sent. (Full trace in the chat analysis / this is a client+emulator issue,
not a server issue — the login payload is byte-identical to the working baseline.)

## Patch
File: `analyze/client-apk-src/smali/com/anansimobile/nge/NGReachability.smali`
Method: `updateStatus()` — the `:cond_2` branch (taken when `getActiveNetworkInfo()` is null).

```diff
     .line 58
     :cond_2
-    const/4 v1, 0x0      # null network -> report 0 (offline) -> "Not connected" dialog
+    const/4 v1, 0x1      # null network -> report 1 (WiFi/online) -> proceed to /city/impart
     goto :goto_0
 .end method
```

Effect: a null `getActiveNetworkInfo()` now reports **WiFi/online (1)** instead of offline,
so `CLoadingMnger` proceeds to the keepalive/city fetch instead of showing the dialog.
WiFi (type 1 → 1) and other networks (→ 2) are unchanged.

## Build & sign
- Source tree: `analyze/client-apk-src` (its `lib/armeabi/libcity_ar.so` SHA `18d15117…`
  matches the working build — same IP/CheckUpdate/gettopmsgs/frida patches).
- `java -jar analyze/frida-gadget/apktool.jar b analyze/client-apk-src -o ...unsigned.apk`
  (apktool 2.10.0)
- `java -jar analyze/client-apk-src/uber-apk-signer.jar -a ...unsigned.apk`
  (debug key; v1+v2+v3 signatures)

## Output
- **`client/waker-reachpatch-signed.apk`** (89.3 MiB) — SHA256 `d72961513706b422…`
- Verified: the built classes.dex contains `:cond_2 / const/4 v1, 0x1`.

## Install (signature differs from the previous APK → uninstall first)
```bash
adb uninstall com.anansimobile.city_ar
adb install -r client/waker-reachpatch-signed.apk
adb shell pm clear com.anansimobile.city_ar      # fresh = direct-login path
adb shell am start -n com.anansimobile.city_ar/.Main
```
Then watch the server log — after `/api/connect` you should now see `/city/impart` instead
of the "Not connected" dialog.

> Note: the `client-apk-src/` tree is gitignored, so this `.md` is the tracked record of the
> patch. Re-apply the one-line smali change + rebuild to reproduce.
