# 과제: todo CLI 에 마감일과 내보내기 기능 추가

현재 폴더의 `todo` 패키지는 `python -m todo` 로 실행하는 할 일 관리 CLI 입니다. 데이터는 환경변수 `TODO_FILE` 이 가리키는 JSON 파일(없으면 `~/.todo.json`)에 저장됩니다. 먼저 코드 구조를 파악한 뒤 아래 기능을 추가해 주세요.

1. `add` 에 `--due YYYY-MM-DD` 옵션 추가.
   - 형식이 틀리거나 존재하지 않는 날짜(예: 2026-02-30)면 아무것도 저장하지 않고, stderr 에 `invalid due date` 를 포함한 메시지를 출력하고 종료 코드 2 로 끝납니다.
2. `list` 에 `--overdue` 옵션 추가. 마감일이 오늘보다 이전이고 완료되지 않은 항목만 보여 줍니다. 오늘 날짜는 환경변수 `TODO_TODAY`(YYYY-MM-DD)가 있으면 그것을 씁니다(테스트용).
   - `list` 출력의 각 줄 형식은 기존과 같고, 마감일이 있으면 줄 끝에 ` (due YYYY-MM-DD)` 를 붙입니다.
3. 새 하위 명령 `export`.
   - `--format csv|md` (기본 csv), `--status open|done|all` (기본 all), `--out FILE` (없으면 stdout).
   - csv: 헤더 `id,title,done,due`, `done` 은 `true`/`false`, 마감일 없으면 빈 칸. 제목에 쉼표나 따옴표가 있어도 표준 CSV 규칙으로 올바르게 이스케이프.
   - md: 헤더 `| id | title | done | due |` 와 구분선 `|---|---|---|---|`, 이후 항목마다 한 줄. 제목 안의 `|` 는 `\|` 로 이스케이프. done 은 `x` 또는 빈 칸.
   - id 오름차순.
4. 기존 JSON 파일(마감일 필드가 없는 예전 형식)도 그대로 읽혀야 하고, 기존 명령의 동작과 출력은 바뀌면 안 됩니다.

테스트도 함께 추가해 주세요.
