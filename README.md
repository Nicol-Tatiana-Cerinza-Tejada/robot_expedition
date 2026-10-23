# Robot Expedition

Prototipo de un robot bípedo que explora Marte en 3D con MuJoCo y Gymnasium.

## Ejecutar una prueba

```bash
source .venv/bin/activate
python -c "from robot_expedition import RobotExpeditionEnv; e=RobotExpeditionEnv(); o,i=e.reset(seed=7); print(o.shape, i); print(e.step(e.action_space.sample())[1:])"
```

El agente controla diez motores: cadera (balanceo y avance), rodilla y tobillo
(avance y balanceo) en cada pierna. La observacion combina pose, velocidades,
comandos, IMU, contactos, distancias a obstaculos, bateria y progreso.

El episodio termina por caida, bateria agotada o mision cumplida; tambien se
trunca al alcanzar el limite de pasos. La recompensa favorece avance, postura
vertical y eficiencia energetica, penalizando inclinacion y control excesivo.

Para PPO se requieren dependencias adicionales de PyTorch y Stable-Baselines3.
