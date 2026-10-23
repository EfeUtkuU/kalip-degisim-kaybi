"""Excel okuma ve temizleme katmanı.

Excel'deki "Üretim Verileri" sayfası ana kaynaktır. Her satır bir makine-vardiya kaydıdır.
Doğrulanan kurallar (2026 verisi):
  * Üretim adedi = Sağlam + Fire  (= Baskı Adedi x Göz Sayısı)
  * Fire hücresi boşsa fire = 0
  * F1..F8 toplamı fire adedine eşittir (satırların %99'unda)
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MAIN_SHEET = "Üretim Verileri"
KALIP_SHEET = "kalıp Listesi Çevrim zamanı"

FIRE_LABELS = {
    "F1": "İlk deneme / ayar baskısı",
    "F2": "Renk uygunsuzluğu",
    "F3": "Eksik baskı",
    "F4": "Boya izi (dalgalanma)",
    "F5": "Siyah nokta / beyaz iz",
    "F6": "Çatlak / kırık",
    "F7": "Çizik",
    "F8": "Diğer",
}
DURUS_LABELS = {
    "D1": "Kalıp ayarı",
    "D2": "Kalıp değişimi",
    "D3": "Kalıp arızası",
    "D4": "Deneme üretimi",
    "D5": "Malzeme eksikliği",
    "D6": "Eğitim / toplantı",
    "D7": "Elektrik kesintisi",
    "D8": "Makine arızası",
    "D9": "Planlı duruş",
    "D10": "Personel yetersizliği",
}
FIRE_COLS = list(FIRE_LABELS)
DURUS_COLS = list(DURUS_LABELS)

_BASE_NAMES = {
    "Hafta": "hafta",
    "Tarih": "tarih",
    "Vardiya": "vardiya",
    "Mak. No": "makine",
    "Personelin Adı Soyadı": "operator_ham",
    "Ürün Kodu": "urun_kodu",
    "Ürün Adı": "urun_adi",
    "Kalıp No": "kalip",
    "Göz Sayısı": "goz",
    "Hammadde Kodu": "hammadde_ham",
    "Lot No": "lot",
    "Çevrim Süresi sn": "cevrim",
    "Baskı Adedi": "baski",
    "Sağlam Adet": "saglam",
    "Fire Adedi": "fire_ham",
    "Kalıp Değişikliği Var mi?": "kalip_degisti",
}


# ----------------------------------------------------------------- yardımcılar
def tr_upper(s) -> str:
    s = "" if s is None or (isinstance(s, float) and np.isnan(s)) else str(s)
    return s.replace("i", "İ").replace("ı", "I").upper()


def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _normalize_key(name: str) -> str:
    """Yazım hatası karşılaştırması için: I/İ ve aksan farklarını yok say."""
    t = tr_upper(name)
    for a, b in zip("İŞĞÜÖÇ", "ISGUOC"):
        t = t.replace(a, b)
    return t


def split_operators(raw) -> list[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    parts = [_norm_spaces(tr_upper(p)) for p in str(raw).split("\n")]
    return [p for p in parts if p and p not in ("#N/A", "NAN")]


def build_name_map(all_names: pd.Series) -> dict[str, str]:
    """Az görülen isimleri, çok görülen çok benzer bir isme eşler (ARLAN -> ARSLAN)."""
    counts = all_names.value_counts()
    frequent = [n for n, c in counts.items() if c >= 10]
    mapping: dict[str, str] = {}
    for name, c in counts.items():
        if c >= 10:
            mapping[name] = name
            continue
        best, best_r = name, 0.0
        for f in frequent:
            r = difflib.SequenceMatcher(None, _normalize_key(name), _normalize_key(f)).ratio()
            if r > best_r:
                best, best_r = f, r
        mapping[name] = best if best_r >= 0.9 else name
    return mapping


def clean_material(v) -> tuple[str, bool]:
    """'9110\\n9110-K' -> ('9110', True): ilk satır ana hammadde, '-K' kırma (yolluk) karışımı."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ("?", False)
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    parts = [p.strip() for p in s.split("\n") if p.strip()]
    if not parts:
        return ("?", False)
    base = parts[0]
    if base.endswith(".0"):
        base = base[:-2]
    regrind = len(parts) > 1 or base.upper().endswith("-K")
    return (base.replace("-K", "").replace("-k", ""), regrind)


# ------------------------------------------------------------------ veri sınıfı
@dataclass
class Dataset:
    rows: pd.DataFrame
    kalip: pd.DataFrame
    operator_rows: pd.DataFrame  # operatör başına açılmış (explode) satırlar
    notes: list[str] = field(default_factory=list)
    path: str = ""


def _read_main(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=MAIN_SHEET, usecols=range(0, 40))
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    ren = {}
    for c in df.columns:
        if c in _BASE_NAMES:
            ren[c] = _BASE_NAMES[c]
            continue
        m = re.search(r"\b([FD]\d{1,2})$", c)
        if m:
            ren[c] = m.group(1)
    df = df.rename(columns=ren)
    return df


def _read_kalip(path: str) -> pd.DataFrame:
    k = pd.read_excel(path, sheet_name=KALIP_SHEET)
    k.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in k.columns]
    k = k.dropna(subset=["KALIP NO"])
    k["KALIP NO"] = k["KALIP NO"].astype(str).str.strip().str.upper()
    cyc = pd.to_numeric(k.get("Çevrim Süresi"), errors="coerce")
    cyc1 = pd.to_numeric(k.get("Çevrim Süresi (sn)"), errors="coerce")
    out = pd.DataFrame(
        {
            "kalip": k["KALIP NO"],
            "kalip_adi": k.get("ADI-MUHTEVİYATI"),
            "nominal_cevrim": cyc.fillna(cyc1),
            "urun_agirlik_gr": pd.to_numeric(k.get("1 Adet Ürün Ağırlığı (Gr)"), errors="coerce"),
            "yolluk_gr": pd.to_numeric(k.get("Yolluk Ağırlığı (Gr)"), errors="coerce"),
            "kalip_goz": pd.to_numeric(k.get("GÖZ SAYISI"), errors="coerce"),
            "kolon_arasi": pd.to_numeric(k.get("Kolon Arası mm"), errors="coerce"),
            "yukseklik": pd.to_numeric(k.get("Yükseklik mm"), errors="coerce"),
        }
    )
    # aynı kalıp birden fazla satırda olabilir: ilk dolu değeri al
    return out.groupby("kalip", as_index=False).first()


def load_dataset(path: str) -> Dataset:
    notes: list[str] = []
    raw = _read_main(path)
    n_raw = len(raw)

    d = raw[(pd.to_numeric(raw["baski"], errors="coerce") > 0) & raw["urun_kodu"].notna()].copy()
    d = d[d["makine"].notna()]
    notes.append(f"{n_raw:,} satırdan {len(d):,} gerçek üretim kaydı kullanıldı (boş/atıl satırlar elendi).")

    d["tarih"] = pd.to_datetime(d["tarih"], errors="coerce")
    d = d.dropna(subset=["tarih"])
    d["hafta"] = d["tarih"].dt.isocalendar().week.astype(int)
    d["ay"] = d["tarih"].dt.month

    d["makine"] = d["makine"].astype(str).map(_norm_spaces)
    d["istasyon_tipi"] = np.where(d["makine"].str.upper().str.startswith("YAPIŞTIRMA"), "Yapıştırma", "Enjeksiyon")
    d["urun_kodu"] = d["urun_kodu"].astype(str).str.strip()
    d["kalip"] = d["kalip"].map(lambda s: _norm_spaces(tr_upper(s)) or "?")
    d["vardiya"] = d["vardiya"].map({"S": "Sabah", "A": "Akşam"}).fillna("?")

    for c in ["baski", "saglam", "goz", "cevrim"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["cevrim"] = d["cevrim"].where(d["cevrim"] > 0)
    d["saglam"] = d["saglam"].fillna(0)
    d["fire"] = pd.to_numeric(d["fire_ham"], errors="coerce").fillna(0)
    d["uretim"] = d["saglam"] + d["fire"]
    d["fire_orani"] = np.where(d["uretim"] > 0, d["fire"] / d["uretim"], np.nan)

    for c in FIRE_COLS + DURUS_COLS:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0) if c in d.columns else 0.0
    d["durus_dk"] = d[DURUS_COLS].sum(axis=1)

    mat = d["hammadde_ham"].map(clean_material)
    d["hammadde"] = mat.map(lambda t: t[0])
    d["kirma_var"] = mat.map(lambda t: t[1])
    d["kalip_degisti"] = pd.to_numeric(d["kalip_degisti"], errors="coerce").fillna(0).astype(int)

    # --- operatörler: çoklu isim = aynı vardiyada birden fazla kişi
    lists = d["operator_ham"].map(split_operators)
    flat = pd.Series([n for ls in lists for n in ls])
    name_map = build_name_map(flat) if len(flat) else {}
    d["operatorler"] = lists.map(lambda ls: list(dict.fromkeys(name_map.get(n, n) for n in ls)))
    d["operator_sayisi"] = d["operatorler"].map(len)
    n_merged = sum(1 for k, v in name_map.items() if k != v)
    notes.append(
        f"{flat.nunique():,} farklı yazım → {len(set(name_map.values())):,} kişi "
        f"({n_merged} yazım hatası birleştirildi). Birden fazla isim yazılı satırlar ortak vardiya sayıldı."
    )

    kalip = _read_kalip(path)
    d = d.merge(kalip, on="kalip", how="left")
    matched = d["nominal_cevrim"].notna().mean()
    notes.append(f"Kalıp listesiyle eşleşen satır oranı (nominal çevrim): %{matched * 100:.0f}.")

    keep = [
        "hafta", "ay", "tarih", "vardiya", "makine", "istasyon_tipi", "operator_ham", "operatorler",
        "operator_sayisi", "urun_kodu", "urun_adi", "kalip", "kalip_adi", "goz", "hammadde", "kirma_var",
        "lot", "cevrim", "nominal_cevrim", "baski", "saglam", "fire", "uretim", "fire_orani", "kalip_degisti",
        "durus_dk", "urun_agirlik_gr", "yolluk_gr", "kolon_arasi", "yukseklik",
    ] + FIRE_COLS + DURUS_COLS
    d = d[keep].reset_index(drop=True)

    return Dataset(rows=d, kalip=kalip, operator_rows=explode_operators(d), notes=notes, path=path)


def explode_operators(d: pd.DataFrame) -> pd.DataFrame:
    e = d.explode("operatorler").rename(columns={"operatorler": "operator"})
    e = e[e["operator"].notna()].copy()
    e["ortak_vardiya"] = e["operator_sayisi"] > 1
    return e


def chrono(x: pd.DataFrame) -> pd.DataFrame:
    """Kayıtları makine içinde gerçek zaman sırasına dizer: tarih, sonra Sabah vardiyası → Akşam vardiyası, sonra satır sırası.
    (Vardiya adına göre alfabetik sıralama Akşam'ı Sabah'tan önce koyar ve kalıp değişimlerini yanlış sayar.)"""
    vr = x["vardiya"].astype(str).str.lower().map(lambda s: 0 if s.startswith("sa") else 1 if s.startswith("ak") else 2)
    return x.assign(_vr=vr.values, _ix=range(len(x)) if not x.index.is_monotonic_increasing else x.index.values).sort_values(
        ["makine", "tarih", "_vr", "_ix"], kind="stable").drop(columns=["_vr", "_ix"])
