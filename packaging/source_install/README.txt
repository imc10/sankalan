SANKALAN {VERSION} - RUN FROM SOURCE (DEVELOPMENT AND TEST FALLBACK ONLY)
=========================================================================

This package is a stop-gap for development and test PCs until the signed installer
(Sankalan-Setup-<version>.exe) is available. It is NOT for customer laptops:
Smart App Control blocks the unsigned compiled files inside duckdb and python-calamine,
so on a laptop with Smart App Control turned on Sankalan will not start from source.
Use it only on a PC where Smart App Control is off.

1. Install Python 3.13 (64-bit) from python.org (once per PC), with
   "Add python.exe to PATH" ticked.

2. Unzip this package and double-click "Install Sankalan.bat".
   It takes 1-2 minutes and ends with "Sankalan is installed".
   With a "wheels" folder in the package no internet is needed; without one the
   packages are downloaded.

3. Open Sankalan from the Start menu or the desktop shortcut.

Sample files: demo-data\Sales_Oct.xlsx and demo-data\Sales_Nov.csv (if included).

Update: run "Install Sankalan.bat" from the newer package. Your data is kept.
Remove: double-click "Uninstall Sankalan.bat". It asks whether to delete your data too.

Where things are:
  App:          %LOCALAPPDATA%\Programs\Sankalan
  Data folder:  %LOCALAPPDATA%\Sankalan\Data (can be moved in App settings)
  Settings:     %LOCALAPPDATA%\Sankalan\settings.json
  Log:          %LOCALAPPDATA%\Sankalan\logs\sankalan.log (no cell values)
