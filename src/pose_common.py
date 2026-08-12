"""공통 상수와 각도 계산.

이 PoC는 회원의 몸이 찍힌 영상을 다루므로 모든 처리를 로컬에서 수행한다.
어떤 함수도 네트워크를 호출하지 않는다.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

# MediaPipe Pose Landmarker 33점 중 이번 판정에 쓰는 것만
LM = {
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}

# 무릎 각도를 만드는 관절 셋 (좌/우)
KNEE_TRIPLETS = {
    "left": (LM["left_hip"], LM["left_knee"], LM["left_ankle"]),
    "right": (LM["right_hip"], LM["right_knee"], LM["right_ankle"]),
}


def angle_deg(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float
) -> Optional[float]:
    """세 점 A-B-C에서 B에 생기는 각도(도).

    화면에 보이는 가로·세로 좌표만 쓴다. 깊이(z)는 한 장의 사진에서 추정한
    값이라 성질이 다르므로 이번 판정에서는 쓰지 않는다. 측면 촬영에서는
    무릎 굽힘이 화면 가로·세로 평면에 그대로 놓이므로 이 두 값으로 충분하다.
    """
    v1x, v1y = ax - bx, ay - by
    v2x, v2y = cx - bx, cy - by
    n1 = math.hypot(v1x, v1y)
    n2 = math.hypot(v2x, v2y)
    if n1 == 0.0 or n2 == 0.0:
        return None
    cos = (v1x * v2x + v1y * v2y) / (n1 * n2)
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


def median_filter(values: Sequence[Optional[float]], window: int) -> list[Optional[float]]:
    """결측(None)을 건너뛰는 중앙값 필터.

    관절이 한두 프레임 튀는 것을 눌러 준다. window=1이면 원값 그대로.
    """
    if window <= 1:
        return list(values)
    half = window // 2
    out: list[Optional[float]] = []
    for i in range(len(values)):
        if values[i] is None:
            out.append(None)
            continue
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        chunk = [v for v in values[lo:hi] if v is not None]
        if not chunk:
            out.append(None)
            continue
        chunk.sort()
        out.append(chunk[len(chunk) // 2])
    return out
