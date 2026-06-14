"""
timed_hook.py — launch the game, wait until libcity_ar.so is mapped (it loads
only when entering the GL world), then ATTACH frida and install hooks at the
recovered base. Litmus: does ngInteger::IntValue fire under Houdini at all?

Usage: python timed_hook.py
"""
import subprocess, sys, time, re, frida

PKG = "com.anansimobile.city_ar"
ACT = PKG + "/" + PKG + ".Main"
INTVALUE = 0x5cbdc4
GOODS = 0x40cc70
RACE  = 0x35edb8
SCREENUPD = 0x30b98c   # ngScreen::HandleUpdate — per-frame canary
VIEWUPD   = 0x311ce0   # ngView::HandleUpdate — per-frame canary

def adb(*a):
    return subprocess.run(["adb"] + list(a), capture_output=True, text=True).stdout

def pidof():
    return adb("shell", "pidof", PKG).strip()

def libcity_base(pid):
    maps = adb("shell", "cat", f"/proc/{pid}/maps")
    for line in maps.splitlines():
        if "libcity_ar.so" in line and " r-xp " in line and " 00000000 " in line:
            return int(line.split("-")[0], 16)
    # fallback: any libcity mapping, lowest base
    bases = [int(l.split("-")[0], 16) for l in maps.splitlines() if "libcity_ar.so" in l]
    return min(bases) if bases else None

JS = r"""
var BASE = ptr('%BASE%');
function t(o){return BASE.add(o).or(1);}
var intCalls=0, intNull=0, canary=0;
function hook(name,o,en,le){try{var cb={onEnter:en};if(le)cb.onLeave=le;Interceptor.attach(t(o),cb);send({tag:'HOOKED',name:name,addr:t(o).toString()});}catch(e){send({tag:'HOOKFAIL',name:name,err:e.message});}}
hook('ScreenUpd',%SCREENUPD%,function(a){canary++;},null);
hook('ViewUpd',%VIEWUPD%,function(a){canary++;},null);
hook('IntValue',%INTVALUE%,function(a){intCalls++;var s=a[0];if(s.isNull()||s.compare(ptr(0x1000))<0){intNull++;send({tag:'INTVALUE_NULL',self:s.toString()});}},null);
hook('GoodsParse',%GOODS%,function(a){send({tag:'GOODS_ENTER',node:a[1].toString()});},null);
hook('RaceParse',%RACE%,function(a){send({tag:'RACE_ENTER',node:a[1].toString()});},null);
var n=0;
var iv=setInterval(function(){n++;send({tag:'HB',canary:canary,intCalls:intCalls,intNull:intNull});if(n>30)clearInterval(iv);},2000);
"""

def on_message(m, d):
    if m.get("type") == "send":
        print("[MSG]", m["payload"], flush=True)
    else:
        print("[ERR]", m, flush=True)

def main():
    adb("shell", "am", "force-stop", PKG)
    adb("shell", "pm", "clear", PKG)
    adb("shell", "am", "start", "-n", ACT)
    print("[*] launched, polling for libcity_ar.so map...", flush=True)
    base = None
    deadline = time.time() + 240
    while time.time() < deadline:
        pid = pidof()
        if pid:
            base = libcity_base(pid)
            if base:
                print(f"[*] libcity_ar base=0x{base:x} pid={pid} — attaching NOW", flush=True)
                break
        time.sleep(0.4)
    if not base:
        print("[!] libcity_ar never mapped within timeout", flush=True)
        return 2
    try:
        dev = frida.get_usb_device(timeout=10)
        session = dev.attach(int(pid))
        src = (JS.replace("%BASE%", hex(base))
                  .replace("%INTVALUE%", hex(INTVALUE))
                  .replace("%GOODS%", hex(GOODS))
                  .replace("%RACE%", hex(RACE))
                  .replace("%SCREENUPD%", hex(SCREENUPD))
                  .replace("%VIEWUPD%", hex(VIEWUPD)))
        script = session.create_script(src)
        script.on("message", on_message)
        script.load()
        print("[*] hooks installed; observing 30s", flush=True)
        time.sleep(30)
    except Exception as e:
        print("[!] attach/hook failed:", e, flush=True)
        return 3
    print("[*] done", flush=True)

if __name__ == "__main__":
    sys.exit(main() or 0)
