"""Kalıp–makine atama optimizasyonu (karma tamsayılı doğrusal programlama, scipy/HiGHS).

Amaç: talebi karşılamak için kullanılan toplam makine süresini (dk) en aza indirmek.
Süre = üretim süresi (sağlam adet başına dk, fire dahil) + her kullanılan (kalıp, makine) çifti için kalıp değiştirme süresi.
Kısıt: makine kapasitesi, kalıbın geçmişte çalıştığı makineler (uyumluluk), talep.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import LinearConstraint, Bounds, milp
from scipy.sparse import lil_matrix


@dataclass
class PlanResult:
    lines: pd.DataFrame        # makine, kalıp, ürün, adet, süre
    util: pd.DataFrame         # makine, kullanılan_dk, kapasite_dk
    kpi: dict
    unmet: pd.DataFrame


def pair_stats(d: pd.DataFrame, shrink: float = 2000.0) -> pd.DataFrame:
    """(kalıp, makine) bazında hız ve fire tahmini."""
    x = d[d["istasyon_tipi"] == "Enjeksiyon"].copy()
    kal_rate = (x.groupby("kalip")["fire"].sum() / x.groupby("kalip")["uretim"].sum()).to_dict()
    g = x.groupby(["kalip", "makine"]).agg(
        uretim=("uretim", "sum"), fire=("fire", "sum"), cevrim=("cevrim", "median"), nominal=("nominal_cevrim", "first"),
        goz=("goz", "median"), kalip_goz=("kalip_goz", "first") if "kalip_goz" in x.columns else ("goz", "median"),
        urun=("urun_kodu", lambda s: s.mode().iat[0] if len(s.mode()) else ""),
    ).reset_index()
    g["cyc"] = g["cevrim"].fillna(g["nominal"])
    g["goz_f"] = g["goz"].fillna(g["kalip_goz"]).fillna(1).clip(lower=1)
    kr = g["kalip"].map(kal_rate).fillna(0)
    g["fire_orani"] = ((g["fire"] + shrink * kr) / (g["uretim"] + shrink)).clip(0, 0.5)
    g["tpu"] = (g["cyc"] / 60.0) / (g["goz_f"] * (1 - g["fire_orani"]))   # sağlam adet başına dakika
    g = g[(g["cyc"] > 0) & g["tpu"].notna() & (g["uretim"] > 0)].copy()
    tot = g.groupby("kalip")["uretim"].transform("sum")
    g["pay"] = g["uretim"] / tot
    return g[["kalip", "makine", "urun", "uretim", "fire_orani", "cyc", "goz_f", "tpu", "pay"]]


def default_demand(d: pd.DataFrame, days: int, weeks: int = 4, top: int = 40) -> pd.DataFrame:
    x = d[d["istasyon_tipi"] == "Enjeksiyon"]
    end = x["tarih"].max()
    rec = x[x["tarih"] > end - pd.Timedelta(days=7 * weeks)]
    g = rec.groupby("kalip").agg(adet=("saglam", "sum"), urun=("urun_kodu", lambda s: s.mode().iat[0])).reset_index()
    g["adet"] = (g["adet"] / weeks * days / 7).round(-1)
    g = g[g["adet"] > 0].sort_values("adet", ascending=False).head(top)
    return g[["kalip", "urun", "adet"]].reset_index(drop=True)


def solve(demand: pd.DataFrame, pairs: pd.DataFrame, cap_min: dict, setup_min, time_limit: float = 25.0, setup_weight: float = 1.0) -> PlanResult:
    dem = demand[demand["adet"] > 0].reset_index(drop=True)
    P = pairs[pairs["kalip"].isin(dem["kalip"]) & pairs["makine"].isin(cap_min)].reset_index(drop=True)
    jobs = dem["kalip"].tolist()
    machines = list(cap_min)
    J, M, N = len(jobs), len(machines), len(P)
    jidx = {k: i for i, k in enumerate(jobs)}
    midx = {k: i for i, k in enumerate(machines)}
    cap = np.array([cap_min[m] for m in machines])
    D = dem["adet"].values.astype(float)

    # değişkenler: x[N] (sağlam adet), y[N] (ikili), u[J] (karşılanamayan adet)
    nv = 2 * N + J
    sm_pair = (P['makine'].map(setup_min).fillna(float(np.mean(list(setup_min.values())))).values.astype(float)
               if isinstance(setup_min, dict) else np.full(N, float(setup_min)))
    sm_avg = float(sm_pair.mean()) if N else 0.0
    pen = 1000.0
    c = np.concatenate([P["tpu"].values, sm_pair * float(setup_weight), np.full(J, pen)])
    A = lil_matrix((J + M + N, nv))
    lb = np.zeros(J + M + N)
    ub = np.zeros(J + M + N)
    for p, row in P.iterrows():
        j, m = jidx[row["kalip"]], midx[row["makine"]]
        A[j, p] = 1
        A[J + m, p] = row["tpu"]
        A[J + m, N + p] = sm_pair[p]
        bigm = min(D[j], cap[m] / row["tpu"])
        A[J + M + p, p] = 1
        A[J + M + p, N + p] = -bigm
    for j in range(J):
        A[j, 2 * N + j] = 1
        lb[j] = ub[j] = D[j]
    for m in range(M):
        lb[J + m], ub[J + m] = -np.inf, cap[m]
    lb[J + M:], ub[J + M:] = -np.inf, 0
    integrality = np.concatenate([np.zeros(N), np.ones(N), np.zeros(J)])
    bounds = Bounds(np.zeros(nv), np.concatenate([np.full(N, np.inf), np.ones(N), D]))
    res = milp(c, constraints=LinearConstraint(A.tocsr(), lb, ub), integrality=integrality, bounds=bounds,
               options={"time_limit": time_limit, "mip_rel_gap": 0.01})
    if res.x is None:
        raise RuntimeError("Çözüm bulunamadı: " + str(res.message))
    x = res.x[:N]
    y = np.round(res.x[N:2 * N])
    u = res.x[2 * N:]

    P = P.assign(x=x, y=y)
    L = P[P["x"] > 1].copy()
    L["sure_dk"] = L["x"] * L["tpu"]
    L["fire_adet"] = L["x"] * L["fire_orani"] / (1 - L["fire_orani"])
    L["setup_dk"] = L["makine"].map(setup_min).fillna(sm_avg) if isinstance(setup_min, dict) else float(setup_min)
    L["setup_dk"] = L["setup_dk"] * (L["y"] > 0)
    lines = L.rename(columns={"urun": "Ürün"})[["makine", "kalip", "Ürün", "x", "sure_dk", "fire_adet", "fire_orani", "setup_dk"]]
    lines = lines.sort_values(["makine", "sure_dk"], ascending=[True, False]).reset_index(drop=True)
    setups = int((L["y"] > 0).sum())

    use = (L.groupby("makine")["sure_dk"].sum() + L.groupby("makine")["setup_dk"].sum()).reindex(machines).fillna(0)
    util = pd.DataFrame({"makine": machines, "kullanilan_dk": use.values, "kapasite_dk": cap})

    # --- geçmiş dağılım (referans): talep, tarihsel makine paylarıyla bölünür
    B = P.copy()
    B["xb"] = B["kalip"].map(dict(zip(jobs, D))) * B["pay"]
    B = B[B["xb"] > 1]
    base_prod = float((B["xb"] * B["tpu"]).sum())
    base_setups = int((B["pay"] >= 0.05).sum())
    base_min = base_prod + base_setups * sm_avg
    base_fire = float((B["xb"] * B["fire_orani"] / (1 - B["fire_orani"])).sum())
    plan_min = float(L["sure_dk"].sum() + L["setup_dk"].sum())

    un = pd.DataFrame({"kalip": jobs, "urun": dem["urun"].values, "acik": u})
    un = un[un["acik"] > 1].sort_values("acik", ascending=False)
    kpi = {
        "plan_dk": plan_min, "base_dk": base_min, "setups": setups, "base_setups": base_setups,
        "fire_plan": float(L["fire_adet"].sum()), "fire_base": base_fire, "talep": float(D.sum()),
        "unmet": float(u.sum()), "n_jobs": J, "status": res.message,
    }
    return PlanResult(lines=lines, util=util, kpi=kpi, unmet=un)
