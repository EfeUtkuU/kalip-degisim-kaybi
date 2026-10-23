"""Saha kayıtları ve hedefler için küçük yerel veritabanı (SQLite, uygulama veri klasöründe)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

STEPS = [
    {"key": "hazirlik", "label": "Hazırlık: kalıp, ekipman, malzeme hazır", "dis": True},
    {"key": "sokum", "label": "Eski kalıbı çıkar", "dis": False},
    {"key": "temizlik", "label": "Makine, yolluk ve malzeme temizliği", "dis": False},
    {"key": "montaj", "label": "Yeni kalıbı tak ve bağla", "dis": False},
    {"key": "baglanti", "label": "Su, hava, elektrik bağlantıları", "dis": False},
    {"key": "isitma", "label": "Isıtma ve ayar", "dis": True},
    {"key": "deneme", "label": "İlk deneme baskıları ve onay", "dis": False},
]
STEP_KEYS = [s["key"] for s in STEPS]

_lock = threading.Lock()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        with self._c() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, tarih TEXT, vardiya TEXT, makine TEXT,
                onceki_kalip TEXT, yeni_kalip TEXT, toplam_dk REAL, adimlar TEXT, ilk_deneme_fire REAL, operator TEXT, not_ TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, metrik TEXT, deger REAL, baslangic TEXT, baz REAL)""")

    def _c(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return _Ctx(c)

    # ---- kayıtlar
    def add_log(self, r: dict) -> int:
        steps = {k: max(float(r.get("adimlar", {}).get(k, 0) or 0), 0.0) for k in STEP_KEYS}   # dakika
        total = float(r.get("toplam_dk") or 0) or sum(steps.values())
        if total <= 0:
            raise ValueError("Toplam süre sıfır olamaz.")
        with _lock, self._c() as c:
            cur = c.execute("INSERT INTO logs (created,tarih,vardiya,makine,onceki_kalip,yeni_kalip,toplam_dk,adimlar,ilk_deneme_fire,operator,not_) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (datetime.now().isoformat(timespec="seconds"), r.get("tarih") or datetime.now().date().isoformat(), r.get("vardiya") or "",
                             r.get("makine") or "", (r.get("onceki_kalip") or "").strip().upper(), (r.get("yeni_kalip") or "").strip().upper(), total,
                             json.dumps(steps), float(r.get("ilk_deneme_fire") or 0), (r.get("operator") or "").strip(), (r.get("not") or "").strip()))
            return int(cur.lastrowid)

    def logs(self) -> list:
        with self._c() as c:
            rows = c.execute("SELECT * FROM logs ORDER BY tarih DESC, id DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["adimlar"] = json.loads(d["adimlar"] or "{}")
            d["not"] = d.pop("not_")
            out.append(d)
        return out

    def delete_log(self, i: int):
        with _lock, self._c() as c:
            c.execute("DELETE FROM logs WHERE id=?", (i,))

    # ---- hedefler
    def set_target(self, metrik: str, deger: float, baslangic: str, baz: float | None) -> int:
        with _lock, self._c() as c:
            cur = c.execute("INSERT INTO targets (created,metrik,deger,baslangic,baz) VALUES (?,?,?,?,?)",
                            (datetime.now().isoformat(timespec="seconds"), metrik, float(deger), baslangic, baz))
            return int(cur.lastrowid)

    def targets(self) -> list:
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM targets ORDER BY id DESC").fetchall()]

    def delete_target(self, i: int):
        with _lock, self._c() as c:
            c.execute("DELETE FROM targets WHERE id=?", (i,))


class _Ctx:
    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self.c

    def __exit__(self, et, ev, tb):
        if et is None:
            self.c.commit()
        self.c.close()
        return False
