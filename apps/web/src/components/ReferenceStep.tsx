import { FormEvent, useState } from "react";

import type { DurationFilter, ReferenceCandidate, ReferenceSearchPayload } from "../types";

interface ReferenceStepProps {
  readonly candidates: readonly ReferenceCandidate[];
  readonly selectedReference: ReferenceCandidate | null;
  readonly isBusy: boolean;
  readonly onSearch: (payload: ReferenceSearchPayload) => void;
  readonly onAddDirect: (url: string) => void;
  readonly onSelect: (videoId: string) => void;
}

const DURATIONS: readonly { value: DurationFilter; label: string; max: number }[] = [
  { value: "under_60", label: "60초 이하", max: 60 },
  { value: "under_180", label: "3분 이하", max: 180 },
  { value: "under_300", label: "5분 이하", max: 300 },
  { value: "all", label: "전체 길이", max: 600 }
];

// Korean + English + Japanese per niche: YouTube returns results in the query's language,
// so foreign references only show up for foreign-language keywords (100 quota units each).
const GENRES = [
  { label: "정보·상식", keyword: "알아두면 쓸모있는 상식, fun facts, 雑学" },
  { label: "썰·이야기", keyword: "실화 썰, true story, 実話" },
  { label: "뉴스·시사", keyword: "오늘의 뉴스 이슈, news explained, ニュース 解説" },
  { label: "명언·동기부여", keyword: "동기부여 명언, motivational quotes, 名言" },
  { label: "재테크", keyword: "돈 버는 습관, money habits, お金 習慣" },
  { label: "건강", keyword: "건강 습관 꿀팁, health tips, 健康 習慣" },
  { label: "심리", keyword: "심리학 행동 특징, psychology facts, 心理学" },
  { label: "역사", keyword: "역사 이야기, history facts, 歴史 雑学" },
  { label: "과학", keyword: "신기한 과학, science facts, 科学 雑学" },
  { label: "미스터리", keyword: "미스터리 괴담, unsolved mystery, 都市伝説" }
] as const;

const fmt = (value: number | null) => (value === null ? "-" : new Intl.NumberFormat("ko-KR", { notation: "compact" }).format(value));
const fmtDuration = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const fmtRatio = (r: number | null) => (r === null ? null : `${r >= 10 ? Math.round(r) : r.toFixed(1)}배`);

export function ReferenceStep({ candidates, selectedReference, isBusy, onSearch, onAddDirect, onSelect }: ReferenceStepProps) {
  const [keyword, setKeyword] = useState("");
  const [genre, setGenre] = useState<string | null>(null);
  const [duration, setDuration] = useState<DurationFilter>("under_180");
  const [channel, setChannel] = useState("");
  const [minViews, setMinViews] = useState("");
  const [maxSubs, setMaxSubs] = useState("");
  const [after, setAfter] = useState("");
  const [directUrl, setDirectUrl] = useState("");

  function search(event: FormEvent) {
    event.preventDefault();
    if (isBusy || (!keyword.trim() && !channel.trim())) return;
    onSearch({
      keyword: keyword.trim() || undefined,
      channel_query: channel.trim() || undefined,
      published_after: after || undefined,
      published_before: after ? new Date().toISOString().slice(0, 10) : undefined,
      duration_filter: duration,
      max_duration_seconds: DURATIONS.find((d) => d.value === duration)?.max ?? 180,
      minimum_views: Math.max(0, Number(minViews) || 0),
      maximum_subscribers: maxSubs ? Number(maxSubs) : undefined,
      max_results: 50
    });
  }

  function addDirect(event: FormEvent) {
    event.preventDefault();
    if (!directUrl.trim() || isBusy) return;
    onAddDirect(directUrl.trim());
    setDirectUrl("");
  }

  return (
    <div className="stack">
      <div className="section-head">
        <h2>참고할 쇼츠 고르기</h2>
        <p>잘 된 쇼츠를 고르면 성공 공식을 분석해 새 대본을 만듭니다. 노란 배지는 구독자 대비 조회수 배율입니다.</p>
      </div>

      <form className="card" onSubmit={search}>
        <div className="search-row">
          <input aria-label="검색어" className="input" onChange={(e) => setKeyword(e.target.value)} placeholder="예: 돈 버는 습관, money habits, お金 習慣 (쉼표로 여러 언어)" value={keyword} />
          <select aria-label="영상 길이" className="select" onChange={(e) => setDuration(e.target.value as DurationFilter)} value={duration}>
            {DURATIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
          <button className="btn primary" disabled={isBusy || (!keyword.trim() && !channel.trim())} type="submit">
            {isBusy ? "검색 중…" : "검색"}
          </button>
        </div>
        <div className="chips" style={{ marginTop: 12 }}>
          {GENRES.map((g) => (
            <button
              aria-pressed={genre === g.label}
              key={g.label}
              onClick={() => { setGenre(g.label); setKeyword(g.keyword); }}
              type="button"
            >
              {g.label}
            </button>
          ))}
        </div>
        <p className="muted small" style={{ margin: "10px 0 0" }}>
          해외 쇼츠는 그 나라 말 키워드로만 나옵니다. 쉼표로 나눈 키워드마다 검색하며, 키워드 1개당 YouTube 무료 한도 100포인트(하루 10,000)를 씁니다.
        </p>
        <details className="more">
          <summary>상세 조건 (채널, 기간, 조회수)</summary>
          <div className="search-extra">
            <label className="field">채널 (선택)<input className="input" onChange={(e) => setChannel(e.target.value)} placeholder="@채널 또는 URL" value={channel} /></label>
            <label className="field">이 날짜 이후 업로드<input className="input" onChange={(e) => setAfter(e.target.value)} type="date" value={after} /></label>
            <label className="field">최소 조회수<input className="input" min="0" onChange={(e) => setMinViews(e.target.value)} type="number" value={minViews} /></label>
            <label className="field">최대 구독자<input className="input" min="0" onChange={(e) => setMaxSubs(e.target.value)} type="number" value={maxSubs} /></label>
          </div>
          <p className="muted small">조건을 빡빡하게 걸면 결과가 줄어듭니다. 처음엔 비워두고 배율을 보고 고르세요.</p>
        </details>
      </form>

      <form className="direct-row" onSubmit={addDirect}>
        <input aria-label="유튜브 링크" className="input" onChange={(e) => setDirectUrl(e.target.value)} placeholder="또는 유튜브 쇼츠 링크를 바로 붙여넣기" type="url" value={directUrl} />
        <button className="btn" disabled={isBusy || !directUrl.trim()} type="submit">링크로 선택</button>
      </form>

      {selectedReference && (
        <div className="card selected-ref">
          <img alt="" src={selectedReference.thumbnail_url} />
          <div>
            <span className="chip ok">선택됨</span>
            <p style={{ margin: "6px 0 4px", fontWeight: 700 }}>{selectedReference.title}</p>
            <span className="muted small">
              {selectedReference.channel_name} · 조회수 {fmt(selectedReference.view_count)} · 구독자 {fmt(selectedReference.subscriber_count)}
              {fmtRatio(selectedReference.vs_ratio) && ` · ${fmtRatio(selectedReference.vs_ratio)}`} ·{" "}
              <a href={selectedReference.url} rel="noreferrer" target="_blank">유튜브에서 보기 ↗</a>
            </span>
          </div>
        </div>
      )}

      {candidates.length > 0 ? (
        <div className="refs" role="list">
          {candidates.map((c) => (
            <button
              aria-label={`${c.title} 선택`}
              aria-pressed={selectedReference?.video_id === c.video_id}
              className="ref"
              disabled={isBusy}
              key={c.video_id}
              onClick={() => onSelect(c.video_id)}
              type="button"
            >
              <div className="ref-thumb">
                <img alt="" loading="lazy" src={c.thumbnail_url} />
                {fmtRatio(c.vs_ratio) && <span className="ref-ratio">{fmtRatio(c.vs_ratio)}</span>}
                <span className="ref-dur">{fmtDuration(c.duration_seconds)}</span>
              </div>
              <div className="ref-body">
                <b>{c.title}</b>
                {c.title_ko && <span className="ref-ko">🇰🇷 {c.title_ko}</span>}
                <small>{c.channel_name} · 조회수 {fmt(c.view_count)}</small>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <p className="empty">검색하거나 링크를 붙여넣으면 여기에 쇼츠가 나옵니다.</p>
      )}
    </div>
  );
}
