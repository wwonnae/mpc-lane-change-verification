#!/usr/bin/env bash
# 야간 실행 (2026-10-14 작성, run #6 대응 커밋 2와 함께 커밋) — Git Bash에서 저장소 어디서든 실행:
#   bash docs/verification/mutation/overnight_run.sh            # 정식 실행: 결과 파일만 커밋·푸시
#   bash docs/verification/mutation/overnight_run.sh --dry-run  # 단계별 짧은 실행, 커밋·푸시 없음, 출력은 저장소 밖
#
# 정식 실행 순서(앞 단계가 실패해도 다음 단계는 계속한다 — 서로 독립):
#   1) mutation 2차 전체 실행 → docs/verification/mutation/raw/run_after.json
#   2) RESULTS.md 사전 선언 변경 5번 규칙의 kill 재확인 → raw/run_after_tl_recheck.json
#   3) anomaly closed_loop --check: 저장 평가 폴더 20261012_142758_3층PC109_it3_closed_loop_eval
#      (선택지 5가 출력 불변인지 저장 평가 수준에서 확인. git 추적 파일 _check_diag_timing.csv를 덮어쓰고, 불일치면
#       _check_episodes_*.csv·_check_summary.json을 남긴다 — 모두 커밋 대상)
#   --check를 마지막에 두는 이유: 저장 평가 폴더의 파일을 바꾸므로, 먼저 하면 mutation 원자료의 git.dirty가 참으로 기록된다.
# 시작 전 확인: 작업 트리가 깨끗하고 HEAD == origin/main(git fetch 후). 아니면 아무것도 실행하지 않고 종료한다.
# 실행 전후로 PC 부하와 전원·절전 설정을 기록한다.
# 끝나면 아래 결과 경로만 git add해 커밋하고 git push(일반 푸시)한다. 결과 경로 밖의 변경이 있으면 커밋하지 않는다.
# 이 스크립트는 제품 코드·테스트·문서를 수정하지 않는다.
set -u

DRY=0
if [ "${1:-}" = "--dry-run" ]; then DRY=1; fi

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT" || exit 2
PY="$ROOT/.venv/Scripts/python.exe"
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
EVAL_DIR="thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval"
MUT=docs/verification/mutation
TS="$(date +%Y%m%d_%H%M%S)"
if [ $DRY -eq 1 ]; then
  WORK="$(cygpath -m "${TEMP:-/tmp}")/overnight_dryrun_$TS"
  LOGDIR="$WORK/overnight"
  RUN_AFTER="$WORK/run_after_dry.json"
  RECHECK_OUT="$WORK/run_after_tl_recheck_dry.json"
else
  LOGDIR="$MUT/raw/overnight/$TS"
  RUN_AFTER="$MUT/raw/run_after.json"
  RECHECK_OUT="$MUT/raw/run_after_tl_recheck.json"
fi
mkdir -p "$LOGDIR"
MAIN="$LOGDIR/overnight.log"
STEPS="$LOGDIR/steps.tsv"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$MAIN"; }

pc_state() {  # $1: before|after
  MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command '
    [Console]::OutputEncoding=[Text.Encoding]::UTF8
    "time: " + (Get-Date -Format o)
    "host: " + $env:COMPUTERNAME
    $os = Get-CimInstance Win32_OperatingSystem
    "uptime_since: " + $os.LastBootUpTime.ToString("o")
    "cpu_load_percent(3 samples, 2s): " + ((1..3 | ForEach-Object { (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average; Start-Sleep 2 }) -join ",")
    "free_mem_mb: " + [int]($os.FreePhysicalMemory/1024)
    "top_processes_by_cpu_seconds:"
    Get-Process | Sort-Object CPU -Descending | Select-Object -First 12 Name,Id,@{n="cpu_s";e={[math]::Round($_.CPU,1)}},@{n="ws_mb";e={[int]($_.WorkingSet64/1MB)}} | Format-Table -AutoSize | Out-String -Width 200
    "power_scheme:"; powercfg /getactivescheme
    "sleep_standby_idle(AC/DC):"; powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-Object -Last 3
    "hibernate_idle(AC/DC):"; powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE | Select-Object -Last 3
    "reboot_pending(WindowsUpdate RebootRequired key): " + (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired")
    "reboot_pending(CBS RebootPending key): " + (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending")
  ' > "$LOGDIR/pc_$1.txt" 2>&1
  log "PC 상태 기록($1): $LOGDIR/pc_$1.txt"
}

step() {  # step <이름> <명령...> — 표준출력/오류를 따로 남기고, 시작·끝 시각과 종료 코드를 steps.tsv에 적는다
  local name="$1"; shift
  local t0; t0="$(date -Iseconds)"
  log "단계 시작: $name — $*"
  "$@" > "$LOGDIR/$name.out" 2> "$LOGDIR/$name.err"
  local rc=$?
  local t1; t1="$(date -Iseconds)"
  printf '%s\t%s\t%s\t%s\n' "$name" "$t0" "$t1" "$rc" >> "$STEPS"
  log "단계 끝: $name — 종료 코드 $rc ($t0 → $t1)"
  return 0
}

log "overnight_run 시작 (dry-run=$DRY), 저장소 $ROOT, 로그 $LOGDIR"
printf 'step\tstart\tend\texit_code\n' > "$STEPS"

# ---- a. 시작 전 확인 ----
git fetch origin >> "$MAIN" 2>&1; FETCH_RC=$?
HEAD_SHA="$(git rev-parse HEAD)"
ORIGIN_SHA="$(git rev-parse origin/main 2>/dev/null || echo '?')"
# 앞선 정식 실행이 시작 전 확인에서 멈추며 남긴 로그(raw/overnight/ 아래 미추적 파일)는 확인에서 뺀다
DIRTY="$(git -c core.quotePath=false status --porcelain --untracked-files=all | grep -v -E "^\?\? $MUT/raw/overnight/" || true)"
log "git fetch 종료 코드 $FETCH_RC, HEAD=$HEAD_SHA, origin/main=$ORIGIN_SHA"
PRE_OK=1
if [ "$FETCH_RC" -ne 0 ]; then log "중단 사유: git fetch 실패"; PRE_OK=0; fi
if [ "$HEAD_SHA" != "$ORIGIN_SHA" ]; then log "중단 사유: HEAD와 origin/main이 다름"; PRE_OK=0; fi
if [ -n "$DIRTY" ]; then log "중단 사유: 작업 트리가 깨끗하지 않음:"; echo "$DIRTY" | tee -a "$MAIN"; PRE_OK=0; fi
if [ $PRE_OK -eq 0 ]; then
  if [ $DRY -eq 1 ]; then
    log "(dry-run: 시작 전 확인이 실패했지만 동작 확인을 위해 계속한다. 정식 실행이라면 여기서 종료한다)"
  else
    log "시작 전 확인 실패 — 아무것도 실행하지 않고 종료한다."
    exit 1
  fi
fi

pc_state before

# ---- b. 실행 ----
if [ $DRY -eq 1 ]; then
  # 1) mutation: fsm 모듈의 변이 3개만(mutate.py를 import해 generate 결과를 앞 3개로 줄여 run_all 호출 — 파일 수정 없음)
  step 1_mutation "$PY" -c "
import sys; from pathlib import Path
sys.path.insert(0, '$MUT')
import mutate
_g = mutate.generate
mutate.generate = lambda m, t: _g(m, t)[:3]
mutate.run_all(Path(r'$RUN_AFTER'), ['fsm'])
"
  # 2) kill 재확인: (a) 위 dry 결과로 전 과정, (b) 1차 결과(run_before)로 대상이 있는 경로를 1개·1회만
  step 2a_tl_recheck_dry "$PY" "$MUT/recheck_tl_kills.py" --run "$RUN_AFTER" --out "$RECHECK_OUT" --allow-dirty \
       --repeats 1 --work "$WORK/recheck_a"
  step 2b_tl_recheck_run_before "$PY" "$MUT/recheck_tl_kills.py" --run "$MUT/raw/run_before.json" \
       --out "$WORK/run_before_tl_recheck_dry.json" --allow-dirty --repeats 1 --max-targets 1 --work "$WORK/recheck_b"
  # 3) --check: 저장 평가 폴더를 저장소 밖으로 복사해 P0 조합만(부분 확인) — 저장소 파일을 건드리지 않는다
  EVAL_COPY="$WORK/eval_copy"
  cp -r "$EVAL_DIR" "$EVAL_COPY"
  step 3_closed_loop_check "$PY" -m thesis_v2.anomaly.closed_loop --check "$EVAL_COPY" --check-only P0
else
  step 1_mutation "$PY" "$MUT/mutate.py" run --out "$RUN_AFTER"
  step 2_tl_recheck "$PY" "$MUT/recheck_tl_kills.py" --run "$RUN_AFTER" --out "$RECHECK_OUT"
  step 3_closed_loop_check "$PY" -m thesis_v2.anomaly.closed_loop --check "$EVAL_DIR"
fi

pc_state after

# ---- d~f. 결과만 커밋·푸시 ----
summary() {
  while IFS=$'\t' read -r n s e rc; do
    [ "$n" = "step" ] && continue
    if [ "$rc" = "0" ]; then st="성공"; else st="실패(종료 코드 $rc)"; fi
    echo "- $n: $st ($s → $e)"
  done < "$STEPS"
}
if [ $DRY -eq 1 ]; then
  log "dry-run: 커밋·푸시하지 않는다. 단계 요약:"
  summary | tee -a "$MAIN"
  log "dry-run 출력: $WORK"
  exit 0
fi

ALLOWED_RE="^($MUT/raw/run_after\.json|$MUT/raw/run_after_tl_recheck\.json|$MUT/raw/overnight/.*|$EVAL_DIR/_check_[^/]*)$"
CHANGED="$(git -c core.quotePath=false status --porcelain --untracked-files=all | sed -E 's/^.{3}//; s/^"(.*)"$/\1/')"
OUTSIDE="$(echo "$CHANGED" | grep -v -E "$ALLOWED_RE" | grep -v '^$' || true)"
if [ -n "$OUTSIDE" ]; then
  log "커밋하지 않음: 결과 경로 밖의 변경이 있다:"
  echo "$OUTSIDE" | tee -a "$MAIN"
  exit 1
fi
log "커밋 대상:"; echo "$CHANGED" | tee -a "$MAIN"

MSG="$LOGDIR/commit_message.txt"
{
  echo "Mutation stage 4B: overnight run (mutation 2nd run, tl kill recheck, closed_loop --check)"
  echo
  echo "Automated by docs/verification/mutation/overnight_run.sh at HEAD $HEAD_SHA."
  echo "Only result files are committed (no code, docs or tests)."
  echo
  summary
  echo
  echo "Exit codes: closed_loop --check 0=match 1=mismatch; mutate 0=done; recheck 0=all kept 3=some to review."
  echo
  echo "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
} > "$MSG"

git add -- "$MUT/raw/overnight"
[ -f "$RUN_AFTER" ] && git add -- "$RUN_AFTER"
[ -f "$RECHECK_OUT" ] && git add -- "$RECHECK_OUT"
for f in "$EVAL_DIR"/_check_*; do [ -e "$f" ] && git add -- "$f"; done
# 커밋·푸시 결과는 커밋 뒤에 생기므로 저장소 밖 파일에 남긴다(저장소 작업 트리를 깨끗하게 두기 위해)
POST="$(cygpath -m "${TEMP:-/tmp}")/overnight_post_$TS.log"
log "커밋 시도 — 커밋·푸시 결과 로그: $POST"
git add -- "$MUT/raw/overnight"   # 마지막 로그 줄까지 포함
if git commit -q -F "$MSG"; then
  echo "[$(date -Iseconds)] 커밋 완료: $(git rev-parse HEAD)" >> "$POST"
  if git push >> "$POST" 2>&1; then
    echo "[$(date -Iseconds)] 푸시 완료" >> "$POST"
  else
    echo "[$(date -Iseconds)] 푸시 실패 — 로컬 커밋만 남김" >> "$POST"
  fi
else
  echo "[$(date -Iseconds)] 커밋 실패" >> "$POST"
fi
cat "$POST"
exit 0
