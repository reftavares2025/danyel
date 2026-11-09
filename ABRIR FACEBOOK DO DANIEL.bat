@echo off
chcp 65001 >nul
rem Abre um Chrome SEPARADO, so com o Facebook do Daniel, para o Danyel fazer as buscas.
rem Na primeira vez: faca login com o Facebook do Daniel nessa janela. Depois e so deixar aberta.
set "PERFIL=%~dp0chrome-daniel"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
start "" "%CHROME%" --user-data-dir="%PERFIL%" --remote-debugging-port=9223 --no-first-run --no-default-browser-check https://www.facebook.com/
