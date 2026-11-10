# AI 관상가 단계별 개발 프롬프트

> 각 단계 프롬프트를 순서대로 복사해서 Claude Code에 붙여 넣으세요.
> 한 단계가 끝나면 `streamlit run app.py`로 직접 확인한 뒤 다음 단계로 넘어가는 것을 권장합니다.

---

## 1단계: 기본 뼈대 작성

```
PRD.md를 읽고 프로젝트의 기본 뼈대를 만들어줘. 이번 단계에서는 OpenAI API 호출은 하지 말고 구조만 잡아줘.

만들 파일:
1. requirements.txt
   - streamlit, openai, python-dotenv, pillow (버전은 Streamlit Cloud에서 설치 가능한 범위로 하한만 지정)
2. .gitignore
   - .env, .streamlit/secrets.toml, __pycache__/, *.pyc, .venv/, venv/ 포함
3. .env.example
   - OPENAI_API_KEY=your-api-key-here
   - OPENAI_MODEL=gpt-4o-mini
4. app.py
   - st.set_page_config(페이지 제목 "AI 관상가", 아이콘 🔮, layout="centered")
   - 제목, 부제, 면책 고지 문구(PRD F9)
   - 설정 로딩 함수 get_config(): PRD 8.3 순서대로 st.secrets → .env(os.environ) 순으로 OPENAI_API_KEY, OPENAI_MODEL을 읽기.
     st.secrets 파일이 없을 때 예외가 나지 않도록 try/except 처리.
     키가 없으면 설정 방법을 st.error로 안내하고 st.stop()
   - 이미지 업로드 영역, 미리보기 영역, "관상 보기" 버튼, 결과 영역은 자리만 잡아두기 (TODO 주석)
   - 함수 단위로 나누기: get_config(), render_header(), main()
5. README.md
   - 프로젝트 소개, 로컬 실행 방법(가상환경, pip install, .env 작성, streamlit run), Streamlit Cloud 배포 방법(Secrets 설정 포함)

완료 후:
- pip install -r requirements.txt 를 실행하고
- streamlit run app.py 가 오류 없이 뜨는지 확인해줘 (헤드리스로 실행 후 종료).
- .env가 없을 때 안내 메시지가 제대로 나오는지도 확인해줘.
```

---

## 2단계: 주요 기능 추가

```
PRD.md의 5.1 필수 기능(F1~F9)과 6장 AI 분석 설계를 app.py에 구현해줘.

구현 내용:
1. 이미지 입력 (F1, F2)
   - st.tabs로 "사진 업로드" / "카메라 촬영" 두 탭 제공
   - 업로드: jpg, jpeg, png, webp만 허용, 10MB 초과 시 오류 안내
   - 카메라: st.camera_input
2. 미리보기 (F3)
   - 선택된 이미지를 화면에 표시
3. 이미지 전처리 (F4) - preprocess_image(file) 함수
   - Pillow로 열기, EXIF 회전 보정(ImageOps.exif_transpose)
   - RGBA/P 모드는 RGB로 변환
   - 긴 변 기준 1024px 이하로 리사이즈
   - JPEG(quality=85)로 저장 후 base64 인코딩해서 data URL 반환
   - 손상된 이미지는 친절한 오류 메시지
4. 관상 분석 (F5) - analyze_face(image_data_url, api_key, model) 함수
   - openai 패키지의 OpenAI 클라이언트로 Chat Completions API 호출
   - 메시지에 image_url(data URL)과 텍스트를 함께 전달
   - max_tokens 약 1500, temperature 약 0.8
   - SYSTEM_PROMPT는 파일 상단 상수로 분리하고 PRD 6.2 원칙을 모두 반영:
     * 한국 전통 관상가 역할, 재미용 엔터테인먼트 맥락 명시
     * 긍정적이고 존중하는 말투, 외모 비하·인종·성별·나이 고정관념 금지
     * 얼굴이 없거나 여러 명이면 분석하지 말고 정해진 문구로 안내
     * 특정 인물이 누구인지 추측 금지
     * PRD 6.3 출력 형식(Markdown 섹션) 그대로 따르기
5. 결과 표시 (F6, F7)
   - "관상 보기" 버튼 클릭 시 st.spinner("관상을 살펴보는 중...") 표시
   - 분석 중 버튼 중복 클릭 방지 (st.session_state 사용)
   - 결과를 st.session_state에 저장해 리런 후에도 유지
   - 새 이미지를 올리면 이전 결과 초기화
   - 결과 Markdown 표시 + "다시 하기" 버튼
6. 오류 처리 (F8)
   - openai의 AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError, BadRequestError 등을 구분해서 한국어로 안내
   - 그 외 예외도 앱이 죽지 않도록 처리
   - 응답이 비어 있으면 재시도 안내
7. 개인정보 안내
   - "업로드한 사진은 저장되지 않으며 분석 후 바로 폐기됩니다" 문구 표시
   - "본인 또는 동의받은 사람의 사진만 올려주세요" 문구 표시

주의:
- API 키를 코드나 로그에 출력하지 말 것
- 이미지를 디스크에 저장하지 말 것
- 모델명은 하드코딩하지 말고 get_config()에서 받은 값 사용

완료 후 실제 .env의 키로 테스트 이미지 1장을 분석해 보고, 얼굴이 없는 이미지(예: 단색 이미지)로도 테스트해서 결과를 알려줘.
.env에 키가 없으면 그 부분은 건너뛰고 건너뛰었다고 알려줘.
```

---

## 3단계: UI 디자인

```
app.py의 기능은 그대로 두고 UI 디자인만 개선해줘. PRD 11장 와이어프레임을 기준으로 해줘.

디자인 방향:
- 컨셉: 동양적이고 신비로운 "관상가의 방" 느낌. 과하지 않고 깔끔하게.
- 색상: 짙은 남색/먹색 계열 배경 + 금색 포인트, 또는 한지 느낌의 밝은 베이지 배경 + 먹색 글씨 중 어울리는 쪽 선택
- 폰트: Google Fonts의 한글 폰트(예: Noto Serif KR, Gowun Batang) 를 st.markdown + CSS로 적용
- .streamlit/config.toml 로 기본 테마(primaryColor, backgroundColor, textColor, font) 설정

구성:
1. 헤더: 큰 제목, 부제, 짧은 설명
2. 면책·개인정보 안내: 눈에 띄지만 방해되지 않는 작은 안내 박스
3. 입력 영역: 탭(업로드/카메라) + 미리보기를 둥근 모서리 카드 안에, 미리보기 크기는 적당히 제한
4. "관상 보기" 버튼: 전체 폭, 강조 색상
5. 결과 영역:
   - 결과를 섹션별로 나눠 카드 형태로 표시 (첫인상, 부위별 관상, 성격, 재물운, 연애운, 건강운, 종합 한마디)
   - 모델 응답 Markdown을 "## " 기준으로 파싱해서 카드로 나누고, 파싱에 실패하면 원문 그대로 표시 (안전한 대체 경로 필수)
   - 종합 한마디는 가장 강조
   - st.code 또는 복사 버튼으로 결과 전체 복사 기능
6. 푸터: 면책 문구 한 줄

조건:
- 모바일 화면(폭 375px)에서도 가로 스크롤 없이 보이게
- 커스텀 CSS는 한 곳(상수 또는 함수)에 모으기
- unsafe_allow_html=True는 CSS와 정적 HTML에만 쓰고, 모델 응답 텍스트는 HTML로 그대로 넣지 말 것 (XSS 방지, st.markdown 기본 렌더링 사용)
- 기존 기능(업로드, 카메라, 오류 처리, 세션 상태)이 깨지지 않게 할 것

완료 후 streamlit run app.py 로 오류 없이 실행되는지 확인해줘.
```

---

## 4단계: 종합 검토 (코드 리뷰 + Playwright 검증)

```
PRD.md를 기준으로 지금까지 만든 프로젝트 전체를 자세히 검토해줘. 검토는 두 부분으로 나눠서 해줘.

### A. 코드 검토
app.py, requirements.txt, .gitignore, .env.example, README.md, .streamlit/config.toml 을 모두 읽고 확인:

1. PRD 요구사항 충족 여부
   - F1~F9 각각을 표로 정리: 구현 여부(O/△/X), 해당 코드 위치(파일:줄), 비고
   - 6장 프롬프트 원칙, 6.3 출력 형식 반영 여부
   - 7장 비기능 요구사항(보안, 개인정보, 비용, 호환성, 유지보수) 충족 여부
   - 8장 키 로딩 순서가 PRD와 같은지
2. 버그 및 문제점
   - st.secrets가 없을 때 예외 발생 여부
   - 세션 상태 버그 (새 이미지 업로드 시 이전 결과가 남는지, 버튼 중복 클릭, 다시 하기 동작)
   - 이미지 처리 예외 (PNG 투명 배경, 세로 사진 EXIF 회전, 손상 파일, 10MB 초과, 아주 작은 이미지)
   - OpenAI API 예외 처리 누락 여부, 응답이 None/빈 문자열일 때
   - 결과 파싱 실패 시 대체 경로 동작
3. 보안
   - API 키가 코드, 로그, 화면에 노출되는 곳이 없는지
   - .gitignore에 .env와 secrets.toml이 있는지, git에 추적되고 있지 않은지
   - unsafe_allow_html로 모델 응답을 렌더링하는 곳이 없는지
4. 배포 준비
   - requirements.txt로 Streamlit Cloud에서 설치 가능한지
   - 메인 파일 경로, Python 버전 문제 없는지
   - README의 배포 안내가 정확한지

### B. Playwright로 실제 화면 검증
streamlit run app.py --server.headless true --server.port 8501 로 앱을 백그라운드에서 띄운 뒤 Playwright로 직접 사용해 보면서 확인해줘.

1. 첫 화면
   - http://localhost:8501 접속, 제목·면책 고지·개인정보 안내가 보이는지
   - 스크린샷 저장
2. 정상 흐름
   - 테스트용 얼굴 이미지를 업로드 (없으면 공개 라이선스 이미지나 생성한 이미지 사용, 실존 인물 사진은 피할 것)
   - 미리보기 표시 확인 → "관상 보기" 클릭 → 스피너 표시 확인 → 결과 카드 표시 확인
   - 결과에 PRD 6.3의 섹션이 모두 있는지 확인
   - 스크린샷 저장
3. 예외 흐름
   - 얼굴이 없는 이미지(단색 PNG) 업로드 → 분석 거부 안내가 나오는지
   - 지원하지 않는 형식(.txt, .gif) 업로드 시도 → 막히는지
   - 손상된 이미지 파일(확장자만 .jpg) → 오류 메시지가 나오고 앱이 죽지 않는지
   - 다른 이미지로 교체 시 이전 결과가 사라지는지
   - "다시 하기" 버튼 동작
4. 반응형
   - 뷰포트를 375x812(모바일), 1280x800(데스크톱)로 바꿔 각각 스크린샷
   - 가로 스크롤, 겹침, 잘린 글자가 없는지
5. 콘솔
   - 브라우저 콘솔 에러, Streamlit 서버 로그 에러 확인
   - 서버 로그에 API 키가 찍히지 않는지 확인

.env에 API 키가 없으면 실제 분석이 필요한 테스트는 건너뛰고 건너뛰었다고 명시해줘. 테스트용 파일과 스크린샷은 프로젝트 폴더가 아닌 임시 폴더에 저장해줘.

### 결과 보고
- PRD 충족 표 (F1~F9 + 비기능 요구사항)
- 발견한 문제 목록: 심각도(높음/중간/낮음), 위치(파일:줄), 재현 방법, 수정 제안
- Playwright 테스트 결과 표: 시나리오, 기대 결과, 실제 결과, 통과 여부
- 스크린샷 경로
- 마지막에 "배포 가능 / 수정 후 배포 / 배포 불가" 중 하나로 결론

검토가 끝나면 바로 고치지 말고, 문제 목록을 먼저 보여준 뒤 수정 여부를 물어봐줘.
수정한 경우에는 해당 시나리오를 Playwright로 다시 테스트해서 고쳐졌는지 확인해줘.
```
