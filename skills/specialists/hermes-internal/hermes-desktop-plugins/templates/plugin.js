/**
 * Plantilla de plugin de Hermes Desktop (chip + panel + comandos de paleta).
 * Copiar a <HERMES_HOME>/desktop-plugins/<id>/plugin.js y ajustar.
 * SIN JSX (el archivo se carga sin compilar) y solo 3 imports permitidos.
 */
import { host, haptic, useQuery, queryClient, PALETTE_AREA, Button } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const QUERY_KEY = ['my-plugin', 'data']
let api = null // ctx.rest, ligado en register()

function useData() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => api('/data'),
    refetchInterval: 60_000,   // nunca menos de unos segundos
    staleTime: 30_000,
    retry: 1
  })
}

function Chip() {
  const { data, isError } = useData()
  return jsx('button', {
    type: 'button',
    title: data ? JSON.stringify(data) : 'sin datos',
    className: 'flex items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    onClick: () => {
      haptic('tap')
      void api('/refresh', { method: 'POST', body: {} }).finally(() =>
        queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      )
    },
    children: jsx('span', { children: isError ? 'err' : 'ok' })
  })
}

function Pane() {
  const { data, isLoading, isError, isFetching } = useData()
  return jsxs('div', {
    className: 'flex h-full flex-col gap-2 overflow-auto p-3 text-sm',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('div', { className: 'font-medium text-(--ui-text-secondary)', children: 'My plugin' }),
          jsx(Button, { type: 'button', onClick: () => void queryClient.invalidateQueries({ queryKey: QUERY_KEY }), children: isFetching ? '…' : 'Actualizar' })
        ]
      }),
      isLoading && !data
        ? jsx('div', { className: 'text-xs text-(--ui-text-quaternary)', children: 'cargando…' })
        : isError
          ? jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Sin datos del backend.' })
          : jsx('pre', { className: 'text-xs text-(--ui-text-tertiary)', children: JSON.stringify(data, null, 1) })
    ]
  })
}

export default {
  id: 'my-plugin', // DEBE coincidir con el nombre de la carpeta
  name: 'My Plugin',
  register(ctx) {
    api = ctx.rest
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'My Plugin',
      data: { placement: 'right', width: '300px' },
      render: () => jsx(Pane, {})
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 120,
      render: () => jsx(Chip, {})
    })
    ctx.register({
      id: 'refresh',
      area: PALETTE_AREA,
      data: {
        id: 'my-plugin.refresh',
        label: 'My Plugin: actualizar',
        keywords: ['my', 'plugin'],
        run: () => void queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      }
    })
  }
}
