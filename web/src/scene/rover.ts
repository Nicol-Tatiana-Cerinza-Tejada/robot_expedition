import * as THREE from 'three'
import type { ReplayFrame } from '../types'

const material = (color: THREE.ColorRepresentation, extra: THREE.MeshStandardMaterialParameters = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.72, ...extra })

const box = (width: number, height: number, depth: number, meshMaterial: THREE.MeshStandardMaterial) => {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), meshMaterial)
  mesh.castShadow = true
  mesh.receiveShadow = true
  return mesh
}

const quaternionFromFrame = (frame: ReplayFrame) =>
  new THREE.Quaternion(frame[4], frame[6], -frame[5], frame[3])

export class RoverModel {
  readonly group = new THREE.Group()
  readonly hitFlash: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>
  private wheels: Array<THREE.Mesh<THREE.CylinderGeometry, THREE.MeshStandardMaterial>> = []
  private wheelAngle = 0

  constructor(scene: THREE.Scene) {
    const bodyMaterial = material(0xeee8dc, { roughness: 0.48 })
    const darkMaterial = material(0x202529, { roughness: 0.62 })
    const goldMaterial = material(0xd7a342, { roughness: 0.38, metalness: 0.34 })

    const chassis = box(0.52, 0.1, 0.34, bodyMaterial)
    chassis.position.y = 0.11
    this.group.add(chassis)
    const solarPanel = box(0.43, 0.018, 0.51, material(0x193f5a, { roughness: 0.3, metalness: 0.5 }))
    solarPanel.position.y = 0.177
    this.group.add(solarPanel)
    const mast = box(0.045, 0.2, 0.045, darkMaterial)
    mast.position.set(0.14, 0.27, 0)
    this.group.add(mast)
    const camera = box(0.11, 0.075, 0.15, goldMaterial)
    camera.position.set(0.16, 0.34, 0)
    this.group.add(camera)
    const visor = box(0.024, 0.044, 0.105, material(0x61d5d2, { emissive: 0x61d5d2, emissiveIntensity: 1.1 }))
    visor.position.set(0.22, 0.34, 0)
    this.group.add(visor)

    this.wheels = [-1, 1].map((side) => {
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.07, 24), material(0x111315))
      wheel.rotation.x = Math.PI / 2
      wheel.position.set(0, 0.1, side * 0.22)
      wheel.castShadow = true
      const hub = box(0.12, 0.02, 0.076, goldMaterial)
      wheel.add(hub)
      this.group.add(wheel)
      return wheel
    })

    for (const x of [0.2, -0.2]) {
      const caster = new THREE.Mesh(new THREE.SphereGeometry(0.05, 12, 8), darkMaterial)
      caster.position.set(x, 0.08, 0)
      caster.castShadow = true
      this.group.add(caster)
    }

    this.hitFlash = new THREE.Mesh(
      new THREE.RingGeometry(0.31, 0.47, 32),
      new THREE.MeshBasicMaterial({ color: 0xff7164, transparent: true, opacity: 0, side: THREE.DoubleSide }),
    )
    this.hitFlash.rotation.x = -Math.PI / 2
    this.hitFlash.position.y = 0.025
    this.group.add(this.hitFlash)
    this.group.visible = false
    scene.add(this.group)
  }

  applyInterpolated(
    current: ReplayFrame,
    next: ReplayFrame,
    mix: number,
    position: (x: number, y: number, elevation?: number) => THREE.Vector3,
  ) {
    const x = THREE.MathUtils.lerp(current[0], next[0], mix)
    const y = THREE.MathUtils.lerp(current[1], next[1], mix)
    const elevation = THREE.MathUtils.lerp(current[2], next[2], mix)
    const previousPosition = this.group.position.clone()
    this.group.position.copy(position(x, y, elevation))
    this.group.quaternion.copy(quaternionFromFrame(current)).slerp(quaternionFromFrame(next), mix)

    const forward = new THREE.Vector3(1, 0, 0).applyQuaternion(this.group.quaternion)
    this.wheelAngle -= this.group.position.clone().sub(previousPosition).dot(forward) / 0.1
    this.wheels.forEach((wheel) => { wheel.rotation.y = this.wheelAngle })
    this.group.visible = true
  }

  flashCollision() {
    this.hitFlash.material.opacity = 1
  }

  tick() {
    this.hitFlash.material.opacity *= 0.9
  }

  forward() {
    return new THREE.Vector3(1, 0, 0).applyQuaternion(this.group.quaternion)
  }

  sensorPosition(sensorHeight: number) {
    return this.group.localToWorld(new THREE.Vector3(0.16, sensorHeight, 0))
  }

  setShadows(enabled: boolean) {
    this.group.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.castShadow = enabled
        object.receiveShadow = true
      }
    })
  }
}
