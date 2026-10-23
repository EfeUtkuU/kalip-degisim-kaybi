import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Pause, Play, Square, Trash2 } from "lucide-react";
import { api } from "../api";
import { BarsChart, DataTable, Hint, Kpis, Page, Panel, Rich, fnum, useData } from "../ui";

const KEY = "deg_session";
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const today = () => new Date().toISOString().slice(0, 10);
const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } };
const save = (v) => { try { v ? localStorage.setItem(KEY, JSON.stringify(v)) : localStorage.removeItem(KEY); } catch { /* yok */ } };

export default function Kayit({ ctx, title }) {
  const [steps, setSteps] = useState([]);
  const [ver, setVer] = useState(0);
  const logs = useData("/logs", {}, [ver], true);
  const [form, setForm] = useState({ tarih: today(), vardiya: "", makine: "", onceki_kalip: "", yeni_kalip: "", ilk_deneme_fire: 0, operator: "", not_: "" });
  const [manual, setManual] = useState({});
  const [sess, setSess] = useState(load);   // {acc:{step:sn}, cur, since}
  const [, tick] = useState(0);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const iv = useRef(null);

  useEffect(() => { api.get("/steps").then((r) => setSteps(r.steps)); }, []);
  useEffect(() => { iv.current = setInterval(() => tick((x) => x + 1), 500); return () => clearInterval(iv.current); }, []);
  const machines = ctx.status?.machines || [];
  const molds = ctx.status?.molds || [];

  const elapsed = (k) => {
    const base = sess?.acc?.[k] || 0;
    return base + (sess?.cur === k && sess.since ? (Date.now() - sess.since) / 1000 : 0);
  };
  const start = (k) => {
    const acc = { ...(sess?.acc || {}) };
    if (sess?.cur) acc[sess.cur] = (acc[sess.cur] || 0) + (Date.now() - sess.since) / 1000;
    const n = { acc, cur: k, since: Date.now() }; setSess(n); save(n);
  };
  const pause = () => {
    if (!sess?.cur) return;
    const acc = { ...sess.acc, [sess.cur]: (sess.acc[sess.cur] || 0) + (Date.now() - sess.since) / 1000 };
    const n = { acc, cur: null, since: null }; setSess(n); save(n);
  };
  const reset = () => { setSess(null); save(null); setManual({}); };
  const mins = (k) => (sess ? elapsed(k) / 60 : 0) + (parseFloat(String(manual[k] ?? "").replace(",", ".")) || 0);
  const total = steps.reduce((a, s) => a + mins(s.key), 0);

  const submit = () => {
    setErr(null); setMsg(null);
    if (!form.makine) { setErr("Makineyi seç."); return; }
    if (!(total > 0)) { setErr("En az bir adıma süre gir ya da kronometreyi çalıştır."); return; }
    const adimlar = Object.fromEntries(steps.map((s) => [s.key, Math.round(mins(s.key) * 10) / 10]));
    api.post("/logs", { ...form, ilk_deneme_fire: +form.ilk_deneme_fire || 0, adimlar, toplam_dk: Math.round(total * 10) / 10 })
      .then(() => { setMsg(`Kayıt eklendi (${fnum(total, 0)} dk).`); reset(); setVer((v) => v + 1); })
      .catch((e) => setErr(e.message));
  };
  const del = (id) => api.del(`/logs/${id}`).then(() => setVer((v) => v + 1));
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const a = logs.data?.analysis;
  const table = useMemo(() => {
    const L = logs.data?.logs || [];
    return { columns: [
      { key: "tarih", label: "Tarih", fmt: "text" }, { key: "makine", label: "Makine", fmt: "text" }, { key: "yeni_kalip", label: "Yeni kalıp", fmt: "text" },
      { key: "toplam_dk", label: "Süre (dk)", fmt: "num0" }, { key: "ilk_deneme_fire", label: "İlk deneme fire", fmt: "int" }, { key: "id", label: "No", fmt: "int" },
    ], rows: L.map((l) => ({ ...l })).reverse() };
  }, [logs.data]);

  return (
    <Page title={title} desc="Değişimi adım adım ölç."
      state={{ data: {}, loading: false }}>
      {() => (
        <>
          <Panel title="Yeni kayıt" sub="Adıma bas, süre işlesin. Başka adıma basınca öncekini durdurur.">
            <div className="form-grid">
              <label>Tarih<input className="input" type="date" value={form.tarih} onChange={set("tarih")} /></label>
              <label>Vardiya<select className="select" value={form.vardiya} onChange={set("vardiya")}><option value="">–</option><option>Sabah</option><option>Akşam</option></select></label>
              <label>Makine<select className="select" value={form.makine} onChange={set("makine")}><option value="">Seç…</option>{machines.map((m) => <option key={m}>{m}</option>)}</select></label>
              <label>Önceki kalıp<input className="input" list="mold-list" value={form.onceki_kalip} onChange={set("onceki_kalip")} /></label>
              <label>Yeni kalıp<input className="input" list="mold-list" value={form.yeni_kalip} onChange={set("yeni_kalip")} /></label>
              <label>İlk deneme fire (adet)<input className="input" type="number" min="0" value={form.ilk_deneme_fire} onChange={set("ilk_deneme_fire")} /></label>
              <label>Operatör<input className="input" value={form.operator} onChange={set("operator")} /></label>
              <label>Not<input className="input" value={form.not_} onChange={set("not_")} /></label>
              <datalist id="mold-list">{molds.map((m) => <option key={m} value={m} />)}</datalist>
            </div>
            <div className="step-list">
              {steps.map((s) => {
                const on = sess?.cur === s.key;
                return (
                  <div key={s.key} className={`step-row ${on ? "running" : ""}`}>
                    <button className={`step-btn ${on ? "on" : ""}`} onClick={() => (on ? pause() : start(s.key))} aria-label={on ? "Durdur" : "Başlat"}>{on ? <Pause /> : <Play />}</button>
                    <div className="step-name">{s.label}{s.dis && <span className="tag">dışa alınabilir</span>}</div>
                    <div className="step-time">{fmt(elapsed(s.key))}</div>
                    <input className="input step-manual" placeholder="+ dk" value={manual[s.key] ?? ""} onChange={(e) => setManual({ ...manual, [s.key]: e.target.value })} />
                  </div>
                );
              })}
            </div>
            <div className="toolbar" style={{ marginTop: 14 }}>
              <strong style={{ color: "var(--text)", fontSize: 15 }}>Toplam: {fnum(total, 1)} dk</strong>
              <button className="btn" onClick={submit}><Square />Kaydı bitir</button>
              <button className="btn secondary" onClick={reset}>Sıfırla</button>
            </div>
            {err && <div className="error-box">{err}</div>}
            {msg && <Hint>{msg}</Hint>}
          </Panel>

          {a && (a.n > 0 ? (
            <>
              <p className="plan-lead"><Rich text={a.insights[0]} /></p>
              <Kpis items={a.kpis} />
              <div className="grid2 grid-gap">
                <Panel title="Adımların ortalama süresi (dk)"><BarsChart data={a.steps} fmt={(v) => `${fnum(v, 1)} dk`} nameWidth={220} /></Panel>
                <Panel title="Haftalık ortalama süre (dk)"><BarsChart layout="v" data={a.weekly} fmt={(v) => `${fnum(v, 0)} dk`} /></Panel>
              </div>
              {a.machines?.rows?.length > 0 && <DataTable table={a.machines} title="Makine bazında" filename="saha_makine" search={false} />}
            </>
          ) : <Hint>{a.insights?.[0]}</Hint>)}

          <DataTable table={table} title="Kayıtlar" filename="saha_kayitlari" pageSize={15} search={false} />
          <div className="toolbar">
            <label>Kaydı sil (No) <select className="select" defaultValue="" onChange={(e) => { if (e.target.value) { del(e.target.value); e.target.value = ""; } }}>
              <option value="">Seç…</option>{(logs.data?.logs || []).map((l) => <option key={l.id} value={l.id}>{l.id} · {l.tarih} · {l.makine}</option>)}</select></label>
            <a className="btn secondary" href="/api/logs/export"><Download />CSV indir</a>
          </div>
        </>
      )}
    </Page>
  );
}
