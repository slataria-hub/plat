import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Property } from '../types'
import { MONTHS } from '../types'

export default function Analytics() {
  const [properties, setProperties] = useState<Property[]>([])
  const [pid, setPid] = useState<number | null>(null)
  const [year, setYear] = useState(new Date().getFullYear())
  const [month, setMonth] = useState(new Date().getMonth() + 1)
  const [spending, setSpending] = useState<any>(null)
  const [reconcile, setReconcile] = useState<any>(null)
  const [dual, setDual] = useState<any>(null)
  const [tariffs, setTariffs] = useState<any[]>([])
  const [expected, setExpected] = useState<any>(null)

  useEffect(() => {
    api.listProperties().then((p) => {
      setProperties(p)
      if (p.length) setPid(p[0].id)
    })
  }, [])

  useEffect(() => {
    if (!pid) return
    api.spending(pid, year).then(setSpending).catch(() => setSpending(null))
    api.reconcile(pid, year, month).then(setReconcile).catch(() => setReconcile(null))
    api.dualTariff(pid, year).then(setDual).catch(() => setDual(null))
    api.tariffHistory(pid).then((r: any) => setTariffs(r.items || [])).catch(() => setTariffs([]))
    api.expectedPayment(pid, 6).then(setExpected).catch(() => setExpected(null))
  }, [pid, year, month])

  return (
    <div>
      <h1 className="page-title">Аналитика</h1>
      <div className="btn-row">
        {properties.length > 0 && (
          <select className="select-pill" value={pid ?? ''} onChange={(e) => setPid(Number(e.target.value))}>
            {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        <select className="select-pill" value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {[2026, 2025, 2024, 2023].map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select className="select-pill" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
          {MONTHS.map((m, i) => i > 0 && <option key={i} value={i}>{m}</option>)}
        </select>
      </div>

      {expected && (
        <div className="card highlight-card mt">
          <div className="stat-label">Ожидаемый платёж</div>
          <div className="stat-value">{Number(expected.expected || 0).toLocaleString('ru-RU')} ₽</div>
          <div className="muted small">{expected.message}</div>
        </div>
      )}

      <h2 className="section-title">Сверка с квитанцией ({MONTHS[month]} {year})</h2>
      {reconcile?.items?.length ? (
        reconcile.items.map((r: any) => (
          <div key={r.resource} className={`card property-card ${r.ok ? '' : 'card-warn'}`}>
            <div className="card-title">{r.label} {r.ok ? '✓' : '⚠'}</div>
            <div className="muted">
              Счётчики: {r.meter_consumption} {r.unit} · Квитанция: {r.bill_volume} {r.unit}
              · Δ {r.delta} ({r.message})
            </div>
          </div>
        ))
      ) : (
        <p className="muted">Нет данных для сверки за период (нужны показания и строки квитанции с объёмами).</p>
      )}

      <h2 className="section-title">Двухтарифный vs однотарифный ({year})</h2>
      {dual ? (
        <div className="card">
          <p>{dual.message}</p>
          <div className="muted small">
            День {dual.total_day_kwh} кВт·ч · Ночь {dual.total_night_kwh} кВт·ч ·
            Двухтариф {Number(dual.dual_total).toLocaleString('ru-RU')} ₽ ·
            Однотариф {Number(dual.single_total).toLocaleString('ru-RU')} ₽
          </div>
        </div>
      ) : (
        <p className="muted">Нет данных по электричеству.</p>
      )}

      <h2 className="section-title">История тарифов</h2>
      {tariffs.length === 0 && <p className="muted">Тарифы ещё не заведены.</p>}
      {tariffs.slice(0, 20).map((t, i) => (
        <div key={i} className="item-row">
          <span>{t.service_name} · {t.start_date}</span>
          <span>
            {t.price_t1}
            {t.delta != null && (
              <span className={t.delta > 0 ? 'text-warn' : 'text-ok'}>
                {' '}({t.delta > 0 ? '+' : ''}{t.delta}{t.pct != null ? `, ${t.pct}%` : ''})
              </span>
            )}
          </span>
        </div>
      ))}

      <h2 className="section-title">Траты по месяцам</h2>
      {spending?.months ? (
        spending.months.map((m: any) => (
          <div key={m.month} className="item-row">
            <span>{MONTHS[m.month] || m.month}</span>
            <span>{Number(m.total || m.amount || 0).toLocaleString('ru-RU')} ₽</span>
          </div>
        ))
      ) : (
        <p className="muted">Нет данных о тратах.</p>
      )}
    </div>
  )
}
