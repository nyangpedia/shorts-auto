# 작업 인수인계 (free-api-migration 브랜치)

## 목표
원본 shorts-auto(원작자 nam_ai_ai가 "조건 없이 무료" 공개)를 유료 API 없이 돌아가게 바꾸는 중. GPU 없는 PC 기준.

## 현재 무료 구성 (2026-10-23, 끝까지 영상 생성 성공)
| 단계 | 사용 | 비고 |
|---|---|---|
| 자막/STT | Faster-Whisper (CPU, base) | `av<18` 고정 필수 (1.2.1이 PyAV 18+와 충돌) |
| 대본/분석 | Gemini `gemini-3.5-flash` (OpenAI 호환 URL) | 3.8-flash는 100초+로 너무 느림, 2.5-flash는 신규 사용자 불가 |
| 음성 | Gemini TTS `gemini-3.8-flash-tts`, 음성 Kore | edge / qwen3도 선택 가능 (`TTS_PROVIDER`) |
| 이미지/영상 | 씬 모델 `stock`(Pixabay, Pexels 폴백) + `kenburns`(ffmpeg 줌) | Pexels는 신규 키 발급 중단 상태 |
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
`.env`는 git에 없음 → `.env.example` 참고해 다시 만들기 (GEMINI_API_KEY, PIXABAY_API_KEY, LLM_BASE_URL, OPENAI_ANALYSIS_MODEL=gemini-3.5-flash).

## 실행 (uv 없이)
- 백엔드: `apps/api`에서 `.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- 화면: 루트에서 `npx -y pnpm@9 dev:web` → http://127.0.0.1:5173
- 전체 자동 점검: `tools/dev/e2e_smoke.py <레퍼런스 음성.wav>` (서버 켠 상태에서)

## 남은 일
- 첫 영상 품질 검토 → 스톡 검색어를 LLM이 만들게 할지 결정
- 장르 프리셋 (정보/썰/뉴스/명언)
- 렌더링 6분 단축 검토
- Windows 전용 테스트 실패 3개(`/tmp/...` 경로)는 원래 있던 문제
- 원작자에게 LICENSE 파일 추가 요청
