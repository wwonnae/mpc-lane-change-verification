"""호환용 진입점: `python -m thesis_v2.anomaly.dev_detect_a ...` = `dev_detect --detector A ...`
(2단계 기록 DESIGN.md §14의 명령 유지). 구현은 dev_detect.py."""
import sys

from .dev_detect import main

if __name__ == "__main__":
    if "--detector" not in sys.argv and "--check" not in sys.argv:
        sys.argv[1:1] = ["--detector", "A"]
    main()
