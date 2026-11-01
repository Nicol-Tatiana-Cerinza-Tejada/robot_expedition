import type { EpisodeData, HistoryPoint } from '../types'

export class LearningCurve {
  private canvas: HTMLCanvasElement
  private history: HistoryPoint[] = []
  private episode?: EpisodeData

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    new ResizeObserver(() => this.draw()).observe(canvas)
  }

  setData(history: HistoryPoint[], episode?: EpisodeData) {
    this.history = history
    this.episode = episode
    this.draw()
  }

  private draw() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2)
    const width = Math.max(1, this.canvas.clientWidth)
    const height = Math.max(1, this.canvas.clientHeight)
    this.canvas.width = Math.round(width * ratio)
    this.canvas.height = Math.round(height * ratio)
    const context = this.canvas.getContext('2d')
    if (!context) return
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
    context.clearRect(0, 0, width, height)

    const points = this.history.length ? this.history : this.pointsFromEpisode()
    if (!points.length) {
      context.fillStyle = '#756b63'
      context.font = '10px DM Mono, monospace'
      context.fillText('SIN EVIDENCIA DISPONIBLE', 13, 23)
      return
    }

    const padding = { left: 31, right: 23, top: 15, bottom: 22 }
    const innerWidth = width - padding.left - padding.right
    const innerHeight = height - padding.top - padding.bottom
    const windowSize = Math.max(1, Math.min(30, Math.floor(points.length / 12)))
    const rolling = (key: 'reward' | 'success') => points.map((_, index) => {
      const sample = points.slice(Math.max(0, index - windowSize + 1), index + 1)
      return sample.reduce((total, point) => total + point[key], 0) / sample.length
    })
    const rewards = rolling('reward')
    const success = rolling('success')
    const rewardMin = Math.min(...rewards, 0)
    const rewardMax = Math.max(...rewards, 1)
    const x = (index: number) => padding.left + (index / Math.max(1, points.length - 1)) * innerWidth
    const rewardY = (value: number) => padding.top + (1 - (value - rewardMin) / Math.max(1, rewardMax - rewardMin)) * innerHeight
    const successY = (value: number) => padding.top + (1 - value) * innerHeight

    context.strokeStyle = 'rgba(255, 239, 222, 0.08)'
    context.lineWidth = 1
    for (let line = 0; line <= 3; line += 1) {
      const y = padding.top + (line * innerHeight) / 3
      context.beginPath()
      context.moveTo(padding.left, y)
      context.lineTo(width - padding.right, y)
      context.stroke()
    }

    const drawLine = (values: number[], projectY: (value: number) => number, color: string, lineWidth = 1.8) => {
      context.beginPath()
      values.forEach((value, index) => {
        const px = x(index)
        const py = projectY(value)
        if (index === 0) context.moveTo(px, py)
        else context.lineTo(px, py)
      })
      context.strokeStyle = color
      context.lineWidth = lineWidth
      context.stroke()
    }
    drawLine(rewards, rewardY, '#f27d42', 2)
    if (this.history.length) drawLine(success, successY, '#7fd692', 1.7)

    context.fillStyle = '#756b63'
    context.font = '9px DM Mono, monospace'
    context.textAlign = 'right'
    context.fillText(rewardMax.toFixed(0), padding.left - 5, padding.top + 3)
    context.fillText(rewardMin.toFixed(0), padding.left - 5, padding.top + innerHeight)
    context.textAlign = 'left'
    context.fillText(this.history.length ? '100%' : 'REWARD', width - padding.right + 4, padding.top + 3)
    context.fillText('0', padding.left, height - 5)
    context.textAlign = 'right'
    context.fillText(String(points.at(-1)?.episode ?? points.length), width - padding.right, height - 5)
  }

  private pointsFromEpisode(): HistoryPoint[] {
    if (!this.episode) return []
    let total = 0
    return this.episode.frames.map((frame, index) => {
      total += frame[10]
      return { episode: index, reward: total, success: 0 }
    })
  }
}
