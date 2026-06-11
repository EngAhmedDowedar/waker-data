/**
 * Waker (وكر الاوغاد) - Frida Java-Layer Hook Script
 *
 * Works on x86 emulators with Houdini/NativeBridge (where native ARM hooks fail).
 * Hooks the Java/JNI boundary to capture HTTP requests, responses, and logging.
 *
 * Targets:
 *   - NGHttpSession.doPut()         → HTTP request URL + body
 *   - NextGenEngine.nge_log()       → Native engine log output
 *   - NextGenEngine.nge_logf()      → Formatted native log
 *   - URL/HttpURLConnection         → Any Java-layer HTTP (fallback)
 *   - System.loadLibrary            → Track native lib loading
 *   - android.util.Log              → All logcat from game process
 *
 * Usage:
 *   frida -U -p <PID> -l frida_java_hooks.js
 *   frida -U -f com.anansimobile.city_ar -l frida_java_hooks.js --no-pause
 */

"use strict";

var TAG = "[JAVA-DUMP]";
var MAX_STR = 4096;

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

function byteArrayToString(arr) {
    if (!arr) return "<null>";
    try {
        var len = arr.length;
        if (len === 0) return "<empty>";
        var s = "";
        for (var i = 0; i < Math.min(len, MAX_STR); i++) {
            var b = arr[i] & 0xff;
            if (b >= 32 && b < 127) {
                s += String.fromCharCode(b);
            } else {
                s += "\\x" + (b < 16 ? "0" : "") + b.toString(16);
            }
        }
        if (len > MAX_STR) s += "...(" + len + " total)";
        return s;
    } catch (e) {
        return "<error: " + e + ">";
    }
}

function byteArrayToHex(arr, maxBytes) {
    if (!arr) return "<null>";
    try {
        var len = arr.length;
        var max = maxBytes || 128;
        var hex = "";
        for (var i = 0; i < Math.min(len, max); i++) {
            var b = (arr[i] & 0xff).toString(16);
            hex += (b.length < 2 ? "0" : "") + b + " ";
        }
        if (len > max) hex += "... (" + len + " total)";
        return hex.trim();
    } catch (e) {
        return "<error: " + e + ">";
    }
}

Java.perform(function() {
    log("============================================");
    log("  Waker Java-Layer Protocol Dump");
    log("  (Houdini/x86-compatible)");
    log("============================================");

    // =========================================================================
    // 1. NGHttpSession.doPut() - Main HTTP request interception
    // =========================================================================
    try {
        var NGHttpSession = Java.use("com.anansimobile.nge.NGHttpSession");

        NGHttpSession.doPut.implementation = function(url, data, l) {
            log(">>> NGHttpSession.doPut()");
            log("    URL:  " + url);
            log("    Long: " + l);
            if (data) {
                log("    Body (" + data.length + " bytes): " + byteArrayToString(data));
                if (data.length < 256) {
                    log("    Hex:  " + byteArrayToHex(data));
                }
            } else {
                log("    Body: <null>");
            }
            log("---");

            // Call original
            this.doPut(url, data, l);
        };
        log("✓ Hooked NGHttpSession.doPut");
    } catch (e) {
        log("✗ NGHttpSession.doPut: " + e);
    }

    // =========================================================================
    // 2. NextGenEngine.nge_log() - Native engine logging
    // =========================================================================
    try {
        var NGE = Java.use("com.anansimobile.nge.NextGenEngine");

        NGE.nge_log.implementation = function(logStr) {
            log("[NGE_LOG] " + logStr);
            this.nge_log(logStr);
        };
        log("✓ Hooked NextGenEngine.nge_log");
    } catch (e) {
        log("✗ NextGenEngine.nge_log: " + e);
    }

    // Try nge_logf
    try {
        var NGE2 = Java.use("com.anansimobile.nge.NextGenEngine");
        NGE2.nge_logf.implementation = function(fmt, args) {
            var msg = "" + fmt;
            if (args) {
                for (var i = 0; i < args.length; i++) {
                    msg += " " + args[i];
                }
            }
            log("[NGE_LOGF] " + msg);
            this.nge_logf(fmt, args);
        };
        log("✓ Hooked NextGenEngine.nge_logf");
    } catch (e) {
        log("  (nge_logf not found or already hooked)");
    }

    // =========================================================================
    // 3. System.loadLibrary - Track native lib loading
    // =========================================================================
    try {
        var System = Java.use("java.lang.System");
        System.loadLibrary.implementation = function(lib) {
            log("[LOAD] System.loadLibrary(\"" + lib + "\")");
            this.loadLibrary(lib);
        };
        log("✓ Hooked System.loadLibrary");
    } catch (e) {
        log("✗ System.loadLibrary: " + e);
    }

    // =========================================================================
    // 4. android.util.Log - Capture logcat from game
    // =========================================================================
    try {
        var Log = Java.use("android.util.Log");

        Log.d.overload("java.lang.String", "java.lang.String").implementation = function(tag, msg) {
            if (tag && (tag.toString().indexOf("nge") !== -1 ||
                        tag.toString().indexOf("city") !== -1 ||
                        tag.toString().indexOf("anansi") !== -1 ||
                        tag.toString().indexOf("NGE") !== -1)) {
                log("[LOG.d] " + tag + ": " + msg);
            }
            return this.d(tag, msg);
        };

        Log.i.overload("java.lang.String", "java.lang.String").implementation = function(tag, msg) {
            if (tag && (tag.toString().indexOf("nge") !== -1 ||
                        tag.toString().indexOf("city") !== -1 ||
                        tag.toString().indexOf("anansi") !== -1 ||
                        tag.toString().indexOf("NGE") !== -1)) {
                log("[LOG.i] " + tag + ": " + msg);
            }
            return this.i(tag, msg);
        };

        Log.e.overload("java.lang.String", "java.lang.String").implementation = function(tag, msg) {
            log("[LOG.e] " + tag + ": " + msg);
            return this.e(tag, msg);
        };

        log("✓ Hooked android.util.Log (d/i/e) with game filter");
    } catch (e) {
        log("✗ android.util.Log: " + e);
    }

    // =========================================================================
    // 5. RootActivity / Main class hooks
    // =========================================================================
    try {
        var Main = Java.use("com.anansimobile.city_ar.Main");
        // List all declared methods for discovery
        var methods = Main.class.getDeclaredMethods();
        log("Main class methods (" + methods.length + "):");
        for (var i = 0; i < methods.length; i++) {
            log("  " + methods[i].getName() + " - " + methods[i].toString());
        }
    } catch (e) {
        log("  Main class enumeration: " + e);
    }

    // =========================================================================
    // 6. URL / HttpURLConnection (if game uses any Java HTTP)
    // =========================================================================
    try {
        var URL = Java.use("java.net.URL");
        URL.openConnection.overload().implementation = function() {
            var urlStr = this.toString();
            log("[URL] openConnection: " + urlStr);
            return this.openConnection();
        };
        log("✓ Hooked java.net.URL.openConnection");
    } catch (e) {
        log("  URL.openConnection: " + e);
    }

    // =========================================================================
    // 7. Hook all methods in NGHttpSession for discovery
    // =========================================================================
    try {
        var cls = Java.use("com.anansimobile.nge.NGHttpSession");
        var methods = cls.class.getDeclaredMethods();
        log("NGHttpSession methods (" + methods.length + "):");
        for (var m = 0; m < methods.length; m++) {
            log("  " + methods[m].toString());
        }
    } catch (e) {
        log("  NGHttpSession enumeration: " + e);
    }

    // =========================================================================
    // 8. Hook NextGenEngine for all native method declarations
    // =========================================================================
    try {
        var ngeCls = Java.use("com.anansimobile.nge.NextGenEngine");
        var ngeMethods = ngeCls.class.getDeclaredMethods();
        log("NextGenEngine methods (" + ngeMethods.length + "):");
        for (var n = 0; n < ngeMethods.length; n++) {
            log("  " + ngeMethods[n].toString());
        }
    } catch (e) {
        log("  NextGenEngine enumeration: " + e);
    }

    // =========================================================================
    // 9. SharedPreferences - capture stored tokens/session data
    // =========================================================================
    try {
        var SP = Java.use("android.app.SharedPreferencesImpl$EditorImpl");
        SP.putString.implementation = function(key, value) {
            if (key) {
                var k = key.toString().toLowerCase();
                if (k.indexOf("token") !== -1 || k.indexOf("session") !== -1 ||
                    k.indexOf("player") !== -1 || k.indexOf("server") !== -1 ||
                    k.indexOf("user") !== -1 || k.indexOf("login") !== -1) {
                    log("[PREFS] putString(\"" + key + "\", \"" + value + "\")");
                }
            }
            return this.putString(key, value);
        };
        log("✓ Hooked SharedPreferences.putString (filtered)");
    } catch (e) {
        log("  SharedPreferences: " + e);
    }

    // =========================================================================
    // 10. NGDevice.launchUrl(String) - selectively suppress empty-URL calls
    // =========================================================================
    //
    // Behavior:
    //   - empty-string URL  -> log + SUPPRESS (do NOT invoke original).
    //     The Java NGDevice.launchUrl implementation builds an Intent.ACTION_VIEW
    //     from Uri.parse(arg); on "" this throws / fails inside the OS layer.
    //     Skipping the call short-circuits that crash without altering the
    //     decision logic on the C++ side.
    //   - any non-empty URL -> log + PASS-THROUGH unchanged.
    //     We do not modify, sanitize, or default the URL. A live non-empty URL
    //     is exactly the evidence we want to see in this experiment.
    //   - the URL is taken as the FIRST java.lang.String argument of whichever
    //     overload fired; non-String overloads (if any) are passed through.
    //
    // Goal: determine whether the boot proceeds past CheckUpdate once the
    // empty-Intent side effect is removed. We only intervene on the specific
    // failing input shape — every other code path is preserved.
    try {
        var NGDevice = Java.use("com.anansimobile.nge.NGDevice");
        var devMethods = NGDevice.class.getDeclaredMethods();
        log("NGDevice methods (" + devMethods.length + "):");
        for (var d = 0; d < devMethods.length; d++) {
            log("  " + devMethods[d].toString());
        }

        var STRING_CLASS = "java.lang.String";

        function emptyArgIndex(argTypes, argv) {
            // Return index of the first java.lang.String arg whose value is the
            // empty string. -1 if no such arg exists.
            for (var i = 0; i < argTypes.length; i++) {
                if (argTypes[i] && argTypes[i].className === STRING_CLASS) {
                    var v = argv[i];
                    if (v !== null && v !== undefined) {
                        var s = ("" + v);
                        if (s.length === 0) return i;
                    }
                }
            }
            return -1;
        }

        function defaultReturnFor(retClassName) {
            // Best-effort default when we suppress the call.
            // Most launchUrl variants are void; we cover the common cases.
            switch (retClassName) {
                case "void":     return undefined;
                case "boolean":  return false;
                case "int":
                case "long":
                case "short":
                case "byte":
                case "float":
                case "double":   return 0;
                default:         return null;  // any reference type
            }
        }

        var launchUrlOverloads = NGDevice.launchUrl.overloads;
        if (!launchUrlOverloads || launchUrlOverloads.length === 0) {
            log("✗ NGDevice.launchUrl: no overloads visible (method may be lazy-loaded)");
        } else {
            log("Hooking " + launchUrlOverloads.length + " overload(s) of NGDevice.launchUrl:");
            launchUrlOverloads.forEach(function(ov, idx) {
                var argTypes = [];
                try { argTypes = ov.argumentTypes || []; } catch (e) {}
                var sig = argTypes.map(function(t) { return t && t.className; }).join(",");
                var retName = (ov.returnType && ov.returnType.className) || "?";
                log("  [" + idx + "] launchUrl(" + sig + ")  ret=" + retName);

                ov.implementation = function() {
                    var argv = [];
                    for (var i = 0; i < arguments.length; i++) argv.push(arguments[i]);
                    var rendered = argv.map(function(a) {
                        if (a === null || a === undefined) return "<null>";
                        if (typeof a === "string" || a instanceof String) return JSON.stringify("" + a);
                        return ("" + a);
                    });

                    var emptyIdx = emptyArgIndex(argTypes, argv);
                    var isEmpty = emptyIdx !== -1;

                    log("=================================================");
                    log(">>> NGDevice.launchUrl() " +
                        (isEmpty ? "EMPTY-URL  (SUPPRESSED)" : "FIRED  (pass-through)") +
                        "  overload " + idx);
                    log("    signature: (" + sig + ") ret=" + retName);
                    log("    args:      [" + rendered.join(", ") + "]");
                    if (isEmpty) {
                        log("    suppress reason: arg[" + emptyIdx + "] is empty String");
                    }
                    try {
                        var Throwable = Java.use("java.lang.Throwable");
                        var LogJ = Java.use("android.util.Log");
                        var t = Throwable.$new();
                        var stack = LogJ.getStackTraceString(t);
                        log("    Java stack:");
                        var lines = stack.split("\n");
                        for (var k = 0; k < lines.length && k < 40; k++) log("      " + lines[k]);
                    } catch (se) {
                        log("    (stack capture failed: " + se + ")");
                    }
                    // Cross-script trigger: if frida_native_aborts.js installed
                    // the native ring buffer (libcity_ar.so dispatcher trace),
                    // dump it now. This identifies the native dispatcher that
                    // just invoked Java launchUrl with an empty string.
                    try {
                        if (typeof globalThis.__waker_dump_native_ring === "function") {
                            globalThis.__waker_dump_native_ring(
                                "launchUrl_" + (isEmpty ? "EMPTY" : "nonempty") + "_ov" + idx);
                        } else {
                            log("    (native ring dump not available — load frida_native_aborts.js)");
                        }
                    } catch (re) {
                        log("    (native ring dump err: " + re + ")");
                    }
                    log("=================================================");

                    if (isEmpty) {
                        // Suppress: do NOT invoke original. Return type-appropriate default.
                        return defaultReturnFor(retName);
                    }
                    // Non-empty: pass through unchanged.
                    return ov.apply(this, arguments);
                };
            });
            log("✓ NGDevice.launchUrl hooks installed (suppress-on-empty, pass-through otherwise)");
        }
    } catch (e) {
        log("✗ NGDevice.launchUrl: " + e);
    }

    log("============================================");
    log("  Java hooks active. Monitoring...");
    log("============================================");
});
