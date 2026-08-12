"""무릎 각도 시계열 → 반복 판정.

판정에 쓰는 값은 전부 인자로 받는다. 코드에 숫자를 박지 않는다.

반복 판정 규칙
--------------
내려갔다고 볼 각도(down_angle)와 올라왔다고 볼 각도(up_angle)를 **따로** 받는다.
하나의 값으로 하면 그 경계에서 몸이 흔들릴 때 한 번이 여러 번으로 세어진다.

  각도 < down_angle  → DOWN 상태로 들어감 (이때부터 최저 각도를 추적)
  각도 > up_angle    → UP 상태로 돌아옴 (여기서 한 번으로 셈)

얕은 반복 판정
--------------
각도는 작을수록 깊이 앉은 것이다. 한 반복의 최저 각도가 target_angle보다
'크면' 충분히 앉지 않은 것으로 표시한다.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Sequence


@dataclass
class Rep:
    index: int          # 1부터
    start_frame: int    # DOWN으로 들어간 프레임
    bottom_frame: int   # 최저 각도 프레임
    end_frame: int      # UP으로 돌아온 프레임
    min_angle: float    # 최저 무릎 각도(도)
    shallow: bool       # 목표 각도에 못 미쳤는가

    def as_dict(self) -> dict:
        return asdict(self)


def count_reps(
    angles: Sequence[Optional[float]],
    down_angle: float,
    up_angle: float,
    target_angle: float,
    min_frames_down: int = 1,
) -> tuple[list[Rep], dict]:
    """각도 시계열에서 반복을 센다.

    Parameters
    ----------
    angles : 프레임별 무릎 각도. 신뢰도가 낮아 계산에서 제외한 프레임은 None.
    down_angle : 이 값보다 작아지면 내려간 것으로 본다.
    up_angle : 이 값보다 커지면 올라온 것으로 본다. down_angle보다 커야 한다.
    target_angle : 이 값 이하로 내려가야 '충분히 앉았다'로 본다.
    min_frames_down : DOWN 상태를 최소 몇 프레임 유지해야 한 번으로 셀지.
                      값이 튀어 생기는 순간적인 진입을 거른다.

    Returns
    -------
    (reps, stats)
    """
    if up_angle <= down_angle:
        raise ValueError(
            f"up_angle({up_angle})은 down_angle({down_angle})보다 커야 합니다. "
            "두 값을 벌려 두지 않으면 경계에서 한 번이 여러 번으로 세어집니다."
        )

    reps: list[Rep] = []
    state = "UP"
    start_f = bottom_f = -1
    min_a = float("inf")
    frames_down = 0
    excluded = sum(1 for a in angles if a is None)

    for i, a in enumerate(angles):
        if a is None:
            # 신뢰도가 낮아 계산에서 제외한 프레임. 상태를 바꾸지 않는다.
            continue

        if state == "UP":
            if a < down_angle:
                state = "DOWN"
                start_f = bottom_f = i
                min_a = a
                frames_down = 1
        else:  # DOWN
            frames_down += 1
            if a < min_a:
                min_a = a
                bottom_f = i
            if a > up_angle:
                if frames_down >= min_frames_down:
                    reps.append(
                        Rep(
                            index=len(reps) + 1,
                            start_frame=start_f,
                            bottom_frame=bottom_f,
                            end_frame=i,
                            min_angle=min_a,
                            shallow=min_a > target_angle,
                        )
                    )
                state = "UP"
                min_a = float("inf")
                frames_down = 0

    stats = {
        "n_frames": len(angles),
        "n_excluded_frames": excluded,
        "excluded_ratio": (excluded / len(angles)) if angles else 0.0,
        "n_reps": len(reps),
        "n_shallow": sum(1 for r in reps if r.shallow),
        "open_rep_at_end": state == "DOWN",  # 마지막에 내려간 채 끝났는가
    }
    return reps, stats
