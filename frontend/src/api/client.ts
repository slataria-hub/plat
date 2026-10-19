import { API_ORIGIN } from './config'
const API = `${API_ORIGIN}/api/v1`

function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem('token', token)
  else localStorage.removeItem('token')
}

function formatError(err: unknown, fallback: string): string {
  if (typeof err === 'string') return err
  if (Array.isArray(err)) {
    return err.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
  }
  if (err && typeof err === 'object' && 'msg' in (err as any)) {
    return String((err as any).msg)
  }
  return fallback
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API}${path}`, { ...options, headers })
  if (res.status === 401) {
    setToken(null)
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(formatError(body.detail, 'Ошибка запроса'))
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  register: (email: string, password: string, name?: string) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, name }) }),
  login: async (email: string, password: string) => {
    const form = new URLSearchParams()
    form.set('username', email)
    form.set('password', password)
    const data = await request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    })
    setToken(data.access_token)
    return data
  },
  me: () => request<import('../types').User>('/auth/me'),

  listProperties: () => request<import('../types').Property[]>('/properties'),
  createProperty: (data: { name: string; address?: string; account_number?: string }) =>
    request<import('../types').Property>('/properties', { method: 'POST', body: JSON.stringify(data) }),

  listMeters: (propertyId: number) =>
    request<import('../types').Meter[]>(`/properties/${propertyId}/meters`),
  createMeter: (propertyId: number, data: object) =>
    request(`/properties/${propertyId}/meters`, { method: 'POST', body: JSON.stringify(data) }),
  listReadings: (meterId: number, year?: number) =>
    request<import('../types').MeterReading[]>(
      `/meters/${meterId}/readings${year ? `?year=${year}` : ''}`
    ),
  createReading: (meterId: number, data: object) =>
    request(`/meters/${meterId}/readings`, { method: 'POST', body: JSON.stringify(data) }),

  listBills: (propertyId: number, params?: Record<string, string | number>) => {
    const q = params ? '?' + new URLSearchParams(params as any).toString() : ''
    return request<import('../types').BillListItem[]>(`/properties/${propertyId}/bills${q}`)
  },
  getBill: (id: number) => request<import('../types').Bill>(`/bills/${id}`),
  createBill: (propertyId: number, data: object) =>
    request(`/properties/${propertyId}/bills`, { method: 'POST', body: JSON.stringify(data) }),

  listTariffs: (propertyId: number) => request(`/properties/${propertyId}/tariffs`),
  tariffChanges: (propertyId: number, from: string, to: string) =>
    request(`/properties/${propertyId}/tariffs/changes?from_date=${from}&to_date=${to}`),
  compareBills: (propertyId: number, prevY: number, prevM: number, currY: number, currM: number) =>
    request(`/properties/${propertyId}/bills/compare?prev_year=${prevY}&prev_month=${prevM}&curr_year=${currY}&curr_month=${currM}`),

  consumption: (propertyId: number, year?: number) =>
    request(`/properties/${propertyId}/analytics/consumption${year ? `?year=${year}` : ''}`),
  spending: (propertyId: number, year?: number) =>
    request(`/properties/${propertyId}/analytics/spending${year ? `?year=${year}` : ''}`),
  summary: (propertyId: number, year: number) =>
    request(`/properties/${propertyId}/analytics/summary?year=${year}`),
  exportExcelUrl: (propertyId: number) => `/api/v1/properties/${propertyId}/export/excel`,
  recognizeBill: (billId: number) => request(`/bills/${billId}/recognize`, { method: 'POST' }),
  backupZipUrl: () => `${API_ORIGIN}/api/v1/backup/zip`,
  importExcel: async (propertyId: number, file: File) => {
    const token = localStorage.getItem('token')
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${API_ORIGIN}/api/v1/properties/${propertyId}/import/excel`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || 'Ошибка импорта')
    return data
  },
  addPayment: (billId: number, data: { amount: number; payment_date: string; method?: string }) =>
    request(`/bills/${billId}/payments`, { method: 'POST', body: JSON.stringify(data) }),
  notifications: (propertyId?: number) =>
    request(`/notifications${propertyId ? `?property_id=${propertyId}` : ''}`),

  // Features 1-12
  getSettings: (propertyId: number) => request(`/properties/${propertyId}/settings`),
  patchSettings: (propertyId: number, data: object) =>
    request(`/properties/${propertyId}/settings`, { method: 'PATCH', body: JSON.stringify(data) }),
  reminders: (propertyId: number) => request(`/properties/${propertyId}/reminders`),
  reconcile: (propertyId: number, year: number, month: number) =>
    request(`/properties/${propertyId}/reconcile?year=${year}&month=${month}`),
  expectedPayment: (propertyId: number, months = 6) =>
    request(`/properties/${propertyId}/expected-payment?months=${months}`),
  tariffHistory: (propertyId: number) => request(`/properties/${propertyId}/tariff-history`),
  listNotes: (propertyId: number, year?: number) =>
    request<any[]>(`/properties/${propertyId}/notes${year ? `?year=${year}` : ''}`),
  saveNote: (propertyId: number, data: { year: number; month: number; text: string }) =>
    request(`/properties/${propertyId}/notes`, { method: 'POST', body: JSON.stringify(data) }),
  exportPdfUrl: (propertyId: number, year?: number, month?: number) => {
    let u = `${API_ORIGIN}/api/v1/properties/${propertyId}/export/pdf`
    const q: string[] = []
    if (year) q.push(`year=${year}`)
    if (month) q.push(`month=${month}`)
    return q.length ? u + '?' + q.join('&') : u
  },
  dualTariff: (propertyId: number, year: number) =>
    request(`/properties/${propertyId}/dual-tariff-compare?year=${year}`),
  listAccounts: (propertyId: number) => request<any[]>(`/properties/${propertyId}/accounts`),
  createAccount: (propertyId: number, data: object) =>
    request(`/properties/${propertyId}/accounts`, { method: 'POST', body: JSON.stringify(data) }),
  deleteAccount: (propertyId: number, id: number) =>
    request(`/properties/${propertyId}/accounts/${id}`, { method: 'DELETE' }),
  portals: (propertyId: number) => request(`/properties/${propertyId}/portals`),
  listShares: (propertyId: number) => request<any[]>(`/properties/${propertyId}/shares`),
  createShare: (propertyId: number, guest_email: string) =>
    request(`/properties/${propertyId}/shares`, { method: 'POST', body: JSON.stringify({ guest_email }) }),
  acceptShare: (token: string) => request(`/shares/accept/${token}`, { method: 'POST' }),
  sharedWithMe: () => request<any[]>('/shared-with-me'),
  widget: (propertyId?: number) =>
    request(`/widget${propertyId ? `?property_id=${propertyId}` : ''}`),
  quickReadings: (propertyId: number, data: { reading_date: string; items: { meter_id: number; value_t1: number; value_t2?: number }[] }) =>
    request(`/properties/${propertyId}/readings/quick`, { method: 'POST', body: JSON.stringify(data) }),
}
