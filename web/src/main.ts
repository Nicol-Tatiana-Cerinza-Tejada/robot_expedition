import './app.css'
import { ApiError, ExpeditionApi, type SimulationResponse } from './api'
import {
  createContractMap,
  normalizeCatalog,
  normalizeEpisode,
  normalizeFrame,
  normalizeMap,
  normalizeReplayBundle,
} from './data'
import { ExpeditionScene } from './scene/expedition-scene'
import type { CatalogData, EpisodeData, ExpeditionMap, ReplayFrame, RunOption } from './types'
import { FRAME_INDEX } from './types'
import { LearningCurve } from './ui/curve'
import { MissionHud, required } from './ui/hud'

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const hud = new MissionHud()
const curve = new LearningCurve(required<HTMLCanvasElement>('#curve'))
const playButton = required<HTMLButtonElement>('#playButton')
const playIcon = required<HTMLElement>('#playIcon')
const timeline = required<HTMLInputElement>('#timeline')
const runSelect = required<HTMLSelectElement>('#runSelect')
const levelSelect = required<HTMLSelectElement>('#levelSelect')
const seedsInput = required<HTMLInputElement>('#seedsInput')
const evaluateButton = required<HTMLButtonElement>('#evaluateButton')
const manualButton = required<HTMLButtonElement>('#manualButton')
const keypadButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-action]'))

const scene = new ExpeditionScene(required<HTMLElement>('#scene'), {
  onFrame: (snapshot) => hud.updateFrame(snapshot),
  onPlaybackChange: (playing) => {
    playIcon.textContent = playing ? 'Ⅱ' : '▶'
    playButton.setAttribute('aria-label', playing ? 'Pausar' : 'Reproducir')
  },
})

let api: ExpeditionApi | undefined
let catalog: CatalogData = { runs: [] }
let currentMap = createContractMap()
let apiEnvironmentVersion = 'sin-versión'
let apiOnline = false
let manualSessionId: string | undefined
let manualEpisode: EpisodeData | undefined
let manualBusy = false

scene.setMap(currentMap)
scene.setSpeed(4)
hud.reset()
setManualControls(false)

const errorMessage = (error: unknown) => {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return 'Ocurrió un error inesperado.'
}

const extractRecord = (value: unknown, key: string): UnknownRecord | undefined => {
  if (!isRecord(value)) return undefined
  return isRecord(value[key]) ? value[key] : undefined
}

const mapFromPayload = (value: unknown): ExpeditionMap | undefined => {
  if (!isRecord(value)) return undefined
  const candidate = value.map ?? extractRecord(value, 'episode')?.map ?? extractRecord(value, 'replay')?.map
  return candidate === undefined ? undefined : normalizeMap(candidate)
}

const frameFromResponse = (response: SimulationResponse): ReplayFrame | undefined => {
  const direct = normalizeFrame(response.frame)
  if (direct) return direct
  if (Array.isArray(response.frames)) return normalizeFrame(response.frames.at(-1))
  const state = isRecord(response.state) ? response.state : undefined
  return normalizeFrame(state?.frame)
}

const environmentVersionFrom = (value: unknown): string | undefined => {
  if (!isRecord(value)) return undefined
  for (const key of ['environment_version', 'served_version', 'version']) {
    if (typeof value[key] === 'string' && value[key]) return value[key]
  }
  return undefined
}

const parseSeeds = () => {
  const seeds = seedsInput.value
    .split(/[;,\s]+/)
    .filter(Boolean)
    .map(Number)
    .filter((value) => Number.isInteger(value))
  if (!seeds.length) throw new Error('Escribe al menos una semilla entera para evaluar.')
  return [...new Set(seeds)]
}

const setBusy = (button: HTMLButtonElement, busy: boolean, idleLabel: string, busyLabel: string) => {
  button.disabled = busy
  button.querySelector('span')?.replaceChildren(document.createTextNode(busy ? busyLabel : idleLabel))
}

const loadEpisode = (
  episode: EpisodeData,
  map: ExpeditionMap,
  source: 'api' | 'replay',
  sourceLabel?: string,
) => {
  currentMap = map
  scene.setMap(map)
  scene.setEpisode(episode)
  hud.setEpisode(episode, source)
  if (sourceLabel) hud.setSource(source, sourceLabel)
  curve.setData(episode.history, episode)
  timeline.max = String(Math.max(0, episode.frames.length - 1))
  timeline.value = '0'
  timeline.disabled = false
  playButton.disabled = false
}

const selectedRun = (): RunOption | undefined => catalog.runs.find((run) => run.runId === runSelect.value)

const fillCatalog = (data: CatalogData) => {
  catalog = data
  runSelect.replaceChildren()
  for (const run of data.runs) {
    const option = document.createElement('option')
    option.value = run.runId
    const metric = run.successRate === undefined ? '' : ` · ${(run.successRate * 100).toFixed(0)}% éxito`
    option.textContent = `${run.runId} · ${run.algorithm.toUpperCase()} · ${run.levelId.toUpperCase()}${metric}`
    runSelect.append(option)
  }
  if (!data.runs.length) {
    const option = document.createElement('option')
    option.value = ''
    option.textContent = 'Catálogo vacío'
    runSelect.append(option)
  }
  if (data.recommendedRunId && data.runs.some((run) => run.runId === data.recommendedRunId)) {
    runSelect.value = data.recommendedRunId
  }
  runSelect.disabled = !data.runs.length
  evaluateButton.disabled = !data.runs.length
  required<HTMLElement>('#catalogCount').textContent = `${data.runs.length} run${data.runs.length === 1 ? '' : 's'}`
  const run = selectedRun()
  if (run) levelSelect.value = run.levelId
}

const connectApi = async () => {
  try {
    api = new ExpeditionApi()
  } catch (error) {
    hud.setConnection('offline', 'Sin configurar')
    hud.showNotice(
      'API no configurada',
      `${errorMessage(error)} Define una API HTTPS o carga un archivo local, que aparecerá claramente como REPLAY.`,
    )
    return
  }

  hud.setConnection('loading', 'Conectando')
  try {
    await api.health()
    const [catalogResult, versionResult] = await Promise.allSettled([api.catalog(), api.version()])
    if (catalogResult.status === 'rejected') throw catalogResult.reason
    const normalizedCatalog = normalizeCatalog(catalogResult.value)
    fillCatalog(normalizedCatalog)
    if (versionResult.status === 'fulfilled') {
      apiEnvironmentVersion = environmentVersionFrom(versionResult.value)
        ?? normalizedCatalog.servedVersion
        ?? apiEnvironmentVersion
    }
    hud.setConnection('online', 'API disponible')
    apiOnline = true
    manualButton.disabled = false
    if (normalizedCatalog.runs.length) hud.hideNotice()
    else hud.showNotice('Catálogo vacío', 'La API responde, pero /catalog todavía no contiene modelos recuperables.')
  } catch (error) {
    apiOnline = false
    hud.setConnection('offline', 'API sin respuesta')
    hud.showNotice('No fue posible conectar con la API', errorMessage(error))
  }
}

const evaluateSelectedRun = async () => {
  if (!api) return
  const run = selectedRun()
  if (!run) {
    hud.showNotice('Selecciona un modelo', 'El catálogo no contiene un run válido para evaluar.')
    return
  }

  setBusy(evaluateButton, true, 'Evaluar modelo', 'Evaluando…')
  try {
    const result = await api.evaluate(run.runId, levelSelect.value, parseSeeds())
    const episode = normalizeEpisode(result, {
      mode: 'evaluación',
      runId: run.runId,
      modelName: run.modelName,
      environmentVersion: run.environmentVersion || apiEnvironmentVersion,
      levelId: levelSelect.value,
    })
    loadEpisode(episode, mapFromPayload(result) ?? currentMap, 'api')
    hud.hideNotice()
  } catch (error) {
    hud.showNotice('La evaluación falló', errorMessage(error))
  } finally {
    setBusy(evaluateButton, false, 'Evaluar modelo', 'Evaluando…')
    evaluateButton.disabled = !catalog.runs.length
  }
}

const startManualMode = async () => {
  if (!api) return
  manualButton.disabled = true
  manualButton.textContent = 'Iniciando…'
  try {
    const response = await api.reset(levelSelect.value)
    const frame = frameFromResponse(response)
    if (!response.session_id) throw new Error('/sim/reset no devolvió session_id.')
    if (!frame) throw new Error('/sim/reset no devolvió un cuadro compatible.')
    manualSessionId = response.session_id
    manualEpisode = normalizeEpisode(
      { ...response, frames: [frame], episode: 'manual', end: 'running' },
      {
        mode: 'manual',
        runId: 'control-manual',
        modelName: 'sin-modelo',
        environmentVersion: environmentVersionFrom(response) ?? apiEnvironmentVersion,
        levelId: levelSelect.value,
      },
    )
    loadEpisode(manualEpisode, response.map ? normalizeMap(response.map) : currentMap, 'api', 'API · MANUAL')
    setManualControls(true)
    hud.hideNotice()
  } catch (error) {
    manualSessionId = undefined
    manualEpisode = undefined
    setManualControls(false)
    hud.showNotice('No se pudo iniciar el control manual', errorMessage(error))
  } finally {
    manualButton.disabled = false
    manualButton.textContent = manualSessionId ? 'Reiniciar' : 'Iniciar'
  }
}

async function sendManualAction(action: number) {
  if (!api || !manualSessionId || !manualEpisode || manualBusy) return
  manualBusy = true
  setManualControls(false)
  try {
    const response = await api.step(manualSessionId, action)
    const frame = frameFromResponse(response)
    if (!frame) throw new Error('/sim/step no devolvió un cuadro compatible.')
    const frames = [...manualEpisode.frames, frame]
    const finished = Boolean(response.terminated || response.truncated)
    manualEpisode = {
      ...manualEpisode,
      frames,
      steps: frames.length - 1,
      battery: frame[FRAME_INDEX.battery],
      reward: frames.reduce((total, item) => total + item[FRAME_INDEX.reward], 0),
      visited: Math.max(manualEpisode.visited, frame[FRAME_INDEX.stage] - 1),
      success: response.end === 'exito' || manualEpisode.success,
      end: typeof response.end === 'string' ? response.end : finished ? 'finished' : 'running',
    }
    loadEpisode(manualEpisode, response.map ? normalizeMap(response.map) : currentMap, 'api', 'API · MANUAL')
    scene.seek(frames.length - 1)
    if (finished) {
      manualSessionId = undefined
      hud.showNotice('Episodio finalizado', `Causa de fin: ${manualEpisode.end}. Pulsa Reiniciar para conducir de nuevo.`)
    }
  } catch (error) {
    hud.showNotice('Falló la orden manual', errorMessage(error))
  } finally {
    manualBusy = false
    setManualControls(Boolean(manualSessionId))
  }
}

function setManualControls(enabled: boolean) {
  keypadButtons.forEach((button) => { button.disabled = !enabled })
}

playButton.addEventListener('click', () => scene.togglePlayback())
timeline.addEventListener('input', () => {
  scene.setPlaying(false)
  scene.seek(Number(timeline.value))
})
required<HTMLSelectElement>('#speedSelect').addEventListener('change', (event) => {
  scene.setSpeed(Number((event.currentTarget as HTMLSelectElement).value))
})

required<HTMLButtonElement>('#followButton').addEventListener('click', (event) => {
  const button = event.currentTarget as HTMLButtonElement
  const active = button.getAttribute('aria-pressed') !== 'true'
  button.setAttribute('aria-pressed', String(active))
  scene.setFollow(active)
})

required<HTMLButtonElement>('#lightModeButton').addEventListener('click', (event) => {
  const button = event.currentTarget as HTMLButtonElement
  const active = button.getAttribute('aria-pressed') !== 'true'
  button.setAttribute('aria-pressed', String(active))
  scene.setLightMode(active)
})

runSelect.addEventListener('change', () => {
  const run = selectedRun()
  if (run) levelSelect.value = run.levelId
})
evaluateButton.addEventListener('click', () => { void evaluateSelectedRun() })
manualButton.addEventListener('click', () => { void startManualMode() })

keypadButtons.forEach((button) => {
  button.addEventListener('click', () => { void sendManualAction(Number(button.dataset.action)) })
})

window.addEventListener('keydown', (event) => {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return
  const actions: Partial<Record<string, number>> = { ArrowUp: 0, ArrowLeft: 3, ArrowRight: 4 }
  const action = actions[event.key]
  if (action === undefined || !manualSessionId) return
  event.preventDefault()
  void sendManualAction(action)
})

required<HTMLInputElement>('#replayInput').addEventListener('change', async (event) => {
  const input = event.currentTarget as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const bundle = normalizeReplayBundle(JSON.parse(await file.text()) as unknown)
    loadEpisode(bundle.episodes[0], bundle.map, 'replay', `REPLAY · ${file.name}`)
    if (apiOnline) hud.hideNotice()
  } catch (error) {
    hud.showNotice('Replay incompatible', errorMessage(error))
  } finally {
    input.value = ''
  }
})

void connectApi()
