# Module 2 데이터 처리

첫 구현은 Module 1의 기존 호출 입력 계약을 사용하는 재현 가능한 유한 시나리오 생성기다.
실제 수요를 재현하는 모델이 아닌 통합·회귀 테스트용 합성 데이터다.
필드·좌표·시간 의미는 [공용 계약](contracts/common_contracts.md#호출-입력module-2--module-1)을 따른다.

## 시나리오 생성

저장소 루트에서 Python 3.13으로 실행한다. 추가 의존성은 없다.

```powershell
.\.venv\Scripts\python.exe -m module2_preprocessing --config configs/module2_scenario.toml --output data/generated/module2_calls.json
.\.venv\Scripts\python.exe -m module1_simulation --scenario data/generated/module2_calls.json
.\.venv\Scripts\python.exe -m pytest
```

`data/generated/`는 Git에서 제외한다. 출력 파일이 이미 있으면 덮어쓰지 않고 실패한다.
생성 파일은 Module 1이 읽는 호출 JSON이며 메타데이터 필드를 추가하지 않는다.
재현 시 사용한 TOML 설정과 코드 버전을 함께 보존해야 한다.

`generate_scenario(*, seed, call_count, start_seconds, interval_seconds, tick_seconds)`를
패키지의 공개 진입점으로 제공한다. 모든 인자는 필수다.
`tick_seconds`는 실행할 Module 1 설정과 같아야 한다.
호출 수는 0 이상 정수이며 시작 시각은 0 이상, 간격·tick은 양수다.
시작 시각과 간격은 tick에 정렬되어야 한다. 잘못된 값은 `ValueError`로 거부한다.

호출은 일정 간격으로 생성하며 전용 `random.Random(seed)`로 각 교차로를 균등 추출한다.
출발지와 목적지는 서로 다르게 선택한다. 동일 시드·설정은 같은 순서의 호출을 만든다.
이 선택은 Module 2 생성기 한정이며 현실 수요 분포나 프로젝트 공통 수요 정책으로 확정하지 않는다.
구역별 균등 분포도 의미하지 않는다. 외곽 교차로의 구역 귀속 규칙 때문이다.
전역 난수 상태와 Module 1 런타임 호출 생성 규칙을 사용하지 않는다.

## 학습 데이터셋 생성

처리 의미와 출력 열·JSON 스키마는 [공용 계약 7절](contracts/common_contracts.md#7-module-2--module-3-데이터-처리-기준)이 단일 원본이다.
Module 1 호출 JSON을 변경하지 않으며 새 라이브러리를 사용하지 않는다.

먼저 전체 관측 기간과 실제 수집 기록을 확인한다. 다음 예시는 24시간 관측 범위다.
마지막 호출 시각을 관측 종료 시각으로 추측하면 안 된다.

```powershell
.\.venv\Scripts\python.exe -m module2_preprocessing dataset --coverage-template --start-seconds 0 --end-seconds 86400 --output data/generated/coverage.csv
```

생성 템플릿은 모든 셀이 false다. 수집 로그 또는 완결된 합성 시나리오 생성 기록으로
확인한 셀만 true로 바꾼다. 호출 0건은 완료의 근거가 아니다.
실제 데이터의 경우 수집 완료 시점이 예측 시각보다 늦지 않은지도 확인해야 한다.

```powershell
.\.venv\Scripts\python.exe -m module2_preprocessing dataset --calls data/generated/calls.json --coverage data/generated/coverage.csv --start-seconds 0 --end-seconds 86400 --tick-seconds 0.05 --source-kind synthetic --coverage-evidence "완료를 확인한 생성 실행 기록 또는 수집 로그 위치" --output data/generated/training
```

실제 호출에는 `--source-kind real`을 명시한다. 한 실행에서 실제·합성 데이터를 혼합하지 않는다.
근거 문자열을 필수로 저장하지만 외부 수집 로그의 진위까지 자동 검증하지는 않는다.
기존 출력 디렉터리는 덮어쓰지 않는다. 출력은 분할 CSV 3개, 집계 CSV,
정규화한 coverage.csv, 품질·분할·누락·제외 행 수를 담은 report.json이다.
빈 분할은 헤더만 출력하고 보고서에서 경고한다. 데이터가 없는데 학습 성공으로 간주하면 안 된다.
부정확한 좌표·시각·중복 ID·중복 coverage·잘못된 열은 오류로 거부한다.
피처나 타깃의 결측은 보간하지 않는다. 분할은 원래 관측 기간 기준이므로 제외 후 행 비율은 달라진다.

공개 API는 `aggregate_calls`, `build_dataset`, `write_dataset`, `write_coverage_template`이다.
`aggregate_calls`와 `build_dataset`은 호출 JSON 객체와 coverage 행 목록을 받는다.
관측 시작·종료 시각과 tick을 명시한다. `build_dataset`은 출처·완료 근거도 필수다.
반환값은 `aggregates`, `splits`, `report`이며 `write_dataset`으로 저장한다.
Module 3 소비자가 아직 없어 실제 모델 학습 연동은 검증하지 않았다.

개발 시 생성한 실행 예시는 `data/generated/module2_training_demo/`에 있다(버전 관리 제외).
`generation_settings.json`은 기존 일정 간격 생성기의 재현 인자를 기록하고,
`coverage.csv`는 해당 유한 합성 생성이 완료된 기간에 한해서만 true다.
`dataset/`에는 Train 477행, Validation 90행, Test 90행과 보고서가 있다.
이는 처리 흐름 확인용이며 시간대별 변동 수요 모델로 생성한 데이터가 아니다.

## 샘플 한계와 변동 데이터 제안

기존 샘플 60건은 0~590초에 10초마다 발생한다. 5분당 도시 전체 30건으로 일정하며,
과거 60분과 미래 30분을 구성할 수 없어 학습용으로 사용할 수 없다.
관측 범위와 수집 근거도 호출 파일만으로는 확인할 수 없다.
보고서는 완전 관측된 도시 전체 구간의 총 호출량이 일정하면 경고한다.
구역별 위치가 무작위라도 도시 총량의 시간 변화를 학습하기에는 한계가 있다.

실제 데이터가 없을 때의 후속 생성 방안은 다음과 같다. 아직 구현한 수요 모델은 아니다.

- 설정 파일에서 시간대별 발생률과 구역별 가중치를 지정한다. 출퇴근 피크와 주거·업무 구역 차이를 표현한다.
- 시드로 고정한 전용 난수 흐름에서 구간별 호출 수와 구간 내 tick 정렬 시각을 추출한다.
- 구역을 먼저 선택하고 그 구역에 속하는 유효 교차로에서 출발지를 뽑아 외곽 귀속 편향을 통제한다.
- 목적지도 유효 교차로에서 선택하며 동일 시나리오를 비교 정책에 재사용한다.
- 최소 여러 날의 시나리오와 복수 시드를 생성한다. 생성 성공한 명시적 기간만 coverage 완료로 기록한다.
- 합성 데이터는 출처를 표시하고 실제 데이터에서의 예측 성능 근거와 구분한다.
