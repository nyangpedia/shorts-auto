from app.production.word_timing import _BOUND_START, leans_on_next, one_line_chunks


def chunk(text: str) -> list[str]:
    words = [{"text": t, "start": k * 0.3, "end": k * 0.3 + 0.25} for k, t in enumerate(text.split())]
    return [c["text"] for c in one_line_chunks(words)]


def test_a_word_is_never_stranded_from_the_one_it_leans_on():
    cut = chunk("여기서 한 장면이 바뀌면서 거대한 피라미드가 지구의 중력을 이겨낸 것입니다")
    assert cut == ["여기서 한 장면이", "바뀌면서", "거대한 피라미드가", "지구의 중력을", "이겨낸 것입니다"]


def test_particles_with_a_final_consonant_do_not_count_as_leaning():
    assert not any(leans_on_next(w) for w in ("중력을", "겉보기엔", "지구는", "사람만"))
    assert all(leans_on_next(w) for w in ("한", "거대한", "지구의", "이겨낼"))
    assert _BOUND_START.match("것입니다")
