#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smoke-test for Agency OS full stack.
.EXAMPLE
    .\scripts\smoke-test.ps1
#>

$ErrorActionPreference = "Stop"

$baseUrl = "http://localhost:8000"
$webUrl = "http://localhost:3000"

Write-Host "=== Agency OS Smoke-Test ===" -ForegroundColor Cyan

# Wait for services to start
Write-Host "`nWaiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# API health
Write-Host "`n--- GET $baseUrl/health ---" -ForegroundColor Green
try {
    $r = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    $r | ConvertTo-Json
    if ($r.status -ne "ok") { throw "status != ok" }
} catch {
    Write-Host "FAIL: $_" -ForegroundColor Red
    exit 1
}

# API docs
Write-Host "`n--- GET $baseUrl/docs ---" -ForegroundColor Green
try {
    $r = Invoke-WebRequest -Uri "$baseUrl/docs" -Method Get -UseBasicParsing
    if ($r.StatusCode -ge 400) { throw "HTTP $($r.StatusCode)" }
    Write-Host "OK (HTTP $($r.StatusCode))"
} catch {
    Write-Host "FAIL: $_" -ForegroundColor Red
    exit 1
}

# Web
Write-Host "`n--- GET $webUrl ---" -ForegroundColor Green
try {
    $r = Invoke-WebRequest -Uri $webUrl -Method Get -UseBasicParsing
    if ($r.StatusCode -ge 400) { throw "HTTP $($r.StatusCode)" }
    Write-Host "OK (HTTP $($r.StatusCode))"
} catch {
    Write-Host "FAIL: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== All smoke-tests passed ===" -ForegroundColor Cyan