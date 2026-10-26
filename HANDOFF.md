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
- 전체 자동 점검: `tools/dev/e2e_smoke.py <레퍼런스 음성.wav>` (서버 켠 상태에서, Gemini 한도 5~6회 소모)
- 테스트 프로젝트: `outputs/261023_1711`(피라미드, 웹툰 화풍). `outputs/261026_1249`는 **사용자 작업용이라 건드리지 말 것**

## 다음 할 일 (우선순위 순)
1. **이미지 잘림 조정** — 사용자가 2026-10-26 영상에서 "일부 이미지가 화면을 벗어남" 지적.
   원인: 정사각형(1024²) → 9:16 크롭으로 양옆 44% 손실 + kenburns 줌(1.12~1.15)·좌우 이동이 더 잘라냄.
   후보: (a) 줌·이동 폭 축소, (b) 이미지 프롬프트에 "주요 피사체 중앙, 여백 있게" 추가,
   (c) 잘리지 않게 전체를 넣고 위아래를 흐린 같은 이미지로 채우기. a+b가 가장 작은 수정. 테스트 프로젝트로 비교 후 결정
2. **채널 주제 확정** (사용자 결정 대기). 주제가 흩어지면 기능만 늘어남
3. **대본 직접 편집 기능** — 지금은 AI 피드백 재작성만 가능(`FinalScriptPanel.tsx`). 확정 대본을 직접 고치고 저장,
   바뀌면 음성·씬 재생성 필요 표시. **AI 대본이 소수설을 정설처럼 단정**함(예: 피라미드 고대 콘크리트설) → 사람 검수 필수
4. 2~3편 실제 업로드 → 시청 지속률/스와이프율 보고 다음 개선 결정 (캐릭터·유료 훅 영상·업로드 자동화는 그 뒤)

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
