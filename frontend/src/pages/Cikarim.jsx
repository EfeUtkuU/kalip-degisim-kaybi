import { BarsChart, DataTable, Hint, Kpis, Page, Panel, Rich, useData } from "../ui";

const TONE = { "Güçlü": "#8fc25b", "Orta": "#e3a866", "Bilgi": "#6b7a90" };

function Block({ label, text }) {
  if (!text) return null;
  return (
    <div className="cx-block">
      <div className="cx-label">{label}</div>
      <div className="cx-text"><Rich text={text} /></div>
    </div>
  );
}

export default function Cikarim({ ctx, title }) {
  const st = useData("/cikarim", ctx.params, [ctx.ver], !!ctx.status?.loaded);
  return (
    <Page title={title} desc="Tablolara bakmak yerine verinin kendi içinde karşılaştırma yaparak çıkan sonuçlar: aynı kalıbı farklı makinelerde, değişim vardiyasını normal vardiyayla kıyaslıyoruz. Her bulgunun yanında kanıt gücü ve dikkat edilecek noktalar yazıyor."
      state={ctx.status?.loaded ? st : { data: null, loading: false, error: { status: 409, message: "Henüz veri yüklenmedi." } }} onNeedData={() => ctx.go("data")}>
      {(d) => !d.bulgular?.length ? <Hint kind="warn">{d.uyari}</Hint> : (
        <>
          <Kpis items={d.kpis} />
          {d.bulgular.map((b, i) => (
            <Panel key={b.id} title={`${i + 1}. ${b.baslik}`} sub={null}>
              <div className="cx-badge" style={{ color: TONE[b.guc], borderColor: TONE[b.guc] }}>Kanıt gücü: {b.guc}</div>
              <p className="cx-lead"><Rich text={b.ozet} /></p>
              {b.bars && <BarsChart data={b.bars} fmt={(v) => `${Math.round(v)} sa`} nameWidth={190} />}
              {b.tablo && <DataTable table={b.tablo} filename={`cikarim_${b.id}`} pageSize={12} search={false} />}
              <div className="cx-grid">
                <Block label="Nasıl buldum" text={b.kanit} />
                <Block label="Ne yapılabilir" text={b.yapilir} />
                <Block label="Dikkat" text={b.dikkat} />
              </div>
            </Panel>
          ))}
        </>
      )}
    </Page>
  );
}
