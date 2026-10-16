@echo off
REM ==============================================================================
REM Script de inicio rápido para SIGE-UBE API (Windows 11)
REM ==============================================================================

echo [1/3] Verificando servicio de PostgreSQL en Windows...
sc query postgresql-x64-16 | find "RUNNING" >nul 2>&1
if errorlevel 1 (
    sc query postgresql-x64-15 | find "RUNNING" >nul 2>&1
    if errorlevel 1 (
        echo Iniciando PostgreSQL...
        net start postgresql-x64-16 >nul 2>&1 || net start postgresql-x64-15 >nul 2>&1
    )
)

echo [2/3] Activando entorno virtual...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] No se encontro el entorno virtual en venv.
    echo Ejecuta: python -m venv venv y pip install -r requirements.txt
    pause
    exit /b 1
)

echo [3/3] Iniciando servidor Django en http://127.0.0.1:8000/ ...
python manage.py runserver
pause
