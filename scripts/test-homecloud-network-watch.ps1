. "$PSScriptRoot/homecloud-network-watch.ps1"
$now=Get-Date
$base=[pscustomobject]@{HostOnline=$true;VmIdentified=$true;VmLanReady=$true;GatewayResolved=$false;TailnetReady=$false;GuestProbeValid=$true;GuestGatewayReachable=$false;GuestInternet=$false;NatStatus='Running'}
$state=[pscustomobject]@{Failures=0;LastRepair=$null;Repairs=@()}
function Assert-Decision($want){$actual=Get-RecoveryDecision $base $state $now;if($actual -ne $want){throw "Expected $want; got $actual"}}
Assert-Decision 'confirm_next_sample'
$state.Failures=1;Assert-Decision 'repair_nat'
$base.HostOnline=$false;Assert-Decision 'host_offline';$base.HostOnline=$true
$base.VmIdentified=$false;Assert-Decision 'vm_unavailable';$base.VmIdentified=$true
$base.VmLanReady=$false;Assert-Decision 'no_nat_fault';$base.VmLanReady=$true
$base.GuestGatewayReachable=$true;Assert-Decision 'no_nat_fault';$base.GuestGatewayReachable=$false
$base.GuestProbeValid=$false;Assert-Decision 'no_nat_fault';$base.GuestProbeValid=$true
$base.GuestInternet=$true;Assert-Decision 'tailscale_fault';$base.GuestInternet=$false
$state.LastRepair=$now.AddMinutes(-5).ToString('o');Assert-Decision 'cooldown'
$state.LastRepair=$null;$state.Repairs=@($now.AddMinutes(-40).ToString('o'),$now.AddMinutes(-20).ToString('o'));Assert-Decision 'rate_limited'
$state.Repairs=@();$base.NatStatus='Stopped';$base.VmLanReady=$false;Assert-Decision 'repair_nat'
'PASS: repeated fault, healthy gateway, host offline, VM absent, app fault, cooldown, restart cap and stopped service'
