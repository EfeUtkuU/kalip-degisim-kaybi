import { useEffect, useRef, useState } from "react";
import { Play, Upload } from "lucide-react";
import { api } from "../api";
import { DataTable, Kpis, Page, Panel, Rich } from "../ui";

const num = (v) => { const x = parseFloat(String(v).replace(/\./g, "").replace(",", ".")); return Number.isFinite(x) ? x : 0; };

export default function Plan({ ctx, title }) {
  const loaded = !!ctx.status?.loaded;
  const [days, setDays] = useState(28);
  const [shifts, setShifts] = useState(2);
  const [avail, setAvail] = useState(80);
  const [demand, setDemand] = useState([]);
  const [res, setRes] = useState(null);
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showDemand, setShowDemand] = useState(false);
  const [err, setErr] = useState(null);
  const fileRef = useRef(null);

  const loadDefault = () => api.get("/plan/demand", { ...ctx.params, days }).then((r) => { setDemand(r.demand || []); setRes(null); }).catch((e) => setErr(e.message));
  useEffect(() => { if (loaded) loadDefault(); /* eslint-disable-next-line */ }, [loaded, ctx.ver]);

  const run = () => {
    setBusy(true); setErr(null);
    api.post("/plan", { demand: demand.filter((r) => r.kalip && num(r.adet) > 0).map((r) => ({ ...r, adet: num(r.adet) })), days, shifts, avail }, ctx.params)
      .then((r) => { setRes(r); setSel(r.selected); }).catch((e) => setErr(e.message)).finally(() => setBusy(false));
  };
  const upd = (i, k, v) => setDemand((d) => d.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const readCsv = (file) => {
    if (!file) return;
    file.text().then((t) => {
      const rows = t.split(/\r?\n/).map((l) => l.split(/[;,\t]/).map((c) => c.trim())).filter((r) => r.length >= 2 && r[0]);
      const out = rows.filter((r) => num(r[r.length - 1]) > 0).map((r) => ({ kalip: r[0], urun: r.length > 2 ? r[1] : "", adet: num(r[r.length - 1]) }));
      if (out.length) { setDemand(out); setRes(null); } else setErr("CSV'de 'kalıp; adet' biçiminde satır bulunamadı.");
    });
  };

  return (
    <Page title={title} desc="Aynı talep için kaç değişim gerekir: geçmiş düzen ile birleştirilmiş planlar."
      state={{ data: loaded ? {} : null, loading: false, error: loaded ? null : { status: 409, message: "Henüz veri yüklenmedi." } }} onNeedData={() => ctx.go("data")}>
      {() => (
        <>
          <Panel title="Talep">
            <div className="toolbar">
              <label>Süre (gün) <input className="input" type="number" min="1" max="90" value={days} onChange={(e) => setDays(+e.target.value || 1)} /></label>
              <label>Vardiya/gün <select className="select" value={shifts} onChange={(e) => setShifts(+e.target.value)}>{[1, 2, 3].map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
              <label>Makine kullanılabilirliği (%) <input className="input" type="number" min="30" max="100" value={avail} onChange={(e) => setAvail(+e.target.value || 80)} /></label>
              <button className="btn secondary" onClick={loadDefault}>Talebi yeniden türet</button>
              <button className="btn secondary" onClick={() => fileRef.current.click()}><Upload />CSV yükle</button>
              <input ref={fileRef} type="file" accept=".csv,.txt" hidden onChange={(e) => { readCsv(e.target.files?.[0]); e.target.value = ""; }} />
              <button className="btn" onClick={run} disabled={busy || !demand.length}>{busy ? <><span className="spinner" />Hesaplanıyor…</> : <><Play />Planı karşılaştır</>}</button>
            </div>
            {err && <div className="error-box" style={{ marginBottom: 12 }}>{err}</div>}
            <button className="link-btn" onClick={() => setShowDemand(!showDemand)}>{showDemand ? "Talep listesini gizle" : `Talep listesini düzenle (${demand.length} kalıp)`}</button>
            {showDemand && <div className="demand-list" style={{ marginTop: 10 }}>
              <div className="demand-row demand-head"><span>Kalıp</span><span>Ürün</span><span>Adet</span><span /></div>
              {demand.map((r, i) => (
                <div className="demand-row" key={i}>
                  <input className="input" value={r.kalip} onChange={(e) => upd(i, "kalip", e.target.value)} />
                  <input className="input" value={r.urun || ""} onChange={(e) => upd(i, "urun", e.target.value)} />
                  <input className="input" value={r.adet} onChange={(e) => upd(i, "adet", e.target.value)} />
                  <button className="chip" onClick={() => setDemand((d) => d.filter((_, j) => j !== i))}>Sil</button>
                </div>
              ))}
              <button className="chip" style={{ marginTop: 8 }} onClick={() => setDemand((d) => [...d, { kalip: "", urun: "", adet: "" }])}>+ Satır ekle</button>
            </div>}
          </Panel>
          {res && (
            <>
              <p className="plan-lead"><Rich text={res.insights[0]} /></p>
              <div className="chips" style={{ marginBottom: 12 }}>
                {res.scenarios.map((s) => <button key={s} className={`chip ${sel === s ? "on" : ""}`} onClick={() => setSel(s)}>{s}</button>)}
              </div>
              <Kpis items={res.kpis} />
              <DataTable table={res.table} title="Senaryolar" filename="senaryolar" search={false} />
              {res.shifts?.[sel]?.rows?.length > 0 && <DataTable table={res.shifts[sel]} title="Hangi kalıp hangi makineye alınmalı" sub="Plan, kalıbı geçmişte en çok çalıştığı makineden başka makineye alıyor. Kazanç: o kalıp için makine saati." filename="makine_degisikligi" pageSize={15} search={false} />}
              {res.lines?.[sel] && <DataTable table={res.lines[sel]} title={`Plan satırları: ${sel}`} filename="plan_satirlari" pageSize={25} />}
            </>
          )}
          {res && <p className="ol-note">{res.insights[res.insights.length - 1]}</p>}
        </>
      )}
    </Page>
  );
}
