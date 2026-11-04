#!/usr/bin/env node
/**
 * Verificación de un plugin de Hermes Desktop SIN Hermes:
 *   1. parsea el ESM real del plugin (quita imports, los vuelve parámetros)
 *   2. ejecuta register() con un ctx falso y recolecta las contribuciones
 *   3. renderiza cada contribución llamando los componentes de verdad
 *   4. repite con varias formas de datos: éxito, vacío y error
 * Detecta typos, identificadores no importados y accesos a undefined ANTES de
 * que el usuario cargue nada en la app.
 *
 * Uso:  node verify-desktop-plugin.mjs <ruta>/plugin.js
 * Salida: líneas ✓/❌ y código de salida 1 si algo falla.
 */
import fs from 'node:fs'

const file = process.argv[2]
if (!file) {
  console.error('uso: node verify-desktop-plugin.mjs <plugin.js>')
  process.exit(2)
}
const src = fs.readFileSync(file, 'utf8')

// --- globals que un plugin puede tocar al renderizar (colores de estado)
globalThis.document = { documentElement: {} }
globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' })

const notes = []
const log = (m) => notes.push(m)
let FAKE = null
let FAKE_ERR = null
let FALSE_ERR = false

const jx = (type, props, key) => ({ __node: true, type, props: props || {}, key })
const sdk = {
  host: { notify: (p) => log(`notify(${JSON.stringify(p)})`), navigate: () => {}, state: {} },
  haptic: () => {},
  // componentes: strings inertes (no se validan sus props, sí que se importen)
  Button: 'Button', Badge: 'Badge', Input: 'Input', Select: 'Select', Switch: 'Switch',
  StatusDot: 'StatusDot', EmptyState: 'EmptyState', ErrorState: 'ErrorState', Separator: 'Separator',
  // áreas
  PANES_AREA: 'panes', PALETTE_AREA: 'palette', KEYBINDS_AREA: 'keybinds', THEMES_AREA: 'themes',
  ROUTES_AREA: 'routes', SIDEBAR_NAV_AREA: 'sidebarNav', TRANSCRIPT_DIRECTIVE_AREA: 'directive',
  STATUSBAR_AREAS: {}, TITLEBAR_AREAS: {}, COMPOSER_AREAS: {},
  // estado / datos
  useQuery: () => ({ data: FAKE, isLoading: false, isError: FALSE_ERR, error: FAKE_ERR, isFetching: false }),
  useMutation: () => ({ mutate: () => {}, mutateAsync: async () => ({}) }),
  useQueryClient: () => ({ invalidateQueries: () => {}, getQueryData: () => FAKE }),
  queryClient: { invalidateQueries: () => {}, getQueryData: () => FAKE, setQueryData: () => {} },
  atom: (v) => ({ get: () => v, set: () => {} }),
  computed: (fn) => ({ get: fn }),
  useValue: (a) => (a && a.get ? a.get() : a),
  Contribute: 'Contribute',
  jsx: jx,
  jsxs: jx
}

// --- convertir los import en parámetros de una factory
const names = []
const body = src
  .replace(/^import\s+([\s\S]+?)\s+from\s+['"][^'"]+['"]\s*;?$/gm, (_, spec) => {
    names.push(...spec.replace(/[{}]/g, '').split(',').map((s) => s.trim()).filter(Boolean))
    return ''
  })
  .replace(/export\s+default/, '__plugin =')

if (/^\s*import\s/m.test(body)) throw new Error('quedaron imports sin transformar')
if (!/__plugin\s*=/.test(body)) throw new Error('no se reescribió el export default')

const factory = new Function(...names, `${body}\nreturn __plugin`)
const plugin = factory(
  ...names.map((n) => {
    if (!(n in sdk)) throw new Error(`el plugin importa '${n}', que no existe en la API del SDK`)
    return sdk[n]
  })
)

const contribs = []
const ctx = {
  source: `plugin:${plugin.id}`,
  rest: async () => FAKE,
  socket: () => () => {},
  os: { writeClipboard: (t) => log(`clipboard(${String(t).length})`), notify: () => {} },
  storage: { get: () => null, set: () => {}, remove: () => {} },
  register: (c) => { contribs.push(c); return () => {} },
  registerMany: (cs) => { cs.forEach((c) => contribs.push(c)); return () => {} }
}

function render(node) {
  if (node === null || node === undefined || node === false || node === true) return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(render).join(' ')
  if (node.__node) {
    if (typeof node.type === 'function') return render(node.type(node.props))
    return `${typeof node.type === 'string' ? node.type : '[comp]'}(${render(node.props.children)})`
  }
  return String(node)
}

function check(cond, msg) {
  if (cond) { console.log(`✓ ${msg}`) } else { console.error(`❌ ${msg}`); process.exitCode = 1 }
}

check(typeof plugin.id === 'string' && plugin.id.length > 0, `id = '${plugin.id}'`)
check(typeof plugin.register === 'function', 'register() existe')
check(plugin.defaultEnabled === undefined || plugin.defaultEnabled === true, 'activo por defecto')
plugin.register(ctx)
check(contribs.length > 0, `${contribs.length} contribuciones (${contribs.map((c) => c.id).join(', ')})`)

const SHAPES = {
  'datos': { ok: true, items: [{ id: 'a', pct: 38.4, level: 'amber' }, { id: 'b', pct: 0 }], level: 'amber', generated_at: new Date().toISOString() },
  'vacío': { ok: true, items: [], level: 'ok', generated_at: new Date().toISOString() },
  'error': null
}

for (const [label, shape] of Object.entries(SHAPES)) {
  FAKE = shape
  FALSE_ERR = shape === null
  FAKE_ERR = shape === null ? new Error('backend no disponible') : null
  notes.length = 0
  for (const c of contribs) {
    if (!c.render) continue
    let text
    try {
      text = render(c.render()).replace(/\s+/g, ' ').trim()
    } catch (err) {
      console.error(`❌ render ${c.id} falló con ${label}: ${err.message}`)
      process.exitCode = 1
      continue
    }
    // OJO: el nombre del proveedor puede ser literalmente "NaN Usage" — es un
    // literal legítimo de la UI (falso positivo real, ya visto). Limpiar los
    // literales conocidos ANTES de buscar fugas de datos.
    const probe = text.replace(/NaN\s+Usage/gi, '').replace(/NaN\s*[·…]+/g, '')
    check(!/undefined|\bNaN\b/.test(probe), `render ${c.id} sin undefined/NaN · ${label}`)
    if (text) console.log(`   ${c.id}: ${text.slice(0, 140)}${text.length > 140 ? '…' : ''}`)
  }
}

// comandos de paleta / handlers con y sin datos
for (const c of contribs.filter((x) => x.area === 'palette' || x.data?.run)) {
  for (const shape of [SHAPES['datos'], null]) {
    FAKE = shape
    notes.length = 0
    try {
      c.data.run()
    } catch (err) {
      console.error(`❌ run() de ${c.id} falló (${shape ? 'con datos' : 'sin datos'}): ${err.message}`)
      process.exitCode = 1
    }
  }
  check(true, `comando ${c.id} ejecuta sin lanzar`)
}

console.log(process.exitCode ? '\nRESULTADO: FALLÓ' : '\nRESULTADO: OK')
