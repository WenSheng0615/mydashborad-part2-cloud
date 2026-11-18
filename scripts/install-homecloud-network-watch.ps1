param([switch]$DisableAcSleep)
$ErrorActionPreference='Stop'
$root=Join-Path $env:ProgramData 'HomeCloud\NetworkGuard'
$admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if(-not $admin){throw 'Run this installer as Administrator'}
try {
New-Item -ItemType Directory -Path $root -Force|Out-Null
Unregister-ScheduledTask -TaskName 'HomeCloud Network Guard' -Confirm:$false -ErrorAction SilentlyContinue
# An elevated task must execute scripts writable only by administrators and SYSTEM.
& icacls.exe $root /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
if($LASTEXITCODE -ne 0){throw 'Unable to secure watchdog directory'}
$watch=Join-Path $root 'homecloud-network-watch.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'homecloud-network-watch.ps1') -Destination $watch -Force
& icacls.exe $watch /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' '*S-1-5-32-545:RX'|Out-Null
if($LASTEXITCODE -ne 0){throw 'Unable to secure watchdog script'}
$key=Join-Path $root 'ssh-key'
Copy-Item -LiteralPath (Join-Path $env:USERPROFILE '.ssh/homecloud_backup') -Destination $key -Force
& icacls.exe $key /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F'|Out-Null
if($LASTEXITCODE -ne 0){throw 'Unable to protect diagnostic SSH key'}
$known=Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.ssh/known_hosts')|Where-Object {$_ -match '^100\.113\.77\.65\s'}
if(-not $known){throw 'Pinned HomeCloud SSH host key is missing'}
$known|Set-Content -LiteralPath (Join-Path $root 'known_hosts') -Encoding ASCII
$exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskLog=Join-Path $root 'task-output.log'
$taskCommand='""'+$exe+'" -NoProfile -NonInteractive -File "'+$watch+'" -Mode Watch > "'+$taskLog+'" 2>&1"'
$action=New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32/cmd.exe') -Argument ('/d /c '+$taskCommand)
$startup=New-ScheduledTaskTrigger -AtStartup
$periodic=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
$runAs=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$principal=New-ScheduledTaskPrincipal -UserId $runAs -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName 'HomeCloud Network Guard' -Action $action -Trigger @($startup,$periodic) -Settings $settings -Principal $principal -Description 'Check VMnet8 data-plane connectivity; bounded NAT recovery with diagnostic logs.' -Force|Out-Null
if($DisableAcSleep){
    if(-not (Test-Path (Join-Path $root 'power-before.txt'))){& powercfg.exe /query SCHEME_CURRENT SUB_SLEEP | Set-Content (Join-Path $root 'power-before.txt')}
    & powercfg.exe /change standby-timeout-ac 0
    if($LASTEXITCODE -ne 0){throw 'Unable to set AC sleep timeout'}
    & powercfg.exe /change hibernate-timeout-ac 0
    if($LASTEXITCODE -ne 0){throw 'Unable to set AC hibernate timeout'}
}
& $exe -NoProfile -NonInteractive -File $watch -Mode Repair | Set-Content -LiteralPath (Join-Path $root 'initial-repair.json') -Encoding UTF8
if($LASTEXITCODE -ne 0){throw 'Initial diagnosis/recovery failed; inspect logs'}
# Validate the actual scheduled execution context, including the protected SSH key.
$started=Get-Date
Start-ScheduledTask -TaskName 'HomeCloud Network Guard'
$taskInfo=$null
for($i=0;$i -lt 50;$i++){
    Start-Sleep -Milliseconds 500
    $task=Get-ScheduledTask -TaskName 'HomeCloud Network Guard'
    $taskInfo=Get-ScheduledTaskInfo -TaskName 'HomeCloud Network Guard'
    if($taskInfo.LastRunTime -ge $started.AddSeconds(-1) -and $task.State -ne 'Running'){break}
}
@{Info=($taskInfo|Select-Object LastTaskResult,LastRunTime,NextRunTime);State=[string]$task.State}|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $root 'task-diagnostic.json') -Encoding UTF8
if($taskInfo.LastTaskResult -ne 0 -or $task.State -eq 'Running'){throw 'Scheduled check did not complete successfully'}
$timeline=@()
foreach($provider in @('Microsoft-Windows-Kernel-Power','Microsoft-Windows-Power-Troubleshooter')){
    $timeline+=@(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName=$provider;StartTime=(Get-Date).AddDays(-7)} -MaxEvents 100 -ErrorAction SilentlyContinue|Select-Object TimeCreated,Id,ProviderName,Message)
}
$timeline|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $root 'power-timeline.json') -Encoding UTF8
[pscustomobject]@{Installed=(Get-Date).ToString('o');Task='HomeCloud Network Guard';AcSleepDisabled=[bool]$DisableAcSleep;WatchdogHash=(Get-FileHash -LiteralPath $watch -Algorithm SHA256).Hash;TaskResult=$taskInfo.LastTaskResult;TaskLastRun=$taskInfo.LastRunTime.ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'installed.json') -Encoding UTF8

}catch{
    [pscustomobject]@{Time=(Get-Date).ToString('o');Error=$_.Exception.Message;Detail=$_.ScriptStackTrace}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'install-error.json') -Encoding UTF8
    throw
}
