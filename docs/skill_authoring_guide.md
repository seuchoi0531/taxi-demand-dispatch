# Codex Skill 작성 및 사용 가이드

이 문서는 이 저장소에서 사용하는 Codex Skill의 공통 작성 규칙을 정의한다. Skill을 만들거나 수정할 때 `AGENTS.md`와 함께 이 문서를 확인한다.

Skill은 반복 작업을 안정적으로 수행하기 위한 절차 묶음이다. 각 Skill은 독립된 디렉터리에 필수 파일인 `SKILL.md`를 가지며, 필요한 경우 스크립트·참고 문서·템플릿을 함께 포함한다.

## 1. Skill이 적합한 경우

다음 조건을 여러 개 만족하면 Skill을 고려한다.

- 같은 작업 절차가 반복된다.
- 작업 순서나 검증 방법을 일관되게 유지해야 한다.
- 특정 모듈에 관한 전문 규칙이 필요하다.
- 매번 찾아야 하는 참고 문서나 실행 스크립트가 있다.
- 입력과 결과물 형식을 표준화할 필요가 있다.

다음 구분을 따른다.

| 내용 | 기록 위치 |
|---|---|
| 모든 작업에 항상 적용되는 저장소 규칙 | `AGENTS.md` |
| 프로젝트 전체의 설계·계약·검증 기준 | `docs/` |
| 반복 실행하는 작업 절차 | `.agents/skills/<skill-name>/SKILL.md` |
| 결정론적으로 실행해야 하는 처리 | Skill의 `scripts/` 또는 프로젝트 코드 |
| 한 번만 수행하는 임시 작업 | 사용자 요청 또는 작업 계획 |

단순 참고 정보만 있는 문서를 Skill로 복제하지 않는다. Skill은 기존 공용 문서를 필요한 시점에 읽도록 안내하고, 동일한 규칙을 다시 장문으로 복사하지 않는다.

## 2. 저장 위치와 탐색 범위

Codex는 세션의 현재 작업 디렉터리에서 저장소 루트 방향으로 올라가며 각 디렉터리의 `.agents/skills`를 탐색한다. 현재 작업 디렉터리의 하위 폴더를 모두 재귀적으로 탐색하는 방식은 아니다.

공용 Skill은 저장소 루트에 둔다.

```text
repository/
└── .agents/
    └── skills/
        ├── common-verify-contracts/
        │   └── SKILL.md
        └── common-prepare-experiment-report/
            └── SKILL.md
```

모듈 전용 Skill은 담당 모듈 아래에 둘 수 있다.

```text
module1_simulation/
└── .agents/
    └── skills/
        ├── module1-run-simulation/
        │   └── SKILL.md
        └── module1-validate-state-transitions/
            └── SKILL.md
```

모듈별 권장 위치는 다음과 같다.

```text
module1_simulation/.agents/skills/
module2_preprocessing/.agents/skills/
module3_prediction/.agents/skills/
module4_dispatch/.agents/skills/
```

적용 범위에 유의한다.

- 저장소 루트의 `.agents/skills`는 저장소 내부 어디에서 시작해도 탐색할 수 있는 공용 Skill에 사용한다.
- 모듈 아래의 `.agents/skills`는 해당 모듈 또는 그 하위 폴더를 현재 작업 위치로 시작한 세션에 적합하다.
- 저장소 루트에서 시작한 세션은 하위 모듈의 Skill을 자동으로 탐색하지 않을 수 있다.
- 단순히 셸에서 `cd`한 것과 Codex 세션의 작업 기준 위치가 바뀌는 것은 같다고 가정하지 않는다.
- 루트에서 항상 사용해야 하는 모듈 관련 Skill은 루트 `.agents/skills`에 두되 모듈 접두사를 유지한다.

## 3. 이름 규칙

Skill 디렉터리 이름과 `SKILL.md`의 `name`은 같게 작성한다. 영문 소문자와 하이픈을 사용한다.

| 소유 범위 | 필수 접두사 | 예시 |
|---|---|---|
| Module 1 | `module1-` | `module1-run-simulation` |
| Module 2 | `module2-` | `module2-validate-input-data` |
| Module 3 | `module3-` | `module3-evaluate-forecast` |
| Module 4 | `module4-` | `module4-compare-dispatch` |
| 여러 모듈 공통 | `common-` | `common-verify-contracts` |

이름은 다음 원칙을 따른다.

- 담당 모듈 접두사를 반드시 붙인다.
- 접두사 뒤에는 수행 작업을 동사 중심으로 표현한다.
- 폴더 이름과 `name`을 일치시킨다.
- 같은 저장소 안에서 동일한 `name`을 재사용하지 않는다.
- `module3+4-`처럼 특수문자를 섞지 않고 실제 책임 모듈을 선택한다.
- 두 모듈이 공동 소유하고 어느 한쪽으로 나누기 어렵다면 `common-`을 사용한다.

좋은 예시는 다음과 같다.

```text
module1-run-headless-simulation
module2-build-demand-features
module3-evaluate-forecast
module4-compare-dispatch
common-verify-contracts
```

피해야 할 예시는 다음과 같다.

```text
run                         # 담당 모듈과 목적이 불명확함
validation                  # 어떤 검증인지 불명확함
module3+4-evaluation        # 소유권이 불명확하고 특수문자를 사용함
module2-helper              # 실행 조건과 결과를 예상하기 어려움
```

## 4. 기본 폴더 구조

Skill 하나는 다음 구조를 사용한다.

```text
<skill-name>/
├── SKILL.md                 # 필수: 메타데이터와 작업 절차
├── scripts/                 # 선택: 반복 실행하거나 결정론적이어야 하는 도구
├── references/              # 선택: Skill에서 필요할 때 읽는 상세 참고 자료
├── assets/                  # 선택: 보고서·설정·출력 템플릿
└── agents/
    └── openai.yaml          # 선택: 표시 정보, 암시적 호출 정책, 도구 의존성
```

사용하지 않는 빈 폴더를 미리 만들지 않는다. 자료가 작고 `SKILL.md`만으로 충분하면 `SKILL.md` 하나만 둔다.

각 폴더의 용도는 다음과 같다.

- `scripts/`: 사람이 설명문으로 반복하기보다 코드로 정확히 수행해야 하는 작업
- `references/`: 배경지식, 상세 규칙, 데이터 사전처럼 필요할 때만 읽을 내용
- `assets/`: 결과 보고서나 설정 파일처럼 복사하여 사용하는 재사용 자료
- `agents/openai.yaml`: Skill 표시 정보, 암시적 호출 허용 여부, 필요한 도구 선언

## 5. `SKILL.md` 작성 규칙

`SKILL.md`는 YAML front matter로 시작하고 `name`과 `description`을 반드시 포함한다.

```markdown
---
name: module1-run-simulation
description: 실행 조건과 적용 범위, 사용해야 할 상황과 사용하지 말아야 할 상황을 간결하게 설명합니다.
---
```

`description`은 Codex가 Skill을 선택하는 데 사용하므로 다음 내용을 앞부분에 명확히 적는다.

- 무엇을 하는 Skill인지
- 어떤 사용자 요청에서 사용해야 하는지
- 혼동하기 쉬운 작업 중 무엇에는 사용하지 않는지

본문은 작업에 필요한 범위에서 다음 순서로 작성한다.

1. 목표와 완료 조건
2. 먼저 읽을 공용 문서와 입력
3. 단계별 작업 절차
4. 실행해야 할 스크립트나 명령
5. 검증 방법
6. 결과 보고 형식
7. 중단하거나 사용자 확인을 받아야 하는 조건

작성 원칙은 다음과 같다.

- Skill 하나는 한 가지 중심 작업만 담당한다.
- 명령형 문장으로 구체적인 행동을 지시한다.
- 입력, 출력과 완료 조건을 분명히 한다.
- 저장소의 기존 스크립트와 템플릿을 우선 재사용한다.
- 존재하지 않는 명령이나 파일을 있는 것처럼 가정하지 않는다.
- 프로젝트 공용 규칙은 복사하지 않고 해당 `docs/` 문서를 참조한다.
- 외부 전송, 삭제, 배포처럼 추가 승인이 필요한 행동을 자동으로 허용하지 않는다.
- 결정론적 처리가 필요하면 긴 설명보다 테스트 가능한 스크립트를 사용한다.

## 6. 상황별 작성 방식

| 상황 | 작성 방식 |
|---|---|
| 정해진 명령을 순서대로 실행 | 명령, 선행 조건, 성공·실패 판정과 중단 조건을 명시 |
| 데이터 품질 검증 | 입력 경로, 스키마, 검사 항목, 원본 변경 금지와 보고 형식을 명시 |
| 코드 리뷰 | 검토 범위, 중요도 기준, 허위 양성 방지와 근거 제시 방식을 명시 |
| 문서 생성 | 읽을 원본, 사용할 템플릿, 출력 위치와 검수 기준을 명시 |
| 실험 실행 | 설정·시드·코드 버전 기록, 비교 조건과 재현성 확인을 명시 |
| 외부 서비스 사용 | 필요한 도구·권한, 승인 지점과 데이터 전송 범위를 명시 |

여러 목적이 섞이면 하나의 큰 Skill로 만들지 말고 독립적으로 실행 가능한 단위로 나눈다.

## 7. 전체 예시: Module 2 입력 데이터 검증

다음은 Module 2가 전처리를 시작하기 전에 입력 데이터의 품질을 반복 검증하는 상황의 예시다.

### 예시 폴더 구조

```text
module2_preprocessing/
└── .agents/
    └── skills/
        └── module2-validate-input-data/
            ├── SKILL.md
            ├── scripts/
            │   └── validate_input.py
            ├── references/
            │   └── validation_rules.md
            └── assets/
                └── validation_report_template.md
```

이 예시에서 스크립트, 참고 자료와 템플릿은 실제로 필요한 경우에만 만든다. 파일이 없다면 `SKILL.md`에서 참조하지 않는다.

### 예시 `SKILL.md`

```markdown
---
name: module2-validate-input-data
description: Module 2 입력 데이터의 스키마, 결측값, 값 범위, 중복과 시간 순서를 검증하고 품질 보고서를 작성합니다. 전처리 전 데이터 점검 요청에 사용하며, 예측 모델 평가나 시뮬레이션 런타임 상태 검증에는 사용하지 않습니다.
---

# Module 2 입력 데이터 검증

입력 데이터를 변경하지 않고 전처리 가능 여부와 문제점을 확인한다.

## 먼저 확인할 내용

1. 저장소 루트의 `AGENTS.md`를 읽는다.
2. `docs/contracts/common_contracts.md`를 읽는다.
3. `references/validation_rules.md`가 있으면 읽는다.
4. 사용자가 지정한 입력 파일과 설정을 확인한다.

입력 경로가 없거나 여러 후보 중 선택에 따라 결과가 달라지면 사용자에게 확인한다.

## 검증 절차

1. 입력 파일의 형식, 인코딩과 레코드 수를 확인한다.
2. 필수 필드와 자료형이 공용 계약에 맞는지 확인한다.
3. 결측값, 중복 ID와 허용 범위를 벗어난 값을 집계한다.
4. 호출 시각이 유효하고 시간 순서가 보존되는지 확인한다.
5. 출발지와 목적지가 유효한 구역을 참조하는지 확인한다.
6. 미래 데이터 유출 가능성이 있는 필드나 집계 방식을 확인한다.
7. `scripts/validate_input.py`가 있으면 문서화된 사용법으로 실행한다.

## 안전 규칙

- 원본 입력 파일을 수정, 이동 또는 삭제하지 않는다.
- 민감한 원본 레코드를 보고서에 그대로 출력하지 않는다.
- 외부 서비스에 데이터를 전송하지 않는다.
- 정의되지 않은 기본값으로 오류를 숨기지 않는다.

## 완료 조건

- 실행한 검사와 검사하지 못한 항목을 구분한다.
- 오류와 경고를 나누고 각 항목에 개수와 영향을 기록한다.
- 전처리를 진행할 수 있는지 결론을 제시한다.
- 수정이 필요하면 데이터가 아니라 생성·적재 코드를 수정할 위치를 제안한다.

## 결과 형식

`assets/validation_report_template.md`가 있으면 사용한다. 그렇지 않으면 다음 순서로 보고한다.

1. 입력 요약
2. 통과한 검사
3. 오류
4. 경고
5. 수행하지 못한 검사와 이유
6. 권장 다음 행동
```

이 예시는 `description`에서 호출 조건과 제외 범위를 구분하고, 본문에서 입력·절차·안전 규칙·완료 조건·출력 형식을 명시한다.

## 8. Skill 사용 방법

Codex CLI 또는 IDE 확장에서는 이름을 명시하여 호출할 수 있다.

```text
$module2-validate-input-data data/sample_calls.csv를 검사해줘.
```

`/skills`에서 사용 가능한 Skill을 확인할 수도 있다. 명시적으로 호출하지 않아도 사용자 요청이 `description`과 일치하면 Codex가 Skill을 선택할 수 있다.

암시적 호출이 적합하지 않은 Skill은 `agents/openai.yaml`에서 다음 정책을 사용할 수 있다.

```yaml
policy:
  allow_implicit_invocation: false
```

이 경우에도 `$<skill-name>`을 사용한 명시적 호출은 가능하다.

## 9. 생성과 변경 절차

1. 반복되는 작업인지 확인한다.
2. 공용 Skill인지 모듈 전용 Skill인지 결정한다.
3. 담당 모듈 접두사를 포함한 고유 이름을 정한다.
4. Skill 디렉터리를 만들고 `SKILL.md`를 작성한다.
5. 필요한 경우에만 `scripts/`, `references/`, `assets/`를 추가한다.
6. Skill이 사용되어야 하는 요청과 사용되면 안 되는 요청으로 `description`을 점검한다.
7. 실제 입력으로 절차와 결과 형식을 검증한다.
8. 적용되는 `AGENTS.md`와 공용 문서를 위반하지 않는지 확인한다.

새 Skill을 만들거나 기존 Skill의 범위를 크게 바꿀 때는 Codex의 `$skill-creator`를 사용할 수 있다.

## 10. 검토 체크리스트

- [ ] 디렉터리 이름과 `name`이 일치한다.
- [ ] `module1-`, `module2-`, `module3-`, `module4-` 또는 `common-` 접두사를 사용했다.
- [ ] `description`에 사용 상황과 제외 상황이 분명하다.
- [ ] 한 가지 중심 작업만 다룬다.
- [ ] 입력, 출력과 완료 조건이 명시되어 있다.
- [ ] 필요한 검증과 실패 처리가 포함되어 있다.
- [ ] 공용 문서를 중복 복사하지 않고 참조한다.
- [ ] 불필요한 빈 폴더나 사용하지 않는 자료를 포함하지 않는다.
- [ ] 위험하거나 외부 상태를 변경하는 행동의 승인 조건이 명확하다.
- [ ] 세션 작업 위치에서 해당 Skill이 탐색되는지 확인했다.
- [ ] 긍정·부정 예시 요청으로 호출 범위를 점검했다.

## 11. 공식 참고 자료

- [OpenAI Docs — Build skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI Docs — Customization overview](https://learn.chatgpt.com/docs/customization/overview)
