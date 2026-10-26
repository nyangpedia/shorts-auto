# 작업 인수인계 (free-api-migration 브랜치)

## 목표
원본 shorts-auto(원작자 nam_ai_ai가 "조건 없이 무료" 공개)를 유료 API 없이 돌아가게 바꾸는 중. GPU 없는 PC 기준.

## 현재 무료 구성 (2026-10-23, 끝까지 영상 생성 성공)
| 단계 | 사용 | 비고 |
|---|---|---|
| 자막/STT | Faster-Whisper (CPU, base) | `av<18` 고정 필수 (1.2.1이 PyAV 18+와 충돌) |
| 대본/분석 | Gemini `gemini-3.5-flash` (OpenAI 호환 URL) | 3.8-flash는 100초+로 너무 느림, 2.5-flash는 신규 사용자 불가 |
| 음성 | Gemini TTS `gemini-3.8-flash-tts`, 음성 Kore | edge / qwen3도 선택 가능 (`TTS_PROVIDER`) |
| 이미지 | 씬 모델 `cloudflare`(Workers AI FLUX, 기본값, 하루 ~200장 무료, 정사각형 출력→ffmpeg가 9:16으로 크롭) | 2026-10-24 실제 생성 확인 |
| 영상 | `kenburns`(ffmpeg 줌) | |
| 이미지 제거됨 | `stock`(Pixabay/Pexels): 대본과 무관한 사진만 나와 2026-10-26 코드에서 삭제. `pollinations`: 키 없는 요청은 402로 막혀 제거함. `gemini_image`: 코드는 있으나 무료 한도 429라 사용 불가 | |
| 렌더링 | Remotion | Windows에서 publicDir를 프로젝트 폴더로 좁혀 symlink EPERM 해결 |

첫 결과물: 1080x1920, 24fps, 50초. 렌더링 약 6분(CPU).

## 새 PC 준비
```
git clone https://github.com/nyangpedia/shorts-auto
cd shorts-auto
git checkout free-api-migration
winget install Gyan.FFmpeg yt-dlp.yt-dlp
npx -y pnpm@9 install
cd apps/api && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```
`.env`는 git에 없음 → `.env.example`을 복사해 만들고 아래를 채우기:
- `GEMINI_API_KEY` (대본·음성), `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`, `OPENAI_ANALYSIS_MODEL=gemini-3.5-flash`
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` (이미지. dash.cloudflare.com → AI → Workers AI → Use REST API)
- `YOUTUBE_API_KEY` (레퍼런스 영상 검색. Google Cloud에서 YouTube Data API v3 사용 설정 후 "공개 데이터" API 키)
- Python 3.14 환경이라 `requirements.txt`의 `==` 고정을 `>=`로 풀어둠(httpx는 google-genai 때문에 >=0.28.1)

## 실행 (uv 없이)
- 백엔드: `apps/api`에서 `.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- 화면: 루트에서 `npx -y pnpm@9 dev:web` → http://127.0.0.1:5173
- 전체 자동 점검: `tools/dev/e2e_smoke.py <레퍼런스 음성.wav>` (서버 켠 상태에서)

## 2026-10-24 이후 추가된 것
- 이미지 모델 `cloudflare`(기본), `gemini_image` 추가 / Pollinations 제거
- 레퍼런스 검색 화면에 분야(Genre) 드롭다운 추가: 고르면 Keyword 칸이 채워짐. 키워드 목록은 `ReferenceSearchPanel.tsx`의 `GENRE_OPTIONS`
- 2026-10-26 회사 PC: `cloudflare` 이미지로 영상 끝까지 성공 (47초, 12씬, 렌더 7분). 이미지-대본 일치·캐릭터 일관성 좋음
- Cloudflare 토큰은 반드시 Workers AI → Use REST API → "Create a Workers AI API Token"으로 만든 것 (일반 토큰은 401)

## 2026-10-26 회사 PC에서 추가
- 화풍 선택 7종 (`apps/api/app/production/styles.py`, 화면 제작 패널의 "화풍" + [씬 구성하기]). 기본값은 `.env`의 `VISUAL_STYLE`
- Gemini 무료 한도는 **모델당 하루 약 20회** (영상 1편에 5~6회) → `LLM_FALLBACK_MODELS` 순서대로 자동 전환. 3.7-flash는 응답 없어 제외
- New Project / Edit title이 VS Code 미리보기에서 안 되던 문제 수정 (window.prompt 제거)
- Cloudflare 일시적 400 자동 재시도
- 레퍼런스 분석의 추천 주제 2~5번이 다른 분야로 나오는 건 원작자 설계(`analysis.py`). 같은 분야로 바꿀지 미정

## 영상(진짜 움직임) 조사 결과 (2026-10-26)
- 무료 AI 영상은 GPU 없이 불가. OpenRouter `wan-2.6:free`는 404(없음), Flow는 수작업+무료 워터마크/상업이용 불확실
- OpenRouter 유료 Seedance 1.5 Pro: 5초 480p 실측 $0.12 (720p 약 $0.25 추정). 품질 좋음, 워터마크 없음
- OpenRouter는 충전 이력 없어도 마이너스 잔액 허용 → 테스트 1회로 -$0.12 발생. 키는 .env에서 제거함
- 쓰게 되면: 훅 씬만 유료 영상, 나머지는 kenburns + 모션그래픽(무료). 돈 드는 요청은 사전 승인 받기

## 남은 일
- 정사각형→세로 크롭 시 양옆 잘림 있음 → 블러 배경 채우기(A) 또는 프롬프트에 중앙 배치(B) 중 사용자 확인 결과 거슬리지 않아 보류 (2026-10-26)
- 첫 영상 품질 검토 → 스톡 검색어를 LLM이 만들게 할지 결정
- 장르 프리셋 (정보/썰/뉴스/명언)
- 렌더링 6분 단축 검토
- Windows 전용 테스트 실패 3개(`/tmp/...` 경로)는 원래 있던 문제
- 원작자에게 LICENSE 파일 추가 요청
