import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { MONTHS } from '../types'
import type { Bill } from '../types'

export default function BillDetail() {
  const { id } = useParams()
  const [bill, setBill] = useState<Bill | null>(null)
  const [error, setError] = useState('')
  const [recognizing, setRecognizing] = useState(false)
  const [ocrMsg, setOcrMsg] = useState('')
  const [payAmount, setPayAmount] = useState('')
  const [payDate, setPayDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [paying, setPaying] = useState(false)

  const load = () => {
    if (!id) return
    api.getBill(Number(id)).then(setBill).catch((e) => setError(e.message))
  }
  useEffect(() => { load() }, [id])

  const runOcr = async () => {
    if (!bill) return
    setRecognizing(true)
    setOcrMsg('')
    try {
      const token = localStorage.getItem('token')
      const r = await fetch(`/api/v1/bills/${bill.id}/recognize?apply=true`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await r.json()
      setOcrMsg(data.message || data.status)
      load()
    } catch {
      setOcrMsg('Ошибка распознавания')
    } finally {
      setRecognizing(false)
    }
  }

  const addPay = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!bill) return
    setPaying(true)
    try {
      await api.addPayment(bill.id, {
        amount: Number(payAmount),
        payment_date: payDate,
        method: 'manual',
      })
      setPayAmount('')
      load()
    } catch (err: any) {
      alert(err.message || 'Ошибка')
    } finally {
      setPaying(false)
    }
  }

  if (error) return <div className="error-box">{error}</div>
  if (!bill) return <p className="muted">Загрузка…</p>

  return (
    <div>
      <Link to="/bills" className="back-link">← Квитанции</Link>
      <div className="section-header">
        <h1>{bill.provider}</h1>
        <span className={`status-badge status-${bill.status}`}>{bill.status}</span>
      </div>
      <p className="muted">{MONTHS[bill.period_month]} {bill.period_year}</p>

      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-label">Начислено</div>
          <div className="stat-value">{bill.total_accrued.toLocaleString('ru-RU')} ₽</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Оплачено</div>
          <div className="stat-value">{bill.total_paid.toLocaleString('ru-RU')} ₽</div>
        </div>
      </div>

      <h2 className="section-title">Услуги</h2>
      <div className="item-list">
        {bill.items.map((it: any) => (
          <div key={it.id} className="item-row">
            <span>{it.service_type?.name || it.raw_name || '—'}</span>
            <span className="item-amount">{Number(it.amount).toLocaleString('ru-RU')} ₽</span>
          </div>
        ))}
        {bill.items.length === 0 && <p className="muted">Нет строк — загрузите файл и нажмите «Распознать»</p>}
      </div>

      <h2 className="section-title">Оплаты</h2>
      {bill.payments.map((p) => (
        <div key={p.id} className="item-row">
          <span>{p.payment_date}{p.method ? ` · ${p.method}` : ''}</span>
          <span>{Number(p.amount).toLocaleString('ru-RU')} ₽</span>
        </div>
      ))}
      {bill.payments.length === 0 && <p className="muted">Оплат пока нет</p>}

      <form className="card form-card mt" onSubmit={addPay}>
        <div className="section-title" style={{ marginTop: 0 }}>Внести оплату</div>
        <label>Сумма, ₽
          <input type="number" step="0.01" min="0" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} required />
        </label>
        <label>Дата
          <input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} required />
        </label>
        <button type="submit" className="btn primary" disabled={paying}>
          {paying ? 'Сохранение…' : 'Сохранить оплату'}
        </button>
      </form>

      {bill.file_path && (
        <div className="mt">
          <button className="btn primary" disabled={recognizing} onClick={runOcr}>
            {recognizing ? 'Распознавание…' : 'Распознать файл (OCR)'}
          </button>
          {ocrMsg && <p className="muted mt">{ocrMsg}</p>}
          <a className="btn secondary mt" href={`/uploads/${bill.file_path}`} target="_blank" rel="noreferrer" style={{ display: 'inline-flex' }}>
            Открыть файл ({bill.file_type})
          </a>
        </div>
      )}
    </div>
  )
}
