# Module 3 수요 예측

Module 2의 과거 피처만 사용하는 재현 가능한 무학습 예측기 두 가지를 제공한다.

- `rolling-mean-12`: 직전 60분의 구역별 평균을 6개 구간에 동일하게 예측하는 baseline
- `recent-trend`: 직전 5분 수요와 `lag_1`·`lag_6`의 최근 추세를 사용해
  horizon별 변화를 완만하게 반영하는 개선 모델

기본 모델은 `recent-trend`다. 둘 다 초기 흐름과 계약을 검증하기 위한 모델이며
실제 데이터로 학습한 최종 모델이 아니다.

## 평가

Module 2가 만든 `validation.csv` 또는 `test.csv`를 명시하여 실행한다.
출력 파일이 이미 있으면 덮어쓰지 않고 실패한다.

```powershell
.\.venv\Scripts\python.exe -m module3_prediction evaluate --input data/generated/module2_training_demo/dataset/validation.csv --output data/generated/module3_validation.json --model recent-trend
```

결과는 전체 MAE와 horizon별 MAE, 행 수, 데이터 출처와 경고를 JSON으로 기록한다.
이 MAE는 첫 구현을 검증하기 위한 진단값이며 프로젝트 최종 평가 지표로 확정한 값이 아니다.
빈 CSV는 성공으로 처리하지 않는다. 열 순서, 중복·역순 행, 유효하지 않은 구역·시각·수치를
오류로 거부한다.

두 예측기는 파라미터를 학습하거나 검증·테스트 결과로 자동 조정하지 않는다.
따라서 학습 명령과 모델 파일은 제공하지 않는다. 향후 학습 모델을 추가할 때는 train으로 적합하고
validation으로 선택한 뒤, test는 최종 평가에 한 번만 사용하는 절차를 별도로 정의해야 한다.

## HTML 평가 보고서

같은 CSV에서 브라우저로 볼 수 있는 자체 포함 HTML 보고서를 생성할 수 있다.
외부 서버나 네트워크 연결은 필요하지 않는다. 출력 파일이 이미 존재하면 기존 파일을
보존하고 이름 뒤에 `_2`, `_3`처럼 다음 번호를 붙여 자동 생성한다.

```powershell
.\.venv\Scripts\python.exe -m module3_prediction report --input data/generated/module2_training_demo/dataset/validation.csv --output data/generated/module3_report.html --model recent-trend
```

보고서는 다음 내용을 제공한다.

- 개선 모델 MAE, 60분 평균 baseline MAE와 개선율
- 첫 번째 5분 구간의 실제·baseline·개선 모델 수요 시간 그래프
- 6개 horizon별 MAE 그래프와 표
- 전체 평균과 시점별 개별 값을 전환하는 3×3 구역별 실제 수요·예측 수요·절대 오차 히트맵
- 합성 데이터 사용과 그래프 축약 등 해석 주의사항

시간 그래프는 사용 가능한 구역 행만 시각별로 합산한다. 240개가 넘는 시점은
브라우저 가독성을 위해 균등 간격으로 축약하지만 MAE 계산에는 전체 행을 사용한다.
히트맵의 `시점별 값`에서는 예측 시각과 H1~H6를 선택해 각 구역의 원래 실제값,
선택 모델의 예측값과 절대 오차를 확인할 수 있다. 선택을 바꿀 때 같은 값의 색이 달라져
변화가 과장되지 않도록 개별 값 모드의 색상 척도는 전체 시점·horizon 기준으로 고정한다.

## 단일 예측

`target_1`~`target_6`이 없는 피처 JSON 한 행을 입력으로 사용할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m module3_prediction predict --input data/generated/module3_features.json --output data/generated/module3_forecast.json --model recent-trend
```

입력 피처의 의미는 [공용 계약 7절](contracts/common_contracts.md#7-module-2--module-3-데이터-처리-기준),
출력 구조는 [공용 계약 8절](contracts/common_contracts.md#8-module-3-수요-예측-출력--임시-01)과
`docs/contracts/module3_forecast.schema.json`을 따른다. 공개 API는 다음과 같다.

```python
from module3_prediction import evaluate, load_rows, predict, write_html_report, write_json
```

## 한계

- `rolling-mean-12`는 수요 추세, 요일, 날씨나 구역 간 관계를 학습하지 않는다.
- `recent-trend`는 최근 변화에 반응하지만 반복 패턴, 요일, 날씨와 구역 간 관계를 학습하지 않는다.
- 급격한 방향 전환에서는 과거 추세를 연장해 오차가 커질 수 있다.
- 합성 데이터의 MAE는 실제 환경의 예측 성능 근거가 아니다.
- Module 4 재배치와 동일 시나리오 비교 실험은 아직 연결되지 않았다.
