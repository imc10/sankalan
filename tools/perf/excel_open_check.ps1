# AC-EXP-9a (Feature Spec A2 10.4; plan A2-6 step 3): every part of a split export opens in Excel with all its rows.
# Development only, like tests/fixtures/make_static_formats.ps1 (Excel COM). Never shipped.
#
#   powershell -NoProfile -File tools\perf\excel_open_check.ps1 -Expected <expected.json> -Out <result.json>
#
# <expected.json>: {"C:\\...\\name_part01of03.csv": 1000001, ...}: the records in each file, header included, counted
# by Python's csv module (a quoted value with a line break is one record). For each file the script opens it in
# Excel (read-only), reads the first sheet's used rows, and writes {"excel": "<version>", "files": [{"path", "expected",
# "excel_rows", "ok", "seconds"}]} to <result.json>. Exit 0 when every file matches, 1 when one doesn't, 3 when Excel
# isn't installed (the test then reports AC-EXP-9a as not verified).
param(
    [Parameter(Mandatory = $true)][string]$Expected,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Stop"
$want = Get-Content -LiteralPath $Expected -Raw -Encoding UTF8 | ConvertFrom-Json
try {
    $excel = New-Object -ComObject Excel.Application
} catch {
    @{ excel = $null; files = @() } | ConvertTo-Json | Set-Content -LiteralPath $Out -Encoding UTF8
    exit 3
}
$excel.Visible = $false
$excel.DisplayAlerts = $false
$results = @()
$allOk = $true
try {
    foreach ($p in $want.PSObject.Properties) {
        $path = $p.Name
        $expect = [int64]$p.Value
        $t = [Diagnostics.Stopwatch]::StartNew()
        # Open (not OpenText): the way a double-click opens a .csv, with Excel's own CSV parsing.
        $wb = $excel.Workbooks.Open($path, 0, $true)
        $ws = $wb.Worksheets.Item(1)
        $used = $ws.UsedRange
        $rows = [int64]($used.Row + $used.Rows.Count - 1)
        $wb.Close($false)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($used)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($ws)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wb)
        $t.Stop()
        $ok = ($rows -eq $expect)
        if (-not $ok) { $allOk = $false }
        $results += [ordered]@{ path = $path; expected = $expect; excel_rows = $rows; ok = $ok;
                                seconds = [math]::Round($t.Elapsed.TotalSeconds, 1) }
        Write-Host ("{0}: expected {1}, Excel {2} ({3})" -f (Split-Path $path -Leaf), $expect, $rows, $(if ($ok) { "ok" } else { "MISMATCH" }))
    }
    $version = $excel.Version
} finally {
    $excel.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    [GC]::Collect()
}
[ordered]@{ excel = $version; files = $results } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Out -Encoding UTF8
if ($allOk) { exit 0 } else { exit 1 }
