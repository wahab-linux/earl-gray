param([Parameter(Mandatory=$true)][string]$LogPath)
$Host.UI.RawUI.WindowTitle = 'Earl Gray - Debug terminal'
Write-Host 'EARL GRAY | Live process log' -ForegroundColor Cyan
Write-Host 'Imports, slide conversion, previews, merges, and errors appear here.'
Write-Host 'Closing this terminal does not close Earl Gray.'
Write-Host "Log file: $LogPath`n" -ForegroundColor DarkGray
Get-Content -LiteralPath $LogPath -Encoding UTF8 -Tail 200 -Wait
