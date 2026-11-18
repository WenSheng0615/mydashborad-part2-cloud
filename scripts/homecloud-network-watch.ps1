param([ValidateSet('Check','Watch','Repair')][string]$Mode='Watch',[string]$StateDirectory="$env:ProgramData\HomeCloud\NetworkGuard")
$ErrorActionPreference='Stop'
function Test-HostInternet {
    foreach($address in @('1.1.1.1','8.8.8.8')) {
        $client=[Net.Sockets.TcpClient]::new()
        try{$pending=$client.ConnectAsync($address,443);if($pending.Wait(2500) -and $client.Connected){return $true}}catch{}finally{$client.Dispose()}
    }
    return $false
}
function Get-RecoveryDecision($Sample,$State,[datetime]$Now) {
    if(-not $Sample.HostOnline){return 'host_offline'}
    if(-not $Sample.VmIdentified){return 'vm_unavailable'}
    $broken=($Sample.NatStatus -ne 'Running') -or ($Sample.VmLanReady -and $Sample.GuestProbeValid -and -not $Sample.GuestGatewayReachable -and -not $Sample.GuestInternet)
    if(-not $broken){if($Sample.TailnetReady -eq $false -and $Sample.GuestInternet){return 'tailscale_fault'};return 'no_nat_fault'}
    if($State.LastRepair -and ($Now-[datetime]$State.LastRepair).TotalMinutes -lt 15){return 'cooldown'}
    $recent=@($State.Repairs | Where-Object {($Now-[datetime]$_).TotalHours -lt 1})
    if($recent.Count -ge 2){return 'rate_limited'}
    if($Mode -ne 'Repair' -and $State.Failures -lt 1){return 'confirm_next_sample'}
    return 'repair_nat'
}
function Get-GuestNetwork($Address) {
    $key=Join-Path $StateDirectory 'ssh-key'
    $hosts=Join-Path $StateDirectory 'known_hosts'
    if($Mode -eq 'Check'){$key=Join-Path $env:USERPROFILE '.ssh/homecloud_backup';$hosts=Join-Path $env:USERPROFILE '.ssh/known_hosts'}
    try{
        $command='echo aW1wb3J0IGpzb24sc29ja2V0LHN1YnByb2Nlc3MKcm91dGVzPWpzb24ubG9hZHMoc3VicHJvY2Vzcy5ydW4oWyJpcCIsIi1qIiwicm91dGUiLCJzaG93IiwiZGVmYXVsdCJdLGNhcHR1cmVfb3V0cHV0PVRydWUsdGV4dD1UcnVlLHRpbWVvdXQ9MyxjaGVjaz1UcnVlKS5zdGRvdXQpCmdhdGV3YXk9cm91dGVzWzBdWyJnYXRld2F5Il0KcGluZz1zdWJwcm9jZXNzLnJ1bihbInBpbmciLCItYyIsIjEiLCItVyIsIjIiLGdhdGV3YXldLHN0ZG91dD1zdWJwcm9jZXNzLkRFVk5VTEwsc3RkZXJyPXN1YnByb2Nlc3MuREVWTlVMTCx0aW1lb3V0PTQpCmludGVybmV0PUZhbHNlCnRyeToKIHdpdGggc29ja2V0LmNyZWF0ZV9jb25uZWN0aW9uKCgiMS4xLjEuMSIsNDQzKSwzKTogaW50ZXJuZXQ9VHJ1ZQpleGNlcHQgT1NFcnJvcjogcGFzcwpwcmludChqc29uLmR1bXBzKHsiR2F0ZXdheVJlYWNoYWJsZSI6cGluZy5yZXR1cm5jb2RlPT0wLCJJbnRlcm5ldCI6aW50ZXJuZXR9KSkK | base64 -d | python3'
        $result=& "$env:SystemRoot\System32\OpenSSH\ssh.exe" -F NUL -i $key -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$hosts" -o HostKeyAlias=100.113.77.65 -o ConnectTimeout=5 -o ServerAliveInterval=3 -o ServerAliveCountMax=1 "wensheng@$Address" $command 2>$null
        if($LASTEXITCODE -ne 0){return $null}
        $data=($result|Out-String)|ConvertFrom-Json
        if($data.GatewayReachable -isnot [bool] -or $data.Internet -isnot [bool]){return $null}
        return $data
    }catch{return $null}
}
function Get-NetworkSample {
    $natConfig=Get-Content -LiteralPath "$env:ProgramData\VMware\vmnetnat.conf" -Raw
    $gateway=[regex]::Match($natConfig,'(?m)^ip\s*=\s*([0-9.]+)/').Groups[1].Value
    if(-not $gateway){throw 'VMware NAT gateway not found'}
    $leaseText=Get-Content -LiteralPath "$env:ProgramData\VMware\vmnetdhcp.leases" -Raw
    $leases=[regex]::Matches($leaseText,'(?s)lease\s+([0-9.]+)\s*\{(.*?)\}')
    $vmAddress=$null
    foreach($lease in $leases){if($lease.Groups[2].Value -match 'hardware ethernet 00:0c:29:75:1f:5f;'){$vmAddress=$lease.Groups[1].Value}}
    if(-not $vmAddress){throw 'HomeCloud DHCP lease not found; no recovery attempted'}
    & "$env:SystemRoot\System32\PING.EXE" -n 1 -w 1000 $vmAddress | Out-Null
    $vmNeighbor=Get-NetNeighbor -AddressFamily IPv4 -IPAddress $vmAddress -ErrorAction SilentlyContinue | Where-Object LinkLayerAddress -eq '00-0C-29-75-1F-5F' | Select-Object -First 1
    $identified=[bool]($vmNeighbor -and $vmNeighbor.State -notin @('Unreachable','Incomplete'))
    $lanReady=$false
    if($identified){try{$response=Invoke-WebRequest -UseBasicParsing -Uri "http://$vmAddress/health/ready" -TimeoutSec 4;$lanReady=($response.StatusCode -eq 200 -and ($response.Content|ConvertFrom-Json).status -eq 'ready')}catch{}}
    & "$env:SystemRoot\System32\PING.EXE" -n 1 -w 1000 $gateway | Out-Null
    $neighbor=Get-NetNeighbor -AddressFamily IPv4 -IPAddress $gateway -ErrorAction SilentlyContinue | Where-Object {$_.LinkLayerAddress -and $_.LinkLayerAddress -ne '00-00-00-00-00-00' -and $_.State -notin @('Unreachable','Incomplete')} | Select-Object -First 1
    $tailnetReady=$false
    try{$tailnetResponse=Invoke-WebRequest -UseBasicParsing -Uri 'https://homecloud.tailea7aa9.ts.net/health/ready' -TimeoutSec 5;$tailnetReady=($tailnetResponse.StatusCode -eq 200 -and ($tailnetResponse.Content|ConvertFrom-Json).status -eq 'ready')}catch{}
    $hostOnline=Test-HostInternet
    $guest=$null
    if($identified -and $hostOnline){$guest=Get-GuestNetwork $vmAddress}
    [pscustomobject]@{Time=(Get-Date).ToString('o');HostOnline=$hostOnline;VmAddress=$vmAddress;VmIdentified=$identified;VmLanReady=$lanReady;Gateway=$gateway;GatewayResolved=[bool]$neighbor;TailnetReady=$tailnetReady;GuestProbeValid=[bool]$guest;GuestGatewayReachable=($guest -and $guest.GatewayReachable);GuestInternet=($guest -and $guest.Internet);NatStatus=[string](Get-Service 'VMware NAT Service').Status}

}
# Tests dot-source the decision function without executing diagnostics or repairs.
if($MyInvocation.InvocationName -eq '.'){return}
try {
$sample=Get-NetworkSample
if($Mode -eq 'Check'){$sample|ConvertTo-Json -Compress;exit 0}
New-Item -ItemType Directory -Path $StateDirectory -Force|Out-Null
$statePath=Join-Path $StateDirectory 'state.json';$logPath=Join-Path $StateDirectory 'events.jsonl'
$state=[pscustomobject]@{Failures=0;LastRepair=$null;Repairs=@()}
if(Test-Path -LiteralPath $statePath){$state=Get-Content -LiteralPath $statePath -Raw|ConvertFrom-Json}
$decision=Get-RecoveryDecision $sample $state (Get-Date)
$event=[ordered]@{Time=$sample.Time;Decision=$decision;Sample=$sample;Result=$null}
if($decision -eq 'repair_nat'){
    $now=(Get-Date).ToString('o');$state.LastRepair=$now;$state.Repairs=@($state.Repairs|Where-Object {((Get-Date)-[datetime]$_).TotalHours -lt 1})+@($now)
    # Persist the attempt before touching the service; a failed restart must not loop.
    $state|ConvertTo-Json|Set-Content -LiteralPath $statePath -Encoding UTF8
    try{
        Restart-Service -Name 'VMware NAT Service' -ErrorAction Stop
        (Get-Service 'VMware NAT Service').WaitForStatus('Running',[timespan]::FromSeconds(20))
        $event.Result='nat_service_restarted';$state.Failures=0
    }catch{$event.Result='restart_failed: '+$_.Exception.Message}
}elseif($decision -eq 'confirm_next_sample'){$state.Failures++}
elseif($decision -in @('no_nat_fault','tailscale_fault')){$state.Failures=0}
else{$state.Failures=0}
$state|ConvertTo-Json|Set-Content -LiteralPath $statePath -Encoding UTF8
if((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 5MB){Move-Item -LiteralPath $logPath -Destination "$logPath.previous" -Force}
$event|ConvertTo-Json -Depth 5 -Compress|Add-Content -LiteralPath $logPath -Encoding UTF8
$event|ConvertTo-Json -Depth 5 -Compress

}catch{
    if(Test-Path -LiteralPath $StateDirectory){
        [pscustomobject]@{Time=(Get-Date).ToString('o');Decision='watchdog_error';Error=$_.Exception.Message}|ConvertTo-Json -Compress|Add-Content -LiteralPath (Join-Path $StateDirectory 'events.jsonl') -Encoding UTF8
    }
    Write-Error $_
    exit 1
}
