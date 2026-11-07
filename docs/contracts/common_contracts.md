# 모듈 공용 계약

이 문서는 모든 모듈이 공유하는 데이터와 인터페이스 계약의 단일 문서 원본이다. 코드에서 사용하는 구체적인 스키마 형식과 공개 진입점은 `../project_decisions.md`에 확정된 결정을 따른다.

## 1. 계약 대상

다음 데이터는 모듈 간 핵심 계약이다.

- 시뮬레이션 시각
- 구역 ID와 좌표
- 택시 ID, 위치와 상태
- 승객 호출 ID, 발생 시각, 출발지와 목적지
- 수요 예측 대상 시각과 구역
- 구역별 예측 수요
- 배차 명령
- 재배치 명령
- 이동 결과
- 실험 이벤트와 평가 지표

## 2. 필수 정의 항목

각 계약은 가능한 범위에서 다음 내용을 정의해야 한다.

- 필드 이름과 의미
- 자료형
- 필수 여부
- 허용 범위와 열거값
- 시간·거리의 단위
- 좌표 기준
- 상태 전이 규칙
- 잘못된 입력의 처리 방식
- 버전 또는 호환성 정책

문서 설명과 코드 스키마가 함께 존재하면 어느 것이 실행 가능한 기준인지 명시하고 서로 다르게 유지하지 않는다.

## 3. Module 1과 Module 2의 호출 경계

- Module 2는 재현 가능한 호출 시나리오와 입력 데이터를 생성한다.
- 호출 시나리오는 호출 ID, 발생 시각, 출발지, 목적지와 필요한 시나리오 메타데이터를 제공한다.
- Module 1은 호출 시나리오를 읽고 시뮬레이션 시각에 맞춰 런타임 호출 객체와 이벤트를 생성한다.
- Module 1은 데이터 생성 규칙을 복제하지 않고, Module 2는 런타임 상태 전이를 담당하지 않는다.

## 4. 계약 구현 원칙

- 공용 계약을 한 모듈 내부에만 정의하고 다른 모듈이 내부 파일을 import하게 만들지 않는다.
- 생산자와 소비자는 동일한 필드 의미와 단위를 사용한다.
- 필수 필드가 없거나 값이 범위를 벗어나면 조용히 보정하지 않는다.
- 알 수 없는 미래 정보가 계약을 통해 예측 또는 배차 모듈에 전달되지 않게 한다.
- 동일한 개념에 여러 이름이나 서로 다른 단위를 사용하지 않는다.
- 계약 버전 변경은 재현 가능성과 기존 데이터 호환성에 미치는 영향을 기록한다.

## 5. 계약 변경 절차

1. 변경 이유와 영향을 받는 생산자·소비자를 확인한다.
2. 이 문서 또는 확정된 코드 스키마를 먼저 갱신한다.
3. 생산자와 소비자 코드를 함께 수정한다.
4. `tests/contracts/`의 계약 테스트를 추가하거나 갱신한다.
5. 필요한 통합 테스트를 실행한다.
6. 하위 호환이 깨지면 명시하고 `../project_decisions.md`에 결정 근거를 기록한다.

한 모듈의 단위 테스트만 통과했다는 이유로 공용 계약 변경을 완료된 것으로 판단하지 않는다.

## 6. Module 1 운행 경계 — 임시 `0.1`

사용자가 승인한 차량·승객 운행 구현의 임시 계약이다. Module 2~4의
구현과 전체 팀 합의는 아직 없으며, 해당 모듈 통합 전에 재검토한다.
문서가 필드 의미의 원본이다. 공용 교환 형식은 Python 기본 자료형
(`dict`, `list`, 문자열, 수, `None`)이며 JSON으로 표현할 수 있다.
별도 공용 패키지·스키마 라이브러리는 도입하지 않는다.
Module 1 내부 dataclass는 런타임 구현이며 다른 모듈이 내부 파일을 import하지 않는다.
공개 진입점은 `from module1_simulation import Simulation, load_config, load_calls`이다.

### 좌표·구역·시간

- 도시: 3×3 블록, 교차로 `(x, y)`는 각 축 0~3의 정수.
- 원점은 좌하단, 동쪽 +x, 북쪽 +y. 화면 z는 높이이며 이동 계산에 사용하지 않는다.
- 교차로 간격은 설정 `block_size_m`(미터), 속도는 `speed_mps`(m/s).
- 인접 교차로 사이 양방향 도로를 사용한다. 최단 경로가 여러 개면 x축 이동 후 y축 이동한다.
- 구역 ID는 `zone-x-y`(x,y 각각 0~2)이다. 지점의 소속 구역은 동·북쪽 블록을 택하되
  도시 동·북쪽 외곽선에서는 마지막 블록을 사용한다. 경계 공유를 해결하는
  임시 규칙이며 invalid 좌표를 도시 안으로 보정하는 규칙이 아니다.
- 시뮬레이션 초는 0에서 시작한다. `tick_seconds`는 유한한 양수.
  호출·시연 명령 시각은 tick의 정수 배수여야 하며 다른 시각은 오류다
  (부동소수점 표현 오차만 허용). 이동 도착 시각은 tick 사이에도 정확히 기록한다.
- 같은 구간에서 모든 차량을 독립적으로 이동시키고 도착·픽업·하차를 처리한다.
  구간 끝 시각에 호출을 발생시킨 뒤 외부 명령을 받는다.
  최초 시각 0에도 호출이 먼저 발생한다. 같은 시각 호출은 `call_id` 순서,
  차량 이벤트는 `taxi_id` 순서로 결정한다. 외부 명령은 호출한 순서로 처리한다.
- 픽업·하차 시간은 0초이며, 같은 출발·도착 지점도 허용한다.
  한 tick의 남은 시간은 다음 운행 단계 또는 대기 시간에 계속 반영한다.

### 호출 입력(Module 2 → Module 1)

`load_calls(path)`는 `{"schema_version":"0.1", "calls":[...]}` JSON을 읽는다.
각 호출의 아래 필드는 모두 필수이다. 알 수 없는 필드는 오류로 거부한다.

| 필드 | 형식 | 의미 |
|---|---|---|
| `call_id` | 비어 있지 않은 고유 문자열 | 호출 ID, 이 MVP에서는 승객 1명과 1:1 |
| `requested_at_seconds` | 유한한 0 이상 수 | 호출 발생 시뮬레이션 시각 |
| `origin` | `[x,y]` | 출발 교차로 |
| `destination` | `[x,y]` | 도착 교차로 |

`Simulation(config, calls)`에 전체 호출을 적재하되 `observe()`와 이벤트에는
**발생한 호출만** 노출한다. 미래 스케줄은 정책 입력에 전달하지 않는다.
시뮬레이터는 호출 데이터 생성 알고리즘을 구현하지 않는다.
`has_initial_calls`는 초기 호출 입력의 존재 여부만 반환하는 읽기 전용 속성이다.
호출 내용·발생 시각은 노출하지 않으며 개발 실행기의 입력 방식 충돌 확인에 사용한다.

`add_calls(calls)`로 같은 형식의 추가 입력을 받을 수 있다. 과거 시각이나
기존 ID와 중복되는 호출은 전체 묶음을 오류로 거부한다. 현재 시각의 호출은
즉시 발생하고 미래 시각의 호출은 시각 도달 전까지 관측에 노출하지 않는다.
호출을 추가해도 시계·차량·기존 승객·기록은 초기화하지 않는다.
개발 화면은 설정된 간격마다 현재 시각의 호출 한 건을 추가한다.
출발·도착은 그 순간 추출하며, 이 개발용 입력은 Module 2의 시나리오 생성기를 대체하지 않는다.

### 명령(Module 4 → Module 1)

- `dispatch(taxi_id, call_id)`: `idle` 택시와 `waiting` 호출에 대해서만 허용.
- `apply_command(command)`: `{"type":"dispatch", "taxi_id":..., "call_id":...}`
  를 실행한다. 어떤 택시를 선택할지는 호출자가 결정하며 Module 1은 매칭 정책을 구현하지 않는다.
  개발 화면의 `DemoRunner`는 사용자가 선택한 임시 FIFO·가까운 빈 택시 규칙으로
  이 명령을 호출한다. 이 규칙은 `Simulation` 자체나 Module 4의 공용 정책 계약에 포함하지 않는다.
- 잘못된 ID·지점·상태·필드·명령은 `ValueError`로 거부하고
  `command_rejected` 이벤트에 대상과 이유를 기록한다. 운행 상태는 변경하지 않는다.
  시연 스크립트에서도 오류를 숨기지 않는다.
- 이번 Module 1 범위에는 재배치를 포함하지 않는다. 재배치 명령도 지원하지 않는다.
  취소·실패 호출 생명주기는 아직 미구현이다.
  호출 미배정은 정상적인 `waiting`이며 오류를 의미하지 않는다.

### 상태 전이

| 대상/현재 상태 | 이벤트 | 다음 상태 | 선행 조건 | 실패 처리 |
|---|---|---|---|---|
| 호출 없음 | `call_created` | `waiting` | 발생 시각 도달, 고유 ID | 잘못된 시나리오는 실행 전 오류 |
| 택시 `idle`, 승객 `waiting` | `assigned` | `to_pickup`, `assigned` | 유효 배차 명령 | 명령 거부, 기존 상태 유지 |
| 택시 `to_pickup`, 승객 `assigned` | `pickup_completed`, `trip_started` | `occupied`, `onboard` | 출발지 도착 | 내부 불일치 시 실행 오류 |
| 택시 `occupied`, 승객 `onboard` | `dropoff_completed` | `idle`, `completed` | 목적지 도착 | 내부 불일치 시 실행 오류 |

픽업 완료와 이동 시작은 같은 시각의 별도 이벤트이다. 하차 완료 시 택시와
호출 연결을 해제하되 승객 기록에는 배정 택시와 배정·탑승·하차 시각을 보존한다.

### 관측·이벤트·측정(Module 1 → 소비자)

- `observe()`: `schema_version`, `tick`, `time_seconds`, `taxis`, `passengers`,
  `metrics`를 포함하는 새로운 dict. `snapshot()`과 `passenger_snapshots()`는
  Module 1 화면용 불변 snapshot이며 다른 모듈은 `observe()`를 사용한다.
- `taxis`: `taxi_id`, `x_m`, `y_m`, `heading_degrees`, `distance_m`, `state`,
  `call_id`(연결 없으면 null), `zone_id` 필드를 갖는다.
- `passengers`: 발생한 호출만 포함. 입력의 네 필드와 `state`, `taxi_id`,
  `assigned_at_seconds`, `picked_up_at_seconds`, `completed_at_seconds`,
  `x_m`, `y_m`, `wait_seconds`를 포함한다. 미발생 타임스탬프는 null.
  대기·배정 중 위치는 출발지, 탑승 중 위치는 택시 위치, 완료 시 목적지이다.
- `events()`: 발생한 이벤트를 시간순으로 반환한다. 각 항목은
  `time_seconds`, `event`, `taxi_id`, `call_id`, `details`를 포함한다.
  동시각 순서는 기록 순서로 안정적이며 반환값 수정은 내부에 영향을 주지 않는다.
- `metrics()`: `by_taxi`에 `idle_seconds`, `pickup_seconds`,
  `occupied_seconds`, `distance_m`, `empty_distance_m`, `completed_calls`를 기록한다.
  세 시간의 합은 각 택시의 관측 기간과 같다.
- 전체 지표: `fleet_available_seconds`, `completed_calls`, `pending_calls`,
  `picked_up_calls`, `mean_wait_seconds`(탑승 완료된 승객만의 평균, 표본 없으면 null),
  `occupancy_percent`(공통 명세 산식, 기간 0이면 null), `rejected_commands`.
  `pending_calls`에는 발생 후 아직 하차하지 않은 모든 호출이 포함된다.
- 평균 공차시간의 포함 항목·분모는 아직 미확정이다. 이번에는 각 구성요소만
  제공하고 임의의 평균 공차시간이나 개선 효과를 계산하지 않는다.
- 초기화는 모든 상태·측정·이벤트를 지우고 같은 시나리오의 시각 0으로 돌아간다.

호환성: 이전 `route` 순환 이동 설정과 `passenger_id`만 가진 객체는 폐기한다.
택시 설정은 `initial_node`, 호출 식별자는 `call_id`로 전환한다.
이 계약은 첫 소비자 통합 전 변경 가능하며, 변경 시 이 문서·결정 기록·계약 테스트를 함께 수정한다.

## 7. Module 2 → Module 3 데이터 처리 기준

2026-11-02 사용자 지정 및 후속 승인 기준이다.
이 절의 기준 확정은 Module 3 소비자 구현 완료를 의미하지 않는다.

- 수요는 출발 구역별 호출 **발생 건수**다. 픽업·하차 건수와 구분한다.
- 공간은 6절의 좌표와 `zone-x-y`를 사용한다. 시간 집계는 5분이다.
- 호출이 없는 완전 수집 구간은 0이다. 수집 누락을 0으로 간주하지 않는다.
- 과거 12개 구간(60분)으로 `lag_1`, `lag_2`, `lag_3`, `lag_6`, `lag_12`,
  `rolling_mean_3`, `rolling_mean_6`, `rolling_mean_12`를 만든다.
- 모든 피처는 예측 시점에 이용 가능한 과거 데이터만 사용한다.
- 향후 30분을 5분 단위 6개 구간으로 나누어 `target_1`~`target_6`을 만든다.
  타깃은 각 구간의 호출 수이며 누적 수요가 아니다.
- Train/Validation/Test는 시간순 70%/15%/15%다.
  미래 타깃이 분할 경계를 넘는 샘플은 제외한다.
- Module 3 학습 입력은 CSV로 생성하고, 향후 통신용 JSON 스키마도 문서화한다.
- 일정 간격·고정 호출량 샘플의 학습 한계를 보고한다.
  실제 데이터가 없으면 시간대·구역별 변동을 갖는 합성 데이터 방안을 제안한다.

### 실행 가능한 교환 구조

- 기존 호출 JSON `0.1`은 변경하지 않는다. 호출은 출발 교차로의 구역에 집계한다.
- `coverage.csv`의 필수 열은 `interval_start_seconds,zone_id,is_complete`다.
  시작 시각은 0 이상인 300초 배수 정수, 구역은 기존 9개 구역,
  완료 여부는 소문자 `true` 또는 `false`다. 중복 키와 알 수 없는 열·구역은 오류다.
  명시한 관측 범위 `[start_seconds,end_seconds)` 밖 입력도 오류다.
  미기록 또는 false인 구간의 수요는 null이며 부분 수집 호출 수도 정답으로 사용하지 않는다.
- coverage 템플릿 생성은 전 구간 false로 시작한다. true 지정은 입력 제공자가
  수집 로그 또는 합성 생성 완료 기록으로 확인해야 하며, 전처리 실행 시 `coverage_evidence`를
  필수 기록한다. 근거 문자열의 진위를 자동 검증하는 기능은 없다.
- 데이터 출처는 실행 시 `source_kind`=`real` 또는 `synthetic`으로 명시한다.
  파일명으로 추측하지 않는다. 전체 호출 JSON은 오프라인 학습 전용이며 온라인 예측 입력으로 보내지 않는다.
- 예측 시각 t는 300초 경계다. lag_k는 `[t-k*300,t-(k-1)*300)`의 수요,
  rolling_mean_k는 직전 k구간의 평균, target_k는 `[t+(k-1)*300,t+k*300)` 수요다.
  t 시각 호출은 target_1에만 포함된다. 실제 데이터는 해당 과거 구간이 t까지 수집 완료됐음을
  제공자가 확인해야 한다. 수집 지연을 자동 보정하지 않는다.
- 직전 12구간 또는 미래 6구간에 누락이 하나라도 있으면 해당 구역의 학습 행을 제외한다.
  초기 과거 부족과 말미 미래 부족도 제외한다. 임의 보간·정규화·통계 적합은 하지 않는다.
- 시간 분할 경계는 관측 구간 수 N에 대해 start+floor(0.70N)*300,
  start+floor(0.85N)*300이다. 모든 구역에 동일 적용한다.
  예측 시각으로 분할을 선택하며 t+1800이 그 분할 종료보다 크면 행을 제외한다.
  경계와 정확히 같은 타깃 종료는 허용한다. 검증·테스트 피처는 앞 구간의 과거를 사용할 수 있다.
  제외 후 실제 행 비율은 70:15:15와 다를 수 있다.
- `train.csv`, `validation.csv`, `test.csv` 열 순서는
  `prediction_time_seconds,zone_id,source_kind,lag_1,lag_2,lag_3,lag_6,lag_12,rolling_mean_3,rolling_mean_6,rolling_mean_12,target_1,target_2,target_3,target_4,target_5,target_6`이다.
  시각·lag·타깃은 0 이상 정수, 평균은 유한한 0 이상 수다. 학습 CSV에는 결측 행을 넣지 않는다.
  시각, 구역 순으로 정렬한다. `source_kind`는 출처 표시이며 학습 피처가 아니다.
- `aggregates.csv`는 `interval_start_seconds,zone_id,is_complete,demand`를 담는다.
  누락 demand는 빈 칸, 실제 0건은 0이다. `report.json`은 출처·근거·설정·분할 경계·제외 건수·품질 경고를 기록한다.
- 향후 JSON 전송용 학습 행의 구조는 `docs/contracts/module2_training_row.schema.json`이다.
  CSV와 동일한 필드를 JSON 수치형으로 표현한다. 온라인 추론 계약은 아래 인계 기준을 따른다.
- 공개 API: `from module2_preprocessing import aggregate_calls, build_dataset, write_dataset, write_coverage_template`.
  Module 3 기준 예측기는 같은 열 순서와 값 제약을 검증하여 CSV를 소비한다.

### Module 2 온라인 추론 피처 인계 요청

PR #4의 인계 요청에 따라 구현한 온라인 추론 API다.

```python
rows = build_inference_features(
    observed_calls,
    coverage,
    prediction_time_seconds=3600,
    source_kind="synthetic",
)
```

- 공개 진입점은 `from module2_preprocessing import build_inference_features`로 한다.
- `observed_calls`는 6절 호출 입력의 네 필드만 가진 호출 배열이다. 예측 시각보다 미래인
  호출을 포함하면 오류다. 예측 시각과 같은 호출은 이미 관측됐더라도 피처 구간에 넣지 않는다.
- `prediction_time_seconds`는 3600 이상인 300초 경계다. 직전 12개 구간
  `[t-3600,t)`만 사용한다.
- `coverage`는 기존 coverage 행 형식으로 직전 12개 구간과 9개 구역의 완료 여부를 제공한다.
  108개 셀 중 하나라도 없거나 `false`이면 0으로 보정하지 않고 오류다.
- `source_kind`는 `real` 또는 `synthetic`이며 피처로 사용하지 않고 출처만 기록한다.
- 반환값은 시각과 구역 순으로 정렬한 정확히 9개 행이다. 각 행은 7절
  `train.csv`에서 `target_1`~`target_6`을 제거한 필드만 가진다.
- 파일을 쓰거나 미래 타깃을 계산하지 않는다. 같은 입력은 같은 행을 반환한다.
- 호출이 없는 완료 구간은 0이고 미완료 구간은 오류다. `lag_1`은 `[t-300,t)`,
  `lag_12`는 `[t-3600,t-3300)`이며 rolling mean 의미는 7절과 같다.

이 API의 9개 행을 Module 3 `predict()`에 하나씩 전달하면 같은 예측 시각의 9개 구역
예측을 만들 수 있다. 오프라인 학습 CSV의 타깃 열을 제거해 온라인 입력처럼 재사용하거나
전체 미래 호출 파일을 런타임 정책에 전달하면 안 된다.

추가 검증: 과거 60분보다 오래된 호출과 t 시각 호출도 형식·ID·좌표·시각을 검증한다.
오래된 호출은 집계에서 제외하고, coverage는 직전 108개 셀만 받으며 범위 밖 행은 오류다.
tick 인자가 없는 온라인 API는 유한한 0 이상 호출 시각을 받고 별도 tick 정렬을 강제하지 않는다.

### 합성 시뮬레이션 관측 연결

- 공개 `build_simulation_features(observation, *, complete_since_seconds, coverage_evidence)`는
  Module 1 `observe()`의 누적 호출 이력을 온라인 피처로 연결한다. 합성 시뮬레이션 전용이다.
- 호출이 없다는 이유로 완료를 추정하지 않는다. 호출 누락 없이 관측됐음을 확인한 시작 시각
  `complete_since_seconds`(0 이상 300초 배수 정수)와 비어 있지 않은 근거를 호출자가 명시한다.
  관측은 완료 호출을 포함한 전체 발생 이력을 유지해야 하며, 미래 예약 호출 파일은 받지 않는다.
- 관측 시각 직전 60분이 확인된 기간 안에 있어야 한다. 이 조건이 충족되면 해당 기간의
  108개 coverage 셀을 생성하고 네 호출 필드를 추출하여 `build_inference_features()`로 검증한다.
- 반환값은 동일한 9개 피처 행이며 출처는 `synthetic`이다. 실제 외부 데이터는 이 연결 API를
  사용하지 않고 별도 수집 완료 coverage와 함께 기존 온라인 API에 전달한다.
- 시뮬레이션 진행·배차·예측 정책은 실행하지 않고 입력을 변경하지 않는다.

## 8. Module 3 수요 예측 출력 — 임시 `0.1`

Module 3의 첫 기준 예측기와 Module 4의 후속 소비자가 공유할 임시 계약이다.
예측 방식 자체를 프로젝트 최종 모델로 확정하지 않으며, 출력 경계만 정의한다.

- 입력은 7절 학습 행에서 `target_1`~`target_6`을 제거한 피처 행이다.
  전체 호출 JSON이나 예측 시각 이후 실제 수요를 입력으로 전달하지 않는다.
- `prediction_time_seconds`는 300초 경계이며 `zone_id`는 기존 9개 구역이다.
- 출력 `schema_version`은 `module3-forecast-0.1`이다.
- 출력 `model`은 `rolling-mean-12` 또는 `recent-trend`이며 예측을 만든 방식을 명시한다.
- `predictions`는 horizon 1부터 6까지 정확히 6개이며 순서대로 정렬한다.
  horizon k의 `interval_start_seconds`는 `prediction_time_seconds + (k-1)*300`이다.
- `predicted_demand`는 해당 5분 구간에 그 구역에서 발생할 것으로 예상한 호출 수다.
  유한한 0 이상 수이며 누적 수요가 아니다.
- 실행 가능한 JSON 구조는 `docs/contracts/module3_forecast.schema.json`을 따른다.
- 첫 기준 예측기는 직전 60분 평균인 `rolling_mean_12`를 6개 horizon에 동일하게 사용한다.
  이는 Module 3 첫 구현에 한정한 임시 기준이며 학습된 모델이나 최종 비교 기준이 아니다.
- 개선 예측기 `recent-trend`는 직전 구간 `lag_1`을 수준으로 사용하고,
  `(lag_1-lag_6)/5`를 구간당 최근 추세로 계산한다. horizon h의 예측은
  `max(0, lag_1 + 0.5 × 최근 추세 × h)`다. 미래 실제값은 사용하지 않는다.
- Module 3 CLI의 기본 모델은 `recent-trend`다. `--model rolling-mean-12`로 기존
  baseline을 실행할 수 있으며 비교 보고서에서는 두 결과를 함께 기록한다.
- 공개 API는 `from module3_prediction import evaluate, load_rows, predict, write_json, write_html_report`이다.
