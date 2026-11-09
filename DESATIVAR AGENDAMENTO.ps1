Get-ScheduledTask -TaskPath "\Danyel\" -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
Write-Host "Danyel automático DESATIVADO."
