// hook_probe.js — does a native Interceptor hook fire on ARM code under Houdini?
// Hooks ngInteger::IntValue (0x5cbdc4, hot) as the litmus test, plus the 3 crash
// parsers. Logs the JSON key on each ngHashMap::GetNode so the field lookup
// immediately before a crash is captured.

'use strict';

var OFF = {
  IntValue:   0x5cbdc4,  // ngInteger::IntValue() const
  GetNode:    null,      // ngHashMap::GetNode — filled from symbol below
  GoodsParse: 0x40cc70,  // CGoods::Parse(void*)
  RaceParse:  0x35edb8,  // CConfigure_RG_Atheltic_Reward::ParseData(void*)
};

function thumb(addr) { return addr.or(1); }      // set Thumb bit
function hexs(p) { try { return p.toString(); } catch (e) { return '?'; } }

// read a C string from a char* that may itself be at obj+offset; best-effort
function readCStr(p) {
  try { if (p.isNull()) return null; return p.readUtf8String(); }
  catch (e) { try { return p.readCString(); } catch (e2) { return null; } }
}

// Houdini maps the ARM .so outside the x86 linker, so enumerateModules misses it.
// Find the lowest mapped range whose file path contains libcity_ar.so (= load base).
var base = null;
var mod = Process.findModuleByName('libcity_ar.so');
if (mod !== null) base = mod.base;
if (base === null) {
  var cands = [];
  Process.enumerateRanges('r--').concat(Process.enumerateRanges('r-x')).forEach(function (r) {
    if (r.file && r.file.path && r.file.path.indexOf('libcity_ar.so') >= 0) cands.push(r);
  });
  cands.sort(function (a, b) { return a.base.compare(b.base); });
  if (cands.length) {
    // base = mapping whose file.offset == 0
    cands.forEach(function (r) { if (base === null && r.file.offset === 0) base = r.base; });
    if (base === null) base = cands[0].base;
    send({tag:'RANGES', count: cands.length, paths: cands.slice(0,3).map(function(r){return r.file.path+'@'+r.base+' off='+r.file.offset;})});
  }
}
if (base === null) { send({tag:'FATAL', msg:'libcity_ar.so not found in modules or ranges'}); }
else {
  send({tag:'MODULE', base: base.toString()});

  var firedIntValue = 0;
  var lastKey = { cmd: null, key: null };

  function hookAt(name, off, onEnter, onLeave) {
    if (off === null) { send({tag:'SKIP', name:name, reason:'no offset'}); return; }
    var addr = thumb(base.add(off));
    try {
      Interceptor.attach(addr, { onEnter: onEnter, onLeave: onLeave });
      send({tag:'HOOKED', name:name, addr: addr.toString()});
    } catch (e) {
      send({tag:'HOOK_FAIL', name:name, err: e.message});
    }
  }

  // LITMUS: IntValue — if this fires, native hooks work under Houdini.
  hookAt('IntValue', OFF.IntValue, function (args) {
    firedIntValue++;
    this.self = args[0];
    if (this.self.isNull() || this.self.compare(ptr(0x1000)) < 0) {
      send({tag:'INTVALUE_NULL', this: hexs(this.self), lastKey: lastKey.key, lastCmd: lastKey.cmd});
    }
  }, null);

  // ngHashMap::GetNode(key) — key is a hashable; for JSON it's usually a char*.
  // arg0=this(map), arg1=key. Try to read key as a string.
  hookAt('GetNode', OFF.GetNode, function (args) {
    var k = readCStr(args[1]);
    if (k !== null && k.length > 0 && k.length < 64) { lastKey.key = k; }
  }, null);

  hookAt('GoodsParse', OFF.GoodsParse, function (args) {
    send({tag:'GOODS_PARSE_ENTER', node: hexs(args[1])});
  }, function (ret) {});

  hookAt('RaceParse', OFF.RaceParse, function (args) {
    send({tag:'RACE_PARSE_ENTER', node: hexs(args[1])});
  }, function (ret) {});

  // heartbeat so we know the script is alive and whether IntValue ever fired
  setInterval(function () {
    send({tag:'HEARTBEAT', intValueCalls: firedIntValue, lastKey: lastKey.key});
  }, 3000);
}
