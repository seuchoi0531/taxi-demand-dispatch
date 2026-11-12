# 택시 수요 예측 및 동적 배차

가상 도시에서 수요 예측과 동적 배차를 비교하는 Python 프로젝트입니다.
현재 구현은 Module 1의 차량·승객 운행과 명령 실행 환경,
Module 2의 합성 호출 생성 및 coverage 기반 학습 데이터 전처리,
Module 3의 기준·최근 추세 수요 예측과 Module 4의 배차·재배치 계획입니다.

- 3×3 블록 도시와 도로
- 택시 3대의 대기·픽업·탑승 운행·하차
- 호출 시각에 따른 승객 생성과 위치·상태 추적
- 고정 tick simulation clock, 이벤트와 운행 시간 구성요소 기록
- Panda3D 화면의 일시정지·초기화·배속·카메라 조작

## 설치 및 실행

Python 3.13을 사용합니다. 자세한 환경 설정은
[개발 시작 가이드](docs/development_start_guide.md)를 참고하세요.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,simulation]"
python -m module1_simulation
```

Windows에서는 `.venv\Scripts\python.exe`로 같은 명령을 실행할 수 있습니다.
저장소 루트에서 실행하세요. 설정은 `configs/module1_demo.toml`에서 관리합니다.

```bash
python -m pytest
python -m module1_simulation --headless --steps 1200 --events
python -m module1_simulation --manual
python -m module3_prediction evaluate --input <validation.csv> --output <evaluation.json> --model recent-trend
python -m module3_prediction report --input <validation.csv> --output <evaluation.html> --model recent-trend
```

Space로 일시정지/재개, R로 초기화합니다. 1/2/3은 0.5/1/2배속,
방향키는 카메라 조절, 마우스 휠은 확대/축소, Esc는 종료입니다.
기본 실행은 **시작할 때 손님 한 명, 이후 10초마다 한 명씩** 계속 등장시킵니다.
출발·도착은 매번 16개 교차로에서 서로 다르게 무작위로 선택합니다.
호출 간격과 시드는 `configs/module1_calls.toml`에서 설정합니다.
`--call-interval 3`으로 간격을, `--seed 7`로 위치 패턴을 바꿀 수 있습니다.
호출은 묶음으로 반복하지 않으며 시계와 차량 위치는 계속 이어집니다.
호출 순서대로 현재 가장 가까운 빈 택시를 연결합니다. 빈 택시가 없으면 기다렸다가
다음 택시가 비는 시점에 다시 선택합니다. 사전 지정 택시·호출 연결은 사용하지 않습니다.
이 기준은 Module 1 운행 확인용이며 Module 4의 정식 배차 정책은 아닙니다.
수동 모드에서는 T로 택시, C로 호출을 선택하고 Enter로 배차합니다.
명령이 없으면 택시는 대기합니다.
헤드리스 실행에는 `simulation` 선택 의존성과 화면이 필요하지 않습니다.

## 구조와 현재 제한

`module1_simulation/`은 시뮬레이션, `module2_preprocessing/`은 데이터 처리,
`module3_prediction/`은 예측, `module4_dispatch/`는 배차 담당 영역입니다.
Module 2는 유한 호출 생성, 수집 누락을 구분하는 집계와 피처·타깃 생성,
시간순 분할 및 Module 3용 CSV 출력을 제공합니다.
[Module 2 사용법](docs/module2_preprocessing.md)을 참고하세요.
Module 3는 Module 2 CSV를 검증하여 읽고 60분 평균 baseline과 최근 추세 보정 예측,
MAE 비교 및 브라우저용 HTML 평가 보고서를 제공합니다.
[Module 3 사용법](docs/module3_prediction.md)을 참고하세요. Module 4는 현재 관측으로
FIFO·최근접 택시 배차를 계획하고 9개 구역 예측으로 잔여 택시의 재배치 명령을 만듭니다.
[Module 4 사용법](docs/module4_dispatch.md)을 참고하세요.
[Module 4 통합 인계 가이드](docs/module4_integration_handoff.md)에는 현재 검증 범위,
시각화 계획과 Module 1·2 담당자의 후속 구현·테스트 항목을 정리했습니다.
설정은 `configs/`, 테스트는 `tests/`, 공용 명세와 계약은 `docs/`에서 관리합니다.

학습 수요 모델·Module 4 정책의 최종 평가·비교 실험은 아직 구현하지 않았습니다.
Module 1은 `reposition` 명령을 아직 실행하지 않으며 구현 인계 계약만 정의되어 있습니다.
차량 충돌과 교통 신호는 모델링하지 않습니다. 제공된 Unity Asset 대신
기본 도형을 사용하며 Asset 적용은 후속 작업입니다. 승객 보행·취소도 미구현입니다.
사용법은 [Module 1 설명](docs/module1_simulation.md), 시간·구역·명령·상태의
임시 `0.1` 계약은 [공용 계약](docs/contracts/common_contracts.md)을 따릅니다.
평균 공차시간의 포함 항목·분모는 아직 미확정이므로 구성요소를 분리 기록합니다.
