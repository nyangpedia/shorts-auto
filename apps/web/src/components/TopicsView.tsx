import type { TopicItem } from "../api";

interface TopicsViewProps {
  readonly topics: readonly TopicItem[];
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly onStart: (topic: TopicItem) => void;
  readonly onOpenProject: (projectId: string) => void;
}

export function TopicsView({ topics, isBusy, busyText, onStart, onOpenProject }: TopicsViewProps) {
  const unused = topics.filter((t) => !t.used_by);
  const used = topics.filter((t) => t.used_by);

  return (
    <div className="stack">
      <div className="section-head">
        <h2>주제 창고</h2>
        <span className="chip accent">남은 주제 {unused.length}개</span>
        <p>레퍼런스를 분석할 때마다 추천 주제 5개가 여기 쌓입니다. 고르면 그 분석을 가져와 새 프로젝트에서 바로 대본 초안을 만듭니다.</p>
      </div>
      {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}

      {topics.length === 0 ? (
        <p className="empty">아직 주제가 없습니다. 레퍼런스를 하나 분석하면 추천 주제 5개가 쌓입니다.</p>
      ) : (
        <div className="topics">
          {[...unused, ...used].map((topic) => (
            <div className="topic" key={topic.id} style={topic.used_by ? { opacity: 0.55 } : undefined}>
              <span className="topic-n">{topic.category ? "•" : ""}</span>
              <span>
                <b>{topic.title}</b>
                {topic.hook ? <small>훅: “{topic.hook}”</small> : null}
                <small style={{ display: "block", color: "var(--ink-3)" }}>
                  출처: {topic.reference_title} · {topic.analyzed_at.replace("T", " ")}
                  {topic.category ? ` · ${topic.category}` : ""}
                </small>
              </span>
              {topic.used_by ? (
                <button className="btn small" onClick={() => onOpenProject(topic.used_by!)} type="button">만든 프로젝트 열기</button>
              ) : (
                <button className="btn accent small" disabled={isBusy} onClick={() => onStart(topic)} type="button">이 주제로 만들기</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
