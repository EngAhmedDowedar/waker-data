/**
 * Waker (وكر الاوغاد) - Frida Protocol Dump Script
 *
 * Hooks key functions in libcity_ar.so to dump plaintext requests/responses
 * BEFORE encryption and AFTER decryption, fully recovering the game protocol.
 *
 * Target functions (C++ mangled names resolved by symbol scan):
 *   - CMsgCodec::EnCode*        → outgoing message before encryption
 *   - CMsgCodec::GetJsonData*   → incoming JSON after decryption
 *   - ngHttpClient::PutURL      → HTTP PUT with URL + body
 *   - ngHttpSession::OnResponse → HTTP response callback
 *   - curl_easy_setopt          → libcurl URL/POST/header config
 *   - ngRC4Mnger::EncryptKpAliveData → TCP plaintext before RC4
 *   - ngRC4Mnger::DecryptKpAliveData → TCP plaintext after RC4
 *
 * Usage:
 *   frida -U -f com.anansimobile.city_ar -l frida_dump.js --no-pause
 *   frida -U com.anansimobile.city_ar -l frida_dump.js
 *
 * Log output goes to Frida console. Use  frida ... | tee dump.log  to save.
 */

"use strict";

// ============================================================================
// CONFIG
// ============================================================================

var LIB_NAME   = "libcity_ar.so";
var TAG        = "[DUMP]";
var MAX_HEXDUMP = 512;   // max bytes to hexdump per buffer
var MAX_STR     = 2048;  // max chars to print per string

// CURLOPT constants (from curl.h) used by curl_easy_setopt
var CURLOPT_URL            = 10002;  // CURLOPTTYPE_STRINGPOINT + 2
var CURLOPT_POSTFIELDS     = 10015;  // CURLOPTTYPE_STRINGPOINT + 15
var CURLOPT_HTTPHEADER     = 10023;  // CURLOPTTYPE_SLISTPOINT  + 23
var CURLOPT_WRITEFUNCTION  = 20011;  // CURLOPTTYPE_FUNCTIONPOINT + 11
var CURLOPT_WRITEDATA      = 10001;  // CURLOPTTYPE_OBJECTPOINT + 1
var CURLOPT_POST           = 47;     // CURLOPTTYPE_LONG + 47
var CURLOPT_CUSTOMREQUEST  = 10036;  // CURLOPTTYPE_STRINGPOINT + 36
var CURLOPT_USERAGENT      = 10018;

// ============================================================================
// HELPERS
// ============================================================================

function ts() {
    var d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" +
           ("0" + d.getMinutes()).slice(-2) + ":" +
           ("0" + d.getSeconds()).slice(-2) + "." +
           ("00" + d.getMilliseconds()).slice(-3);
}

function safeCStr(ptr) {
    if (ptr.isNull()) return "<null>";
    try {
        var s = ptr.readCString();
        if (s && s.length > MAX_STR) s = s.substring(0, MAX_STR) + "...";
        return s || "<empty>";
    } catch (e) {
        return "<unreadable@" + ptr + ">";
    }
}

function safeUtf8(ptr, len) {
    if (ptr.isNull()) return "<null>";
    try {
        if (len > 0) {
            return ptr.readUtf8String(len > MAX_STR ? MAX_STR : len);
        }
        return ptr.readUtf8String();
    } catch (e) {
        return "<unreadable@" + ptr + ">";
    }
}

function safeDump(ptr, size) {
    if (ptr.isNull()) return "<null ptr>";
    try {
        var n = Math.min(size, MAX_HEXDUMP);
        return hexdump(ptr, { length: n, ansi: false });
    } catch (e) {
        return "<hexdump failed: " + e + ">";
    }
}

function tryReadStdString(ptr) {
    // Attempt to read a C++ std::string (libstdc++ / libc++ layout).
    // Layout A (short-string-opt, libc++): first word is pointer or inline buffer.
    // Layout B (libstdc++): ptr to char* at offset 0.
    // We try the simplest approach: treat ptr as char** → deref → readCString.
    if (ptr.isNull()) return null;
    try {
        var inner = ptr.readPointer();
        if (inner.isNull()) return "";
        return inner.readCString();
    } catch (e) {
        // Might be SSO / inline buffer – try reading ptr itself as char*
        try { return ptr.readCString(); } catch (e2) { return null; }
    }
}

function log(msg) {
    console.log(TAG + " " + ts() + " " + msg);
}

// ============================================================================
// SYMBOL SCANNER
// ============================================================================

function findExportsBySubstring(mod, substr) {
    var results = [];
    var exports = mod.enumerateExports();
    for (var i = 0; i < exports.length; i++) {
        if (exports[i].name.indexOf(substr) !== -1) {
            results.push(exports[i]);
        }
    }
    return results;
}

function findSymbolsBySubstring(mod, substr) {
    var results = [];
    var syms = mod.enumerateSymbols();
    for (var i = 0; i < syms.length; i++) {
        if (syms[i].name.indexOf(substr) !== -1) {
            results.push(syms[i]);
        }
    }
    return results;
}

function findAll(mod, substr) {
    var found = findExportsBySubstring(mod, substr);
    if (found.length === 0) {
        found = findSymbolsBySubstring(mod, substr);
    }
    return found;
}

// ============================================================================
// HOOKS
// ============================================================================

function hookCMsgCodecEnCode(mod) {
    var matches = findAll(mod, "CMsgCodec");
    var encodeMatches = [];
    var jsonMatches = [];
    var allMatches = [];

    for (var i = 0; i < matches.length; i++) {
        allMatches.push(matches[i]);
        if (matches[i].name.indexOf("EnCode") !== -1) {
            encodeMatches.push(matches[i]);
        }
        if (matches[i].name.indexOf("GetJsonData") !== -1 ||
            matches[i].name.indexOf("getJsonData") !== -1) {
            jsonMatches.push(matches[i]);
        }
    }

    if (allMatches.length > 0) {
        log("CMsgCodec symbols found: " + allMatches.length);
        for (var j = 0; j < allMatches.length; j++) {
            log("  " + allMatches[j].name + " @ " + allMatches[j].address);
        }
    }

    // Hook EnCode variants
    encodeMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    this._name = sym.name;
                    // CMsgCodec::EnCode typically: this, buffer/data, length or string
                    // We dump the first few args
                    log(">>> " + sym.name + " CALLED (outgoing message)");
                    log("    this=" + args[0]);
                    log("    arg1=" + args[1]);
                    log("    arg2=" + args[2]);

                    // Try reading arg1 as a C string (URL or message)
                    var s1 = safeCStr(args[1]);
                    if (s1 && s1.length > 1 && s1.indexOf("<unreadable") === -1) {
                        log("    arg1 str: " + s1);
                    }
                    // Try reading arg2
                    if (!args[2].isNull()) {
                        var s2 = safeCStr(args[2]);
                        if (s2 && s2.length > 1 && s2.indexOf("<unreadable") === -1) {
                            log("    arg2 str: " + s2);
                        }
                    }
                },
                onLeave: function(retval) {
                    log("<<< " + this._name + " returned: " + retval);
                    // Try reading return as string (encoded message)
                    if (!retval.isNull()) {
                        var rs = safeCStr(retval);
                        if (rs && rs.length > 1 && rs.indexOf("<unreadable") === -1) {
                            log("    return str: " + rs);
                        }
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {
            log("  ✗ Failed to hook " + sym.name + ": " + e);
        }
    });

    // Hook GetJsonData variants
    jsonMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    this._name = sym.name;
                    log(">>> " + sym.name + " CALLED (incoming JSON)");
                    log("    this=" + args[0]);
                },
                onLeave: function(retval) {
                    log("<<< " + this._name + " returned: " + retval);
                    if (!retval.isNull()) {
                        // Return value may be a pointer to JSON string or std::string
                        var rs = safeCStr(retval);
                        if (rs && rs.length > 1 && rs.indexOf("<unreadable") === -1) {
                            log("    JSON: " + rs);
                        } else {
                            // Try reading as std::string
                            var ss = tryReadStdString(retval);
                            if (ss) log("    JSON (std::string): " + ss);
                        }
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {
            log("  ✗ Failed to hook " + sym.name + ": " + e);
        }
    });
}

function hookNgHttpClient(mod) {
    var matches = findAll(mod, "ngHttpClient");
    var putUrlMatches = [];

    for (var i = 0; i < matches.length; i++) {
        if (matches[i].name.indexOf("PutURL") !== -1 ||
            matches[i].name.indexOf("putURL") !== -1 ||
            matches[i].name.indexOf("PutUrl") !== -1) {
            putUrlMatches.push(matches[i]);
        }
    }

    if (matches.length > 0) {
        log("ngHttpClient symbols found: " + matches.length);
    }

    putUrlMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    this._name = sym.name;
                    // ngHttpClient::PutURL(this, url, data, len, ...)
                    log(">>> " + sym.name + " (HTTP request)");
                    log("    this=" + args[0]);

                    var url = safeCStr(args[1]);
                    log("    URL: " + url);

                    // arg2 might be post body (char* or byte*)
                    if (args[2] && !args[2].isNull()) {
                        var body = safeCStr(args[2]);
                        if (body && body.indexOf("<unreadable") === -1) {
                            log("    BODY: " + body);
                        }
                    }
                    // arg3 might be length
                    if (args[3]) {
                        log("    arg3 (len?): " + args[3].toInt32());
                    }
                },
                onLeave: function(retval) {
                    log("<<< " + this._name + " returned: " + retval);
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {
            log("  ✗ Failed to hook " + sym.name + ": " + e);
        }
    });

    // Also look for other HTTP methods
    var httpMethods = ["GetURL", "PostURL", "SendRequest", "DoRequest"];
    httpMethods.forEach(function(method) {
        var found = findAll(mod, method);
        found.forEach(function(sym) {
            if (sym.name.indexOf("ngHttp") !== -1 || sym.name.indexOf("CHttpClient") !== -1) {
                try {
                    Interceptor.attach(sym.address, {
                        onEnter: function(args) {
                            log(">>> " + sym.name);
                            if (args[1] && !args[1].isNull()) {
                                var s = safeCStr(args[1]);
                                if (s && s.indexOf("<unreadable") === -1) log("    arg1: " + s);
                            }
                            if (args[2] && !args[2].isNull()) {
                                var s2 = safeCStr(args[2]);
                                if (s2 && s2.indexOf("<unreadable") === -1) log("    arg2: " + s2);
                            }
                        }
                    });
                    log("  ✓ Hooked " + sym.name);
                } catch (e) {}
            }
        });
    });
}

function hookNgHttpSessionOnResponse(mod) {
    var matches = findAll(mod, "OnResponse");
    var sessionMatches = [];

    for (var i = 0; i < matches.length; i++) {
        if (matches[i].name.indexOf("ngHttp") !== -1 ||
            matches[i].name.indexOf("Session") !== -1 ||
            matches[i].name.indexOf("Connection") !== -1) {
            sessionMatches.push(matches[i]);
        }
    }

    if (sessionMatches.length === 0) {
        // Broaden: any OnResponse in the lib
        sessionMatches = matches;
    }

    sessionMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    this._name = sym.name;
                    log(">>> " + sym.name + " (HTTP response)");
                    log("    this=" + args[0]);

                    // OnResponse(this, data, length, statusCode, ...)
                    // Try multiple arg positions for the response body
                    for (var a = 1; a <= 3; a++) {
                        if (args[a] && !args[a].isNull()) {
                            var s = safeCStr(args[a]);
                            if (s && s.length > 2 && s.indexOf("<unreadable") === -1) {
                                log("    arg" + a + " str: " + s);
                            }
                        }
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {
            log("  ✗ Failed to hook " + sym.name + ": " + e);
        }
    });
}

function hookCurlEasySetopt(mod) {
    // curl_easy_setopt is in libcity_ar.so (statically linked libcurl)
    // or in a separate libcurl.so
    var sym = mod.findExportByName("curl_easy_setopt");
    if (!sym) {
        // Try system libcurl
        try {
            sym = Module.findExportByName("libcurl.so", "curl_easy_setopt");
        } catch (e) {}
    }
    if (!sym) {
        // Scan all loaded modules
        sym = Module.findExportByName(null, "curl_easy_setopt");
    }

    if (!sym) {
        log("curl_easy_setopt: NOT FOUND (may be inlined or obfuscated)");
        return;
    }

    Interceptor.attach(sym, {
        onEnter: function(args) {
            var option = args[1].toInt32();
            var value  = args[2];

            if (option === CURLOPT_URL) {
                var url = safeCStr(value);
                log("[CURL] CURLOPT_URL = " + url);
            } else if (option === CURLOPT_POSTFIELDS) {
                var body = safeCStr(value);
                log("[CURL] CURLOPT_POSTFIELDS = " + body);
            } else if (option === CURLOPT_CUSTOMREQUEST) {
                var method = safeCStr(value);
                log("[CURL] CURLOPT_CUSTOMREQUEST = " + method);
            } else if (option === CURLOPT_USERAGENT) {
                var ua = safeCStr(value);
                log("[CURL] CURLOPT_USERAGENT = " + ua);
            } else if (option === CURLOPT_HTTPHEADER) {
                // value is a curl_slist*; walk the linked list
                log("[CURL] CURLOPT_HTTPHEADER (slist):");
                try {
                    var node = value;
                    var count = 0;
                    while (!node.isNull() && count < 20) {
                        var dataPtr = node.readPointer();
                        if (!dataPtr.isNull()) {
                            log("    Header: " + safeCStr(dataPtr));
                        }
                        node = node.add(Process.pointerSize).readPointer();
                        count++;
                    }
                } catch (e) {
                    log("    (slist walk error: " + e + ")");
                }
            }
        }
    });
    log("  ✓ Hooked curl_easy_setopt @ " + sym);
}

function hookCurlWriteCallback(mod) {
    // Hook the curl write callback to capture response bodies.
    // curl_easy_setopt(handle, CURLOPT_WRITEFUNCTION, callback)
    // We find it via curl_easy_setopt and then hook the callback.
    var sym = mod.findExportByName("curl_easy_setopt") ||
              Module.findExportByName(null, "curl_easy_setopt");

    if (!sym) return;

    var writeCallbacks = {};

    Interceptor.attach(sym, {
        onEnter: function(args) {
            var option = args[1].toInt32();
            if (option === CURLOPT_WRITEFUNCTION) {
                var cb = args[2];
                var key = cb.toString();
                if (!writeCallbacks[key]) {
                    writeCallbacks[key] = true;
                    try {
                        // size_t write_callback(char *ptr, size_t size, size_t nmemb, void *userdata)
                        Interceptor.attach(cb, {
                            onEnter: function(args) {
                                var ptr    = args[0];
                                var size   = args[1].toInt32();
                                var nmemb  = args[2].toInt32();
                                var total  = size * nmemb;
                                if (total > 0 && !ptr.isNull()) {
                                    var body = safeUtf8(ptr, total);
                                    log("[CURL-RESP] write_callback (" + total + " bytes):");
                                    log("    " + body);
                                }
                            }
                        });
                        log("  ✓ Hooked curl write_callback @ " + cb);
                    } catch (e) {
                        log("  ✗ Failed to hook write_callback: " + e);
                    }
                }
            }
        }
    });
}

function hookRC4(mod) {
    // ngRC4Mnger::EncryptKpAliveData / DecryptKpAliveData
    var encMatches = findAll(mod, "EncryptKpAliveData");
    var decMatches = findAll(mod, "DecryptKpAliveData");

    // Also try InitKey
    var initMatches = findAll(mod, "InitKey");
    initMatches = initMatches.filter(function(s) {
        return s.name.indexOf("RC4") !== -1 || s.name.indexOf("rc4") !== -1;
    });

    encMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    this._name = sym.name;
                    // EncryptKpAliveData(this, data, len)
                    this._data = args[1];
                    this._len  = args[2] ? args[2].toInt32() : 0;
                    if (this._len > 0 && !this._data.isNull()) {
                        log(">>> " + sym.name + " (TCP PLAINTEXT → encrypt, " + this._len + " bytes)");
                        log(safeDump(this._data, this._len));
                        var txt = safeUtf8(this._data, this._len);
                        if (txt) log("    TEXT: " + txt);
                    }
                },
                onLeave: function(retval) {
                    log("<<< " + this._name + " done (data is now encrypted)");
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {
            log("  ✗ Failed to hook " + sym.name + ": " + e);
        }
    });

    decMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    this._name = sym.name;
                    this._data = args[1];
                    this._len  = args[2] ? args[2].toInt32() : 0;
                    log(">>> " + sym.name + " (TCP encrypted → PLAINTEXT, " + this._len + " bytes)");
                },
                onLeave: function(retval) {
                    // After decryption, data buffer contains plaintext
                    if (this._len > 0 && !this._data.isNull()) {
                        log("<<< " + this._name + " DECRYPTED (" + this._len + " bytes):");
                        log(safeDump(this._data, this._len));
                        var txt = safeUtf8(this._data, this._len);
                        if (txt) log("    TEXT: " + txt);
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {
            log("  ✗ Failed to hook " + sym.name + ": " + e);
        }
    });

    initMatches.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    log(">>> " + sym.name + " (RC4 key init)");
                    // Key is likely arg1 (char*) with arg2 (len)
                    if (args[1] && !args[1].isNull()) {
                        var keyStr = safeCStr(args[1]);
                        log("    key str: " + keyStr);
                        if (args[2]) {
                            var klen = args[2].toInt32();
                            if (klen > 0 && klen < 256) {
                                log("    key hex (" + klen + " bytes): " +
                                    safeDump(args[1], klen));
                            }
                        }
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {}
    });
}

function hookJsonHelpers(mod) {
    // CJsonHelper / CDZ_JsonHelper — JSON parsing/building
    var jsonSyms = findAll(mod, "JsonHelper");
    if (jsonSyms.length === 0) jsonSyms = findAll(mod, "jsonHelper");

    // Also hook ngJsonRoot or ngJsonHash creation from strings
    var jsonRootParse = findAll(mod, "ngJsonRoot");
    jsonRootParse = jsonRootParse.filter(function(s) {
        return s.name.indexOf("parse") !== -1 || s.name.indexOf("Parse") !== -1 ||
               s.name.indexOf("init") !== -1 || s.name.indexOf("Init") !== -1;
    });

    jsonRootParse.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    log(">>> " + sym.name + " (JSON parse)");
                    // Likely: ngJsonRoot::init(const char* json)
                    if (args[1] && !args[1].isNull()) {
                        var json = safeCStr(args[1]);
                        if (json && json.length > 2 && json.indexOf("<unreadable") === -1) {
                            log("    JSON INPUT: " + json);
                        }
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {}
    });
}

function hookConnectionManager(mod) {
    // ngConnectionManager or ngConnectionSession – request dispatch
    var dispatchSyms = findAll(mod, "ngConnectionSession");
    var sendSyms = dispatchSyms.filter(function(s) {
        return s.name.indexOf("send") !== -1 || s.name.indexOf("Send") !== -1 ||
               s.name.indexOf("start") !== -1 || s.name.indexOf("Start") !== -1 ||
               s.name.indexOf("request") !== -1 || s.name.indexOf("Request") !== -1;
    });

    sendSyms.forEach(function(sym) {
        try {
            Interceptor.attach(sym.address, {
                onEnter: function(args) {
                    log(">>> " + sym.name + " (connection session)");
                    for (var a = 1; a <= 4; a++) {
                        if (args[a] && !args[a].isNull()) {
                            var s = safeCStr(args[a]);
                            if (s && s.length > 2 && s.indexOf("<unreadable") === -1) {
                                log("    arg" + a + ": " + s);
                            }
                        }
                    }
                }
            });
            log("  ✓ Hooked " + sym.name);
        } catch (e) {}
    });
}

function hookCHttpClientMethods(mod) {
    // CHttpClient has ~636 API methods. Hook the central dispatch ones.
    var httpClientSyms = findAll(mod, "CHttpClient");

    // Log all found symbols for analysis
    log("CHttpClient symbols found: " + httpClientSyms.length);
    if (httpClientSyms.length <= 30) {
        httpClientSyms.forEach(function(s) {
            log("  " + s.name + " @ " + s.address);
        });
    }

    // Hook specific interesting methods by name patterns
    var interestingPatterns = [
        "CheckVersion", "GuestRegister", "Connect", "PlayerAuth",
        "GetServerInfo", "GetPlayerList", "UserCreate",
        "ChatGetMessage", "ChatPostMessage"
    ];

    interestingPatterns.forEach(function(pat) {
        var found = httpClientSyms.filter(function(s) {
            return s.name.indexOf(pat) !== -1;
        });
        found.forEach(function(sym) {
            try {
                Interceptor.attach(sym.address, {
                    onEnter: function(args) {
                        log(">>> CHttpClient::" + pat + " (" + sym.name + ")");
                        for (var a = 1; a <= 3; a++) {
                            if (args[a] && !args[a].isNull()) {
                                var s = safeCStr(args[a]);
                                if (s && s.length > 1 && s.indexOf("<unreadable") === -1) {
                                    log("    arg" + a + ": " + s);
                                }
                            }
                        }
                    },
                    onLeave: function(retval) {
                        log("<<< CHttpClient::" + pat + " returned: " + retval);
                    }
                });
                log("  ✓ Hooked CHttpClient method: " + sym.name);
            } catch (e) {}
        });
    });
}

// ============================================================================
// SYMBOL ENUMERATION (discovery mode)
// ============================================================================

function dumpAllSymbols(mod) {
    log("=== FULL SYMBOL DUMP for " + mod.name + " ===");
    var exports = mod.enumerateExports();
    log("Exports: " + exports.length);

    // Filter to interesting game symbols only
    var gameKeywords = [
        "CMsgCodec", "CHttpClient", "ngHttp", "ngRC4", "ngConnection",
        "ngJson", "CServer", "CTcpClient", "CHeartBeat", "CLoading",
        "CGameData", "JsonHelper", "EnCode", "Decode", "GetJsonData",
        "PutURL", "OnResponse", "curl_easy", "Encrypt", "Decrypt",
        "InitKey", "SendRequest", "ParseServer", "ParseRole",
        "ngByteBuffer"
    ];

    var relevant = exports.filter(function(e) {
        for (var k = 0; k < gameKeywords.length; k++) {
            if (e.name.indexOf(gameKeywords[k]) !== -1) return true;
        }
        return false;
    });

    log("Relevant game exports: " + relevant.length);
    relevant.forEach(function(e) {
        log("  [" + e.type + "] " + e.name + " @ " + e.address);
    });

    // If few exports, try symbols table
    if (relevant.length < 5) {
        log("Few exports found, scanning symbols table...");
        try {
            var syms = mod.enumerateSymbols();
            var relevantSyms = syms.filter(function(s) {
                for (var k = 0; k < gameKeywords.length; k++) {
                    if (s.name.indexOf(gameKeywords[k]) !== -1) return true;
                }
                return false;
            });
            log("Relevant symbols: " + relevantSyms.length);
            relevantSyms.forEach(function(s) {
                log("  [" + s.type + "] " + s.name + " @ " + s.address);
            });
        } catch (e) {
            log("Symbol enumeration failed: " + e);
        }
    }

    log("=== END SYMBOL DUMP ===");
}

// ============================================================================
// JAVA HOOKS (supplementary — log NGHttpSession.doPut calls from Java side)
// ============================================================================

function hookJava() {
    Java.perform(function() {
        try {
            var NGHttpSession = Java.use("com.anansimobile.nge.NGHttpSession");
            NGHttpSession.doPut.implementation = function(url, data, l) {
                log("[JAVA] NGHttpSession.doPut() url=" + url +
                    " data_len=" + (data ? data.length : 0) +
                    " l=" + l);
                if (data && data.length > 0 && data.length < MAX_HEXDUMP) {
                    // Hex dump of byte[] data
                    var hex = "";
                    for (var i = 0; i < Math.min(data.length, 128); i++) {
                        var b = (data[i] & 0xff).toString(16);
                        hex += (b.length < 2 ? "0" : "") + b + " ";
                    }
                    log("    data hex: " + hex);
                    // Try as UTF-8 string
                    try {
                        var s = "";
                        for (var j = 0; j < Math.min(data.length, MAX_STR); j++) {
                            s += String.fromCharCode(data[j] & 0xff);
                        }
                        log("    data str: " + s);
                    } catch (e) {}
                }
                // Call original
                this.doPut(url, data, l);
            };
            log("[JAVA] ✓ Hooked NGHttpSession.doPut");
        } catch (e) {
            log("[JAVA] NGHttpSession hook failed: " + e);
        }

        // Hook NextGenEngine.nge_log to see native log output
        try {
            var NGE = Java.use("com.anansimobile.nge.NextGenEngine");
            NGE.nge_log.implementation = function(logStr) {
                log("[NGE_LOG] " + logStr);
                this.nge_log(logStr);
            };
            log("[JAVA] ✓ Hooked NextGenEngine.nge_log");
        } catch (e) {
            log("[JAVA] nge_log hook failed: " + e);
        }
    });
}

// ============================================================================
// MAIN
// ============================================================================

function main() {
    log("============================================");
    log("  Waker Protocol Dump - Frida Hook Script");
    log("  Target: " + LIB_NAME);
    log("============================================");

    var mod = null;

    // Try direct name first
    try {
        mod = Process.getModuleByName(LIB_NAME);
    } catch (e) {}

    // If not found, scan all loaded modules for one containing our lib name
    if (!mod) {
        var modules = Process.enumerateModules();
        log("Loaded modules (" + modules.length + "):");
        for (var i = 0; i < modules.length; i++) {
            // Log all .so modules that look game-related, or any with "city"
            var mname = modules[i].name.toLowerCase();
            if (mname.indexOf("city") !== -1 || mname.indexOf("anansi") !== -1 ||
                mname.indexOf("game") !== -1 || mname.indexOf("nge") !== -1) {
                log("  ** " + modules[i].name + " @ " + modules[i].base + " (" + modules[i].path + ")");
            }
            if (modules[i].name.indexOf("libcity_ar") !== -1 ||
                modules[i].path.indexOf("libcity_ar") !== -1) {
                mod = modules[i];
                log("Found library via module scan: " + mod.path);
            }
        }
        // If still not found, log first 30 modules for debugging
        if (!mod) {
            log("Library NOT found. First 30 loaded modules:");
            for (var j = 0; j < Math.min(30, modules.length); j++) {
                log("  [" + j + "] " + modules[j].name + " (" + modules[j].path + ")");
            }
        }
    }

    if (mod) {
        attachHooks(mod);
    } else {
        log(LIB_NAME + " not yet loaded. Waiting for dlopen...");

        // Find dlopen/android_dlopen_ext with full error protection
        var dlopenAddr = null;
        var dlopenNames = [
            ["libdl.so", "android_dlopen_ext"],
            ["libdl.so", "dlopen"],
            [null, "android_dlopen_ext"],
            [null, "dlopen"]
        ];
        for (var k = 0; k < dlopenNames.length; k++) {
            if (dlopenAddr) break;
            try {
                dlopenAddr = Module.findExportByName(dlopenNames[k][0], dlopenNames[k][1]);
            } catch (e) {
                log("  dlopen lookup failed for " + dlopenNames[k][0] + "/" + dlopenNames[k][1] + ": " + e);
            }
        }

        if (!dlopenAddr) {
            log("ERROR: Cannot find dlopen. Library not loaded and cannot watch for it.");
            log("Try spawning the app with: frida -U -f com.anansimobile.city_ar -l frida_dump.js --no-pause");
            return;
        }

        var dlInterceptor = Interceptor.attach(dlopenAddr, {
            onEnter: function(args) {
                this._path = safeCStr(args[0]);
            },
            onLeave: function(retval) {
                if (this._path && this._path.indexOf("libcity_ar") !== -1) {
                    log(LIB_NAME + " loaded! Attaching hooks...");
                    setTimeout(function() {
                        var m = null;
                        try { m = Process.getModuleByName(LIB_NAME); } catch(e) {}
                        if (!m) {
                            var mods = Process.enumerateModules();
                            for (var mi = 0; mi < mods.length; mi++) {
                                if (mods[mi].name.indexOf("libcity_ar") !== -1) {
                                    m = mods[mi]; break;
                                }
                            }
                        }
                        if (m) attachHooks(m);
                        else log("ERROR: library loaded but module not found!");
                    }, 500);
                    dlInterceptor.detach();
                }
            }
        });
        log("Watching dlopen @ " + dlopenAddr);
    }

    // Java hooks (independent)
    hookJava();
}

function attachHooks(mod) {
    log("Module: " + mod.name + " base=" + mod.base + " size=" + mod.size);
    log("");

    // Phase 1: Enumerate all relevant symbols for discovery
    dumpAllSymbols(mod);
    log("");

    // Phase 2: Attach hooks
    log("=== ATTACHING HOOKS ===");

    log("--- CMsgCodec (encode/decode) ---");
    hookCMsgCodecEnCode(mod);
    log("");

    log("--- ngHttpClient (HTTP requests) ---");
    hookNgHttpClient(mod);
    log("");

    log("--- ngHttpSession::OnResponse (HTTP responses) ---");
    hookNgHttpSessionOnResponse(mod);
    log("");

    log("--- curl_easy_setopt (libcurl layer) ---");
    hookCurlEasySetopt(mod);
    hookCurlWriteCallback(mod);
    log("");

    log("--- ngRC4Mnger (TCP RC4 encryption) ---");
    hookRC4(mod);
    log("");

    log("--- JSON parsing ---");
    hookJsonHelpers(mod);
    log("");

    log("--- ngConnectionSession ---");
    hookConnectionManager(mod);
    log("");

    log("--- CHttpClient API methods ---");
    hookCHttpClientMethods(mod);
    log("");

    log("=== HOOKS ATTACHED - MONITORING ===");
    log("All traffic will be logged below.");
    log("============================================");
}

// Auto-start
setTimeout(main, 0);
