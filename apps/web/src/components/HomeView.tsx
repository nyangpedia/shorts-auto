import type { Project } from "../types";

interface HomeViewProps {
  readonly projects: readonly Project[];
  readonly topicsLeft: number;
  readonly stepLabel: (project: Project) => string;
  readonly onNew: () => void;
  readonly onOpen: (project: Project) => void;
  readonly onGo: (view: "daily" | "topics") => void;
}

// Two a day for the topic experiment (3 topics × 8–10 videos over two weeks).
const WEEKLY_GOAL = 14;
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

const thumb = (p: Project) => `/api/projects/${encodeURIComponent(p.project_id)}/production/scenes/scene_01_start.png`;
const name = (p: Project) => (p.project_title === "untitled" ? p.display_name : p.project_title);

export function HomeView({ projects, topicsLeft, stepLabel, onNew, onOpen, onGo }: HomeViewProps) {
  const now = Date.now();
  const thisWeek = projects.filter((p) => now - Date.parse(p.updated_at) < WEEK_MS);
  const madeThisWeek = thisWeek.filter((p) => p.generated_files.final_video).length;
  const uploadedThisWeek = thisWeek.filter((p) => p.generated_files.youtube_video).length;
  const inProgress = projects
    .filter((p) => !p.archived && !p.generated_files.final_video)
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 6);
  const today = new Date().toLocaleDateString("ko-KR", { month: "long", day: "numeric", weekday: "long" });

  return (
    <div className="stack home">
      <section className="hero">
        <div>
          <span className="hero-date">{today}</span>
          <h2>오늘 만들 쇼츠, 여기서 시작하세요</h2>
          <p>레퍼런스를 고르고 → 분석하고 → 내 대본으로 다시 만듭니다.</p>
        </div>
        <div className="hero-stats">
          <div>
            <b>{madeThisWeek}<small>/{WEEKLY_GOAL}</small></b>
            <span>이번 주 완성</span>
            <i aria-hidden="true" style={{ width: `${Math.min(100, (madeThisWeek / WEEKLY_GOAL) * 100)}%` }} />
          </div>
          <div><b>{uploadedThisWeek}</b><span>이번 주 업로드</span></div>
          <div><b>{topicsLeft}</b><span>남은 주제</span></div>
        </div>
      </section>

      <div className="home-actions">
        <button className="home-action primary" onClick={onNew} type="button">
          <span aria-hidden="true">＋</span><b>새 프로젝트</b><small>마지막 분야로 바로 검색</small>
        </button>
        <button className="home-action" onClick={() => onGo("daily")} type="button">
          <span aria-hidden="true">📌</span><b>오늘의 레퍼런스</b><small>최근 7일 뜨는 쇼츠</small>
        </button>
        <button className="home-action" onClick={() => onGo("topics")} type="button">
          <span aria-hidden="true">🗂</span><b>주제 창고</b><small>분석에서 나온 주제 {topicsLeft}개</small>
        </button>
      </div>

      <div className="section-head"><h2>이어서 만들기</h2><p>완성·보관한 프로젝트는 빠집니다.</p></div>
      {inProgress.length === 0 ? (
        <p className="empty">진행 중인 프로젝트가 없습니다. 새 프로젝트로 시작하세요.</p>
      ) : (
        <div className="home-projects">
          {inProgress.map((p) => (
            <button className="home-project" key={p.project_id} onClick={() => onOpen(p)} type="button">
              <img alt="" onError={(e) => (e.currentTarget.style.visibility = "hidden")} src={thumb(p)} />
              <span><b>{name(p)}</b><small>{stepLabel(p)} 단계 · {new Date(p.updated_at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</small></span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
