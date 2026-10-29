# Robot Expedition

Un robot explorador en Marte debe **visitar la baliza 1, luego la baliza 2 y
volver a la base antes de agotar la batería**. La ficha de diseño está en
[`docs/ambiente-v0.1.md`](docs/ambiente-v0.1.md) y el mapa en
[`docs/mapa-ambiente-v0.1.svg`](docs/mapa-ambiente-v0.1.svg).

El repositorio tiene dos ambientes Gymnasium:

| Ambiente | Clase | Agente |
|---|---|---|
| Navegación con la misión completa (avance y giro) | `BeaconExpeditionEnv` | Q-learning tabular (`python -m robot_expedition`) |
| Bípedo físico en MuJoCo (10 motores) | `RobotExpeditionEnv` | `qlearning_agent.py` (no logra caminar) o PPO (`train.py`) |

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install gymnasium mujoco numpy matplotlib pytest
```

## CLI: entrenar, evaluar y ver el proceso

Todos los comandos se ejecutan desde la raíz del repositorio:

```bash
python -m robot_expedition train          # 2000 episodios, ~40 s; muestra el avance en la terminal
python -m robot_expedition evaluate       # las 3 métricas de la ficha en 50 episodios nuevos
python -m robot_expedition evaluate --perturbation   # con el corredor bloqueado
python -m robot_expedition demo           # un episodio animado en la terminal (mapa ASCII)
python -m robot_expedition transitions    # transiciones reales en tabla Markdown
python -m robot_expedition plot           # logs/expedition_learning.png
python -m robot_expedition serve          # vista 3D en http://localhost:8000/expedicion_3d.html
```

Use `python -m robot_expedition <comando> --help` para ver las opciones
(`--episodes`, `--seed`, `--ray-noise`, `--jitter`, `--max-steps`, ...).

Lo que genera cada comando:
- `models/qlearning_balizas.npz`: la tabla Q.
- `logs/expedition_history.csv`: una fila por episodio.
- `logs/expedition_replays.json`: trayectorias grabadas para la vista 3D.
- `logs/expedition_live.json`: el último episodio, para el modo en vivo.

### Vista 3D (Three.js)

`expedicion_3d.html` reproduce las **trayectorias reales** que graba el CLI.
Muestra el mapa de la ficha, el robot, los 9 rayos, el rastro coloreado por
etapa, las balizas que se ponen verdes al visitarlas, los choques, el bloqueo
y la curva de aprendizaje. El botón «Recorrer todo el aprendizaje» pasa por
los episodios grabados, desde el robot que explora al azar hasta el que
cumple la misión.

```bash
python -m robot_expedition serve      # terminal 1
# abrir http://localhost:8000/expedicion_3d.html
```

Para verlo **en vivo** mientras entrena, active «En vivo» en la página y en
otra terminal ejecute:

```bash
python -m robot_expedition train --live-delay 0.5
```

Si todavía no hay `logs/`, la página usa los datos de ejemplo de `docs/demo/`.

### Pruebas

```bash
python -m pytest -q
```

Las pruebas verifican las reglas de la ficha: el orden de las balizas, que
cada bono se dé una sola vez, los choques, la grieta, la batería, el límite de
tiempo, la perturbación y que no se gane girando en el sitio.

## Bípedo físico (MuJoCo)

### Ejecutar una prueba

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

### Agente Q-learning del bípedo

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

### Páginas del bípedo (Three.js y paneles)

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

Nota (28 oct): con 300 episodios este agente no logra que el bípedo camine (0
éxitos, cae antes de 80 pasos). Por eso la misión completa se entrena en el
ambiente de navegación de arriba.
