# Ativa o Danyel automático no Agendador de Tarefas do Windows.
#  - Varredura do Facebook: todo dia às 9h e às 15h
#  - Leitura do "APROVO" do Daniel e envios: a cada 30 min, das 8h às 20h
# Para desligar: rode  DESATIVAR AGENDAMENTO.ps1

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py  = (Get-Command pythonw.exe -ErrorAction Stop).Source
$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -MultipleInstances IgnoreNew

$a1 = New-ScheduledTaskAction -Execute $py -Argument "-m danyel ciclo" -WorkingDirectory $dir
$t1 = @((New-ScheduledTaskTrigger -Daily -At "09:00"), (New-ScheduledTaskTrigger -Daily -At "15:00"))
Register-ScheduledTask -TaskPath "\Danyel\" -TaskName "Varredura Facebook" -Action $a1 -Trigger $t1 -Settings $set `
  -Description "Danyel: varre o Facebook e manda relatório ao Daniel (cópia ao Régis)" -Force | Out-Null

$a2  = New-ScheduledTaskAction -Execute $py -Argument "-m danyel aprovacoes" -WorkingDirectory $dir
$rep = (New-ScheduledTaskTrigger -Once -At "08:00" -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 12)).Repetition
$t2  = New-ScheduledTaskTrigger -Daily -At "08:00"; $t2.Repetition = $rep
Register-ScheduledTask -TaskPath "\Danyel\" -TaskName "Aprovacoes e envios" -Action $a2 -Trigger $t2 -Settings $set `
  -Description "Danyel: lê o APROVO do Daniel e envia com travas (8h-20h)" -Force | Out-Null

Get-ScheduledTask -TaskPath "\Danyel\" | ForEach-Object { "{0}  ->  próxima execução: {1}" -f $_.TaskName, (Get-ScheduledTaskInfo $_).NextRunTime }
Write-Host "`nDanyel automático ATIVADO. Deixe o Chrome aberto (com o Facebook e o WhatsApp Web logados)."
