import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3, CalendarClock, Lightbulb, Database, Repeat, Target, Timer } from "lucide-react";
import { api } from "./api";
import Ozet from "./pages/Ozet";
import Oneri from "./pages/Oneri";
import Plan from "./pages/Plan";
import Kayit from "./pages/Kayit";
import Hedef from "./pages/Hedef";
import DataPage from "./pages/DataPage";

const ITEMS = [
  { key: "oneri", label: "Öneriler", icon: Lightbulb },
  { key: "ozet", label: "Rakamlar", icon: BarChart3 },
  { key: "plan", label: "Plan", icon: CalendarClock },
  { key: "kayit", label: "Saha kaydı", icon: Timer },
  { key: "hedef", label: "Hedef", icon: Target },
];
const ALL = [...ITEMS, { key: "data", label: "Veri" }];
const PAGES = { oneri: Oneri, ozet: Ozet, plan: Plan, kayit: Kayit, hedef: Hedef, data: DataPage };

function loadFilters() {
  try { const v = JSON.parse(localStorage.getItem("deg_filters") || "null"); if (v) return v; } catch { /* yok */ }
  return { start: "", end: "" };
}

export default function App() {
  const [tab, setTab] = useState("oneri");
  const [filters, setFiltersRaw] = useState(loadFilters);
  const [status, setStatus] = useState(null);
  const [ver, setVer] = useState(0);
  const setFilters = useCallback((f) => {
    setFiltersRaw(f);
    try { localStorage.setItem("deg_filters", JSON.stringify(f)); } catch { /* sorun değil */ }
  }, []);
  const refreshStatus = useCallback(() => api.get("/status").then((s) => { setStatus(s); setVer((v) => v + 1); return s; }).catch(() => setStatus({ loaded: false })), []);
  useEffect(() => { refreshStatus().then((s) => { if (s && !s.loaded) setTab("data"); }); }, [refreshStatus]);
  const params = useMemo(() => ({ start: filters.start || undefined, end: filters.end || undefined }), [filters]);
  const Page = PAGES[tab];
  const cur = ALL.find((i) => i.key === tab);
  const ctx = { params, ver, filters, setFilters, status, refreshStatus, go: setTab };

  return (
    <div className="app-shell">
      <nav className="sidebar" aria-label="Ana menü">
        <div className="brand">
          <span className="brand-mark"><Repeat /></span>
          <span className="brand-text"><span className="brand-name">Kalıp Değişim Kaybı</span></span>
        </div>
        <div className="nav-scroll">
          {ITEMS.map((i) => { const I = i.icon; return (
            <button key={i.key} className={`nav-item ${tab === i.key ? "active" : ""}`} onClick={() => setTab(i.key)}>
              <I /><span className="nav-label">{i.label}</span>
            </button>); })}
        </div>
        <button className="file-chip" onClick={() => setTab("data")}>
          {status?.loaded ? (<><strong>{status.name}</strong><span>{status.min?.slice(0, 10)} – {status.max?.slice(0, 10)}{filters.start || filters.end ? " · filtreli" : ""}</span></>)
            : (<><strong>Veri yüklenmedi</strong><span>Excel seçmek için tıkla</span></>)}
        </button>
      </nav>
      <main className="app-main" key={tab}>
        {status && <Page ctx={ctx} title={cur?.label} />}
      </main>
    </div>
  );
}
