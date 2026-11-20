import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { auth, useLocalVersion } from './localBackend'
import { classifyGuideline } from './specialties'
import type { Guideline } from './types'

export function useCurrentUser() {
  useLocalVersion()
  return auth.currentUser()
}

type AsyncState<T> = { data: T | null; error: Error | null; loading: boolean }

export function useAsync<T>(load: () => Promise<T>, key: string) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setState((previous) => ({ ...previous, loading: true, error: null }))
    load().then(
      (data) => active && setState({ data, error: null, loading: false }),
      (error: Error) => active && setState({ data: null, error, loading: false }),
    )
    return () => {
      active = false
    }
    // `key` identifica a consulta; `load` muda a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt])

  const reload = useCallback(() => setAttempt((value) => value + 1), [])
  return { ...state, reload }
}

export type CatalogEntry = Guideline & { specialties: string[] }

// O catálogo é carregado uma vez e compartilhado entre telas.
let catalogPromise: Promise<CatalogEntry[]> | null = null

export function loadCatalog(force = false) {
  if (!catalogPromise || force) {
    catalogPromise = api
      .guidelines()
      .then((items) => items.map((item) => ({ ...item, specialties: classifyGuideline(item.title) })))
    catalogPromise.catch(() => {
      catalogPromise = null
    })
  }
  return catalogPromise
}

export function useCatalog() {
  const [refresh, setRefresh] = useState(0)
  const state = useAsync(() => loadCatalog(refresh > 0), `catalog:${refresh}`)
  return { ...state, reload: () => setRefresh((value) => value + 1) }
}
