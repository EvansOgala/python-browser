@echo off
setlocal

echo Installing Python build/runtime dependencies...
py -m pip install --upgrade pip pyinstaller
py -m pip install PySide6 PySide6-Addons
py -m pip install pywebview pythonnet pywin32

echo Checking Microsoft Edge WebView2 Runtime...
reg query "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F1F6AA6E-2A4A-4481-AF4E-8F2B9CFAE6FA}" >nul 2>nul
if %errorlevel% neq 0 (
  reg query "HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F1F6AA6E-2A4A-4481-AF4E-8F2B9CFAE6FA}" >nul 2>nul
)
if %errorlevel% neq 0 (
  echo.
  echo WebView2 Runtime not detected.
  echo Install with: winget install Microsoft.EdgeWebView2Runtime
  echo.
)

echo Building executable...
py -m PyInstaller --noconfirm --clean PythonBrowser.spec

echo.
echo Build complete. Output: dist\PythonBrowser\
if exist "app_icon.ico" (
  echo Using icon: app_icon.ico
) else (
  echo Tip: add app_icon.ico in this folder for a custom EXE icon.
)

endlocal
