# 🔮 AI 관상가

얼굴 사진을 올리면 OpenAI 이미지 분석 모델이 관상을 풀이해 주는 Streamlit 웹앱입니다.

> 본 서비스는 재미를 위한 것이며 과학적 근거가 없습니다. 이 앱은 사진을 저장하지 않으며, 사진은 분석을 위해서만 OpenAI로 전송됩니다.

## 로컬 실행

```bash
# 1. 가상환경 만들기
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 환경 변수 설정: .env.example을 복사해 .env를 만들고 키를 넣기
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 4. 실행
streamlit run app.py
```

`streamlit` 명령을 찾을 수 없다고 나오면 `python -m streamlit run app.py`로 실행하세요.

## 설정값

`.env`(로컬) 또는 Streamlit Secrets(배포)에 넣습니다. Secrets를 먼저 읽고, 없으면 `.env`에서 읽습니다.

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `OPENAI_API_KEY` | O | | OpenAI API 키 |
| `OPENAI_MODEL` | | `gpt-4o-mini` | 이미지 입력을 지원하는 모델 |
| `MAX_ANALYSES_PER_SESSION` | | `5` | 한 번 접속(브라우저 탭)에서 분석할 수 있는 횟수 |
| `DAILY_ANALYSIS_LIMIT` | | `100` | 앱 전체에서 하루에 분석할 수 있는 횟수. 앱이 재시작되면 초기화됩니다 |

## Streamlit Cloud 배포

1. 이 저장소를 GitHub에 push합니다. `.env`는 `.gitignore`에 들어 있어 올라가지 않습니다.
2. [share.streamlit.io](https://share.streamlit.io)에서 **Create app**을 누르고 저장소, 브랜치, 메인 파일 `app.py`를 고릅니다.
3. **Advanced settings**에서
   - **Python version**은 `3.12`를 고릅니다.
   - **Secrets**에 아래 내용을 넣습니다.
     ```toml
     OPENAI_API_KEY = "sk-..."
     OPENAI_MODEL = "gpt-4o-mini"
     MAX_ANALYSES_PER_SESSION = "5"
     DAILY_ANALYSIS_LIMIT = "100"
     ```
4. **Deploy**를 누릅니다.

## 비용 관리

공개 URL은 누구나 접속할 수 있고, 분석할 때마다 내 OpenAI API 비용이 나갑니다.

- 앱에는 접속당 횟수 제한과 하루 전체 횟수 제한이 있습니다 (위 설정값 참고).
- 하루 제한은 앱이 재시작되면 초기화되므로, **OpenAI 대시보드의 Limits 메뉴에서 월 사용 한도(budget)도 꼭 설정**하세요.
