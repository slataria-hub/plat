import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Property } from '../types'

export default function BillCreate() {
  const nav = useNavigate()
  const [properties, setProperties] = useState<Property[]>([])
  const [propertyId, setPropertyId] = useState<number | null>(null)
  const [provider, setProvider] = useState('МосОблЕИРЦ')
  const [year, setYear] = useState(new Date().getFullYear())
  const [month, setMonth] = useState(new Date().getMonth() || 12)
  const [total, setTotal] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [pasteText, setPasteText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ocrInfo, setOcrInfo] = useState('')

  useEffect(() => {
    api.listProperties().then((p) => {
      setProperties(p)
      if (p.length) setPropertyId(p[0].id)
    })
  }, [])

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!propertyId) return
    setError('')
    setLoading(true)
    try {
      // Optional: parse pasted text first
      let items: any[] = []
      let accrued = total ? parseFloat(total) : 0
      let prov = provider
      let y = year
      let m = month

      if (pasteText.trim().length > 20) {
        const parsed: any = await api.recognizeBill // will use parse-text
        // call parse-text via fetch
        const token = localStorage.getItem('token')
        const pr = await fetch('/api/v1/ocr/parse-text', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: pasteText }),
        }).then((r) => r.json())
        if (pr.status === 'done' || pr.status === 'partial') {
          if (pr.provider) prov = pr.provider
          if (pr.period_year) y = pr.period_year
          if (pr.period_month) m = pr.period_month
          if (pr.total_accrued) accrued = pr.total_accrued
          items = (pr.items || []).map((it: any) => ({
            raw_name: it.raw_name,
            amount: it.amount || 0,
            volume: it.volume,
            tariff: it.tariff,
          }))
          setOcrInfo(pr.message || 'Текст разобран')
        }
      }

      const bill: any = await api.createBill(propertyId, {
        property_id: propertyId,
        provider: prov,
        period_year: y,
        period_month: m,
        total_accrued: accrued,
        items: items.length ? items : undefined,
      })

      if (file) {
        const token = localStorage.getItem('token')
        const fd = new FormData()
        fd.append('file', file)
        await fetch(`/api/v1/bills/${bill.id}/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        })
        // auto-recognize from file
        await fetch(`/api/v1/bills/${bill.id}/recognize?apply=true`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
      }

      nav(`/bills/${bill.id}`)
    } catch (err: any) {
      setError(err.message || 'Ошибка')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1>Новая квитанция</h1>
      <form className="card form-card" onSubmit={onSubmit}>
        {properties.length > 1 && (
          <label>Объект
            <select value={propertyId ?? ''} onChange={(e) => setPropertyId(Number(e.target.value))}>
              {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        )}
        <label>Поставщик
          <input value={provider} onChange={(e) => setProvider(e.target.value)} list="providers" />
          <datalist id="providers">
            <option value="МосОблЕИРЦ" />
            <option value="Техкомсервис" />
            <option value="Теплосеть" />
            <option value="Водоканал" />
          </datalist>
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <label>Год
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </label>
          <label>Месяц
            <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>{i + 1}</option>
              ))}
            </select>
          </label>
        </div>
        <label>Сумма начислено
          <input type="number" step="0.01" value={total} onChange={(e) => setTotal(e.target.value)} placeholder="Можно оставить пустым" />
        </label>
        <label>Фото или PDF квитанции
          <input type="file" accept="image/*,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        <label>Или вставьте текст с квитанции
          <textarea
            rows={5}
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder="Скопируйте текст из PDF или письма ЕИРЦ…"
            style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 10, width: '100%', font: 'inherit' }}
          />
        </label>
        {ocrInfo && <div className="muted">{ocrInfo}</div>}
        {error && <div className="error-box">{error}</div>}
        <button type="submit" className="btn primary" disabled={loading || !propertyId}>
          {loading ? 'Сохранение…' : 'Создать'}
        </button>
      </form>
    </div>
  )
}
