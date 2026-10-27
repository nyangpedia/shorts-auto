import { useEffect, useState } from "react";

import {
  addDirectReference,
  createProject,
  extractReferenceAudio,
  factCheckScript,
  fetchUsage,
  fetchProductionState,
  fetchProjects,
  fetchReferenceState,
  fetchScriptsState,
  finalizeScript,
  generateAllSceneImages,
  generateConcepts,
  generateSceneImage,
  generateSceneVideo,
  generateScriptCandidates,
  generateTtsAudio,
  getProject,
  regenerateSceneWithFeedback,
  renderShorts,
  runReferenceAnalysis,
  runReferenceStt,
  searchReferences,
  selectReference,
  selectScriptCandidate,
  updateFinalScript,
  updateProject,
  updateScenePrompts,
  type UsageToday
} from "./api";
import { AnalysisStep } from "./components/AnalysisStep";
import { FinalStep } from "./components/FinalStep";
import { ReferenceStep } from "./components/ReferenceStep";
import { ScenesStep } from "./components/ScenesStep";
import { ScriptStep } from "./components/ScriptStep";
import { VoiceStep } from "./components/VoiceStep";
import type { ProductionState, Project, ReferenceSearchPayload, ReferenceState, ScriptsState, StepName } from "./types";
import { STEPS, reachedStep, type StepNumber } from "./wizard";

export const APP_NAME = "쇼츠공방";

type Area = "reference" | "analysis" | "script" | "production";

const STEP_KO: Record<StepName, string> = {
  Reference: "레퍼런스",
  STT: "분석",
  Analysis: "분석",
  Candidates: "대본",
  Script: "대본",
  Production: "제작",
  Render: "완성"
};

const errorText = (reason: unknown, fallback: string) => (reason instanceof Error ? reason.message : fallback);

export default function App() {
  const [projects, setProjects] = useState<readonly Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [reference, setReference] = useState<ReferenceState | null>(null);
  const [scripts, setScripts] = useState<ScriptsState | null>(null);
  const [production, setProduction] = useState<ProductionState | null>(null);
  const [viewStep, setViewStep] = useState<StepNumber>(1);
  const [busy, setBusy] = useState<{ area: Area; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  const [usageToday, setUsageToday] = useState<UsageToday | null>(null);

  const refreshUsage = () => void fetchUsage().then(setUsageToday).catch(() => undefined);
  useEffect(refreshUsage, []);

  const projectId = project?.project_id ?? null;
  const reached = reachedStep(reference, scripts, production);

  useEffect(() => {
    fetchProjects()
      .then((loaded) => {
        setProjects(loaded);
        const wanted = new URLSearchParams(window.location.search).get("project");
        setProject((current) => current ?? loaded.find((p) => p.project_id === wanted) ?? loaded[0] ?? null);
      })
      .catch((reason) => setError(errorText(reason, "프로젝트를 불러오지 못했습니다. 백엔드 서버가 켜져 있는지 확인하세요.")))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (!projectId) {
      setReference(null);
      setScripts(null);
      setProduction(null);
      return;
    }
    let active = true;
    Promise.all([fetchReferenceState(projectId), fetchScriptsState(projectId), fetchProductionState(projectId)])
      .then(([ref, scr, prod]) => {
        if (!active) return;
        setReference(ref);
        setScripts(scr);
        setProduction(prod);
        const reachable = reachedStep(ref, scr, prod);
        const asked = Number(new URLSearchParams(window.location.search).get("step"));
        setViewStep((asked >= 1 && asked <= reachable ? asked : reachable) as StepNumber);
        setError(null);
      })
      .catch((reason) => active && setError(errorText(reason, "프로젝트 상태를 불러오지 못했습니다.")));
    return () => {
      active = false;
    };
  }, [projectId]);

  function storeProject(updated: Project) {
    setProject(updated);
    setProjects((list) => list.map((item) => (item.project_id === updated.project_id ? updated : item)));
  }

  /** Runs one long action with a single busy lock, then refreshes the project record. */
  async function run(area: Area, text: string, action: (id: string) => Promise<void>): Promise<boolean> {
    if (!projectId || busy) return false;
    setBusy({ area, text });
    try {
      await action(projectId);
      storeProject(await getProject(projectId));
      setError(null);
      return true;
    } catch (reason) {
      setError(errorText(reason, "작업에 실패했습니다."));
      return false;
    } finally {
      setBusy(null);
      refreshUsage();
    }
  }

  const loadReference = async (id: string) => setReference(await fetchReferenceState(id));
  const loadScripts = async (id: string) => setScripts(await fetchScriptsState(id));
  const loadProduction = async (id: string) => setProduction(await fetchProductionState(id));

  // ── project ──
  async function handleCreateProject() {
    try {
      const created = await createProject("untitled");
      setProjects((list) => [created, ...list]);
      setProject(created);
      setTitleDraft("");
      setError(null);
    } catch (reason) {
      setError(errorText(reason, "프로젝트를 만들지 못했습니다."));
    }
  }

  function handleSelectProject(next: Project) {
    setTitleDraft(null);
    setProject(next);
  }

  async function handleSaveTitle() {
    if (!project || titleDraft === null) return;
    const title = titleDraft.trim() || "untitled";
    setTitleDraft(null);
    try {
      storeProject(await updateProject(project.project_id, { project_title: title }));
    } catch (reason) {
      setError(errorText(reason, "제목을 바꾸지 못했습니다."));
    }
  }

  // ── 1 reference ──
  const handleSearch = (payload: ReferenceSearchPayload) =>
    void run("reference", "쇼츠 검색 중…", async (id) => {
      await searchReferences(id, payload);
      await loadReference(id);
    });
  const handleSelectReference = (videoId: string) =>
    void run("reference", "선택 중…", async (id) => {
      await selectReference(id, videoId);
      await Promise.all([loadReference(id), loadScripts(id), loadProduction(id)]);
    });
  const handleAddDirect = (url: string) =>
    void run("reference", "링크 확인 중…", async (id) => {
      const result = await addDirectReference(id, url);
      if (result.candidate?.video_id) await selectReference(id, result.candidate.video_id);
      await Promise.all([loadReference(id), loadScripts(id), loadProduction(id)]);
    });

  // ── 2 analysis ──
  async function handleRunAnalysis() {
    if (!project) return;
    const needsAudio = !project.generated_files?.reference_audio;
    const needsStt = needsAudio || !reference?.reference_script;
    const ok = await run("analysis", needsAudio ? "음원 내려받는 중…" : "분석 준비 중…", async (id) => {
      if (needsAudio) await extractReferenceAudio(id);
      if (needsStt) {
        setBusy({ area: "analysis", text: "자막으로 변환 중… (로컬 Whisper)" });
        await runReferenceStt(id);
      }
      setBusy({ area: "analysis", text: "성공 공식 분석 중… (Gemini, 30초 정도)" });
      await runReferenceAnalysis(id);
      await loadReference(id);
    });
    if (ok) setViewStep(2);
  }

  async function handleGenerateDrafts(feedback: string) {
    const ok = await run("script", "대본 초안 2개 만드는 중… (30초 정도)", async (id) => {
      await generateScriptCandidates(id, feedback || undefined);
      await loadScripts(id);
    });
    if (ok) setViewStep(3);
  }

  // ── 3 script ──
  const handleSelectCandidate = (candidateId: string) =>
    void run("script", "초안 선택 중…", async (id) => {
      await selectScriptCandidate(id, candidateId);
      await loadScripts(id);
    });
  const handleFinalize = (feedback: string) =>
    void run("script", "대본 확정 중… (낭독용으로 다듬고 씬도 미리 구성합니다)", async (id) => {
      await finalizeScript(id, feedback);
      await Promise.all([loadScripts(id), loadProduction(id)]);
    });
  const handleSaveScript = (text: string) =>
    void run("script", "저장 중…", async (id) => setScripts(await updateFinalScript(id, text)));
  const handleFactCheck = () =>
    void run("script", "AI가 대본의 사실 주장을 하나씩 확인하는 중…", async (id) => setScripts(await factCheckScript(id)));

  // ── 4 voice / style ──
  const handleGenerateVoice = () =>
    void run("production", "음성 만들고 자막 타이밍 맞추는 중… (1분 정도)", async (id) => setProduction(await generateTtsAudio(id)));
  async function handleBuildScenes(style: string) {
    const ok = await run("production", "화풍에 맞춰 씬 구성 중… (Gemini)", async (id) => setProduction(await generateConcepts(id, style)));
    if (ok) setViewStep(5);
  }

  // ── 5 scenes (per-scene work runs in parallel, outside the global lock) ──
  async function sceneTask(task: (id: string) => Promise<unknown>) {
    if (!projectId) return;
    try {
      await task(projectId);
      setError(null);
    } catch (reason) {
      setError(errorText(reason, "씬 작업에 실패했습니다."));
    } finally {
      await loadProduction(projectId).catch(() => undefined);
      refreshUsage();
    }
  }

  // ── 6 final ──
  const handleRender = (title: string) =>
    void run("production", "렌더링 중… 5분 정도 걸립니다. 창을 닫지 마세요.", async (id) => setProduction(await renderShorts(id, title || undefined)));
  async function handleTitleChange(title: string) {
    if (!project) return;
    try {
      storeProject(await updateProject(project.project_id, { project_title: title.trim() || "untitled" }));
    } catch {
      // keep the typed value; the next render request sends it anyway
    }
  }

  const busyFor = (area: Area) => (busy?.area === area ? busy.text : null);
  const scenes = production?.video_scenes ?? [];
  const info = [
    reference?.selected_reference ? `선택: ${reference.selected_reference.title}` : "참고할 쇼츠를 하나 고르세요",
    reference?.analysis ? "주제를 고르고 대본 초안을 만드세요" : "분석을 시작하세요",
    scripts?.final_script
      ? scripts.fact_check
        ? `사실 확인 필요 ${scripts.fact_check.claims.filter((c) => c.verdict !== "확실").length}곳`
        : "대본을 다듬고 AI 사실 확인을 돌려보세요"
      : "초안을 고르고 확정하세요",
    production?.has_audio ? (scenes.length ? `씬 ${scenes.length}개 구성됨` : "화풍을 고르고 씬을 구성하세요") : "음성을 만드세요",
    `이미지 ${scenes.filter((s) => s.start_image_url).length}/${scenes.length} · 영상 ${scenes.filter((s) => s.generated_video_url).length}/${scenes.length}`,
    production?.has_final_video ? "렌더링 완료 · 업로드 전 확인을 체크하세요" : "렌더링하세요"
  ][viewStep - 1];

  return (
    <div className="app">
      <aside className="rail" aria-label="프로젝트">
        <div className="brand">
          <span aria-hidden="true" className="brand-mark">▶</span>
          <span>{APP_NAME}<small>쇼츠 제작 도구</small></span>
        </div>
        <button className="new-project" onClick={handleCreateProject} type="button">+ 새 프로젝트</button>
        <div className="rail-label">프로젝트</div>
        <div className="proj-list">
          {projects.length === 0 && !isLoading ? <p className="rail-empty">아직 프로젝트가 없습니다.</p> : null}
          {projects.map((item) => (
            <button
              aria-current={item.project_id === projectId ? "page" : undefined}
              className="proj"
              key={item.project_id}
              onClick={() => handleSelectProject(item)}
              type="button"
            >
              <img
                alt=""
                className="proj-thumb"
                onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                src={`/api/projects/${encodeURIComponent(item.project_id)}/production/scenes/scene_01_start.png`}
              />
              <span>
                <b>{item.project_title === "untitled" ? item.display_name : item.project_title}</b>
                <small>{STEP_KO[item.current_step] ?? item.current_step}</small>
              </span>
            </button>
          ))}
        </div>
        {usageToday ? <UsageMeter usage={usageToday} /> : null}
      </aside>

      <section className="main">
        {project ? (
          <>
            <header className="top">
              <div className="titlerow">
                {titleDraft === null ? (
                  <>
                    <h1>{project.project_title === "untitled" ? "제목 없음" : project.project_title}</h1>
                    <button className="link-btn" onClick={() => setTitleDraft(project.project_title === "untitled" ? "" : project.project_title)} type="button">✎ 제목 수정</button>
                  </>
                ) : (
                  <form className="title-edit" onSubmit={(e) => { e.preventDefault(); void handleSaveTitle(); }}>
                    <input
                      aria-label="프로젝트 제목"
                      autoFocus
                      className="input"
                      onChange={(e) => setTitleDraft(e.target.value)}
                      onKeyDown={(e) => e.key === "Escape" && setTitleDraft(null)}
                      placeholder="프로젝트 제목"
                      value={titleDraft}
                    />
                    <button className="btn primary" type="submit">저장</button>
                    <button className="btn" onClick={() => setTitleDraft(null)} type="button">취소</button>
                  </form>
                )}
                <div className="meta">{project.display_name}</div>
              </div>
              <nav aria-label="제작 단계" className="stepper">
                {STEPS.map((step, i) => {
                  const n = (i + 1) as StepNumber;
                  const state = n === viewStep ? "current" : n < reached ? "done" : "";
                  return (
                    <button
                      aria-current={n === viewStep ? "step" : undefined}
                      className={`step ${state}`}
                      disabled={n > reached}
                      key={step.title}
                      onClick={() => setViewStep(n)}
                      type="button"
                    >
                      <span className="step-n">{n < reached && n !== viewStep ? "✓" : n}</span>
                      <span><b>{step.title}</b><small>{step.sub}</small></span>
                    </button>
                  );
                })}
              </nav>
            </header>

            <div className="body">
              {error ? (
                <div className="banner bad" role="alert">
                  ⚠️ {error} <button className="link-btn" onClick={() => setError(null)} type="button">닫기</button>
                </div>
              ) : null}

              {viewStep === 1 && (
                <ReferenceStep
                  candidates={reference?.candidates ?? []}
                  isBusy={busy !== null}
                  onAddDirect={handleAddDirect}
                  onSearch={handleSearch}
                  onSelect={handleSelectReference}
                  selectedReference={reference?.selected_reference ?? null}
                />
              )}
              {viewStep === 2 && (
                <AnalysisStep
                  analysis={reference?.analysis ?? null}
                  busyText={busyFor("analysis") ?? busyFor("script")}
                  isBusy={busy !== null}
                  isScriptBusy={busy !== null}
                  onGenerateDrafts={handleGenerateDrafts}
                  onRunAnalysis={handleRunAnalysis}
                  referenceScript={reference?.reference_script ?? null}
                />
              )}
              {viewStep === 3 && (
                <ScriptStep
                  busyText={busyFor("script")}
                  candidates={scripts?.candidates ?? []}
                  factCheck={scripts?.fact_check ?? null}
                  finalScript={scripts?.final_script ?? null}
                  isBusy={busy !== null}
                  onFactCheck={handleFactCheck}
                  onFinalize={handleFinalize}
                  onSave={handleSaveScript}
                  onSelect={handleSelectCandidate}
                  selectedCandidateId={scripts?.selected_candidate?.candidate_id ?? null}
                  ttsValidation={scripts?.tts_validation ?? null}
                />
              )}
              {viewStep === 4 && (
                <VoiceStep
                  audioUrl={production?.has_audio ? `/api/projects/${encodeURIComponent(project.project_id)}/production/audio` : null}
                  busyText={busyFor("production")}
                  conceptKit={production?.concept_kit ?? null}
                  durationSeconds={production?.duration_seconds ?? null}
                  isBusy={busy !== null}
                  onBuildScenes={handleBuildScenes}
                  onGenerateVoice={handleGenerateVoice}
                  sceneCount={scenes.length}
                />
              )}
              {viewStep === 5 && (
                <ScenesStep
                  isBusy={busy !== null}
                  onGenerateAllImages={(model) => sceneTask((id) => generateAllSceneImages(id, model))}
                  onGenerateImage={(sceneId, model) => sceneTask((id) => generateSceneImage(id, sceneId, model))}
                  onGenerateVideo={(sceneId, model) => sceneTask((id) => generateSceneVideo(id, sceneId, model, 5, false, false))}
                  onRegenerate={(sceneId, feedback, target, model) =>
                    sceneTask((id) => regenerateSceneWithFeedback(id, sceneId, feedback, target, model, 5, false, false))
                  }
                  onUpdatePrompts={(sceneId, img, vid) => sceneTask((id) => updateScenePrompts(id, sceneId, img, vid))}
                  scenes={scenes}
                />
              )}
              {viewStep === 6 && (
                <FinalStep
                  busyText={busyFor("production")}
                  candidate={scripts?.selected_candidate ?? null}
                  finalVideoUrl={production?.has_final_video ? production.final_video_url ?? `/api/projects/${encodeURIComponent(project.project_id)}/production/final-video` : null}
                  isBusy={busy !== null}
                  onRender={handleRender}
                  onTitleChange={handleTitleChange}
                  projectId={project.project_id}
                  scenesReady={scenes.length > 0 && scenes.every((s) => s.start_image_url)}
                  videoTitle={project.project_title === "untitled" ? "" : project.project_title}
                />
              )}
            </div>

            <footer className="actionbar">
              <span className="info">{busy ? `⏳ ${busy.text}` : info}</span>
              {viewStep > 1 && (
                <button className="btn" onClick={() => setViewStep((viewStep - 1) as StepNumber)} type="button">이전</button>
              )}
              {viewStep < 6 && (
                <button className="btn accent" disabled={viewStep >= reached} onClick={() => setViewStep((viewStep + 1) as StepNumber)} type="button">
                  다음: {STEPS[viewStep]?.title} →
                </button>
              )}
            </footer>
          </>
        ) : (
          <div className="welcome">
            <h1>{APP_NAME}</h1>
            <p className="muted">잘 터진 쇼츠의 공식을 분석해 내 쇼츠를 만듭니다.</p>
            {error ? <div className="banner bad">{error}</div> : null}
            <button className="btn accent" onClick={handleCreateProject} type="button">+ 새 프로젝트 시작</button>
          </div>
        )}
      </section>
    </div>
  );
}

function UsageMeter({ usage }: { readonly usage: UsageToday }) {
  const rows = [
    ["대본 AI (Gemini)", usage.llm, usage.llm_limit],
    ["이미지 (Cloudflare)", usage.image, usage.image_limit]
  ] as const;
  return (
    <div className="quota" title="앱이 직접 센 추정치입니다. Gemini는 미국 서부 자정, Cloudflare는 UTC 자정에 초기화됩니다.">
      <div>오늘 무료 사용량 (추정)</div>
      {rows.map(([label, used, limit]) => (
        <div className="quota-row" key={label}>
          <div>{label}<span style={{ float: "right" }}>{limit ? `${used} / ${limit}` : used}</span></div>
          {limit ? (
            <div className="meter"><i className={used / limit > 0.85 ? "low" : ""} style={{ width: `${Math.min(100, (used / limit) * 100)}%` }} /></div>
          ) : null}
        </div>
      ))}
      <div>음성 (Gemini TTS) <span style={{ float: "right" }}>{usage.tts}회</span></div>
    </div>
  );
}
