"""
Download and Install Oracle Instant Client
"""
import os
import urllib.request
import zipfile
import sys

print("=" * 80)
print("Oracle Instant Client Installation")
print("=" * 80)
print()

# Oracle Instant Client URL (Basic package for Windows 64-bit)
# Note: This is a direct download link to Oracle's official site
instant_client_url = "https://download.oracle.com/otn_software/nt/instantclient/2340000/instantclient-basic-windows.x64-23.4.0.24.05.zip"

download_dir = r"C:\oracle"
zip_file = os.path.join(download_dir, "instantclient.zip")

print(f"Installation directory: {download_dir}")
print()

# Create directory
if not os.path.exists(download_dir):
    os.makedirs(download_dir)
    print(f"[OK] Created directory: {download_dir}")
else:
    print(f"[OK] Directory exists: {download_dir}")

# Check if already installed
instant_client_dir = os.path.join(download_dir, "instantclient_23_4")
if os.path.exists(instant_client_dir):
    print(f"[OK] Oracle Instant Client already exists at: {instant_client_dir}")
    
    # Add to PATH
    current_path = os.environ.get('PATH', '')
    if instant_client_dir not in current_path:
        print("\n[ACTION REQUIRED] Add to System PATH:")
        print(f"  {instant_client_dir}")
        print("\nManual steps:")
        print("  1. Press Win + X")
        print("  2. Select 'System'")
        print("  3. Click 'Advanced system settings'")
        print("  4. Click 'Environment Variables'")
        print("  5. Under 'System variables', find 'Path'")
        print("  6. Click 'Edit'")
        print(f"  7. Add: {instant_client_dir}")
        print("  8. Click OK and restart terminal")
    else:
        print(f"[OK] Already in PATH")
    
    sys.exit(0)

print("\n[STEP 1] Downloading Oracle Instant Client...")
print(f"  URL: {instant_client_url}")
print(f"  This may take 2-3 minutes (file is ~80MB)...")

try:
    # Download with progress
    def download_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, (downloaded / total_size) * 100)
        print(f"\r  Progress: {percent:.1f}% ({downloaded/1024/1024:.1f} MB)", end='')
    
    urllib.request.urlretrieve(instant_client_url, zip_file, download_progress)
    print("\n  [OK] Download complete")
    
except Exception as e:
    print(f"\n  [ERROR] Download failed: {e}")
    print("\n  Manual download:")
    print(f"  1. Visit: https://www.oracle.com/database/technologies/instant-client/downloads.html")
    print(f"  2. Download 'Basic Package (ZIP)' for Windows 64-bit")
    print(f"  3. Extract to: {download_dir}")
    sys.exit(1)

print("\n[STEP 2] Extracting...")
try:
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(download_dir)
    print(f"  [OK] Extracted to: {download_dir}")
    
    # Clean up
    os.remove(zip_file)
    print(f"  [OK] Cleaned up ZIP file")
    
except Exception as e:
    print(f"  [ERROR] Extraction failed: {e}")
    sys.exit(1)

print("\n[STEP 3] Adding to PATH...")
print(f"\n  [ACTION REQUIRED] Add to System PATH:")
print(f"    {instant_client_dir}")
print("\n  Quick PowerShell command (run as Administrator):")
print(f'    $env:Path += ";{instant_client_dir}"')
print(f'    [Environment]::SetEnvironmentVariable("Path", $env:Path, "Machine")')

print("\n" + "=" * 80)
print("Installation Complete!")
print("=" * 80)
print("\nNext steps:")
print("  1. Add Instant Client to PATH (see above)")
print("  2. Restart terminal/PowerShell")
print("  3. Run: python scripts\\test_oracle_connection.py")
print()
print("=" * 80)
