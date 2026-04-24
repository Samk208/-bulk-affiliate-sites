@echo off
REM ================================================================
REM setup-scheduler.bat — Create Windows Task Scheduler job
REM Runs daily_runner.py every morning at 6:00 AM Korea time
REM
REM Usage: Right-click → Run as Administrator
REM ================================================================

echo Creating scheduled task: BulkAffiliate-DailyRunner
echo This will run every day at 6:00 AM...

schtasks /create /tn "BulkAffiliate-DailyRunner" ^
    /tr "python \"C:\Users\Lenovo\Desktop\Claude cowork\wordpress\bulk-affiliate-sites\scripts\daily_runner.py\"" ^
    /sc daily ^
    /st 06:00 ^
    /f ^
    /rl HIGHEST

if %ERRORLEVEL% equ 0 (
    echo.
    echo SUCCESS! Task created.
    echo.
    echo Task name:  BulkAffiliate-DailyRunner
    echo Schedule:   Daily at 6:00 AM
    echo Script:     daily_runner.py
    echo.
    echo To check:   schtasks /query /tn "BulkAffiliate-DailyRunner"
    echo To delete:  schtasks /delete /tn "BulkAffiliate-DailyRunner" /f
    echo To run now: schtasks /run /tn "BulkAffiliate-DailyRunner"
    echo.
    echo IMPORTANT: Add these to _global\.env.cowork:
    echo   SMTP_USER=skonneh2020@gmail.com
    echo   SMTP_PASS=your-gmail-app-password
) else (
    echo.
    echo FAILED! Try running as Administrator.
)

pause
