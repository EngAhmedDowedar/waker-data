"""
Waker (وكر الاوغاد) - Binary Patcher for libcity_ar.so

Patches the native library to redirect all server URLs to a configurable host.
Works regardless of what the .so is currently patched to — it finds URLs by
their path suffix (the part after the host), which is stable across patches.

Usage:
    python patch_so.py --server-host 192.168.1.3
    python patch_so.py --server-host waker.local
    python patch_so.py --server-host my-vps.example.com

Max hostname length: 24 characters (limited by the tightest .rodata slot).
"""

import os
import sys
import re
import shutil
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT = os.path.join(PROJECT_DIR, 'client-apk-src', 'lib', 'armeabi', 'libcity_ar.so')
DEFAULT_OUTPUT = DEFAULT_INPUT

DEFAULT_SERVER_HOST = '192.168.1.3'
MAX_HOST_LEN = 24

# Each URL slot is identified by its path suffix and port. The slot size is
# the length of the ORIGINAL string (before any patching), which is the max
# we can write. We find the current URL by regex and replace it.
URL_SLOTS = [
    # (name, port, path_suffix, original_full_length)
    ('Main API Server',      8080, '/',                       37),  # http://city-arab.anansigame.org:8080/
    ('Password Reset',       8080, '/page/pwdreset',          50),  # http://city-arab.anansigame.org:2095/page/pwdreset
    ('Analytics Server',     8992, '/logevent/weightevent',   55),  # http://appstat.anansicorp.org:8992/logevent/weightevent
    ('Resource Download',    8080, '/respkg/%s',              63),  # http://s3.amazonaws.com/.../respkg/%s
    ('Resource Pack',        8080, '/CityRes_005.zip',        49),  # http://www.sakhabgame.com/.../CityRes_005.zip
    ('FAQ/Help Page',        8080, '/helpfaq.html',           44),  # http://city.wiyun.com/.../helpfaq.html
    ('Privacy Policy',       8080, '/policy.html',            65),  # http://s3.amazonaws.com/.../policy.html
]


def patch_so(data, new_host):
    """Find each URL slot by its path suffix and replace the host portion."""
    applied = 0

    for name, port, path_suffix, orig_len in URL_SLOTS:
        # Build regex to find "http://<anything>:<port><path_suffix>" followed by \x00
        # The path_suffix for "/" needs special handling (it's a prefix of others)
        escaped_path = re.escape(path_suffix.encode('ascii'))
        if path_suffix == '/':
            pattern = rb'http://[^\x00]+?:' + str(port).encode() + rb'/' + rb'(?=\x00)'
        else:
            pattern = rb'http://[^\x00]+?:' + str(port).encode() + escaped_path

        match = re.search(pattern, data)
        if not match:
            print(f'  [--] {name}: URL slot not found')
            continue

        old_url = match.group(0)
        old_start = match.start()
        # Find the null terminator to get the full slot
        null_pos = data.find(b'\x00', old_start)
        slot_size = null_pos - old_start

        new_url = f'http://{new_host}:{port}{path_suffix}'.encode('ascii')
        if len(new_url) > orig_len:
            print(f'  [!!] {name}: new URL ({len(new_url)}B) exceeds '
                  f'original slot ({orig_len}B) — SKIPPED')
            continue

        padded = new_url.ljust(slot_size, b'\x00')
        data = data[:old_start] + padded + data[old_start + slot_size:]
        applied += 1
        print(f'  [OK] {name} @ 0x{old_start:x}:')
        print(f'       {old_url.decode("ascii", errors="replace")}')
        print(f'    -> {new_url.decode("ascii")}')

    return data, applied


def main():
    parser = argparse.ArgumentParser(
        description='Patch libcity_ar.so to redirect to a custom server host')
    parser.add_argument('--server-host', '--server-ip', default=DEFAULT_SERVER_HOST,
                        help=f'Hostname or IP to redirect to (default: {DEFAULT_SERVER_HOST}). '
                             f'Max {MAX_HOST_LEN} characters.')
    parser.add_argument('--input', '-i', default=DEFAULT_INPUT,
                        help='Input .so file path')
    parser.add_argument('--output', '-o', default=None,
                        help='Output .so file path (default: overwrite input)')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip creating a .bak backup file')
    args = parser.parse_args()

    host = args.server_host
    if len(host) > MAX_HOST_LEN:
        print(f'ERROR: Hostname "{host}" is {len(host)} chars; '
              f'max is {MAX_HOST_LEN} (limited by the tightest .rodata slot).')
        sys.exit(1)

    input_path = args.input
    output_path = args.output or input_path

    if not os.path.exists(input_path):
        print(f'ERROR: Input file not found: {input_path}')
        sys.exit(1)

    print('=' * 50)
    print('  Waker - libcity_ar.so Binary Patcher')
    print('=' * 50)
    print(f'  Input:       {input_path}')
    print(f'  Output:      {output_path}')
    print(f'  Server host: {host}')
    print('=' * 50)

    with open(input_path, 'rb') as f:
        data = f.read()
    print(f'  File size: {len(data)} bytes')
    print()

    print('Applying patches:')
    patched_data, applied = patch_so(data, host)

    print()
    print(f'Patches applied: {applied}/{len(URL_SLOTS)}')

    if applied == 0:
        print('No patches applied.')
        sys.exit(0)

    if not args.no_backup and input_path == output_path:
        backup_path = input_path + '.bak'
        if not os.path.exists(backup_path):
            shutil.copy2(input_path, backup_path)
            print(f'Backup saved: {backup_path}')

    with open(output_path, 'wb') as f:
        f.write(patched_data)
    print(f'Patched file written: {output_path}')
    print()
    print(f'Done! The game will connect to {host}:8080')
    if not host.replace('.', '').isdigit():
        print(f'Ensure "{host}" resolves to your server IP.')


if __name__ == '__main__':
    main()
