# Signs every .exe, .dll and .pyd in a folder that doesn't already carry a valid signature.
# Smart App Control checks each program file Windows loads, not just Sankalan.exe, so all of them
# are signed. Files already signed by their makers (e.g. Python, Qt) are left as they are.
# Usage: powershell -ExecutionPolicy Bypass -File packaging\sign_files.ps1 -Folder dist\Sankalan -Pfx cert.pfx -Password ****
param(
  [Parameter(Mandatory = $true)][string]$Folder,
  [Parameter(Mandatory = $true)][string]$Pfx,
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$Timestamp = "http://timestamp.digicert.com"
)
$ErrorActionPreference = "Stop"
$files = Get-ChildItem -Path $Folder -Recurse -Include *.exe, *.dll, *.pyd -File
$toSign = @()
foreach ($f in $files) {
  $sig = Get-AuthenticodeSignature -FilePath $f.FullName
  if ($sig.Status -ne "Valid") { $toSign += $f.FullName }
}
Write-Host ("{0} program files found, {1} need signing" -f $files.Count, $toSign.Count)
$batch = 50
for ($i = 0; $i -lt $toSign.Count; $i += $batch) {
  $chunk = $toSign[$i..([Math]::Min($i + $batch, $toSign.Count) - 1)]
  & signtool sign /fd SHA256 /td SHA256 /tr $Timestamp /f $Pfx /p $Password $chunk
  if ($LASTEXITCODE -ne 0) { throw "signtool failed" }
}
$bad = Get-ChildItem -Path $Folder -Recurse -Include *.exe, *.dll, *.pyd -File |
  Where-Object { (Get-AuthenticodeSignature -FilePath $_.FullName).Status -ne "Valid" }
if ($bad) { $bad | ForEach-Object { Write-Host "Not signed: $($_.FullName)" }; exit 1 }
Write-Host "All program files are signed."
