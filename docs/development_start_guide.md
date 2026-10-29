# 개발 시작 가이드

이 문서는 저장소를 처음 받은 개발자의 환경 설정과 매 작업 시작 절차, Codex 대화 시작 형식을 정의한다. `README.md` 대신 이 문서를 초기 개발 온보딩의 공용 원본으로 사용한다.

## 1. 기본 환경

프로젝트의 기본 개발 환경은 다음과 같다.

```text
Python >=3.13,<3.14
venv
pip
pyproject.toml
pytest
```

- Python 3.13의 호환되는 최신 패치 버전을 사용한다.
- 가상환경 디렉터리 이름은 `.venv`로 통일한다.
- 일반 의존성과 개발 의존성은 `pyproject.toml`에서 관리한다.
- 개발 환경은 `.[dev]` 선택 의존성을 포함하여 설치한다.
- 별도의 `requirements.txt`를 중복 관리하지 않는다.
- 의존성 잠금 방식은 `project_decisions.md`에서 확정되기 전까지 임의로 추가하지 않는다.

## 2. 저장소를 처음 받을 때

새 개발자는 `pull`이 아니라 저장소를 `clone`하여 시작한다.

### Windows PowerShell

```powershell
git clone https://github.com/seuchoi0531/taxi-demand-dispatch.git
Set-Location taxi-demand-dispatch
git switch develop

py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

PowerShell 실행 정책으로 활성화가 차단되면 정책을 영구 변경하지 말고 다음처럼 가상환경의 Python을 직접 사용할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

### macOS 또는 Linux

```bash
git clone https://github.com/seuchoi0531/taxi-demand-dispatch.git
cd taxi-demand-dispatch
git switch develop

python3.13 --version
python3.13 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

설치가 끝나면 다음 순서로 문서를 확인한다.

1. 루트 `AGENTS.md`
2. 담당 모듈 폴더의 `AGENTS.md`가 있으면 해당 문서
3. `common_project_spec.md`
4. `contracts/common_contracts.md`
5. `testing_and_evaluation.md`
6. `git_workflow.md`
7. 작업 내용에 따라 일정, 결정 기록 또는 Skill 가이드

## 3. 기존 저장소에서 매 작업을 시작할 때

작업을 시작하기 전에 로컬 변경사항이 있는지 먼저 확인한다. 변경사항이 있으면 무조건 되돌리거나 덮어쓰지 말고 소유자와 목적을 확인한다.

### Windows PowerShell

```powershell
Set-Location <repository-path>
git status --short --branch

git switch develop
git pull --ff-only

.\.venv\Scripts\Activate.ps1
python --version
python -m pytest

git switch -c feat/module1-<summary>
```

### macOS 또는 Linux

```bash
cd <repository-path>
git status --short --branch

git switch develop
git pull --ff-only

source .venv/bin/activate
python --version
python -m pytest

git switch -c feat/module1-<summary>
```

작업 유형과 모듈에 맞춰 브랜치의 `type`, `scope`와 `summary`를 바꾼다. 정확한 규칙은 `git_workflow.md`를 따른다.

로컬 변경사항이 있거나 아직 병합하지 않은 브랜치에서 작업 중이면 `develop`으로 전환하거나 `pull`하기 전에 현재 상태를 보존해야 한다. 명령을 기계적으로 그대로 실행하지 않는다.

## 4. 의존성이 변경되었을 때

`pyproject.toml`이 변경되었거나 새 의존성이 추가되면 가상환경을 활성화한 뒤 다시 설치한다.

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Python 요구 버전이 바뀌었으면 기존 `.venv`를 그대로 사용하지 않는다. 변경 이유와 전환 방법을 먼저 확인한 뒤 새 가상환경을 만든다.

## 5. Codex에서 개발 작업을 시작하는 채팅

대괄호 부분만 바꿔서 사용한다.

```text
[작업 모듈]에서 [작업 내용]을 진행해줘.
먼저 적용되는 AGENTS.md와 관련 문서, Git 변경사항을 확인하고 구현과 테스트까지 진행해줘.
기존 변경을 되돌리지 말고, 요청 전에는 커밋·푸시·Pull Request를 만들지 마.
```
