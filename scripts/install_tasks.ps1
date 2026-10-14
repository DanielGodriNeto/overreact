# Registers the crypto recorder and news ear as logon tasks (pythonw directly, so stopping a task kills Python).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_tasks.ps1
# Remove: Unregister-ScheduledTask -TaskName overreact-crypto-rec,overreact-crypto-news -Confirm:$false
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\pythonw.exe"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
$tasks = @{ "overreact-crypto-rec" = "overreact.crypto.recorder"; "overreact-crypto-news" = "overreact.crypto.newsear" }
foreach ($name in $tasks.Keys) {
    $action = New-ScheduledTaskAction -Execute $py -Argument "-u -m $($tasks[$name])" -WorkingDirectory $root
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
}
Get-ScheduledTask -TaskName overreact-crypto-* | Select-Object TaskName, State
