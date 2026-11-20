# 실행·테스트 명령 모음

이 문서는 저장소에서 현재 제공하는 테스트, 시각화, 데이터 생성과 보고서 명령을
Windows PowerShell, Windows Git Bash와 macOS bash/zsh에서 실행하는 방법을 정리한다.
모든 명령은 저장소 루트에서 실행한다.

## 1. 셸별 Python 준비

각 셸에서 `pyrepo` 함수를 한 번 정의하면 이후 명령은 운영체제와 관계없이 동일하다.
이 함수는 현재 터미널 세션에서만 유지된다.

### Windows PowerShell

```powershell
py -3.13 -m venv .venv
function pyrepo { & ".\.venv\Scripts\python.exe" @args }
pyrepo -m pip install -e ".[dev,simulation]"
```

### Windows Git Bash

```bash
py -3.13 -m venv .venv
pyrepo() { "./.venv/Scripts/python.exe" "$@"; }
pyrepo -m pip install -e ".[dev,simulation]"
```

Windows에 `py` 명령이 없으면 설치된 Python 3.13 실행 명령으로 바꾼다. Git Bash에서
가상환경을 활성화하려면 `source .venv/Scripts/activate`를 사용할 수 있지만, 아래 명령은
활성화 없이 `pyrepo`로 실행할 수 있다.

### macOS bash 또는 zsh

```bash
python3.13 -m venv .venv
pyrepo() { "./.venv/bin/python" "$@"; }
pyrepo -m pip install -e ".[dev,simulation]"
```

macOS에서 가상환경을 활성화하려면 `source .venv/bin/activate`를 사용할 수 있다.

## 2. 테스트

```bash
pyrepo -m pytest
pyrepo -m pytest tests/module1
pyrepo -m pytest tests/module2
pyrepo -m pytest tests/module3
pyrepo -m pytest tests/module4
pyrepo -m pytest tests/contracts
pyrepo -m pytest tests/integration
pyrepo -m pytest --collect-only -q
pyrepo -m pytest -x -vv
```

Module 1~4 종단 흐름과 보고서만 검사하려면 다음을 실행한다.

```bash
pyrepo -m pytest tests/integration/test_end_to_end_flow.py tests/integration/test_end_to_end_report.py tests/integration/test_visualize_end_to_end_script.py
```

## 3. Module 1 시뮬레이션

```bash
pyrepo -m module1_simulation
pyrepo -m module1_simulation --manual
pyrepo -m module1_simulation --call-interval 3
pyrepo -m module1_simulation --seed 7
pyrepo -m module1_simulation --headless --steps 1200 --events
pyrepo -m module1_simulation --scenario tests/fixtures/module1_calls.json
pyrepo -m module1_simulation --config configs/module1_demo.toml --calls-config configs/module1_calls.toml
```

기본 `tick_seconds=0.05`에서 `--steps 1200`은 시뮬레이션 60초다. 화면에서는 `Space`로
재생·정지, `R`로 초기화, `1`·`2`·`3`으로 배속 변경, 방향키로 회전, 휠로 확대·축소,
`D`로 좌표 표시, `Esc`로 종료한다. 수동 모드에서는 `T`, `C`, `Enter`를 사용한다.

## 4. Module 2 시나리오와 데이터셋

합성 호출을 만들고 Module 1에서 재생한다.

```bash
pyrepo -m module2_preprocessing --config configs/module2_scenario.toml --output data/generated/module2_calls.json
pyrepo -m module1_simulation --scenario data/generated/module2_calls.json
```

coverage 템플릿과 학습·검증·테스트 데이터셋을 만든다.

```bash
pyrepo -m module2_preprocessing dataset --coverage-template --start-seconds 0 --end-seconds 86400 --output data/generated/coverage.csv
pyrepo -m module2_preprocessing dataset --calls data/generated/module2_calls.json --coverage data/generated/coverage.csv --start-seconds 0 --end-seconds 86400 --tick-seconds 0.05 --source-kind synthetic --coverage-evidence "완료를 확인한 합성 시나리오 실행 기록" --output data/generated/module2_dataset
```

coverage 템플릿은 전부 `false`로 생성된다. 두 번째 명령 전에 실제로 완료를 확인한 셀만
`true`로 수정해야 한다. 데이터셋 출력은 `train.csv`, `validation.csv`, `test.csv`,
`aggregates.csv`, `coverage.csv`, `report.json`이다.

## 5. Module 3 예측과 보고서

`recent-trend` 대신 `rolling-mean-12`를 지정해 기준 모델을 비교할 수 있다.

```bash
pyrepo -m module3_prediction evaluate --input data/generated/module2_dataset/validation.csv --output data/generated/module3_validation.json --model recent-trend
pyrepo -m module3_prediction report --input data/generated/module2_dataset/validation.csv --output data/generated/module3_report.html --model recent-trend
pyrepo -m module3_prediction predict --input data/generated/module3_features.json --output data/generated/module3_forecast.json --model recent-trend
```

`predict` 입력은 `target_1`~`target_6`이 없는 Module 2 피처 JSON 한 행이어야 한다.
현재는 학습 명령과 모델 파일 생성 명령을 제공하지 않는다.

## 6. Module 4 배차·재배치

Module 4에는 독립 실행 CLI가 없다. 테스트 또는 종단 시각화로 확인한다.

```bash
pyrepo -m pytest tests/module4
pyrepo -m pytest tests/contracts/test_module4_commands.py
pyrepo -m pytest tests/integration/test_module4_flow.py
```

## 7. Module 1~4 종단 시각화

```bash
pyrepo scripts/visualize_end_to_end.py
pyrepo scripts/visualize_end_to_end.py --model recent-trend
pyrepo scripts/visualize_end_to_end.py --headless
pyrepo scripts/visualize_end_to_end.py --model recent-trend --headless
```

화면에서는 구역별 H1 예측, 사전 재배치, 동시 호출, 대기 호출, 승객 위치와 이벤트 로그를
확인할 수 있다.

## 8. Module 1~4 정책 비교 HTML

```bash
pyrepo -m scripts.evaluate_end_to_end --output data/generated/end_to_end_report.html
pyrepo -m scripts.evaluate_end_to_end --model recent-trend --output data/generated/end_to_end_recent_trend_report.html
```

보고서는 예측·실제 수요, 재배치 결정, 대기시간, 픽업·공차 거리와 상태별 시간을 비교한다.
통합 완료 판정표가 아니라 한 합성 시나리오의 실험 결과다.

## 9. HTML 열기

### Windows PowerShell

```powershell
Start-Process .\data\generated\module3_report.html
Start-Process .\data\generated\end_to_end_report.html
```

### Windows Git Bash

```bash
cmd.exe /c start "" "$(cygpath -w data/generated/module3_report.html)"
cmd.exe /c start "" "$(cygpath -w data/generated/end_to_end_report.html)"
```

### macOS bash 또는 zsh

```bash
open data/generated/module3_report.html
open data/generated/end_to_end_report.html
```

## 10. 도움말

```bash
pyrepo -m module1_simulation --help
pyrepo -m module2_preprocessing --help
pyrepo -m module2_preprocessing dataset --help
pyrepo -m module3_prediction --help
pyrepo -m module3_prediction evaluate --help
pyrepo -m module3_prediction report --help
pyrepo scripts/visualize_end_to_end.py --help
pyrepo -m scripts.evaluate_end_to_end --help
```

Module 2 시나리오, 데이터셋 디렉터리와 Module 3 JSON 출력은 기존 경로를 덮어쓰지 않는다.
새 출력 이름을 사용한다. Module 3 HTML과 종단 비교 HTML은 기존 파일을 보존하고 이름에
`_2`, `_3` 접미사를 붙인다.
