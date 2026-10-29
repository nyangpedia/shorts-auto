// Every call to the API in one place. All responses are JSON; a non-2xx reply throws with the API's message.
import type {
  DailyState,
  FinalScriptState,
  KeyStatus,
  ProductionState,
  Project,
  ReferenceCandidate,
  ReferenceSearchPayload,
  ReferenceState,
  ScriptCandidate,
  ScriptsState,
  TopicItem,
  TopicListing,
  UpdateProjectPayload,
  UsageToday,
  YouTubeStatus,
  YouTubeUploadResult
} from "./types";

export type { DailyItem, DailyState, TopicItem, TopicListing, TrendPoint, UsageToday, YouTubeStatus, YouTubeUploadResult } from "./types";

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error((await response.text()) || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const get = <T>(path: string) => call<T>("GET", path);
const post = <T>(path: string, body?: unknown) => call<T>("POST", path, body);
const put = <T>(path: string, body: unknown) => call<T>("PUT", path, body);

/** /api/projects/<id><rest> with the id escaped. */
const p = (projectId: string, rest = "") => `/api/projects/${encodeURIComponent(projectId)}${rest}`;
const qs = (params: Record<string, string | number | boolean | undefined>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");

// ── projects ──
export const fetchProjects = () => get<{ projects: readonly Project[] }>("/api/projects").then((r) => r.projects);
export const getProject = (projectId: string) => get<{ project: Project }>(p(projectId)).then((r) => r.project);
export const createProject = (projectTitle: string) =>
  post<{ project: Project }>("/api/projects", { project_title: projectTitle }).then((r) => r.project);
export const updateProject = (projectId: string, payload: UpdateProjectPayload) =>
  call<{ project: Project }>("PATCH", p(projectId), payload).then((r) => r.project);
export const deleteProject = (projectId: string) => call<unknown>("DELETE", p(projectId));

// ── reference step ──
type Candidates = { candidates: readonly ReferenceCandidate[] };
export const fetchReferenceState = (projectId: string) => get<ReferenceState>(p(projectId, "/reference"));
export const searchReferences = (projectId: string, payload: ReferenceSearchPayload) => post<Candidates>(p(projectId, "/reference/search"), payload);
/** Search without a project: nothing is created until a video is picked. */
export const searchReferencesWithoutProject = (payload: ReferenceSearchPayload) => post<Candidates>("/api/references/search", payload);
export const addDirectReference = (projectId: string, url: string) =>
  post<Candidates & { candidate: ReferenceCandidate }>(p(projectId, "/reference/direct"), { url });
export const selectReference = (projectId: string, videoId: string) =>
  post<{ selected_reference: ReferenceCandidate }>(p(projectId, "/reference/select"), { video_id: videoId });
export const extractReferenceAudio = (projectId: string) => post<{ audio_path: string }>(p(projectId, "/reference/audio/extract"));
export const runReferenceStt = (projectId: string) => post<{ reference_script: string }>(p(projectId, "/reference/stt"));
export const runReferenceAnalysis = (projectId: string) =>
  post<Pick<ReferenceState, "analysis" | "analysis_markdown">>(p(projectId, "/reference/analyze"));

// ── script step ──
export const fetchScriptsState = (projectId: string) => get<ScriptsState>(p(projectId, "/scripts"));
export const generateScriptCandidates = (projectId: string, feedback?: string) =>
  post<{ candidates: readonly ScriptCandidate[] }>(p(projectId, "/scripts/candidates"), { feedback: feedback ?? "" });
export const selectScriptCandidate = (projectId: string, candidateId: string) =>
  post<{ selected_candidate: ScriptCandidate }>(p(projectId, "/scripts/select"), { candidate_id: candidateId });
export const finalizeScript = (projectId: string, feedback: string) => post<FinalScriptState>(p(projectId, "/scripts/finalize"), { feedback });
export const updateFinalScript = (projectId: string, finalScript: string) =>
  put<ScriptsState>(p(projectId, "/scripts/final"), { final_script: finalScript });
export const factCheckScript = (projectId: string) => post<ScriptsState>(p(projectId, "/scripts/factcheck"));

// ── production ──
export const fetchProductionState = (projectId: string) => get<ProductionState>(p(projectId, "/production"));
export const generateTtsAudio = (projectId: string) => post<ProductionState>(p(projectId, "/production/tts"));
export const generateConcepts = (projectId: string, style?: string) =>
  post<ProductionState>(p(projectId, `/production/concepts${style ? `?${qs({ style })}` : ""}`));
export const generateSceneImage = (projectId: string, sceneId: number, model = "cloudflare") =>
  post<ProductionState>(p(projectId, `/production/scenes/${sceneId}/image?${qs({ model })}`));
export const generateAllSceneImages = (projectId: string, model = "cloudflare") =>
  post<ProductionState>(p(projectId, `/production/scenes/images?${qs({ model })}`));
export const generateSceneVideo = (projectId: string, sceneId: number, model = "parallax", duration = 5, multiShots = false, matchPrevFrame = true) =>
  post<ProductionState>(p(projectId, `/production/scenes/${sceneId}/video?${qs({ model, duration, multi_shots: multiShots, match_prev_frame: matchPrevFrame })}`));
export const regenerateSceneWithFeedback = (
  projectId: string,
  sceneId: number,
  feedback: string,
  target: "image" | "video" | "both" | "prompt_image" | "prompt_video",
  model?: string,
  duration = 5,
  multiShots = false,
  matchPrevFrame = true
) =>
  post<ProductionState>(p(projectId, `/production/scenes/${sceneId}/feedback-regenerate`), {
    feedback, target, model, duration, multi_shots: multiShots, match_prev_frame: matchPrevFrame
  });
export const updateScenePrompts = (projectId: string, sceneId: number, startImagePrompt?: string, videoPrompt?: string) =>
  put<ProductionState>(p(projectId, `/production/scenes/${sceneId}/prompts`), { start_image_prompt: startImagePrompt, video_prompt: videoPrompt });
export const makeThumbnail = (projectId: string, sceneId: number, title: string) =>
  post<{ thumbnail_url: string }>(p(projectId, "/production/thumbnail"), { scene_id: sceneId, title });
export const renderShorts = (projectId: string, title?: string) =>
  post<ProductionState>(p(projectId, "/production/render"), title !== undefined ? { title } : {});

// ── side views ──
export const fetchUsage = () => get<UsageToday>("/api/usage");
export const fetchTopics = () => get<TopicListing>("/api/topics");
export const hideTopics = (ids: readonly string[]) => post<TopicListing>("/api/topics/hide", { ids });
export const restoreTopics = (ids: readonly string[]) => post<TopicListing>("/api/topics/restore", { ids });
export const startTopic = (topic: TopicItem) =>
  post<{ project: Project; feedback: string }>(`/api/topics/${encodeURIComponent(topic.source_project_id)}/${topic.id.split(":")[1]}/start`);
export const fetchDaily = () => get<DailyState>("/api/daily-references");
export const saveDailyKeywords = (keywords: readonly string[]) => put<DailyState>("/api/daily-references/keywords", { keywords });
export const refreshDaily = (force = false) => post<DailyState>(`/api/daily-references/refresh${force ? "?force=true" : ""}`);

// ── settings and YouTube ──
export const fetchKeyStatus = () => get<KeyStatus>("/api/settings/keys");
/** Keys go to the server's .env; the reply only says which are set. "" clears one. */
export const saveKeys = (values: Readonly<Record<string, string>>) => put<KeyStatus>("/api/settings/keys", { values });
export const fetchYouTubeStatus = () => get<YouTubeStatus>("/api/youtube/status");
export const fetchYouTubeAuthUrl = () => get<{ auth_url: string }>("/api/youtube/connect");
export const saveClientSecret = (content: string) => put<YouTubeStatus>("/api/youtube/client-secret", { content });
export const disconnectYouTube = () => call<YouTubeStatus>("DELETE", "/api/youtube/connection");
export const uploadToYouTube = (projectId: string, payload: { title: string; description: string; tags: string }) =>
  post<YouTubeUploadResult>(p(projectId, "/youtube/upload"), payload);
