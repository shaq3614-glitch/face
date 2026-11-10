"""AI 관상가: 얼굴 사진을 올리면 OpenAI 비전 모델이 관상을 풀이해 주는 Streamlit 앱."""

import base64
import datetime
import hashlib
import io
import os
import threading

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps, UnidentifiedImageError

# ---------------------------------------------------------------------------
# 설정값
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "gpt-4o-mini"
ALLOWED_TYPES = ["jpg", "jpeg", "png", "webp"]
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}  # MPO: 일부 휴대폰 카메라의 JPEG 변형
MAX_FILE_MB = 10
MAX_SIDE_PX = 1024
PREVIEW_WIDTH_PX = 260
JPEG_QUALITY = 85
MAX_COMPLETION_TOKENS = 1500
TEMPERATURE = 0.8
REQUEST_TIMEOUT_SEC = 30
REFUSAL_TAG = "[분석 불가]"

# 사용량 제한 (Secrets 또는 .env의 MAX_ANALYSES_PER_SESSION, DAILY_ANALYSIS_LIMIT로 변경 가능)
DEFAULT_MAX_PER_SESSION = 5
DEFAULT_DAILY_LIMIT = 100

CONSENT_NOTICE = "🙏 본인 또는 동의받은 사람의 사진만 올려주세요."

SETUP_GUIDE = """
**OpenAI API 키가 설정되지 않았습니다.**

- **로컬 실행:** 프로젝트 폴더에 `.env` 파일을 만들고 아래 내용을 넣어주세요.
  ```
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o-mini
  ```
- **Streamlit Cloud:** 앱 설정 → Secrets에 아래 내용을 넣어주세요.
  ```toml
  OPENAI_API_KEY = "sk-..."
  OPENAI_MODEL = "gpt-4o-mini"
  ```
"""

SYSTEM_PROMPT = f"""당신은 수십 년 경력의 한국 전통 관상가입니다.
이 서비스는 재미를 위한 엔터테인먼트이며, 사용자는 결과가 과학적 근거가 없다는 것을 알고 즐기고 있습니다.
사진을 올린 사람에게 직접 이야기하듯 "당신"이라고 부르며, 전통 관상학의 관점에서 풀이해 주세요.

[반드시 지킬 원칙]
1. 긍정적이고 따뜻하며 존중하는 말투를 사용합니다. 아쉬운 점도 조언이나 보완점으로 부드럽게 표현합니다.
2. 외모를 비하하거나 평가하지 않습니다. 인종, 피부색, 성별, 나이에 대한 고정관념을 담은 표현을 쓰지 않습니다.
3. 사진 속 인물이 누구인지 추측하거나 실존 인물(연예인 등)과 비교하거나 언급하지 않습니다.
4. 사진에 사람 얼굴이 전혀 없거나, 두 명 이상의 얼굴이 뚜렷하게 있을 때만 관상을 풀이하지 않습니다.
   이때는 첫 줄을 정확히 "{REFUSAL_TAG}"로 시작한 뒤 그 이유(얼굴 없음 / 여러 명)를 한두 문장으로 정중히 안내합니다.
5. 사람 얼굴이 한 명이라도 보이면 반드시 풀이합니다. 사진이 조금 흐리거나, 어둡거나, 각도가 비스듬하거나,
   일부가 가려져 있어도 보이는 특징을 바탕으로 최대한 풀이하세요. 화질을 이유로 거절하지 마세요.
   잘 보이지 않는 부위는 "사진에서 또렷하지 않지만"처럼 짧게 언급하고 전체 인상으로 풀이합니다.
6. 건강운은 일반적인 생활 습관 조언 수준으로만 쓰고, 질병을 진단하거나 암시하지 않습니다.
7. 아래 형식의 각 부위 이름에 붙은 전통 관상 용어(천정, 인당, 전택, 준두, 인중, 수주, 삼정)를 본문에서도 한 번 이상 써서
   전통 관상학의 해석을 들려주세요. 누구에게나 해당하는 뻔한 말보다 사진에서 보이는 특징에 근거해 구체적으로 씁니다.

[출력 형식]
분석이 가능하면 아래 Markdown 형식을 그대로 따릅니다. 제목(## 줄)과 부위 이름은 바꾸지 말고, 다른 ## 제목을 추가하지 마세요.
각 항목은 2~4문장으로 씁니다.

## 🧭 첫인상
## 👁️ 부위별 관상
- **이마 · 천정(天庭, 초년운):**
- **눈썹 · 인당(印堂, 눈썹 사이):**
- **눈 · 전택(田宅, 눈과 눈썹 사이):**
- **코 · 준두(準頭, 코끝):**
- **입 · 인중(人中, 코와 입 사이):**
- **귀 · 수주(垂珠, 귓불):**
- **얼굴형 · 삼정(三停, 이마·코·턱의 균형):**
## 💡 성격
## 💰 재물운
## ❤️ 연애운
## 🌿 건강운
## ✨ 종합 한마디
"""

USER_PROMPT = "제 사진입니다. 관상을 봐주세요."


# ---------------------------------------------------------------------------
# 설정 로딩
# ---------------------------------------------------------------------------
def _read_secret(name: str) -> str | None:
    """st.secrets에서 값을 읽는다. secrets 파일이 없으면 None."""
    try:
        value = st.secrets.get(name)
    except Exception:  # secrets.toml이 없으면 StreamlitSecretNotFoundError 등이 발생
        return None
    return str(value).strip() if value else None


def _setting(name: str) -> str:
    """st.secrets → .env(os.environ) 순서로 설정값을 읽는다. 없으면 빈 문자열."""
    return _read_secret(name) or os.getenv(name, "").strip()


def _int_setting(name: str, default: int) -> int:
    try:
        return max(0, int(_setting(name)))
    except ValueError:
        return default


def get_config() -> dict:
    """API 키, 모델명, 사용량 제한을 st.secrets → .env(os.environ) 순서로 읽는다."""
    load_dotenv()

    api_key = _setting("OPENAI_API_KEY")
    if not api_key:
        st.error(SETUP_GUIDE)
        st.stop()

    return {
        "api_key": api_key,
        "model": _setting("OPENAI_MODEL") or DEFAULT_MODEL,
        "max_per_session": _int_setting("MAX_ANALYSES_PER_SESSION", DEFAULT_MAX_PER_SESSION),
        "daily_limit": _int_setting("DAILY_ANALYSIS_LIMIT", DEFAULT_DAILY_LIMIT),
    }


# ---------------------------------------------------------------------------
# 사용량 제한 (공개 배포 시 API 비용 보호)
# ---------------------------------------------------------------------------
@st.cache_resource
def _daily_usage() -> dict:
    """서버 프로세스 전체가 공유하는 하루 사용량 카운터. 앱이 재시작되면 초기화된다."""
    return {"lock": threading.Lock(), "date": None, "count": 0}


def consume_daily_quota(daily_limit: int) -> bool:
    """오늘 사용량을 1 늘린다. 한도를 넘으면 False."""
    usage = _daily_usage()
    with usage["lock"]:
        today = datetime.date.today().isoformat()
        if usage["date"] != today:
            usage["date"], usage["count"] = today, 0
        if usage["count"] >= daily_limit:
            return False
        usage["count"] += 1
        return True


# ---------------------------------------------------------------------------
# 이미지 처리
# ---------------------------------------------------------------------------
class ImageError(Exception):
    """사용자에게 보여줄 이미지 관련 오류."""


def validate_upload(name: str, size: int) -> None:
    """확장자와 크기를 확인한다. 문제가 있으면 ImageError."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext and ext not in ALLOWED_TYPES:
        raise ImageError(
            f"'.{ext}' 파일은 올릴 수 없어요. JPG, PNG, WEBP 사진만 올려주세요."
        )
    if size > MAX_FILE_MB * 1024 * 1024:
        raise ImageError(
            f"파일이 너무 커요 ({size / 1024 / 1024:.1f}MB). {MAX_FILE_MB}MB 이하의 사진을 올려주세요."
        )


def preprocess_image(image_bytes: bytes) -> bytes:
    """이미지를 검사하고, RGB로 바꾸고, 긴 변 1024px 이하로 줄인 JPEG bytes를 돌려준다."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise ImageError("JPG, PNG, WEBP 형식의 사진만 올려주세요.")
            img.load()
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.getchannel("A"))
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    except ImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ImageError(
            "이미지를 읽을 수 없어요. 파일이 손상되었거나 사진 파일이 아닐 수 있어요. "
            "다른 사진으로 다시 시도해 주세요."
        ) from exc
    return buffer.getvalue()


def to_data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# 관상 분석
# ---------------------------------------------------------------------------
class AnalysisError(Exception):
    """사용자에게 보여줄 분석 관련 오류."""


def _is_unsupported_temperature(exc: openai.BadRequestError) -> bool:
    """모델이 temperature 값을 지원하지 않아 생긴 오류인지 확인한다."""
    return getattr(exc, "param", None) == "temperature" or "temperature" in str(exc).lower()


def analyze_face(image_data_url: str, api_key: str, model: str) -> str:
    """OpenAI 비전 모델에 이미지를 보내 관상 풀이 Markdown을 받아온다."""
    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SEC, max_retries=1)
    request = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        # high: 저해상도로 줄여 보지 않도록 원본(최대 1024px) 그대로 분석
                        "image_url": {"url": image_data_url, "detail": "high"},
                    },
                ],
            },
        ],
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "temperature": TEMPERATURE,
    }
    try:
        try:
            response = client.chat.completions.create(**request)
        except openai.BadRequestError as exc:
            if not _is_unsupported_temperature(exc):
                raise
            # 일부 모델은 temperature를 기본값 외에 지원하지 않는다 → 빼고 한 번 더 요청
            request.pop("temperature")
            response = client.chat.completions.create(**request)
    except openai.AuthenticationError as exc:
        raise AnalysisError("API 키가 올바르지 않아요. 키 설정을 확인해 주세요.") from exc
    except openai.PermissionDeniedError as exc:
        raise AnalysisError("이 API 키로는 해당 모델을 사용할 권한이 없어요.") from exc
    except openai.NotFoundError as exc:
        raise AnalysisError(
            f"모델 '{model}'을(를) 찾을 수 없어요. OPENAI_MODEL 설정을 확인해 주세요."
        ) from exc
    except openai.RateLimitError as exc:
        raise AnalysisError(
            "요청이 너무 많거나 API 사용 한도를 넘었어요. 잠시 후 다시 시도해 주세요."
        ) from exc
    except openai.APITimeoutError as exc:
        raise AnalysisError("응답이 너무 늦어요. 잠시 후 다시 시도해 주세요.") from exc
    except openai.APIConnectionError as exc:
        raise AnalysisError("OpenAI 서버에 연결할 수 없어요. 인터넷 연결을 확인해 주세요.") from exc
    except openai.BadRequestError as exc:
        raise AnalysisError(
            "요청을 처리할 수 없어요. 다른 사진으로 시도하거나, "
            "이미지 입력을 지원하는 모델인지 확인해 주세요."
        ) from exc
    except openai.APIStatusError as exc:
        raise AnalysisError(
            f"OpenAI 서버에서 오류가 발생했어요 (코드 {exc.status_code}). 잠시 후 다시 시도해 주세요."
        ) from exc
    except openai.OpenAIError as exc:
        raise AnalysisError("분석 중 알 수 없는 오류가 발생했어요. 다시 시도해 주세요.") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise AnalysisError("결과를 받지 못했어요. 다시 시도해 주세요.")
    return content.strip()


# ---------------------------------------------------------------------------
# 결과 해석
# ---------------------------------------------------------------------------
MARKDOWN_DECORATION = "*_#> `"


def parse_refusal(result: str) -> str | None:
    """분석 거부 응답이면 안내 문구를, 아니면 None을 돌려준다. (**[분석 불가]** 같은 꾸밈도 허용)"""
    lines = result.strip().splitlines()
    first = lines[0].strip().strip(MARKDOWN_DECORATION) if lines else ""
    if not first.startswith(REFUSAL_TAG):
        return None
    rest = [first.removeprefix(REFUSAL_TAG).strip(MARKDOWN_DECORATION)] + lines[1:]
    message = "\n".join(rest).strip()
    return message or "이 사진으로는 관상을 볼 수 없어요."


def split_sections(markdown: str) -> tuple[str, list[tuple[str, str]]] | None:
    """'## 제목' 기준으로 (머리말, [(제목, 본문), ...])을 돌려준다. 형식이 맞지 않으면 None."""
    preamble: list[str] = []
    sections: list[list] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            sections.append([line[3:].strip(), []])
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)

    parsed = [(title, "\n".join(body).strip()) for title, body in sections]
    if len(parsed) < 3 or any(not title for title, _ in parsed):
        return None
    return "\n".join(preamble).strip(), parsed


# ---------------------------------------------------------------------------
# 세션 상태
# ---------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "result": None,          # 분석 결과 Markdown
        "error": None,           # 분석 관련 오류 메시지
        "image_digest": None,    # 지금 입력된 사진의 해시 (바뀌면 결과 초기화)
        "prepared_jpeg": None,   # 검사·전처리를 통과한 JPEG bytes
        "input_error": None,     # 사진 검사 실패 메시지
        "analyzing": False,      # 분석 중이면 버튼 비활성화
        "analysis_count": 0,     # 이번 접속에서 분석한 횟수
        "source": "upload",      # 마지막으로 입력한 쪽: upload / camera
        "input_nonce": 0,        # 다시 하기 시 입력 위젯 초기화용
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_result() -> None:
    st.session_state.result = None
    st.session_state.error = None
    st.session_state.analyzing = False


def clear_image() -> None:
    st.session_state.image_digest = None
    st.session_state.prepared_jpeg = None
    st.session_state.input_error = None
    reset_result()


def start_over() -> None:
    clear_image()
    st.session_state.input_nonce += 1  # 위젯 key가 바뀌면서 업로드/카메라 입력이 비워진다


def start_analysis() -> None:
    st.session_state.analyzing = True
    st.session_state.error = None


def load_image(file) -> None:
    """새 사진이면 검사·전처리해서 세션에 저장한다. 같은 사진이면 아무것도 하지 않는다."""
    image_bytes = file.getvalue()
    digest = hashlib.sha256(image_bytes).hexdigest()
    if digest == st.session_state.image_digest:
        return

    clear_image()  # 새 사진이면 이전 결과 초기화
    st.session_state.image_digest = digest
    try:
        validate_upload(file.name, file.size)
        st.session_state.prepared_jpeg = preprocess_image(image_bytes)
    except ImageError as exc:
        st.session_state.input_error = str(exc)


# ---------------------------------------------------------------------------
# 디자인 (커스텀 CSS는 모두 여기에 모은다. 정적 CSS/HTML에만 unsafe_allow_html 사용)
# ---------------------------------------------------------------------------
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Noto+Serif+KR:wght@400;600;700&display=swap');

.stApp {
    background:
        radial-gradient(ellipse at top, rgba(212, 175, 55, 0.10), transparent 55%),
        #0E1322;
}
.stApp, .stMarkdown, p, li, label, button, input, textarea {
    font-family: 'Noto Serif KR', serif;
}
h1, h2, h3, h4, .hero-title {
    font-family: 'Gowun Batang', 'Noto Serif KR', serif !important;
}
.block-container {
    max-width: 720px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}
img { max-width: 100%; height: auto; }
.stApp p, .stApp li, .hero, .notice { word-break: keep-all; }  /* 한글 단어 중간 줄바꿈 방지 */
.st-key-preview { align-items: center; }

/* 헤더 */
.hero { text-align: center; margin-bottom: 1.25rem; }
.hero-mark {
    display: inline-block;
    padding: 0.15rem 0.5rem 0.15rem 1rem;
    border: 1px solid rgba(212, 175, 55, 0.6);
    color: #D4AF37;
    letter-spacing: 0.5em;
    font-size: 0.85rem;
}
.hero-title {
    font-size: clamp(2.1rem, 9vw, 2.9rem);
    font-weight: 700;
    color: #F3E3B0;
    margin: 0.7rem 0 0.2rem;
    line-height: 1.2;
}
.hero-sub { font-size: 1.05rem; color: #D9CFB8; margin: 0; }
.hero-desc { font-size: 0.9rem; opacity: 0.7; margin-top: 0.4rem; }

/* 안내 박스 */
.notice {
    font-size: 0.82rem;
    line-height: 1.7;
    padding: 0.7rem 1rem;
    margin-bottom: 1.25rem;
    border-left: 3px solid #D4AF37;
    border-radius: 8px;
    background: rgba(212, 175, 55, 0.07);
    color: #D9CFB8;
}

/* 카드 공통: 입력 카드와 결과 카드 */
.st-key-input_card, [class*="st-key-card_"] {
    background: #182036;
    border: 1px solid rgba(212, 175, 55, 0.22);
    border-radius: 16px;
    padding: 1.25rem 1.4rem;
}
[class*="st-key-card_"] h4 {
    color: #E8C766;
    font-size: 1.15rem;
    padding: 0 0 0.3rem;
    margin: 0;
}
[class*="st-key-card_"] p, [class*="st-key-card_"] li { line-height: 1.75; }

/* 종합 한마디: 가장 강조 */
.st-key-card_final {
    background: linear-gradient(160deg, rgba(212, 175, 55, 0.20), #182036 70%);
    border: 1.5px solid #D4AF37;
    box-shadow: 0 0 24px rgba(212, 175, 55, 0.18);
}
.st-key-card_final h4 { color: #F3E3B0; font-size: 1.3rem; }
.st-key-card_final p { font-size: 1.05rem; }

/* 관상 보기 버튼 */
button[kind="primary"], [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #E8C766, #C9A13B) !important;
    color: #1A1408 !important;
    border: none !important;
    font-weight: 700;
    font-size: 1.05rem;
    padding: 0.7rem 1rem;
}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
    filter: brightness(1.08);
}
button[kind="primary"] p, [data-testid="stBaseButton-primary"] p { color: #1A1408 !important; }

/* 푸터 */
.footer { text-align: center; font-size: 0.78rem; opacity: 0.55; margin-top: 2.5rem; }

/* 모바일 */
@media (max-width: 640px) {
    .block-container { padding: 1.5rem 1rem 2rem; }
    .st-key-input_card, [class*="st-key-card_"] { padding: 1rem; }
}
</style>
"""

HEADER_HTML = """
<div class="hero">
  <div class="hero-mark">觀相</div>
  <div class="hero-title">AI 관상가</div>
  <p class="hero-sub">사진 한 장으로 보는 나의 관상</p>
  <p class="hero-desc">이마·눈·코·입을 살펴 성격과 운세를 풀이해 드립니다</p>
</div>
"""

NOTICE_HTML = f"""
<div class="notice">
  ⚠️ 재미를 위한 서비스이며 과학적 근거가 없습니다.<br>
  🔒 이 앱은 사진을 저장하지 않으며, 사진은 분석을 위해서만 OpenAI로 전송됩니다.<br>
  {CONSENT_NOTICE}
</div>
"""

FOOTER_HTML = """
<div class="footer">본 결과는 재미로만 즐겨주세요 · 이 앱은 사진을 저장하지 않습니다</div>
"""


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
def inject_css() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_header() -> None:
    st.markdown(HEADER_HTML, unsafe_allow_html=True)
    st.markdown(NOTICE_HTML, unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def render_input():
    """업로드/카메라 탭을 그리고, 선택된 파일(UploadedFile)을 돌려준다.

    형식 제한(type)을 Streamlit에 맡기면 영어 오류가 나오므로, 형식·크기 검사는 앱에서 직접 한다.
    """
    nonce = st.session_state.input_nonce
    tab_upload, tab_camera = st.tabs(["📁 사진 업로드", "📸 카메라 촬영"])

    with tab_upload:
        uploaded = st.file_uploader(
            f"얼굴이 잘 보이는 정면 사진을 올려주세요 (JPG, PNG, WEBP · 최대 {MAX_FILE_MB}MB)",
            key=f"upload_{nonce}",
            on_change=lambda: st.session_state.update(source="upload"),
        )
    with tab_camera:
        captured = st.camera_input(
            "카메라로 찍기",
            key=f"camera_{nonce}",
            on_change=lambda: st.session_state.update(source="camera"),
        )

    # 마지막으로 입력한 쪽을 우선하고, 그쪽이 비어 있으면 다른 쪽을 사용
    order = [captured, uploaded] if st.session_state.source == "camera" else [uploaded, captured]
    return next((f for f in order if f is not None), None)


def render_result_cards(result: str) -> None:
    """결과를 섹션별 카드로 보여준다. 형식이 맞지 않으면 원문 그대로 보여준다.

    모델 응답은 st.markdown 기본 렌더링(HTML 비허용)으로만 표시한다.
    """
    parsed = split_sections(result)
    if parsed is None:
        with st.container(key="card_raw"):
            st.markdown(result)
        return

    preamble, sections = parsed
    if preamble:
        st.markdown(preamble)
    final_used = False
    for i, (title, body) in enumerate(sections):
        if "종합" in title and not final_used:  # 강조 카드는 하나만 (key 중복 방지)
            key, final_used = "card_final", True
        else:
            key = f"card_{i}"
        with st.container(key=key):
            st.markdown(f"#### {title}")
            if body:
                st.markdown(body)


def render_result() -> None:
    if st.session_state.error:
        st.error(st.session_state.error)

    result = st.session_state.result
    if not result:
        return

    refusal = parse_refusal(result)
    if refusal is not None:
        st.warning(refusal)
    else:
        st.markdown("### 📜 관상 풀이")
        render_result_cards(result)
        with st.expander("📋 결과 텍스트 복사하기"):
            st.code(result, language=None, wrap_lines=True)

    st.button("🔄 다시 하기", on_click=start_over, width="stretch")


def run_analysis(config: dict) -> None:
    """사용량 제한을 확인한 뒤 분석하고, 결과나 오류를 세션에 저장한다."""
    try:
        if st.session_state.analysis_count >= config["max_per_session"]:
            raise AnalysisError(
                f"한 번 접속할 때 최대 {config['max_per_session']}번까지 볼 수 있어요. "
                "잠시 후 다시 이용해 주세요."
            )
        if not consume_daily_quota(config["daily_limit"]):
            raise AnalysisError("오늘 준비된 관상 풀이가 모두 끝났어요. 내일 다시 찾아주세요.")

        st.session_state.analysis_count += 1
        with st.spinner("관상을 살펴보는 중..."):
            data_url = to_data_url(st.session_state.prepared_jpeg)
            st.session_state.result = analyze_face(data_url, config["api_key"], config["model"])
    except AnalysisError as exc:
        st.session_state.error = str(exc)
    except Exception:  # 예상하지 못한 오류에도 앱이 죽지 않도록
        st.session_state.error = "알 수 없는 오류가 발생했어요. 다시 시도해 주세요."
    finally:
        st.session_state.analyzing = False


def main() -> None:
    st.set_page_config(page_title="AI 관상가", page_icon="🔮", layout="centered")
    inject_css()
    init_state()
    render_header()
    config = get_config()

    with st.container(key="input_card"):
        file = render_input()
        if file is None:
            if st.session_state.image_digest is not None:  # 사진을 지우면 이전 결과도 지운다
                clear_image()
        else:
            load_image(file)

        if st.session_state.input_error:
            st.error(st.session_state.input_error)
        elif st.session_state.prepared_jpeg is not None:
            # 원본 대신 검사를 통과한 JPEG를 보여준다 (손상 파일로 앱이 멈추지 않음, 회전도 보정됨)
            with st.container(key="preview"):  # CSS로 가운데 정렬
                st.image(st.session_state.prepared_jpeg, caption="미리보기", width=PREVIEW_WIDTH_PX)

            remaining = max(0, config["max_per_session"] - st.session_state.analysis_count)
            st.button(
                "🔍 관상 보기",
                type="primary",
                width="stretch",
                disabled=st.session_state.analyzing or remaining == 0,
                on_click=start_analysis,
            )
            st.caption(
                f"이번 접속에서 {remaining}번 더 볼 수 있어요."
                if remaining
                else "이번 접속에서 볼 수 있는 횟수를 모두 사용했어요."
            )

    if st.session_state.prepared_jpeg is not None and st.session_state.analyzing:
        run_analysis(config)
        st.rerun()

    render_result()
    render_footer()


if __name__ == "__main__":
    main()
