"""data/videos 의 모든 영상을 한 묶음으로 처리하고 곧바로 검증까지 돌린다.

  python src/run_all.py
  python src/run_all.py --target-angle 95 --confidence-threshold 0.6

판정에 쓰는 값은 그대로 run_poc.py 로 넘어간다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".ogv"}

# run_poc.py 로 그대로 넘길 인자들
PASS_THROUGH = [
    "--confidence-threshold", "--confidence-field", "--down-angle", "--up-angle",
    "--target-angle", "--smooth-window", "--min-frames-down", "--side",
    "--min-pose-detection-confidence", "--min-pose-presence-confidence",
    "--min-tracking-confidence", "--rotate", "--model",
]


def main() -> int:
    p = argparse.ArgumentParser(
        description="영상 전부를 한 묶음으로 처리하고 검증까지 실행한다.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--videos", type=Path, default=REPO / "data" / "videos")
    p.add_argument("--run-stamp", default=None, help="결과 폴더 이름 (기본: 실행 시각)")
    p.add_argument("--no-overlay", action="store_true")
    p.add_argument("--skip-eval", action="store_true", help="검증을 돌리지 않음")
    for flag in PASS_THROUGH:
        p.add_argument(flag, default=None)
    a, unknown = p.parse_known_args()
    if unknown:
        print(f"[오류] 모르는 인자: {unknown}", file=sys.stderr)
        return 2

    vids = sorted(v for v in a.videos.iterdir()
                  if v.is_file() and v.suffix.lower() in VIDEO_EXT) if a.videos.exists() else []
    if not vids:
        print(f"[오류] 처리할 영상이 없습니다: {a.videos}\n"
              f"       측면에서 찍은 영상을 {a.videos} 에 넣으십시오. "
              "파일 이름이 정답 파일의 video_id 가 됩니다.\n"
              f"       읽는 확장자: {', '.join(sorted(VIDEO_EXT))}", file=sys.stderr)
        return 2

    stamp = a.run_stamp or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = REPO / "results" / stamp
    extra: list[str] = []
    for flag in PASS_THROUGH:
        val = getattr(a, flag.lstrip("-").replace("-", "_"))
        if val is not None:
            extra += [flag, str(val)]
    if a.no_overlay:
        extra.append("--no-overlay")

    print(f"영상 {len(vids)}건 → {run_dir}\n")
    failed: list[str] = []
    for v in vids:
        print(f"── {v.name} " + "─" * max(0, 60 - len(v.name)))
        r = subprocess.run(
            [PY, str(REPO / "src" / "run_poc.py"), "--video", str(v),
             "--run-stamp", stamp] + extra)
        if r.returncode != 0:
            failed.append(v.name)
        print()

    if failed:
        print(f"[경고] 처리에 실패한 영상: {', '.join(failed)}\n")

    if a.skip_eval:
        return 1 if failed else 0

    print("=" * 70)
    r = subprocess.run([PY, str(REPO / "src" / "evaluate.py"), "--run", str(run_dir)])
    return r.returncode or (1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
