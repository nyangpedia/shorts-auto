import { useEffect, useRef, useState } from "react";

import type { FactCheckResult, FactVerdict, ScriptCandidate, SimilarityResult, TtsValidationResult } from "../types";

interface ScriptStepProps {
  readonly candidates: readonly ScriptCandidate[];
  readonly selectedCandidateId: string | null;
  readonly finalScript: string | null;
  readonly factCheck: FactCheckResult | null;
  readonly similarity: SimilarityResult | null;
  readonly ttsValidation: TtsValidationResult | null;
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly onSelect: (candidateId: string) => void;
  readonly onFinalize: (feedback: string) => void;
  readonly onSave: (script: string) => void;
  readonly onFactCheck: () => void;
}

const VERDICT_CHIP: Record<FactVerdict, string> = { 의심: "bad", 논란: "warn", 확실: "ok" };
const SIMILARITY_CHIP: Record<SimilarityResult["level"], string> = { 낮음: "ok", 주의: "warn", 높음: "bad", "비교 불가": "" };
const LABEL: Record<string, string> = { draft_a: "초안 A · 상식 충돌형", draft_b: "초안 B · 스토리텔링형" };

export function ScriptStep(props: ScriptStepProps) {
  const { candidates, selectedCandidateId, finalScript, factCheck, similarity, ttsValidation, isBusy, busyText } = props;
  const [draft, setDraft] = useState(finalScript ?? "");
  const [feedback, setFeedback] = useState("");
  const editorRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => setDraft(finalScript ?? ""), [finalScript]);

  if (candidates.length === 0) {
    return <p className="empty">분석 단계에서 주제를 고르고 대본 초안을 만들어주세요.</p>;
  }

  const dirty = finalScript !== null && draft.trim() !== finalScript.trim();
  const issues = factCheck?.claims.filter((c) => c.verdict !== "확실").length ?? 0;

  function jumpTo(quote: string) {
    const el = editorRef.current;
    const at = el ? draft.indexOf(quote) : -1;
    if (!el || at < 0) return;
    el.focus();
    el.setSelectionRange(at, at + quote.length);
  }

  return (
    <div className="stack">
      {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}
      <div className="grid2">
        {candidates.map((c) => (
          <button
            aria-pressed={selectedCandidateId === c.candidate_id}
            className="card draft"
            disabled={isBusy}
            key={c.candidate_id}
            onClick={() => props.onSelect(c.candidate_id)}
            type="button"
          >
            <span className="chip accent" style={{ justifySelf: "start" }}>{LABEL[c.candidate_type] ?? c.candidate_type}</span>
            <h3>{c.title}</h3>
            <p>{c.draft_script}</p>
          </button>
        ))}
      </div>

      {selectedCandidateId && (
        <div className="card">
          <div className="section-head">
            <h2>{finalScript ? "대본 다듬기" : "선택한 초안 확정"}</h2>
            <p>{finalScript ? "직접 고친 뒤 저장하세요. 내 말투와 의견을 넣으면 수익화 심사에도 유리합니다." : "고칠 방향이 있으면 적고 확정하세요. AI가 낭독용으로 다듬습니다."}</p>
          </div>

          {!finalScript ? (
            <>
              <textarea aria-label="확정 요청" className="textarea" onChange={(e) => setFeedback(e.target.value)} placeholder="예: 더 짧게, 마지막 문장을 질문으로" rows={2} value={feedback} />
              <div className="row">
                <button className="btn accent" disabled={isBusy} onClick={() => props.onFinalize(feedback)} type="button">이 초안으로 확정</button>
              </div>
            </>
          ) : (
            <>
              {ttsValidation && !ttsValidation.is_valid && (
                <div className="banner warn">낭독 주의: {ttsValidation.issues.join(" / ")}</div>
              )}
              <textarea aria-label="최종 대본" className="textarea editor" onChange={(e) => setDraft(e.target.value)} ref={editorRef} value={draft} />
              <div className="row">
                <button className="btn primary" disabled={isBusy || !dirty} onClick={() => props.onSave(draft)} type="button">저장</button>
                <button className="btn" disabled={isBusy || dirty} onClick={props.onFactCheck} title={dirty ? "저장한 뒤 확인할 수 있습니다" : undefined} type="button">
                  {factCheck ? "사실 다시 확인" : "AI 사실 확인"}
                </button>
                <span className="muted small">{draft.length}자 · 약 {Math.round(draft.length / 9)}초</span>
              </div>
            </>
          )}
        </div>
      )}

      {finalScript && similarity && !dirty && (
        <div className="card">
          <div className="section-head">
            <h2>원본과 겹침</h2>
            <span className={`chip ${SIMILARITY_CHIP[similarity.level]}`}>
              {similarity.comparable ? `${similarity.level} · ${Math.round(similarity.score * 100)}%` : "비교 불가"}
            </span>
            <p>
              {similarity.comparable
                ? "레퍼런스 자막과 글자가 겹치는 비율입니다. 15% 아래를 권합니다."
                : "레퍼런스가 다른 언어라 문장 비교가 안 됩니다. 번역해서 옮긴 것도 2차 저작물이니 구성·사례까지 그대로 따라가지 마세요."}
            </p>
          </div>
          {similarity.sentences.length > 0 && (
            <div className="claims">
              {similarity.sentences.map((s, i) => (
                <div className="claim" key={i}>
                  <span className="chip warn">{Math.round(s.score * 100)}%</span>
                  <button className="link-btn" onClick={() => jumpTo(s.text)} style={{ padding: 0, color: "inherit", textAlign: "left" }} type="button">
                    <q>{s.text}</q>
                  </button>
                  <span className="muted small">원본과 거의 같음</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {finalScript && factCheck && !dirty && (
        <div className="card">
          <div className="section-head">
            <h2>사실 확인 결과</h2>
            <span className={`chip ${issues ? "warn" : "ok"}`}>{issues ? `확인 필요 ${issues}곳` : "문제 없음"}</span>
            <p>AI가 자기 지식으로 판단한 결과라 틀릴 수 있습니다. 검색 링크로 직접 확인하세요.</p>
          </div>
          <div className="claims">
            {factCheck.claims.map((claim, i) => (
              <div className="claim" key={i}>
                <span className={`chip ${VERDICT_CHIP[claim.verdict]}`}>{claim.verdict}</span>
                <div>
                  <button className="link-btn" onClick={() => jumpTo(claim.quote)} style={{ padding: 0, color: "inherit", textAlign: "left" }} type="button">
                    <q>{claim.quote}</q>
                  </button>
                  <p>{claim.reason}</p>
                </div>
                <a href={`https://www.google.com/search?q=${encodeURIComponent(claim.search_query || claim.quote)}`} rel="noreferrer" target="_blank">검색 ↗</a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
