# 작업 인수인계 (free-api-migration 브랜치)

> 새 세션의 Claude에게: 이 파일을 먼저 읽고 이어서 작업. 사용자는 **동의보다 비판적 검토**를 원함
> (아이디어마다 단점·우선순위를 먼저 짚을 것). **돈이 드는 API 호출은 금액을 말하고 승인받은 뒤에만.**

## 목표
원본 shorts-auto(원작자 nam_ai_ai가 "조건 없이 무료" 공개)를 유료 API 없이 돌아가게 바꾸는 중. GPU 없는 PC 기준.
개인 채널용으로 먼저 쓰고, 잘 되면 서비스화 검토.

## 현재 무료 구성 (2026-10-26 기준, 끝까지 영상 생성 확인)
| 단계 | 사용 | 비고 |
|---|---|---|
| 자막/STT | Faster-Whisper (CPU, base) | `av<18` 고정 필수 |
| 대본/분석 | Gemini `gemini-3.5-flash` | 무료 한도 **모델당 하루 ~20회**(영상 1편에 5~6회) → `LLM_FALLBACK_MODELS` 순서로 자동 전환 |
| 음성 | Gemini TTS `gemini-3.8-flash-tts`, 음성 Kore | edge / qwen3도 선택 가능 (`TTS_PROVIDER`) |
| 이미지 | `cloudflare` (Workers AI FLUX schnell, 하루 ~200장) | 정사각형 출력 → 9:16로 크롭. 일시적 400은 자동 재시도 |
| 화풍 | 7종 선택 (`app/production/styles.py`) | 제작 패널 "화풍" + [씬 구성하기]. 기본값 `VISUAL_STYLE` |
| 영상 | `kenburns` 카메라 5종 순환 + Remotion 모션그래픽 | 씬 전환 펀치줌·플래시, 자막 숫자 노란 강조, 상단 진행 바 |
| 렌더링 | Remotion | 약 5~7분(CPU) |

삭제/불가: `stock`(Pixabay/Pexels, 대본과 무관한 사진 → 삭제), `pollinations`(402), `gemini_image`(무료 한도 없음).

## 새 PC 준비
```
git clone https://github.com/nyangpedia/shorts-auto
cd shorts-auto
git checkout free-api-migration
git pull
winget install Gyan.FFmpeg yt-dlp.yt-dlp
npx -y pnpm@9 install
cd apps/api && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```
`.env`는 git에 없음 → `.env.example` 복사 후 채우기:
- `GEMINI_API_KEY`, `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`, `OPENAI_ANALYSIS_MODEL=gemini-3.5-flash`
- `LLM_FALLBACK_MODELS=gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest` (3.7-flash는 응답 없음, 넣지 말 것)
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` — 반드시 Workers AI → Use REST API → "Create a Workers AI API Token" (일반 토큰은 401)
- `YOUTUBE_API_KEY` (선택, 키워드 검색용), `VISUAL_STYLE` (선택, 예: `webtoon`)

## 실행 (uv 없이)
- 백엔드: `apps/api`에서 `.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- 화면: 루트에서 `npx -y pnpm@9 dev:web` → http://127.0.0.1:5173 (VS Code 미리보기보다 크롬 권장)
- **주의:** `--reload`가 스크립트로 쓴 파일 변경을 놓치는 경우가 있음. 코드 바꾼 뒤 예전처럼 동작하면 서버 재시작
- **재시작할 때:** 8000번 포트 프로세스만 죽이면 예전 워커(`multiprocessing spawn_main` python)가 소켓을 쥔 채 남아 옛 코드로 응답함. 그 python 프로세스도 같이 종료할 것.
- 프로젝트 보관(`archived`)·삭제(`DELETE /api/projects/{id}`), 렌더 완료·보관 프로젝트는 사이드바 "완료·보관함"으로. 레퍼런스 검색 시 외국어 제목은 LLM 1회 호출로 한국어 뜻(`title_ko`)을 붙임(실패해도 검색은 성공).
- 전체 자동 점검: `tools/dev/e2e_smoke.py <레퍼런스 음성.wav>` (서버 켠 상태에서, Gemini 한도 5~6회 소모)
- 테스트 프로젝트: `outputs/261023_1711`(피라미드, 웹툰 화풍). `outputs/261026_1249`는 **사용자 작업용이라 건드리지 말 것**

## 2026-10-27 작업 (앱 이름 "쇼츠공방", 설치형 배포 목표)
- 화면 전면 개편: 6단계 마법사(레퍼런스→분석→대본→음성·화풍→이미지·영상→완성). `apps/web/src/App.tsx` + `components/*Step.tsx`, 단계 계산 `wizard.ts`
  - 주소 `?project=<id>&step=<1-6>`로 특정 화면 바로 열기 (헤드리스 캡처 확인용으로도 씀)
- 대본: 정확성 최우선 규칙 추가(소수설 단정 금지), 직접 편집 `PUT /scripts/final`, AI 사실 확인 `POST /scripts/factcheck`
  (검색 없이 모델 지식으로 판정. Gemini 무료 등급은 검색 grounding 불가 — 2.5는 신규 사용자 막힘, 3.x는 무료 한도 0)
- 레퍼런스 검색: `videoDuration=short` + 50개 + KR/ko → 같은 할당량으로 후보 약 3배
- 사용량 추정 `/api/usage` (outputs/_usage.json), 왼쪽 아래 표시
- 예전 패널 전부 삭제(ProductionPanel 2천 줄 등). API 키 상태 화면(SettingsPanel)도 같이 빠짐

## 다음 할 일 (우선순위 순)
1. **사용자가 새 화면으로 한 편 끝까지 만들어 보기** — 화면은 캡처·단위 테스트로만 확인함. 실제 클릭 흐름 검증 필요
2. **이미지 잘림 조정** — 정사각형→9:16 크롭 + kenburns 줌으로 양옆 손실. (a) 줌 폭 축소 (b) 프롬프트에 "피사체 중앙" 추가가 최소 수정
3. **설치형 배포 준비** — 원작자 LICENSE 받기 → NOTICE(크레딧), 원클릭 실행 스크립트, 설치 안내서,
   **API 키 입력 화면**(지금은 .env 직접 편집 — 배포 시 필수)
4. 2~3편 실제 업로드 → 시청 지속률 보고 다음 개선 결정
5. 다크 모드 (아직 없음)

## 결정·조사 기록
- 추천 주제 5개: 레퍼런스와 **같은 분야, 서로 다른 각도**로 변경 완료 (`analysis.py`)
- 유튜브 2025-07 정책: 템플릿 대량생산형은 "inauthentic content"로 수익화 제외 위험 → 사람 관점·대본 손질이 대응책
- 무료 AI 영상은 GPU 없이 불가. Flow(수작업, 무료 워터마크·상업이용 불확실), Qwen/Wan(로컬 GPU 필요),
  OpenRouter `wan-2.6:free`(404, 없음), NVIDIA NIM(텍스트만, 무료는 개발용 약관) 모두 확인함
- 유료 영상 단가(5초 9:16, 소리 없이): Seedance 1.5 Pro 480p ~$0.06 / 720p ~$0.13, Grok Imagine 1.5 Lite 720p ~$0.16,
  Veo 3.1 Lite 720p ~$0.15. Higgsfield 경유는 클립당 $0.25~0.35 + 월 구독. **`generate_audio` 끄면 절반**
- OpenRouter: 충전 없이도 마이너스 잔액 허용 → 테스트로 -$0.12 발생. 키는 .env에서 제거, 계정만 남음
- 캐릭터 후보 8종(SVG, `outputs/style_compare/characters.html`) — 보류. 플랫 벡터라 실사/웹툰 배경과 스타일 충돌
- Windows 전용 테스트 실패 3개(`/tmp/...` 경로)는 원래 있던 문제
- 원작자에게 LICENSE 파일 추가 요청 필요 (유료화 전)

## 원작자 코드 재작성 (라이선스 없이 배포하기 위해) — 진행 중
- 원칙: 기능·화면·파일 형식은 유지, 코드는 새로 작성. 대본/이미지 프롬프트는 기존과 A/B 비교 후 교체.
- 진행 상황 확인: `git blame --line-porcelain <file> | grep -c "^author gwnam1"` (원작자 줄 수)
- [x] 1단계 제작 파이프라인 (`app/production/`: paths, media, voice, scenes, images, motion, revise, state, numbers). DALL·E 3 → `gpt-image-2.5-flare`. Qwen TTS 제거.
- [ ] 2단계 대본·분석 프롬프트 (`scripts/generation.py`, `references/analysis.py`) — A/B 필수
- [ ] 3단계 레퍼런스 (`references/router.py`, `youtube.py`, `files.py`, `audio.py`, `models.py`)
- [ ] 4단계 렌더러·제작 라우터·작업 기록·프로젝트·설정 (`production/renderer.py`, `production/router.py`, `production/models.py`, `jobs/*`, `projects/service.py`, `core/settings.py`, `main.py`)
- [ ] 5단계 웹 `api.ts`, `types.ts`, 원작자 테스트
- [ ] 6단계 `tools/higgsfield-mcp` (기능 유지, 코드 재작성)
