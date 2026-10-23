"""Kalıp değişimi kaybı: olayları bulur, kaybı ölçer, kampanya yapısını çıkarır, planları karşılaştırır.

Tanımlar
  * Olay: aynı makinede bir önceki kayıttan farklı kalıp çalışan kayıt VEYA Excel'de 'kalıp değişti' işaretli kayıt.
    Kayıtlar gerçek zaman sırasına dizilir (tarih → Sabah → Akşam → satır sırası); aksi halde değişimler yanlış sayılır.
  * Kampanya: aynı makinede aynı kalıbın art arda çalıştığı kayıt dizisi.
  * Süre: Excel'deki D2 (kalıp değişimi duruşu) kaydı; yoksa makinenin beklenen değişim süresi (tahmini olarak işaretlenir).
  * İlk deneme kaybı: olay kaydındaki F1 fire adedi; ayrıca kalıbın sağlam adet başına süresiyle dakikaya çevrilir.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import planner
from .data import chrono
from .util import bars, clean, dlabel, fint, fnum, kpi, table

SHIFT_MIN = 720
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


# ------------------------------------------------------------------ olaylar
def _expected_setup(x: pd.DataFrame, shrink: float = 5.0) -> dict:
    """Makine bazında beklenen değişim süresi (dk): kayıtlı sürelerin ortancası, az veri varsa genel ortancaya büzülür."""
    r = x[x["olay"] & (x["D2"] > 0)]
    glob = float(r["D2"].median()) if len(r) else 60.0
    out = {}
    for mk, g in r.groupby("makine"):
        n = len(g)
        out[mk] = float((n * g["D2"].median() + shrink * glob) / (n + shrink))
    for mk in x["makine"].unique():
        out.setdefault(mk, glob)
    out["_glob"] = glob
    return out


def events(d: pd.DataFrame):
    """(kayıtlar, olaylar, makine_beklenen_süre) döndürür."""
    x = chrono(d[d["istasyon_tipi"] == "Enjeksiyon"]).copy()
    g = x.groupby("makine")
    x["onceki"] = g["kalip"].shift(1)
    x["ch"] = (x["kalip"] != x["onceki"]) & x["onceki"].notna()
    x["olay"] = x["ch"] | (x["kalip_degisti"].fillna(0) > 0)
    x["kamp"] = x.groupby("makine")["ch"].cumsum()
    setup = _expected_setup(x)
    ev = x[x["olay"]].copy()
    ev["kayitli"] = ev["D2"] > 0
    ev["sure"] = ev["D2"].where(ev["kayitli"], ev["makine"].map(setup))
    # ilk deneme kaybı: F1 adedi, kalıbın sağlam adet başına süresiyle dakikaya çevrilir
    try:
        ps = planner.pair_stats(d)
        tpu = (ps.assign(w=ps["uretim"] * ps["tpu"]).groupby("kalip").apply(lambda t: t["w"].sum() / t["uretim"].sum())).to_dict()
    except Exception:  # noqa: BLE001
        tpu = {}
    med_tpu = float(np.median(list(tpu.values()))) if tpu else 0.05
    ev["f1"] = ev["F1"].fillna(0)
    ev["f1_dk"] = ev["f1"] * ev["kalip"].map(tpu).fillna(med_tpu)
    ev["hb"] = ev["tarih"] - pd.to_timedelta(ev["tarih"].dt.dayofweek, unit="D")
    return x, ev, setup


def _campaigns(x: pd.DataFrame) -> pd.DataFrame:
    c = x.groupby(["makine", "kamp"]).agg(kalip=("kalip", "first"), kayit=("kalip", "size"), adet=("saglam", "sum"), bas=("tarih", "min")).reset_index()
    return c


def weekly_series(d: pd.DataFrame) -> pd.DataFrame:
    """Tam haftalar (en az 4 farklı gün): değişim sayısı, toplam kayıp saati, ortalama kayıtlı süre."""
    x, ev, _ = events(d)
    x = x.assign(hb=x["tarih"] - pd.to_timedelta(x["tarih"].dt.dayofweek, unit="D"))
    gun = x.groupby("hb")["tarih"].nunique()
    ok = gun[gun >= 4].index
    w = pd.DataFrame(index=sorted(ok))
    g = ev.groupby("hb")
    w["n"] = g.size().reindex(w.index).fillna(0)
    w["kayip_sa"] = ((g["sure"].sum() + g["f1_dk"].sum()) / 60).reindex(w.index).fillna(0)
    w["ort_dk"] = ev[ev["kayitli"]].groupby("hb")["D2"].mean().reindex(w.index)
    w.index.name = "hb"
    return w


# ------------------------------------------------------------------ kayıp özeti
def summary(d: pd.DataFrame) -> dict:
    x, ev, setup = events(d)
    if len(ev) < 10:
        return {"insights": ["Bu dönemde yeterli kalıp değişimi olayı yok. Dönemi genişlet."], "kpis": []}
    n = len(ev)
    sure_h = float(ev["sure"].sum() / 60)
    kay_h = float(ev.loc[ev["kayitli"], "sure"].sum() / 60)
    tah_h = sure_h - kay_h
    f1 = float(ev["f1"].sum())
    f1_h = float(ev["f1_dk"].sum() / 60)
    tot_h = sure_h + f1_h
    cap_h = len(x) * SHIFT_MIN / 60
    p_rec = float(ev["kayitli"].mean())
    rec = ev.loc[ev["kayitli"], "D2"]
    mode_v = float(rec.mode().iat[0]) if len(rec) else float("nan")
    mode_p = float((rec == mode_v).mean()) if len(rec) else float("nan")
    avg_rec = float(rec.mean()) if len(rec) else float("nan")

    # kırılımlar
    def breakdown(key):
        g = ev.groupby(key)
        t = pd.DataFrame({"n": g.size(), "sure": g["sure"].sum() / 60, "f1": g["f1"].sum(), "ort": g["sure"].mean(),
                          "kay": g["kayitli"].mean() * 100})
        return t
    mk = breakdown("makine").sort_values("sure", ascending=False)
    mk["vard"] = x.groupby("makine").size().reindex(mk.index)
    mk["oran"] = mk["n"] / mk["vard"] * 100
    mk_t = mk.reset_index().rename(columns={"makine": "Makine", "n": "Değişim", "sure": "Kayıp süre (saat)", "ort": "Ort. süre (dk)", "f1": "İlk deneme fire", "kay": "Süre kayıtlı %", "oran": "100 vardiyada değişim"})
    mk_t = mk_t[["Makine", "Değişim", "Kayıp süre (saat)", "Ort. süre (dk)", "İlk deneme fire", "100 vardiyada değişim", "Süre kayıtlı %"]]

    sh = breakdown(ev["vardiya"].astype(str)).drop(index=[i for i in ("?", "nan") if i in ev["vardiya"].astype(str).unique()], errors="ignore")
    sh_rec = x.groupby(x["vardiya"].astype(str)).size()
    wd = breakdown(ev["tarih"].dt.dayofweek)
    wd.index = [DAYS_TR[int(i)] for i in wd.index]
    wd_rec = x.groupby(x["tarih"].dt.dayofweek).size()
    wd["oran"] = wd["n"].values / np.array([wd_rec.get(DAYS_TR.index(i), np.nan) for i in wd.index]) * 100
    mo = breakdown(ev["tarih"].dt.month)
    mo.index = [MONTHS_TR[int(i) - 1] for i in mo.index]

    # kalıp bazında ve kampanya yapısı
    camp = _campaigns(x)
    cs = camp.groupby("kalip").agg(kampanya=("kamp", "size"), kayit=("kayit", "mean"), adet=("adet", "mean"))
    kg = ev.groupby("kalip").agg(n=("sure", "size"), sure=("sure", "sum"), f1=("f1", "sum"))
    km = cs.join(kg, how="left").fillna({"n": 0, "sure": 0, "f1": 0})
    km["sa"] = km["sure"] / 60
    top = km.sort_values("sa", ascending=False).head(15).reset_index()
    top_t = top.rename(columns={"kalip": "Kalıp", "kampanya": "Kampanya", "kayit": "Ort. kampanya (vardiya)", "adet": "Ort. kampanya (adet)", "sa": "Kayıp süre (saat)", "f1": "İlk deneme fire"})
    top_t = top_t[["Kalıp", "Kampanya", "Ort. kampanya (vardiya)", "Ort. kampanya (adet)", "Kayıp süre (saat)", "İlk deneme fire"]]

    n_camp = len(camp) - camp["kamp"].eq(0).sum() * 0
    short = camp[camp["kayit"] <= 2]
    p_short = float(len(short) / len(camp))
    rep = km[km["kampanya"] >= 5]
    rep_share = float(rep["sure"].sum() / max(km["sure"].sum(), 1) * 100)
    top5 = km.sort_values("sure", ascending=False).head(5)
    top5_share = float(top5["sure"].sum() / max(km["sure"].sum(), 1) * 100)
    mk_top = mk.index[0]
    mk3_share = float(mk["sure"].head(3).sum() / max(mk["sure"].sum(), 1) * 100)
    slow = mk[mk["n"] >= 15].sort_values("ort", ascending=False)
    fast = mk[mk["n"] >= 15].sort_values("ort")

    ins = [f"Dönemde **{fint(n)}** kalıp değişimi var; toplam kayıp **{fnum(tot_h, 0)} saat** (makine-vardiya zamanının %{fnum(tot_h / cap_h * 100, 1)}'i). "
           f"Bunun {fnum(kay_h, 0)} saati kayıtlı süre, {fnum(tah_h, 0)} saati süresi girilmemiş değişimlerin tahmini."]
    ins.append(f"Kaybın %{fnum(mk3_share, 0)}'i üç makinede: **{mk.index[0]}**, **{mk.index[1]}**, **{mk.index[2]}**. "
               f"En çok kalıp değiştiren makine **{mk.sort_values('n', ascending=False).index[0]}** ({fint(mk['n'].max())} değişim).")
    ins.append(f"En çok kayıp yaratan 5 kalıp toplamın %{fnum(top5_share, 0)}'ini oluşturuyor: " + ", ".join(f"**{k}**" for k in top5.index) + ".")
    ins.append(f"Kampanyaların %{fnum(p_short * 100, 0)}'i en fazla 2 vardiya sürüyor (kısa kampanya = her biri için tam bir değişim kaybı). "
               f"{len(rep)} kalıp dönemde 5 kez ya da daha fazla yeniden takılmış; bunlar toplam değişim süresinin %{fnum(rep_share, 0)}'ini oluşturuyor: kampanyaları birleştirmek burada kazandırır.")
    if len(slow) >= 2:
        ins.append(f"Ortalama değişim süresi en uzun makine **{slow.index[0]}** ({fnum(slow['ort'].iloc[0], 0)} dk), en kısa **{fast.index[0]}** ({fnum(fast['ort'].iloc[0], 0)} dk). "
                   "Bu fark ürün ve kalıp büyüklüğünden de gelebilir; yine de iyi çalışan yöntemi öğrenmek için ilk bakılacak yer burası.")
    ins.append(f"İlk deneme kaybı: **{fint(f1)}** adet fire (yaklaşık {fnum(f1_h, 0)} saat makine zamanı karşılığı). Süre kaybının yanında küçük; asıl kayıp süre.")
    ins.append(f"Veri güvenilirliği: süreler değişimlerin %{fnum(p_rec * 100, 0)}'inde kayıtlı; kayıtlı sürelerin %{fnum(mode_p * 100, 0)}'i tam {fnum(mode_v, 0)} dk. "
               "Yuvarlak değerler ölçüm yerine tahmin olabilir; Saha kaydı sayfasındaki kronometre bu belirsizliği kaldırmak için var.")

    wk = weekly_series(d)
    wk_bars = bars([dlabel(i) for i in wk.index], wk["kayip_sa"].values, "orange")
    hist = rec.value_counts().sort_index()
    hist_bars = bars([f"{int(k)} dk" for k in hist.index], hist.values, ["amber" if k == mode_v else "slate" for k in hist.index], [f"{int(v)} kez" for v in hist.values])

    clamp = lambda df, c: df[c].values  # noqa: E731
    out = {
        "insights": ins,
        "kpis": [
            kpi("Toplam kayıp", f"{fnum(tot_h, 0)} saat", f"kayıtlı {fnum(kay_h, 0)} + tahmini {fnum(tah_h, 0)} + ilk deneme {fnum(f1_h, 0)}", "red", wk["kayip_sa"].values),
            kpi("Kalıp değişimi", fint(n), f"{fnum(n / max(x['tarih'].nunique(), 1) * 7, 1)} değişim / hafta", "amber", wk["n"].values),
            kpi("Ortalama süre", f"{fnum(avg_rec, 0)} dk", f"kayıtlı değişimlerin ortalaması", None, wk["ort_dk"].fillna(avg_rec).values),
            kpi("İlk deneme fire", fint(f1), f"yaklaşık {fnum(f1_h, 0)} saat karşılığı", "red"),
            kpi("Kısa kampanya payı", f"%{fnum(p_short * 100, 0)}", "en fazla 2 vardiya süren kampanyalar", "amber"),
            kpi("Süre kaydı", f"%{fnum(p_rec * 100, 0)}", f"%{fnum(mode_p * 100, 0)}'i tam {fnum(mode_v, 0)} dk", "slate"),
        ],
        "machines": bars(mk.index, mk["sure"], "orange", [f"{fnum(v, 0)} sa · {fint(nn)} değişim" for v, nn in zip(mk["sure"], mk["n"])]),
        "machine_table": table(mk_t, {"Değişim": "int", "Kayıp süre (saat)": "num1", "Ort. süre (dk)": "num1", "İlk deneme fire": "int", "100 vardiyada değişim": "num1", "Süre kayıtlı %": "num0"}),
        "shift": bars(sh.index, sh["ort"], "teal", [f"ort. {fnum(a, 0)} dk · {fint(nn)} değişim · 100 vardiyada {fnum(nn / sh_rec.get(i, np.nan) * 100, 1)}" for i, a, nn in zip(sh.index, sh["ort"], sh["n"])]),
        "weekday": bars(wd.index, wd["oran"], "amber", [f"100 vardiyada {fnum(r, 1)} · {fint(nn)} değişim · ort. {fnum(a, 0)} dk" for r, nn, a in zip(wd["oran"], wd["n"], wd["ort"])]),
        "months": bars(mo.index, mo["sure"], "orange", [f"{fnum(v, 0)} sa · {fint(nn)} değişim" for v, nn in zip(mo["sure"], mo["n"])]),
        "weekly": wk_bars,
        "weekly_avg": float(wk["kayip_sa"].mean()) if len(wk) else None,
        "hist": hist_bars,
        "molds": table(top_t, {"Kampanya": "int", "Ort. kampanya (vardiya)": "num1", "Ort. kampanya (adet)": "int", "Kayıp süre (saat)": "num1", "İlk deneme fire": "int"}),
        "note": ("Değişim = aynı makinede bir önceki kayıttan farklı kalıp (ya da Excel'de 'kalıp değişti' işareti). Süresi girilmemiş değişimler makinenin beklenen süresiyle tahmin edilir. "
                 "Kampanya = aynı makinede aynı kalıbın art arda çalıştığı kayıtlar."),
    }
    return clean(out)


# ------------------------------------------------------------------ plan karşılaştırması
# senaryo = kalıp talebinin kaç partiye bölündüğü (stok/teslim için sık parti ↔ az değişim dengesi)
SCEN = [(1, "Tek kampanya", "Her kalıp dönemde tek seferde, tek kampanya olarak çalışır (en az değişim)"),
        (2, "İki parti", "Her kalıbın talebi iki partiye bölünür (ör. iki haftada bir teslim)"),
        (4, "Dört parti", "Her kalıbın talebi dört partiye bölünür (ör. haftalık teslim)")]


def default_demand(d: pd.DataFrame, days: int, weeks: int = 4, top: int = 40) -> pd.DataFrame:
    return planner.default_demand(d, days, weeks, top)


def _shifts(L: pd.DataFrame, pairs: pd.DataFrame) -> dict:
    """Plan, kalıbı geçmişte çalıştığı makineden başka makineye alıyorsa: fire ve makine süresi farkı."""
    out = []
    for kal, z in L.groupby("kalip"):
        pp = pairs[pairs["kalip"] == kal]
        if pp.empty or z["x"].sum() <= 1:
            continue
        hist = pp.sort_values("pay", ascending=False).iloc[0]
        h_tpu = float((pp["pay"] * pp["tpu"]).sum())
        h_fire = float((pp["pay"] * pp["fire_orani"]).sum())
        x = float(z["x"].sum())
        p_tpu = float(z["sure_dk"].sum() / x)
        p_fire = float((z["x"] * z["fire_orani"]).sum() / x)
        main = z.sort_values("x", ascending=False).iloc[0]["makine"]
        if main == hist["makine"]:
            continue
        sav = (h_tpu - p_tpu) * x / 60
        if sav < 0.5:
            continue
        out.append({"Kalıp": kal, "Geçmişte": f"{hist['makine']} (%{hist['pay'] * 100:.0f})", "Planda": ", ".join(sorted(set(z["makine"]))),
                    "Fire geçmiş %": h_fire * 100, "Fire plan %": p_fire * 100, "Kazanç (makine saati)": sav})
    if not out:
        return {}
    df = pd.DataFrame(out).sort_values("Kazanç (makine saati)", ascending=False).head(15)
    return table(df, {"Fire geçmiş %": "pct1", "Fire plan %": "pct1", "Kazanç (makine saati)": "num1"})


def plan_compare(d: pd.DataFrame, demand: list, days: int, shifts: int, avail: float, time_limit: float = 8.0) -> dict:
    x, ev, setup = events(d)
    machines = sorted(x["makine"].unique())
    dem = pd.DataFrame(demand)
    dem["kalip"] = dem["kalip"].astype(str).str.strip().str.upper()
    dem["adet"] = pd.to_numeric(dem["adet"], errors="coerce").fillna(0)
    if "urun" not in dem:
        dem["urun"] = ""
    dem = dem[dem["adet"] > 0].reset_index(drop=True)
    pairs = planner.pair_stats(d)
    cap_each = days * shifts * SHIFT_MIN * avail / 100
    setup_map = {m: setup.get(m, setup["_glob"]) for m in machines}

    # geçmiş düzen: her kalıp geçmişteki ortalama kampanya büyüklüğüyle çalıştırılır
    camp = _campaigns(x)
    ca = camp.groupby("kalip")["adet"].sum() / camp.groupby("kalip").size()
    ca_glob = float(ca.median()) if len(ca) else 5000.0
    P = pairs[pairs["kalip"].isin(dem["kalip"])].copy()
    P["s"] = P["makine"].map(setup_map).fillna(setup["_glob"])
    avg_setup = (P.assign(w=P["pay"] * P["s"]).groupby("kalip")["w"].sum()).to_dict()
    base_ch = 0
    base_dk = 0.0
    for r in dem.itertuples():
        size = float(ca.get(r.kalip, ca_glob)) or ca_glob
        k = max(1, math.ceil(r.adet / max(size, 1.0)))
        base_ch += k
        base_dk += k * float(avg_setup.get(r.kalip, setup["_glob"]))
    f1_pc = float(ev["f1"].sum() / max(len(ev), 1))
    # üretim süresi: tarihsel makine dağılımıyla
    B = pairs[pairs["kalip"].isin(dem["kalip"])].copy()
    B["xb"] = B["kalip"].map(dict(zip(dem["kalip"], dem["adet"]))) * B["pay"]
    base_prod = float((B["xb"] * B["tpu"]).sum())

    rows, lines_by = [], {}
    shift_by, fire_pl = {}, {}
    for k, name, desc in SCEN:
        dk = pd.concat([dem.assign(kalip=dem["kalip"] + (f"#{i + 1}" if k > 1 else ""), adet=dem["adet"] / k) for i in range(k)], ignore_index=True)
        pk = pd.concat([pairs[pairs["kalip"].isin(dem["kalip"])].assign(kalip=lambda t, i=i: t["kalip"] + (f"#{i + 1}" if k > 1 else "")) for i in range(k)], ignore_index=True)
        try:
            r = planner.solve(dk, pk, {m: cap_each for m in machines}, setup_map, time_limit=time_limit)
        except Exception as e:  # noqa: BLE001
            rows.append({"Senaryo": name, "Açıklama": f"çözülemedi: {e}"})
            continue
        L = r.lines.copy()
        L["kalip"] = L["kalip"].str.replace(r"#\d+$", "", regex=True)
        fire_pl[name] = (float(r.kpi["fire_plan"]), float(r.kpi["fire_base"]))
        shift_by[name] = _shifts(L, pairs)
        ch = int((L["setup_dk"] > 0).sum())
        ch_h = float(L["setup_dk"].sum() / 60)
        pr_h = float(L["sure_dk"].sum() / 60)
        unmet = float(r.kpi["unmet"])
        rows.append({"Senaryo": name, "Açıklama": desc, "Değişim": ch, "Değişim süresi (saat)": ch_h, "Üretim süresi (saat)": pr_h, "Toplam makine (saat)": ch_h + pr_h,
                     "İlk deneme fire": ch * f1_pc, "Karşılanamayan": unmet})
        t = L.rename(columns={"makine": "Makine", "kalip": "Kalıp", "x": "Adet", "sure_dk": "Üretim (saat)", "setup_dk": "Değişim (dk)", "fire_adet": "Beklenen fire"}).copy()
        t["Üretim (saat)"] = t["Üretim (saat)"] / 60
        t = t.sort_values(["Makine", "Üretim (saat)"], ascending=[True, False])
        lines_by[name] = table(t[["Makine", "Kalıp", "Ürün", "Adet", "Üretim (saat)", "Değişim (dk)", "Beklenen fire"]],
                               {"Adet": "int", "Üretim (saat)": "num1", "Değişim (dk)": "num0", "Beklenen fire": "int"})
    ok = [r for r in rows if "Değişim" in r]
    if not ok:
        raise RuntimeError("Hiçbir senaryo çözülemedi.")
    base_row = {"Senaryo": "Geçmiş düzen (tahmin)", "Açıklama": "Her kalıp geçmişteki ortalama kampanya büyüklüğüyle, tarihsel makine dağılımıyla çalışır",
                "Değişim": base_ch, "Değişim süresi (saat)": base_dk / 60, "Üretim süresi (saat)": base_prod / 60, "Toplam makine (saat)": (base_dk + base_prod) / 60,
                "İlk deneme fire": base_ch * f1_pc, "Karşılanamayan": 0.0}
    allr = [base_row] + rows
    sel = ok[0]
    dch = base_ch - sel["Değişim"]
    dh = base_dk / 60 - sel["Değişim süresi (saat)"]
    df_ = base_ch * f1_pc - sel["İlk deneme fire"]
    kp = [kpi("Değişim sayısı", f"{int(sel['Değişim'])}", f"geçmiş düzende yaklaşık {base_ch} ({'−' if dch >= 0 else '+'}{abs(dch)})", "green" if dch > 0 else "red"),
          kpi("Değişim süresi", f"{fnum(sel['Değişim süresi (saat)'], 0)} saat", f"geçmiş düzende yaklaşık {fnum(base_dk / 60, 0)} saat ({'−' if dh >= 0 else '+'}{fnum(abs(dh), 0)} sa)", "green" if dh > 0 else "red"),
          kpi("İlk deneme fire", fint(sel["İlk deneme fire"]), f"geçmiş düzende yaklaşık {fint(base_ch * f1_pc)} ({'−' if df_ >= 0 else '+'}{fint(abs(df_))})", "green" if df_ > 0 else "red"),
          kpi("Beklenen fire", fint(fire_pl[sel["Senaryo"]][0]), f"geçmiş dağılımda yaklaşık {fint(fire_pl[sel['Senaryo']][1])}", "green" if fire_pl[sel["Senaryo"]][0] <= fire_pl[sel["Senaryo"]][1] else "red"),
          kpi("Toplam makine süresi", f"{fnum(sel['Toplam makine (saat)'], 0)} saat", f"geçmiş düzende yaklaşık {fnum((base_dk + base_prod) / 60, 0)} saat", "teal")]
    txt = [f"Seçili senaryo (**{sel['Senaryo']}**): {days} günlük talep için **{int(sel['Değişim'])}** değişim gerekiyor; geçmişteki kampanya alışkanlıklarıyla yaklaşık **{base_ch}** olurdu. "
           f"Fark: **{abs(dch)}** değişim, yaklaşık **{fnum(abs(dh), 0)} saat** {'tasarruf' if dh >= 0 else 'fazladan kayıp'}.",
           "Senaryolar aynı talebi karşılar; tek fark kalıpların kaç partiye bölündüğü. Parti sayısı arttıkça teslim/stok esnekliği artar, ama her parti yeni bir değişim demektir. Tablodan dengeyi seç; işletme için uygun parti sıklığı üretim planlamayla birlikte belirlenmeli.",
           f"Bu plan kuramsaldır: kalıp–makine uygunluğu geçmişte çalışılan makinelerden, değişim süresi makinenin kayıtlı ortancasından ({fnum(setup['_glob'], 0)} dk genel ortanca) tahmin edilir; "
           "termin, stok ve kalıp hazırlığı hesaba katılmaz. Uygulamadan önce üretim planlamayla kontrol et."]
    if any(r.get("Karşılanamayan", 0) > 1 for r in ok):
        txt.append("Uyarı: bazı senaryolarda kapasite yetmiyor, karşılanamayan adet tabloda görünür. Plan süresini, vardiya sayısını ya da kullanılabilirliği artır.")
    tb = pd.DataFrame(allr)
    tb = tb[["Senaryo", "Değişim", "Değişim süresi (saat)", "Üretim süresi (saat)", "Toplam makine (saat)", "İlk deneme fire", "Karşılanamayan", "Açıklama"]]
    return clean({"kpis": kp, "insights": txt, "selected": sel["Senaryo"], "scenarios": [r["Senaryo"] for r in ok],
                  "table": table(tb, {"Değişim": "int", "Değişim süresi (saat)": "num1", "Üretim süresi (saat)": "num1", "Toplam makine (saat)": "num1", "İlk deneme fire": "int", "Karşılanamayan": "int"}),
                  "lines": lines_by, "shifts": shift_by, "demand_n": int(len(dem)), "demand_total": float(dem["adet"].sum())})


# ------------------------------------------------------------------ hedef durumu (Excel tarafı)
METRIC = {"ort_sure": ("Ortalama değişim süresi (dk)", "ort_dk"),
          "haftalik_kayip": ("Haftalık değişim kaybı (saat)", "kayip_sa"),
          "haftalik_degisim": ("Haftalık değişim sayısı", "n")}


def weekly_for_targets(d: pd.DataFrame) -> pd.DataFrame:
    return weekly_series(d)


# ------------------------------------------------------------------ saha kayıtlarının analizi
def logs_analysis(logs: list, steps: list, excel_by_machine: dict | None = None) -> dict:
    if not logs:
        return {"n": 0, "insights": ["Henüz saha kaydı yok. Kronometreyle ya da elle ilk değişimi kaydet."], "kpis": []}
    df = pd.DataFrame(logs)
    keys = [s["key"] for s in steps]
    S = pd.DataFrame(list(df["adimlar"])).reindex(columns=keys).fillna(0.0)
    n = len(df)
    tot = df["toplam_dk"].astype(float)
    avg = float(tot.mean())
    step_avg = S.mean()
    labs = {s["key"]: s["label"] for s in steps}
    big = step_avg.sort_values(ascending=False)
    ext = float(sum(step_avg[s["key"]] for s in steps if s["dis"]))
    ins = [f"**{n}** değişim kaydı var; ortalama süre **{fnum(avg, 0)} dk** (en kısa {fnum(tot.min(), 0)}, en uzun {fnum(tot.max(), 0)} dk)."]
    if step_avg.sum() > 0:
        ins.append(f"En uzun adım **{labs[big.index[0]]}** (ortalama {fnum(big.iloc[0], 0)} dk, toplamın %{fnum(big.iloc[0] / step_avg.sum() * 100, 0)}'i); ardından **{labs[big.index[1]]}** ({fnum(big.iloc[1], 0)} dk).")
        ins.append(f"Makine durmadan önce yapılabilecek adımlar (hazırlık, ön ısıtma) ortalama **{fnum(ext, 0)} dk** tutuyor. Bunlar makine çalışırken yapılırsa değişim süresi o kadar kısalır (dışa alma).")
    mk = df.groupby("makine").agg(n=("toplam_dk", "size"), ort=("toplam_dk", "mean"), en_kisa=("toplam_dk", "min"), en_uzun=("toplam_dk", "max")).reset_index()
    if excel_by_machine:
        mk["excel"] = mk["makine"].map(excel_by_machine)
        cmp_ = mk.dropna(subset=["excel"])
        if len(cmp_):
            diff = float((cmp_["ort"] * cmp_["n"]).sum() / cmp_["n"].sum() - (cmp_["excel"] * cmp_["n"]).sum() / cmp_["n"].sum())
            ins.append(f"Aynı makinelerde Excel'e girilen süreler ortalama {fnum(abs(diff), 0)} dk {'daha kısa' if diff > 0 else 'daha uzun'} (saha ölçümü {fnum(float((cmp_['ort'] * cmp_['n']).sum() / cmp_['n'].sum()), 0)} dk). "
                       "Fark büyükse Excel'deki süreler yuvarlak/tahmini olabilir.")
    mk_t = mk.rename(columns={"makine": "Makine", "n": "Kayıt", "ort": "Ort. süre (dk)", "en_kisa": "En kısa (dk)", "en_uzun": "En uzun (dk)", "excel": "Excel ortalaması (dk)"})
    fmts = {"Kayıt": "int", "Ort. süre (dk)": "num1", "En kısa (dk)": "num0", "En uzun (dk)": "num0", "Excel ortalaması (dk)": "num1"}
    df["hb"] = pd.to_datetime(df["tarih"]) - pd.to_timedelta(pd.to_datetime(df["tarih"]).dt.dayofweek, unit="D")
    wk = df.groupby("hb")["toplam_dk"].mean()
    return clean({"n": n, "insights": ins,
                  "kpis": [kpi("Kayıt", str(n), "saha ölçümü", "teal"), kpi("Ortalama süre", f"{fnum(avg, 0)} dk", f"en kısa {fnum(tot.min(), 0)} · en uzun {fnum(tot.max(), 0)}", "amber"),
                           kpi("Dışa alınabilir", f"{fnum(ext, 0)} dk", "hazırlık + ön ısıtma (ortalama)", "green"),
                           kpi("İlk deneme fire", fint(df["ilk_deneme_fire"].sum()), f"kayıt başına {fnum(df['ilk_deneme_fire'].mean(), 1)} adet")],
                  "steps": bars([labs[k] for k in keys], step_avg.values, ["green" if s["dis"] else "orange" for s in steps], [f"{fnum(v, 1)} dk" for v in step_avg.values]),
                  "machines": table(mk_t, fmts),
                  "weekly": bars([dlabel(i) for i in wk.index], wk.values, "teal", [f"{fnum(v, 0)} dk" for v in wk.values])})


# ------------------------------------------------------------------ hedefler
def targets_status(d: pd.DataFrame, targets: list, logs: list) -> dict:
    w = weekly_series(d)
    sug = {}
    for key, (label, col) in METRIC.items():
        s = w[col].dropna()
        base = float(s.tail(8).mean()) if len(s) else None
        sug[key] = {"label": label, "baz": base, "onerilen": None if base is None else base * 0.8}
    lw = None
    if logs:
        ldf = pd.DataFrame(logs)
        t = pd.to_datetime(ldf["tarih"])
        ldf["hb"] = t - pd.to_timedelta(t.dt.dayofweek, unit="D")
        lw = ldf.groupby("hb")["toplam_dk"].mean()
    out = []
    for t in targets:
        label, col = METRIC[t["metrik"]]
        s = w[col].dropna()
        cur = float(s.tail(4).mean()) if len(s) else None
        baz = t["baz"] if t["baz"] is not None else (sug[t["metrik"]]["baz"])
        prog = None
        if cur is not None and baz is not None and baz != t["deger"]:
            prog = float((baz - cur) / (baz - t["deger"]) * 100)
        series = bars([dlabel(i) for i in s.index], s.values, ["green" if (v <= t["deger"]) else "orange" for v in s.values])
        saha = None
        if lw is not None and t["metrik"] == "ort_sure":
            saha = bars([dlabel(i) for i in lw.index], lw.values, "teal", [f"{fnum(v, 0)} dk (saha)" for v in lw.values])
        out.append({"id": t["id"], "metrik": t["metrik"], "label": label, "hedef": t["deger"], "baz": baz, "baslangic": t["baslangic"], "guncel": cur, "ilerleme": prog,
                    "seri": series, "saha": saha})
    return clean({"targets": out, "suggest": sug})
