from app.scripts.similarity import check_similarity

REFERENCE = "돈이 모이는 세 가지 습관. 왜 열심히 벌어도 통장은 늘 텅 비어있을까? 첫 번째, 버는 것보다 쓰는 걸 먼저 관리하라."


def test_near_copy_is_high_and_flags_the_copied_sentence():
    result = check_similarity("왜 열심히 벌어도 통장은 늘 텅 비어있을까? 오늘은 다른 이야기를 해볼게요.", REFERENCE)
    assert result.comparable and result.level in ("주의", "높음")
    assert any("통장은 늘 텅" in s.text for s in result.sentences)


def test_rewritten_script_is_low():
    result = check_similarity("월급날 다음 주면 잔고가 바닥나는 이유, 구독 서비스 정리부터 시작해 보세요.", REFERENCE)
    assert result.level == "낮음" and result.sentences == []


def test_foreign_reference_is_reported_as_not_comparable():
    result = check_similarity("문어는 심장이 세 개입니다.", "Octopuses have three hearts and blue blood.")
    assert not result.comparable and result.level == "비교 불가"
