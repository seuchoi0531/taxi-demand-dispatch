# 택시 수요 예측 및 동적 배차

가상 도시에서 수요 예측과 동적 배차를 비교하는 Python 프로젝트입니다.
현재 구현은 Module 1의 첫 3D 이동 시제품입니다.

- 3×3 블록 도시와 도로
- 택시 3대의 순환 이동과 위치·상태 표시
- Passenger 데이터 객체와 고정 tick simulation clock
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
python -m module1_simulation --headless --steps 400
```

Space로 일시정지/재개, R로 초기화합니다. 1/2/3은 0.5/1/2배속,
방향키는 카메라 조절, 마우스 휠은 확대/축소, Esc는 종료입니다.
헤드리스 실행에는 `simulation` 선택 의존성과 화면이 필요하지 않습니다.

## 구조와 현재 제한

`module1_simulation/`은 시뮬레이션, `module2_preprocessing/`은 데이터 처리,
`module3_prediction/`은 예측, `module4_dispatch/`는 배차 담당 영역입니다.
Module 2~4는 아직 기본 패키지만 있습니다. 설정은 `configs/`, 테스트는
`tests/`, 공용 명세와 계약은 `docs/`에서 관리합니다.

승객 호출·픽업·하차·배차·예측·비교 실험은 아직 구현하지 않았습니다.
차량 충돌과 교통 신호는 모델링하지 않습니다. 제공된 Unity Asset 대신
기본 도형을 사용하며 Asset 적용은 후속 작업입니다. 이동 시제품의 임시
규칙과 Passenger 객체의 범위는 [Module 1 설명](docs/module1_simulation.md)을 따릅니다.
