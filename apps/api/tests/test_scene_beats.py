from app.production.service import split_into_beats


def test_beats_are_short_and_keep_every_word():
    clauses = ["첫째,", "피라미드 하나에 쓰인 돌은 무려 230만 개 총무게만 600만 톤으로 63빌딩 12채를 합친 엄청난 스케일입니다."]
    beats = split_into_beats(clauses)
    assert " ".join(beats).split() == " ".join(clauses).split()  # nothing dropped or reordered
    assert beats[0].startswith("첫째, ")  # the stub is folded into the next beat
    assert all(len(b) <= 30 for b in beats) and len(beats) >= 3
    assert not any(b.endswith("230만") or b.endswith("600만") for b in beats)  # numbers stay with units
