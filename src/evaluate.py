"""개선 효과 검증 — PoC 결과를 '돌리기 전에 적어 둔 정답'과 대조한다.

정답(data/ground_truth.csv)은 모델을 돌리기 전에 사람이 적은 것이다.
결과를 본 뒤에 정답을 정하면 이미 나온 답 쪽으로 기준이 기울고,
그렇게 만든 채점표로는 아무것도 판단할 수 없다.

사용 예
-------
  python src/evaluate.py --run results/2026-08-12T15-30-00
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PoC 결과를 정답과 대조한다.")
    p.add_argument("--run", required=True, type=Path,
                   help="results/<실행시각> 폴더 (그 아래 영상별 폴더가 있음)")
    p.add_argument("--truth", type=Path, default=REPO / "data" / "ground_truth.csv")
    p.add_argument("--s1-reps-match", type=int, default=18,
                   help="성공 기준 S1: 20회 중 몇 회 이상 일치해야 하는가")
    p.add_argument("--s1-total", type=int, default=20)
    p.add_argument("--s2-f1", type=float, default=0.70,
                   help="성공 기준 S2: 얕은 회차 판정 F1 하한")
    p.add_argument("--out", type=Path, default=None,
                   help="결과 마크다운 저장 경로 (기본: <run>/evaluation.md)")
    return p.parse_args()


def parse_shallow(s: str) -> set[int]:
    s = (s or "").strip().strip('"')
    if not s:
        return set()
    return {int(x) for x in s.replace(" ", "").split(",") if x}


def main() -> int:
    a = parse_args()
    if not a.truth.exists():
        print(f"[오류] 정답 파일이 없습니다: {a.truth}")
        return 2
    if not a.run.exists():
        print(f"[오류] 결과 폴더가 없습니다: {a.run}")
        return 2

    truth: dict[str, dict] = {}
    # '#'로 시작하는 주석 줄을 걷어낸 뒤 파싱한다. 정답 파일 맨 위에 설명을 달 수 있게.
    body = [ln for ln in a.truth.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not body:
        print(f"[오류] 정답 파일에 내용이 없습니다: {a.truth}\n"
              "       data/ground_truth.EXAMPLE.csv 를 참고해 채우십시오.")
        return 2
    reader = csv.DictReader(body)
    if not reader.fieldnames or "video_id" not in reader.fieldnames:
        print(f"[오류] 정답 파일에 video_id 열이 없습니다: {reader.fieldnames}")
        return 2
    for r in reader:
        vid = (r.get("video_id") or "").strip()
        if vid:
            truth[vid] = {
                "reps_true": int(r["reps_true"]),
                "shallow_true": parse_shallow(r.get("shallow_reps", "")),
                "note": (r.get("note") or "").strip(),
                "manual_seconds": float(r["manual_seconds"]) if r.get("manual_seconds") else None,
            }

    if not truth:
        print(f"[오류] 정답 파일에 행이 없습니다: {a.truth}\n"
              "       모델을 돌리기 전에 data/ground_truth.csv 를 먼저 채우십시오.\n"
              "       (양식은 data/ground_truth.EXAMPLE.csv)")
        return 2

    rows = []
    tp = fp = fn = 0
    reps_hit = reps_total = 0
    poc_seconds = manual_seconds = 0.0
    missing: list[str] = []

    for vid, t in sorted(truth.items()):
        sdir = a.run / vid
        sfile = sdir / "summary.json"
        if not sfile.exists():
            missing.append(vid)
            rows.append({"video": vid, "status": "결과 없음", **t})
            continue
        s = json.loads(sfile.read_text(encoding="utf-8"))
        pred_reps = s["stats"]["n_reps"]
        pred_shallow = set(s["shallow_reps"])

        reps_total += 1
        ok_reps = pred_reps == t["reps_true"]
        reps_hit += int(ok_reps)

        v_tp = len(pred_shallow & t["shallow_true"])
        v_fp = len(pred_shallow - t["shallow_true"])
        v_fn = len(t["shallow_true"] - pred_shallow)
        tp, fp, fn = tp + v_tp, fp + v_fp, fn + v_fn

        poc_seconds += s["elapsed_seconds"]
        if t["manual_seconds"]:
            manual_seconds += t["manual_seconds"]

        rows.append({
            "video": vid,
            "status": "",
            "reps_true": t["reps_true"],
            "reps_pred": pred_reps,
            "reps_ok": ok_reps,
            "shallow_true": sorted(t["shallow_true"]),
            "shallow_pred": sorted(pred_shallow),
            "tp": v_tp, "fp": v_fp, "fn": v_fn,
            "excluded_ratio": s["stats"]["excluded_ratio"],
            "elapsed": s["elapsed_seconds"],
            "video_sec": s["video_seconds"],
            "note": t["note"],
        })

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    # 성공 기준 판정 — 반복 횟수는 '영상 단위 일치'가 아니라 '회 단위 일치'로 환산.
    # 결과가 없는 영상은 분모·분자 어디에도 넣지 않는다. 넣지 않으면 100% 통과로
    # 보이고, 0으로 넣으면 모델이 틀린 것처럼 보인다. 둘 다 사실이 아니므로
    # '평가하지 못함'으로 따로 센다.
    evaluated = [r for r in rows if r.get("status") == ""]
    total_reps_true = sum(r["reps_true"] for r in evaluated)
    total_abs_err = sum(abs(r["reps_pred"] - r["reps_true"]) for r in evaluated)
    matched_reps = max(0, total_reps_true - total_abs_err)
    s1_rate = matched_reps / total_reps_true if total_reps_true else 0.0

    # 평가된 영상이 하나도 없으면 판정 자체가 성립하지 않는다.
    if not evaluated:
        print(f"[오류] 결과가 있는 영상이 하나도 없습니다.\n"
              f"       정답에 적힌 영상: {', '.join(sorted(truth))}\n"
              f"       찾은 결과 폴더 : {a.run}/<video_id>/summary.json\n"
              "       먼저 src/run_poc.py 로 각 영상을 처리하십시오.")
        return 2

    s1_pass = s1_rate >= (a.s1_reps_match / a.s1_total)

    # S2는 '판정할 대상'이 자료에 있어야 평가가 성립한다.
    # 정답에도 예측에도 얕은 회차가 하나도 없으면 F1은 0으로 계산되지만,
    # 그것은 '못 맞혔다'가 아니라 '맞힐 것이 없었다'는 뜻이다.
    # 이 둘을 구분하지 않으면 자료의 한계를 도구의 실패로 잘못 적게 된다.
    s2_evaluable = (tp + fp + fn) > 0
    s2_pass = (f1 >= a.s2_f1) if s2_evaluable else None
    n_shallow_true = sum(len(t["shallow_true"]) for t in truth.values())

    lines: list[str] = []
    A = lines.append
    A("# 개선 효과 검증 결과\n")
    A("> 정답(`data/ground_truth.csv`)은 **모델을 돌리기 전에** 적은 것입니다.\n")
    A(f"- 결과 폴더: `{a.run}`")
    A(f"- 평가한 영상: {len(evaluated)}건 / 정답에 적힌 영상: {len(truth)}건")
    if missing:
        A(f"- ⚠️ 결과가 없어 평가하지 못한 영상: {', '.join(missing)} "
          f"— 아래 판정에서 제외했습니다")
    A(f"- 평가한 영상의 총 반복(정답): {total_reps_true}회\n")

    A("## 1. 영상별 대조\n")
    A("| 영상 | 정답 반복 | PoC 반복 | 일치 | 정답 얕은 회차 | PoC 얕은 회차 | 제외율 | 처리(초) | 비고 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r.get("status"):
            A(f"| {r['video']} | {r.get('reps_true','')} | — | — | — | — | — | — | {r['status']} |")
            continue
        A(f"| {r['video']} | {r['reps_true']} | {r['reps_pred']} | "
          f"{'⭕' if r['reps_ok'] else '❌'} | "
          f"{r['shallow_true'] or '—'} | {r['shallow_pred'] or '—'} | "
          f"{r['excluded_ratio']*100:.1f}% | {r['elapsed']:.1f} | {r['note']} |")

    A("\n## 2. 성공 기준 판정\n")
    A("| 기준 | 내용 | 목표 | 실측 | 판정 |")
    A("|---|---|---|---|---|")
    A(f"| **S1** | 반복 횟수 일치 | {a.s1_reps_match}/{a.s1_total} "
      f"({a.s1_reps_match/a.s1_total*100:.0f}%) | "
      f"{matched_reps}/{total_reps_true} ({s1_rate*100:.1f}%) | "
      f"{'**통과**' if s1_pass else '**미달**'} |")
    if s2_evaluable:
        A(f"| **S2** | 얕은 회차 판정 F1 | {a.s2_f1:.2f} | {f1:.3f} "
          f"(정밀도 {prec:.3f} / 재현율 {rec:.3f}) | "
          f"{'**통과**' if s2_pass else '**미달**'} |")
    else:
        A(f"| **S2** | 얕은 회차 판정 F1 | {a.s2_f1:.2f} | — | **평가 불가** |")
        A("\n> **S2는 '미달'이 아니라 '평가 불가'입니다.**  \n"
          f"> 정답에 적힌 얕은 회차가 **{n_shallow_true}개**이고 도구도 하나도 표시하지 않았습니다. "
          "**판정할 대상 자체가 자료에 없었습니다.**  \n"
          "> 목표 각도를 올리면 얕은 회차가 '생겨서' 통과한 것처럼 보이지만, "
          "임계값을 임의로 정한 뒤 만족했다고 적으면 그 채점표로는 아무것도 판단할 수 없습니다.  \n"
          "> → 다음 단계는 **얕은 회차가 포함된 자료를 만드는 것**입니다. "
          "(`docs/04_한계와_다음단계.md` 5절)")

    if poc_seconds:
        A(f"\n## 3. 기존 방식과의 비교\n")
        A("| | 기존 (사람이 영상 보며 셈) | PoC |")
        A("|---|---|---|")
        if manual_seconds:
            A(f"| 총 소요 | {manual_seconds:.0f}초 | {poc_seconds:.0f}초 |")
            A(f"| 배속 | 1.0× | {manual_seconds/poc_seconds:.1f}× |")
        else:
            A(f"| 총 소요 | (미측정) | {poc_seconds:.0f}초 |")
        A(f"| 회차별 기록 | 남지 않음 | `reps.csv`로 남음 |")
        A(f"| 동시 처리 | 불가 | 영상 수만큼 가능 |")

    A("\n## 4. 혼동 내역 (얕은 회차 판정)\n")
    A(f"- 맞게 잡음(TP): {tp}")
    A(f"- 잘못 잡음(FP): {fp}  ← 얕지 않은데 얕다고 표시")
    A(f"- 놓침(FN): {fn}  ← 얕은데 표시하지 못함")

    A("\n## 5. 결론\n")
    if s1_pass and s2_pass is True:
        A("**두 기준 모두 통과했습니다.** → 구축 대상으로 판단합니다.")
    else:
        A("**기준을 넘지 못했거나 평가하지 못한 항목이 있습니다.**")
        if not s1_pass:
            A(f"- **S1 미달**: 반복 횟수 일치율 {s1_rate*100:.1f}% "
              f"(목표 {a.s1_reps_match/a.s1_total*100:.0f}%)")
        if s2_pass is None:
            A("- **S2 평가 불가**: 자료에 얕은 회차가 없어 판정할 대상이 없었습니다. "
              "도구의 실패가 아니라 **자료의 한계**입니다.")
        elif not s2_pass:
            A(f"- **S2 미달**: 얕은 회차 판정 F1 {f1:.3f} (목표 {a.s2_f1:.2f})")
        A("\n> PoC의 산출물은 작동하는 물건이 아니라 판단입니다. "
          "기준을 못 넘은 이유가 결과물입니다. `docs/04_한계와_다음단계.md`에 정리했습니다.")

    md = "\n".join(lines) + "\n"
    out = a.out or (a.run / "evaluation.md")
    out.write_text(md, encoding="utf-8")

    metrics = {
        "n_videos": reps_total,
        "total_reps_true": total_reps_true,
        "matched_reps": matched_reps,
        "s1_rate": s1_rate, "s1_pass": s1_pass,
        "precision": prec, "recall": rec, "f1": f1, "s2_pass": s2_pass, "s2_evaluable": s2_evaluable,
        "n_shallow_true": n_shallow_true,
        "tp": tp, "fp": fp, "fn": fn,
        "poc_seconds": poc_seconds, "manual_seconds": manual_seconds or None,
    }
    (a.run / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(md)
    print(f"저장: {out}")
    print(f"저장: {a.run / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
