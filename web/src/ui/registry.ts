import type { CatalogRun, LevelMetrics, MonitorData, RichCatalog } from '../types'

type Child = Node | string | null | undefined | false
type Attrs = Record<string, string | boolean | undefined>

const LEVELS = ['n1', 'n2', 'n3'] as const
type Level = (typeof LEVELS)[number]
const COLORS = ['#61d5d2', '#f27d42', '#7fd692', '#e6c36a', '#ff7164', '#b69cff']
const STATUS_LABEL: Record<string, string> = {
  completed: 'completado',
  failed: 'fallido',
  interrupted: 'interrumpido',
  rejected: 'rechazado',
  baseline: 'referencia',
}
const CAUSES = ['grieta', 'volco', 'bateria', 'tiempo']

/** Crea un elemento; el texto siempre entra como texto, nunca como HTML. */
function h(tag: string, attrs: Attrs = {}, ...children: Child[]): HTMLElement {
  const element = document.createElement(tag)
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === false) continue
    element.setAttribute(key, value === true ? '' : value)
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue
    element.append(child instanceof Node ? child : document.createTextNode(child))
  }
  return element
}

const pct = (value?: number | null) => (value === undefined || value === null ? '—' : `${Math.round(value * 100)} %`)
const num = (value?: number | null, digits = 1) =>
  value === undefined || value === null ? '—' : value.toLocaleString('es-CO', { maximumFractionDigits: digits })
const short = (id?: string | null) => (id ? id.slice(0, 8) : '—')
const duration = (seconds?: number | null) => {
  if (!seconds && seconds !== 0) return '—'
  const minutes = Math.floor(seconds / 60)
  return minutes ? `${minutes} min ${Math.round(seconds % 60)} s` : `${Math.round(seconds)} s`
}
const failures = (m?: LevelMetrics) => {
  if (!m) return '—'
  const parts = CAUSES.filter((cause) => m.failures_by_cause[cause]).map((cause) => `${cause} ${m.failures_by_cause[cause]}`)
  return parts.length ? parts.join(' · ') : 'ninguno'
}
const family = (version: string) => version.split('/')[0]

export interface RegistryCallbacks {
  onEvaluate: (run: CatalogRun, levelId: string) => void
  onRefreshMonitor: () => void
}

export class RegistryView {
  private catalog: RichCatalog = { recommended_run_id: {}, runs: [] }
  private compare = new Set<string>()
  private detailId?: string
  private levelFilter = required<HTMLSelectElement>('#registryLevel')
  private statusFilter = required<HTMLSelectElement>('#registryStatus')
  private compareLevel = required<HTMLSelectElement>('#compareLevel')
  private tableBody = required<HTMLElement>('#registryRows')
  private detail = required<HTMLElement>('#runDetail')
  private compareBox = required<HTMLElement>('#compareView')
  private monitorBox = required<HTMLElement>('#monitorView')

  private callbacks: RegistryCallbacks

  constructor(callbacks: RegistryCallbacks) {
    this.callbacks = callbacks
    this.levelFilter.addEventListener('change', () => this.renderTable())
    this.statusFilter.addEventListener('change', () => this.renderTable())
    this.compareLevel.addEventListener('change', () => this.renderCompare())
    required<HTMLButtonElement>('#refreshMonitor').addEventListener('click', () => callbacks.onRefreshMonitor())
    required<HTMLButtonElement>('#clearCompare').addEventListener('click', () => {
      this.compare.clear()
      this.syncUrl()
      this.renderTable()
      this.renderCompare()
    })
    window.addEventListener('popstate', () => this.readUrl())
  }

  get runs() {
    return this.catalog.runs
  }

  run(runId: string) {
    return this.catalog.runs.find((run) => run.run_id === runId)
  }

  recommendedFor(levelId: string) {
    return this.catalog.recommended_run_id?.[levelId] ?? undefined
  }

  setCatalog(value: unknown) {
    const record = (typeof value === 'object' && value !== null ? value : {}) as Partial<RichCatalog>
    this.catalog = {
      ...record,
      recommended_run_id: record.recommended_run_id && typeof record.recommended_run_id === 'object' ? record.recommended_run_id : {},
      runs: Array.isArray(record.runs)
        ? record.runs.map((run) => ({ ...run, metrics_by_level: run.metrics_by_level ?? {} }))
        : [],
    }
    required<HTMLElement>('#catalogMeta').textContent = this.catalog.served_version
      ? `${this.catalog.served_version} · publicado ${this.catalog.published_at?.replace('T', ' ').slice(0, 16) ?? ''} UTC por ${this.catalog.published_by ?? '—'}`
      : this.catalog.source ?? 'catálogo sin versión publicada'
    this.readUrl()
    this.renderTable()
    this.renderCompare()
  }

  /** Enlaces profundos: /run/<run_id> abre el detalle; ?compare=a,b preselecciona la comparación. */
  readUrl() {
    const match = window.location.pathname.match(/^\/run\/([\w-]+)/)
    const params = new URLSearchParams(window.location.search)
    const compare = params.get('compare')
    if (compare) {
      this.compare = new Set(compare.split(',').filter((id) => this.run(id)))
    }
    if (match && this.run(match[1])) {
      this.showDetail(match[1], false)
      document.querySelector('#catalogo')?.scrollIntoView({ behavior: 'smooth' })
    }
    this.renderCompare()
  }

  private syncUrl(runId = this.detailId) {
    const path = runId ? `/run/${runId}` : '/'
    const query = this.compare.size ? `?compare=${[...this.compare].join(',')}` : ''
    window.history.pushState({}, '', `${path}${query}${window.location.hash}`)
  }

  private visibleRuns() {
    const level = this.levelFilter.value
    const status = this.statusFilter.value
    return this.catalog.runs.filter((run) =>
      (level === 'todos' || run.level_id === level || run.level_id === 'todos') &&
      (status === 'todos' || run.status === status))
  }

  private metricLevel(run: CatalogRun): Level {
    const filter = this.levelFilter.value
    if ((LEVELS as readonly string[]).includes(filter)) return filter as Level
    return (LEVELS as readonly string[]).includes(run.level_id) ? (run.level_id as Level) : 'n2'
  }

  renderTable() {
    const runs = this.visibleRuns()
    required<HTMLElement>('#registryCount').textContent = `${runs.length} de ${this.catalog.runs.length} runs`
    const recommended = new Set(Object.values(this.catalog.recommended_run_id ?? {}).filter(Boolean))
    const rows = runs.map((run) => {
      const level = this.metricLevel(run)
      const metrics = run.metrics_by_level[level]
      const checkbox = h('input', {
        type: 'checkbox', 'aria-label': `Comparar ${run.run_id}`,
        checked: this.compare.has(run.run_id), disabled: !Object.keys(run.metrics_by_level).length,
      }) as HTMLInputElement
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) this.compare.add(run.run_id)
        else this.compare.delete(run.run_id)
        this.syncUrl()
        this.renderCompare()
      })
      const evaluate = h('button', { type: 'button', class: 'table-button', disabled: !this.canServe(run) }, 'Cargar y evaluar')
      evaluate.addEventListener('click', () => this.callbacks.onEvaluate(run, level))
      const open = h('a', { href: `/run/${run.run_id}`, class: 'run-link' }, short(run.run_id))
      open.addEventListener('click', (event) => {
        event.preventDefault()
        this.showDetail(run.run_id)
      })
      return h('tr', { class: run.run_id === this.detailId ? 'selected' : undefined },
        h('td', {}, checkbox),
        h('td', {}, open, recommended.has(run.run_id) ? h('span', { class: 'tag tag-gold', title: 'Recomendado' }, '★') : null),
        h('td', {}, run.experiment_id),
        h('td', {}, run.algorithm.toUpperCase()),
        h('td', {}, run.level_id.toUpperCase()),
        h('td', {}, run.seed === undefined || run.seed === null ? '—' : String(run.seed)),
        h('td', { class: 'num' }, metrics ? pct(metrics.success_rate) : '—'),
        h('td', {}, h('span', { class: `status status-${run.status}` }, STATUS_LABEL[run.status] ?? run.status)),
        h('td', {}, evaluate),
      )
    })
    this.tableBody.replaceChildren(...(rows.length ? rows : [h('tr', {}, h('td', { colspan: '9', class: 'empty' }, 'Sin runs con este filtro.'))]))
    required<HTMLElement>('#successHeader').textContent = (LEVELS as readonly string[]).includes(this.levelFilter.value)
      ? `Éxito ${this.levelFilter.value.toUpperCase()}`
      : 'Éxito (su nivel)'
  }

  canServe(run: CatalogRun) {
    return (run.status === 'completed' || run.status === 'baseline') && family(run.environment_version) === 'robot-expedition-3d'
  }

  showDetail(runId: string, push = true) {
    const run = this.run(runId)
    if (!run) return
    this.detailId = runId
    if (push) this.syncUrl(runId)
    const decisions = Object.entries(this.catalog.decisions ?? {}).flatMap(([level, items]) =>
      items.filter((item) => item.run_id === runId).map((item) => `${level.toUpperCase()}: ${item.decision} — ${item.reason}`))
    const field = (label: string, value: Child) => h('div', {}, h('dt', {}, label), h('dd', {}, value ?? '—'))
    const commit = run.commit_url
      ? h('a', { href: run.commit_url, target: '_blank', rel: 'noopener' }, short(run.git_commit))
      : short(run.git_commit)
    const levelCards = LEVELS.map((level) => {
      const m = run.metrics_by_level[level]
      const button = h('button', { type: 'button', class: 'table-button', disabled: !this.canServe(run) }, `Evaluar en ${level.toUpperCase()}`)
      button.addEventListener('click', () => this.callbacks.onEvaluate(run, level))
      return h('article', { class: 'level-card' },
        h('header', {}, h('strong', {}, level.toUpperCase()), h('span', {}, m ? pct(m.success_rate) : 'sin evaluar')),
        m ? h('p', {}, `fallos: ${failures(m)}`) : null,
        m ? h('p', {}, `pasos ${num(m.steps_mean)} · choques/ep ${num(m.collisions_per_episode, 2)} · latencia ${num(m.latency_ms_mean, 2)} ms`) : null,
        button)
    })
    this.detail.replaceChildren(...nodes(
      h('div', { class: 'section-heading' },
        h('div', {}, h('span', { class: 'eyebrow' }, 'Detalle del run'), h('h3', {}, run.model_name)),
        h('span', { class: `status status-${run.status}` }, STATUS_LABEL[run.status] ?? run.status)),
      run.hypothesis ? h('p', { class: 'hypothesis' }, `Hipótesis: ${run.hypothesis}`) : null,
      h('dl', { class: 'detail-grid' },
        field('run_id', h('code', {}, run.run_id)),
        field('Cambio frente a la referencia', run.change ? `${run.change}${run.reference ? ` (ref. ${run.reference})` : ''}` : '—'),
        field('Entrenado en', run.level_id.toUpperCase()),
        field('Semilla', run.seed === null || run.seed === undefined ? '—' : String(run.seed)),
        field('Pasos', run.effective_budget_timesteps ? `${num(run.effective_budget_timesteps, 0)} (presupuesto ${num(run.budget_timesteps, 0)})` : '—'),
        field('Tiempo de entrenamiento', duration(run.training_time_s)),
        field('Padre (continúa de)', run.parent_run_id ? short(run.parent_run_id) : '—'),
        field('Commit', commit),
        field('MLflow', run.mlflow_url
          ? h('a', { href: run.mlflow_url, target: '_blank', rel: 'noopener' }, `run ${short(run.mlflow_run_id)} · ${run.mlflow_run_name ?? ''}`)
          : run.mlflow_run_id ? `run ${short(run.mlflow_run_id)} · ${run.mlflow_run_name ?? ''} (local)` : '—'),
        field('Ambiente', run.environment_version),
        field('SHA-256 del modelo', run.model_sha256 ? h('code', {}, short(run.model_sha256)) : '—'),
        field('Configuración', run.config_path ?? '—'),
      ),
      run.diagnosis ? h('p', { class: 'diagnosis' }, `Diagnóstico: ${run.diagnosis}`) : null,
      decisions.length ? h('ul', { class: 'decisions' }, ...decisions.map((text) => h('li', {}, text))) : null,
      h('div', { class: 'level-cards' }, ...levelCards),
    ))
    this.detail.hidden = false
    this.renderTable()
  }

  renderCompare() {
    const level = this.compareLevel.value as Level
    const selected = [...this.compare].map((id) => this.run(id)).filter((run): run is CatalogRun => Boolean(run))
    required<HTMLElement>('#compareCount').textContent = `${selected.length} seleccionados`
    if (selected.length < 2) {
      this.compareBox.replaceChildren(h('p', { class: 'section-copy' },
        'Marca dos o más runs en el catálogo para compararlos con la misma suite fija.'))
      return
    }
    const families = new Set(selected.map((run) => family(run.environment_version)))
    const warning = families.size > 1
      ? h('p', { class: 'diagnosis' }, 'Hay runs de ambientes incompatibles: no se comparan entre sí.')
      : null
    const rows: Array<[string, (m?: LevelMetrics, run?: CatalogRun) => string]> = [
      ['Éxito', (m) => pct(m?.success_rate)],
      ['Fallos por causa', (m) => failures(m)],
      ['Balizas (media)', (m) => num(m?.beacons_visited_mean, 2)],
      ['Pasos (media)', (m) => num(m?.steps_mean)],
      ['Batería final (éxitos)', (m) => (m?.final_battery_success === undefined || m?.final_battery_success === null ? '—' : `${num(m.final_battery_success)} %`)],
      ['Choques por episodio', (m) => num(m?.collisions_per_episode, 2)],
      ['Latencia media / p95 (ms)', (m) => (m ? `${num(m.latency_ms_mean, 2)} / ${num(m.latency_ms_p95, 2)}` : '—')],
      ['Entrenado en · semilla', (_m, run) => `${run?.level_id.toUpperCase()} · ${run?.seed ?? '—'}`],
      ['Tiempo de entrenamiento', (_m, run) => duration(run?.training_time_s)],
    ]
    const table = h('table', { class: 'compare-table' },
      h('thead', {}, h('tr', {}, h('th', {}, `Suite ${level.toUpperCase()}`),
        ...selected.map((run, i) => h('th', {}, h('i', { class: 'swatch', style: `background:${COLORS[i % COLORS.length]}` }), run.model_name)))),
      h('tbody', {}, ...rows.map(([label, fn]) =>
        h('tr', {}, h('th', {}, label), ...selected.map((run) => h('td', {}, fn(run.metrics_by_level[level], run)))))))
    this.compareBox.replaceChildren(
      warning ?? '',
      h('div', { class: 'table-scroll' }, table),
      h('div', { class: 'curves' },
        this.curveChart('Éxito en entrenamiento (exploración incluida)', selected, 'training_success_rate', [0, 1]),
        this.curveChart('Recompensa por episodio en entrenamiento', selected, 'training_reward')),
      h('p', { class: 'section-copy' },
        'Las curvas son de entrenamiento (MLflow, training/*). La tabla es la evaluación determinista con la suite fija: no se mezclan.'),
    )
  }

  private curveChart(title: string, runs: CatalogRun[], key: 'training_success_rate' | 'training_reward', range?: [number, number]) {
    const series = runs.map((run) => run.curves?.[key] ?? [])
    const points = series.flat()
    const width = 420
    const height = 160
    const pad = 28
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`)
    svg.setAttribute('class', 'curve-chart')
    svg.setAttribute('role', 'img')
    svg.setAttribute('aria-label', title)
    if (!points.length) {
      return h('figure', {}, h('figcaption', {}, title), h('p', { class: 'section-copy' }, 'Sin curvas registradas en el catálogo.'))
    }
    const maxX = Math.max(...points.map((p) => p[0]))
    const minY = range ? range[0] : Math.min(...points.map((p) => p[1]))
    const maxY = range ? range[1] : Math.max(...points.map((p) => p[1]))
    const x = (v: number) => pad + (v / (maxX || 1)) * (width - pad - 8)
    const y = (v: number) => height - pad - ((v - minY) / ((maxY - minY) || 1)) * (height - pad - 10)
    const axis = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    axis.setAttribute('d', `M${pad} 8 V${height - pad} H${width - 8}`)
    axis.setAttribute('class', 'axis')
    svg.append(axis)
    for (const [label, value] of [[num(maxY, 2), maxY], [num(minY, 2), minY]] as Array<[string, number]>) {
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('x', String(pad - 4))
      text.setAttribute('y', String(y(value) + 3))
      text.setAttribute('text-anchor', 'end')
      text.textContent = label
      svg.append(text)
    }
    const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    xLabel.setAttribute('x', String(width - 8))
    xLabel.setAttribute('y', String(height - 8))
    xLabel.setAttribute('text-anchor', 'end')
    xLabel.textContent = `${num(maxX / 1000, 0)}k pasos`
    svg.append(xLabel)
    series.forEach((line, i) => {
      if (!line.length) return
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      path.setAttribute('d', line.map((p, j) => `${j ? 'L' : 'M'}${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join(' '))
      path.setAttribute('stroke', COLORS[i % COLORS.length])
      path.setAttribute('class', 'series')
      svg.append(path)
    })
    return h('figure', {}, h('figcaption', {}, title), svg)
  }

  renderMonitor(monitor: MonitorData | undefined, version: Record<string, unknown> | undefined, error?: string) {
    const served = typeof version?.served_version === 'string' ? version.served_version : undefined
    const apiRecommended = (version?.recommended_run_id ?? {}) as Record<string, string | null>
    const levelCards = LEVELS.map((level) => {
      const runId = this.catalog.recommended_run_id?.[level] ?? undefined
      const run = runId ? this.run(runId) : undefined
      const m = run?.metrics_by_level[level]
      const pin = this.catalog.pins?.[level]
      const mismatch = apiRecommended[level] !== undefined && apiRecommended[level] !== runId
      return h('article', { class: 'level-card' },
        h('header', {}, h('strong', {}, `${level.toUpperCase()} · recomendado`), h('span', {}, m ? pct(m.success_rate) : '—')),
        h('p', {}, run ? run.model_name : 'sin modelo recomendado'),
        run ? h('p', {}, `run ${short(run.run_id)} · fallos: ${failures(m)}`) : null,
        pin ? h('p', { class: 'diagnosis' }, `Fijado por rollback (antes ${short(pin.from_run_id)}): ${pin.reason}`) : null,
        mismatch ? h('p', { class: 'diagnosis' }, `La API sirve ${short(apiRecommended[level])}: versión desalineada.`) : null)
    })
    const routes = Object.entries(monitor?.routes ?? {}).sort((a, b) => b[1].requests - a[1].requests)
    const routeTable = h('table', { class: 'compare-table' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Ruta'), h('th', {}, 'Solicitudes'), h('th', {}, 'Errores'), h('th', {}, 'Latencia media'), h('th', {}, 'p95'))),
      h('tbody', {}, ...routes.map(([route, r]) => h('tr', {},
        h('th', {}, route), h('td', {}, String(r.requests)),
        h('td', { class: r.errors ? 'bad' : undefined }, String(r.errors)),
        h('td', {}, `${num(r.latency_ms_mean, 1)} ms`), h('td', {}, `${num(r.latency_ms_p95, 1)} ms`)))))
    const errors = monitor?.last_errors?.length
      ? h('ul', { class: 'decisions' }, ...monitor.last_errors.slice(-6).reverse().map((e) =>
        h('li', {}, `${e.at.replace('T', ' ')} · ${e.route} · ${e.status}${e.detail ? ` · ${e.detail}` : ''}`)))
      : h('p', { class: 'section-copy' }, 'Sin errores registrados desde el último arranque de la API.')
    this.monitorBox.replaceChildren(
      error ? h('p', { class: 'diagnosis' }, `Monitoreo no disponible: ${error}`) : '',
      h('dl', { class: 'detail-grid' },
        h('div', {}, h('dt', {}, 'Versión servida (API)'), h('dd', {}, served ?? '—')),
        h('div', {}, h('dt', {}, 'Catálogo cargado'), h('dd', {}, this.catalog.served_version ?? '—')),
        h('div', {}, h('dt', {}, 'Commit de la API'), h('dd', {}, short(typeof version?.git_commit === 'string' ? version.git_commit : undefined))),
        h('div', {}, h('dt', {}, 'Release'), h('dd', {}, typeof version?.release === 'string' ? version.release : '—')),
        h('div', {}, h('dt', {}, 'Sesiones activas'), h('dd', {}, String(monitor?.sessions ?? '—'))),
        h('div', {}, h('dt', {}, 'Tiempo en línea'), h('dd', {}, duration(monitor?.uptime_s))),
      ),
      h('div', { class: 'level-cards' }, ...levelCards),
      h('div', { class: 'table-scroll' }, routeTable),
      h('h4', {}, 'Últimos errores de la API'),
      errors,
    )
  }
}

function nodes(...children: Child[]): Array<Node | string> {
  return children.filter((child): child is Node | string => child !== null && child !== undefined && child !== false)
}

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector)
  if (!element) throw new Error(`Falta el elemento ${selector}.`)
  return element
}
