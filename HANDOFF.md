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
| 이미지 | `cloudflare` (Workers AI **FLUX.2 klein 768x1344 세로 그대로**, 실패 시 flux-1-schnell 정사각형→가운데 크롭; **하루 약 70장**, 24시간 롤링 — 대시보드 0이어도 429 code 4006이면 소진) | 일시적 400은 자동 재시도 |
| 화풍 | 7종 선택 (`app/production/styles.py`) | 제작 패널 "화풍" + [씬 구성하기]. 기본값 `VISUAL_STYLE` |
| 영상 | `parallax` 2.5D 입체 모션(기본, 깊이 모델 Depth Anything V2 small) 또는 `kenburns` + HyperFrames 모션그래픽 | 씬 전환 펀치줌·플래시, 자막 숫자 노란 강조, 상단 진행 바 |
| 렌더링 | HyperFrames 0.8.214 (`apps/video/shorts.html`, WAAPI 애니메이션, 텔레메트리 끔) | 50초 영상 약 5분(CPU) |

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

## 2026-10-29 작업
- 렌더러 Remotion → HyperFrames (SSIM 0.984로 동등 확인). 정지 이미지는 2.5D 패럴랙스로 움직임
- 말소리 없는 레퍼런스: 저화질로 받아 프레임 24장을 Gemini가 읽어 대본 대신 사용 (`references/screen.py`)
- 썸네일 만들기, 유튜브 **수동 업로드 도우미**(파일 준비+폴더 열기, 제목·설명·태그 복사).
  API 자동 업로드는 미인증 앱이면 비공개로 잠겨서 보류 (YouTube 감사 통과 후)
- 화풍 고르면 이미지 자동 생성, Cloudflare 한도 소진 표시 동기화
- 장면 나누기: 22자 넘으면 조사·어미 뒤에서 자르고 "것·수·때"는 앞말에 붙임 (`scenes.py`, 사용자 요청)
- 오늘의 레퍼런스 키워드: 만약에 지구/과학, what if earth/science, もしも 地球/科学

## 집 PC로 이어가기 (2026-10-29 기준 계획)
- 코드는 GitHub(`mine` = nyangpedia/shorts-auto, `free-api-migration`)에 다 있음. 위 "새 PC 준비" 순서대로 설치
- **git에 없는 것 2가지는 따로 옮길 것:** `.env`(저장소 최상위 폴더, 키), `outputs/`(프로젝트, ~740MB)
  → 구글 드라이브/USB. 두 PC에서 **동시에 같은 프로젝트를 열지 말 것**(덮어쓰기)
- 첫 실행 때 깊이 모델(~100MB)·Whisper 모델이 자동 다운로드됨
- 회원 관리(Supabase): 사용자의 블로그 자동화 앱 "글모아"와 **같은 Supabase 프로젝트 공유** 방향.
  집 PC에 글모아 코드가 있으니 거기서 로그인·이용권 확인·자동 업데이트 방식을 읽고 설계할 것.
  service_role 키는 앱에 절대 넣지 않음(anon 키 + URL만). 설치 파일은 Supabase 저장소 말고 GitHub Releases (무료 egress 5GB/월)
  — 단, **영상 20~30편 올려 반응 보기 전엔 착수 보류** 권장

## 2026-10-29 회원 로그인 (1단계: 화면만)
- 글모아와 **같은 Supabase 프로젝트·같은 계정**으로 로그인 (`apps/web/src/components/LoginGate.tsx`, `src/supabase.ts`).
  `.env`의 `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`(공개 값, 글모아 `.env.local`의 NEXT_PUBLIC_* 와 같은 값)가 비어 있으면 로그인 없이 열림. `vite.config.ts`의 `envDir`이 저장소 최상위 `.env`를 읽음
- **아직 없음**: 회원가입(글모아 DB 트리거가 약관 동의 메타데이터 없으면 가입 거부 → 쇼츠공방 약관을 먼저 정해야 함), 서버 쪽 토큰 검증(지금은 화면에서만 막음), 하루 한도, 구글 로그인, 비밀번호 재설정
- 다음 설계: 계정은 하나, 이용권은 앱별 표(예: `shorts_members`: 기간·요금제·하루 영상 한도)로 분리. 글모아 `members` 표는 건드리지 않음. DB 변경 SQL은 Supabase SQL Editor에 사용자가 직접 붙여 넣어야 함(글모아 때 자동 적용이 막혔음). 글모아 참고 코드: `G:\블로그자동화\블로그자동화` 의 `lib/member.ts`, `supabase/migrations/0001·0006`, `components/MemberGate.tsx`

## 2026-10-30 작업·결정
- **통근열차·우주정거장 눈물**: 이 PC(회사)에서 이미지·렌더·썸네일까지 끝남(`final.mp4`, `thumbnail.jpg`). **아직 유튜브에 안 올림.** `261029_1712`(핸드폰 로딩)는 대본까지만 됨(화풍·씬 구성 전)
- 화풍 선택 카드에 샘플 그림 12장 추가 (`apps/web/public/styles/<id>.jpg`, 원본은 `outputs/style_samples`)
- 이미지 모델: OpenAI는 `gpt-image-2.5-flare` 유지(Sunburst로 바꿨다 되돌림, 유료·비교 후 판단). 무료 기본은 Cloudflare FLUX.2 klein 세로 768x1344
- 장면 나누기 규칙 개선(`scenes.py`): 조사·어미 뒤에서 자르고 "것·수·때"는 앞말에 붙임
- **약관 초안** `legal/terms-ko.md` — `[ ]` 칸(운영자 정보·유료/환불·시행일)은 비어 있음. 법률 검토 전. 개인정보처리방침은 아직 없음(이메일 수집하므로 필요)
- **로그인**: 이 PC `.env`에도 `VITE_SUPABASE_URL`(기본 주소만, `/rest/v1/` 붙이지 말 것)과 `VITE_SUPABASE_PUBLISHABLE_KEY` 넣어 화면 로그인 확인함. Secret(service_role) 키는 절대 넣지 않음
- **웹 서버는 `.env`를 시작할 때만 읽음.** 패키지(`pnpm install`)나 `.env`가 바뀌면 웹 서버(vite) 재시작
- **작업 내역 동기화 결정**: 로그인은 "누구인지"만 확인함. 프로젝트는 PC마다 `outputs/`에만 있음(git 제외). 개인용 해법은 `outputs`를 구글 드라이브 등 동기화 폴더로 옮기고 `OUTPUT_DIR`로 지정(미러링 모드, 한 번에 한 PC만 열기). **서비스·서버 방식은 배포 계획(각자 PC 설치)과 맞지 않아 보류.** 동기화 서비스·폴더는 사용자 미정
- **지인 평가·배포 논의**(미결정): 막힌 것 = 설치 파일 없음, 서버 로그인 검증 없음, 가입 경로 없음(글모아 DB 트리거가 약관 동의 정보 없으면 가입 거부), 약관·방침 미완, 지인이 Gemini·Cloudflare 키를 각자 발급해야 함. 선택지: A 결과물(영상·녹화)로 먼저 반응 보기 / B 소수에게 직접 설치 안내 / C 설치 파일 제작. 사용자 답 대기
- 설치 파일 크기 실측(압축 전): venv 644MB, node_modules 764MB(대부분 개발 도구), ffmpeg full 665MB(경량 빌드로 교체 가능), HyperFrames 크롬 274MB, 모델 236MB(첫 실행 때 받게 하면 제외). 줄이면 압축 후 약 0.6~0.9GB 추정(합산 추정, 실측 아님). Windows 전용. 설치 파일은 GitHub Releases
- 로그인 화면 평가: 폰 안이 블러 동그라미뿐(실제 영상 프레임으로 교체 권장), 가운데 여백, 서비스 설명·가입·비번 찾기·약관 링크 없음. 기능(서버 검증)이 우선, 화면은 평가자에게 보여 주기 전에
- `PROGRESS.md`(10/30 13:25, 이 세션이 만들지 않음, 내용이 낡음)는 커밋하지 않음 — 쓰는 규칙 확인 필요

## 집에서 이어서 (다음 작업 순서)
1. `git pull` 후 `npx -y pnpm@9 install`, 웹 서버 재시작
2. **서버(API)가 Supabase 로그인 토큰 검증** (FastAPI, 공개 JWKS로 검증, 비밀 키 불필요). 배포 모드는 **값이 없으면 앱이 안 열리게**(지금은 꺼짐)
3. 글모아 코드(`G:\블로그자동화\블로그자동화`의 `lib/member.ts`, `supabase/migrations`, `components/MemberGate.tsx`)를 보고 **가입(약관 동의 메타데이터)·이용권 표** 설계. 이 PC에는 글모아 폴더가 없음
4. 약관 `[ ]` 채우기 → 개인정보처리방침 작성
5. 첫 영상 2편 유튜브 수동 업로드 후 반응 확인

## 다음 할 일 (우선순위 순)
1. **두 영상 수동 업로드** — 통근열차(`261029_1213`), 우주정거장 눈물(`261029_1211`): 렌더·썸네일 완료, 업로드만 남음
2. 레이아웃: **꽉 찬 화면 유지** (2026-10-29 결정 — 레터박스+노란 제목 틀은 양산형·재업로드 채널처럼 보일 위험). 2.5D 움직임 세기 피드백 대기
3. 2~3편 업로드 후 시청 지속률 보고 다음 개선 결정
4. **설치형 배포 준비** — NOTICE(크레딧), 원클릭 실행, 설치 안내서, README·manual 재작성(아직 원작자 글), 개인정보처리방침
5. 보류: 모션그래픽 템플릿, OAuth 읽기 전용 분석, 다크 모드

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
- [x] 2단계 대본·분석 프롬프트 (`scripts/generation.py`, `references/analysis.py`) — A/B 완료: 새 쪽이 분량·정확성 기준을 더 잘 지킴
- [x] 3단계 레퍼런스 (`references/router.py`, `youtube.py`, `files.py`, `audio.py`, `models.py`)
- [x] 4단계 렌더러·제작 라우터·작업 기록·프로젝트·설정 (`production/renderer.py`, `production/router.py`, `production/models.py`, `jobs/*`, `projects/service.py`, `core/settings.py`, `main.py`)
- [x] 5단계 웹 `api.ts`, `types.ts`, 원작자 테스트 전부 재작성(API 195개·웹 14개 통과). 안 쓰던 `/align`, `/pass-next` 삭제. App.tsx·App.test.tsx에 남은 원작자 줄은 괄호·import 이름·테스트 상투구뿐이라 유지
- [x] 6단계 `tools/higgsfield-mcp` 삭제: 앱은 쓰지 않음(Codex/Gemini용 플러그인, 원작자 맥 경로 고정). 앱 안의 Higgsfield 이미지·영상 옵션은 그대로. `tools/dev/start-dev.mjs` 재작성: 윈도우에서 실제로 뜨게(이전엔 경로 비교 버그로 아무것도 안 켜짐), `--reload` 제거, pnpm 없어도 npm으로 웹 실행
