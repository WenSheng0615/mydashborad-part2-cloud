# VM-external copy; only report success after SQLite and checksum verification.
$ErrorActionPreference = 'Stop'
$Server = '100.113.77.65'
$User = 'wensheng'
$Key = Join-Path $env:USERPROFILE '.ssh/homecloud_backup'
$BackupDir = Join-Path $env:USERPROFILE 'HomeCloud-Backups'
$ProjectDir = Join-Path $env:USERPROFILE 'Desktop/mydashborad-part2-cloud'
$Python = Join-Path $ProjectDir '.venv/Scripts/python.exe'
$Verifier = Join-Path $ProjectDir 'scripts/verify_backup.py'
$LogFile = Join-Path $BackupDir 'backup.log'
$Partial = $null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
function Write-Log($Message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message" | Tee-Object -FilePath $LogFile -Append
}
try {
    $Remote = & ssh -i $Key -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 "$User@$Server" 'python3 /home/wensheng/services/focusflow/scripts/verify_backup.py --select /home/wensheng/backups/focusflow'
    if ($LASTEXITCODE -ne 0 -or -not $Remote) { throw 'No verified remote backup available' }
    $Parts = ($Remote.Trim() -split '\|')
    if ($Parts.Count -ne 2 -or $Parts[1] -notmatch '^[a-f0-9]{64}$' -or $Parts[0] -notmatch '^/home/wensheng/backups/focusflow/focusflow-[A-Za-z0-9-]+\.db$') { throw 'Unexpected backup selection' }
    $Destination = Join-Path $BackupDir ([IO.Path]::GetFileName($Parts[0]))
    if (Test-Path -LiteralPath $Destination) {
        $ExistingHash = & $Python $Verifier --verify $Destination
        if ($LASTEXITCODE -ne 0 -or $ExistingHash.Trim() -ne $Parts[1]) { throw 'Existing copy is invalid or mismatched; retained for investigation' }
    } else {
        $Partial = Join-Path $BackupDir ('.download-' + [guid]::NewGuid().ToString('N') + '.partial')
        & scp -q -i $Key -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 "${User}@${Server}:$($Parts[0])" $Partial
        if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed' }
        $CopiedHash = & $Python $Verifier --verify $Partial
        if ($LASTEXITCODE -ne 0 -or $CopiedHash.Trim() -ne $Parts[1]) { throw 'Copied backup verification failed' }
        Move-Item -LiteralPath $Partial -Destination $Destination
        $Partial = $null
    }
    Write-Log "[OK] SQLite and SHA256 verified: $([IO.Path]::GetFileName($Destination))"
    exit 0
} catch {
    Write-Log "[ERROR] $($_.Exception.Message)"
    exit 1
} finally {
    if ($Partial -and (Test-Path -LiteralPath $Partial)) { Remove-Item -LiteralPath $Partial }
}
