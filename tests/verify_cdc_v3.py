"""
CareLock CDC Monitor v3 — Comprehensive Test Runner & Verifier
===============================================================

This script:
1. Verifies all 9 risks are addressed in the code
2. Runs both test files (unit + performance)
3. Produces a detailed risk-by-risk report
4. Shows test coverage for each risk

Run:
    python tests\verify_cdc_v3.py

Or just the unit tests:
    pytest tests\unit\test_cdc_monitor.py -v

Or just the performance tests:
    pytest tests\unit\test_cdc_performance.py -v -s
"""
import os
import sys
import subprocess
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# ── Colors (Windows-safe) ─────────────────────────────────────────────────────
try:
    import colorama
    colorama.init()
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = ""

def green(s):  return f"{GREEN}{s}{RESET}"
def red(s):    return f"{RED}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"
def cyan(s):   return f"{CYAN}{s}{RESET}"

# ── Risk verification against code ────────────────────────────────────────────

RISKS = {
    1: {
        "title": "Per-row SELECT cost",
        "fix": "current_setting('app.tenant_id', true) with _cdc_config fallback",
        "code_markers": [
            ("connector/cdc_monitor.py", "current_setting('app.tenant_id', true)"),
            ("connector/cdc_monitor.py", "def set_session_tenant"),
        ],
        "tests": [
            "test_cdc_monitor.py::TestTenantTracking::test_tenant_id_in_change_row",
            "test_cdc_performance.py::TestHighVolumeBurst::test_burst_tenant_id_consistent",
        ]
    },
    2: {
        "title": "DROP … CASCADE in setup",
        "fix": "Query pg_trigger to find dependents, drop them first, then DROP FUNCTION without CASCADE",
        "code_markers": [
            ("connector/cdc_monitor.py", "SELECT t.tgname, c.relname"),
            ("connector/cdc_monitor.py", "DROP TRIGGER IF EXISTS"),
            ("connector/cdc_monitor.py", "DROP FUNCTION IF EXISTS log_data_change();"),
        ],
        "tests": [
            "test_cdc_monitor.py::TestSchema::test_no_legacy_log_data_change_function",
        ]
    },
    3: {
        "title": "Large batches & memory",
        "fix": "iter_changes_since() with server-side cursor (psycopg2 named cursor, fetchmany)",
        "code_markers": [
            ("connector/cdc_monitor.py", "def iter_changes_since"),
            ("connector/cdc_monitor.py", "raw_conn.cursor(cursor_name)"),
            ("connector/cdc_monitor.py", "cur.fetchmany(batch_size)"),
        ],
        "tests": [
            "test_cdc_performance.py::TestStreamingGenerator::test_streaming_yields_correct_total",
            "test_cdc_performance.py::TestStreamingGenerator::test_streaming_ordered_asc",
            "test_cdc_performance.py::TestStreamingGenerator::test_eager_batch_size_respected",
        ]
    },
    4: {
        "title": "Watermark advancement on partial failures",
        "fix": "advance_watermark() with GREATEST() logic, only called after successful batch",
        "code_markers": [
            ("connector/cdc_monitor.py", "cdc_watermarks"),
            ("connector/cdc_monitor.py", "GREATEST("),
            ("connector/cdc_monitor.py", "def advance_watermark"),
        ],
        "tests": [
            "test_cdc_performance.py::TestWatermarkPersistence::test_advance_never_goes_backwards",
            "test_cdc_performance.py::TestConcurrentWriters::test_concurrent_watermark_advance_is_safe",
        ]
    },
    5: {
        "title": "Migration locking & downtime",
        "fix": "migrate_schema() with lock_timeout = '5s', skip if already TEXT, pg_repack guidance",
        "code_markers": [
            ("connector/cdc_monitor.py", "def migrate_schema"),
            ("connector/cdc_monitor.py", "lock_timeout = '5s'"),
            ("connector/cdc_monitor.py", "ALTER COLUMN record_id TYPE TEXT"),
        ],
        "tests": [
            "test_cdc_monitor.py::TestSchema::test_record_id_is_text",
        ]
    },
    6: {
        "title": "Per-tenant scheduler state",
        "fix": "cdc_watermarks table with tenant_id PRIMARY KEY, atomic ON CONFLICT DO UPDATE",
        "code_markers": [
            ("connector/cdc_monitor.py", "CREATE TABLE IF NOT EXISTS cdc_watermarks"),
            ("connector/cdc_monitor.py", "tenant_id     INTEGER     PRIMARY KEY"),
            ("connector/cdc_monitor.py", "ON CONFLICT (tenant_id) DO UPDATE"),
        ],
        "tests": [
            "test_cdc_performance.py::TestWatermarkPersistence::test_watermark_isolated_per_tenant",
            "test_cdc_performance.py::TestWatermarkPersistence::test_load_returns_zero_for_new_tenant",
        ]
    },
    7: {
        "title": "Trigger permissions & RLS",
        "fix": "SECURITY DEFINER on log_table_changes, GRANT EXECUTE TO PUBLIC",
        "code_markers": [
            ("connector/cdc_monitor.py", "SECURITY DEFINER"),
            ("connector/cdc_monitor.py", "GRANT EXECUTE ON FUNCTION log_table_changes() TO PUBLIC"),
        ],
        "tests": [
            "test_cdc_monitor.py::TestSchema::test_canonical_trigger_function_exists",
        ]
    },
    8: {
        "title": "pg_notify payload completeness",
        "fix": "pg_notify uses tenant_id_value from GUC fast-path, includes timestamp ISO 8601",
        "code_markers": [
            ("connector/cdc_monitor.py", "PERFORM pg_notify"),
            ("connector/cdc_monitor.py", "'tenant_id', tenant_id_value"),
            ("connector/cdc_monitor.py", "to_char(NOW(),"),
        ],
        "tests": [
            # Notification tests would require LISTEN/NOTIFY setup - covered by manual testing
        ]
    },
    9: {
        "title": "Concurrency & performance tests",
        "fix": "test_cdc_performance.py with 5 test groups covering all scenarios",
        "code_markers": [
            ("tests/unit/test_cdc_performance.py", "class TestHighVolumeBurst"),
            ("tests/unit/test_cdc_performance.py", "class TestConcurrentWriters"),
            ("tests/unit/test_cdc_performance.py", "class TestStreamingGenerator"),
            ("tests/unit/test_cdc_performance.py", "class TestIndexUtilization"),
            ("tests/unit/test_cdc_performance.py", "class TestWatermarkPersistence"),
        ],
        "tests": [
            "test_cdc_performance.py::TestHighVolumeBurst",
            "test_cdc_performance.py::TestConcurrentWriters",
            "test_cdc_performance.py::TestStreamingGenerator",
            "test_cdc_performance.py::TestIndexUtilization",
            "test_cdc_performance.py::TestWatermarkPersistence",
        ]
    },
}

def verify_code_markers():
    """Check that each risk's fix is present in the code."""
    print("\n" + "=" * 70)
    print("  RISK VERIFICATION — Code Markers")
    print("=" * 70)
    
    all_ok = True
    for risk_num, risk in RISKS.items():
        print(f"\n{cyan(f'Risk {risk_num}')}: {risk['title']}")
        print(f"  Fix: {risk['fix']}")
        
        for filepath, marker in risk["code_markers"]:
            full_path = ROOT / filepath
            if not full_path.exists():
                print(f"  {red('✗')} File not found: {filepath}")
                all_ok = False
                continue
            
            with open(full_path, encoding="utf-8") as f:
                content = f.read()
            
            if marker in content:
                print(f"  {green('✓')} Found: {marker[:60]}...")
            else:
                print(f"  {red('✗')} Missing: {marker}")
                all_ok = False
    
    return all_ok

def run_tests():
    """Run pytest on both test files."""
    print("\n" + "=" * 70)
    print("  RUNNING TESTS")
    print("=" * 70)
    
    test_files = [
        "tests/unit/test_cdc_monitor.py",
        "tests/unit/test_cdc_performance.py",
    ]
    
    results = {}
    for test_file in test_files:
        print(f"\n{cyan('Running')}: {test_file}")
        cmd = ["pytest", test_file, "-v", "--tb=short", "-x"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        
        results[test_file] = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        
        if result.returncode == 0:
            print(f"{green('✓ PASS')}")
        else:
            print(f"{red('✗ FAIL')}")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    
    return results

def show_summary(code_ok, test_results):
    """Print final summary."""
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    print(f"\n{cyan('Code Verification')}:")
    if code_ok:
        print(f"  {green('✓ All 9 risks addressed in code')}")
    else:
        print(f"  {red('✗ Some risk fixes missing in code')}")
    
    print(f"\n{cyan('Test Execution')}:")
    all_pass = all(r["returncode"] == 0 for r in test_results.values())
    
    for test_file, result in test_results.items():
        name = Path(test_file).name
        if result["returncode"] == 0:
            print(f"  {green('✓')} {name}")
        else:
            print(f"  {red('✗')} {name}")
    
    print("\n" + "=" * 70)
    if code_ok and all_pass:
        print(f"  {green('✓✓✓ ALL VERIFICATIONS PASSED ✓✓✓')}")
    elif code_ok:
        print(f"  {yellow('Code OK but tests failed — check PostgreSQL connection')}")
    else:
        print(f"  {red('Verification failed — see details above')}")
    print("=" * 70)
    
    print(f"\n{cyan('Test Coverage by Risk')}:")
    for risk_num, risk in RISKS.items():
        print(f"\n  Risk {risk_num}: {risk['title']}")
        for test in risk["tests"]:
            if any(test in r["stdout"] for r in test_results.values()):
                print(f"    {green('✓')} {test}")
            else:
                print(f"    {yellow('○')} {test} (not in output)")
    
    return code_ok and all_pass

def main():
    print(cyan("\n╔════════════════════════════════════════════════════════════════╗"))
    print(cyan("║  CareLock CDC Monitor v3 — Comprehensive Verification         ║"))
    print(cyan("╚════════════════════════════════════════════════════════════════╝"))
    
    # Step 1: Verify code
    code_ok = verify_code_markers()
    
    # Step 2: Run tests
    test_results = run_tests()
    
    # Step 3: Summary
    success = show_summary(code_ok, test_results)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
