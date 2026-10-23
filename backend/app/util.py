"""Biçim yardımcıları ve JSON-uyumlu çıktı kurucular (arayüz bunlara göre çizer)."""
from __future__ import annotations

import numpy as np
import pandas as pd

TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


# ----------------------------------------------------------------- biçimler
def _nan(x) -> bool:
    return x is None or (isinstance(x, (float, np.floating)) and np.isnan(x))


def fint(x) -> str:
    return "–" if _nan(x) else f"{x:,.0f}".replace(",", ".")


def fnum(x, d=1) -> str:
    return "–" if _nan(x) else f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fpct(x, d=2) -> str:
    return "–" if _nan(x) else fnum(x * 100, d) + "%"


def short(v) -> str:
    a = abs(v)
    if a >= 1e6:
        return fnum(v / 1e6, 1) + " mn"
    if a >= 1e3:
        return fnum(v / 1e3, 0) + " bin"
    return fnum(v, 0)


def dlabel(ts) -> str:
    return f"{ts.day} {TR_MONTHS[ts.month - 1]}"


def b(s) -> str:
    return f"**{s}**"


def clean(o):
    """NaN/Inf -> None, numpy -> python (JSON için)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [clean(v) for v in o.tolist()]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if (np.isnan(o) or np.isinf(o)) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if o is pd.NaT:
        return None
    return o


def kpi(label, value, sub="", tone=None, spark=None):
    return {"label": label, "value": value, "sub": sub, "tone": tone,
            "spark": None if spark is None else [float(v) for v in spark]}


def table(df: pd.DataFrame, fmts: dict | None = None, rules: dict | None = None) -> dict:
    fmts, rules = fmts or {}, rules or {}
    cols = [{"key": c, "label": c, "fmt": fmts.get(c, "text"), "rules": rules.get(c)} for c in df.columns]
    return {"columns": cols, "rows": clean(df.astype(object).where(df.notna(), None).to_dict("records"))}


def weekly(d: pd.DataFrame) -> pd.DataFrame:
    """Tam haftalar (en az 4 farklı gün); etiket = pazartesi tarihi."""
    w = d.groupby("hafta").agg(saglam=("saglam", "sum"), fire=("fire", "sum"), uretim=("uretim", "sum"),
                               durus=("durus_dk", "sum"), kalip=("kalip_degisti", "sum"),
                               gun=("tarih", "nunique"), ilk=("tarih", "min"))
    w = w[w["gun"] >= 4].copy()
    w["pzt"] = w["ilk"] - pd.to_timedelta(w["ilk"].dt.weekday, unit="D")
    w["lab"] = w["pzt"].map(dlabel)
    w["fire_pct"] = w["fire"] / w["uretim"] * 100
    return w


def bars(names, values, tones, labels=None):
    out = []
    for i, (n, v) in enumerate(zip(names, values)):
        out.append({"name": str(n), "value": None if _nan(v) else float(v),
                    "tone": tones[i] if isinstance(tones, list) else tones,
                    "label": labels[i] if labels is not None else None})
    return out


