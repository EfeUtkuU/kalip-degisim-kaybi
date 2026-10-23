import { useState } from "react";
import { ChevronRight, HelpCircle } from "lucide-react";
import { DataTable, Page, Kpis, Rich, useData } from "../ui";

function Row({ n, it, open, onToggle, go }) {
  const [why, setWhy] = useState(false);
  return (
    <div className={`ol-item ${open ? "open" : ""}`}>
      <button className="ol-head" onClick={onToggle} aria-expanded={open}>
        <span className="ol-n">{n}</span>
        <span className="ol-main">
          <span className="ol-title">{it.baslik}</span>
          <span className="ol-sub">{it.kisa}</span>
        </span>
        <span className={`ol-gain ${it.dogrula ? "warn" : ""}`}>{it.kazanc}</span>
        <ChevronRight className="ol-chev" />
      </button>
      {open && (
        <div className="ol-body">
          {it.hedef && <div className="ol-target"><span>Hedef</span>{it.hedef}</div>}
          <div className="ol-label">Ne yapılabilir</div>
          <ul className="ol-list">{it.nasil.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <div className="ol-actions">
            {it.git && <button className="btn secondary" onClick={() => go(it.git)}>{it.git === "plan" ? "Planı karşılaştır" : "Saha kaydına git"}</button>}
            <button className={`btn ${why ? "" : "secondary"}`} onClick={() => setWhy(!why)}><HelpCircle />{why ? "Gerekçeyi gizle" : "Neden böyle?"}</button>
          </div>
          {why && (
            <div className="ol-why">
              <ul className="ol-list">{it.neden.map((t, i) => <li key={i}>{t}</li>)}</ul>
              {it.tablo && <DataTable table={it.tablo} filename={`oneri_${it.id}`} pageSize={10} search={false} />}
              {it.dikkat && <p className="ol-note">{it.dikkat}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Oneri({ ctx, title }) {
  const [vardiya, setVardiya] = useState(12);
  const [open, setOpen] = useState(0);
  const st = useData("/cikarim", { ...ctx.params, vardiya }, [ctx.ver], !!ctx.status?.loaded);
  return (
    <Page title={title} desc="Verideki kayıpları en büyükten küçüğe sıraladık. Birine tıklayınca ne yapılabileceğini görürsün."
      state={ctx.status?.loaded ? st : { data: null, loading: false, error: { status: 409, message: "Henüz veri yüklenmedi." } }} onNeedData={() => ctx.go("data")}>
      {(d) => !d.oneriler?.length ? <div className="hint warn">{d.uyari}</div> : (
        <>
          <Kpis items={d.kpis} />
          <div className="toolbar" style={{ marginTop: 4 }}>
            <label>Vardiya süresi (saat) <input className="input" type="number" min="6" max="24" value={vardiya} onChange={(e) => setVardiya(+e.target.value || 12)} /></label>
            <span>Saat hesapları bu değere göre değişir.</span>
          </div>
          <div className="ol">
            {d.oneriler.map((it, i) => <Row key={it.id} n={i + 1} it={it} open={open === i} onToggle={() => setOpen(open === i ? -1 : i)} go={ctx.go} />)}
          </div>
        </>
      )}
    </Page>
  );
}
