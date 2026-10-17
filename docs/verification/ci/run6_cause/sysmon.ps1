# run6_cause CPU 기록기 (Windows). harness.py가 실험 동안 백그라운드로 띄운다.
# - 언어 설정과 무관하게 동작하도록 성능 카운터 원시값(Win32_PerfRawData_PerfProc_Process)을 쓰고,
#   두 표본 사이의 차분으로 "구간 평균" 사용률을 계산한다(순간값 아님).
# - 모든 %는 "기계 전체 용량 대비"(프로세스 CPU 시간 / (구간 길이 x 논리 코어 수) x 100)이다.
#   total = 100 - Idle, exp = 실험 프로세스(PID 파일), load = 부하 프로세스(PID 파일),
#   other = 그 밖의 프로세스 합(직접 합산), residual = total - exp - load(참고),
#   ide = other 중 VS Code·claude·node 프로세스(-IdePattern), top_other = other에 기여한 상위 8개(원인 기록).
# - 표본 간격 -Interval 초(기본 10). -Once면 -OnceGap 초 간격 표본 2개로 1줄만 쓰고 끝낸다(시작·끝 스냅샷).
# - -ExpPidFile/-LoadPidFile는 ';'로 여러 파일을 줄 수 있다.
# - -ParentPid 프로세스가 사라지거나 -StopFile이 생기면 끝낸다.
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$ExpPidFile = "",
    [string]$LoadPidFile = "",
    [int]$Interval = 10,
    [switch]$Once,
    [int]$OnceGap = 2,
    [string]$Tag = "",
    [int]$ParentPid = 0,
    [string]$StopFile = "",
    # 사용자 결정(2026-10-14): Claude Code가 VS Code 터미널 안에서 돌기 때문에 VS Code·claude는 닫을 수 없다.
    # 위반 기준(other)은 그대로 두고, 이 이름에 맞는 프로세스 사용량을 ide_pct로 따로 기록한다.
    [string]$IdePattern = '^(Code|claude|node)(#\d+)?$'
)
$ErrorActionPreference = "Stop"
$ncpu = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors

function Read-Pids([string]$files) {
    # 여러 파일은 ';'로 구분. 각 줄 하나에 PID 하나.
    $out = @()
    foreach ($f in ($files -split ';')) {
        if ($f -and (Test-Path $f)) {
            $out += @(Get-Content $f | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
        }
    }
    return $out
}

function Take-Sample {
    $rows = Get-CimInstance Win32_PerfRawData_PerfProc_Process |
        Select-Object Name, IDProcess, PercentProcessorTime, Timestamp_Sys100NS
    $h = @{}
    $ts = 0
    foreach ($r in $rows) {
        if ($r.Name -eq '_Total') { $ts = [double]$r.Timestamp_Sys100NS; continue }
        # PID로 구분한다(성능 카운터 인스턴스 이름 python#2 등은 프로세스가 생기고 없어질 때마다 바뀐다).
        $key = [int]$r.IDProcess
        if ($r.Name -eq 'Idle') { $key = -1 }
        $h[$key] = @([double]$r.PercentProcessorTime, [string]$r.Name)
        if ($ts -eq 0) { $ts = [double]$r.Timestamp_Sys100NS }
    }
    return @{ ts = $ts; procs = $h; wall = (Get-Date) }
}

function Diff-Sample($a, $b, [string]$tag) {
    $dt = $b.ts - $a.ts
    if ($dt -le 0) { return $null }
    $cap = $dt * $ncpu
    $expP = Read-Pids $ExpPidFile
    $expP += $PID
    $loadP = Read-Pids $LoadPidFile
    $idle = 0.0; $exp = 0.0; $load = 0.0; $other = 0.0; $ide = 0.0
    $per = @()
    $oth = @()
    foreach ($k in $b.procs.Keys) {
        if ($a.procs.ContainsKey($k)) { $d = $b.procs[$k][0] - $a.procs[$k][0] }
        else { $d = $b.procs[$k][0] }   # 구간 중에 새로 생긴 프로세스: 누적 CPU 시간 전체가 이 구간 것
        if ($d -lt 0) { continue }
        $procId = [int]$k; $name = $b.procs[$k][1]
        $pct = 100.0 * $d / $cap
        if ($procId -eq -1) { $idle += $pct; continue }
        if ($expP -contains $procId) { $exp += $pct }
        elseif ($loadP -contains $procId) { $load += $pct }
        else {
            $other += $pct
            if ($name -match $IdePattern) { $ide += $pct }
            $oth += [pscustomobject]@{ name = $name; pid = $procId; pct = [math]::Round($pct, 3) }
        }
        $per += [pscustomobject]@{ name = $name; pid = $procId; pct = [math]::Round($pct, 3) }
    }
    $total = [math]::Max(0.0, 100.0 - $idle)
    # other = 실험·부하가 아닌 프로세스의 합(직접 합산). residual = total - exp - load(구간 중 끝난 프로세스 몫이 여기에 섞임).
    $residual = [math]::Max(0.0, $total - $exp - $load)
    $top = @($per | Sort-Object pct -Descending | Select-Object -First 5)
    $topOther = @($oth | Where-Object { $_.pct -gt 0 } | Sort-Object pct -Descending | Select-Object -First 8)
    return [ordered]@{
        tag = $tag
        t_start = $a.wall.ToString("o"); t_end = $b.wall.ToString("o")
        interval_s = [math]::Round($dt / 1e7, 3)
        ncpu = $ncpu
        total_pct = [math]::Round($total, 3); exp_pct = [math]::Round($exp, 3)
        load_pct = [math]::Round($load, 3); other_pct = [math]::Round($other, 3)
        residual_pct = [math]::Round($residual, 3)
        ide_pct = [math]::Round($ide, 3); other_excl_ide_pct = [math]::Round($other - $ide, 3)
        exp_pids = $expP; load_pids = $loadP
        top = $top
        top_other = $topOther
    }
}

function Write-Line($obj) {
    if ($null -eq $obj) { return }
    $line = $obj | ConvertTo-Json -Compress -Depth 4
    [System.IO.File]::AppendAllText($Out, $line + "`n", [System.Text.UTF8Encoding]::new($false))
}

if ($Once) {
    $a = Take-Sample
    Start-Sleep -Seconds $OnceGap
    $b = Take-Sample
    Write-Line (Diff-Sample $a $b $Tag)
    exit 0
}

$prev = Take-Sample
while ($true) {
    Start-Sleep -Seconds $Interval
    $cur = Take-Sample
    Write-Line (Diff-Sample $prev $cur "periodic")
    $prev = $cur
    if ($StopFile -and (Test-Path $StopFile)) { break }
    if ($ParentPid -gt 0 -and -not (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)) { break }
}
