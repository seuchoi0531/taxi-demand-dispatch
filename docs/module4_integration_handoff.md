# Module 4 검증·시각화 및 Module 1·2 인계 가이드

이 문서는 Module 4 Pull Request를 독립적으로 검증하는 방법과, Module 1·2 담당자가
통합 전에 추가할 기능, 각 기능을 합친 뒤 수행할 테스트와 시각화를 구분한다.

## 1. 현재 확인 가능한 범위

현재 Module 4는 Module 1 관측과 선택적인 Module 3 예측을 받아 명령 계획을 만드는
순수 정책이다. 실제 시뮬레이션 상태를 직접 변경하지 않는다.

| 범위 | 현재 상태 | 지금 검증 가능 여부 |
|---|---|---|
| FIFO·최근접 택시 배차 선택 | 구현됨 | 가능 |
| 예측 수요에 따른 재배치 명령 선택 | 구현됨 | 가능 |
| `dispatch` 명령의 Module 1 실행 | 구현됨 | 가능 |
| `reposition` 명령의 실제 차량 이동 | Module 1 미구현 | 불가능 |
| 시뮬레이션 이력에서 온라인 예측 피처 생성 | Module 2 미구현 | 불가능 |
| 동일 시나리오 기준·예측 정책 비교 | 통합 실행기 미구현 | 불가능 |
| Module 4 전용 HTML 시각화 | 미구현 | 추가 후 가능 |

따라서 현재 PR에서는 **정책이 올바른 명령을 선택하는지**를 검증할 수 있다.
실제 이동 결과와 예측 데이터 파이프라인까지 포함한 효과 검증은 Module 1·2 인계 작업 후 한다.

## 2. 현재 Module 4 PR 테스트

저장소 루트에서 Python 3.13 가상환경으로 실행한다.

```powershell
# 정책 선택, 동률 해결, 입력 검증
.\.venv\Scripts\python.exe -m pytest tests/module4

# Module 1 dispatch 호환성과 향후 reposition 명령 형식
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_module4_commands.py

# 기존 모듈을 포함한 전체 회귀
.\.venv\Scripts\python.exe -m pytest
```

현재 테스트는 다음을 확인한다.

- 오래 기다린 호출을 먼저 처리한다.
- 도로 거리와 ID 동률 규칙이 재현 가능하다.
- 같은 택시를 배차와 재배치에 중복 사용하지 않는다.
- 현재 구역의 예측 필요량을 초과한 idle 택시만 부족 구역으로 보낸다.
- 9개 구역 예측 누락, 예측·관측 시각 불일치와 미래 호출을 오류로 거부한다.
- 입력 객체를 변경하지 않는다.
- 기존 `dispatch` 명령은 Module 1이 그대로 실행할 수 있다.

이 테스트가 통과해도 실제 재배치 이동과 성능 개선을 검증한 것은 아니다.

## 3. Module 4를 통합 전에 시각적으로 확인하는 방법

Module 1의 재배치 구현을 기다리지 않고 정책 선택을 시각적으로 확인하려면 Module 4가
자체 포함 HTML 계획 보고서를 추가해야 한다. 이는 **Module 4 담당 범위**다.

### Module 4 담당자가 추가할 것

1. 고정 관측 fixture 1개와 같은 시각의 9개 구역 예측 fixture 1개
2. `build_plan()` 결과를 저장하는 `module4-plan-0.1` JSON
3. 외부 JavaScript·서버 없이 열리는 자체 포함 HTML 생성기
4. 기존 결과를 덮어쓰지 않는 보고서 출력 함수 또는 CLI
5. 보고서 구조와 덮어쓰기 방지에 대한 `tests/module4/test_report.py`

HTML에는 최소한 다음 화면이 필요하다.

- 3×3 구역의 horizon 1 예측 수요 히트맵
- 구역별 현재 idle 택시 수, 필요 대수와 부족·잉여 대수
- 현재 택시와 대기 호출 위치
- 배차 연결선과 재배치 출발→목적 화살표
- 명령 순서와 `decisions`의 선택 근거 표
- 같은 입력을 다시 실행했을 때 동일한 명령이 나오는지 확인하는 요약

이 보고서는 **명령 선택 시각화**다. 차량이 실제로 이동했음을 보여주는 애니메이션이나
대기 시간 개선 근거로 사용하면 안 된다.

권장 실행 형태는 다음과 같다. 이 명령은 보고서 기능을 구현한 뒤 제공한다.

```powershell
.\.venv\Scripts\python.exe -m module4_dispatch report `
  --observation tests/fixtures/module4_observation.json `
  --forecasts tests/fixtures/module4_forecasts.json `
  --block-size-m 20 `
  --output data/generated/module4_plan.html
```

## 4. Module 1 담당자 인계

단일 원본은 [공용 계약 9절](contracts/common_contracts.md#9-module-4-배차재배치-결정--임시-01)이다.
Module 1은 정책을 구현하거나 Module 4를 import하지 않는다. 외부에서 받은 명령을 실행하고
관측·이벤트·측정값을 반환하는 역할만 맡는다.

### Module 1 담당자가 만들 것

- `reposition(taxi_id, destination) -> None`
- `apply_command({"type":"reposition", ...})` 지원
- 택시 `repositioning` 상태와 최단 도로 이동
- `reposition_started`, `reposition_completed` 이벤트
- `reposition_seconds` 측정과 공차 거리 반영
- 같은 위치 즉시 완료, 운행 중 택시 거부, 잘못된 좌표·필드 거부
- 외부 정책 명령을 적용할 때 개발용 자동 배차를 끌 수 있는 실행 경계

마지막 항목은 Module 1이 Module 4에 의존하라는 의미가 아니다. 통합 실행기가
`observe() → build_plan() → apply_command()`를 호출할 수 있도록 개발용 자동 연결기와
외부 명령 모드를 동시에 실행하지 않게 해야 한다.

### Module 1 담당자가 추가할 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest tests/module1
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_module1_boundary.py
```

- idle 택시만 재배치할 수 있다.
- 이동 중 `call_id`는 `None`이고 상태는 `repositioning`이다.
- 목적지 도착 후 `idle`로 돌아간다.
- 시작·완료 이벤트의 시각과 목적지가 맞는다.
- 재배치 시간과 거리가 상태별 시간·전체 거리와 일치한다.
- 배차 중·승객 탑승 중·재배치 중 중복 명령을 거부한다.
- 잘못된 명령은 상태를 바꾸지 않고 `command_rejected`를 기록한다.

Module 1 작업 완료 조건은 Module 4가 만든 `reposition` 명령을 변환 없이
`Simulation.apply_command()`에 전달하여 이동 완료까지 관측할 수 있는 것이다.

## 5. Module 2 담당자 인계

현재 Module 2의 `build_dataset()`은 미래 타깃을 포함한 오프라인 학습·평가 데이터용이다.
이를 런타임 추론에 사용하면 미래 정보 유출 위험이 있다. Module 2는 [공용 계약 7절의
온라인 추론 피처 인계 요청](contracts/common_contracts.md#module-2-온라인-추론-피처-인계-요청)을 구현한다.

### Module 2 담당자가 만들 것

```python
from module2_preprocessing import build_inference_features

rows = build_inference_features(
    observed_calls,
    coverage,
    prediction_time_seconds=simulation_time,
    source_kind="synthetic",
)
```

- 예측 시각 직전 60분만 사용하는 타깃 없는 피처 행 9개
- 기존 lag·rolling mean 의미와 완전히 같은 계산
- 호출이 없는 완료 구간과 수집 누락 구간 구분
- 미래 호출·미완료 coverage·300초 비정렬 시각 거부
- `target_1`~`target_6`을 만들거나 반환하지 않음
- Module 3 `predict()`에 변환 없이 전달 가능한 필드와 값

### Module 2 담당자가 추가할 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest tests/module2
.\.venv\Scripts\python.exe -m pytest tests/contracts
```

- 반환 행이 정확히 9개이며 시각·구역 순으로 정렬된다.
- `lag_1`은 `[t-300,t)`, `lag_12`는 `[t-3600,t-3300)`만 센다.
- 시각 `t`에 발생한 호출은 온라인 피처에 포함하지 않는다.
- 108개 coverage 셀 중 하나라도 미완료면 실패한다.
- 완료된 무호출 구간은 0으로 계산한다.
- 반환 필드에 타깃이 없으며 Module 3 `predict()`가 그대로 읽는다.
- 전체 미래 시나리오를 전달하거나 참조하지 않는다.

Module 2 작업 완료 조건은 반환한 9개 행을 Module 3에 전달하여 같은 시각의 9개 예측을
만들고, 그 결과를 Module 4 `build_plan()`이 별도 변환 없이 소비하는 것이다.

## 6. Module 1·2 작업 후 통합 테스트

통합 데이터 흐름은 다음 순서를 고정한다.

```text
Module 1 현재 관측·발생 호출
  → Module 2 과거 60분 피처 9개
  → Module 3 같은 시각 예측 9개
  → Module 4 배차·재배치 계획
  → Module 1 명령 실행과 다음 관측
```

통합 실행기는 어느 모듈의 내부 파일도 import하지 않고 공개 진입점만 사용한다.
300초 예측 경계가 아닌 tick에는 예측을 새로 만들지 않고 기준 배차만 판단한다.
300초 경계에서는 그 시각까지 발생한 호출을 배차 대상으로 볼 수 있지만, 시각 `t` 호출을
과거 수요 피처에 넣어서는 안 된다.

동일한 호출 시나리오·택시 초기 위치·속도·tick·시드로 두 실행을 만든다.

1. 기준 실행: `build_plan(observation, block_size_m=...)`
2. 예측 실행: 300초마다 `forecasts`를 포함해 `build_plan(...)`
3. 두 실행 모두 Module 4 명령 외의 자동 배차를 끈다.
4. 종료 시각과 호출 입력을 동일하게 유지한다.

추가할 통합 테스트는 다음과 같다.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_module4_flow.py
.\.venv\Scripts\python.exe -m pytest
```

- 같은 입력과 시드는 같은 명령·이벤트·지표를 만든다.
- 미래 호출이 Module 2·3·4 입력에 노출되지 않는다.
- 한 택시가 배차와 재배치에 동시에 사용되지 않는다.
- 재배치된 택시가 도착한 뒤 정상적으로 새 호출을 배정받는다.
- 모든 택시의 상태별 시간 합이 관측 기간과 같다.
- 기준·예측 실행의 차이는 예측과 재배치 정책뿐이다.
- 정책이 나빠지는 경우도 정상 결과로 기록하며 실패나 개선으로 조작하지 않는다.

공차 시간의 최종 산식은 아직 미확정이므로 우선 다음 원시 구성요소를 함께 기록한다.

- `idle_seconds`, `pickup_seconds`, `occupied_seconds`, `reposition_seconds`
- `distance_m`, `empty_distance_m`
- 완료·대기·탑승 완료 호출 수
- 평균·최대·분위수 승객 대기 시간
- 명령 거부 수

## 7. 통합 후 시각화

통합 시각화는 Module 4 단독 계획 보고서와 실제 실행 비교 보고서를 분리한다.

### 실행 비교 HTML

Module 4 또는 별도 통합 계층에서 두 실행의 계획·이벤트·지표를 받아 자체 포함 HTML을 만든다.

- 기준 정책과 예측 정책의 지표 비교 표
- 시각별 waiting·idle·to_pickup·occupied·repositioning 택시 수
- 300초별 예측 수요·현재 공급·부족량 3×3 히트맵
- 실제 재배치 이동 경로와 완료 시각
- 평균뿐 아니라 실행별 원시값과 악화 여부
- 사용한 시드, 설정, 코드 버전과 데이터 출처

### Panda3D 실행 화면

실제 차량 이동을 눈으로 확인해야 하면 Module 1 화면에 정책을 넣지 말고 외부에서 생성한
명령을 주입한다. 재배치 차량의 색 또는 표식을 별도로 표시하고 목적 구역을 강조할 수 있다.
이 화면은 동작 확인용이며 성능 근거는 HTML의 재현 가능한 지표로 판단한다.

## 8. PR에 전달할 요약문

다음 문구를 Module 4 PR 설명의 후속 작업 항목으로 사용할 수 있다.

```markdown
## 다음 통합 전 요청

### Module 1
- 공용 계약 9절에 따라 `reposition(taxi_id, destination)`와
  `apply_command({"type":"reposition", ...})`를 구현해 주세요.
- `repositioning` 상태, 시작·완료 이벤트, `reposition_seconds`와 공차 거리 측정을
  단위·계약 테스트로 검증해 주세요.
- 외부 정책 명령 모드에서는 개발용 자동 배차가 함께 실행되지 않게 해 주세요.

### Module 2
- 공용 계약 7절에 따라 타깃 없는 `build_inference_features()`를 구현해 주세요.
- 예측 시각 직전 60분의 완료된 구간만 사용해 9개 구역 피처를 반환하고,
  미래 호출과 미완료 coverage를 거부해 주세요.
- 반환값을 Module 3 `predict()`가 변환 없이 소비하는 계약 테스트를 추가해 주세요.

### 통합 검증
- 같은 시나리오와 시드로 기준 배차와 예측 기반 재배치를 각각 실행합니다.
- 실제 재배치 이동, 미래 정보 비노출, 결정 재현성과 상태별 시간·거리 지표를 확인합니다.
- Module 4 단독 HTML은 명령 선택을, 통합 HTML/Panda3D는 실제 실행을 확인하는 용도로 구분합니다.
```
