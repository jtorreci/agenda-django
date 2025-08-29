@echo off
echo Activating virtual environment and generating requirements.txt...

:: Replace with the actual path to your virtual environment's activate script
:: Example: C:\path\to\your\venv\Scripts\activate.bat
call "C:\Users\Usuario\Dropbox\Universidad\Desarrollo\your_venv_name\Scripts\activate.bat"

:: Navigate to your Django project root if not already there
:: cd C:\Users\Usuario\Dropbox\Universidad\Desarrollo\agenda-django

pip freeze > requirements.txt

echo requirements.txt generated.
pause
