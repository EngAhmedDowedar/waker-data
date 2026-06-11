// frida_mascot_probe.js — verify the mascot/mission data path at runtime.
//
// Hypothesis: the bottom-of-screen mascot bubble's text is `missionTip` from
// the CMission entry whose id matches CPlayer.missionId. mission.city ships
// 29 entries (ids ~1..29); we send missionId=100, so the entry lookup
// returns NULL and the bubble renders empty.
//
// What this script confirms:
//   1. How many CMission entries are actually loaded (count CMission::Read).
//   2. Whether CMissionManager::GetMission returns NULL during boot.
//   3. When CMainScreen / CMissionManager actually queries for the mission.
//   4. The bytes the client sees out of /city/connect/connect via
//      ngHttpClient::ParseResponse (independent check vs server-side dump).
//   5. What CMissionManager::IsInThisMission is asked about.
//
// Run:  frida -U -f com.anansimobile.city_ar -l frida_mascot_probe.js --no-pause

'use strict';

const TAG = '[PROBE]';
function log(m) { console.log(TAG + ' ' + m); }

const MOD = 'libcity_ar.so';

function resolveAll(names) {
    const out = {};
    for (const n of names) {
        const a = Module.findExportByName(MOD, n);
        out[n] = a;
        log('  ' + (a ? ('@ ' + a) : '(not found)') + '   ' + n);
    }
    return out;
}

setTimeout(function () {
    const m = Process.findModuleByName(MOD);
    if (!m) { log('libcity_ar.so not loaded yet — retrying in 200ms'); setTimeout(arguments.callee, 200); return; }
    log('libcity_ar.so base=' + m.base + ' size=' + m.size);

    const syms = resolveAll([
        '_ZN8CMission4ReadEP12ngFileReader',                    // CMission::Read(ngFileReader*)
        '_ZN15CMissionManager10GetMissionEv',                   // CMissionManager::GetMission()
        '_ZN15CMissionManager11ShowMissionEv',                  // ShowMission()
        '_ZN15CMissionManager15IsInThisMissionEi',              // IsInThisMission(int)
        '_ZN15CMissionManager9IsMissionEi',                     // IsMission(int)
        '_ZN15CMissionManager9needGuideEi',                     // needGuide(int)
        '_ZN15CMissionManager11IsNeedGuideEii',                 // IsNeedGuide(int,int)
        '_ZN15CMissionManager13AcceptMissionEv',                // AcceptMission()
        '_ZN15CMissionManager20AcceptNoGuideMissionEv',         // AcceptNoGuideMission()
        '_ZN15CMissionManager20MainScreenShowSpriteEP8ngButtonP8ngScreeniiiih',  // MainScreenShowSprite(...)
        '_ZN15CMissionManager17OnReceiveResponseEiPv',          // OnReceiveResponse(int, void*)
        '_ZN11CMainScreen15InitMissionInfoEv',                  // InitMissionInfo()
        '_ZN11CMainScreen17ShowMissionScreenEv',                // ShowMissionScreen()
        '_ZN11CMainScreen19UpdateMissionStatusEi',              // UpdateMissionStatus(int)
        '_ZN11CMainScreen23ShowMissionFinishScreenEv',          // ShowMissionFinishScreen()
        '_ZN11CMainScreen21ClearAllMissionSpriteEP6ngView',     // ClearAllMissionSprite(ngView*)
        '_ZN12ngHttpClient13ParseResponseExPv',                 // ngHttpClient::ParseResponse(long long, void*)
    ]);

    // --- Counters ---
    let missionReadCount = 0;
    const visitedSeqs = new Set();

    // CMission::Read(ngFileReader*) — fires once per record loaded from mission.city
    if (syms['_ZN8CMission4ReadEP12ngFileReader']) {
        Interceptor.attach(syms['_ZN8CMission4ReadEP12ngFileReader'], {
            onEnter(args) {
                this.this_ = args[0];
            },
            onLeave(retval) {
                missionReadCount++;
                // Try to read first 4 bytes of the CMission object — typically `id`
                // (CMission::Read reads BE32 id first per .city loader pattern).
                let id = 'n/a';
                try { id = this.this_.readU32(); } catch (e) {}
                if (missionReadCount <= 35) {
                    log('CMission::Read   #' + missionReadCount + '   id@+0=' + id + '   this=' + this.this_);
                }
            }
        });
    }

    // CMissionManager::GetMission() — returns CMission* (NULL if missionId not in table)
    if (syms['_ZN15CMissionManager10GetMissionEv']) {
        Interceptor.attach(syms['_ZN15CMissionManager10GetMissionEv'], {
            onLeave(retval) {
                const r = retval.toInt32();
                const tag = (r === 0) ? 'NULL <== empty mascot proof' : ('CMission*=' + retval);
                log('GetMission()    -> ' + tag);
            }
        });
    }

    // CMissionManager::ShowMission()
    if (syms['_ZN15CMissionManager11ShowMissionEv']) {
        Interceptor.attach(syms['_ZN15CMissionManager11ShowMissionEv'], {
            onEnter() { log('ShowMission()   <- entered'); }
        });
    }

    // IsInThisMission(int missionId) — predicate the screen asks
    if (syms['_ZN15CMissionManager15IsInThisMissionEi']) {
        Interceptor.attach(syms['_ZN15CMissionManager15IsInThisMissionEi'], {
            onEnter(args) { this.mid = args[1].toInt32(); },
            onLeave(retval) { log('IsInThisMission(' + this.mid + ') -> ' + retval.toInt32()); }
        });
    }
    if (syms['_ZN15CMissionManager9IsMissionEi']) {
        Interceptor.attach(syms['_ZN15CMissionManager9IsMissionEi'], {
            onEnter(args) { this.mid = args[1].toInt32(); },
            onLeave(retval) { log('IsMission(' + this.mid + ')         -> ' + retval.toInt32()); }
        });
    }
    if (syms['_ZN15CMissionManager9needGuideEi']) {
        Interceptor.attach(syms['_ZN15CMissionManager9needGuideEi'], {
            onEnter(args) { this.mid = args[1].toInt32(); },
            onLeave(retval) { log('needGuide(' + this.mid + ')          -> ' + retval.toInt32()); }
        });
    }

    if (syms['_ZN11CMainScreen15InitMissionInfoEv']) {
        Interceptor.attach(syms['_ZN11CMainScreen15InitMissionInfoEv'], {
            onEnter() { log('CMainScreen::InitMissionInfo() <- entered'); }
        });
    }
    if (syms['_ZN11CMainScreen17ShowMissionScreenEv']) {
        Interceptor.attach(syms['_ZN11CMainScreen17ShowMissionScreenEv'], {
            onEnter() { log('CMainScreen::ShowMissionScreen() <- entered'); }
        });
    }
    if (syms['_ZN11CMainScreen19UpdateMissionStatusEi']) {
        Interceptor.attach(syms['_ZN11CMainScreen19UpdateMissionStatusEi'], {
            onEnter(args) { this.s = args[1].toInt32(); },
            onLeave(_)    { log('CMainScreen::UpdateMissionStatus(' + this.s + ')'); }
        });
    }

    // ngHttpClient::ParseResponse(long long, void*) — fired for every HTTP
    // response (after cipher decode). The second arg is the response data
    // object; the first is a sequence/command id. Just log the id so we
    // can correlate with server-side dump.
    if (syms['_ZN12ngHttpClient13ParseResponseExPv']) {
        Interceptor.attach(syms['_ZN12ngHttpClient13ParseResponseExPv'], {
            onEnter(args) {
                // arg0=this (Frida thiscall on ARM passes 'this' in r0 only for member fns;
                // since the symbol is normal _ZN..., args[0]=this, args[1]=long long lo,
                // args[2]=long long hi, args[3]=void*). On 32-bit ARM, long long is split.
                const seq = args[1].toInt32();
                if (!visitedSeqs.has(seq)) {
                    visitedSeqs.add(seq);
                    log('ngHttpClient::ParseResponse seq=' + seq + ' (first time)');
                }
            }
        });
    }
    if (syms['_ZN15CMissionManager17OnReceiveResponseEiPv']) {
        Interceptor.attach(syms['_ZN15CMissionManager17OnReceiveResponseEiPv'], {
            onEnter(args) { this.cmd = args[1].toInt32(); },
            onLeave(_)    { log('CMissionManager::OnReceiveResponse(cmd=' + this.cmd + ')'); }
        });
    }

    log('all hooks installed; missionReadCount runs to reveal mission.city entry count');

    // Periodic summary
    let lastCount = 0;
    setInterval(function () {
        if (missionReadCount !== lastCount) {
            log('--- summary: CMission::Read count = ' + missionReadCount + ' ---');
            lastCount = missionReadCount;
        }
    }, 3000);
}, 100);
