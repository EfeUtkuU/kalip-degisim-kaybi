"""Veriden çıkarımlar: tabloya bakarak değil, karşılaştırarak bulunan sonuçlar.

Her bulgu: ne bulundu, kanıt gücü, neden böyle düşünüyoruz, ne yapılabilir, nelere dikkat.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, kruskal, mannwhitneyu

from . import change as CH
from .data import DURUS_LABELS
from .util import bars, clean, fint, fnum, kpi, table

SHIFT_H = 12.0  # vardiya uzunluğu varsayımı (Excel'de yok; yalnızca saate çevirmek için)


def _inj(d: pd.DataFrame) -> pd.DataFrame:
    return d[d["istasyon_tipi"] == "Enjeksiyon"]


# ------------------------------------------------------------------ 1) gizli kayıp
def hidden_loss(d: pd.DataFrame, ev: pd.DataFrame, x: pd.DataFrame) -> Optional[dict]:
    """Değişim olan vardiyada, AYNI kalıp AYNI makinedeki normal vardiyalara göre ne kadar az üretildi?"""
    y = x[(x["baski"] > 0) & (x["cevrim"] > 0) & (x["goz"] > 0)].copy()
    y["kap"] = y["goz"] * 43200.0 / y["cevrim"]
    k = ["makine", "tarih", "vardiya"]
    y = y[y.groupby(k)["baski"].transform("size") == 1].copy()  # vardiyada tek kalıp: kısmi vardiya karışmasın
    y["perf"] = y["uretim"] / y["kap"]
    y["ch"] = y["olay"].astype(bool)
    rows = []
    for (kal, mak), z in y.groupby(["kalip", "makine"]):
        a, bn = z[z["ch"]], z[~z["ch"]]
        if len(a) >= 1 and len(bn) >= 2:
            rows.append((kal, mak, len(a), a["perf"].mean(), bn["perf"].mean(), a["D2"].fillna(0).mean()))
    if len(rows) < 15:
        return None
    R = pd.DataFrame(rows, columns=["kalip", "makine", "n", "pa", "pb", "d2"]).dropna()
    w = R["n"].to_numpy(float)
    diff = (R["pa"] - R["pb"]).to_numpy()
    est = float(np.average(diff, weights=w))
    rng = np.random.default_rng(0)
    bs = []
    for _ in range(1500):
        i = rng.integers(0, len(R), len(R))
        bs.append(np.average(diff[i], weights=w[i]))
    lo, hi = np.percentile(bs, [2.5, 97.5])
    base = float(np.average(R["pb"], weights=w))
    d2 = float(np.average(R["d2"], weights=w))
    return {"fark": est, "lo": float(lo), "hi": float(hi), "base": base, "n": int(w.sum()), "pairs": len(R), "d2": d2}


# ------------------------------------------------------------------ 2) makine ve fire
def extreme_molds(d: pd.DataFrame) -> list:
    """Genel fire oranı %25'in üstündeki kalıplar ve bilinmeyen ('?') kalıp: makine karşılaştırmasını bozmasın diye ayrı tutulur."""
    y = d[d["baski"] > 0]
    rate = y.groupby("kalip")["fire"].sum() / y.groupby("kalip")["baski"].sum()
    return sorted(set(rate[rate > 0.25].index) | ({"?"} if "?" in rate.index else set()))


def scrap_by_machine(d: pd.DataFrame) -> pd.DataFrame:
    y = d[d["baski"] > 0].copy()
    y = y[~y["kalip"].isin(extreme_molds(d))]
    rate = y.groupby("kalip")["fire"].sum() / y.groupby("kalip")["baski"].sum()
    y["beklenen"] = y["kalip"].map(rate) * y["baski"]
    m = y.groupby("makine").agg(baski=("baski", "sum"), fire=("fire", "sum"), beklenen=("beklenen", "sum"))
    m["fark"] = m["fire"] - m["beklenen"]
    m["z"] = m["fark"] / np.sqrt(m["beklenen"].clip(lower=1))
    m["oran"] = m["fire"] / m["baski"]
    m["bek_oran"] = m["beklenen"] / m["baski"]
    return m[m["baski"] >= 20000].sort_values("fark")


def scrap_pairs(d: pd.DataFrame) -> pd.DataFrame:
    y = d[(d["baski"] > 0) & (d["kalip"] != "?")]
    g = y.groupby(["kalip", "makine"]).agg(n=("baski", "size"), baski=("baski", "sum"), fire=("fire", "sum")).reset_index()
    tot = g.groupby("kalip").agg(tb=("baski", "sum"), tf=("fire", "sum"))
    g = g.join(tot, on="kalip")
    g = g[(g["baski"] >= 3000) & (g["tb"] - g["baski"] >= 3000)].copy()
    out = []
    for r in g.itertuples():
        ob, of = r.tb - r.baski, r.tf - r.fire
        t = np.array([[r.fire, r.baski - r.fire], [of, ob - of]], float)
        try:
            p = chi2_contingency(t)[1]
        except Exception:  # noqa: BLE001
            p = 1.0
        # en iyi alternatif makine
        alt = g[(g["kalip"] == r.kalip) & (g["makine"] != r.makine)]
        best = alt.assign(o=alt["fire"] / alt["baski"]).sort_values("o").iloc[0] if len(alt) else None
        out.append({"kalip": r.kalip, "makine": r.makine, "baski": r.baski, "oran": r.fire / r.baski, "diger": of / ob, "p": p,
                    "iyi_makine": None if best is None else best["makine"], "iyi_oran": None if best is None else best["o"]})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ 3) değişim süresi neye bağlı
def duration_drivers(ev: pd.DataFrame) -> dict:
    r = ev[ev["kayitli"]].copy()
    tot = ((r["sure"] - r["sure"].mean()) ** 2).sum()
    grp = r.groupby("makine")["sure"]
    within = ((r["sure"] - grp.transform("mean")) ** 2).sum()
    eta_m = 1 - within / tot
    grp2 = r.groupby("kalip")["sure"]
    eta_k = 1 - ((r["sure"] - grp2.transform("mean")) ** 2).sum() / tot
    n_k = r["kalip"].nunique()
    adj_k = 1 - (1 - eta_k) * (len(r) - 1) / (len(r) - n_k)
    adj_m = 1 - (1 - eta_m) * (len(r) - 1) / (len(r) - r["makine"].nunique())
    a, bn = r.loc[r["vardiya"] == "Sabah", "sure"], r.loc[r["vardiya"] == "Akşam", "sure"]
    p_v = float(mannwhitneyu(a, bn).pvalue) if len(a) > 5 and len(bn) > 5 else float("nan")
    o = r.explode("operatorler")
    o = o[o["operatorler"].notna()]
    big = o.groupby("operatorler")["sure"].transform("size") >= 15
    o = o[big]
    p_o = float(kruskal(*[z["sure"].values for _, z in o.groupby("operatorler")]).pvalue) if o["operatorler"].nunique() > 2 else float("nan")
    # operatör etkisi makine karışımından mı? makineye göre fark alıp tekrar dene
    o = o.assign(art=o["sure"] - o.groupby("makine")["sure"].transform("mean"))
    p_o2 = float(kruskal(*[z["art"].values for _, z in o.groupby("operatorler")]).pvalue) if o["operatorler"].nunique() > 2 else float("nan")
    mod = r["sure"] % 30 == 0
    return {"adj_m": float(adj_m), "adj_k": float(adj_k), "p_v": p_v, "p_o": p_o, "p_o2": p_o2, "n": len(r), "kat30": float(mod.mean())}


# ------------------------------------------------------------------ ana işlev
def _rate_per_hour(d: pd.DataFrame) -> pd.Series:
    """Kalıp başına saatlik baskı (göz × 3600 / çevrim)."""
    y = d[(d["cevrim"] > 0) & (d["goz"] > 0)]
    return (y["goz"] * 3600.0 / y["cevrim"]).groupby(y["kalip"]).median()


def _merge_candidates(x: pd.DataFrame) -> pd.DataFrame:
    y = x[x["baski"] > 0].copy()
    y["ay"] = y["tarih"].dt.strftime("%Y-%m")
    y["k"] = y["makine"] + "#" + y["kamp"].astype(str)
    g = y.groupby(["kalip", "ay"]).agg(kamp=("k", "nunique"), adet=("uretim", "sum"), makine=("makine", lambda s: ", ".join(sorted(set(s))))).reset_index()
    g = g[(g["kalip"] != "?") & (g["kamp"] >= 2)]
    g["azalir"] = g["kamp"] - 1
    return g.sort_values(["azalir", "adet"], ascending=False)


def oneriler(d: pd.DataFrame, logs: Optional[list] = None, steps: Optional[list] = None, vardiya: float = 12.0) -> dict:
    d = _inj(d)
    x, ev, _setup = CH.events(d)
    if len(ev) < 30:
        return {"oneriler": [], "kpis": [], "uyari": "Bu dönemde yeterli değişim yok. Dönemi genişlet."}
    logs, steps = logs or [], steps or []
    vardiya = float(min(max(vardiya, 6), 24))
    rec_h = float(ev["sure"].sum() / 60)
    n_ev = len(ev)
    items = []

    # ---------- değişim başına gerçek kayıp
    h = hidden_loss(d, ev, x)
    per = (-h["fark"] * vardiya) if h else float(ev["sure"].mean() / 60)
    per_lo = (-h["hi"] * vardiya) if h else per
    per_hi = (-h["lo"] * vardiya) if h else per
    real_h = per * n_ev
    kpis = [
        kpi("Değişim sayısı", fint(n_ev), "seçili dönemde"),
        kpi("Excel'deki süre", f"{fnum(rec_h, 0)} saat", f"değişim başına {fnum(rec_h / n_ev * 60, 0)} dk", "amber"),
        kpi("Gerçek kayıp (tahmin)", f"{fnum(real_h, 0)} saat", f"değişim başına {fnum(per, 1)} saat", "red"),
    ]

    # ---------- 1) sahada ölç / dışa al
    ext_keys = [s["key"] for s in steps if s.get("dis")]
    saha = [l for l in logs if l.get("toplam_dk")]
    neden, nasil = [], []
    if h:
        neden.append(f"Değişim olan vardiyada aynı kalıp aynı makinede normal vardiyaya göre %{fnum(-h['fark'] * 100, 0)} az üretiyor (aralık %{fnum(-h['hi'] * 100, 0)}–%{fnum(-h['lo'] * 100, 0)}).")
        neden.append(f"Bu değişim başına yaklaşık {fnum(per, 1)} saat ({fnum(per_lo, 1)}–{fnum(per_hi, 1)}), Excel'de ise ortalama {fnum(h['d2'], 0)} dk görünüyor.")
        neden.append(f"{h['pairs']} kalıp–makine çiftinde {h['n']} değişim vardiyası, aynı çiftin değişimsiz vardiyalarıyla karşılaştırıldı.")
    if len(saha) >= 5:
        ext = np.mean([sum((l["adimlar"] or {}).get(k, 0) for k in ext_keys) for l in saha])
        avg = np.mean([l["toplam_dk"] for l in saha])
        gain = ext / 60 * n_ev
        neden.append(f"Saha kayıtların ({len(saha)} adet): ortalama {fnum(avg, 0)} dk, bunun {fnum(ext, 0)} dk'sı makine çalışırken yapılabilecek hazırlık ve ön ısıtma.")
        nasil.append("Hazırlık ve ön ısıtmayı makine çalışırken yap (kalıp, ekipman, malzeme önceden hazır; kalıp ısıtıcıda ısınmış).")
        kz, kt = gain, f"~{fnum(gain, 0)} saat (saha ölçümüne göre)"
        baslik = "Hazırlık ve ön ısıtmayı makine çalışırken yap"
    else:
        nasil.append("Birkaç hafta boyunca her değişimi 'Saha kaydı' ekranında adım adım ölç.")
        nasil.append("Ölçüm gelince hangi adımın kısalacağı ve kazancın kaç saat olduğu burada otomatik hesaplanır.")
        kz, kt = None, "Ölçüm sonrası hesaplanır"
        baslik = "Değişimin neresinde zaman gittiğini ölç"
    items.append({"id": "olc", "baslik": baslik, "kisa": f"Gerçek kayıp Excel'deki sürenin yaklaşık {fnum(real_h / max(rec_h, 1), 1)} katı." if h else "Excel'deki süre yuvarlak, gerçek ölçüm gerekli.",
                  "saat": kz, "kazanc": kt, "neden": neden, "nasil": nasil,
                  "hedef": "Her değişimi ölç; hedef: ölçülen süreyi ilk ayda %20 kısaltmak (Hedef sayfasında koy).",
                  "dikkat": f"Vardiya {fnum(vardiya, 0)} saat varsayıldı (yukarıdan değiştirilebilir). Yüzde değişmez, saat karşılığı değişir.", "git": "kayit"})

    # ---------- 2) kısa kampanyaları birleştir
    mc = _merge_candidates(x)
    if len(mc):
        av = int(mc["azalir"].sum())
        t = mc.head(10)[["kalip", "ay", "kamp", "adet", "makine"]].copy()
        t.columns = ["Kalıp", "Ay", "Kampanya", "Adet", "Makineler"]
        items.append({"id": "birlestir", "baslik": "Aynı ay içinde bölünen kalıpları tek seferde çalıştır",
                      "kisa": f"{len(mc)} kalıp–ay çiftinde aynı kalıp birden fazla kez takılmış.",
                      "saat": av * per, "kazanc": f"en çok ~{fnum(av * per, 0)} saat ({av} değişim)",
                      "hedef": f"Aynı kalıp ayda en çok 1 kampanya: {fint(len(mc))} kalıp–ay için toplam {av} değişim az.",
                      "neden": [f"Aynı kalıp aynı ayda 2 ya da daha çok ayrı kampanyayla çalışmış: toplam {av} fazladan değişim.",
                                f"Her değişim yaklaşık {fnum(per, 1)} saat kapasite götürüyor."],
                      "nasil": ["Tabloda en çok bölünen kalıplardan başla; üretim planlamayla aynı ayın talebini tek kampanyada topla.",
                                "'Plan karşılaştırması' sayfasında kendi talebinle tek kampanya ile bölünmüş planı karşılaştır."],
                      "dikkat": "Bu bir üst sınır: termin ya da malzeme yüzünden bölünmesi gerekenler de var, hepsi birleşmez.",
                      "tablo": table(t, {"Kampanya": "int", "Adet": "int"}), "git": "plan"})

    # ---------- 3) fire: kalıp–makine
    rate = _rate_per_hour(d)
    p = scrap_pairs(d)
    exm = extreme_molds(d)
    if len(p):
        s = p[p["p"] < 0.001]
        kot = s[(s["oran"] > s["diger"]) & s["iyi_makine"].notna()].copy()
        kot["kazanim"] = (kot["oran"] - kot["iyi_oran"]).clip(lower=0) * kot["baski"]
        kot["saat"] = kot["kazanim"] / kot["kalip"].map(rate).fillna(rate.median())
        kot = kot.sort_values("kazanim", ascending=False)
        ok = kot[kot["oran"] <= 0.5].head(10)
        sus = kot[kot["oran"] > 0.5]
        if len(ok):
            t = ok[["kalip", "makine", "oran", "iyi_makine", "iyi_oran", "kazanim"]].copy()
            t["oran"] *= 100
            t["iyi_oran"] *= 100
            t.columns = ["Kalıp", "Şimdi çalıştığı makine", "Fire %", "Daha iyi makine", "Orada fire %", "Önlenebilir fire"]
            top = ok.iloc[0]
            items.append({"id": "kalip_makine", "baslik": "Fire yüksek kalıpları daha iyi çalıştığı makineye al",
                          "kisa": f"Örnek: {top['kalip']} {top['makine']}'de %{fnum(top['oran'] * 100, 0)}, {top['iyi_makine']}'de %{fnum(top['iyi_oran'] * 100, 1)} fire.",
                          "saat": float(ok["saat"].sum()), "kazanc": f"~{fnum(ok['saat'].sum(), 0)} saat ({fint(ok['kazanim'].sum())} adet fire)",
                          "hedef": "; ".join(f"{r.kalip} → {r.iyi_makine} (fire %{fnum(r.iyi_oran * 100, 1)})" for r in ok.head(4).itertuples()) + ("…" if len(ok) > 4 else ""),
                          "neden": ["Aynı kalıbın farklı makinelerdeki fire oranları karşılaştırıldı; fark tesadüf olamayacak kadar büyük (her çift için istatistiksel test, p < 0,001).",
                                    "Önlenebilir fire = (bu makinedeki oran − aynı kalıbın en iyi makinedeki oranı) × baskı sayısı. Saate çevirmek için kalıbın çevrim süresi kullanıldı."],
                          "nasil": ["Tablodaki kalıpları 'daha iyi makine'ye kaydır ya da o makinenin ayarlarını (sıcaklık, kurutma, basınç) karşılaştır.",
                                    "Kaydırdıktan sonra Hedef sayfasından fire takibi yap."],
                          "dikkat": "Hammadde, renk ya da operatör farkı da bu farkı yaratıyor olabilir; veri ayıramıyor. Küçük bir denemeyle doğrula.",
                          "tablo": table(t, {"Fire %": "pct1", "Orada fire %": "pct1", "Önlenebilir fire": "int"})})
        if len(sus):
            items.append({"id": "dogrula", "baslik": "Olağan dışı fire kayıtlarını sahada kontrol et",
                          "kisa": f"{', '.join(sus['kalip'] + ' (' + sus['makine'] + ')')}: fire %50'nin üstünde.",
                          "saat": float(sus["saat"].sum()), "kazanc": f"doğruysa ~{fnum(sus['saat'].sum(), 0)} saat",
                          "hedef": "; ".join(f"{r.kalip} → {r.iyi_makine} (fire %{fnum(r.iyi_oran * 100, 1)})" for r in sus.itertuples()),
                          "neden": ["Bu çiftlerde baskıların yarısından fazlası fire görünüyor, aynı kalıp başka makinede çok daha iyi çalışıyor.",
                                    "Ya gerçek bir uyumsuzluk var ya da fire/baskı sayıları yanlış girilmiş."],
                          "nasil": ["Bu iki kayıt için vardiya raporlarına bak, gerçek mi kontrol et.", "Gerçekse kalıbı hemen daha iyi makineye al."],
                          "dikkat": "Doğrulanana kadar diğer hesaplara katılmadı.", "dogrula": True})

    # ---------- 4) fire: makine
    m = scrap_by_machine(d)
    if len(m):
        wm = d[d["baski"] > 0].groupby("makine").apply(lambda z: float((z["goz"] * 3600.0 / z["cevrim"].replace(0, np.nan)).median()))
        bad = m[(m["z"] > 4) & (m["fark"] > 500)].sort_values("fark", ascending=False)
        if len(bad):
            sa = float(sum(r.fark / wm.get(i, np.nan) for i, r in bad.iterrows() if pd.notna(wm.get(i, np.nan))))
            t = bad.reset_index()[["makine", "fire", "beklenen", "fark"]].copy()
            t.columns = ["Makine", "Fire", "Beklenen fire", "Fazla fire"]
            items.append({"id": "makine_fire", "baslik": f"{bad.index[0]} ve benzerlerinde fire nedenini ara",
                          "kisa": f"{', '.join(bad.index[:3])}: aynı kalıplarla beklenenden fazla fire.",
                          "saat": sa, "kazanc": f"~{fnum(sa, 0)} saat ({fint(bad['fark'].sum())} adet fire)",
                          "hedef": "Bu makinelerin fire oranını, aynı kalıpların ortalama oranına indir: " + ", ".join(f"{i} %{fnum(r.oran * 100, 1)} → %{fnum(r.bek_oran * 100, 1)}" for i, r in bad.head(3).iterrows()) + ".",
                          "neden": ["Her kalıbın tüm makinelerdeki ortalama fire oranı 'beklenen' alındı, makinenin gerçek fire sayısı bununla kıyaslandı.",
                                    "Yalnız fark sayının karekökünün 4 katından büyük olan makineler listelendi."],
                          "nasil": ["Bu makinelerde kalıp–makine uyumu, kurutma/ısıtma ve ayar kayıtlarına bak.", "İyi çalışan makinedeki ayarlarla karşılaştır."],
                          "dikkat": "Makineye düşen ürünlerin zorluğu da etkileyebilir. Fire oranı %25'in üstündeki kalıplar ve '?' kalıbı bu hesapta yok.",
                          "tablo": table(t, {"Fire": "int", "Beklenen fire": "int", "Fazla fire": "int"})})

    # ---------- 5) süre: yavaş makineler
    dd = duration_drivers(ev)
    r = ev[ev["kayitli"]]
    mt = r.groupby("makine")["sure"].agg(["size", "median", "mean"]).reset_index()
    mt = mt[mt["size"] >= 8].sort_values("median", ascending=False)
    slow = mt[mt["median"] >= 60]
    if len(slow):
        t = mt.rename(columns={"makine": "Makine", "size": "Kayıt", "median": "Ortanca dk", "mean": "Ortalama dk"})
        items.append({"id": "yavas", "baslik": "Değişimi uzun süren makinelerde hazırlığı iyileştir",
                      "kisa": f"{', '.join(slow['makine'].head(3))}: ortanca değişim {fnum(slow['median'].min(), 0)}+ dk. En hızlı makineler 30 dk.",
                      "saat": None, "kazanc": "Ölçüm sonrası hesaplanır",
                      "hedef": f"{', '.join(slow['makine'].head(3))} için ortanca süreyi {fnum(slow['median'].min(), 0)} dk'dan, en hızlı makinelerin düzeyine (30 dk) yaklaştır.",
                      "neden": [f"Kayıtlı süredeki farkın yaklaşık %{fnum(dd['adj_m'] * 100, 0)}'ini makine, %{fnum(max(dd['adj_k'], 0) * 100, 0)}'ini kalıp açıklıyor.",
                                "Sabah ve akşam vardiyası arasında anlamlı fark yok." if dd["p_v"] > 0.05 else "Sabah ve akşam vardiyası arasında fark var."],
                      "nasil": ["Yavaş makinelerde vinç, hızlı bağlama, kalıp ısıtıcı ve ekipman yerleşimine bak.", "En hızlı makinedeki düzeni örnek al."],
                      "dikkat": f"Süreler büyük ölçüde yuvarlak girilmiş (%{fnum(dd['kat30'] * 100, 0)}'ü 30 dk'nın katı), ±15 dk farklar ayırt edilemez.",
                      "tablo": table(t, {"Kayıt": "int", "Ortanca dk": "num0", "Ortalama dk": "num0"}), "git": "kayit"})

    # ---------- 6) ilk deneme
    f1 = ev.groupby("kalip").agg(n=("f1", "size"), f1=("f1", "mean")).reset_index()
    f1 = f1[(f1["n"] >= 8) & (f1["f1"] >= 2 * max(float(ev["f1"].mean()), 1))].sort_values("f1", ascending=False).head(8)
    if len(f1):
        t = f1.rename(columns={"kalip": "Kalıp", "n": "Değişim", "f1": "İlk deneme fire (ort.)"})
        items.append({"id": "f1", "baslik": "İlk denemesi çok fire veren kalıplara ayar kaydı tut",
                      "kisa": f"{f1['kalip'].iloc[0]}: her değişimde ortalama {fnum(f1['f1'].iloc[0], 0)} adet.",
                      "saat": None, "kazanc": "Küçük (adet olarak)",
                      "hedef": f"İlk deneme fire: {fnum(float(f1['f1'].iloc[0]), 0)} adetten {fnum(float(ev['f1'].mean()), 0)} adedin altına (genel ortalama).",
                      "neden": [f"Değişim başına ortalama {fnum(float(ev['f1'].mean()), 0)} adet ilk deneme fire var; bu kalıplar bunun en az 2 katı."],
                      "nasil": ["Bu kalıplar için iyi çalışan ayarı (sıcaklık, basınç, süre) kalıp kartına yaz, takınca aynısıyla başla."],
                      "dikkat": "En az 8 değişimi olan kalıplar alındı.", "tablo": table(t, {"Değişim": "int", "İlk deneme fire (ort.)": "num0"})})

    key = lambda i: -(i["saat"] if i.get("saat") is not None else -1)
    items.sort(key=lambda i: (0 if i["id"] == "olc" else 1 if i.get("dogrula") else 2, key(i)))
    return clean({"oneriler": items, "kpis": kpis, "vardiya_saat": vardiya})
