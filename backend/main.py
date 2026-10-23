"""Kalıp Değişim Kaybı - FastAPI arka ucu (masaüstü uygulamasında arayüzü de sunar)."""
from __future__ import annotations

import csv
import io
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import change as C  # noqa: E402
from app.data import load_dataset  # noqa: E402
from app.store import STEPS, Store  # noqa: E402
from app.util import clean  # noqa: E402


def data_dir() -> Path:
    env = os.environ.get("DEG_DATA_DIR")
    if env:
        p = Path(env)
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "KalipDegisimKaybi"
    else:
        p = Path.home() / ".kalip-degisim-kaybi"
    p.mkdir(parents=True, exist_ok=True)
    return p


DATA_FILE = data_dir() / "veri.xlsx"
NAME_FILE = data_dir() / "dosya_adi.txt"
STORE = Store(data_dir() / "degisim.sqlite")

app = FastAPI(title="Kalıp Değişim Kaybı")
_lock = threading.Lock()
STATE: dict = {"ds": None, "name": "", "version": 0, "cache": {}}


def _load(path: Path, name: str):
    ds = load_dataset(str(path))
    with _lock:
        STATE.update(ds=ds, name=name, version=STATE["version"] + 1, cache={})


def _autoload():
    if DATA_FILE.exists() and STATE["ds"] is None:
        try:
            _load(DATA_FILE, NAME_FILE.read_text(encoding="utf-8") if NAME_FILE.exists() else DATA_FILE.name)
        except Exception as e:  # noqa: BLE001
            print("Kayıtlı veri okunamadı:", e)


_autoload()


def _ds():
    if STATE["ds"] is None:
        raise HTTPException(409, "Henüz veri yüklenmedi. Veri sayfasından Excel dosyasını seç.")
    return STATE["ds"]


def frames(start: Optional[str], end: Optional[str]):
    ds = _ds()
    key = (STATE["version"], start, end)
    c = STATE["cache"]
    if key not in c:
        d = ds.rows[ds.rows["istasyon_tipi"] == "Enjeksiyon"]
        if start:
            d = d[d["tarih"] >= pd.Timestamp(start)]
        if end:
            d = d[d["tarih"] <= pd.Timestamp(end)]
        if len(c) > 12:
            c.clear()
        c[key] = d
    d = c[key]
    if d.empty:
        raise HTTPException(422, "Seçili dönemde kayıt yok. Dönemi genişlet.")
    return d


def Q(start=Query(None), end=Query(None)):
    return start, end


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/status")
def status():
    ds = STATE["ds"]
    if ds is None:
        return {"loaded": False}
    r = ds.rows[ds.rows["istasyon_tipi"] == "Enjeksiyon"]
    return clean({"loaded": True, "name": STATE["name"], "rows": len(r), "machines": sorted(r["makine"].unique()), "molds": sorted(r["kalip"].dropna().astype(str).unique()),
                  "min": r["tarih"].min(), "max": r["tarih"].max(), "notes": ds.notes})


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Lütfen bir Excel (.xlsx) dosyası seç.")
    tmp = Path(tempfile.mkdtemp()) / "veri.xlsx"
    with open(tmp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        _load(tmp, file.filename)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Dosya okunamadı: {e}. 'Üretim Verileri' sayfası bulunmalı.")
    shutil.copy(tmp, DATA_FILE)
    NAME_FILE.write_text(file.filename, encoding="utf-8")
    return status()


# ---------------------------------------------------------------- kayıp özeti
@app.get("/api/summary")
def summary(q=Depends(Q)):
    return C.summary(frames(*q))


# ---------------------------------------------------------------- çıkarımlar
@app.get("/api/cikarim")
def cikarim(vardiya: float = 12, q=Depends(Q)):
    from app import inference as INF
    d = frames(*q)
    logs = STORE.logs()
    key = ("cikarim", STATE["version"], q, vardiya, len(logs), logs[-1]["id"] if logs else 0)
    c = STATE["cache"]
    if key not in c:
        c[key] = INF.oneriler(d, logs, STEPS, vardiya)
    return c[key]


# ---------------------------------------------------------------- plan karşılaştırması
@app.get("/api/plan/demand")
def plan_demand(days: int = 28, q=Depends(Q)):
    d = frames(*q)
    return clean({"demand": C.default_demand(d, max(1, min(days, 120))).to_dict("records")})


class PlanReq(BaseModel):
    demand: list[dict]
    days: int = 28
    shifts: float = 2
    avail: float = 80


@app.post("/api/plan")
def plan(req: PlanReq, q=Depends(Q)):
    d = frames(*q)
    if not req.demand:
        raise HTTPException(422, "Talep listesi boş.")
    try:
        return C.plan_compare(d, req.demand, max(1, min(req.days, 120)), max(1, min(int(req.shifts), 3)), max(10.0, min(req.avail, 100.0)))
    except RuntimeError as e:
        raise HTTPException(422, str(e))


# ---------------------------------------------------------------- saha kaydı
@app.get("/api/steps")
def steps():
    return {"steps": STEPS}


class LogReq(BaseModel):
    tarih: Optional[str] = None
    vardiya: Optional[str] = None
    makine: str
    onceki_kalip: Optional[str] = None
    yeni_kalip: Optional[str] = None
    toplam_dk: Optional[float] = None
    adimlar: dict = {}
    ilk_deneme_fire: Optional[float] = 0
    operator: Optional[str] = None
    not_: Optional[str] = None


@app.post("/api/logs")
def add_log(req: LogReq):
    r = req.dict()
    r["not"] = r.pop("not_", None)
    try:
        i = STORE.add_log(r)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"id": i}


def _excel_by_machine():
    ds = STATE["ds"]
    if ds is None:
        return None
    try:
        _, ev, _ = C.events(ds.rows)
        return ev[ev["kayitli"]].groupby("makine")["D2"].mean().to_dict()
    except Exception:  # noqa: BLE001
        return None


@app.get("/api/logs")
def list_logs():
    logs = STORE.logs()
    return clean({"logs": logs, "analysis": C.logs_analysis(logs, STEPS, _excel_by_machine()), "steps": STEPS})


@app.delete("/api/logs/{log_id}")
def del_log(log_id: int):
    STORE.delete_log(log_id)
    return {"ok": True}


@app.get("/api/logs/export")
def export_logs():
    logs = STORE.logs()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    keys = [s["key"] for s in STEPS]
    w.writerow(["tarih", "vardiya", "makine", "onceki_kalip", "yeni_kalip", "toplam_dk"] + keys + ["ilk_deneme_fire", "operator", "not"])
    for r in logs:
        w.writerow([r["tarih"], r["vardiya"], r["makine"], r["onceki_kalip"], r["yeni_kalip"], str(round(r["toplam_dk"], 1)).replace(".", ",")]
                   + [str(round(r["adimlar"].get(k, 0), 1)).replace(".", ",") for k in keys] + [r["ilk_deneme_fire"], r["operator"], r["not"]])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=degisim_kayitlari.csv"})


# ---------------------------------------------------------------- hedefler
class TargetReq(BaseModel):
    metrik: str
    deger: float
    baslangic: Optional[str] = None


@app.get("/api/targets")
def targets(q=Depends(Q)):
    d = frames(*q)
    return C.targets_status(d, STORE.targets(), STORE.logs())


@app.post("/api/targets")
def add_target(req: TargetReq, q=Depends(Q)):
    if req.metrik not in C.METRIC:
        raise HTTPException(422, "Bilinmeyen hedef türü.")
    d = frames(*q)
    sug = C.targets_status(d, [], [])["suggest"][req.metrik]
    return {"id": STORE.set_target(req.metrik, req.deger, req.baslangic or pd.Timestamp.today().date().isoformat(), sug["baz"])}


@app.delete("/api/targets/{tid}")
def del_target(tid: int):
    STORE.delete_target(tid)
    return {"ok": True}


def _dist() -> Optional[Path]:
    for p in (Path(getattr(sys, "_MEIPASS", "")) / "frontend_dist", Path(__file__).parent / "frontend_dist"):
        if (p / "index.html").exists():
            return p
    return None


_D = _dist()
if _D:
    app.mount("/assets", StaticFiles(directory=_D / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = _D / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(_D / "index.html")
