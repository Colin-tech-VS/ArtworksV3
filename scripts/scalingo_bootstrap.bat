@echo off
REM Bootstrap Scalingo ArtworksV3 — exécuter après: scalingo login
set SCALINGO=%~dp0scalingo_1.33.0_windows_amd64\scalingo.exe
set APP=artworksv3

echo === Login Scalingo (si besoin) ===
"%SCALINGO%" auth whoami

echo === Création app %APP% (ignorer si existe) ===
"%SCALINGO%" create %APP% --region osc-fr1 2>nul

echo === Addon PostgreSQL (Scalingo) — optionnel si Supabase ===
REM "%SCALINGO%" addons-add %APP% postgresql postgresql-sandbox

echo.
echo Configurez DATABASE_URL (Supabase) puis relancez scripts\scalingo_env_sync.ps1
pause
