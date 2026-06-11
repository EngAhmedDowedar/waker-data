/**
 * Waker - State-machine probe + synthetic 0x1773 injector
 *
 *  1. Suppresses NGDevice.launchUrl (no Intent fires).
 *  2. Hooks Handler.sendMessage / dispatchMessage globally — full message trace.
 *  3. Auto-injects a synthetic UI_MSG_CHECK_ASSETS_DONE (0x1773) message after:
 *        - launchUrl suppression (delay: 100ms)
 *        - any observed UI_MSG_CHECK_ASSETS_START (0x1771)
 *  4. Hooks NGHttpSession.doPut to detect /server_list appearance.
 *  5. Tags every message in the 500ms post-suppression window with delta-ms.
 *
 * Usage (attach mode, Houdini-safe):
 *   adb shell am force-stop com.anansimobile.city_ar
 *   # manually launch the app on emulator
 *   frida-ps -Uai | findstr city
 *   frida -U -p <PID> -l tools/frida_state_machine.js | tee state_trace.log
 */

"use strict";

var TAG = "[SM]";

// ---- state ----
var SUPPRESSION_TS = 0;
var WINDOW_MS      = 500;
var GAME_HANDLER   = null;     // cached NGMsgHandler instance
var INJECTED_AFTER_1771   = false;
var INJECTED_AFTER_SUPPR  = false;
var SERVER_LIST_SEEN      = false;
var FIRST_HTTP_AFTER_SUPPR = null;

var WHAT_NAMES = {
    0x3e9:  'UI_MSG_VIEW_LAYOUT',
    0x3ea:  'UI_MSG_VIEW_APPEND',
    0x3eb:  'UI_MSG_VIEW_REMOVE',
    0x3ec:  'UI_MSG_VIEW_VISIBLE',
    0x44f:  'UI_MSG_OPEN_URL',
    0x1388: 'UI_MSG_TOAST',
    0x1771: 'UI_MSG_CHECK_ASSETS_START',
    0x1772: 'UI_MSG_CHECK_ASSETS_PROGRESS',
    0x1773: 'UI_MSG_CHECK_ASSETS_DONE',
    0x177a: 'UI_MSG_COMFIRM_QUIT_GAME',
    0x1784: 'UI_ASK_PERMISSION_CONFIRM'
};

function ts() {
    var d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" +
           ("0" + d.getMinutes()).slice(-2) + ":" +
           ("0" + d.getSeconds()).slice(-2) + "." +
           ("00" + d.getMilliseconds()).slice(-3);
}

function log(m) { console.log(TAG + " " + ts() + " " + m); }

function whatName(w) {
    return WHAT_NAMES[w] ? ("0x" + w.toString(16) + " " + WHAT_NAMES[w])
                          : ("0x" + w.toString(16) + " ?");
}

function inWindow() {
    return SUPPRESSION_TS !== 0 && (Date.now() - SUPPRESSION_TS) <= WINDOW_MS;
}

function tag() {
    if (SUPPRESSION_TS === 0) return "";
    return "[POST-SUPPR " + (Date.now() - SUPPRESSION_TS) + "ms]";
}

function stackTrace() {
    try {
        var Ex = Java.use("java.lang.Exception");
        var L  = Java.use("android.util.Log");
        return L.getStackTraceString(Ex.$new());
    } catch (e) { return "<stack-err " + e + ">"; }
}

function dumpBundle(b) {
    if (!b) return "{}";
    try {
        var keys = b.keySet().toArray();
        var parts = [];
        for (var i = 0; i < keys.length; i++) {
            var k = "" + keys[i];
            var v;
            try { v = "" + b.get(k); } catch (e) { v = "?"; }
            parts.push(k + "=" + v);
        }
        return "{" + parts.join(", ") + "}";
    } catch (e) { return "<bundle-err " + e + ">"; }
}

function injectAssetsDone(reason) {
    if (!GAME_HANDLER) {
        log("[INJECT] !! cannot post 0x1773 — NGMsgHandler not yet captured (reason=" + reason + ")");
        return false;
    }
    try {
        var Message = Java.use("android.os.Message");
        var msg = Message.obtain();
        msg.what.value = 0x1773;
        log("[INJECT] >>> POSTING SYNTHETIC 0x1773 UI_MSG_CHECK_ASSETS_DONE (reason=" + reason + ")");
        GAME_HANDLER.sendMessage(msg);
        return true;
    } catch (e) {
        log("[INJECT] !! failed: " + e);
        return false;
    }
}

function scheduleInject(reason, delayMs) {
    setTimeout(function() {
        Java.perform(function() { injectAssetsDone(reason); });
    }, delayMs);
}

Java.perform(function() {
    log("============================================");
    log(" State-machine probe + 0x1773 injector live");
    log("============================================");

    // ---- 0. Pre-capture any existing NGMsgHandler instance ----
    try {
        Java.choose("com.anansimobile.nge.NGMsgHandler", {
            onMatch: function(inst) {
                if (!GAME_HANDLER) {
                    GAME_HANDLER = Java.retain(inst);
                    log("[CACHE] Found existing NGMsgHandler via Java.choose");
                }
            },
            onComplete: function() {
                log("[CACHE] Java.choose scan complete; handler=" + (GAME_HANDLER ? "captured" : "NOT YET"));
            }
        });
    } catch (e) {
        log("[CACHE] Java.choose failed: " + e);
    }

    // Also hook the constructor in case it gets created after we attach
    try {
        var NGMsgHandler = Java.use("com.anansimobile.nge.NGMsgHandler");
        NGMsgHandler.$init.implementation = function() {
            this.$init();
            if (!GAME_HANDLER) {
                GAME_HANDLER = Java.retain(this);
                log("[CACHE] Captured NGMsgHandler via constructor hook");
            }
        };
    } catch (e) {
        log("[CACHE] NGMsgHandler ctor hook failed: " + e);
    }

    // ---- 1. Suppress launchUrl ----
    try {
        var NGDevice = Java.use("com.anansimobile.nge.NGDevice");
        NGDevice.launchUrl.overloads.forEach(function(ov) {
            ov.implementation = function() {
                SUPPRESSION_TS = Date.now();
                log("==============================");
                log(">>> NGDevice.launchUrl  *** SUPPRESSED *** T0 set");
                for (var i = 0; i < arguments.length; i++) {
                    log("    arg[" + i + "]: " + arguments[i]);
                }
                log("    --- native caller stack ---");
                log(stackTrace());
                log("==============================");
                // Schedule synthetic 0x1773 ~100ms after suppression
                if (!INJECTED_AFTER_SUPPR) {
                    INJECTED_AFTER_SUPPR = true;
                    scheduleInject("post-launchUrl-suppression", 100);
                }
                return;
            };
        });
        log("[+] NGDevice.launchUrl suppression installed");
    } catch (e) {
        log("[!] launchUrl hook failed: " + e);
    }

    // ---- 2. Handler.sendMessage / sendMessageAtTime / dispatchMessage ----
    try {
        var Handler = Java.use("android.os.Handler");

        Handler.sendMessageAtTime.implementation = function(msg, uptime) {
            var w = -1, b = null, hcls = "?";
            try { w = msg.what.value; } catch (e) {}
            try { b = msg.peekData(); } catch (e) {}
            try { hcls = this.getClass().getName(); } catch (e) {}

            // Cache NGMsgHandler instance opportunistically
            if (!GAME_HANDLER && hcls.indexOf("NGMsgHandler") !== -1) {
                GAME_HANDLER = Java.retain(this);
                log("[CACHE] Captured NGMsgHandler via sendMessage observation");
            }

            log("[MSG SEND] " + whatName(w) + "  handler=" + hcls +
                "  bundle=" + dumpBundle(b) + "  " + tag());

            // Auto-inject 0x1773 after first 0x1771
            if (w === 0x1771 && !INJECTED_AFTER_1771) {
                INJECTED_AFTER_1771 = true;
                scheduleInject("post-0x1771-START", 50);
            }

            return this.sendMessageAtTime(msg, uptime);
        };

        Handler.dispatchMessage.implementation = function(msg) {
            var w = -1, hcls = "?";
            try { w = msg.what.value; } catch (e) {}
            try { hcls = this.getClass().getName(); } catch (e) {}
            log("[MSG RECV] " + whatName(w) + "  handler=" + hcls + "  " + tag());
            return this.dispatchMessage(msg);
        };

        log("[+] Handler.sendMessageAtTime + dispatchMessage hooks installed");
    } catch (e) {
        log("[!] Handler hooks failed: " + e);
    }

    // ---- 3. HTTP egress trace via NGHttpSession.doPut ----
    // Native code calls this static Java method for every PUT it makes (it's a
    // logging trampoline — the real curl call is native). Catching this is the
    // cleanest way to see /server_list (or any next endpoint) without watching
    // the server log file.
    try {
        var Session = Java.use("com.anansimobile.nge.NGHttpSession");
        Session.doPut.implementation = function(url, data, l) {
            var len = data ? data.length : 0;
            var t = tag();
            log("[HTTP PUT] url=" + url + "  body_len=" + len + "  " + t);

            if (SUPPRESSION_TS !== 0 && FIRST_HTTP_AFTER_SUPPR === null) {
                FIRST_HTTP_AFTER_SUPPR = url;
                log("[HTTP] *** FIRST HTTP AFTER SUPPRESSION: " + url + " (" +
                    (Date.now() - SUPPRESSION_TS) + "ms after suppress) ***");
            }
            if (url && url.indexOf("/server_list") !== -1) {
                SERVER_LIST_SEEN = true;
                log("[HTTP] *** /server_list OBSERVED — BOOT ADVANCED ***");
            }
            return this.doPut(url, data, l);
        };
        log("[+] NGHttpSession.doPut hook installed (HTTP-egress trace)");
    } catch (e) {
        log("[!] NGHttpSession.doPut hook failed: " + e);
    }

    // ---- 4. Heartbeat status print every 2s ----
    setInterval(function() {
        if (SUPPRESSION_TS === 0) return;
        var dt = Date.now() - SUPPRESSION_TS;
        log("[STATUS] " + dt + "ms since suppression  " +
            "inject_after_1771=" + INJECTED_AFTER_1771 +
            "  inject_after_suppr=" + INJECTED_AFTER_SUPPR +
            "  first_http=" + (FIRST_HTTP_AFTER_SUPPR || "<none>") +
            "  server_list_seen=" + SERVER_LIST_SEEN);
    }, 2000);

    log("============================================");
    log(" Hooks live. Trigger boot now.");
    log("============================================");
});
