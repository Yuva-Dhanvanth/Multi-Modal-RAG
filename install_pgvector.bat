@echo off
echo ============================================
echo Installing pgvector for PostgreSQL 16...
echo ============================================

set SRC=%TEMP%\pgvector-win-pg16\pgvector-x86_64-pc-windows-msvc-pg16
set PGROOT=C:\Program Files\PostgreSQL\16

echo Copying vector.dll...
copy /Y "%SRC%\lib\vector.dll" "%PGROOT%\lib\vector.dll"

echo Copying extension SQL files...
copy /Y "%SRC%\share\extension\*" "%PGROOT%\share\extension\"

echo.
echo Verifying installation...
if exist "%PGROOT%\lib\vector.dll" (
    echo [SUCCESS] vector.dll installed!
) else (
    echo [FAILED] vector.dll not found!
)

if exist "%PGROOT%\share\extension\vector.control" (
    echo [SUCCESS] vector.control installed!
) else (
    echo [FAILED] vector.control not found!
)

echo.
echo ============================================
echo Now setting up the database...
echo ============================================

echo Creating multimodal_rag database...
"%PGROOT%\bin\psql.exe" -U postgres -h localhost -c "SELECT 1 FROM pg_database WHERE datname='multimodal_rag'" | findstr /C:"1" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Database multimodal_rag already exists.
) else (
    "%PGROOT%\bin\psql.exe" -U postgres -h localhost -c "CREATE DATABASE multimodal_rag;"
    echo Database multimodal_rag created.
)

echo Enabling vector extension...
"%PGROOT%\bin\psql.exe" -U postgres -h localhost -d multimodal_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo.
echo Verifying vector extension...
"%PGROOT%\bin\psql.exe" -U postgres -h localhost -d multimodal_rag -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

echo.
echo ============================================
echo ALL DONE! You can close this window.
echo ============================================
pause
