"""검증에 쓴 영상을 Wikimedia Commons에서 내려받는다.

영상 파일은 저장소에 커밋하지 않는다. 대신 이 스크립트로 누구나 같은 자료를
받아 같은 결과를 재현할 수 있게 한다.

전부 자유 라이선스이고, 출처와 조건은 data/SOURCES.md 에 적어 두었다.
(라이선스는 2026-08-12에 Commons API의 extmetadata 로 확인했다.)

  python src/fetch_data.py
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "data" / "videos"
UA = "aiffel-mainquest-poc/1.0 (educational; https://commons.wikimedia.org)"

# (저장할 이름, Commons 원본 URL, 라이선스, 저작자, 원본 파일명)
SOURCES = [
    (
        "cc01_squat_demo.webm",
        "https://upload.wikimedia.org/wikipedia/commons/5/5c/Squat_-_exercise_demonstration_video.webm",
        "CC BY 3.0",
        "Scott Webb (via Wikimedia Commons)",
        "File:Squat - exercise demonstration video.webm",
    ),
    (
        "cc02_squat_frontal_raise.webm",
        "https://upload.wikimedia.org/wikipedia/commons/7/7f/Squat_and_Frontal_Raise.webm",
        "CC BY-SA 4.0",
        "User:Taco fleur (Wikimedia Commons)",
        "File:Squat and Frontal Raise.webm",
    ),
    (
        "cc03_single_leg_squat.webm",
        "https://upload.wikimedia.org/wikipedia/commons/1/16/Basic_single_leg_squat.webm",
        "CC BY-SA 4.0",
        "User:RickyBennison (Wikimedia Commons)",
        "File:Basic single leg squat.webm",
    ),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    failed = []
    for name, url, lic, author, title in SOURCES:
        out = DEST / name
        if out.exists():
            print(f"[건너뜀] {name}  (이미 있음, sha256={sha256(out)[:16]}…)")
            continue
        print(f"[받는 중] {name}  ← {title}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r, out.open("wb") as f:
                f.write(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"          실패: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(name)
            continue
        print(f"          {out.stat().st_size/1e6:.1f}MB  {lic} · {author}")
        print(f"          sha256={sha256(out)[:16]}…")

    if failed:
        print(f"\n[경고] 받지 못한 파일: {', '.join(failed)}", file=sys.stderr)
        print("       data/SOURCES.md 의 주소에서 직접 받아 data/videos/ 에 넣으십시오.",
              file=sys.stderr)
        return 1

    print(f"\n완료. {DEST} 에 {len(SOURCES)}건.")
    print("출처와 라이선스: data/SOURCES.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
