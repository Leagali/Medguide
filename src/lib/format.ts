const dateFormatter = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' })
const dateTimeFormatter = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
})
const relativeFormatter = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' })

export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  // Datas sem horário (2023-12-15) são locais, não UTC.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date)
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateTimeFormatter.format(date)
}

export function formatRelative(value: string | null | undefined) {
  if (!value) return '—'
  const seconds = (new Date(value).getTime() - Date.now()) / 1000
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ]
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relativeFormatter.format(Math.round(seconds / size), unit)
  }
  return 'agora'
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatInterval(seconds: number) {
  const days = seconds / 86400
  if (days >= 1 && Number.isInteger(days)) return days === 1 ? '1 dia' : `${days} dias`
  const hours = seconds / 3600
  if (hours >= 1) return `${Number(hours.toFixed(1))} h`
  return `${Math.round(seconds / 60)} min`
}

export function shortHash(hash: string | null | undefined) {
  return hash ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : '—'
}

export function normalize(text: string) {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Como normalize(), mas preserva o comprimento para mapear posições. */
export function foldSameLength(text: string) {
  return text
    .split('')
    .map((char) => {
      const folded = char.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
      return folded.length === 1 ? folded : char
    })
    .join('')
}

export function plural(count: number, singular: string, pluralForm: string) {
  return `${count.toLocaleString('pt-BR')} ${count === 1 ? singular : pluralForm}`
}
