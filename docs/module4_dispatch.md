# Module 4 배차와 재배치 계획

Module 4는 현재 관측만 사용하는 결정적 기준 배차와 Module 3 예측을 사용하는 재배치
계획을 제공한다. 정책은 순수 함수이며 시뮬레이션 상태를 직접 변경하지 않는다.

```python
from module4_dispatch import build_plan

plan = build_plan(
    simulation.observe(),
    block_size_m=simulation.config.block_size_m,
)
for command in plan["commands"]:
    simulation.apply_command(command)
```

예측 기반 계획은 같은 예측 시각과 모델을 사용하는 9개 구역 예측을 전달한다.

```python
plan = build_plan(
    simulation.observe(),
    block_size_m=simulation.config.block_size_m,
    forecasts=zone_forecasts,
)
```

## 정책

- 기준 배차는 오래 기다린 호출부터 현재 도로 거리가 가장 가까운 idle 택시를 선택한다.
- 호출·거리 동률은 ID 순으로 해결하므로 같은 입력은 같은 명령을 만든다.
- 예측을 전달하면 첫 5분 horizon의 구역별 수요 올림값을 필요 택시 수로 사용한다.
- 배차 후에도 남는 택시 중 현재 구역 필요량을 초과한 택시만 부족 구역으로 옮긴다.
- 정책은 관측에 없는 미래 호출이나 이후 horizon의 실제 수요를 참조하지 않는다.

반환 계획의 `schema_version`은 `module4-plan-0.1`이다. `commands`는 실행용이며
`decisions`는 같은 순서로 대기 시간, 픽업 거리, 출발·목적 구역, 예측 수요와
재배치 거리 등 선택 근거를 기록한다. 입력 객체는 변경하지 않는다. 잘못된 관측,
불완전한 9개 구역 예측 또는 관측과 시각이 다른 예측은 `ValueError`로 거부한다.

## 현재 통합 제한

`dispatch`와 `reposition` 명령은 모두 `Simulation.apply_command()`로 변환 없이 실행한다.
재배치 실행은 공용 계약 9절을 따르며 외부 정책 사용 시 개발용 자동 배차를 끈다.
Module 2 온라인 피처도 구현되어 Module 3에 전달할 수 있다.

공차 시간의 최종 산식과 기준·예측 정책의 최종 평가는 아직 확정되지 않았다.
전체 동일 시나리오 비교 실행기와 보고서는 별도 통합 작업이다.

현재 PR의 검증 범위, 계획 시각화 구현 항목, Module 1·2 담당자 요청과 통합 테스트 절차는
[Module 4 검증·시각화 및 인계 가이드](module4_integration_handoff.md)를 따른다.
