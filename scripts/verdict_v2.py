#!/usr/bin/env python3
"""투자판단 v2 — 전략(펀더멘털·리스크 요인) × 위험 레짐 × 전술 플래그를 분리해 최종판단을 계산한다.

사용법:
    python3 scripts/verdict_v2.py <리포트 data.json> [--provisional-close 종가] [--inputs docs/verdict_inputs.json] [--out docs/verdict.json]

설계 원칙(검증 결과는 docs/VERDICT_RULES.md)
  1) 전략 점수: 5개 요인(각 -1/0/+1)을 '수준'이 아니라 '변화·신선도' 기준으로 판정한다.
     F1 이익추정 리비전 · F2 업황 가격 전망 · F3 밸류에이션 괴리(목표가 신선도 보정) · F4 정책·규제 리스크 · F5 수급(외국인)
  2) 위험 레짐: 10일 실현변동성·20일 고점 대비 낙폭 → 비중 배수(변동성 타깃팅). 방향 예측이 필요 없는 안전장치.
  3) 전술 플래그: 과매수(추격 자제)만 약한 근거가 있고, 과매도는 방향 우위가 없음(표본 비일관)으로 표시한다.
  4) 라벨 매핑: 전략 긍정→매수(위험 극단이면 소규모·분할), 중립→중립, 부정→매도. 위험·전술은 라벨이 아니라 비중·확신도에 반영한다.
"""
import json, sys, statistics as st, datetime

TARGET_VOL = 0.03  # 하루 변동성 목표(3%)


def load_closes(data_json, provisional=None):
    d = json.load(open(data_json, encoding="utf-8"))
    pts = [(p["date"], p["close"]) for p in d["price_trend"]["points"] if not p.get("intraday")]
    if provisional:
        pts.append(("provisional", float(provisional)))
    return pts


def price_features(pts):
    cl = [c for _, c in pts]
    i = len(cl) - 1
    r = [cl[j] / cl[j - 1] - 1 for j in range(i - 9, i + 1)]
    vol = st.pstdev(r)
    ma10 = sum(cl[i - 9:i + 1]) / 10
    dev = cl[i] / ma10 - 1
    z = dev / vol if vol > 0 else 0.0
    r3 = cl[i] / cl[i - 3] - 1
    hi20 = max(cl[max(0, i - 19):i + 1])
    dd20 = cl[i] / hi20 - 1
    return {"close": cl[i], "vol10": vol, "ma10_dev": dev, "z10": z, "ret3": r3, "dd20": dd20}


def risk_regime(f):
    if f["vol10"] >= 0.06 or f["dd20"] <= -0.25:
        lvl = "극단"
    elif f["vol10"] >= 0.04 or f["dd20"] <= -0.15:
        lvl = "높음"
    else:
        lvl = "보통"
    mult = max(0.2, min(1.0, TARGET_VOL / f["vol10"]))
    return lvl, round(mult, 2)


def tactical_flags(f):
    flags = []
    if f["z10"] >= 1.5 or f["ret3"] >= 0.10:
        flags.append("과매수: 이후 5일 평균 -5~-6%(소표본, 훈련·검증 구간 모두 음수) → 추격 매수 자제")
    if f["z10"] <= -1.5:
        flags.append("과매도: 반등·추가하락 우위 없음(훈련 +12.5% / 검증 -4.5%로 부호 불일치) → 방향 판단에 사용하지 않음")
    return flags


def strategic(inputs, f):
    fac = inputs["factors"]
    # F3 신선도 보정은 입력 가치 대신 규칙으로 재계산한다
    v = inputs["valuation"]
    gap = v["target_avg"] / (f["close"] / 10000) - 1
    ref = v["price_at_median_target_date"]
    moved = f["close"] / 10000 / ref - 1
    if abs(moved) > 0.15:
        f3, f3why = 0, f"목표가 평균 괴리 {gap*100:+.0f}%이나 목표가 중앙 보도일 이후 주가가 {moved*100:+.0f}% 움직여 목표가가 낡음(stale) → 정보 가치 없음(0)"
    elif gap > 0.30:
        f3, f3why = 1, f"목표가 평균 괴리 {gap*100:+.0f}%, 목표가 신선(보도일 이후 주가 변동 {moved*100:+.0f}%)"
    elif gap < -0.10:
        f3, f3why = -1, f"목표가 평균 괴리 {gap*100:+.0f}%(고평가)"
    else:
        f3, f3why = 0, f"목표가 평균 괴리 {gap*100:+.0f}%(중립대)"
    fac = dict(fac)
    fac["F3"] = {"value": f3, "why": f3why}
    score = sum(x["value"] for x in fac.values())
    label = "긍정" if score >= 2 else ("부정" if score <= -2 else "중립")
    return fac, score, label


def final_label(strat_label, regime, flags):
    base = {"긍정": "매수", "중립": "중립", "부정": "매도"}[strat_label]
    note = ""
    if base == "매수" and regime == "극단":
        note = "소규모·분할"
    if base == "매수" and any(x.startswith("과매수") for x in flags):
        base, note = "중립", "과매수 플래그로 신규 매수 보류"
    return base, note


def confidence(score, regime):
    if regime == "극단":
        return "낮음"
    return "높음" if abs(score) >= 3 else ("중간" if abs(score) == 2 else "낮음")


def main():
    args = [a for a in sys.argv[1:]]
    data_json = args[0]
    prov = args[args.index("--provisional-close") + 1] if "--provisional-close" in args else None
    inp = args[args.index("--inputs") + 1] if "--inputs" in args else "docs/verdict_inputs.json"
    out = args[args.index("--out") + 1] if "--out" in args else "docs/verdict.json"
    inputs = json.load(open(inp, encoding="utf-8"))
    pts = load_closes(data_json, prov)
    f = price_features(pts)
    regime, mult = risk_regime(f)
    flags = tactical_flags(f)
    fac, score, slabel = strategic(inputs, f)
    label, note = final_label(slabel, regime, flags)
    res = {
        "asof": inputs["asof"], "close": f["close"],
        "features": {k: round(v, 4) for k, v in f.items() if k != "close"},
        "factors": fac, "strategic_score": score, "strategic_label": slabel,
        "risk_regime": regime, "position_multiplier": mult, "tactical_flags": flags,
        "final": label, "final_note": note, "confidence": confidence(score, regime),
        "triggers": inputs.get("triggers", {}),
        "prev_v1": inputs.get("prev_v1"),
    }
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
