# Adapter Installation Script
# Run this to copy all adapter files to the correct location

import shutil
import os

print("=" * 70)
print("INSTALLING CDC ADAPTERS")
print("=" * 70)
print()

source_dir = r"C:\Users\03-134222-111\Downloads"  # Adjust if needed
target_dir = r"C:\Projects\CareLock-Sync\backend\cdc"

adapters = [
    'oracle_adapter.py',
    'sqlserver_adapter.py',
    'mysql_adapter.py',
    'mongodb_adapter.py'
]

installed = []
errors = []

for adapter in adapters:
    source = os.path.join(source_dir, adapter)
    target = os.path.join(target_dir, adapter)
    
    # Check if file exists in downloads
    if os.path.exists(source):
        try:
            shutil.copy2(source, target)
            print(f"[OK] {adapter} -> {target}")
            installed.append(adapter)
        except Exception as e:
            print(f"[ERROR] {adapter}: {e}")
            errors.append(adapter)
    else:
        print(f"[SKIP] {adapter} not found in {source_dir}")
        print(f"       (Will use file from outputs folder)")

print()
print("=" * 70)
print(f"INSTALLATION COMPLETE: {len(installed)}/{len(adapters)} adapters")
print("=" * 70)

if installed:
    print("\nInstalled:")
    for adapter in installed:
        print(f"  ✓ {adapter}")

if errors:
    print("\nErrors:")
    for adapter in errors:
        print(f"  ✗ {adapter}")

print()
print("Next: Run validation test")
print("  python scripts\\pre_demo_validation.py")
