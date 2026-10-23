import { useRef, useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";
import { api } from "../api";
import { Page, Panel } from "../ui";

const iso = (d) => d.toISOString().slice(0, 10);

export default function DataPage({ ctx, title }) {
  const { status, filters, setFilters } = ctx;
  const loaded = !!status?.loaded;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [over, setOver] = useState(false);
  const inp = useRef(null);
  const send = (file) => {
    if (!file) return;
    setBusy(true); setErr(null);
    api.upload(file).then(() => { setFilters({ start: "", end: "" }); return ctx.refreshStatus(); })
      .catch((e) => setErr(e.message)).finally(() => setBusy(false));
  };
  const preset = (days) => {
    const end = new Date(status.max);
    const start = new Date(end); start.setDate(start.getDate() - days + 1);
    setFilters({ start: iso(start), end: iso(end) });
  };
  const isAll = !filters.start && !filters.end;
  return (
    <Page title={title} desc="Excel dosyası ve dönem." state={{ data: {}, loading: false }}>
      {() => (
        <>
          <Panel title="Veri dosyası">
            <div className={`drop ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); send(e.dataTransfer.files?.[0]); }}>
              <h3>{loaded ? <><FileSpreadsheet size={16} style={{ verticalAlign: -3 }} /> {status.name}</> : "Excel dosyasını buraya bırak"}</h3>
              <p>{loaded ? `${status.rows?.toLocaleString("tr-TR")} enjeksiyon kaydı · ${status.machines?.length} makine · ${status.min?.slice(0, 10)} – ${status.max?.slice(0, 10)}` : "ya da aşağıdan seç (.xlsx)"}</p>
              <button className="btn" onClick={() => inp.current.click()} disabled={busy}>
                {busy ? <><span className="spinner" />Dosya okunuyor…</> : <><Upload />{loaded ? "Başka dosya seç" : "Dosya seç"}</>}
              </button>
              <input ref={inp} type="file" accept=".xlsx,.xlsm" hidden onChange={(e) => { send(e.target.files?.[0]); e.target.value = ""; }} />
            </div>
            {err && <div className="error-box" style={{ marginTop: 12 }}>{err}</div>}
          </Panel>
          {loaded && (
            <>
              <Panel title="Dönem">
                <div className="filters">
                  <div className="chips">
                    <button className={`chip ${isAll ? "on" : ""}`} onClick={() => setFilters({ start: "", end: "" })}>Tüm dönem</button>
                    <button className="chip" onClick={() => preset(30)}>Son 30 gün</button>
                    <button className="chip" onClick={() => preset(90)}>Son 90 gün</button>
                    <button className="chip" onClick={() => preset(180)}>Son 180 gün</button>
                  </div>
                  <label className="toolbar" style={{ margin: 0 }}>Başlangıç <input className="input" type="date" value={filters.start} min={status.min?.slice(0, 10)} max={status.max?.slice(0, 10)} onChange={(e) => setFilters({ ...filters, start: e.target.value })} /></label>
                  <label className="toolbar" style={{ margin: 0 }}>Bitiş <input className="input" type="date" value={filters.end} min={status.min?.slice(0, 10)} max={status.max?.slice(0, 10)} onChange={(e) => setFilters({ ...filters, end: e.target.value })} /></label>
                </div>
              </Panel>
              {status.notes?.length > 0 && (
                <Panel title="Veri hazırlama notları">
                  <ul className="notes">{status.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                </Panel>
              )}
            </>
          )}
          
        </>
      )}
    </Page>
  );
}
