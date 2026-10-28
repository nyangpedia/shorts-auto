"""Subtitle numbers: "초속 삼십만 킬로미터" → "초속 30만km".

Scripts spell numbers out so the voice reads them right, but on screen digits are faster to read
(and get the yellow number highlight). Ordinary words that merely start with a numeral syllable
("구조", "만약", "사실", "천천히", "이것") must stay untouched, so a word is converted only when the
number is unmistakable from its form or from the counter/unit that follows it.
"""
from __future__ import annotations

import re

_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_SMALL = {"십": 10, "백": 100, "천": 1000}
_BIG = {"만": 10_000, "억": 10**8, "조": 10**12}
_NUMERAL = "".join([*_DIGIT, *_SMALL, *_BIG])
_RUN = re.compile(f"^([{_NUMERAL}]+)(.*)$")

UNITS = {"킬로미터": "km", "미터": "m", "센티미터": "cm", "밀리미터": "mm", "킬로그램": "kg", "그램": "g", "퍼센트": "%"}
_COUNTERS = ("개", "명", "년", "월", "시간", "분", "초", "도", "배", "번", "원", "톤", "살", "층", "채", "가지", "마리", "대", "위",
             "킬로미터", "미터", "센티미터", "킬로그램", "그램", "퍼센트", "광년", "달러", "세기")
_PARTICLES = ("", "은", "는", "이", "가", "을", "를", "의", "에", "에서", "로", "으로", "도", "만", "까지", "부터", "씩", "쯤", "이나", "나", "과", "와")


def _value(run: str) -> int | None:
    """Sino-Korean numeral → int, or None if the syllables don't form a well-made number."""
    total, section, digit = 0, 0, None
    for ch in run:
        if ch in _DIGIT:
            if digit is not None:
                return None  # two digits in a row ("삼사") is not a number
            digit = _DIGIT[ch]
        elif ch in _SMALL:
            section += (digit or 1) * _SMALL[ch]
            digit = None
        else:  # 만/억/조
            chunk = section + (digit or 0)
            if chunk == 0:
                chunk = 1
            total += chunk * _BIG[ch]
            section, digit = 0, None
    return total + section + (digit or 0)


def _format(value: int) -> str:
    """Keep 만/억/조 as words the way Korean captions do: 300000 → "30만", 1000000000 → "10억"."""
    for word, size in (("조", 10**12), ("억", 10**8), ("만", 10_000)):
        if value >= size and value % size == 0:
            return f"{value // size}{word}"
    return str(value)


def _convert_word(word: str, next_word: str) -> str | None:
    match = _RUN.match(word)
    if not match:
        return None
    run, rest = match.groups()
    if len(run) < 2:
        return None  # one syllable is too ambiguous: "이번", "이분", "일주일", "사실"
    stripped = rest.rstrip(",.?!~")
    has_counter = stripped.startswith(_COUNTERS) or (not stripped and next_word.startswith(_COUNTERS))
    has_place = any(c in _SMALL for c in run)  # 십/백/천 make it a number on their own ("삼십", "이천")
    long_enough = len(run) >= 3
    if not (has_counter or ((has_place or long_enough) and stripped in _PARTICLES)):
        return None
    value = _value(run)
    if value is None or value == 0:
        return None
    for spoken, short in UNITS.items():
        if rest.startswith(spoken):
            rest = short + rest[len(spoken):]
            break
    return _format(value) + rest


def digits_for_subtitles(text: str) -> str:
    words = text.split()
    out: list[str] = []
    i = 0
    while i < len(words):
        nxt = words[i + 1] if i + 1 < len(words) else ""
        converted = _convert_word(words[i], nxt)
        if converted is None:
            out.append(words[i])
        elif converted == _format(_value(_RUN.match(words[i]).group(1)) or 0) and nxt and any(nxt.startswith(u) for u in UNITS):
            unit = next(u for u in UNITS if nxt.startswith(u))
            out.append(converted + UNITS[unit] + nxt[len(unit):])  # "삼십만 킬로미터," → "30만km,"
            i += 1
        else:
            out.append(converted)
        i += 1
    return " ".join(out)


if __name__ == "__main__":
    cases = {
        "초속 삼십만 킬로미터, 즉 빛의 속도": "초속 30만km, 즉 빛의 속도",
        "시속 십억 킬로미터로 달리든": "시속 10억km로 달리든",
        "칠십 퍼센트의 사람들": "70%의 사람들",
        "이천오백 년 전 구조를 보면": "2500 년 전 구조를 보면",
        "삼만 명이 모였다": "3만 명이 모였다",
        "만약 사실이라면 천천히 이것을 일주일": "만약 사실이라면 천천히 이것을 일주일",
        "구조는 오늘 사람이 이번에 이분과": "구조는 오늘 사람이 이번에 이분과",
        "하루 열 시간씩 이십 년 동안": "하루 열 시간씩 20 년 동안",
        "육십삼 빌딩 십이 채를": "63 빌딩 12 채를",
    }
    for given, expected in cases.items():
        got = digits_for_subtitles(given)
        assert got == expected, (given, got, expected)
    print("ok")
