import { useMemo } from 'react'
import type { CatalogEntry } from '../lib/hooks'
import { SPECIALTIES } from '../lib/specialties'
import { CheckIcon } from './Icons'

export function SpecialtyPicker({
  value,
  onChange,
  catalog,
}: {
  value: string[]
  onChange: (next: string[]) => void
  catalog: CatalogEntry[] | null
}) {
  const counts = useMemo(() => {
    const result: Record<string, number> = {}
    catalog?.forEach((entry) => entry.specialties.forEach((id) => (result[id] = (result[id] ?? 0) + 1)))
    return result
  }, [catalog])

  function toggle(id: string) {
    onChange(value.includes(id) ? value.filter((item) => item !== id) : [...value, id])
  }

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {SPECIALTIES.map((specialty) => {
        const selected = value.includes(specialty.id)
        return (
          <button
            key={specialty.id}
            type="button"
            aria-pressed={selected}
            onClick={() => toggle(specialty.id)}
            className={`specialty-option ${selected ? 'is-selected' : ''}`}
          >
            <span className="check" aria-hidden="true">
              {selected && <CheckIcon size={14} strokeWidth={2.4} />}
            </span>
            <span className="min-w-0 flex-1 text-left">
              <span className="block text-sm font-semibold">{specialty.name}</span>
              <span className="block text-xs text-slate-400">
                {catalog ? `${counts[specialty.id] ?? 0} diretrizes` : '…'}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
