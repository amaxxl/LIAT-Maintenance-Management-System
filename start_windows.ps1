# LIAT Stage 3 local development helper (Windows PowerShell).
# Run from any folder; always execute commands in the project containing this file.
# DO NOT use on real data or a public production server; seeds fictional users.
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (!(Test-Path '.venv\Scripts\python.exe')) {
        py -3.14 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python 3.14 environment.' }
    }
    $python = '.\.venv\Scripts\python.exe'
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

    # The migrations are already included in the repository.
    & $python manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. Keep your database backup.' }
    & $python manage.py seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo data setup failed.' }
    & $python manage.py test
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Fix issues before demonstration.' }

    Write-Host 'Tests passed. Starting http://127.0.0.1:8000/login/'
    & $python manage.py runserver
}
finally {
    Pop-Location
}
