# Robot Expedition

Un rover en Marte debe **visitar la baliza 1, luego la baliza 2 y volver a la
base antes de agotar la batería**. Todo es 3D: la física la calcula MuJoCo
(gravedad de Marte, dunas, una grieta en la que se puede caer, rocas y ruedas
con motor) y la vista es Three.js. La ficha de diseño está en
[`docs/ambiente-v0.1.md`](docs/ambiente-v0.1.md) y el mapa en
[`docs/mapa-ambiente-v0.1.svg`](docs/mapa-ambiente-v0.1.svg).

El repositorio tiene dos ambientes Gymnasium, los dos en MuJoCo 3D:

| Ambiente | Clase | Agente |
|---|---|---|
| Expedición con rover: misión completa en terreno 3D | `BeaconExpeditionEnv` | Q-learning tabular (`python -m robot_expedition`) |
| Bípedo (10 motores) | `RobotExpeditionEnv` | `qlearning_agent.py` (no logra caminar) o PPO (`train.py`) |

## Instalación

El entorno reproducible usa Python **3.12**. Se recomienda crear un entorno
virtual nuevo; no se deben subir `.venv`, secretos ni artefactos de MLflow.

### Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

Comprobar las piezas críticas:

```bash
python -c "import torch, stable_baselines3; print(torch.__version__, stable_baselines3.__version__)"
python -m pytest -q
```

Los YAML reproducibles de N1, N2 y N3 están en `configs/levels/`. La interfaz
común es observación de 20 valores y `Discrete(5)`; los contratos completos
están en [`docs/contratos.md`](docs/contratos.md).

## Web Vite + Three.js

La aplicación del docente está en `web/`. Presenta el terreno, el rover, los
nueve rayos, el rastro y las métricas del episodio. Consume el catálogo y las
evaluaciones de la API; si la API no responde muestra un error visible y no
reemplaza los resultados con datos de ejemplo. Los archivos locales se cargan
manualmente y quedan identificados como `REPLAY`. El botón **Ver demo REPLAY**
carga y reproduce la evidencia real de `docs/demo/expedition_replays.json`; no
la presenta como una evaluación en vivo.

Versiones verificadas para este frontend:

- Node.js **26.13.0 LTS** (`web/.nvmrc`; Vercel usa la línea `26.x`).
- npm **11.20.0**.
- Vite **8.3.5**.
- Three.js y `@types/three` **0.187.0**.

```bash
cd web
cp .env.example .env.local
# Reemplazar VITE_API_BASE_URL por la API HTTPS real
npm ci
npm run dev
npm run build
```

El control manual usa las flechas y los endpoints `POST /sim/reset` y
`POST /sim/step`. El modo ligero desactiva sombras y reduce la densidad de
píxeles para equipos con menos capacidad gráfica.

Despliegue en Vercel:

- Root Directory: `web`
- Build Command: `npm run build`
- Output Directory: `dist`
- Variable: `VITE_API_BASE_URL` con la URL HTTPS del backend

URL de la web: <https://web-five-gules-83.vercel.app>

La URL ya publica el frontend. La variable `VITE_API_BASE_URL` se añadirá en
Vercel cuando el equipo entregue la URL HTTPS de la API; hasta entonces la web
muestra explícitamente que la API no está configurada.

## CLI: entrenar, evaluar y ver el proceso

Todos los comandos se ejecutan desde la raíz del repositorio:

```bash
python -m robot_expedition train          # 2000 episodios, ~4 min; muestra el avance en la terminal
python -m robot_expedition evaluate       # las 3 métricas de la ficha en 50 episodios nuevos
python -m robot_expedition evaluate --perturbation   # con el corredor bloqueado
python -m robot_expedition demo --viewer  # un episodio en el visor 3D nativo de MuJoCo
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
Cada cuadro guarda la pose 3D completa de MuJoCo: posición x, y, z y
orientación como cuaternión. Así se ve al rover subir, inclinarse en las dunas
o caer en la grieta. La página muestra también el mismo terreno (heightfield),
los 9 rayos, el rastro coloreado por etapa, las balizas que se ponen verdes al
visitarlas, los choques, el bloqueo y la curva de aprendizaje. El botón «Recorrer todo el aprendizaje» pasa por
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

## Bípedo (MuJoCo)

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
ambiente del rover de arriba.
