export interface User {
  id: number
  email: string
  name: string | null
  created_at: string
}

export interface Property {
  id: number
  name: string
  address: string | null
  account_number: string | null
  is_active: boolean
  created_at: string
}

export interface Meter {
  id: number
  property_id: number
  type: 'cold_water' | 'hot_water' | 'electricity'
  name: string
  serial_number: string | null
  tariff_type: 'single' | 'day_night'
  unit: string
  is_active: boolean
  last_reading?: {
    reading_date: string
    value_t1: number
    value_t2: number | null
    consumption_t1: number | null
    consumption_t2: number | null
  } | null
}

export interface MeterReading {
  id: number
  meter_id: number
  reading_date: string
  value_t1: number
  value_t2: number | null
  consumption_t1: number | null
  consumption_t2: number | null
  source: string
  notes: string | null
}

export interface BillItem {
  id: number
  service_code: string | null
  service_name: string
  volume: number | null
  tariff: number | null
  amount: number
  sort_order: number
}

export interface BillListItem {
  id: number
  property_id: number
  provider: string
  period_year: number
  period_month: number
  total_accrued: number
  total_paid: number
  status: string
  items_count: number
  created_at: string
}

export interface Bill {
  id: number
  property_id: number
  provider: string
  period_year: number
  period_month: number
  total_accrued: number
  total_paid: number
  status: string
  file_path: string | null
  file_type: string | null
  notes: string | null
  created_at: string
  items: BillItem[]
  payments: { id: number; amount: number; payment_date: string; method: string | null }[]
}

export const METER_TYPE_LABELS: Record<string, string> = {
  cold_water: 'Холодная вода',
  hot_water: 'Горячая вода',
  electricity: 'Электричество',
}

export const METER_TYPE_COLORS: Record<string, string> = {
  cold_water: '#0EA5E9',
  hot_water: '#F97316',
  electricity: '#EAB308',
}

export const MONTHS = [
  '', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
]
