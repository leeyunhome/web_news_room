아래 내용은 요청하신 **'Google Gemini 기반 AI IT 뉴스룸 구축'**을 위한 전체 개발 명세서입니다.

이 파일을 `spec.md` 또는 `README.md`로 저장하여 개발 가이드라인으로 활용하거나, AI 코딩 도구(Cursor, Windsurf 등)에 입력하여 코드를 생성하는 프롬프트로 사용할 수 있습니다.

---

# 📝 AI IT Newsroom 개발 명세서

## 1. 프로젝트 개요
*   **프로젝트명**: Personal AI IT Newsroom (나만의 AI 뉴스룸)
*   **목표**: 국내외 IT 뉴스 RSS를 수집하여 Google Gemini(Antigravity/v2)가 자동으로 분석·요약하고, 이를 날짜별로 아카이빙하여 보여주는 웹 애플리케이션 구축.
*   **핵심 컨셉**: "Serverless & DB-less". 별도의 데이터베이스 서버 없이 GitHub Repository를 데이터 저장소(Storage)로 활용하여 영구성을 보장함.

## 2. 기술 스택 (Tech Stack)
*   **Frontend & Framework**: Python Streamlit
*   **AI Engine**: Google Gemini API (라이브러리: `google-genai` 최신 SDK)
    *   모델: `gemini-2.0-flash-exp` (권장) 또는 `gemini-1.5-flash`
*   **Data Collection**: `feedparser` (RSS 파싱), `beautifulsoup4` (HTML 정제)
*   **Storage (DB 대용)**: GitHub Repository (라이브러리: `PyGithub`)
    *   JSON 파일 형태로 데이터 Read/Write/Commit 수행
*   **Deployment**: Streamlit Cloud

## 3. 시스템 아키텍처

### 3.1. 데이터 흐름
1.  **Trigger**: 관리자 대시보드에서 '뉴스 분석' 버튼 클릭
2.  **Collect**: 등록된 RSS URL에서 최신 기사 수집
3.  **Process**: 텍스트 전처리(HTML 태그 제거) 후 Gemini API로 전송 (Prompting)
4.  **Store**: 분석 결과를 `news_archive.json`으로 변환하여 GitHub Repo에 Commit
5.  **Serve**: 일반 사용자는 GitHub에서 로드된 JSON 데이터를 기반으로 화면 조회

### 3.2. 디렉토리 구조
```text
/
├── app.py                # 메인 애플리케이션 (UI 및 로직 통합)
├── requirements.txt      # 의존성 패키지 목록
└── data/                 # 데이터 저장소 (GitHub Repo에 자동 생성/관리됨)
    ├── feeds.json        # RSS URL 목록
    ├── news_archive.json # 날짜별 분석된 뉴스 데이터
    └── stats.json        # 방문자 통계 로그
```

## 4. 기능 요구사항 (Functional Requirements)

### 4.1. 메인 화면 (Public View)
*   **날짜 선택기**: 드롭다운 박스를 통해 과거 날짜의 뉴스 브리핑을 선택 가능해야 함.
*   **AI 브리핑 영역**:
    *   **헤드라인**: 주요 이슈 3~5개를 3줄 요약 형태로 표시.
    *   **단신 모음**: 기타 뉴스들을 한 줄 요약으로 나열.
    *   마크다운(Markdown) 렌더링 지원.
*   **원본 보기 (Expander)**: AI 요약의 근거가 된 원본 기사 리스트(제목+링크)를 토글 형태로 제공.
*   **접속 통계 로깅**: 페이지 로드 시 자동으로 방문자 카운트 증가 및 GitHub 저장.

### 4.2. 관리자 대시보드 (Admin View)
*   **진입 보안**: `st.sidebar` 또는 별도 탭에서 비밀번호 입력을 통해서만 접근 가능.
*   **RSS 피드 관리**:
    *   현재 등록된 RSS URL 리스트 조회.
    *   새로운 RSS URL 추가 및 기존 URL 삭제 기능.
*   **뉴스 생성 및 관리**:
    *   **분석 실행 버튼**: 클릭 시 실시간으로 RSS를 긁어오고 Gemini 분석 수행 후 저장.
    *   **삭제 기능**: 잘못 생성된 특정 날짜의 데이터를 삭제.
*   **통계 대시보드**:
    *   총 누적 방문자 수 표시.
    *   최근 접속 로그(시간) 테이블 뷰 제공.

## 5. 데이터 구조 (JSON Schema)

### 5.1. `news_archive.json`
```json
{
  "2024-05-20": {
    "content": "## 🚀 오늘의 주요 IT 뉴스...\n1. 구글 Gemini 2.0 공개...",
    "raw_data": [
      "- 제목: 기사제목1\n- 링크: http://...\n- 요약: ...",
      "..."
    ],
    "created_at": "2024-05-20 09:00:00"
  }
}
```

### 5.2. `feeds.json`
```json
{
  "urls": [
    "https://news.google.com/rss/...",
    "https://feeds.feedburner.com/geeknews-feed"
  ]
}
```

### 5.3. `stats.json`
```json
{
  "total_visits": 1250,
  "log": [
    "2024-05-20 10:01:22",
    "2024-05-20 10:05:00"
  ]
}
```

## 6. AI 프롬프트 설계 (Prompt Engineering)

Gemini에게 전달할 프롬프트 전략:
*   **Role**: 전문 IT 뉴스 에디터.
*   **Input**: RSS에서 추출한 다수의 기사 (제목 + 요약).
*   **Constraints**:
    1.  중복 기사는 통합할 것.
    2.  섹션을 '헤드라인(심층 요약)'과 '단신(한 줄 요약)'으로 나눌 것.
    3.  톤앤매너는 객관적이고 전문적으로.
    4.  반드시 각 기사 끝에 `[원문보기](URL)` 링크를 포함할 것.
    5.  출력 형식은 Markdown.

## 7. 환경 변수 및 보안 (Secrets)

Streamlit Cloud의 `Secrets` 기능을 사용하여 관리 (소스코드 노출 금지).

| 변수명 | 설명 | 비고 |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | GitHub Personal Access Token | Repo 쓰기 권한 필수 |
| `REPO_NAME` | 저장소 경로 (예: `user/repo`) | |
| `GEMINI_API_KEY` | Google AI Studio API Key | |
| `ADMIN_PASSWORD` | 관리자 대시보드 접속 비밀번호 | |

## 8. 개발 단계별 체크리스트

1.  **초기 설정**
    *   [ ] GitHub Repository 생성.
    *   [ ] Streamlit Cloud 연동 및 Secrets 설정.
    *   [ ] 로컬 개발 환경 (`pip install -r requirements.txt`) 구성.

2.  **백엔드 로직 구현**
    *   [ ] `GitHubStorage` 클래스 구현 (JSON Read/Write/Commit).
    *   [ ] `analyze_feeds_with_gemini` 함수 구현 (RSS 파싱 + Gemini SDK 연동).

3.  **UI 구현**
    *   [ ] 사이드바 메뉴 (뉴스룸 vs 관리자) 분기 처리.
    *   [ ] 관리자 인증 로직 구현.
    *   [ ] 메인 화면 날짜별 데이터 로딩 및 렌더링.

4.  **테스트 및 배포**
    *   [ ] 로컬에서 RSS 수집 및 GitHub 파일 생성 테스트.
    *   [ ] Streamlit Cloud 배포 후 영구 저장(새로고침 후 데이터 유지) 확인.

---
*End of Specification*