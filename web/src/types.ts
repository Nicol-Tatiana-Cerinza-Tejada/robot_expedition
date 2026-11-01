export type ReplayFrame = [
  x: number,
  y: number,
  z: number,
  qw: number,
  qx: number,
  qy: number,
  qz: number,
  stage: number,
  battery: number,
  action: number,
  reward: number,
  collision: number,
  rays: number[],
]

export type RockSpec = [name: string, x: number, y: number, halfX: number, halfY: number, height: number]
export type EpisodeRock = [x: number, y: number, halfX: number, halfY: number, height: number]

export interface TerrainSpec {
  n: number
  heights: number[]
}

export interface ExpeditionMap {
  size: [number, number]
  base: [number, number, number, number]
  beacons: Array<[number, number]>
  visit_radius: number
  crack: [number, number, number, number]
  crack_depth: number
  sand: [number, number, number, number]
  rocks: RockSpec[]
  block: [string, number, number, number, number, number]
  sensor_height: number
  ray_angles: number[]
  actions: string[]
  dt: number
  terrain: TerrainSpec
}

export interface HistoryPoint {
  episode: number
  reward: number
  success: number
  epsilon?: number
}

export interface EpisodeData {
  episode: number | string
  mode: string
  runId: string
  modelName: string
  environmentVersion: string
  levelId: string
  frames: ReplayFrame[]
  rocks?: EpisodeRock[]
  block?: boolean
  success: boolean
  end: string
  reward: number
  steps: number
  visited: number
  battery: number
  pathLength?: number
  latencyMs?: number
  history: HistoryPoint[]
}

export interface RunOption {
  runId: string
  modelName: string
  levelId: string
  environmentVersion: string
  algorithm: string
  status: string
  successRate?: number
}

export interface CatalogData {
  runs: RunOption[]
  recommendedRunId?: string
  servedVersion?: string
}

export interface ReplayBundle {
  map: ExpeditionMap
  episodes: EpisodeData[]
  history: HistoryPoint[]
}

export interface FrameSnapshot {
  frame: ReplayFrame
  index: number
  total: number
  cumulativeReward: number
  collisions: number
  actionName: string
  objective: string
}

export const FRAME_INDEX = {
  stage: 7,
  battery: 8,
  action: 9,
  reward: 10,
  collision: 11,
  rays: 12,
} as const

export const STAGE_NAMES = ['B1', 'B2', 'Base'] as const

export const END_LABELS: Record<string, string> = {
  exito: 'Misión cumplida',
  success: 'Misión cumplida',
  grieta: 'Cayó en la grieta',
  volco: 'Rover volcado',
  bateria: 'Batería agotada',
  tiempo: 'Tiempo agotado',
  collision: 'Colisión',
  running: 'En curso',
}
