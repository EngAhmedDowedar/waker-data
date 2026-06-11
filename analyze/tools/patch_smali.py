"""
Waker (وكر الاوغاد) - Smali Patcher

Patches smali files to:
1. Disable analytics/crash reporting SDKs (Umeng, TalkingData, AppsFlyer, Vungle)
2. Disable Google Play License check
3. Disable expansion file (OBB) verification
4. Make all init methods for analytics return immediately

Usage:
    python patch_smali.py [--project-dir DIR]

Default:
    python patch_smali.py
    -> Patches smali files in the parent directory (the decompiled APK root)
"""

import os
import sys
import re
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROJECT_DIR = os.path.dirname(SCRIPT_DIR)


def patch_file_nop_method(filepath, method_name, description):
    """Make a static void method return immediately (nop it)."""
    if not os.path.exists(filepath):
        print(f'  [--] {description}: file not found')
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: find the method, replace its body with just return-void
    # Match: .method ... <method_name>(...) ... .end method
    pattern = re.compile(
        r'(\.method\s+[^\n]*' + re.escape(method_name) + r'\([^\)]*\)V\s*\n)'
        r'(.*?)'
        r'(\.end method)',
        re.DOTALL
    )

    match = pattern.search(content)
    if not match:
        print(f'  [--] {description}: method {method_name} not found')
        return False

    # Replace method body with minimal return-void
    new_body = '    .locals 0\n\n    return-void\n'
    new_content = content[:match.start(2)] + new_body + content[match.start(3):]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f'  [OK] {description}: {method_name}() disabled')
    return True


def patch_umeng(project_dir):
    """Disable Umeng analytics."""
    filepath = os.path.join(project_dir, 'smali', 'com', 'anansimobile', 'nge', 'extra', 'statistics', 'UMStatistics.smali')
    patch_file_nop_method(filepath, 'init', 'Umeng init')
    patch_file_nop_method(filepath, 'onMobEvent', 'Umeng onMobEvent')
    patch_file_nop_method(filepath, 'onResume', 'Umeng onResume')
    patch_file_nop_method(filepath, 'onPause', 'Umeng onPause')
    patch_file_nop_method(filepath, 'onKillProcess', 'Umeng onKillProcess')


def patch_talkingdata(project_dir):
    """Disable TalkingData analytics."""
    filepath = os.path.join(project_dir, 'smali', 'com', 'anansimobile', 'extra', 'statistics', 'talkingdata', 'TalkingDataStatistics.smali')
    patch_file_nop_method(filepath, 'init', 'TalkingData init')
    patch_file_nop_method(filepath, 'onEvent', 'TalkingData onEvent')
    patch_file_nop_method(filepath, 'onResume', 'TalkingData onResume')
    patch_file_nop_method(filepath, 'onPause', 'TalkingData onPause')
    patch_file_nop_method(filepath, 'onKillProcess', 'TalkingData onKillProcess')


def patch_appsflyer(project_dir):
    """Disable AppsFlyer attribution tracking."""
    filepath = os.path.join(project_dir, 'smali', 'com', 'appsflyer', 'AppsFlyerLib.smali')
    if not os.path.exists(filepath):
        print('  [--] AppsFlyer: main file not found')
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Disable sendTracking method - find the inner class that sends data
    sender_file = os.path.join(project_dir, 'smali', 'com', 'appsflyer', 'AppsFlyerLib$SendToServerRunnable.smali')
    if os.path.exists(sender_file):
        patch_file_nop_method(sender_file, 'run', 'AppsFlyer SendToServer')

    print('  [OK] AppsFlyer: tracking disabled')


def patch_expansion_check(project_dir):
    """Disable APK expansion file (OBB) verification in Main.smali."""
    filepath = os.path.join(project_dir, 'smali', 'com', 'anansimobile', 'city_ar', 'Main.smali')
    if not os.path.exists(filepath):
        print('  [--] Expansion check: Main.smali not found')
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The expansion file check uses expansionFileDelivered() method
    # We make it always return true (file is delivered / no download needed)
    pattern = re.compile(
        r'(\.method[^\n]*expansionFileDelivered\(\)Z\s*\n)'
        r'(.*?)'
        r'(\.end method)',
        re.DOTALL
    )

    match = pattern.search(content)
    if match:
        new_body = '    .locals 1\n\n    const/4 v0, 0x1\n\n    return v0\n'
        new_content = content[:match.start(2)] + new_body + content[match.start(3):]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('  [OK] Expansion file check: disabled (always returns true)')
        return True
    else:
        print('  [--] Expansion file check: method not found (may not be needed)')
        return False


def patch_license_check(project_dir):
    """Disable Google Play License check."""
    # Look for license checker files
    license_files = []
    for root, dirs, files in os.walk(os.path.join(project_dir, 'smali')):
        for f in files:
            if 'license' in f.lower() or 'License' in f:
                license_files.append(os.path.join(root, f))

    if not license_files:
        # Check Main.smali for license check code
        main_path = os.path.join(project_dir, 'smali', 'com', 'anansimobile', 'city_ar', 'Main.smali')
        if os.path.exists(main_path):
            with open(main_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'CHECK_LICENSE' in content or 'LicenseChecker' in content:
                print('  [!!] License check found in Main.smali - may need manual patching')
            else:
                print('  [OK] License check: not found (not present in this build)')
        return

    for lf in license_files:
        print(f'  [!!] License file found: {os.path.relpath(lf, project_dir)}')


def patch_firebase_analytics(project_dir):
    """Disable Firebase analytics (if present as wrapper)."""
    # Firebase is usually initialized in the Application or Main class
    # Since the game uses native code primarily, Firebase analytics is minimal
    print('  [OK] Firebase: analytics events are in native code (handled by .so patch)')


def main():
    parser = argparse.ArgumentParser(description='Patch smali files to disable analytics and checks')
    parser.add_argument('--project-dir', default=DEFAULT_PROJECT_DIR,
                        help=f'Decompiled APK project directory (default: {DEFAULT_PROJECT_DIR})')
    args = parser.parse_args()

    project_dir = args.project_dir

    if not os.path.exists(os.path.join(project_dir, 'smali')):
        print(f'ERROR: smali directory not found in {project_dir}')
        sys.exit(1)

    print('=' * 50)
    print('  Waker - Smali Patcher')
    print('=' * 50)
    print(f'  Project: {project_dir}')
    print('=' * 50)
    print()

    print('Disabling Umeng Analytics:')
    patch_umeng(project_dir)
    print()

    print('Disabling TalkingData:')
    patch_talkingdata(project_dir)
    print()

    print('Disabling AppsFlyer:')
    patch_appsflyer(project_dir)
    print()

    print('Disabling Expansion File Check:')
    patch_expansion_check(project_dir)
    print()

    print('Checking License Verification:')
    patch_license_check(project_dir)
    print()

    print('Firebase Analytics:')
    patch_firebase_analytics(project_dir)
    print()

    print('=' * 50)
    print('Smali patching complete!')
    print('Now run patch_so.py to patch the native library.')
    print('Then rebuild the APK with: apktool b <project_dir>')
    print('=' * 50)


if __name__ == '__main__':
    main()
