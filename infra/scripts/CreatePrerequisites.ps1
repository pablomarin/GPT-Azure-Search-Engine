$ErrorActionPreference = "Stop"

& $PSScriptRoot\loadenv.ps1


New-Item -ItemType "directory" -Path ".\infra\target"          -ErrorAction SilentlyContinue
New-Item -ItemType "directory" -Path ".\infra\target\frontend" -ErrorAction SilentlyContinue
New-Item -ItemType "directory" -Path ".\infra\target\backend"  -ErrorAction SilentlyContinue
