import { useState } from "react";

interface Topic {
  readonly topic_number?: number;
  readonly title?: string;
  readonly category?: string;
  readonly hook?: string;
  readonly core_question?: string;
}

interface AnalysisStepProps {
  readonly analysis: Readonly<Record<string, unknown>> | null;
  readonly referenceScript: string | null;
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly isScriptBusy: boolean;
  readonly onRunAnalysis: () => void;
  readonly onGenerateDrafts: (feedback: string) => void;
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");

const INSIGHTS = [
  ["🎣 멈춘 이유", "hook_analysis"],
  ["❓ 계속 본 이유", "curiosity_gap"],
  ["🔄 이탈을 막은 장치", "retention_analysis"],
  ["🎁 끝까지 본 보상", "payoff_analysis"]
] as const;

export function AnalysisStep({ analysis, referenceScript, isBusy, busyText, isScriptBusy, onRunAnalysis, onGenerateDrafts }: AnalysisStepProps) {
  const [picked, setPicked] = useState<number | null>(0);
  const [note, setNote] = useState("");

  if (!analysis) {
    return (
      <div className="stack">
        <div className="section-head"><h2>왜 터졌는지 분석</h2><p>음원 받기 → 자막 변환 → 성공 공식 분석을 한 번에 진행합니다 (1~2분)</p></div>
        {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}
        <div className="row" style={{ marginTop: 0 }}>
          <button className="btn accent" disabled={isBusy} onClick={onRunAnalysis} type="button">
            {isBusy ? "분석 중…" : "분석 시작"}
          </button>
        </div>
      </div>
    );
  }

  const topics = (Array.isArray(analysis.recommended_topics) ? analysis.recommended_topics : []) as Topic[];
  const risks = Array.isArray(analysis.risk_notes) ? (analysis.risk_notes as string[]) : [];
  const formula = text(analysis.winning_formula) || text(analysis.primary_structure);

  function generate() {
    const topic = picked !== null ? topics[picked] : undefined;
    const parts = [
      topic ? `${picked! + 1}번 추천 주제로 작성: ${topic.title ?? ""}` : "",
      note.trim() ? `추가 요청: ${note.trim()}` : ""
    ].filter(Boolean);
    onGenerateDrafts(parts.join("\n"));
  }

  return (
    <div className="stack">
      <div className="section-head">
        <h2>왜 터졌는지 분석</h2>
        {formula ? <span className="chip accent">공식: {formula}</span> : null}
        <button className="link-btn" disabled={isBusy} onClick={onRunAnalysis} type="button">↻ 다시 분석</button>
      </div>
      {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}

      <div className="insight">
        {INSIGHTS.map(([label, key]) =>
          text(analysis[key]) ? (
            <div className="card" key={key}><h4>{label}</h4><p>{text(analysis[key])}</p></div>
          ) : null
        )}
      </div>
      {risks.length > 0 && <div className="banner warn">⚠️ 주의할 점 — {risks.join(" / ")}</div>}

      <div className="section-head" style={{ marginTop: 10 }}>
        <h2>이 공식으로 만들 주제</h2><p>하나를 고르고, 원하는 방향이 있으면 아래에 적어주세요</p>
      </div>
      <div className="topics">
        {topics.map((topic, index) => (
          <button aria-pressed={picked === index} className="topic" key={index} onClick={() => setPicked(picked === index ? null : index)} type="button">
            <span className="topic-n">{index + 1}</span>
            <span><b>{topic.title}</b>{topic.hook ? <small>훅: “{topic.hook}”</small> : null}</span>
            {topic.category ? <span className="chip">{topic.category}</span> : null}
          </button>
        ))}
      </div>
      <textarea
        aria-label="추가 요청"
        className="textarea"
        onChange={(e) => setNote(e.target.value)}
        placeholder="예: 내 경험을 넣어서 1인칭으로, 마지막에 질문으로 끝내기"
        rows={3}
        value={note}
      />
      <div className="row" style={{ marginTop: 0 }}>
        <button className="btn accent" disabled={isScriptBusy || (picked === null && !note.trim())} onClick={generate} type="button">
          {isScriptBusy ? "대본 초안 만드는 중…" : "이 주제로 대본 초안 2개 만들기"}
        </button>
      </div>

      {referenceScript ? (
        <details className="more">
          <summary>레퍼런스 원문 자막 보기</summary>
          <p className="ref-script">{referenceScript}</p>
        </details>
      ) : null}
    </div>
  );
}
