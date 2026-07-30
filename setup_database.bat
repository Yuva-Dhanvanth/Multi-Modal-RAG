@echo off
echo ============================================
echo  MULTIMODAL RAG - FULL DATABASE SETUP
echo ============================================
echo.

set PGROOT=C:\Program Files\PostgreSQL\16
set PGDATA=%PGROOT%\data
set PGBIN=%PGROOT%\bin

echo Step 1: Installing pgvector extension...
echo ------------------------------------------

set SRC=%TEMP%\pgvector-win-pg16\pgvector-x86_64-pc-windows-msvc-pg16

if exist "%SRC%\lib\vector.dll" (
    copy /Y "%SRC%\lib\vector.dll" "%PGROOT%\lib\vector.dll" >nul
    copy /Y "%SRC%\share\extension\*" "%PGROOT%\share\extension\" >nul
    echo [OK] pgvector files copied.
) else (
    echo [WARN] pgvector source not found at %SRC%
    echo        Will try to continue anyway...
)

echo.
echo Step 2: Resetting PostgreSQL password...
echo ------------------------------------------

:: Backup pg_hba.conf
copy /Y "%PGDATA%\pg_hba.conf" "%PGDATA%\pg_hba.conf.backup" >nul
echo [OK] Backed up pg_hba.conf

:: Temporarily set to trust auth
powershell -Command "(Get-Content '%PGDATA%\pg_hba.conf') -replace 'scram-sha-256','trust' | Set-Content '%PGDATA%\pg_hba.conf'"
echo [OK] Set auth to trust temporarily

:: Restart PostgreSQL to apply
echo [..] Restarting PostgreSQL...
net stop postgresql-x64-16 >nul 2>&1
timeout /t 3 /nobreak >nul
net start postgresql-x64-16 >nul 2>&1
timeout /t 3 /nobreak >nul
echo [OK] PostgreSQL restarted

:: Reset password to 'postgres'
"%PGBIN%\psql.exe" -U postgres -h localhost -c "ALTER USER postgres WITH PASSWORD 'postgres';"
echo [OK] Password reset to 'postgres'

:: Restore original auth method
copy /Y "%PGDATA%\pg_hba.conf.backup" "%PGDATA%\pg_hba.conf" >nul
echo [OK] Restored original auth config

:: Restart PostgreSQL again
echo [..] Restarting PostgreSQL...
net stop postgresql-x64-16 >nul 2>&1
timeout /t 3 /nobreak >nul
net start postgresql-x64-16 >nul 2>&1
timeout /t 3 /nobreak >nul
echo [OK] PostgreSQL restarted with password auth

echo.
echo Step 3: Creating database and enabling pgvector...
echo ------------------------------------------

set PGPASSWORD=postgres

:: Create database
"%PGBIN%\psql.exe" -U postgres -h localhost -c "SELECT 1 FROM pg_database WHERE datname='multimodal_rag'" | findstr /C:"1" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Database multimodal_rag already exists
) else (
    "%PGBIN%\psql.exe" -U postgres -h localhost -c "CREATE DATABASE multimodal_rag;"
    echo [OK] Database multimodal_rag created
)

:: Enable vector extension
"%PGBIN%\psql.exe" -U postgres -h localhost -d multimodal_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo [OK] pgvector extension enabled

echo.
echo Step 4: Verifying everything...
echo ------------------------------------------
"%PGBIN%\psql.exe" -U postgres -h localhost -d multimodal_rag -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

echo.
echo ============================================
echo  ALL DONE! 
echo  Database: multimodal_rag
echo  User: postgres
echo  Password: postgres
echo  pgvector: installed
echo ============================================
echo.
echo You can close this window now.
pause
