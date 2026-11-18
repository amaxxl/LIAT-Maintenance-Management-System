# From PowerShell in extracted LIAT_stage2_code. Back up your DB and migration files first!
$ErrorActionPreference = 'Stop'
if (!(Test-Path '.venv\Scripts\python.exe')) {
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the Python environment.' }
}
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $python manage.py makemigrations core
if ($LASTEXITCODE -ne 0) { throw 'Migration generation failed.' }
& $python manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. Do not delete your DB.' }
& $python manage.py seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo data setup failed.' }
& $python manage.py test -v 2
if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Capture the test output and fix issues before demonstration.' }
Write-Host 'Tests passed locally. Starting http://127.0.0.1:8000/login/'
& $python manage.py runserver
