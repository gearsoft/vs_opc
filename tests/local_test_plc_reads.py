#!/usr/bin/env python3
"""
Local read-only PLC smoke test.

- Registers tags in the existing TagStore.
- Opens the PLC drivers (uses the same driver classes the gateway uses if available).
- Performs N reads (reads only, no writes).
- Prints TagStore values each cycle.
- Removes tags and closes drivers.

This script hard-codes the PLC IPs you provided. Run only on your network
and with permission to query these PLCs. It is read-only.
"""
import time
import sys
import json
import argparse
import logging
from pathlib import Path
from pprint import pprint

# Hard-coded PLC IPs (from user)
COMPACTLOGIX_IP = '192.168.32.201'  # MCP5: CompactLogix L35E
SLC500_IP = '192.168.32.146'        # Mogul1 Depositor SLC 5/05

try:
    # import gateway helper pieces
    from vs_opc.plc_gateway_server import tag_store, read_compactlogix_tags, read_slc500_tags
    try:
        from vs_opc.plc_gateway_server import LogixDriver, SLCDriver
    except Exception:
        LogixDriver = None
        SLCDriver = None
except Exception:
    # Fallback: import TagStore directly if gateway not importable
    try:
        from vs_opc.tag_store import TagStore
        tag_store = TagStore()
    except Exception:
        print("Failed to import TagStore from project; aborting.")
        raise

from vs_opc.models import Tag

# CLI flags
parser = argparse.ArgumentParser(description='Local read-only PLC smoke test')
parser.add_argument('--no-cleanup', action='store_true', help='Do not remove tags from TagStore at the end')
parser.add_argument('--quiet', '-q', action='store_true', help='Reduce console output (suppress per-cycle dumps)')
# allow unknown args when imported in other contexts
args, _ = parser.parse_known_args()

# Reduce pycomm3 verbosity by default; make stricter if --quiet passed
logging.getLogger('pycomm3').setLevel(logging.WARNING)
if args.quiet:
    logging.getLogger('pycomm3').setLevel(logging.ERROR)
    logging.getLogger().setLevel(logging.WARNING)

# runtime flags
NO_CLEANUP = bool(args.no_cleanup)
QUIET = bool(args.quiet)


def safe_open(driver, name):
    try:
        if driver is None:
            print(f"No driver class for {name}; skipping open")
            return False
        if hasattr(driver, 'open'):
            driver.open()
        return True
    except Exception as e:
        print(f"[WARN] Failed to open driver {name}: {e}", file=sys.stderr)
        return False


def safe_close(driver, name):
    try:
        if driver is None:
            return
        if hasattr(driver, 'close'):
            driver.close()
    except Exception as e:
        print(f"[WARN] Failed to close driver {name}: {e}", file=sys.stderr)


def main():
    compact_plc_id = 'compactlogix'
    slc_plc_id = 'slc500'

    # Load PLC/tag configuration from tests/plc_config.json
    cfg_path = Path(__file__).resolve().parent / 'plc_config.json'
    if not cfg_path.exists():
        print(f"Config file {cfg_path} not found; aborting")
        return
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))

    # keep a mapping of plc_id -> driver instance
    drivers = {}
    # track tag ids we add from the config so cleanup can remove them deterministically
    added_tags = []

    for plc in cfg.get('plcs', []):
        pid = plc.get('plc_id')
        host = plc.get('host')
        ptype = plc.get('type', '').lower()
        # register tags for this PLC
        for t in plc.get('tags', []):
            tag = Tag(
                tag_id=t.get('tag_id'),
                name=t.get('name') or t.get('tag_id'),
                plc_id=pid,
                address=t.get('address'),
                data_type=t.get('data_type', 'Double'),
                scale_mul=float(t.get('scale_mul', 1.0)),
                scale_add=float(t.get('scale_add', 0.0)),
                # support both 'decimals' (short) and legacy 'decimal_places'
                decimals=(None if t.get('decimals') is None else int(t.get('decimals')))
                if t.get('decimals') is not None else (
                    (int(t.get('decimal_places')) if t.get('decimal_places') is not None else None)
                ),
                description=t.get('description'),
            )
            tag_store.add_tag(tag, initial_value=t.get('initial_value', None))
            # remember we added this tag so we can remove it at the end
            added_tags.append(tag.tag_id)

        # instantiate driver objects for each PLC if classes are available
        drv = None
        try:
            if 'compact' in ptype and LogixDriver is not None:
                drv = LogixDriver(host)
            elif 'slc' in ptype and SLCDriver is not None:
                drv = SLCDriver(host)
        except Exception as e:
            print(f"Failed to instantiate driver for {pid}@{host}: {e}")
            drv = None
        drivers[pid] = {'type': ptype, 'host': host, 'driver': drv}

    if not QUIET:
        print('Tags added to TagStore:')
        pprint(tag_store.list_tags())

    # Open all drivers we instantiated from the config
    for pid, info in drivers.items():
        drv = info.get('driver')
        host = info.get('host')
        print(f"Opening driver for {pid} @ {host} ...")
        safe_open(drv, pid)

    # Perform 20 reads
    N = 20
    delay = 1.0
    for i in range(N):
        print(f"\nCycle {i+1}/{N}")
        # For each configured PLC invoke the appropriate read helper
        for pid, info in drivers.items():
            drv = info.get('driver')
            ptype = info.get('type', '')
            try:
                if 'compact' in ptype and drv is not None:
                    read_compactlogix_tags(drv)
                elif 'slc' in ptype and drv is not None:
                    read_slc500_tags(drv)
            except Exception as e:
                print(f"[ERROR] read failed for {pid}: {e}", file=sys.stderr)

        # Build a dynamic snapshot of all tags currently registered in TagStore
        vals = {}
        for tmeta in tag_store.list_tags():
            tid = tmeta.get('tag_id')
            try:
                vals[tid] = tag_store.get_value(tid)
            except Exception:
                vals[tid] = None
        if not QUIET:
            pprint(vals)

        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            print('Interrupted by user')
            break

    # Cleanup
    if NO_CLEANUP:
        print('\nSkipping tag removal from TagStore (--no-cleanup)')
    else:
        print('\nRemoving tags from TagStore...')
        # remove only the tags we added from the config file
        for tid in added_tags:
            try:
                tag_store.remove_tag(tid)
            except Exception as e:
                print(f"[WARN] failed to remove tag {tid}: {e}")
        if not QUIET:
            print('Remaining tags:', tag_store.list_tags())

    print('Closing drivers...')
    # Close any drivers we created from the config
    for pid, info in drivers.items():
        safe_close(info.get('driver'), pid)
    print('Done.')


if __name__ == '__main__':
    main()
