"""반복 판정 로직 시험.

영상 없이 각도 시계열만으로 확인할 수 있는 부분을 먼저 시험한다.
`python src/test_count_reps.py` 로 실행한다.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from count_reps import count_reps  # noqa: E402
from pose_common import angle_deg, median_filter  # noqa: E402

PASS, FAIL = "  ok  ", " FAIL "
failures = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failures
    print(f"[{PASS if cond else FAIL}] {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        failures += 1


def squat_wave(n_reps: int, top: float = 170.0, bottom: float = 80.0, period: int = 40):
    """위아래로 오르내리는 각도 시계열을 만든다."""
    out = []
    for r in range(n_reps):
        for t in range(period):
            phase = 2 * math.pi * t / period
            out.append(top - (top - bottom) * (1 - math.cos(phase)) / 2)
    return out


# ── 1. 각도 계산 ────────────────────────────────────────────────────────────
a = angle_deg(0, 0, 0, 1, 1, 1)          # 직각
check("각도: 직각이 90도", a is not None and abs(a - 90) < 1e-6)

a = angle_deg(0, 0, 0, 1, 0, 2)          # 일직선
check("각도: 일직선이 180도", a is not None and abs(a - 180) < 1e-6)

a = angle_deg(0, 0, 0, 0, 1, 1)          # 같은 점 → 계산 불가
check("각도: 길이 0이면 None", a is None)

# ── 2. 기본 반복 세기 ──────────────────────────────────────────────────────
angles = squat_wave(5)
reps, stats = count_reps(angles, down_angle=120, up_angle=160, target_angle=100)
check("반복 5회를 5회로 센다", stats["n_reps"] == 5, f"센 값={stats['n_reps']}")
check("깊이 80도면 얕은 회차 0", stats["n_shallow"] == 0, f"얕은={stats['n_shallow']}")

# ── 3. 얕은 반복 판정 ──────────────────────────────────────────────────────
angles = squat_wave(3, bottom=80) + squat_wave(2, bottom=115)  # 뒤 2회는 얕음
reps, stats = count_reps(angles, down_angle=120, up_angle=160, target_angle=100)
check("얕은 회차 2개를 잡는다", stats["n_shallow"] == 2, f"얕은={stats['n_shallow']}")
check("얕은 회차가 4·5번째다",
      [r.index for r in reps if r.shallow] == [4, 5],
      f"실제={[r.index for r in reps if r.shallow]}")

# ── 4. ★ 히스테리시스 — 경계에서 흔들려도 한 번으로 세는가 ──────────────────
# down/up 경계 사이에서 값이 떨리는 구간을 넣는다.
shaky = [170] * 5 + [130, 125, 130, 125, 130, 125] + [170] * 5
reps, stats = count_reps(shaky, down_angle=120, up_angle=160, target_angle=100)
check("경계에서 떨려도 내려간 적 없으면 0회", stats["n_reps"] == 0, f"센 값={stats['n_reps']}")

# 실제로 내려갔다 올라오되 도중에 130 근처에서 떠는 경우
shaky2 = [170] * 5 + [110, 90, 110, 130, 125, 130, 90, 110] + [170] * 5
reps, stats = count_reps(shaky2, down_angle=120, up_angle=160, target_angle=100)
check("한 번 내려갔다 올라오면 흔들려도 1회", stats["n_reps"] == 1, f"센 값={stats['n_reps']}")

# 두 값을 같게 두면 거부해야 한다
try:
    count_reps(shaky2, down_angle=140, up_angle=140, target_angle=100)
    check("up<=down이면 예외", False, "예외가 안 났다")
except ValueError:
    check("up<=down이면 예외", True)

# ── 5. 신뢰도 낮은 프레임(None) 처리 ───────────────────────────────────────
angles = squat_wave(3)
holed = list(angles)
for i in range(len(holed)):
    if 45 <= i <= 55:            # 한 반복 중간에 구멍
        holed[i] = None
reps, stats = count_reps(holed, down_angle=120, up_angle=160, target_angle=100)
check("제외 프레임이 있어도 3회를 유지", stats["n_reps"] == 3, f"센 값={stats['n_reps']}")
check("제외 프레임 수를 센다", stats["n_excluded_frames"] == 11,
      f"제외={stats['n_excluded_frames']}")

all_none = [None] * 50
reps, stats = count_reps(all_none, down_angle=120, up_angle=160, target_angle=100)
check("전부 제외되면 0회", stats["n_reps"] == 0)
check("전부 제외되면 비율 1.0", abs(stats["excluded_ratio"] - 1.0) < 1e-9)

# ── 6. 마지막에 내려간 채 끝나는 경우 ──────────────────────────────────────
partial = [170] * 5 + [110, 90, 85]      # 올라오지 않고 끝
reps, stats = count_reps(partial, down_angle=120, up_angle=160, target_angle=100)
check("올라오지 않으면 세지 않는다", stats["n_reps"] == 0)
check("내려간 채 끝난 것을 표시한다", stats["open_rep_at_end"] is True)

# ── 7. 중앙값 필터 ─────────────────────────────────────────────────────────
spiky = [100, 100, 20, 100, 100]         # 한 프레임만 튐
sm = median_filter(spiky, window=3)
check("중앙값 필터가 튄 값을 누른다", sm[2] == 100, f"결과={sm}")
check("window=1이면 원값 그대로", median_filter(spiky, 1) == spiky)
check("필터가 None을 유지한다", median_filter([1.0, None, 3.0], 3)[1] is None)

# ── 결과 ───────────────────────────────────────────────────────────────────
print()
if failures:
    print(f"실패 {failures}건")
    sys.exit(1)
print("모두 통과")
