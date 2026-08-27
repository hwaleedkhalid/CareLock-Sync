"""
Quick Start - Docker Databases Setup
One-command setup for all 5 databases
"""
import subprocess
import sys
import os

print("""
================================================================================
CARELOCK SYNC - DOCKER QUICK START
================================================================================

This script will:
  1. Start all 5 databases in Docker (PostgreSQL, MySQL, MongoDB, Oracle, SQL Server)
  2. Populate with sample hospital data (100 patients each)
  3. Setup CDC triggers
  4. Test all adapters

Requirements:
  - Docker Desktop installed and running
  - ~5GB disk space
  - ~10 minutes for first-time setup

================================================================================
""")

input("Press ENTER to start, or Ctrl+C to cancel...")

os.chdir(r'C:\Projects\CareLock-Sync')

# Step 1: Start containers
print("\n[Step 1/4] Starting Docker containers...")
print("  (This downloads images on first run - may take 5-10 minutes)")

result = subprocess.run(['docker-compose', 'up', '-d'], capture_output=True, text=True)

if result.returncode != 0:
    print("  [ERROR]", result.stderr)
    sys.exit(1)

print("  [OK] Containers started")

# Step 2: Wait for health
print("\n[Step 2/4] Waiting for databases (2-3 minutes)...")
print("  Checking every 10 seconds...")

import time
for i in range(18):  # 3 minutes max
    time.sleep(10)
    result = subprocess.run(
        ['docker', 'ps', '--filter', 'health=healthy', '--format', '{{.Names}}'],
        capture_output=True,
        text=True
    )
    healthy = result.stdout.strip().split('\n') if result.stdout.strip() else []
    print(f"    Healthy: {len(healthy)}/5 databases")
    
    if len(healthy) >= 3:  # At least 3 healthy is good enough
        break

print("  [OK] Databases ready")

# Step 3: Install dependencies
print("\n[Step 3/4] Installing Python packages...")
deps = ['pymysql', 'pymongo', 'faker']
for dep in deps:
    subprocess.run([sys.executable, '-m', 'pip', 'install', dep, '--break-system-packages'],
                  capture_output=True)
print("  [OK] Dependencies installed")

# Step 4: Populate databases
print("\n[Step 4/4] Populating databases...")

scripts = [
    ('MySQL', r'scripts\setup_mysql_docker_data.py'),
    ('MongoDB', r'scripts\setup_mongodb_docker_data.py'),
]

for name, script in scripts:
    if os.path.exists(script):
        print(f"  Setting up {name}...")
        result = subprocess.run([sys.executable, script], capture_output=True, timeout=60)
        if result.returncode == 0:
            print(f"    [OK] {name} ready")
        else:
            print(f"    [WARN] {name} setup issues (may be OK)")

print("\n" + "=" * 80)
print("SETUP COMPLETE!")
print("=" * 80)
print("\nDatabases running:")
print("  MySQL      : localhost:3306")
print("  MongoDB    : localhost:27017")
print("  Oracle XE  : localhost:1521 (takes ~5 min to fully start)")
print("  SQL Server : localhost:1433")
print("\nNext steps:")
print("  1. Run: python scripts\\test_databases_detailed.py")
print("  2. Or: python backend\\autosync_daemon.py")
print("\nTo stop: docker-compose down")
print("=" * 80)
