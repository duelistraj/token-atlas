[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',
    [string]$Profile = 'core',
    [string]$RetrievalExports = 'off',
    [string]$Simulation = 'changed',
    [string]$TokenBudget = 'summary',
    [string]$ValidationStrictness = 'advisory',
    [switch]$Ci,
    [string]$Intent = '',
    [string[]]$Paths = @()
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$pkfPath = Join-Path $repoRoot '.ai\PKF.md'

$allowedCommands = @('help', 'init', 'maintain', 'extract', 'optimize', 'validate', 'export', 'simulate')
$allowedProfiles = @('core', 'ci', 'retrieval', 'full')
$allowedExports = @('off', 'rag', 'graph', 'all')
$allowedSimulation = @('off', 'changed', 'required', 'all')
$allowedTokenBudget = @('summary', 'full')
$allowedStrictness = @('advisory', 'ci')

function Test-AllowedValue {
    param(
        [string]$Name,
        [string]$Value,
        [string[]]$Allowed
    )
    if ($Allowed -notcontains $Value) {
        [Console]::Error.WriteLine("Invalid $Name '$Value'. Allowed values: $($Allowed -join ', ').")
        exit 2
    }
}

Test-AllowedValue -Name 'command' -Value $Command -Allowed $allowedCommands
Test-AllowedValue -Name 'profile' -Value $Profile -Allowed $allowedProfiles
Test-AllowedValue -Name 'retrieval_exports' -Value $RetrievalExports -Allowed $allowedExports
Test-AllowedValue -Name 'simulation' -Value $Simulation -Allowed $allowedSimulation
Test-AllowedValue -Name 'token_budget' -Value $TokenBudget -Allowed $allowedTokenBudget
Test-AllowedValue -Name 'validation_strictness' -Value $ValidationStrictness -Allowed $allowedStrictness

if ($Ci) {
    $Profile = 'ci'
    $ValidationStrictness = 'ci'
    $Simulation = 'required'
    $TokenBudget = 'full'
}

if ($Profile -eq 'ci') {
    if (-not $PSBoundParameters.ContainsKey('ValidationStrictness')) { $ValidationStrictness = 'ci' }
    if (-not $PSBoundParameters.ContainsKey('Simulation')) { $Simulation = 'required' }
    if (-not $PSBoundParameters.ContainsKey('TokenBudget')) { $TokenBudget = 'full' }
}

if ($Profile -eq 'full') {
    if (-not $PSBoundParameters.ContainsKey('ValidationStrictness')) { $ValidationStrictness = 'ci' }
    if (-not $PSBoundParameters.ContainsKey('Simulation')) { $Simulation = 'all' }
    if (-not $PSBoundParameters.ContainsKey('TokenBudget')) { $TokenBudget = 'full' }
    if (-not $PSBoundParameters.ContainsKey('RetrievalExports')) { $RetrievalExports = 'all' }
}

$workflowByCommand = @{
    init = 'initialize.md'
    maintain = 'maintenance.md'
    extract = 'extract.md'
    optimize = 'optimize.md'
    validate = 'validation.md'
    export = 'export.md'
    simulate = 'simulate.md'
}

if ($Command -eq 'help') {
    Write-Output 'PKF thin workflow wrapper'
    Write-Output ''
    Write-Output 'Usage:'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 init'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 maintain'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 extract'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 optimize'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate [-Ci]'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 export -RetrievalExports rag|graph|all'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 simulate -Intent "change an API route" [-Paths src/routes.ts]'
    Write-Output ''
    Write-Output 'This wrapper selects documented workflows. It does not implement PKF extraction, validation, optimization, or export logic.'
    exit 0
}

$workflow = $workflowByCommand[$Command]
$pkfExists = Test-Path -LiteralPath $pkfPath

Write-Output 'PKF Tool Request'
Write-Output "Command: $Command"
Write-Output "Workflow: .agents/skills/zephyr-pkf/$workflow"
Write-Output "Profile: $Profile"
Write-Output "retrieval_exports: $RetrievalExports"
Write-Output "simulation: $Simulation"
Write-Output "token_budget: $TokenBudget"
Write-Output "validation_strictness: $ValidationStrictness"

if ($Command -eq 'simulate') {
    Write-Output "Intent: $Intent"
    Write-Output ('Paths: ' + (($Paths | Where-Object { $_ }) -join ', '))
}

if (-not $pkfExists) {
    Write-Output 'Startup: .ai/PKF.md is missing; run pkf init before repository analysis.'
    if ($Command -eq 'validate' -and $ValidationStrictness -eq 'ci') {
        Write-Error 'CI validation failed: missing .ai/PKF.md startup contract.'
        exit 1
    }
}

if ($Command -eq 'export' -and $RetrievalExports -eq 'off') {
    Write-Output 'Retrieval exports disabled; no export workflow required.'
    exit 0
}

if ($Command -eq 'validate' -and $ValidationStrictness -eq 'ci') {
    Write-Output 'CI mode selected; blocking validation errors must exit nonzero when reported by validation.md.'
}

Write-Output 'Next: execute the selected documented PKF workflow with these options.'
exit 0