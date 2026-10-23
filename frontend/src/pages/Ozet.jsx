import { useState } from "react";
import { BarsChart, DataTable, Kpis, Page, Panel, fnum, useData } from "../ui";

const TABS = [
  { k: "hafta", l: "Haftalık" }, { k: "makine", l: "Makine" }, { k: "kalip", l: "Kalıp" },
  { k: "ay", l: "Ay" }, { k: "vardiya", l: "Vardiya" }, { k: "gun", l: "Gün" }, { k: "sure", l: "Girilen süreler" },
];

export default function Ozet({ ctx, title }) {
  const st = useData("/summary", ctx.params, [ctx.ver], !!ctx.status?.loaded);
  const [tab, setTab] = useState("hafta");
  return (
    <Page title={title} desc="Bakmak istediğin konuyu seç."
      state={ctx.status?.loaded ? st : { data: null, loading: false, error: { status: 409, message: "Henüz veri yüklenmedi." } }} onNeedData={() => ctx.go("data")}>
      {(d) => !d.kpis?.length ? <div className="hint warn">{d.insights?.[0]}</div> : (
        <>
          <Kpis items={d.kpis.slice(0, 4)} />
          <div className="chips" style={{ margin: "4px 0 14px" }}>
            {TABS.map((t) => <button key={t.k} className={`chip ${tab === t.k ? "on" : ""}`} onClick={() => setTab(t.k)}>{t.l}</button>)}
          </div>
          {tab === "hafta" && <Panel title="Haftalık kayıp (saat)" sub="Kesikli çizgi dönem ortalaması."><BarsChart layout="v" data={d.weekly} fmt={(v) => `${fnum(v, 0)} saat`} refAt={d.weekly_avg} refLabel={`Ort. ${fnum(d.weekly_avg, 0)}`} /></Panel>}
          {tab === "makine" && (<>
            <Panel title="Makineye göre kayıp (saat)"><BarsChart data={d.machines} fmt={(v) => `${fnum(v, 0)} saat`} nameWidth={150} /></Panel>
            <DataTable table={d.machine_table} title="Ayrıntı" filename="makine_kaybi" pageSize={20} search={false} />
          </>)}
          {tab === "kalip" && <DataTable table={d.molds} title="En çok kayıp yaratan kalıplar" filename="kalip_kaybi" pageSize={15} search={false} />}
          {tab === "ay" && <Panel title="Aya göre kayıp (saat)"><BarsChart data={d.months} fmt={(v) => `${fnum(v, 0)} saat`} nameWidth={90} /></Panel>}
          {tab === "vardiya" && <Panel title="Vardiyaya göre ortalama süre"><BarsChart data={d.shift} fmt={(v) => `${fnum(v, 0)} dk`} nameWidth={90} height={150} /></Panel>}
          {tab === "gun" && <Panel title="Güne göre değişim sıklığı" sub="100 vardiyada kaç kalıp değişimi."><BarsChart data={d.weekday} fmt={(v) => fnum(v, 1)} nameWidth={100} /></Panel>}
          {tab === "sure" && <Panel title="Girilen süreler" sub="Tek bir değerin baskın olması, sürenin ölçülmeyip yuvarlandığını gösterir."><BarsChart data={d.hist} fmt={(v) => `${v} kez`} nameWidth={80} /></Panel>}
          <p className="ol-note">{d.note}</p>
        </>
      )}
    </Page>
  );
}
