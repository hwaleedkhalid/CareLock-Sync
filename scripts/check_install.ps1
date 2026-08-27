$py = "C:\Projects\CareLock-Sync\venv\Scripts\python.exe"
$ver = & $py "--version" 2>&1
Write-Output "PY: $ver"
$pkgs = & $py "-m" "pip" "list" "--format" "columns" 2>&1
$chroma = $pkgs | Where-Object { $_ -match "chromadb" }
Write-Output "CHROMADB: $chroma"
if (-not $chroma) {
    Write-Output "Installing chromadb..."
    & $py "-m" "pip" "install" "chromadb" "--no-warn-script-location" 2>&1 | Write-Output
    Write-Output "Done."
}
