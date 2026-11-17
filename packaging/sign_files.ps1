# Signs Sankalan's program files so Smart App Control lets them run (T2, T3), then checks every one.
#
#   sign_files.ps1 -Path dist\Sankalan                 every unsigned .exe/.dll/.pyd in the folder
#   sign_files.ps1 -Path dist\Sankalan-Setup-2.0.0.exe one file (the installer, the uninstaller)
#   sign_files.ps1 -Path dist\Sankalan -VerifyOnly     check only: exit 1 if any file isn't validly signed
#
# The certificate: an RSA OV code-signing certificate (Smart App Control doesn't accept ECC). Give either
#   -Thumbprint <SHA-1 thumbprint>   the certificate in the Windows store / on the USB token (the usual case), or
#   -Pfx <file> -Password <text>     a .pfx file (test certificates only).
# Defaults come from SANKALAN_SIGN_THUMBPRINT, SANKALAN_PFX, SANKALAN_PFX_PASSWORD and SANKALAN_TIMESTAMP_URL.
# Each signature is timestamped by the CA's timestamp server, so the build PC needs internet while signing; the app
# itself stays offline. Files their makers already signed (Python, Qt) are left as they are.
param(
  [Parameter(Mandatory = $true)][string]$Path,
  [string]$Thumbprint = $env:SANKALAN_SIGN_THUMBPRINT,
  [string]$Pfx = $env:SANKALAN_PFX,
  [string]$Password = $env:SANKALAN_PFX_PASSWORD,
  [string]$Timestamp = $(if ($env:SANKALAN_TIMESTAMP_URL) { $env:SANKALAN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }),
  [switch]$VerifyOnly
)
$ErrorActionPreference = "Stop"

function Get-ProgramFiles([string]$p) {
  if (Test-Path -LiteralPath $p -PathType Leaf) { return @(Get-Item -LiteralPath $p) }
  return @(Get-ChildItem -LiteralPath $p -Recurse -File | Where-Object { $_.Extension -in ".exe", ".dll", ".pyd" })
}

function Find-SignTool {
  $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $kits = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
  $found = Get-ChildItem -LiteralPath $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\x64\\" } | Sort-Object FullName -Descending | Select-Object -First 1
  if ($found) { return $found.FullName }
  throw "signtool.exe not found: install the Windows SDK signing tools or put signtool on PATH."
}

$files = Get-ProgramFiles $Path
$ourThumb = $Thumbprint
if (-not $ourThumb -and $Pfx) {
  $ourThumb = (New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($Pfx, $Password)).Thumbprint
}
if (-not $VerifyOnly) {
  if (-not $Thumbprint -and -not $Pfx) { throw "No certificate: give -Thumbprint or -Pfx (or set SANKALAN_SIGN_THUMBPRINT)." }
  $toSign = @($files | Where-Object { (Get-AuthenticodeSignature -LiteralPath $_.FullName).Status -ne "Valid" } |
    ForEach-Object { $_.FullName })
  Write-Host ("{0} program files found, {1} need signing" -f $files.Count, $toSign.Count)
  $signtool = Find-SignTool
  $cert = if ($Thumbprint) { @("/sha1", $Thumbprint) } else { @("/f", $Pfx, "/p", $Password) }
  $batch = 50
  for ($i = 0; $i -lt $toSign.Count; $i += $batch) {
    $chunk = $toSign[$i..([Math]::Min($i + $batch, $toSign.Count) - 1)]
    & $signtool sign /fd SHA256 /td SHA256 /tr $Timestamp @cert $chunk
    if ($LASTEXITCODE -ne 0) { throw "signtool failed" }
  }
}

# Verify: every program file validly signed; the files we signed carry an RSA certificate and a timestamp.
$bad = @()
foreach ($f in $files) {
  $sig = Get-AuthenticodeSignature -LiteralPath $f.FullName
  if ($sig.Status -ne "Valid") { $bad += "Not signed: $($f.FullName)"; continue }
  $ours = ($ourThumb -and $sig.SignerCertificate.Thumbprint -eq $ourThumb)
  if ($ours -and $sig.SignerCertificate.PublicKey.Oid.FriendlyName -ne "RSA") { $bad += "Not RSA: $($f.FullName)" }
  if ($ours -and -not $sig.TimeStamperCertificate) { $bad += "No timestamp: $($f.FullName)" }
}
if ($bad) { $bad | ForEach-Object { Write-Host $_ }; exit 1 }
Write-Host ("All {0} program files are signed." -f $files.Count)
exit 0
