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

## Agente Q-learning y CLI

`qlearning_agent.py` discretiza variables físicas relevantes (posición, altura,
velocidad, postura, obstáculo cercano, batería y progreso) y aprende sobre ocho
acciones motoras discretas. Durante el entrenamiento imprime la recompensa,
progreso, éxitos, estados conocidos y `epsilon`, para observar cómo cambia la
exploración.

```bash
source .venv/bin/activate
python qlearning_agent.py train --episodes 100 --max-steps 500
python qlearning_agent.py plot
python qlearning_agent.py evaluate --episodes 10
```

Los artefactos quedan en `models/qlearning_robot.npz`,
`logs/qlearning_history.csv` y `logs/qlearning_learning.png`. Para ver el robot
durante la evaluación usa `--render`.

## Simulación 3D con Three.js

La página `visualize_3d.html` muestra el bípedo, Marte, obstáculos, meta y las
métricas del entrenamiento real. Genera el historial y sirve el repositorio:

```bash
source .venv/bin/activate
python qlearning_agent.py train --episodes 100 --max-steps 500
python -m http.server 8000
```

Abre `http://localhost:8000/visualize_3d.html`. La página usa Three.js desde
CDN y carga `logs/qlearning_history.csv` para reproducir las pruebas y el
aprendizaje.

Para observar el entrenamiento en vivo, abre `http://localhost:8000/training_dashboard.html`
en una terminal y ejecuta el agente en otra:

```bash
python -m http.server 8000
source .venv/bin/activate
python qlearning_agent.py train --episodes 100 --report-every 1
```

La interfaz lee `logs/qlearning_live.json` después de cada época.
