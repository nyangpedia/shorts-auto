import { useEffect, useRef, useState } from "react";

import {
  addDirectReference,
  createProject,
  deleteProject,
  extractReferenceAudio,
  factCheckScript,
  fetchDaily,
  fetchKeyStatus,
  fetchTopics,
  hideTopics,
  restoreTopics,
  fetchUsage,
  refreshDaily,
  saveDailyKeywords,
  startTopic,
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
  searchReferencesWithoutProject,
  selectReference,
  selectScriptCandidate,
  updateFinalScript,
  updateProject,
  updateScenePrompts,
  type DailyItem,
  type DailyState,
  type TopicItem,
  type UsageToday
} from "./api";
import { AnalysisStep } from "./components/AnalysisStep";
import { DailyView } from "./components/DailyView";
import { TopicsView } from "./components/TopicsView";
import { FinalStep } from "./components/FinalStep";
import { HomeView } from "./components/HomeView";
import { SettingsView } from "./components/SettingsView";
import { ReferenceStep } from "./components/ReferenceStep";
import { ScenesStep } from "./components/ScenesStep";
import { ScriptStep } from "./components/ScriptStep";
import { VoiceStep } from "./components/VoiceStep";
import type { ProductionState, Project, ReferenceCandidate, ReferenceSearchPayload, ReferenceState, ScriptsState, StepName } from "./types";
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

const STEP_ICON: Record<string, string> = { 레퍼런스: "🔍", 분석: "🧪", 대본: "✍️", 제작: "🎨", 완성: "✅" };

const GLOBAL = "_global";

const errorText = (reason: unknown, fallback: string) => (reason instanceof Error ? reason.message : fallback);

export default function App() {
  const [projects, setProjects] = useState<readonly Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [reference, setReference] = useState<ReferenceState | null>(null);
  const [scripts, setScripts] = useState<ScriptsState | null>(null);
  const [production, setProduction] = useState<ProductionState | null>(null);
  const [viewStep, setViewStep] = useState<StepNumber>(1);
  // One lock per project (plus GLOBAL for work that isn't inside a project yet), so rendering one
  // project doesn't freeze another.
  const [busyMap, setBusyMap] = useState<Readonly<Record<string, { area: Area; text: string }>>>({});
  const setBusyFor = (key: string, value: { area: Area; text: string } | null) =>
    setBusyMap((m) => {
      const next = { ...m };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  const [usageToday, setUsageToday] = useState<UsageToday | null>(null);
  // Read the opening URL once; it is cleared after load so a refresh lands on home.
  const linkParams = useRef(new URLSearchParams(window.location.search)).current;
  const [view, setView] = useState<"home" | "find" | "project" | "topics" | "daily" | "settings">(() => {
    const params = linkParams;
    const asked = params.get("view");
    if (asked === "topics" || asked === "daily" || asked === "settings") return asked;
    return params.get("project") ? "project" : "home";
  });
  const [topics, setTopics] = useState<readonly TopicItem[]>([]);
  const [hiddenTopics, setHiddenTopics] = useState<readonly TopicItem[]>([]);
  const [findCandidates, setFindCandidates] = useState<readonly ReferenceCandidate[]>([]);
  const [daily, setDaily] = useState<DailyState | null>(null);

  const refreshUsage = () => void fetchUsage().then(setUsageToday).catch(() => undefined);
  const [missingKeys, setMissingKeys] = useState(0);
  const REQUIRED_KEYS = ["GEMINI_API_KEY", "YOUTUBE_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"];
  const refreshKeys = () =>
    void Promise.resolve(fetchKeyStatus())
      .then((r) => setMissingKeys(REQUIRED_KEYS.filter((k) => !r?.keys[k]).length))
      .catch(() => undefined);
  useEffect(refreshKeys, []);
  useEffect(refreshUsage, []);
  const loadTopics = () => void fetchTopics().then((r) => { setTopics(r.topics); setHiddenTopics(r.hidden ?? []); }).catch(() => undefined);
  useEffect(loadTopics, []);
  useEffect(() => {
    if (view === "daily" && !daily) void fetchDaily().then(setDaily).catch((reason) => setError(errorText(reason, "오늘의 레퍼런스를 불러오지 못했습니다.")));
    if (view === "topics") loadTopics();
  }, [view]);

  const projectId = project?.project_id ?? null;
  const reached = reachedStep(reference, scripts, production);
  // Results of a long task land only if its project is still on screen (the user may have moved on).
  const currentIdRef = useRef(projectId);
  currentIdRef.current = projectId;
  const onScreen = (id: string) => currentIdRef.current === id;
  const busy = (view === "project" && projectId ? busyMap[projectId] : undefined) ?? busyMap[GLOBAL] ?? null;

  useEffect(() => {
    fetchProjects()
      .then((loaded) => {
        setProjects(loaded);
        const wanted = linkParams.get("project");
        setProject((current) => current ?? loaded.find((p) => p.project_id === wanted) ?? loaded[0] ?? null);
        // Deep links are one-shot: a refresh should land on the home screen, not reopen the linked project.
        if (window.location.search) window.history.replaceState(null, "", window.location.pathname);
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
        const asked = linkParams.get("project") === projectId ? Number(linkParams.get("step")) : 0;
        setViewStep((asked >= 1 && asked <= reachable ? asked : reachable) as StepNumber);
        setError(null);
      })
      .catch((reason) => active && setError(errorText(reason, "프로젝트 상태를 불러오지 못했습니다.")));
    return () => {
      active = false;
    };
  }, [projectId]);

  function storeProject(updated: Project) {
    setProject((current) => (current?.project_id === updated.project_id ? updated : current));
    setProjects((list) => list.map((item) => (item.project_id === updated.project_id ? updated : item)));
  }

  /**
   * Runs one long action under this project's lock, then refreshes the project record.
   * Returns true only if it succeeded and the project is still the one on screen.
   */
  async function run(area: Area, text: string, action: (id: string) => Promise<void>): Promise<boolean> {
    const id = projectId;
    if (!id || busyMap[id]) return false;
    setBusyFor(id, { area, text });
    try {
      await action(id);
      storeProject(await getProject(id));
      if (onScreen(id)) setError(null);
      return onScreen(id);
    } catch (reason) {
      setError(errorText(reason, "작업에 실패했습니다."));
      return false;
    } finally {
      setBusyFor(id, null);
      refreshUsage();
    }
  }

  const loadReference = async (id: string) => { const r = await fetchReferenceState(id); if (onScreen(id)) setReference(r); };
  const loadScripts = async (id: string) => { const r = await fetchScriptsState(id); if (onScreen(id)) setScripts(r); };
  const loadProduction = async (id: string) => { const r = await fetchProductionState(id); if (onScreen(id)) setProduction(r); };
  const showScripts = (id: string, value: ScriptsState) => { if (onScreen(id)) setScripts(value); };
  const showProduction = (id: string, value: ProductionState) => { if (onScreen(id)) setProduction(value); };

  // ── project ──
  // "새 프로젝트" opens the finder; the project itself is created only when a video is picked,
  // so browsing never leaves empty "untitled" projects behind.
  const startNewProject = () => setView("find");

  async function handleFindSearch(payload: ReferenceSearchPayload) {
    if (busyMap[GLOBAL]) return;
    setBusyFor(GLOBAL, { area: "reference", text: "쇼츠 검색 중… (처음 검색은 1분 정도)" });
    try {
      setFindCandidates((await searchReferencesWithoutProject(payload)).candidates);
      setError(null);
    } catch (reason) {
      setError(errorText(reason, "검색하지 못했습니다."));
    } finally {
      setBusyFor(GLOBAL, null);
      refreshUsage();
    }
  }

  async function handleArchive(archived: boolean) {
    if (!project) return;
    try {
      storeProject(await updateProject(project.project_id, { archived }));
    } catch (reason) {
      setError(errorText(reason, "보관하지 못했습니다."));
    }
  }

  async function handleDelete() {
    if (!project || busyMap[project.project_id]) return;
    if (!window.confirm(`"${project.display_name}" 프로젝트를 삭제할까요? 영상·이미지·대본 파일이 모두 지워지고 되돌릴 수 없습니다.`)) return;
    try {
      await deleteProject(project.project_id);
      const rest = projects.filter((p) => p.project_id !== project.project_id);
      setProjects(rest);
      setProject(rest[0] ?? null);
      loadTopics();
    } catch (reason) {
      setError(errorText(reason, "삭제하지 못했습니다."));
    }
  }

  function handleSelectProject(next: Project) {
    setTitleDraft(null);
    setView("project");
    setProject(next);
  }

  function openProjectById(id: string) {
    const found = projects.find((p) => p.project_id === id);
    if (found) handleSelectProject(found);
  }

  /** Long actions that start from the topics/daily views (no project selected yet). */
  async function runGlobal(text: string, action: () => Promise<Project>) {
    if (busyMap[GLOBAL]) return;
    setBusyFor(GLOBAL, { area: "reference", text });
    try {
      const created = await action();
      setProjects((list) => [created, ...list.filter((p) => p.project_id !== created.project_id)]);
      handleSelectProject(created);
      setError(null);
    } catch (reason) {
      setError(errorText(reason, "작업에 실패했습니다."));
    } finally {
      setBusyFor(GLOBAL, null);
      refreshUsage();
      loadTopics();
    }
  }

  const handleStartTopic = (topic: TopicItem) =>
    void runGlobal("주제로 새 프로젝트를 만들고 대본 초안 2개를 쓰는 중… (30초 정도)", async () => {
      const started = await startTopic(topic);
      await generateScriptCandidates(started.project.project_id, started.feedback);
      return getProject(started.project.project_id);
    });

  async function handleHideTopics(ids: readonly string[], restore = false) {
    try {
      const listing = await (restore ? restoreTopics(ids) : hideTopics(ids));
      setTopics(listing.topics);
      setHiddenTopics(listing.hidden ?? []);
    } catch (reason) {
      setError(errorText(reason, restore ? "주제를 되살리지 못했습니다." : "주제를 지우지 못했습니다."));
    }
  }

  /** The one place a project is born from a video: finder, daily references, or a pasted link. */
  const startFromVideo = (url: string, onCreated?: (projectId: string) => void) =>
    void runGlobal("이 쇼츠로 새 프로젝트를 만드는 중…", async () => {
      // Project title doubles as the 0–2s opening title on render; never inherit someone else's video title.
      const created = await createProject("untitled");
      const added = await addDirectReference(created.project_id, url);
      await selectReference(created.project_id, added.candidate.video_id);
      onCreated?.(created.project_id);
      return getProject(created.project_id);
    });

  const handleUseDaily = (item: DailyItem) =>
    startFromVideo(item.url, (createdId) =>
      setDaily((d) => (d ? { ...d, items: d.items.map((i) => (i.video_id === item.video_id ? { ...i, used_by: createdId } : i)) } : d))
    );

  async function handleDaily(action: () => Promise<DailyState>, text: string) {
    if (busyMap[GLOBAL]) return;
    setBusyFor(GLOBAL, { area: "reference", text });
    try {
      setDaily(await action());
      setError(null);
    } catch (reason) {
      setError(errorText(reason, "오늘의 레퍼런스 작업에 실패했습니다."));
    } finally {
      setBusyFor(GLOBAL, null);
    }
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
        setBusyFor(id, { area: "analysis", text: "자막으로 변환 중… (로컬 Whisper)" });
        await runReferenceStt(id);
      }
      setBusyFor(id, { area: "analysis", text: "성공 공식 분석 중… (Gemini, 30초 정도)" });
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
    void run("script", "저장 중…", async (id) => showScripts(id, await updateFinalScript(id, text)));
  const handleFactCheck = () =>
    void run("script", "AI가 대본의 사실 주장을 하나씩 확인하는 중…", async (id) => showScripts(id, await factCheckScript(id)));

  // ── 4 voice / style ──
  const handleGenerateVoice = () =>
    void run("production", "음성 만들고 자막 타이밍 맞추는 중… (1분 정도)", async (id) => showProduction(id, await generateTtsAudio(id)));
  async function handleBuildScenes(style: string) {
    const ok = await run("production", "화풍에 맞춰 씬 구성 중… (Gemini)", async (id) => showProduction(id, await generateConcepts(id, style)));
    if (ok) setViewStep(5);
  }

  // ── 5 scenes (per-scene work runs in parallel, outside the global lock) ──
  async function sceneTask(task: (id: string) => Promise<unknown>) {
    const id = projectId;
    if (!id) return;
    try {
      await task(id);
      if (onScreen(id)) setError(null);
    } catch (reason) {
      setError(errorText(reason, "씬 작업에 실패했습니다."));
    } finally {
      await loadProduction(id).catch(() => undefined);
      refreshUsage();
    }
  }

  // ── 6 final ──
  const handleRender = (title: string) =>
    void run("production", "렌더링 중… 5분 정도 걸립니다. 창을 닫지 마세요.", async (id) => showProduction(id, await renderShorts(id, title || undefined)));
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

  // Rendered or archived projects move into a collapsed box so the rail only lists work in progress.
  const isShelved = (p: Project) => Boolean(p.archived || p.generated_files.final_video);
  const doneProjects = projects.filter(isShelved);
  const activeProjects = projects.filter((p) => !isShelved(p));

  // Thumbnail = first scene image; until one exists, an icon shows how far the project got.
  const railProject = (item: Project) => {
    const step = item.generated_files.final_video ? "완성" : STEP_KO[item.current_step] ?? item.current_step;
    return (
      <button
        aria-current={view === "project" && item.project_id === projectId ? "page" : undefined}
        className="proj"
        key={item.project_id}
        onClick={() => handleSelectProject(item)}
        type="button"
      >
        <span aria-hidden="true" className="proj-thumb" data-icon={STEP_ICON[step] ?? "📄"}>
          <img alt="" onError={(e) => e.currentTarget.remove()} src={`/api/projects/${encodeURIComponent(item.project_id)}/production/scenes/scene_01_start.png`} />
        </span>
        <span>
          <b>{item.project_title === "untitled" ? item.display_name : item.project_title}</b>
          <small>{busyMap[item.project_id] ? `⏳ ${busyMap[item.project_id].text.split("…")[0]}…` : step}</small>
        </span>
      </button>
    );
  };

  return (
    <div className="app">
      <aside className="rail" aria-label="프로젝트">
        <button aria-current={view === "home" ? "page" : undefined} className="brand" onClick={() => setView("home")} type="button">
          <img alt="" className="brand-mark" src="/logo.svg" />
          <span>{APP_NAME}<small>쇼츠 제작 도구</small></span>
        </button>
        <button aria-current={view === "find" ? "page" : undefined} className="new-project" onClick={startNewProject} type="button">+ 새 프로젝트</button>
        <button aria-current={view === "daily" ? "page" : undefined} className="proj rail-link" onClick={() => setView("daily")} type="button">
          <span aria-hidden="true">📌</span><span><b>오늘의 레퍼런스</b></span>
        </button>
        <button aria-current={view === "topics" ? "page" : undefined} className="proj rail-link" onClick={() => setView("topics")} type="button">
          <span aria-hidden="true">🗂</span><span><b>주제 창고</b><small>남은 주제 {topics.filter((t) => !t.used_by).length}개</small></span>
        </button>
        <div className="proj-list">
          {/* Both groups are collapsible sections; their projects hang off a guide line underneath. */}
          <details className="rail-group" open>
            <summary className="rail-section">
              <span aria-hidden="true">🎬</span><b>진행 중인 프로젝트</b><small>{activeProjects.length}</small>
            </summary>
            <div className="rail-children">
              {activeProjects.length === 0 && !isLoading ? <p className="rail-empty">진행 중인 프로젝트가 없습니다.</p> : null}
              {activeProjects.map(railProject)}
            </div>
          </details>
          {doneProjects.length > 0 ? (
            <details className="rail-group">
              <summary className="rail-section">
                <span aria-hidden="true">🗄</span><b>완료·보관함</b><small>{doneProjects.length}</small>
              </summary>
              <div className="rail-children">{doneProjects.map(railProject)}</div>
            </details>
          ) : null}
        </div>
        <button aria-current={view === "settings" ? "page" : undefined} className="proj rail-link rail-settings" onClick={() => setView("settings")} type="button">
          <span aria-hidden="true">⚙</span><span><b>설정</b><small>API 키 · 유튜브 계정</small></span>
        </button>
        {usageToday ? <UsageMeter usage={usageToday} /> : null}
      </aside>

      <section className="main">
        {view !== "project" ? (
          <div className="body">
            {error ? (
              <div className="banner bad" role="alert">⚠️ {error} <button className="link-btn" onClick={() => setError(null)} type="button">닫기</button></div>
            ) : null}
            {view === "find" ? (
              <>
                {busy ? <div className="banner busy">⏳ {busy.text}</div> : null}
                <p className="muted small" style={{ margin: "0 0 12px" }}>쇼츠를 고르거나 링크를 붙여넣으면 그때 새 프로젝트가 만들어집니다.</p>
                <ReferenceStep
                  autoSearch={findCandidates.length === 0}
                  candidates={findCandidates}
                  isBusy={busy !== null}
                  onAddDirect={(url) => startFromVideo(url)}
                  onSearch={(payload) => void handleFindSearch(payload)}
                  onSelect={(videoId) => {
                    const picked = findCandidates.find((c) => c.video_id === videoId);
                    if (picked) startFromVideo(picked.url);
                  }}
                  selectedReference={null}
                />
              </>
            ) : view === "settings" ? (
              <SettingsView onSaved={() => { setError(null); refreshUsage(); refreshKeys(); }} />
            ) : view === "home" ? (
              <HomeView
                missingKeys={missingKeys}
                onGo={setView}
                onNew={startNewProject}
                onOpen={handleSelectProject}
                projects={projects}
                stepLabel={(p) => (p.generated_files.final_video ? "완성" : STEP_KO[p.current_step] ?? p.current_step)}
                topicsLeft={topics.filter((t) => !t.used_by).length}
              />
            ) : view === "topics" ? (
              <TopicsView busyText={busy?.text ?? null} isBusy={busy !== null} hidden={hiddenTopics} onHide={(ids) => void handleHideTopics(ids)} onRestore={(ids) => void handleHideTopics(ids, true)} onOpenProject={openProjectById} onStart={handleStartTopic} topics={topics} />
            ) : (
              <DailyView
                busyText={busy?.text ?? null}
                daily={daily}
                isBusy={busy !== null}
                onOpenProject={openProjectById}
                onRefresh={(force) => void handleDaily(() => refreshDaily(force), "최근 7일 쇼츠 검색 중…")}
                onSaveKeywords={(keywords) => void handleDaily(() => saveDailyKeywords(keywords), "저장 중…")}
                onUse={handleUseDaily}
              />
            )}
          </div>
        ) : project ? (
          <>
            <header className="top">
              <div className="titlerow">
                {titleDraft === null ? (
                  <>
                    <h1>{project.project_title === "untitled" ? "제목 없음" : project.project_title}</h1>
                    <button className="link-btn" onClick={() => setTitleDraft(project.project_title === "untitled" ? "" : project.project_title)} type="button">✎ 제목 수정</button>
                    <button className="link-btn" onClick={() => void handleArchive(!project.archived)} type="button">{project.archived ? "↩ 보관 해제" : "🗄 보관함으로"}</button>
                    <button className="link-btn danger" onClick={() => void handleDelete()} type="button">🗑 삭제</button>
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
                  similarity={scripts?.similarity ?? null}
                  finalScript={scripts?.final_script ?? null}
                  isBusy={busy !== null}
                  onFactCheck={handleFactCheck}
                  onFinalize={handleFinalize}
                  onSave={handleSaveScript}
                  onSelect={handleSelectCandidate}
                  selectedCandidateId={scripts?.selected_candidate?.candidate_id ?? null}
                  ttsValidation={scripts?.tts_validation ?? null}
                  onUseTitle={handleTitleChange}
                  videoTitle={project.project_title}
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
                  busyText={busyFor("production")}
                  isBusy={busy !== null}
                  onChangeStyle={(style) => void handleBuildScenes(style)}
                  styleId={production?.concept_kit?.style_id ?? null}
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
                  onOpenSettings={() => setView("settings")}
                  onRender={handleRender}
                  onTitleChange={handleTitleChange}
                  projectId={project.project_id}
                  scenePictures={scenes.flatMap((s) => (s.start_image_url ? [{ id: s.scene_id, url: s.start_image_url }] : []))}
                  thumbnailUrl={production?.thumbnail_url ?? null}
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
            <button className="btn accent" onClick={startNewProject} type="button">+ 새 프로젝트 시작</button>
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
