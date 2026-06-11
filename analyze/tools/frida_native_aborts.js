"use strict";

  function ts() {
      var d = new Date();
      return d.toISOString().substr(11, 12);
  }
  function log(m) { console.log("[NATIVE-ABORT] " + ts() + " " + m); }

  function backtrace(ctx) {
      try {
          var bt = Thread.backtrace(ctx, Backtracer.ACCURATE);
          for (var i = 0; i < bt.length && i < 40; i++) {
              var sym = DebugSymbol.fromAddress(bt[i]);
              log("    " + bt[i] + "  " + sym);
          }
      } catch (e) { log("    backtrace err: " + e); }
  }

  function findExport(modName, fnName) {
      // Frida-17 compatible export lookup.
      // Order: global lookup -> named-module lookup -> enumerate all modules -> legacy.
      try {
          if (typeof Module !== "undefined" && typeof Module.findGlobalExportByName === "function") {
              var a = Module.findGlobalExportByName(fnName);
              if (a) return a;
          }
      } catch (e) {}
      try {
          if (modName && typeof Process !== "undefined" && typeof Process.findModuleByName === "function") {
              var m = Process.findModuleByName(modName);
              if (m && typeof m.findExportByName === "function") {
                  var a2 = m.findExportByName(fnName);
                  if (a2) return a2;
              }
          }
      } catch (e) {}
      try {
          if (typeof Process !== "undefined" && typeof Process.enumerateModules === "function") {
              var mods = Process.enumerateModules();
              for (var i = 0; i < mods.length; i++) {
                  try {
                      if (typeof mods[i].findExportByName === "function") {
                          var a3 = mods[i].findExportByName(fnName);
                          if (a3) return a3;
                      }
                  } catch (e) {}
              }
          }
      } catch (e) {}
      // Legacy Frida <17 fallback.
      try {
          if (typeof Module !== "undefined" && typeof Module.findExportByName === "function") {
              return Module.findExportByName(modName, fnName);
          }
      } catch (e) {}
      return null;
  }

  function hookExport(modName, fnName, argDecoder) {
      var addr = null;
      try { addr = findExport(modName, fnName); }
      catch (e) { log("  lookup err for " + fnName + ": " + e); }
      if (!addr) { log("  miss: " + (modName||"*") + "!" + fnName); return; }
      Interceptor.attach(addr, {
          onEnter: function(args) {
              var decoded = "";
              if (typeof argDecoder === "function") {
                  try {
                      decoded = argDecoder(args);
                  } catch (e) {
                      log("==> " + fnName + " (decoder threw: " + e + ")");
                      backtrace(this.context);
                      return;
                  }
                  if (decoded === null || decoded === undefined) {
                      return;  // decoder explicitly asked to skip
                  }
              }
              log("==> " + fnName + " args=" + decoded);
              backtrace(this.context);
          }
      });
      log("  hooked: " + fnName + " @ " + addr);
  }

  // libc fatal/abort paths
  hookExport(null, "abort", function() { return ""; });
  hookExport(null, "raise", function(a) { return "sig=" + a[0].toInt32(); });
  hookExport(null, "__assert2", function(a) {
      return [a[0].readCString(), a[1].toInt32(), a[2].readCString(), a[3].readCString()].join(" | ");
  });
  hookExport(null, "__android_log_assert", function(a) {
      var cond = a[0].isNull() ? "<null>" : a[0].readCString();
      var tag  = a[1].isNull() ? "<null>" : a[1].readCString();
      var fmt  = a[2].isNull() ? "<null>" : a[2].readCString();
      return "cond=" + JSON.stringify(cond) + " tag=" + JSON.stringify(tag) + " fmt=" + JSON.stringify(fmt);
  });
  hookExport(null, "__android_log_print", function(a) {
      var prio = a[0].toInt32();
      if (prio < 6) return null;          // only ERROR(6) / FATAL(7)
      var tag = a[1].isNull() ? "<null>" : a[1].readCString();
      var fmt = a[2].isNull() ? "<null>" : a[2].readCString();
      return "prio=" + prio + " tag=" + JSON.stringify(tag) + " fmt=" + JSON.stringify(fmt);
  });

  // also catch a SIGSEGV before the kernel kills us, via SignalHandler.set
  // (best-effort — engine may install its own and override)
  try {
      var sa = findExport(null, "sigaction");
      if (sa) {
          Interceptor.attach(sa, {
              onEnter: function(args) {
                  log("sigaction(sig=" + args[0].toInt32() + ", new=" + args[1] + ", old=" + args[2] + ")");
              }
          });
          log("  hooked: sigaction");
      }
  } catch (e) {}

  // =========================================================================
  // libcity_ar.so + libart.so instrumentation: locate the engine site that
  // actually emits the empty launchUrl event.
  // =========================================================================
  //
  // Corrected model (after PLT resolution):
  //   The previously-suspected "JNI dispatcher" helpers at 0x6bcaXX in
  //   libcity_ar.so resolve to OpenGL ES PLT entries (glMatrixMode, glOrthof,
  //   glViewport, glClear, ...). nativeRender attaches JNIEnv, sets up GL
  //   state, calls a vtable[8] scene-render via blx r6, then detaches JNIEnv.
  //   The JNI call that reaches NGDevice.launchUrl must be made from somewhere
  //   inside that vtable[8] chain.
  //
  // Hook 1: ngDeviceAndroid::LaunchURL @ rva 0x5efb9c
  //   Static analysis says zero callers. If runtime says otherwise, the
  //   backtrace identifies the path.
  //
  // Hook 2: JNIEnv->NewStringUTF via libart.so symbol
  //   Filter on empty-buffer creations. When a NewStringUTF("") fires, capture
  //   the backtrace and ring-push it. The most recent entries when the Java
  //   empty-launchUrl suppression triggers identify the engine subsystem
  //   producing the empty jstring.
  //
  // Hook 3: JNIEnv->CallStaticVoidMethod / CallStaticVoidMethodV / -MethodA
  //   Capture (clazz, methodID, first jstring arg) so we can resolve the
  //   target Java method via JVMTI/reflection later if needed.
  //
  // Cross-script trigger: frida_java_hooks.js section #10 invokes
  // globalThis.__waker_dump_native_ring() in the empty-URL suppression branch.

  var LIB = "libcity_ar.so";
  var LAUNCH_URL_RVA = 0x5efb9c;
  var NATIVE_RENDER_RVA_LO = 0x5f4710;
  var NATIVE_RENDER_RVA_HI = 0x5f48ed;

  // HOUDINI SAFETY MODEL (load-bearing):
  //   libcity_ar.so is ARM code translated by Houdini/libnb on this x86
  //   emulator. Interceptor.attach patches native code; patching translated
  //   ARM crashes the linker/translator (observed: SIGSEGV in /system/bin/linker
  //   + __kernel_vsyscall). NEVER hook libcity_ar.so here.
  //   libart.so / libc.so / liblog.so are x86-native -> safe to hook.
  //
  // HOOK_NATIVE_ARM: gates the (unsafe) libcity_ar.so LaunchURL hook. Leave
  //   FALSE under Houdini. Only set true on a real ARM device / non-translated
  //   environment.
  var HOOK_NATIVE_ARM = false;
  //
  // ENABLE_JNI_TRACE: gates the x86-safe libart JNI hooks (NewStringUTF
  //   empty-filter + GetStaticMethodID launchUrl-filter + CallStaticVoidMethod).
  //   Safe under Houdini because libart is x86-native. Default false to confirm
  //   baseline stability first; flip true for the JNI-trace run.
  var ENABLE_JNI_TRACE = true;

  var ringBuffer = [];
  var RING_MAX = 64;
  function ringPush(entry) {
      ringBuffer.push(entry);
      if (ringBuffer.length > RING_MAX) ringBuffer.shift();
  }

  function safeReadCStr(p, maxLen) {
      try {
          if (p === null || p.isNull()) return "<null>";
          var s = p.readCString(maxLen || 64);
          if (s === null) return "<unreadable>";
          return s;
      } catch (e) {
          return "<err:" + e + ">";
      }
  }

  function symFor(addr) {
      try { return "" + addr + " " + DebugSymbol.fromAddress(addr); }
      catch (e) { return "" + addr + " (sym-err)"; }
  }

  globalThis.__waker_dump_native_ring = function(label) {
      var lbl = label || "manual";
      log("================ NATIVE-RING DUMP (" + ringBuffer.length +
          " entries, label=" + lbl + ") ================");
      for (var i = 0; i < ringBuffer.length; i++) {
          var e = ringBuffer[i];
          log("  #" + i + " " + e.time + " " + e.tag + " tid=" + e.tid +
              (e.note ? "  note=" + e.note : ""));
          if (e.lr) log("      lr=" + symFor(e.lr));
          for (var j = 0; j < (e.bt || []).length; j++) {
              log("      bt[" + j + "] " + symFor(e.bt[j]));
          }
      }
      log("================ END DUMP ================");
  };

  // Locate libart.so (JNIEnv impl) for JNI hooks. Try common candidate names.
  function findArt() {
      var candidates = ["libart.so", "libdvm.so", "libnativehelper.so"];
      for (var i = 0; i < candidates.length; i++) {
          var m = null;
          try { m = Process.findModuleByName(candidates[i]); } catch (e) {}
          if (m) return m;
      }
      try {
          var mods = Process.enumerateModules();
          for (var k = 0; k < mods.length; k++) {
              if (mods[k].name === "libart.so" || mods[k].name === "libdvm.so") return mods[k];
          }
      } catch (e) {}
      return null;
  }

  // Timing-safe JNI hook. CRITICAL: the decoder must return null/undefined for
  // the common (uninteresting) case so we early-exit BEFORE doing any
  // backtrace. Per-call cost for the boring path is just whatever the decoder
  // does (kept to ~1 memory read). Backtrace (expensive) only runs when the
  // decoder flags an interesting event. Without this discipline, hooking a
  // high-frequency libart function and backtracing every call stalls the GL
  // thread and trips the watchdog -> instrumentation-induced crash.
  function hookJniCheap(art_exports, frida_name_substr, tag, decoder) {
      var found = null;
      for (var i = 0; i < art_exports.length; i++) {
          if (art_exports[i].name.indexOf(frida_name_substr) !== -1) { found = art_exports[i]; break; }
      }
      if (!found) { log("  miss: libart!" + frida_name_substr); return null; }
      try {
          Interceptor.attach(found.address, {
              onEnter: function(args) {
                  var note;
                  try { note = decoder(args); } catch (e) { return; }
                  if (note === null || note === undefined) return;  // boring -> cheapest exit
                  var entry = { time: ts(), tag: tag, tid: Process.getCurrentThreadId(),
                                lr: this.returnAddress, bt: [], note: note };
                  try {
                      var bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
                      for (var b = 0; b < bt.length && b < 10; b++) entry.bt.push(bt[b]);
                  } catch (e) {}
                  ringPush(entry);
                  log("!!! " + tag + " " + note);
                  for (var j = 0; j < entry.bt.length; j++) log("    " + symFor(entry.bt[j]));
              }
          });
          log("  hooked: " + tag + " @ " + found.address);
          return found.address;
      } catch (e) { log("  attach err " + tag + ": " + e); return null; }
  }

  // jmethodIDs captured at runtime from Get(Static)MethodID for "launchUrl",
  // so the Call*VoidMethod* hooks can recognize the invocation by methodID
  // rather than relying on unreliable Houdini ARM backtraces. We capture both
  // the static-callback and instance-method dispatch shapes.
  var launchUrlMethodIDs = [];
  function rememberLaunchMethodID(retval) {
      try { launchUrlMethodIDs.push(ptr(retval.toString())); } catch (e) {}
  }
  function isLaunchMethodID(midPtr) {
      for (var i = 0; i < launchUrlMethodIDs.length; i++) {
          try { if (launchUrlMethodIDs[i].equals(midPtr)) return true; } catch (e) {}
      }
      return false;
  }
  // Cap empty-jstring backtraces so a hot NewStringUTF path can't flood the log
  // or stall the GL thread (the prior instrumentation-crash failure mode).
  var emptyStrCount = 0;
  var EMPTY_STR_CAP = 24;

  // OPTIONAL native ARM hook — Houdini-UNSAFE. Only runs if HOOK_NATIVE_ARM.
  function setupArmHook() {
      if (!HOOK_NATIVE_ARM) {
          log("  (native ARM hook disabled — HOOK_NATIVE_ARM=false; Houdini-safe)");
          return;
      }
      var mod = null;
      try { mod = Process.findModuleByName(LIB); } catch (e) {}
      if (!mod) {
          try {
              var mods = Process.enumerateModules();
              for (var k = 0; k < mods.length; k++) {
                  if (mods[k].name.indexOf("city_ar") !== -1) { mod = mods[k]; break; }
              }
          } catch (e) {}
      }
      if (!mod) { log("  libcity_ar.so not mapped; ARM hook skipped"); return; }
      var base = mod.base;
      try {
          var launchAddr = base.add(LAUNCH_URL_RVA);
          var launchHits = 0, FULL_LOG_CAP = 8;
          Interceptor.attach(launchAddr, {
              onEnter: function(args) {
                  launchHits++;
                  if (launchHits > FULL_LOG_CAP) {
                      if (launchHits % 100 === 0) log("*** LaunchURL hit #" + launchHits + " (capped)");
                      return;
                  }
                  log("*** ngDeviceAndroid::LaunchURL REACHED (#" + launchHits + ") url=" +
                      JSON.stringify(safeReadCStr(args[1], 256)));
                  try {
                      var bt = Thread.backtrace(this.context, Backtracer.ACCURATE);
                      for (var i = 0; i < bt.length && i < 24; i++) log("      " + symFor(bt[i]));
                  } catch (e) {}
              }
          });
          log("  hooked: ngDeviceAndroid::LaunchURL @ " + launchAddr + "  (ARM, Houdini-RISKY)");
      } catch (e) { log("  LaunchURL ARM hook err: " + e); }
  }

  // x86-safe libart JNI hooks. libart.so is native x86 on this emulator, so
  // Interceptor.attach here does NOT touch Houdini-translated code.
  function setupJniHooks() {
      if (!ENABLE_JNI_TRACE) {
          log("  (JNI trace disabled — ENABLE_JNI_TRACE=false)");
          return;
      }
      var art = findArt();
      if (!art) { log("  libart.so / libdvm.so NOT FOUND - skipping JNI hooks"); return; }
      log("  libart base = " + art.base + " name=" + art.name + "  (x86-native, safe)");
      var artExports = [];
      try { artExports = art.enumerateExports(); } catch (e) { log("  enumExports err: " + e); }

      // Get(Static)MethodID: capture the launchUrl jmethodID(s) (rare; init-time).
      // Hook BOTH the static and instance ID lookups so we recognize whichever
      // dispatch shape the engine actually uses for launchUrl.
      function hookMethodIdLookup(substr, label) {
          var found = null;
          for (var i = 0; i < artExports.length; i++)
              if (artExports[i].name.indexOf(substr) !== -1) { found = artExports[i]; break; }
          if (!found) { log("  miss: " + substr); return; }
          Interceptor.attach(found.address, {
              onEnter: function(args) { this.isLaunch = (safeReadCStr(args[2], 32) === "launchUrl"); },
              onLeave: function(retval) {
                  if (this.isLaunch) {
                      rememberLaunchMethodID(retval);
                      log("*** captured launchUrl jmethodID via " + label + " = " + retval + " ***");
                  }
              }
          });
          log("  hooked: " + label + " (launchUrl filter) @ " + found.address);
      }
      hookMethodIdLookup("GetStaticMethodID", "GetStaticMethodID");
      hookMethodIdLookup("GetMethodID", "GetMethodID");

      // Call*VoidMethod*: when methodID matches a captured launchUrl ID, log +
      // ring-push a backtrace. Covers static (clazz) and instance (jobject)
      // dispatch, in both V (va_list) and A (jvalue*) arg-passing variants.
      // Decoder is hot-path-cheap: length guard + pointer compare; no backtrace
      // unless it actually matches launchUrl. (Native backtrace into the
      // translated ARM caller may be partial, so we also log the return addr.)
      function callVoidDecoder(label) {
          return function(args) {
              if (launchUrlMethodIDs.length === 0) return null;
              if (!isLaunchMethodID(args[2])) return null;
              return "launchUrl invoked via " + label + "  recv=" + args[1] + " methodID=" + args[2];
          };
      }
      hookJniCheap(artExports, "CallStaticVoidMethodV", "CallStaticVoidMethodV", callVoidDecoder("CallStaticVoidMethodV"));
      hookJniCheap(artExports, "CallStaticVoidMethodA", "CallStaticVoidMethodA", callVoidDecoder("CallStaticVoidMethodA"));
      hookJniCheap(artExports, "CallVoidMethodV", "CallVoidMethodV", callVoidDecoder("CallVoidMethodV"));
      hookJniCheap(artExports, "CallVoidMethodA", "CallVoidMethodA", callVoidDecoder("CallVoidMethodA"));

      // NewStringUTF: ultra-cheap empty-buffer filter (single byte read). The
      // empty launchUrl string is created here before dispatch, so this
      // backtrace is often the most useful pointer to the engine subsystem
      // responsible. Capped via EMPTY_STR_CAP to stay timing-safe.
      hookJniCheap(artExports, "NewStringUTF", "NewStringUTF", function(args) {
          var p = args[1];
          if (p.isNull()) return null;
          var first;
          try { first = p.readU8(); } catch (e) { return null; }
          if (first !== 0) return null;          // non-empty -> cheapest skip
          emptyStrCount++;
          if (emptyStrCount > EMPTY_STR_CAP) return null;  // bounded backtraces
          return "*** EMPTY jstring #" + emptyStrCount + " created ***";
      });
  }

  function setupAll() {
      setupArmHook();
      setupJniHooks();
      return true;
  }

  // Run once now; if neither hook needs libcity_ar.so (default), this is
  // immediate and stable. Only retry if HOOK_NATIVE_ARM needed the module.
  setupAll();