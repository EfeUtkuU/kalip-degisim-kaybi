import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, Cell, CartesianGrid, ComposedChart, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, Search } from "lucide-react";
import { api } from "./api";
import { getLang, tr } from "./i18n";

export const TONES = {
  teal: "#3fb8c4", red: "#e26a6a", amber: "#e3a866", green: "#8fc25b", slate: "#6b7a90", orange: "#c9853c", muted: "#3a4252",
};
const GRID = "#262b36";
const AXIS = "#7c8494";

// ---------------- biçimler
const NFC = {};
const nf = (d) => {
  const loc = getLang() === "en" ? "en-US" : "tr-TR";
  const k = `${loc}${d}`;
  if (!NFC[k]) NFC[k] = new Intl.NumberFormat(loc, { minimumFractionDigits: d, maximumFractionDigits: d });
  return NFC[k];
};
export const fnum = (v, d = 1) => (v == null || Number.isNaN(v) ? "–" : nf(d).format(v));
export const fshort = (v) => {
  const en = getLang() === "en";
  if (v == null) return "–";
  const a = Math.abs(v);
  if (a >= 1e6) return `${fnum(v / 1e6, 1)} ${en ? "M" : "mn"}`;
  if (a >= 1e3) return `${fnum(v / 1e3, 0)} ${en ? "K" : "bin"}`;
  return fnum(v, 0);
};
const KIND = {
  int: (v) => fnum(v, 0), num0: (v) => fnum(v, 0), num1: (v) => fnum(v, 1), num2: (v) => fnum(v, 2),
  short_adet: (v) => `${fshort(v)} ${getLang() === "en" ? "units" : "adet"}`, pct2: (v) => `%${fnum(v, 2)}`, pct1: (v) => `%${fnum(v, 1)}`, pct0: (v) => `%${fnum(v, 0)}`,
  saat: (v) => `${fnum(v, 0)} ${getLang() === "en" ? "hours" : "saat"}`, degisim: (v) => `${fnum(v, 0)} ${getLang() === "en" ? "changeovers" : "değişim"}`,
  text: (v) => (v == null ? "–" : typeof v === "string" ? tr(v) : String(v)),
};
export const fmtKind = (kind, v) => (KIND[kind] || KIND.text)(v);
const isNumFmt = (k) => k !== "text";

// **kalın** işaretlerini güvenli biçimde göster
export function Rich({ text }) {
  const parts = String(tr(text)).split(/\*\*(.+?)\*\*/g);
  return <>{parts.map((p, i) => (i % 2 ? <b key={i}>{p}</b> : <span key={i}>{p}</span>))}</>;
}

// ---------------- veri çekme
export function useData(path, params, deps = [], enabled = true) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const key = JSON.stringify([path, params, ...deps]);
  useEffect(() => {
    if (!enabled) return undefined;
    let live = true;
    setState((s) => ({ data: s.data, error: null, loading: true }));
    api.get(path, params).then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);
  return state;
}

export function Page({ title, desc, state, children, toolbar, onNeedData }) {
  const { data, error, loading } = state || {};
  return (
    <div>
      <div className="page-head"><h1>{tr(title)}</h1>{desc && <p>{tr(desc)}</p>}</div>
      {toolbar}
      {error && (
        <div className="error-box">
          {tr(error.message)}
          {error.status === 409 && onNeedData && <> <button className="btn secondary" style={{ marginLeft: 12 }} onClick={onNeedData}>{tr("Veri sayfasına git")}</button></>}
        </div>
      )}
      {!error && !data && loading && <div className="loading"><span className="spinner" />{tr("Hesaplanıyor…")}</div>}
      {!error && data && <div style={{ opacity: loading ? 0.6 : 1, transition: "opacity .15s" }}>{children(data)}</div>}
    </div>
  );
}

// ---------------- kartlar
export function Panel({ title, sub, children, style }) {
  return (
    <div className="panel" style={style}>
      {title && <h2>{tr(title)}</h2>}
      {sub && <p className="sub">{tr(sub)}</p>}
      {children}
    </div>
  );
}

function Spark({ values, tone }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <div className="spark">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
          <Line type="monotone" dataKey="v" stroke={TONES[tone] || TONES.slate} strokeWidth={1.6} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Kpis({ items }) {
  return (
    <div className="kpi-grid">
      {items.map((k) => (
        <div className={`kpi-card ${k.tone ? `tone-${k.tone}` : ""}`} key={k.label}>
          <div className="label">{tr(k.label)}</div>
          <div className="value">{tr(k.value)}</div>
          <div className="ksub">{tr(k.sub)}</div>
          {k.spark && k.spark.length > 2 && <Spark values={k.spark} tone={k.tone} />}
        </div>
      ))}
    </div>
  );
}

export function Insights({ items, title = "Özet" }) {
  if (!items || !items.length) return null;
  return (
    <div className="insights">
      <h3>{tr(title)}</h3>
      <ul>{items.map((t, i) => <li key={i}><Rich text={t} /></li>)}</ul>
    </div>
  );
}

export const Hint = ({ children, kind = "" }) => <div className={`hint ${kind}`}>{typeof children === "string" ? tr(children) : children}</div>;

// ---------------- grafikler
const ValueLabel = ({ x, y, width, height, value }) => (
  <text x={x + width + 6} y={y + height / 2} dy={4} fill="#c4cad6" fontSize={11.5}>{value}</text>
);
export const YTick = ({ x, y, payload, fmt }) => (
  <text x={x - 4} y={y} dy={4} textAnchor="end" fill={AXIS} fontSize={11}>{fmt(payload.value)}</text>
);
function Tip({ active, payload, label, fmt }) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tip">
      <b>{tr(p.name ?? label)}</b>
      {tr(p.label ?? (fmt ? fmt(p.value) : fnum(p.value, 2)))}
    </div>
  );
}

/** Çubuk grafik. layout "h": yatay sıralama (isim solda), "v": dikey sütunlar (zaman serisi). */
function useWidth() {
  const ref = useRef(null);
  const [w, setW] = useState(600);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const upd = () => setW(Math.max(120, Math.floor(el.getBoundingClientRect().width)));
    upd();
    const ro = new ResizeObserver(upd);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export function BarsChart(props) {
  const [ref, w] = useWidth();
  return <div ref={ref} className="chart-box"><BarsChartInner {...props} width={w} /></div>;
}

function BarsChartInner({ data, layout = "h", fmt, refAt: refVal, refLabel, height, domainMax, nameWidth: nw = 150, xInterval, width }) {
  const nameWidth = Math.min(nw, Math.round(width * 0.38));
  const rightM = Math.min(130, Math.round(width * 0.24));
  const lang = getLang();
  const rows = useMemo(() => (data || []).map((d) => ({ ...d, name: tr(d.name), lab: tr(d.label ?? (fmt ? fmt(d.value) : fnum(d.value, 1))), v: d.value })), [data, fmt, lang]);
  if (!rows.length) return <div className="empty">{tr("Gösterilecek veri yok.")}</div>;
  const color = (d) => TONES[d.tone] || TONES.teal;
  if (layout === "h") {
    const h = height || Math.max(180, rows.length * 30 + 30);
    return (
      <ResponsiveContainer width="100%" height={h} minWidth={0}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: rightM, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} horizontal={false} />
          <XAxis type="number" hide domain={[0, domainMax || "dataMax"]} />
          <YAxis type="category" dataKey="name" width={nameWidth} tick={{ fill: "#c4cad6", fontSize: 12 }} axisLine={false} tickLine={false} interval={0} />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<Tip fmt={fmt} />} />
          {refVal != null && <ReferenceLine x={refVal} stroke={AXIS} strokeDasharray="4 4" label={{ value: tr(refLabel), fill: AXIS, fontSize: 11, position: "top" }} />}
          <Bar dataKey="v" radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false}>
            {rows.map((d, i) => <Cell key={i} fill={color(d)} />)}
            <LabelList dataKey="lab" content={<ValueLabel />} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height || 280} minWidth={0}>
      <BarChart data={rows} margin={{ top: 16, right: refVal != null ? 84 : 12, left: 0, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="name" tickFormatter={(v) => tr(v)} tick={{ fill: AXIS, fontSize: 11 }} axisLine={{ stroke: GRID }} tickLine={false} interval={xInterval ?? Math.max(0, Math.ceil(rows.length / Math.max(3, Math.floor(width / 60))) - 1)} />
        <YAxis tick={{ fill: AXIS, fontSize: 11 }} axisLine={false} tickLine={false} width={64} tick={<YTick fmt={(v) => (fmt ? fmt(v).replace(/ adet| saat| değişim| units| hours| changeovers/, "") : fnum(v, 0))} />} domain={[0, domainMax || "auto"]} />
        <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<Tip fmt={fmt} />} />
        {refVal != null && <ReferenceLine y={refVal} stroke={AXIS} strokeDasharray="4 4" label={{ value: tr(refLabel), fill: AXIS, fontSize: 11, position: "right" }} />}
        <Bar dataKey="v" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {rows.map((d, i) => <Cell key={i} fill={color(d)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------- tablo
function cellTone(col, v) {
  if (v == null || !col.rules) return "";
  for (const r of col.rules) {
    if ((r.op === "gt" && v > r.v) || (r.op === "lt" && v < r.v) || (r.op === "ge" && v >= r.v)) return `t-${r.tone}`;
  }
  return "";
}

export function DataTable({ table, title, sub, filename = "tablo", pageSize = 100, search = true }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState(null);
  const [limit, setLimit] = useState(pageSize);
  const { columns, rows } = table;
  const view = useMemo(() => {
    let r = rows;
    if (q.trim()) {
      const t = q.toLocaleLowerCase("tr-TR");
      r = r.filter((row) => columns.some((c) => (String(row[c.key] ?? "") + " " + tr(String(row[c.key] ?? ""))).toLocaleLowerCase("tr-TR").includes(t)));
    }
    if (sort) {
      const { key, dir } = sort;
      r = [...r].sort((a, b) => {
        const x = a[key], y = b[key];
        if (x == null) return 1;
        if (y == null) return -1;
        return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), "tr")) * dir;
      });
    }
    return r;
  }, [rows, q, sort, columns]);
  const csv = () => {
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const text = [columns.map((c) => esc(tr(c.label))).join(";"), ...view.map((r) => columns.map((c) => esc(typeof r[c.key] === "number" ? String(r[c.key]).replace(".", ",") : r[c.key])).join(";"))].join("\n");
    const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = `${filename}.csv`; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <Panel title={title} sub={sub}>
      <div className="tbl-tools">
        {search && (
          <div style={{ position: "relative" }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "var(--text-dim)" }} />
            <input className="input" style={{ paddingLeft: 30, width: 220 }} placeholder={tr("Tabloda ara…")} value={q} onChange={(e) => { setQ(e.target.value); setLimit(pageSize); }} />
          </div>
        )}
        <button className="btn secondary" onClick={csv}><Download /> CSV</button>
        <span className="count">{view.length} {tr("satır")}</span>
      </div>
      <div className="tbl-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={isNumFmt(c.fmt) ? "num" : ""} onClick={() => setSort((s) => (s?.key === c.key ? { key: c.key, dir: -s.dir } : { key: c.key, dir: -1 }))}>
                  {tr(c.label)}{sort?.key === c.key ? (sort.dir < 0 ? " ↓" : " ↑") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.slice(0, limit).map((r, i) => (
              <tr key={i}>
                {columns.map((c) => <td key={c.key} className={`${isNumFmt(c.fmt) ? "num" : ""} ${cellTone(c, r[c.key])}`}>{fmtKind(c.fmt, r[c.key])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {view.length > limit && <div className="more"><button className="btn secondary" onClick={() => setLimit(limit + pageSize)}>{tr("Daha fazla göster")} ({view.length - limit})</button></div>}
        {!view.length && <div className="empty">{tr("Eşleşen satır yok.")}</div>}
      </div>
    </Panel>
  );
}

/** Zaman serisi: sütunlar gerçek değer, turuncu basamaklı çizgi bölüm seviyesi, dikey çizgiler değişim noktaları. */
export function SeriesChart({ data, cuts = [], fmt, height = 300 }) {
  if (!data || !data.length) return <div className="empty">{tr("Gösterilecek veri yok.")}</div>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 16, right: 12, left: 0, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="name" tickFormatter={(v) => tr(v)} tick={{ fill: AXIS, fontSize: 11 }} axisLine={{ stroke: GRID }} tickLine={false} interval={Math.max(0, Math.ceil(data.length / 12) - 1)} />
        <YAxis tick={<YTick fmt={(v) => (fmt ? fmt(v) : fnum(v, 1))} />} axisLine={false} tickLine={false} width={64} domain={[0, "auto"]} />
        <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null;
          const p = payload[0].payload;
          return <div className="tip"><b>{tr(`${p.name} haftası`)}</b>{tr("Gerçek")}: {fmt ? fmt(p.value) : fnum(p.value, 2)}<div style={{ color: TONES.orange }}>{tr("Seviye")}: {fmt ? fmt(p.level) : fnum(p.level, 2)}</div></div>;
        }} />
        {cuts.map((c) => <ReferenceLine key={c} x={c} stroke={TONES.red} strokeDasharray="3 3" />)}
        <Bar dataKey="value" fill={TONES.slate} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        <Line type="stepAfter" dataKey="level" stroke={TONES.orange} strokeWidth={2.4} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
