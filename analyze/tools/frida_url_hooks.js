/**
 * Waker - Frida URL-launch tracer
 *
 * Captures every code path the game uses to launch a URL or intent after
 * receiving a server response. Pairs with /checkversion probe variants in
 * local-server/python/server.py to reconstruct the semantic response schema.
 *
 * Targets (Java layer — Houdini-compatible):
 *   - com.anansimobile.nge.NGDevice.launchUrl(String)
 *       static; the "needUpdate" path (Intent.ACTION_VIEW → Play Store)
 *   - com.anansimobile.nge.RootActivity.openUrl(int ptr, String url)
 *       instance; UI handler message what=0x44f (in-game WebView launch)
 *   - android.content.Intent.setData / setDataAndType
 *   - android.content.Context.startActivity (catch-all for any URL we missed)
 *   - android.net.Uri.parse (catch-all for URL parsing)
 *
 * Usage:
 *   frida -U -f com.anansimobile.city_ar -l frida_url_hooks.js --no-pause
 *   (or attach: frida -U -p <PID> -l frida_url_hooks.js)
 */

"use strict";

var TAG = "[URL]";

// ---- State-machine trace state ----
var SUPPRESSION_TS = 0;      // ms epoch when launchUrl was last suppressed
var WINDOW_MS      = 500;    // post-suppression window during which to flag messages

// NGMsgHandler what-value names (from NGMsgHandler.smali static fields)
var WHAT_NAMES = {
    0x3e9:  'UI_MSG_VIEW_LAYOUT',
    0x3ea:  'UI_MSG_VIEW_APPEND',
    0x3eb:  'UI_MSG_VIEW_REMOVE',
    0x3ec:  'UI_MSG_VIEW_VISIBLE',
    0x44f:  'UI_MSG_OPEN_URL (WebView load)',
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

function log(msg) {
    console.log(TAG + " " + ts() + " " + msg);
}

function inPostSuppressionWindow() {
    if (SUPPRESSION_TS === 0) return false;
    return (Date.now() - SUPPRESSION_TS) <= WINDOW_MS;
}

function tag() {
    return inPostSuppressionWindow() ? "[POST-SUPPRESS " + (Date.now() - SUPPRESSION_TS) + "ms]" : "";
}

function whatName(w) {
    var n = WHAT_NAMES[w] || WHAT_NAMES[w & 0xFFFFFFFF];
    return n ? ("0x" + w.toString(16) + " " + n) : ("0x" + w.toString(16) + " UNKNOWN");
}

function dumpBundle(bundle) {
    if (!bundle) return "<no bundle>";
    try {
        var keys = bundle.keySet().toArray();
        var parts = [];
        for (var i = 0; i < keys.length; i++) {
            var k = "" + keys[i];
            var v;
            try { v = "" + bundle.get(k); } catch (e) { v = "?"; }
            parts.push(k + "=" + v);
        }
        return "{" + parts.join(", ") + "}";
    } catch (e) {
        return "<bundle-err: " + e + ">";
    }
}

function stackTrace() {
    try {
        var Exception = Java.use("java.lang.Exception");
        var Log = Java.use("android.util.Log");
        return Log.getStackTraceString(Exception.$new());
    } catch (e) {
        return "<stack trace unavailable: " + e + ">";
    }
}

function divider() {
    log("==============================");
}

Java.perform(function() {
    log("============================================");
    log("  URL-launch tracer (Houdini-compatible)");
    log("============================================");

    // ---- NGDevice.launchUrl(String) — BLOCKED + traced ----
    // Override: log arg + stack trace, mark suppression timestamp, RETURN.
    // The 500ms window after this is the gate-discovery window.
    try {
        var NGDevice = Java.use("com.anansimobile.nge.NGDevice");
        var overloads = NGDevice.launchUrl.overloads;
        log("NGDevice.launchUrl overloads: " + overloads.length);
        overloads.forEach(function(ov) {
            ov.implementation = function() {
                SUPPRESSION_TS = Date.now();
                divider();
                log(">>> NGDevice.launchUrl  *** SUPPRESSED ***  T0 mark set");
                for (var i = 0; i < arguments.length; i++) {
                    log("    arg[" + i + "]: " + arguments[i]);
                }
                log("    --- stack (identifies native caller) ---");
                log(stackTrace());
                divider();
                log("    Watching message bus for " + WINDOW_MS + "ms ...");
                return;
            };
        });
        log("[+] NGDevice.launchUrl SUPPRESSION hook installed");
    } catch (e) {
        log("[!] NGDevice.launchUrl hook failed: " + e);
    }

    // ---- GLOBAL Handler message bus trace ----
    // Captures EVERY Handler.sendMessage/sendMessageAtTime AND every
    // Handler.dispatchMessage. The post-suppression window tag tells us
    // whether a state-machine event is fired after the update routing.
    try {
        var Handler = Java.use("android.os.Handler");

        Handler.sendMessageAtTime.implementation = function(msg, uptimeMillis) {
            try {
                var w = msg.what.value;
                var b = null;
                try { b = msg.peekData(); } catch (e) {}
                var post = tag();
                log("[MSG SEND] " + whatName(w) +
                    "  handler=" + this.getClass().getName() +
                    "  bundle=" + dumpBundle(b) +
                    "  " + post);
            } catch (e) {
                log("[MSG SEND] (decode err: " + e + ")");
            }
            return this.sendMessageAtTime(msg, uptimeMillis);
        };

        Handler.dispatchMessage.implementation = function(msg) {
            try {
                var w = msg.what.value;
                var b = null;
                try { b = msg.peekData(); } catch (e) {}
                var post = tag();
                log("[MSG RECV] " + whatName(w) +
                    "  handler=" + this.getClass().getName() +
                    "  bundle=" + dumpBundle(b) +
                    "  " + post);
            } catch (e) {
                log("[MSG RECV] (decode err: " + e + ")");
            }
            return this.dispatchMessage(msg);
        };

        log("[+] Global Handler.sendMessageAtTime + dispatchMessage hooks installed");
    } catch (e) {
        log("[!] Handler hooks failed: " + e);
    }

    // ---- Capture any NEW native->Java JNI calls in the suppression window ----
    // ngReachability network-status changes, FCM, Web view load, etc. — any
    // of these could be the gate the native state machine waits on.
    try {
        var NGReach = Java.use("com.anansimobile.nge.NGReachability");
        NGReach.onNetworkStatusChange.overloads.forEach(function(ov) {
            ov.implementation = function() {
                log("[JNI<-] NGReachability.onNetworkStatusChange  " + Array.prototype.slice.call(arguments) + "  " + tag());
                return ov.apply(this, arguments);
            };
        });
    } catch (e) {}

    try {
        var WebViewListener = Java.use("com.anansimobile.nge.NGWebView");
        // Hook common lifecycle methods if present
        ['onPageStarted','onPageFinished','onReceivedError','loadUrl'].forEach(function(mn) {
            try {
                if (WebViewListener[mn]) {
                    WebViewListener[mn].overloads.forEach(function(ov) {
                        ov.implementation = function() {
                            log("[NGWebView." + mn + "] " + Array.prototype.slice.call(arguments) + "  " + tag());
                            return ov.apply(this, arguments);
                        };
                    });
                }
            } catch (e) {}
        });
    } catch (e) {}

    // ---- RootActivity.openUrl(int, String) — BLOCKED + traced ----
    try {
        var RootActivity = Java.use("com.anansimobile.nge.RootActivity");
        var ovs = RootActivity.openUrl.overloads;
        log("RootActivity.openUrl overloads: " + ovs.length);
        ovs.forEach(function(ov) {
            ov.implementation = function() {
                divider();
                log(">>> RootActivity.openUrl  *** SUPPRESSED ***");
                for (var i = 0; i < arguments.length; i++) {
                    log("    arg[" + i + "]: " + arguments[i]);
                }
                log("    --- stack ---");
                log(stackTrace());
                divider();
                return;
            };
        });
        log("[+] RootActivity.openUrl SUPPRESSION hook installed");
    } catch (e) {
        log("[!] RootActivity.openUrl hook failed: " + e);
    }

    // ---- Intent.setData / setDataAndType ----
    try {
        var Intent = Java.use("android.content.Intent");
        Intent.setData.overload("android.net.Uri").implementation = function(uri) {
            log("[Intent.setData] uri=" + uri + " action=" + this.getAction());
            return this.setData(uri);
        };
        Intent.setDataAndType.overload("android.net.Uri", "java.lang.String").implementation = function(uri, type) {
            log("[Intent.setDataAndType] uri=" + uri + " type=" + type);
            return this.setDataAndType(uri, type);
        };
        log("[+] Intent.setData/setDataAndType hooks installed");
    } catch (e) {
        log("[!] Intent.setData hook failed: " + e);
    }

    // ---- Context.startActivity (catch-all for any URL we missed) ----
    try {
        var Activity = Java.use("android.app.Activity");
        Activity.startActivity.overload("android.content.Intent").implementation = function(intent) {
            var action = "";
            var data = "";
            try { action = "" + intent.getAction(); } catch (e2) {}
            try { data = "" + intent.getDataString(); } catch (e2) {}
            if (action.indexOf("VIEW") !== -1 || data.indexOf("http") !== -1 ||
                data.indexOf("market://") !== -1 || data.indexOf("play.google") !== -1) {
                divider();
                log(">>> Activity.startActivity (URL-launch)");
                log("    action: " + action);
                log("    data:   " + data);
                log("    --- stack ---");
                log(stackTrace());
                divider();
            }
            return this.startActivity(intent);
        };
        log("[+] Activity.startActivity hook installed");
    } catch (e) {
        log("[!] Activity.startActivity hook failed: " + e);
    }

    // ---- Uri.parse (catch every URL the game touches) ----
    try {
        var Uri = Java.use("android.net.Uri");
        Uri.parse.overload("java.lang.String").implementation = function(s) {
            if (s && (s.indexOf("http") === 0 || s.indexOf("market://") === 0 ||
                      s.indexOf("intent://") === 0 || s.indexOf("anansi") !== -1)) {
                log("[Uri.parse] " + s);
            }
            return this.parse(s);
        };
        log("[+] Uri.parse hook installed");
    } catch (e) {
        log("[!] Uri.parse hook failed: " + e);
    }

    // ---- RootActivity.intentFilter (called by launchUrl before startActivity) ----
    try {
        var RootActivity2 = Java.use("com.anansimobile.nge.RootActivity");
        if (RootActivity2.intentFilter) {
            RootActivity2.intentFilter.overloads.forEach(function(ov) {
                ov.implementation = function(intent) {
                    var data = "", action = "";
                    try { action = "" + intent.getAction(); } catch (e2) {}
                    try { data = "" + intent.getDataString(); } catch (e2) {}
                    log("[intentFilter] action=" + action + " data=" + data);
                    return ov.apply(this, arguments);
                };
            });
            log("[+] RootActivity.intentFilter hook installed");
        }
    } catch (e) {
        log("[!] intentFilter hook: " + e);
    }

    log("============================================");
    log("  Hooks active. Run /checkversion probe and trigger boot.");
    log("============================================");
});
