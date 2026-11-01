import { useState } from "react";

import type { TopicHistoryItem, TopicItem } from "../api";

interface TopicsViewProps {
  readonly topics: readonly TopicItem[];
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly onStart: (topic: TopicItem) => void;
  readonly onOpenProject: (projectId: string) => void;
  readonly onHide: (ids: readonly string[]) => void;
  readonly hidden?: readonly TopicItem[];
  readonly history?: readonly TopicHistoryItem[];
  readonly onRestore: (ids: readonly string[]) => void;
}

export function TopicsView({ topics, isBusy, busyText, onStart, onOpenProject, onHide, hidden = [], history = [], onRestore }: TopicsViewProps) {
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const toggle = (id: string) => setPicked((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
  function hide(ids: readonly string[], question: string) {
    if (ids.length === 0 || !window.confirm(question)) return;
    onHide(ids);
    setPicked(new Set());
  }
  const unused = topics.filter((t) => !t.used_by);
  const used = topics.filter((t) => t.used_by);
  // Made on another PC (or before this PC had the analysis): same login, so the list follows the account.
  const elsewhere = history.filter((h) => !used.some((t) => t.id === h.topic_id));

  return (
    <div className="stack">
      <div className="section-head">
        <h2>주제 창고</h2>
        <span className="chip accent">남은 주제 {unused.length}개</span>
        <p>레퍼런스를 분석할 때마다 추천 주제 5개가 여기 쌓입니다. 고르면 그 분석을 가져와 새 프로젝트에서 바로 대본 초안을 만듭니다.</p>
      </div>
      {topics.length > 0 ? (
        <div className="row">
          <button className="btn" disabled={picked.size === 0} onClick={() => hide([...picked], `선택한 주제 ${picked.size}개를 지울까요?`)} type="button">
            선택 삭제 ({picked.size})
          </button>
          <button className="btn" onClick={() => hide(topics.map((t) => t.id), `주제 ${topics.length}개를 모두 비울까요? 분석 결과와 프로젝트는 그대로 남습니다.`)} type="button">
            전체 비우기
          </button>
        </div>
      ) : null}
      {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}

      {topics.length === 0 ? (
        <p className="empty">아직 주제가 없습니다. 레퍼런스를 하나 분석하면 추천 주제 5개가 쌓입니다.</p>
      ) : (
        <div className="topics">
          {[...unused, ...used].map((topic) => (
            <div className="topic" key={topic.id} style={topic.used_by ? { opacity: 0.55 } : undefined}>
              <input aria-label={`${topic.title} 선택`} checked={picked.has(topic.id)} onChange={() => toggle(topic.id)} type="checkbox" />
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
      {elsewhere.length > 0 ? (
        <details className="more">
          <summary>다른 PC에서 만든 주제 ({elsewhere.length})</summary>
          <div className="topics">
            {elsewhere.map((item) => (
              <div className="topic" key={item.topic_id} style={{ opacity: 0.7 }}>
                <span />
                <span><b>{item.title}</b><small style={{ display: "block", color: "var(--ink-3)" }}>{item.updated_at.slice(0, 16).replace("T", " ")}</small></span>
              </div>
            ))}
          </div>
        </details>
      ) : null}
      {hidden.length > 0 ? (
        <details className="more">
          <summary>삭제한 주제 ({hidden.length})</summary>
          <div className="topics">
            {hidden.map((topic) => (
              <div className="topic" key={topic.id} style={{ opacity: 0.7 }}>
                <span />
                <span><b>{topic.title}</b><small style={{ display: "block", color: "var(--ink-3)" }}>출처: {topic.reference_title}</small></span>
                <button className="btn small" onClick={() => onRestore([topic.id])} type="button">되살리기</button>
              </div>
            ))}
          </div>
          <button className="btn small" onClick={() => onRestore(hidden.map((t) => t.id))} type="button">전부 되살리기</button>
        </details>
      ) : null}
    </div>
  );
}
