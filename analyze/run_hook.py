import sys, time, frida

PKG = "com.anansimobile.city_ar"

def on_message(msg, data):
    if msg.get("type") == "send":
        print("[MSG]", msg["payload"], flush=True)
    else:
        print("[ERR]", msg, flush=True)

dev = frida.get_usb_device(timeout=10)
# ATTACH (not spawn) per Houdini guidance. PID passed as argv[2] (from adb pidof).
pid = int(sys.argv[2]) if len(sys.argv) > 2 else dev.get_process(PKG).pid
print(f"[*] attaching to {PKG} pid={pid}", flush=True)
session = dev.attach(pid)
with open(sys.argv[1] if len(sys.argv) > 1 else "hook_probe.js", encoding="utf-8") as f:
    src = f.read()
script = session.create_script(src)
script.on("message", on_message)
script.load()
print("[*] script loaded; running 40s", flush=True)
time.sleep(40)
print("[*] done", flush=True)
