@echo off
echo Activating virtual environment and generating database dump...

:: Replace with the actual path to your virtual environment's activate script
:: Example: C:\path\to\your\venv\Scripts\activate.bat
call "C:\Users\Usuario\Dropbox\Universidad\Desarrollo\your_venv_name\Scripts\activate.bat"

:: Navigate to your Django project root if not already there
:: cd C:\Users\Usuario\Dropbox\Universidad\Desarrollo\agenda-django

python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 --encoding=utf-8 > db_dump.json

echo Database dump generated: db_dump.json
pause