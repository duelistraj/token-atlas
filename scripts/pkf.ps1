[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',
    [string]$Profile = 'core',
    [Alias('retrieval-exports')]
    [string]$RetrievalExports = 'off',
    [string]$Simulation = 'changed',
    [Alias('token-budget')]
    [string]$TokenBudget = 'summary',
    [Alias('validation-strictness')]
    [string]$ValidationStrictness = 'advisory',
    [switch]$Ci,
    [Alias('h')]
    [switch]$Help,
    [Alias('bench-suite')]
    [string]$BenchSuite = 'quick',
    [Alias('bench-output')]
    [string]$BenchOutput = 'text',
    [string]$Intent = '',
    [string[]]$Paths = @()
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$pkfPath = Join-Path $repoRoot '.ai\PKF.md'

$allowedCommands = @('help', 'init', 'maintain', 'extract', 'optimize', 'validate', 'export', 'simulate', 'bench')
$allowedProfiles = @('core', 'ci', 'retrieval', 'full')
$allowedExports = @('off', 'rag', 'graph', 'all')
$allowedSimulation = @('off', 'changed', 'required', 'all')
$allowedTokenBudget = @('summary', 'full')
$allowedStrictness = @('advisory', 'ci')
$allowedBenchSuites = @('quick', 'core', 'full')
$allowedBenchOutputs = @('text', 'json')

function Show-Help {
    Write-Output 'PKF thin workflow wrapper'
    Write-Output ''
    Write-Output 'This script selects documented Token Atlas workflows. It does not implement extraction, optimization, validation, benchmark scoring, or retrieval export logic.'
    Write-Output ''
    Write-Output 'Usage:'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 <command> [options]'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 help'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 --help'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate --help'
    Write-Output ''
    Write-Output 'Commands:'
    Write-Output '  init       Select initialize.md. Use when .ai/PKF.md is missing.'
    Write-Output '  maintain   Select maintenance.md for changed, renamed, deleted, and affected knowledge.'
    Write-Output '  extract    Select extract.md for source-backed OKF knowledge extraction.'
    Write-Output '  optimize   Select optimize.md for routing, duplication, and token budget cleanup.'
    Write-Output '  validate   Select validation.md for structure, metadata, references, routing, simulation, and token impact.'
    Write-Output '  simulate   Select simulate.md for retrieval prediction from task intent and changed paths.'
    Write-Output '  export     Select export.md when retrieval exports are explicitly enabled.'
    Write-Output '  bench      Select benchmark.md for fixture-based skill quality evals.'
    Write-Output ''
    Write-Output 'Profiles:'
    Write-Output '  core        Default. Initialize/maintain, extract, optimize, lightweight validation.'
    Write-Output '  ci          Strict validation, required simulations, full token budget gates.'
    Write-Output '  retrieval   Core workflow plus retrieval export generation when enabled.'
    Write-Output '  full        CI strictness, all simulations, full token budget, all retrieval exports.'
    Write-Output ''
    Write-Output 'Options:'
    Write-Output '  -Profile, --profile                            core|ci|retrieval|full       default: core'
    Write-Output '  -RetrievalExports, --retrieval-exports          off|rag|graph|all            default: off'
    Write-Output '  -Simulation, --simulation                       off|changed|required|all     default: changed'
    Write-Output '  -TokenBudget, --token-budget                    summary|full                 default: summary'
    Write-Output '  -ValidationStrictness, --validation-strictness  advisory|ci                  default: advisory'
    Write-Output '  -Ci, --ci                                       Shortcut for CI validation defaults.'
    Write-Output '  -BenchSuite, --bench-suite                      quick|core|full              default: quick'
    Write-Output '  -BenchOutput, --bench-output                    text|json                    default: text'
    Write-Output '  -Intent, --intent                               Natural-language task for simulate.'
    Write-Output '  -Paths, --paths                                 Changed paths for simulate.'
    Write-Output '  -Help, --help, help                             Show this help.'
    Write-Output ''
    Write-Output 'Recommended defaults:'
    Write-Output '  profile=core, retrieval_exports=off, simulation=changed, token_budget=summary, validation_strictness=advisory'
    Write-Output ''
    Write-Output 'Examples:'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 init'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 validate -Ci'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 simulate -Intent "change an API route" -Paths src/routes.ts'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 export -RetrievalExports graph'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 export --retrieval-exports graph'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 bench -BenchSuite core'
    Write-Output '  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pkf.ps1 bench --bench-suite full --bench-output json'
    Write-Output ''
    Write-Output 'Codex skill usage:'
    Write-Output '  In Codex, ask for the token-atlas skill by name and include options in natural language, for example:'
    Write-Output '  "Use token-atlas with profile=ci, simulation=required, token_budget=full."'
    Write-Output ''
    Write-Output 'Exit codes:'
    Write-Output '  0  Valid command request, help output, or advisory findings.'
    Write-Output '  1  CI blocking validation error detected by the wrapper.'
    Write-Output '  2  Invalid command or invalid option value.'
}

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

if ($Help -or $Command -eq 'help') {
    Show-Help
    exit 0
}

Test-AllowedValue -Name 'command' -Value $Command -Allowed $allowedCommands
Test-AllowedValue -Name 'profile' -Value $Profile -Allowed $allowedProfiles
Test-AllowedValue -Name 'retrieval_exports' -Value $RetrievalExports -Allowed $allowedExports
Test-AllowedValue -Name 'simulation' -Value $Simulation -Allowed $allowedSimulation
Test-AllowedValue -Name 'token_budget' -Value $TokenBudget -Allowed $allowedTokenBudget
Test-AllowedValue -Name 'validation_strictness' -Value $ValidationStrictness -Allowed $allowedStrictness
Test-AllowedValue -Name 'bench_suite' -Value $BenchSuite -Allowed $allowedBenchSuites
Test-AllowedValue -Name 'bench_output' -Value $BenchOutput -Allowed $allowedBenchOutputs

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
    bench = 'benchmark.md'
}

$workflow = $workflowByCommand[$Command]
$pkfExists = Test-Path -LiteralPath $pkfPath

Write-Output 'PKF Tool Request'
Write-Output "Command: $Command"
Write-Output "Workflow: .agents/skills/token-atlas/$workflow"
Write-Output "Profile: $Profile"
Write-Output "retrieval_exports: $RetrievalExports"
Write-Output "simulation: $Simulation"
Write-Output "token_budget: $TokenBudget"
Write-Output "validation_strictness: $ValidationStrictness"

if ($Command -eq 'simulate') {
    Write-Output "Intent: $Intent"
    Write-Output ('Paths: ' + (($Paths | Where-Object { $_ }) -join ', '))
}

if ($Command -eq 'bench') {
    Write-Output "bench_suite: $BenchSuite"
    Write-Output "bench_output: $BenchOutput"
    Write-Output 'Benchmark target: isolated fixtures under .agents/skills/token-atlas/benchmarks/fixtures.'
}

if ($Command -ne 'bench' -and -not $pkfExists) {
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

