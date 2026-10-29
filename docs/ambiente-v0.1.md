# Ambiente v0.1

> Ficha de diseño de **Robot Expedition**. Las secciones siguen la plantilla
> `plantilla-ambiente-v0.1.md`. El ambiente ya está implementado en
> [`robot_expedition/envs/beacon_expedition.py`](../robot_expedition/envs/beacon_expedition.py).
> Los números de las secciones de métricas y transiciones salen de ejecuciones
> reales (`python -m robot_expedition ...`), no de cálculos a mano.

## Mision y mapa

**Misión:** el robot sale de la base, visita **la baliza 1 y después la
baliza 2** (en ese orden) y **regresa a la base antes de agotar la batería**,
sin caer en la grieta y chocando lo menos posible.

![Mapa del ambiente v0.1](mapa-ambiente-v0.1.svg)

(También en PNG: [mapa-ambiente-v0.1.png](mapa-ambiente-v0.1.png).)

| Elemento | Posición / tamaño | Unidad | Comentario |
|---|---|---|---|
| Sala | x ∈ [0, 12], y ∈ [-6, 6] | m | Suelo de Marte, paredes de 0.5 m de alto |
| Base (inicio y fin) | Centro (1.5, 0), cuadrado de 2 × 2 | m | El robot empieza en el centro mirando hacia +x |
| Baliza 1 (B1) | (9.5, 3.5), radio de visita 0.6 | m | Primera meta |
| Baliza 2 (B2) | (9.5, -3.5), radio de visita 0.6 | m | Segunda meta |
| Rocas R1–R5 | Cajas de 0.8–1.2 × 0.8–2.0 × 0.5–1.0 | m | Choque físico. Con `--jitter 0.5` se mueven hasta ±0.5 m |
| Grieta | (3.5, 3.5), 1.0 × 0.4 | m | Pisarla termina el episodio (falla). Los rayos **no** la ven |
| Arena | x ∈ [6, 8], y ∈ [-5.2, -3.8] | m | Suelo suelto: la velocidad se reduce a la mitad |
| Robot | Círculo de radio 0.25 | m | Para calcular los choques |

La ruta de referencia base → B1 → B2 → base mide **25.2 m** de centro a
centro. El robot puede acortarla un poco porque basta con entrar al radio de
cada baliza y al borde de la base.

**Dos niveles de simulación.** El repositorio tiene dos ambientes:

| Ambiente | Archivo | Para qué sirve |
|---|---|---|
| **Navegación** (esta ficha) | `envs/beacon_expedition.py` | La misión completa con avance y giro, como pide la ficha del profesor. Q-learning la aprende |
| **Bípedo físico** (MuJoCo) | `envs/mars_biped.py` | Aprender a caminar con 10 motores. Q-learning tabular no lo logra (ver Decisiones pendientes) |

**Parametría (se fija antes de ejecutar):**

| Parámetro | Valor v0.1 | Rango a explorar | Unidad | Qué cambia | Opción del CLI |
|---|---|---|---|---|---|
| Tamaño del mapa | 12 × 12 | 8 × 8 – 20 × 20 | m × m | Escala del recorrido y batería necesaria | (constante `MAP_W`, `MAP_H`) |
| Ancho de pasillos | ≥ 0.5 libre para el robot | 0.5 – 2.0 | m | Dificultad de navegación | `--jitter` |
| Velocidad máxima | 0.6 | 0.3 – 1.0 | m/s | Capacidad de avance | (constante `V_MAX`) |
| Aceleración máxima | 0.6 | 0.3 – 1.2 | m/s² | Qué tan rápido arranca y frena | (constante `A_MAX`) |
| Ruido de distancia | σ = 0.02 | 0 – 0.10 | m (desv. estándar) | Calidad de los sensores | `--ray-noise` |
| Radio de visita | 0.6 | 0.4 – 1.0 | m | Precisión exigida en las balizas | (constante `VISIT_RADIUS`) |
| Límite de tiempo | 400 | 200 – 800 | pasos (0.5 s c/u) | Margen para equivocarse | `--max-steps` |

## Variables y unidades

**Estado del mundo** (lo que existe en el simulador):

| Variable | Significado | Unidad | Rango | ¿La ve el agente? |
|---|---|---|---|---|
| `x, y` | Posición del robot | m | [0.25, 11.75], [-5.75, 5.75] | **No** (solo la distancia y dirección al objetivo) |
| `θ` | Rumbo del robot | rad | [-π, π] | No (solo el ángulo relativo al objetivo) |
| `v` | Velocidad lineal | m/s | [0, 0.6] | Sí (normalizada) |
| `ω` | Velocidad de giro | rad/s | [-1.2, 1.2] | Sí (normalizada) |
| `B` | Batería | % | [0, 100] | Sí (normalizada a [0, 1]) |
| `etapa` | Objetivo actual: 1 = B1, 2 = B2, 3 = base | — | {1, 2, 3} | Sí (one-hot) |
| `visitadas` | Balizas visitadas (v1, v2) | — | {0, 1}² | Indirectamente (por la etapa) |
| `choques` | Pasos en los que el robot chocó | pasos | [0, 400] | No (solo en `info`) |
| `t` | Paso del episodio | pasos | [0, 400] | No |
| Rocas, balizas, base y grieta | Distribución del mapa | m | ver mapa | **No** (solo a través de los rayos y de la dirección al objetivo) |
| `bloqueo` | Si la perturbación está activa | — | {0, 1} | No (solo la detectan los rayos) |

## Observaciones y acciones

**Observación** (vector `float32` de 18 valores):

| Índice | Bloque | Unidad | Rango |
|---|---|---|---|
| 0–8 | **9 rayos de distancia** de -90° (derecha) a +90° (izquierda), cada 22.5°, con ruido N(0, 0.02) | m | [0, 5] (5 = no hay nada) |
| 9 | Distancia al objetivo actual | m | [0, 17] |
| 10–11 | Dirección al objetivo: sen y cos del ángulo relativo | — | [-1, 1] |
| 12 | Velocidad lineal / 0.6 | — | [0, 1] |
| 13 | Velocidad de giro / 1.2 | — | [-1, 1] |
| 14 | Batería / 100 | — | [0, 1] |
| 15–17 | Etapa (one-hot B1, B2, base) | — | {0, 1} |

Los rayos detectan paredes, rocas y el bloqueo. **No detectan la grieta**,
porque es un hueco en el suelo. El agente tiene que aprender a evitarla por la
experiencia.

**Acción** (`Discrete(5)`): cada acción pide una velocidad y un giro, y el
ambiente limita la aceleración.

| # | Acción | Velocidad pedida (m/s) | Giro pedido (rad/s) |
|---|---|---|---|
| 0 | avanzar | 0.6 | 0 |
| 1 | avanzar + izq | 0.4 | +0.8 |
| 2 | avanzar + der | 0.4 | -0.8 |
| 3 | girar izq | 0 | +1.2 |
| 4 | girar der | 0 | -1.2 |

**Estado discreto del agente Q-learning** (`robot_expedition/qlearning.py`): se
arma **solo con la observación**, sin `x, y`.

| Componente | Cómo se discretiza | Valores |
|---|---|---|
| Etapa | B1, B2, base | 3 |
| Distancia al objetivo | cortes en 1.0, 2.5 y 5.0 m | 4 |
| Ángulo al objetivo | sectores de 45° | 8 |
| Obstáculo a la derecha (rayos 0–2) | cortes en 0.5 y 1.0 m | 3 |
| Obstáculo al frente (rayos 3–5) | cortes en 0.6 y 1.2 m | 3 |
| Obstáculo a la izquierda (rayos 6–8) | cortes en 0.5 y 1.0 m | 3 |

Son 2 592 estados × 5 acciones = 12 960 valores Q. En el entrenamiento el
agente visita unos 1 170 estados.

## Dinamica

Cada paso del agente dura **0.5 s** (2 decisiones por segundo). En cada
`step(a)` ocurre lo siguiente, en este orden:

1. **Acción:** se busca `(v_pedida, ω_pedida)` en la tabla de acciones.
   - La velocidad cambia como máximo `A_MAX · 0.5 s = 0.3 m/s` por paso.
2. **Movimiento:** se integra en 5 subpasos de 0.1 s.
   - En cada subpaso: `θ ← θ + ω·dt`, `x ← x + v·cos θ·dt` y
     `y ← y + v·sin θ·dt`.
   - En la arena, `v` se reduce a la mitad.
3. **Choque:** si la nueva posición toca una pared, una roca o el bloqueo, el
   robot se queda en la última posición válida, `v = 0` y `choque = 1`.
4. **Batería:** `B ← max(0, B − (0.1 + 0.4·E))`, con
   `E = min(1, (v/0.6)² + 0.25·(ω/1.2)²)`.
   - Avanzando a fondo gasta 0.5 %/paso, girando en el sitio 0.2 %/paso y
     quieto 0.1 %/paso.
   - La misión óptima (unos 97 pasos) gasta cerca del 41 %, así que sobra
     batería. Si el robot da vueltas sin rumbo, se queda sin batería antes del
     límite de tiempo.
5. **Progreso:** `d_{t-1} − d_t` hacia el objetivo que estaba activo **al
   inicio** del paso.
6. **Visitas:**
   - Si `etapa = 1` y la distancia a B1 es menor que 0.6 m: `v1 = 1` y la etapa
     pasa a 2.
   - Igual para B2 (la etapa pasa a 3).
   - Entrar al radio de una baliza que **no** es el objetivo actual no hace nada.
   - Con perturbación, al visitar B1 aparece el bloqueo.
7. **Fin:** se revisan éxito, grieta, batería y tiempo (ver más abajo).
8. **Observación nueva:** se lanzan los 9 rayos y se calcula la dirección al
   nuevo objetivo.

**Aleatoriedad en `reset(seed)`:**
- El ruido de los rayos cambia en cada paso.
- Con `--jitter`, las rocas se mueven y se comprueba con una búsqueda en anchura
  (BFS) que sigue habiendo una ruta base → B1 → B2.
- Las balizas y la base son fijas en v0.1.

## Recompensa

Recompensa en cada paso:

```
r_t = 1.0 · (d_{t-1} − d_t)      # progreso hacia el objetivo actual (m)
    − 0.01                        # costo de tiempo
    − 0.02 · E_t                  # consumo
    − 0.5 · choque_t              # choque con roca, pared o bloqueo
    + 10   si visita B1 en la etapa 1          (solo una vez)
    + 10   si visita B2 en la etapa 2          (solo una vez)
    + 50 + 20 · (B / 100)  si llega a la base en la etapa 3 (éxito)
    − 50   si pisa la grieta o agota la batería
```

Por qué se eligió así:
- **El progreso es la diferencia de distancias**, que funciona como un
  potencial. Si el robot va y vuelve, la suma de esos términos se cancela, así
  que oscilar no da puntos.
- **Los bonos solo valen para la baliza del objetivo actual y se dan una vez.**
  Esto responde a la pregunta del reto de la ficha: no se gana visitando la
  misma baliza repetidas veces.
- **Fallar (−50) cuesta más que agotar el tiempo** (400 × 0.01 = 4, más
  como máximo 8 de consumo). Así no le conviene terminar el episodio a propósito.
- **El bono final depende de la batería que quede**, lo que premia rutas
  eficientes.

## Exito, fracaso y limite de tiempo

| Caso | Condición | Gymnasium | `info["end"]` |
|---|---|---|---|
| **Éxito** | `v1 = 1`, `v2 = 1`, el robot dentro del cuadrado de la base y `B > 0` | `terminated = True`, `info["success"] = True` | `exito` |
| **Fracaso: grieta** | El centro del robot dentro de la grieta | `terminated = True` | `grieta` |
| **Fracaso: batería** | `B = 0` | `terminated = True` | `bateria` |
| **Límite de tiempo** | `t = 400` pasos (200 s simulados) | `truncated = True` | `tiempo` |

El límite de 400 pasos es unas 4 veces la ruta óptima (unos 97 pasos). Da
margen para explorar al inicio del entrenamiento sin permitir episodios
infinitos. Como `truncated` es distinto de `terminated`, el agente sigue
estimando el valor futuro cuando se acaba el tiempo.

## Metricas e incidente

Se evalúa con **50 episodios con semillas que no se usan en el
entrenamiento**, con la política greedy (ε = 0). Comando:
`python -m robot_expedition evaluate [--perturbation] [--jitter 0.5]`.

| # | Métrica | Cómo se calcula | Unidad |
|---|---|---|---|
| 1 | **Tasa de éxito** | Episodios exitosos / 50 | % |
| 2 | **Eficiencia de ruta** | 25.2 m / distancia recorrida (solo en éxitos) | > 1 = mejor que la ruta de referencia |
| 3 | **Choques por episodio** | Media de `info["collisions"]` | pasos con choque |

También se registran: las balizas visitadas (0–2), la batería final, los pasos
y la causa del fin.

**Resultados medidos** (Q-learning, 2000 episodios de entrenamiento, semilla 7,
unos 36 s en CPU):

| Escenario | Éxito | Eficiencia | Choques / ep. | Batería final | Pasos | Causa del fin |
|---|---|---|---|---|---|---|
| Normal | **100 %** | 1.02 (24.7 m) | 0.0 | 58.7 % | 96.6 | 50 éxitos |
| Rocas movidas ±0.5 m (`--jitter 0.5`) | **100 %** | — | 0.0 | 58.2 % | 98.5 | 50 éxitos |
| **Corredor bloqueado** (`--perturbation`) | **62 %** | 0.89 (28.2 m) | 74.1 | 41.7 % | 268.3 | 31 éxitos, 19 por tiempo |

En el entrenamiento, la tasa de éxito pasa de 21 % (episodios 1–250, ε alto) a
87 % (251–500) y a 98–99 % desde el episodio 1250.

**Perturbación: corredor bloqueado.**
- **Qué pasa:** al visitar B1 aparece una roca de 2.2 × 0.6 × 0.8 m centrada en
  (9.7, 0), que corta el camino directo B1 → B2. Queda un pasillo junto a la
  pared este y el rodeo por el oeste de R3.
- **Cuándo:** solo en la evaluación. El agente nunca la vio al entrenar.
- **Resultado:** la tasa de éxito baja **38 puntos porcentuales**, más que el
  umbral de 20 que nos fijamos, así que **el agente v0.1 no es robusto** a este
  incidente.
  - En la vista 3D se ve que empuja contra el bloqueo: 74 choques por episodio
    en promedio.
  - Solo a veces el ruido de los rayos lo saca hacia el pasillo.
  - Mejoras posibles: entrenar con el bloqueo en una fracción de los episodios,
    y que el estado distinga "obstáculo justo enfrente" con más detalle.
- **Variante:** subir el ruido de los rayos con `--ray-noise 0.05`.

## Cinco transiciones

Son transiciones reales del agente entrenado. Salen de
`python -m robot_expedition transitions --perturbation` (episodio de evaluación
con el bloqueo activo). La dirección es el ángulo al objetivo relativo al frente
del robot (+ = a la izquierda).

| t | Observación (resumen) | Acción | Nuevo estado | Recompensa | ¿Fin? |
|---|---|---|---|---|---|
| 0 | etapa B1; objetivo a 8.73 m y +24°; rayo frontal 4.99 m; batería 100.0 % | girar izq | (1.50, 0.00); etapa B1; batería 99.8 % | -0.015 | No |
| 35 | etapa B1; objetivo a 0.87 m y +8°; rayo frontal 3.64 m; batería 85.2 % | avanzar | (8.94, 3.61); etapa B2; batería 84.7 %; **visita B1** | +10.266 | No |
| 51 | etapa B2; objetivo a 4.21 m y +4°; rayo frontal 0.40 m; batería 79.1 % | avanzar | (9.31, 0.58); etapa B2; batería 79.0 %; **choque con el bloqueo** | -0.390 | No |
| 196 | etapa B2; objetivo a 0.85 m y +10°; rayo frontal 4.98 m; batería 50.8 % | avanzar | (9.83, -3.06); etapa base; batería 50.3 %; **visita B2** | +10.263 | No |
| 230 | etapa base; objetivo a 1.38 m y -2°; rayo frontal 3.16 m; batería 36.6 % | avanzar | (2.48, -0.64); etapa base; batería 36.1 % | +57.499 | **Sí** (éxito) |

Lectura:
- **t = 0:** girar en el sitio no acerca al robot, así que solo paga tiempo y
  consumo.
- **t = 35:** +0.30 m de progreso + 10 de bono − costos.
- **t = 51:** avanzó un poco (+0.12 m) y chocó (−0.5).
- **t = 196:** tardó 145 pasos en encontrar el rodeo.
- **t = 230:** el bono final es 50 + 20 · 0.361 = 57.2, más el progreso del
  último paso.

## Posibles trampas y decisiones pendientes

**Formas de ganar puntos sin cumplir la misión, y cómo las evitamos.** Cada una
tiene una prueba automática en `tests/test_beacon_expedition.py`.

| Trampa | Por qué daría puntos | Cómo se evita | Prueba |
|---|---|---|---|
| Visitar la misma baliza muchas veces | Si el bono se diera en cada entrada al radio | Cada bono se da una sola vez y solo si la baliza es el objetivo actual | `test_b1_bonus_once_and_in_order` |
| Visitar B2 antes que B1 | Si las balizas no tuvieran orden | Solo cuenta la baliza de la etapa actual | `test_b1_bonus_once_and_in_order` |
| Ir y venir cerca de la baliza | Ganaría progreso cada vez que se acerca | El progreso es la diferencia de distancias (ir y volver suma cero) y se paga el tiempo | — |
| Girar o quedarse quieto | Si hubiera un bono por "estar vivo" (como el +0.02·upright del bípedo) | No hay bono por sobrevivir: cada paso cuesta −0.01 y consumo | `test_spinning_in_place_does_not_pay` |
| Volver a la base sin visitar las balizas | Si el bono de la base no dependiera de la etapa | El bono de la base solo cuenta en la etapa 3 | `test_base_without_beacons_is_not_success` |
| Terminar a propósito (grieta) | Si fallar costara menos que el tiempo restante | Fallar cuesta −50, más que todo el costo de tiempo y consumo (−12 como máximo) | `test_crack_ends_episode` |
| Atravesar rocas o empujarse contra ellas | Si la física dejara pasar | El robot se detiene en el choque y paga −0.5 por paso con choque | `test_collision_is_penalized` |

**Decisiones pendientes (para discutir en el equipo):**
1. **El bípedo físico.** Con el Q-learning tabular de `qlearning_agent.py`, el
   bípedo de MuJoCo no aprende a caminar.
   - Medición del 28 oct: 300 episodios, 0 éxitos, como máximo 79 pasos antes
     de caer y 9 % de progreso.
   - Con acciones en cero cae en 36–42 pasos. Se agacha por debajo del umbral
     de 0.85 m sin volcarse, así que el umbral puede ser demasiado alto.
   - Propuesta: dejar la navegación (este ambiente) para Q-learning y usar el
     bípedo con PPO (`train.py`) como nivel físico más adelante.
2. ¿Entrenar con el bloqueo en una fracción de los episodios (por ejemplo 30 %)
   para mejorar la robustez?
3. ¿Balizas aleatorias? Hoy son fijas. Como el estado no usa `x, y`, la política
   debería transferirse en parte, pero no está medido.
4. ¿Agregar un sensor de suelo para que el agente "vea" la grieta?
5. Calibrar los coeficientes de batería y recompensa con más semillas, y
   reportar la media y la desviación de varias ejecuciones de entrenamiento.
