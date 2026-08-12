"""웃카타아사나 반복 판정 PoC — 입력(영상) → AI 처리(자세 추정) → 결과 출력.

설계 원칙
---------
1. 실행 위치      : 전부 로컬. 영상을 외부로 전송하지 않는다.
2. 값은 인자로    : 판정에 쓰는 값을 코드에 박지 않는다. 전부 argparse로 받는다.
3. 반올림 금지    : 좌표·신뢰도·각도를 있는 그대로 CSV에 남긴다.
4. 덮어쓰지 않음  : 실행 시각 폴더를 만들어 그 안에 쌓는다.
5. 눈으로 확인    : 관절을 그린 영상과 각도 그래프를 함께 저장한다.
                   숫자만 보면 값이 의도한 것을 재고 있지 않은 경우를 놓친다.

사용 예
-------
  python src/run_poc.py --video data/videos/v01.mp4 \
      --confidence-threshold 0.5 --down-angle 120 --up-angle 160 --target-angle 100
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from count_reps import count_reps  # noqa: E402
from pose_common import KNEE_TRIPLETS, angle_deg, median_filter  # noqa: E402

import mediapipe as mp  # noqa: E402
from mediapipe.tasks import python as mp_python  # noqa: E402
from mediapipe.tasks.python import vision  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = REPO / "assets" / "pose_landmarker_full.task"

# 그릴 뼈대 (다리 위주 + 몸통 기준선)
SKELETON = [(23, 25), (25, 27), (24, 26), (26, 28), (23, 24), (11, 23), (12, 24), (11, 12)]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="영상에서 무릎 각도를 뽑아 반복을 세고 얕은 회차를 표시한다.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--video", required=True, type=Path, help="입력 영상 경로")
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="pose landmarker .task 파일")
    p.add_argument("--outdir", type=Path, default=REPO / "results", help="결과 상위 폴더")
    p.add_argument("--run-stamp", default=None,
                   help="결과 폴더 이름. 여러 영상을 한 묶음으로 처리할 때 같은 값을 준다. "
                        "기본은 실행 시각 (덮어쓰지 않음)")

    g = p.add_argument_group("판정에 쓰는 값 (전부 인자)")
    g.add_argument("--confidence-threshold", type=float, default=0.5,
                   help="이 값을 못 넘은 관절로는 각도를 계산하지 않는다")
    g.add_argument("--confidence-field", choices=["visibility", "presence"], default="visibility",
                   help="신뢰도로 쓸 값")
    g.add_argument("--down-angle", type=float, default=120.0,
                   help="이 값보다 작아지면 내려간 것으로 본다")
    g.add_argument("--up-angle", type=float, default=160.0,
                   help="이 값보다 커지면 올라온 것으로 본다 (down보다 커야 함)")
    g.add_argument("--target-angle", type=float, default=100.0,
                   help="이 값 이하로 내려가야 '충분히 앉았다'로 본다")
    g.add_argument("--smooth-window", type=int, default=5,
                   help="각도 중앙값 필터 창 크기. 1이면 필터 없음")
    g.add_argument("--min-frames-down", type=int, default=3,
                   help="DOWN 상태를 최소 몇 프레임 유지해야 한 번으로 셀지")
    g.add_argument("--side", choices=["auto", "left", "right"], default="auto",
                   help="무릎 각도를 잴 다리. auto면 신뢰도가 높은 쪽(카메라 가까운 쪽)")

    h = p.add_argument_group("모델 옵션")
    h.add_argument("--min-pose-detection-confidence", type=float, default=0.5)
    h.add_argument("--min-pose-presence-confidence", type=float, default=0.5)
    h.add_argument("--min-tracking-confidence", type=float, default=0.5)
    h.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0,
                   help="입력 영상 회전 보정(도)")
    h.add_argument("--no-overlay", action="store_true", help="관절을 그린 영상을 만들지 않음")
    return p.parse_args()


def rotate_frame(frame: np.ndarray, deg: int) -> np.ndarray:
    if deg == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if deg == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if deg == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def main() -> int:
    a = parse_args()
    if a.up_angle <= a.down_angle:
        print(f"[오류] --up-angle({a.up_angle})은 --down-angle({a.down_angle})보다 커야 합니다.\n"
              "       두 값을 벌려 두지 않으면 경계에서 한 번이 여러 번으로 세어집니다.",
              file=sys.stderr)
        return 2
    if not a.video.exists():
        print(f"[오류] 영상을 찾을 수 없습니다: {a.video}", file=sys.stderr)
        return 2
    if not a.model.exists():
        print(f"[오류] 모델 파일이 없습니다: {a.model}\n"
              "       README의 '모델 내려받기'를 먼저 실행하세요.", file=sys.stderr)
        return 2

    stamp = a.run_stamp or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    outdir = a.outdir / stamp / a.video.stem
    if outdir.exists() and any(outdir.iterdir()):
        print(f"[오류] 결과 폴더가 이미 있고 비어 있지 않습니다: {outdir}\n"
              "       덮어쓰지 않습니다. --run-stamp 를 바꾸거나 폴더를 지우십시오.",
              file=sys.stderr)
        return 2
    outdir.mkdir(parents=True, exist_ok=True)          # 실행 시각별 폴더 → 덮어쓰지 않음

    cap = cv2.VideoCapture(str(a.video))
    if not cap.isOpened():
        print(f"[오류] 영상을 열 수 없습니다: {a.video}", file=sys.stderr)
        return 2
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    landmarker = vision.PoseLandmarker.create_from_options(
        vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(a.model)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=a.min_pose_detection_confidence,
            min_pose_presence_confidence=a.min_pose_presence_confidence,
            min_tracking_confidence=a.min_tracking_confidence,
            output_segmentation_masks=False,
        )
    )

    rows: list[dict] = []
    frames_bgr: list[np.ndarray] = []
    landmarks_per_frame: list[list | None] = []
    t0 = time.time()
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = rotate_frame(frame, a.rotate)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = landmarker.detect_for_video(mp_img, int(idx * 1000 / fps))

        lms = res.pose_landmarks[0] if res.pose_landmarks else None
        landmarks_per_frame.append(lms)
        if not a.no_overlay:
            frames_bgr.append(frame)

        row = {"frame": idx, "t_sec": idx / fps, "detected": int(lms is not None)}
        if lms is not None:
            for side, (hi, ki, ai) in KNEE_TRIPLETS.items():
                for tag, li in (("hip", hi), ("knee", ki), ("ankle", ai)):
                    lm = lms[li]
                    conf = getattr(lm, a.confidence_field, 0.0) or 0.0
                    row[f"{side}_{tag}_x"] = lm.x
                    row[f"{side}_{tag}_y"] = lm.y
                    row[f"{side}_{tag}_conf"] = conf
        rows.append(row)
        idx += 1

    cap.release()
    elapsed = time.time() - t0
    n_frames = idx
    if n_frames == 0:
        print("[오류] 프레임을 하나도 읽지 못했습니다.", file=sys.stderr)
        return 2

    # ── 다리 고르기 : 신뢰도가 높은 쪽이 카메라에 가까운 다리 ─────────────
    mean_conf = {}
    for side in KNEE_TRIPLETS:
        vals = [r.get(f"{side}_{t}_conf") for r in rows for t in ("hip", "knee", "ankle")]
        vals = [v for v in vals if v is not None]
        mean_conf[side] = float(np.mean(vals)) if vals else 0.0
    side = a.side if a.side != "auto" else max(mean_conf, key=mean_conf.get)

    # ── 무릎 각도 : 신뢰도를 못 넘은 관절로는 계산하지 않는다 ──────────────
    raw_angles: list[float | None] = []
    excluded_reason: list[str] = []
    for r in rows:
        if not r["detected"]:
            raw_angles.append(None)
            excluded_reason.append("no_pose")
            continue
        confs = [r[f"{side}_{t}_conf"] for t in ("hip", "knee", "ankle")]
        if min(confs) < a.confidence_threshold:
            raw_angles.append(None)
            excluded_reason.append("low_confidence")
            continue
        ang = angle_deg(
            r[f"{side}_hip_x"], r[f"{side}_hip_y"],
            r[f"{side}_knee_x"], r[f"{side}_knee_y"],
            r[f"{side}_ankle_x"], r[f"{side}_ankle_y"],
        )
        raw_angles.append(ang)
        excluded_reason.append("" if ang is not None else "degenerate")

    angles = median_filter(raw_angles, a.smooth_window)
    for r, raw, sm, why in zip(rows, raw_angles, angles, excluded_reason):
        r["side_used"] = side
        r["knee_angle_raw"] = raw
        r["knee_angle"] = sm
        r["excluded_reason"] = why

    reps, stats = count_reps(
        angles,
        down_angle=a.down_angle,
        up_angle=a.up_angle,
        target_angle=a.target_angle,
        min_frames_down=a.min_frames_down,
    )

    # ── frames.csv (반올림하지 않음) ───────────────────────────────────────
    fields = ["frame", "t_sec", "detected", "side_used", "knee_angle_raw", "knee_angle",
              "excluded_reason"]
    for s in KNEE_TRIPLETS:
        for t in ("hip", "knee", "ankle"):
            fields += [f"{s}_{t}_x", f"{s}_{t}_y", f"{s}_{t}_conf"]
    with (outdir / "frames.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # ── reps.csv ──────────────────────────────────────────────────────────
    with (outdir / "reps.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["index", "start_frame", "bottom_frame", "end_frame",
                                          "min_angle", "shallow"])
        w.writeheader()
        for r in reps:
            w.writerow(r.as_dict())

    # ── 각도 그래프 ────────────────────────────────────────────────────────
    plot_angle(outdir / "angle_plot.png", angles, reps, a, side, fps)

    # ── 관절을 그린 영상 ───────────────────────────────────────────────────
    overlay_path = None
    if not a.no_overlay and frames_bgr:
        overlay_path = outdir / "overlay.mp4"
        write_overlay(overlay_path, frames_bgr, landmarks_per_frame, angles, reps,
                      a.confidence_threshold, a.confidence_field, side, fps)

    summary = {
        "video": str(a.video),
        "run_at": stamp,
        "model": str(a.model.name),
        "n_frames": n_frames,
        "fps": fps,
        "video_seconds": n_frames / fps,
        "elapsed_seconds": elapsed,
        "realtime_factor": (n_frames / fps) / elapsed if elapsed else None,
        "side_used": side,
        "mean_confidence_by_side": mean_conf,
        "params": {
            "confidence_threshold": a.confidence_threshold,
            "confidence_field": a.confidence_field,
            "down_angle": a.down_angle,
            "up_angle": a.up_angle,
            "target_angle": a.target_angle,
            "smooth_window": a.smooth_window,
            "min_frames_down": a.min_frames_down,
            "side": a.side,
            "rotate": a.rotate,
        },
        "stats": stats,
        "reps": [r.as_dict() for r in reps],
        "shallow_reps": [r.index for r in reps if r.shallow],
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 화면 출력 ──────────────────────────────────────────────────────────
    print(f"\n입력      : {a.video.name}  ({n_frames}프레임 / {n_frames/fps:.1f}초 / {fps:.1f}fps)")
    print(f"쓴 다리   : {side}  (신뢰도 평균 left={mean_conf['left']:.3f} right={mean_conf['right']:.3f})")
    print(f"제외 프레임: {stats['n_excluded_frames']} / {n_frames}"
          f"  ({stats['excluded_ratio']*100:.1f}%)")
    print(f"반복      : {stats['n_reps']}회")
    print(f"얕은 회차 : {summary['shallow_reps'] or '없음'}"
          f"  (목표 {a.target_angle:.0f}도 이하)")
    if stats["open_rep_at_end"]:
        print("주의      : 마지막에 내려간 채로 영상이 끝났습니다. 그 회차는 세지 않았습니다.")
    print(f"처리 시간 : {elapsed:.1f}초  (영상 길이 대비 {summary['realtime_factor']:.2f}배속)")
    print(f"\n결과      : {outdir}")
    for name in ("frames.csv", "reps.csv", "angle_plot.png", "summary.json"):
        print(f"  - {name}")
    if overlay_path:
        print(f"  - {overlay_path.name}   ← 눈으로 반드시 확인하십시오")
    return 0


def plot_angle(path: Path, angles, reps, a, side: str, fps: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = [i / fps for i in range(len(angles))]
    y = [np.nan if v is None else v for v in angles]

    fig, ax = plt.subplots(figsize=(12, 4.2), dpi=140)
    ax.plot(t, y, lw=1.4, color="#2c4d44", label="knee angle")

    # 계산 제외 구간을 바닥에 띠로 표시
    for i, v in enumerate(angles):
        if v is None:
            ax.axvspan(i / fps, (i + 1) / fps, color="#d9d9d9", lw=0)

    ax.axhline(a.down_angle, ls="--", lw=1, color="#3f6b5f", label=f"down {a.down_angle:g}")
    ax.axhline(a.up_angle, ls="--", lw=1, color="#7fb3a2", label=f"up {a.up_angle:g}")
    ax.axhline(a.target_angle, ls="-", lw=1.4, color="#a65a3f", label=f"target {a.target_angle:g}")

    for r in reps:
        x = r.bottom_frame / fps
        ax.plot([x], [r.min_angle], "o", ms=6,
                color="#a65a3f" if r.shallow else "#3f6b5f")
        ax.annotate(str(r.index), (x, r.min_angle), textcoords="offset points",
                    xytext=(0, -14), ha="center", fontsize=8,
                    color="#a65a3f" if r.shallow else "#3f6b5f")

    ax.set_xlabel("time (s)")
    ax.set_ylabel("knee angle (deg)")
    ax.set_title(f"knee angle / side={side} / reps={len(reps)} / "
                 f"shallow={[r.index for r in reps if r.shallow]}  "
                 f"(grey band = excluded by confidence)", fontsize=10)
    ax.legend(fontsize=8, ncol=4, loc="lower right")
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_overlay(path: Path, frames, landmarks_per_frame, angles, reps,
                  conf_th: float, conf_field: str, side: str, fps: float) -> None:
    """관절을 그린 영상. 신뢰도를 넘은 관절과 못 넘은 관절을 다른 색으로 칠한다.

    숫자로 보면 '조금 낮은 값'으로 읽히는 관절이, 그려 보면 몸의 다른 부위에
    찍혀 있는 것이 보인다. 각도를 믿기 전에 이 영상을 먼저 본다.
    """
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    shallow = {r.bottom_frame: r for r in reps if r.shallow}
    rep_end = {r.end_frame: r for r in reps}
    GREEN, RED, WHITE = (80, 200, 120), (60, 60, 230), (250, 250, 250)
    banner = 0

    for i, (frame, lms) in enumerate(zip(frames, landmarks_per_frame)):
        img = frame.copy()
        if lms is not None:
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in lms]
            confs = [getattr(lm, conf_field, 0.0) or 0.0 for lm in lms]
            for i0, i1 in SKELETON:
                if i0 < len(pts) and i1 < len(pts):
                    ok = confs[i0] >= conf_th and confs[i1] >= conf_th
                    cv2.line(img, pts[i0], pts[i1], GREEN if ok else RED, 2)
            for p, c in zip(pts, confs):
                cv2.circle(img, p, 4, GREEN if c >= conf_th else RED, -1)

        ang = angles[i]
        cv2.putText(img, f"{side} knee: {'--' if ang is None else f'{ang:.1f}'}",
                    (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, WHITE, 2)
        if ang is None:
            cv2.putText(img, "EXCLUDED (low confidence)", (14, 66),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, RED, 2)
        done = sum(1 for r in reps if r.end_frame <= i)
        cv2.putText(img, f"reps: {done}", (14, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, WHITE, 2)
        if i in shallow:
            banner = int(fps * 1.2)
        if banner > 0:
            cv2.putText(img, "SHALLOW", (w - 190, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, RED, 3)
            banner -= 1
        vw.write(img)

    vw.release()


if __name__ == "__main__":
    raise SystemExit(main())
