@echo off
echo Encerrando servidor anterior...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo Iniciando Centro de Treinamento RV...
cd /d "%~dp0"
start "" /B venv\Scripts\python.exe main.py

echo Aguardando subida...
timeout /t 5 /nobreak >nul

echo Servidor no ar em http://localhost:8060
echo Cadastro publico: http://localhost:8060/cadastro
