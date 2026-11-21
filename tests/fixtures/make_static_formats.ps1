<#
One-off: build the Excel-saved fixtures F22-F27 in tests\fixtures\static (development only; needs Microsoft Excel).

No Python package writes .xlsb, and none in requirements-dev writes .xls, so these files are checked in, like F11.
Excel opens the generated .xlsx fixtures and saves them in the other formats:

    F22 Sales_Nov.xls            F03 saved as Excel 97-2003
    F23 Sales_Nov.xlsb           F03 saved as Excel Binary
    F24 Conversion_Values.xls    F19 saved as Excel 97-2003
    F25 Conversion_Values.xlsb   F19 saved as Excel Binary
    F26 Sales_Protected.xls      F06 (password Sankalan@123) saved as Excel 97-2003 with the same password
    F27 Sales_Protected.xlsb     F06 saved as Excel Binary with the same password
    S05 Sales_Nov-2026_Central.xlsb   S01 saved as Excel Binary (A2-2, Choose sheets; hidden Notes kept)
    S06 Sales_Nov-2026_Central.xls    S01 saved as Excel 97-2003

To rebuild:
    python tests\fixtures\generate.py
    powershell -ExecutionPolicy Bypass -File tests\fixtures\make_static_formats.ps1
#>
param([string]$Generated = (Join-Path $PSScriptRoot "_generated"))
$ErrorActionPreference = "Stop"
$static = Join-Path $PSScriptRoot "static"
$password = "Sankalan@123"
$xlExcel8 = 56
$xlExcel12 = 50

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $jobs = @(
        @{ From = "Sales_Nov.xlsx"; To = "Sales_Nov"; Password = $null },
        @{ From = "Conversion_Values.xlsx"; To = "Conversion_Values"; Password = $null },
        @{ From = "Sales_Protected.xlsx"; To = "Sales_Protected"; Password = $password },
        @{ From = "Sales_Nov-2026_Central.xlsx"; To = "Sales_Nov-2026_Central"; Password = $null }
    )
    foreach ($j in $jobs) {
        $src = Join-Path $Generated $j.From
        if ($j.Password) {
            $wb = $xl.Workbooks.Open($src, 0, $true, [Type]::Missing, $j.Password)
        } else {
            $wb = $xl.Workbooks.Open($src, 0, $true)
        }
        foreach ($fmt in @(@{ Ext = "xls"; Code = $xlExcel8 }, @{ Ext = "xlsb"; Code = $xlExcel12 })) {
            $out = Join-Path $static ("{0}.{1}" -f $j.To, $fmt.Ext)
            if (Test-Path $out) { Remove-Item $out -Confirm:$false }
            if ($j.Password) {
                $wb.SaveAs($out, $fmt.Code, $j.Password)
            } else {
                $wb.SaveAs($out, $fmt.Code)
            }
            Write-Output ("wrote {0}" -f $out)
        }
        $wb.Close($false)
    }
} finally {
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
