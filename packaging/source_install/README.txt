SANKALAN 1.0.0 - INSTALL ON A WINDOWS LAPTOP
=============================================

Works on Windows 10/11, including laptops with Smart App Control turned on.
No admin rights and no internet needed.

1. Install Python 3.13 (64-bit) from https://www.python.org/downloads/windows/
   (once per laptop). In its installer, tick "Add python.exe to PATH".

2. Before unzipping: right-click the downloaded zip file > Properties > tick "Unblock" > OK.
   (Windows marks downloaded files; with Smart App Control on it refuses to run the installer
   from a marked zip. If you already unzipped, delete that folder and unzip again after unblocking.)
   Then unzip it and double-click "Install Sankalan.bat" in the unzipped folder.
   Alternative: open Command Prompt in the unzipped folder and type  "Install Sankalan.bat"
   It takes 1-2 minutes and ends with "Sankalan is installed".

3. Open Sankalan from the Start menu or the desktop shortcut.

To try it with sample data: on the Templates screen click "Change..." and pick the
demo-data\templates folder, then click Run and add the folder
"demo-data\Acme Traders sales FY26-27".

Update: run "Install Sankalan.bat" from the newer package. Templates are kept.
Remove: double-click "Uninstall Sankalan.bat". Templates are kept.

Where things are:
  App:        %LOCALAPPDATA%\Programs\Sankalan
  Templates:  Documents\Sankalan\Templates (can be changed in the app)
  Log:        %LOCALAPPDATA%\Sankalan\logs\sankalan.log (no cell values)
