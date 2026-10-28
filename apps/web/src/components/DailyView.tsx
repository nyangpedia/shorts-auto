import { FormEvent, useEffect, useRef, useState } from "react";

import type { DailyItem, DailyState, TrendPoint } from "../api";

interface DailyViewProps {
  readonly daily: DailyState | null;
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly onSaveKeywords: (keywords: readonly string[]) => void;
  readonly onRefresh: (force: boolean) => void;
  readonly onUse: (item: DailyItem) => void;
  readonly onOpenProject: (projectId: string) => void;
}

const compact = (n: number) => new Intl.NumberFormat("ko-KR", { notation: "compact" }).format(n);
const fmtDuration = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** One keyword, one measure: small-channel breakouts per daily fetch. Median views/day stays a number, not a second axis. */
function TrendCard({ keyword, points }: { keyword: string; points: readonly TrendPoint[] }) {
  const W = 220, H = 56, PAD = 6;
  const last = points[points.length - 1];
  const weekAgo = points.length > 7 ? points[points.length - 8] : points[0];
  const delta = last && weekAgo && points.length > 1 ? last.breakouts - weekAgo.breakouts : null;
  const max = Math.max(1, ...points.map((p) => p.breakouts));
  const x = (i: number) => PAD + (points.length > 1 ? (i / (points.length - 1)) * (W - PAD * 2) : (W - PAD * 2) / 2);
  const y = (v: number) => H - PAD - (v / max) * (H - PAD * 2);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.breakouts).toFixed(1)}`).join(" ");

  return (
    <div className="trend">
      <div className="trend-head">
        <b>{keyword}</b>
        {delta !== null ? (
          <span className={`trend-delta ${delta > 0 ? "up" : delta < 0 ? "down" : ""}`}>
            <i aria-hidden="true">{delta > 0 ? "▲" : delta < 0 ? "▼" : "–"}</i> {delta > 0 ? "+" : delta < 0 ? "−" : ""}{Math.abs(delta)} <small>({points.length > 7 ? "7일 전 대비" : "첫 기록 대비"})</small>
          </span>
        ) : null}
      </div>
      {points.length < 2 ? (
        <p className="muted small">기록 쌓는 중 ({points.length}일째) · 2일부터 그래프가 그려집니다</p>
      ) : (
        <svg aria-label={`${keyword} 터진 영상 수 추이, 최근 ${last.breakouts}개`} className="trend-chart" role="img" viewBox={`0 0 ${W} ${H}`}>
          <line className="trend-base" x1={PAD} x2={W - PAD} y1={H - PAD} y2={H - PAD} />
          <path className="trend-line" d={path} />
          {points.map((p, i) => (
            <g key={p.date}>
              <circle className="trend-hit" cx={x(i)} cy={y(p.breakouts)} r={9}>
                <title>{`${p.date} · 터진 영상 ${p.breakouts}개 / ${p.count}개 · 하루 조회수 중간값 ${p.median_views_per_day.toLocaleString("ko-KR")}`}</title>
              </circle>
              {i === points.length - 1 ? <circle className="trend-dot" cx={x(i)} cy={y(p.breakouts)} r={4} /> : null}
            </g>
          ))}
        </svg>
      )}
      {last ? (
        <small className="muted">오늘 터진 영상 <b>{last.breakouts}</b>개 · 하루 조회수 중간값 {compact(last.median_views_per_day)}</small>
      ) : null}
    </div>
  );
}

export function DailyView({ daily, isBusy, busyText, onSaveKeywords, onRefresh, onUse, onOpenProject }: DailyViewProps) {
  const [keywords, setKeywords] = useState<readonly string[]>(daily?.keywords ?? []);
  const [draft, setDraft] = useState("");
  useEffect(() => setKeywords(daily?.keywords ?? []), [daily?.keywords]);

  const today = new Date().toLocaleDateString("sv-SE"); // local YYYY-MM-DD, same day boundary as the API

  // Opening the view is the daily trigger: fetch once if today's batch isn't there yet.
  const autoFetched = useRef(false);
  useEffect(() => {
    if (autoFetched.current || !daily || isBusy || daily.keywords.length === 0 || daily.fetched_on === today) return;
    autoFetched.current = true;
    onRefresh(false);
  }, [daily, isBusy, today, onRefresh]);
  const changed = JSON.stringify(keywords) !== JSON.stringify(daily?.keywords ?? []);

  function add(event: FormEvent) {
    event.preventDefault();
    const value = draft.trim();
    if (value && !keywords.includes(value) && keywords.length < 8) setKeywords([...keywords, value]);
    setDraft("");
  }

  return (
    <div className="stack">
      <div className="section-head">
        <h2>오늘의 레퍼런스</h2>
        <p>내 분야 키워드로 최근 7일 쇼츠를 모읍니다. 하루 중 처음 열 때 자동으로 새로 가져오고, 하루당 조회수 순서입니다.</p>
      </div>
      {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}

      <div className="card">
        <div className="chips">
          {keywords.map((k) => (
            <button aria-label={`${k} 삭제`} aria-pressed key={k} onClick={() => setKeywords(keywords.filter((x) => x !== k))} type="button">
              {k} ✕
            </button>
          ))}
          {keywords.length === 0 ? <span className="muted small">키워드를 추가하세요. 해외 영상도 보려면 영어 키워드를 같이 넣으세요 (예: 돈 버는 습관 / money habits)</span> : null}
        </div>
        <form className="direct-row" onSubmit={add}>
          <input aria-label="키워드 추가" className="input" maxLength={50} onChange={(e) => setDraft(e.target.value)} placeholder="키워드 추가 후 Enter (최대 8개)" value={draft} />
          <button className="btn" disabled={!draft.trim() || keywords.length >= 8} type="submit">추가</button>
        </form>
        <div className="row">
          {changed ? (
            <button className="btn primary" disabled={isBusy} onClick={() => onSaveKeywords(keywords)} type="button">키워드 저장</button>
          ) : (
            <button className="btn accent" disabled={isBusy || keywords.length === 0} onClick={() => onRefresh(daily?.fetched_on === today)} type="button">
              {daily?.fetched_on === today ? "다시 검색 (한도 사용)" : "오늘 것 가져오기"}
            </button>
          )}
          <span className="muted small">
            {daily?.fetched_on ? `${daily.fetched_on} 기준 · ` : ""}키워드 1개당 YouTube 무료 한도 100포인트 (하루 10,000)
          </span>
        </div>
      </div>

      {daily && daily.keywords.some((k) => daily.trends?.[k]?.length) ? (
        <div className="card">
          <div className="section-head">
            <h2>키워드 추세</h2>
            <p>구독자의 10배 넘게 조회된 최근 7일 쇼츠 수입니다. 몇 주째 줄면 그 포맷이 식는 신호입니다. 점에 마우스를 올리면 그날 숫자가 나옵니다.</p>
          </div>
          <div className="trends">
            {daily.keywords.map((k) => <TrendCard key={k} keyword={k} points={daily.trends?.[k] ?? []} />)}
          </div>
        </div>
      ) : null}

      {daily && daily.items.length > 0 ? (
        <div className="refs">
          {daily.items.map((item) => (
            <div className="ref" key={item.video_id} style={item.used_by ? { opacity: 0.55 } : undefined}>
              <a className="ref-thumb" href={item.url} rel="noreferrer" target="_blank" title="유튜브에서 보기">
                <img alt="" loading="lazy" src={item.thumbnail_url} />
                <span className="ref-ratio">하루 {compact(item.views_per_day)}</span>
                <span className="ref-dur">{fmtDuration(item.duration_seconds)}</span>
              </a>
              <div className="ref-body">
                <b>{item.title}</b>
                <small>{item.channel_name} · 조회수 {compact(item.view_count)} · {item.keyword}</small>
                {item.used_by ? (
                  <button className="btn small" onClick={() => onOpenProject(item.used_by!)} type="button">사용함 · 열기</button>
                ) : (
                  <button className="btn small accent" disabled={isBusy} onClick={() => onUse(item)} type="button">이 쇼츠로 만들기</button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">{daily?.keywords.length ? "‘오늘 것 가져오기’를 누르세요." : "키워드를 저장하면 시작할 수 있습니다."}</p>
      )}
    </div>
  );
}
