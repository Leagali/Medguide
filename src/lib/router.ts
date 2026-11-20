import { useEffect, useState } from 'react'

// Roteamento por hash (#/feed): funciona no Vite e em qualquer hospedagem
// estática sem configuração de servidor.

function currentHash() {
  return window.location.hash.slice(1) || '/'
}

export function useLocation() {
  const [hash, setHash] = useState(currentHash)
  useEffect(() => {
    let lastPath = currentHash().split('?')[0]
    const onChange = () => {
      const next = currentHash()
      setHash(next)
      // Filtros mudam só a query: mantém a rolagem. Nova tela: volta ao topo.
      const nextPath = next.split('?')[0]
      if (nextPath !== lastPath) window.scrollTo(0, 0)
      lastPath = nextPath
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const [path, search = ''] = hash.split('?')
  return { path, query: new URLSearchParams(search) }
}

export function navigate(to: string, options?: { replace?: boolean }) {
  if (options?.replace) {
    window.location.replace(`#${to}`)
  } else {
    window.location.hash = to
  }
}

/** Atualiza a query string sem criar entrada no histórico (filtros). */
export function replaceQuery(path: string, params: Record<string, string | null>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value)
  }
  const search = query.toString()
  navigate(search ? `${path}?${search}` : path, { replace: true })
}

export function matchPath(pattern: string, path: string): Record<string, string> | null {
  const patternParts = pattern.split('/').filter(Boolean)
  const pathParts = path.split('/').filter(Boolean)
  if (patternParts.length !== pathParts.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < patternParts.length; i++) {
    const part = patternParts[i]
    if (part.startsWith(':')) {
      params[part.slice(1)] = decodeURIComponent(pathParts[i])
    } else if (part !== pathParts[i]) {
      return null
    }
  }
  return params
}
