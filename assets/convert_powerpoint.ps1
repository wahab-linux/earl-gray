param([Parameter(Mandatory=$true)][string]$SourceFile,
      [Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference = 'Stop'
$application = $null
$presentation = $null
$previousSecurity = $null
$previousAlerts = $null
# PowerPoint may reuse an existing instance. Never quit a user's running app.
$owned = -not [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
try {
    $application = New-Object -ComObject PowerPoint.Application
    $previousSecurity = $application.AutomationSecurity
    $previousAlerts = $application.DisplayAlerts
    $application.AutomationSecurity = 3
    $application.DisplayAlerts = 1
    $presentation = $application.Presentations.Open($SourceFile, -1, 0, 0)
    $presentation.SaveAs($OutputFile, 32)
    Write-Output 'Presentation exported to PDF.'
} finally {
    if ($null -ne $presentation) {
        $presentation.Close()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($presentation)
    }
    if ($null -ne $application) {
        if ($null -ne $previousSecurity) { $application.AutomationSecurity = $previousSecurity }
        if ($null -ne $previousAlerts) { $application.DisplayAlerts = $previousAlerts }
        if ($owned) { $application.Quit() }
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($application)
    }
}
