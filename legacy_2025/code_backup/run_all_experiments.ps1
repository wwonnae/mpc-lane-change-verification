# 전체 실험 파이프라인 자동 실행 스크립트 (PowerShell)
# 5개 그래프를 모두 생성합니다

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Lane Change MPC - Full Experiment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 설정
$DATASET = "synthetic_dataset.npz"
$N_SAMPLES = 10000
$EPOCHS_MAIN = 100
$SAVE_DIR_MAIN = "./models_main"
$ANALYSIS_DIR = "./analysis"
$SENSITIVITY_DIR = "./sensitivity_analysis"
$CONSTRAINT_DIR = "./constraint_analysis"

# 1. 합성 데이터 생성
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Step 1/5: Generating synthetic dataset" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python generate_synthetic_data.py --n_samples $N_SAMPLES --output $DATASET --seed 42

if (-not (Test-Path $DATASET)) {
    Write-Host "ERROR: Dataset generation failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dataset created: $DATASET" -ForegroundColor Green
Write-Host ""

# 2. 데이터 분석 (그래프 3: 상태별 분포)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Step 2/5: Analyzing dataset distribution" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python analyze_dataset.py --dataset $DATASET --save_dir $ANALYSIS_DIR

if (-not (Test-Path "$ANALYSIS_DIR/dataset_analysis.png")) {
    Write-Host "ERROR: Dataset analysis failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dataset analysis complete" -ForegroundColor Green
Write-Host "[OK] Graph 3: $ANALYSIS_DIR/dataset_analysis.png" -ForegroundColor Green
Write-Host ""

# 3. 메인 학습 (그래프 1, 2: Loss curve, 산점도)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Step 3/5: Training main policy model" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python train_policy.py --dataset $DATASET --hidden_dims 128 128 64 --dropout 0.1 --epochs $EPOCHS_MAIN --batch_size 256 --lr 1e-3 --save_dir $SAVE_DIR_MAIN --patience 20 --use_batchnorm

if (-not (Test-Path "$SAVE_DIR_MAIN/best_model.pth")) {
    Write-Host "ERROR: Training failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Training complete" -ForegroundColor Green
Write-Host "[OK] Graph 1: $SAVE_DIR_MAIN/training_history.png" -ForegroundColor Green
Write-Host "[OK] Graph 2: $SAVE_DIR_MAIN/evaluation.png" -ForegroundColor Green
Write-Host ""

# 4. 파라미터 민감도 분석 (그래프 4)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Step 4/5: Parameter sensitivity analysis" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python sensitivity_analysis.py --dataset $DATASET --save_dir $SENSITIVITY_DIR --quick

if (-not (Test-Path "$SENSITIVITY_DIR/sensitivity_analysis.png")) {
    Write-Host "ERROR: Sensitivity analysis failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Sensitivity analysis complete" -ForegroundColor Green
Write-Host "[OK] Graph 4: $SENSITIVITY_DIR/sensitivity_analysis.png" -ForegroundColor Green
Write-Host ""

# 5. 제약 위반률 분석 (그래프 5)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Step 5/5: Constraint violation analysis" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python constraint_analysis.py --model "$SAVE_DIR_MAIN/best_model.pth" --dataset $DATASET --save_dir $CONSTRAINT_DIR

if (-not (Test-Path "$CONSTRAINT_DIR/constraint_analysis.png")) {
    Write-Host "ERROR: Constraint analysis failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Constraint analysis complete" -ForegroundColor Green
Write-Host "[OK] Graph 5: $CONSTRAINT_DIR/constraint_analysis.png" -ForegroundColor Green
Write-Host ""

# 완료 메시지
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  ✅ ALL EXPERIMENTS COMPLETE!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Generated Graphs:" -ForegroundColor Cyan
Write-Host "  1. Loss Curves:        $SAVE_DIR_MAIN/training_history.png"
Write-Host "  2. Scatter Plots:      $SAVE_DIR_MAIN/evaluation.png"
Write-Host "  3. Data Distribution:  $ANALYSIS_DIR/dataset_analysis.png"
Write-Host "  4. Sensitivity:        $SENSITIVITY_DIR/sensitivity_analysis.png"
Write-Host "  5. Constraints:        $CONSTRAINT_DIR/constraint_analysis.png"
Write-Host ""
Write-Host "📁 Output Directories:" -ForegroundColor Cyan
Write-Host "  - Main model:     $SAVE_DIR_MAIN"
Write-Host "  - Analysis:       $ANALYSIS_DIR"
Write-Host "  - Sensitivity:    $SENSITIVITY_DIR"
Write-Host "  - Constraints:    $CONSTRAINT_DIR"
Write-Host ""
Write-Host "🎉 You can now use these graphs in your report!" -ForegroundColor Green
