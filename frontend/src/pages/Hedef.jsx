import { useState } from "react";
import { Target } from "lucide-react";
import { api } from "../api";
import { BarsChart, Kpis, Page, Panel, fnum, useData } from "../ui";

export default function Hedef({ ctx, title }) {
  const [ver, setVer] = useState(0);
  const loaded = !!ctx.status?.loaded;
  const st = useData("/targets", ctx.params, [ctx.ver, ver], loaded);
  const [metrik, setMetrik] = useState("ort_sure");
  const [deger, setDeger] = useState("");
  const [err, setErr] = useState(null);
  const sug = st.data?.suggest || {};
  const add = () => {
    setErr(null);
    const v = parseFloat(String(deger).replace(",", "."));
    if (!(v > 0)) { setErr("Geçerli bir hedef değeri gir."); return; }
    api.post("/targets", { metrik, deger: v }, ctx.params).then(() => { setDeger(""); setVer((x) => x + 1); }).catch((e) => setErr(e.message));
  };
  return (
    <Page title={title} desc="Hedef koy, haftalık ilerlemeyi izle."
      state={loaded ? st : { data: null, error: { status: 409, message: "Henüz veri yüklenmedi." } }} onNeedData={() => ctx.go("data")}>
      {(d) => (
        <>
          <Panel title="Yeni hedef">
            <div className="toolbar">
              <label>Ölçüt <select className="select" value={metrik} onChange={(e) => { setMetrik(e.target.value); setDeger(""); }}>
                {Object.entries(sug).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
              {sug[metrik] && <span>Baz: <b>{fnum(sug[metrik].baz, 1)}</b> · Önerilen hedef: <button className="chip" onClick={() => setDeger(String(Math.round(sug[metrik].onerilen * 10) / 10).replace(".", ","))}>{fnum(sug[metrik].onerilen, 1)}</button></span>}
              <input className="input" placeholder="Hedef değer" value={deger} onChange={(e) => setDeger(e.target.value)} />
              <button className="btn" onClick={add}><Target />Hedef koy</button>
            </div>
            {err && <div className="error-box">{err}</div>}
          </Panel>
          
          {d.targets?.map((t) => {
            const pr = t.ilerleme;
            return (
              <Panel key={t.id} title={t.label} sub={`Hedef ${fnum(t.hedef, 1)} · baz ${fnum(t.baz, 1)}`}>
                <Kpis items={[
                  { label: "Güncel (son 4 hafta)", value: fnum(t.guncel, 1), sub: `baz ${fnum(t.baz, 1)}`, tone: "teal" },
                  { label: "Hedefe ilerleme", value: `%${fnum(Math.max(pr, -99), 0)}`, sub: pr >= 100 ? "Hedefe ulaşıldı" : pr < 0 ? "Baz değerin gerisinde" : "Yolda", tone: pr >= 100 ? "green" : pr < 0 ? "red" : "amber" },
                  ...(t.saha != null ? [{ label: "Saha ölçümü", value: fnum(t.saha, 1), sub: "kendi kayıtların", tone: "teal" }] : []),
                ]} />
                <BarsChart layout="v" data={t.seri} fmt={(v) => fnum(v, 1)} refAt={t.hedef} refLabel={`Hedef ${fnum(t.hedef, 0)}`} />
                <div style={{ marginTop: 10 }}><button className="chip" onClick={() => api.del(`/targets/${t.id}`).then(() => setVer((x) => x + 1))}>Hedefi sil</button></div>
              </Panel>
            );
          })}
        </>
      )}
    </Page>
  );
}
