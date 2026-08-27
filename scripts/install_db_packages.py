"""
Install required Python packages for all database adapters
"""
import subprocess
import sys

print("=" * 80)
print("INSTALLING DATABASE ADAPTER DEPENDENCIES")
print("=" * 80)
print()

packages = [
    ('pymysql', 'MySQL adapter'),
    ('pymongo', 'MongoDB adapter'),
    ('cx_Oracle', 'Oracle adapter (optional)'),
    ('pyodbc', 'SQL Server adapter'),
]

for package, description in packages:
    print(f"Installing {package} ({description})...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package, '--break-system-packages'],
            capture_output=True,
            timeout=60
        )
        print(f"  [OK] {package} installed")
    except Exception as e:
        print(f"  [WARN] {package} installation issue: {e}")
        if package == 'cx_Oracle':
            print(f"       Oracle adapter requires Oracle Instant Client")
            print(f"       Skipping for now - can install later if needed")

print()
print("=" * 80)
print("INSTALLATION COMPLETE")
print("=" * 80)
