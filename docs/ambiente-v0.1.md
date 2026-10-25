# Ambiente v0.1

> Ficha de diseño de **Robot Expedition**. Es una propuesta por calibrar: los
> rangos y coeficientes se justifican abajo, pero deben ajustarse al medir el
> ambiente real. Las secciones siguen la plantilla `plantilla-ambiente-v0.1.md`.

## Mision y mapa

**Misión:** un robot bípedo sale de la base, visita **la baliza 1 y después la
baliza 2** (en ese orden) y **regresa a la base antes de agotar la batería**,
sin caer y chocando lo menos posible.

![Mapa del ambiente v0.1](mapa-ambiente-v0.1.svg)

(También en PNG: [mapa-ambiente-v0.1.png](mapa-ambiente-v0.1.png).)

| Elemento | Posición / tamaño | Unidad | Comentario |
|---|---|---|---|
| Sala | x ∈ [0, 12], y ∈ [-6, 6] | m | Suelo de Marte (gravedad 3.71 m/s²), paredes de 0.5 m de alto |
| Base (inicio y fin) | Centro (1.5, 0), cuadrado de 2 × 2 | m | El robot empieza en el centro mirando hacia +x |
| Baliza 1 (B1) | (9.5, 3.5), radio de visita 0.6 | m | Primera meta |
| Baliza 2 (B2) | (9.5, -3.5), radio de visita 0.6 | m | Segunda meta |
| Rocas R1–R5 | Cajas de 0.8–1.2 × 0.8–2.0 × 0.5–1.0 | m | Choque físico; en `reset()` se mueven ±0.5 m |
| Grieta | (3.5, 3.5), 1.0 × 0.4 | m | Pisarla termina el episodio (falla) |
| Arena | x ∈ [6, 8], y ∈ [-5.2, -3.8] | m | Fricción μ = 0.25 (resbala) |
| Pasillo mínimo | 1.2 | m | Ancho mínimo garantizado entre obstáculos |

La ruta de referencia base → B1 → B2 → base mide unos **25 m**. El robot mide
unos 0.5 m de ancho, así que un pasillo de 1.2 m deja margen para el balanceo
lateral de la marcha.

**Parametría (se fija antes de ejecutar):**

| Parámetro | Valor v0.1 | Rango a explorar | Unidad | Qué cambia |
|---|---|---|---|---|
| Tamaño del mapa | 12 × 12 | 8 × 8 – 20 × 20 | m × m | Escala del recorrido y batería necesaria |
| Ancho de pasillos | 1.2 | 0.9 – 2.0 | m | Dificultad de navegación |
| Velocidad máxima | No se impone; la limitan los torques (gear 20–35 N·m). Se espera 0.2 – 0.6 | — | m/s | Capacidad de avance |
| Ruido de distancia | σ = 0.02 | 0 – 0.10 | m (desv. estándar) | Calidad de los sensores |
| Radio de visita | 0.6 | 0.4 – 1.0 | m | Precisión exigida en las balizas |
| Consumo de batería | 0.02 + 0.06·E por paso | ver Dinámica | % / paso | Autonomía |

## Variables y unidades

**Estado del mundo** (lo que existe en el simulador):

| Variable | Significado | Unidad | Rango | ¿La ve el agente? |
|---|---|---|---|---|
| `x, y` | Posición del torso en el plano | m | [0, 12], [-6, 6] | **No** (solo relativa al objetivo) |
| `z` | Altura del torso | m | [0, 2.5] | Sí |
| `q` | Orientación del torso (cuaternión) | — | norma 1 | Sí |
| `v` | Velocidad lineal del torso | m/s | aprox. [-3, 3] | Sí (velocímetro) |
| `ω` | Velocidad angular del torso | rad/s | aprox. [-10, 10] | Sí (giroscopio) |
| `θ_j` | Ángulo de las 10 articulaciones | rad | cadera roll ±0.6, cadera pitch ±1.2, rodilla [-0.1, 2.2], tobillo pitch ±0.8, tobillo roll ±0.5 | Sí |
| `θ̇_j` | Velocidad de las articulaciones | rad/s | aprox. [-20, 20] | Sí |
| `contacto_izq/der` | Fuerza de contacto en cada pie | N | [0, ∞) | Sí |
| `B` | Batería | % | [0, 100] | Sí (normalizada a [0, 1]) |
| `etapa` | Objetivo actual: 1 = B1, 2 = B2, 3 = base | — | {1, 2, 3} | Sí (one-hot) |
| `visitadas` | Balizas visitadas (v1, v2) | — | {0, 1}² | Indirectamente (por la etapa) |
| `choques` | Pasos con contacto robot–roca o robot–pared | pasos | [0, 3000] | No (solo en `info`) |
| `t` | Paso del episodio | pasos | [0, 3000] | No (pendiente, ver abajo) |
| Posición de balizas, base y rocas | Distribución del mapa | m | ver mapa | **No** (solo con rayos y dirección al objetivo) |
| `μ` por zona | Fricción del suelo | — | [0.25, 0.9] | No |

## Observaciones y acciones

**Observación** (vector `float32` de 59 valores):

| Bloque | Tamaño | Unidad | Rango |
|---|---|---|---|
| Ángulos de las articulaciones | 10 | rad | límites de cada articulación |
| Velocidades de las articulaciones | 10 | rad/s | aprox. [-20, 20] |
| Orientación del torso (cuaternión) | 4 | — | [-1, 1] |
| Altura del torso | 1 | m | [0, 2.5] |
| Velocidad lineal (velocímetro) | 3 | m/s | aprox. [-3, 3] |
| Velocidad angular (giroscopio) | 3 | rad/s | aprox. [-10, 10] |
| Contacto de los pies | 2 | N | [0, ∞) |
| Acción anterior | 10 | — | [-1, 1] |
| **9 rayos de distancia** de -90° a +90° cada 22.5°, con ruido N(0, 0.02) | 9 | m | [0, 5] (5 = no hay nada) |
| Distancia al objetivo actual | 1 | m | [0, 17] |
| Dirección al objetivo (sen, cos del ángulo relativo) | 2 | — | [-1, 1] |
| Batería | 1 | — | [0, 1] |
| Etapa (one-hot) | 3 | — | {0, 1} |

Los rayos salen horizontalmente desde un sensor a 0.4 m de altura y detectan
rocas, paredes y la roca de la perturbación. Por eso todas las rocas deben medir
más de 0.4 m de alto.

**Acción** (vector continuo de 10 valores en [-1, 1]): un torque por motor,
`τ = a · gear`. Los motores son cadera roll y pitch (gear 35), rodilla (gear 30)
y tobillo pitch y roll (gear 20) de cada pierna, así que el torque máximo va de
20 a 35 N·m. El ambiente recorta toda acción fuera de [-1, 1]. La ficha del
profesor propone "avance y giro"; aquí avanzar y girar no son comandos directos,
sino el resultado de la marcha que aprende el agente.

## Dinamica

Cada paso del agente dura **0.05 s** (20 Hz). En cada `step(a)` ocurre lo
siguiente, en este orden:

1. **Acción:** se recorta `a` a [-1, 1] y se aplican los torques.
2. **Física:** MuJoCo integra 5 subpasos de 0.01 s con gravedad 3.71 m/s²,
   contactos y fricción del suelo de cada zona.
3. **Batería:** `B ← max(0, B − (0.02 + 0.06·E))`, con `E = mean(a²) ∈ [0, 1]`.
   - Con una marcha típica (E ≈ 0.3) se gastan 0.038 %/paso, así que la batería
     dura unos 2 630 pasos (131 s).
   - La ruta de 25 m a 0.3 m/s toma unos 1 670 pasos (83 s) y gasta cerca del
     63 %. Sobra batería, pero no tanta como para desperdiciarla.
   - Si el robot se queda quieto (E = 0) gasta 0.02 %/paso.
4. **Progreso:** se calcula `d_t`, la distancia (x, y) al objetivo de la etapa
   que estaba activa **al inicio** del paso.
5. **Choques:** si hay contacto entre una pieza del robot y una roca o pared,
   `choque = 1`.
6. **Visitas:**
   - Si `etapa = 1` y la distancia a B1 es menor que 0.6 m: `v1 = 1` y la etapa
     pasa a 2.
   - Si `etapa = 2` y la distancia a B2 es menor que 0.6 m: `v2 = 1` y la etapa
     pasa a 3.
   - Entrar al radio de una baliza que **no** es el objetivo actual no hace nada.
7. **Fin:** se revisan éxito, caída, grieta, batería y límite de tiempo (ver más
   abajo).
8. **Observación nueva:** se calculan los rayos (`mj_ray`), la dirección y la
   distancia al nuevo objetivo.

**Aleatoriedad en `reset(seed)`:**
- La postura inicial lleva ruido N(0, 0.02 rad) en las articulaciones.
- Las rocas se mueven ±0.5 m, siempre conservando pasillos de al menos 1.2 m.
- La fricción de las zonas irregulares se sortea en [0.35, 0.9].
- Las balizas quedan fijas en v0.1.

## Recompensa

Recompensa en cada paso:

```
r_t = 1.0 · (d_{t-1} − d_t)      # progreso hacia el objetivo actual (m)
    − 0.01                        # costo de tiempo
    − 0.02 · E_t                  # consumo
    − 0.5 · choque_t              # choque con roca o pared
    + 10   si visita B1 en la etapa 1          (solo una vez)
    + 10   si visita B2 en la etapa 2          (solo una vez)
    + 50 + 20 · (B / 100)  si llega a la base en la etapa 3 (éxito)
    − 50   si cae, pisa la grieta o agota la batería
```

Por qué se eligió así:
- **El progreso es la diferencia de distancias**, que funciona como un
  potencial. Si el robot va y vuelve, la suma de esos términos se cancela, así
  que oscilar no da puntos.
- **Los bonos solo valen para la baliza del objetivo actual y se dan una vez.**
  Esto responde a la pregunta del reto: no se gana visitando la misma baliza
  repetidas veces.
- **La penalización por caer (−50) es mayor que el costo de tiempo de todo un
  episodio (3000 × 0.01 = 30).** Así no le conviene "suicidarse" para cortar el
  episodio.
- **El bono final depende de la batería que quede**, lo que premia rutas
  eficientes.
- **Se elimina el bono por estar de pie** que tiene el código actual, porque
  permite ganar puntos sin moverse (ver Trampas).

## Exito, fracaso y limite de tiempo

| Caso | Condición | Gymnasium |
|---|---|---|
| **Éxito** | `v1 = 1`, `v2 = 1`, el torso dentro del cuadrado de la base, de pie (`upright > 0.7`) y `B > 0` | `terminated = True`, `info["success"] = True` |
| **Fracaso: caída** | Altura del torso menor que 0.85 m, o `upright < 0.35` | `terminated = True` |
| **Fracaso: grieta** | Torso (x, y) dentro de la grieta | `terminated = True` |
| **Fracaso: batería** | `B = 0` | `terminated = True` |
| **Límite de tiempo** | `t = 3000` pasos (150 s simulados) | `truncated = True` |

`upright` es la componente vertical del eje z del torso (1 = derecho). El límite
de 3000 pasos casi duplica los 1 670 que toma la ruta de referencia: da margen
para que el agente se recupere, pero no deja que pierda el tiempo
indefinidamente.

## Metricas e incidente

Se evalúa con **50 episodios con semillas fijas** que no se usan en el
entrenamiento.

| # | Métrica | Cómo se calcula | Unidad |
|---|---|---|---|
| 1 | **Tasa de éxito** | Episodios exitosos / 50 | % |
| 2 | **Eficiencia de ruta** | 25 m / distancia recorrida (solo en éxitos) | [0, 1] |
| 3 | **Choques por episodio** | Media de `info["choques"]` | pasos con choque |

También se registran, sin ser métricas principales: las balizas visitadas en
orden (0–2), la batería final (%) y la causa del fin (éxito, caída, grieta,
batería o tiempo).

**Perturbación: corredor bloqueado.**
- **Qué pasa:** al visitar B1 aparece una roca de 2.2 × 0.6 × 0.8 m centrada en
  (9.7, 0), que corta el camino directo B1 → B2. Solo queda un pasillo de 1.2 m
  junto a la pared este, o el rodeo por el oeste de R3.
- **Cuándo:** solo en los episodios de evaluación de robustez. El agente no la
  ve en el entrenamiento v0.1.
- **Qué se mide:** las 3 métricas con y sin bloqueo. Consideramos robusto al
  agente si la tasa de éxito baja **menos de 20 puntos porcentuales**.
- **Variante:** subir el ruido de los rayos a σ = 0.05 m.

## Cinco transiciones

Son ejemplos ilustrativos con los coeficientes de arriba, no salidas medidas. La
dirección se expresa como el ángulo relativo al frente del robot.

| # | Observación (resumen) | Acción | Nuevo estado | Recompensa | ¿Fin? |
|---|---|---|---|---|---|
| 1 | `t=0`, en la base (1.5, 0), etapa 1 (B1); B1 a 8.73 m y +23.6°; rayo +22.5° = 3.25 m (R1), los demás en 5.0; `B = 100 %` | Inicio de la marcha: cadera izq. pitch +0.4, rodilla der. +0.3, resto pequeño (E = 0.12) | Avanza 0.01 m; `d = 8.72`; `B = 99.97 %` | 0.01 − 0.01 − 0.0024 = **−0.002** | No |
| 2 | `t=840`, etapa 1; B1 a 0.63 m y +5°; `B = 68.1 %` | Paso hacia adelante (E = 0.30) | `d_B1 = 0.58 < 0.6` → `v1 = 1`, **etapa 2**; nuevo objetivo B2 a 7.0 m; `B = 68.06 %` | 0.05 − 0.01 − 0.006 + 10 = **+10.03** | No |
| 3 | `t=905`, etapa 2, **con perturbación**; B2 a 4.05 m al frente; rayo 0° = 0.25 m (bloqueo); `B = 65.6 %` | Sigue de frente (E = 0.35) | El pie choca con la roca y el robot rebota: `d = 4.06`, `choque = 1` | −0.01 − 0.01 − 0.007 − 0.5 = **−0.53** | No |
| 4 | `t=960`, etapa 2; B2 a 6.40 m; el robot vuelve a entrar al radio de **B1** (ya visitada) | Paso hacia B1 (E = 0.30) | `d_B2 = 6.45`; no hay bono porque B1 no es el objetivo actual | −0.05 − 0.01 − 0.006 = **−0.07** | No |
| 5 | `t=1690`, etapa 3 (base); base a 1.02 m; `upright = 0.93`; `B = 35.8 %` | Último paso (E = 0.30) | El torso entra a la base, de pie y con batería → **éxito** | 0.05 − 0.01 − 0.006 + 50 + 20·0.358 = **+57.19** | **Sí** (`terminated`, `success`) |

## Posibles trampas y decisiones pendientes

**Formas de ganar puntos sin cumplir la misión, y cómo las evitamos:**

| Trampa | Por qué daría puntos | Cómo se evita |
|---|---|---|
| Visitar la misma baliza muchas veces | Si el bono se diera en cada entrada al radio | Cada bono se da una sola vez y solo si la baliza es el objetivo de la etapa actual (transición 4) |
| Ir y venir cerca de la baliza | Ganaría progreso cada vez que se acerca | El progreso es la diferencia de distancias: ir y volver suma cero, y además se paga el tiempo |
| Quedarse de pie sin moverse | **En el código actual** cada paso da +0.02·upright y la batería solo baja 0.015/paso. Cuando el agente aprenda a equilibrarse, quedarse quieto sumaría unos +50 en 2500 pasos (hoy no pasa porque todavía se cae, ver nota) | Quitar el bono por estar de pie y cobrar −0.01 por paso: quieto, el agente pierde puntos |
| Volver a la base sin visitar las balizas | Si el bono de la base no dependiera de la etapa | El bono de la base solo cuenta en la etapa 3 |
| Caer a propósito para cortar el episodio | Si caer costara menos que el tiempo restante | La caída cuesta −50, más que el costo máximo de tiempo (−30) |
| Arrastrarse o rodar en vez de caminar | Avanza sin caminar | Termina si la altura del torso baja de 0.85 m o si `upright < 0.35` |
| Empujarse contra la pared | El rebote físico podría impulsarlo | −0.5 por cada paso con choque |

**Nota sobre el código actual (prueba del 25 oct 2026, 3 semillas):** con
acciones en cero el robot termina por caída en 36–42 pasos (unos 2 s). Con
acciones al azar termina en 17–28 pasos. En casi todos los casos la altura del
torso baja de 0.85 m mientras el robot sigue casi derecho (`upright` entre 0.63
y 0.95): se agacha, no se vuelca. Hay que revisar si el umbral de 0.85 m es
demasiado alto para la postura de pie de este modelo.

**Decisiones pendientes (para discutir en el equipo):**
1. **¿Bípedo o robot con ruedas?** El código actual es un bípedo 3D (más
   difícil de entrenar). La ficha del profesor sugiere avance y giro, que sería
   más simple. En v0.1 mantenemos el bípedo para no tirar el trabajo hecho.
2. ¿Mostrar `t / 3000` al agente para que "sepa" cuánto tiempo le queda?
3. ¿Balizas fijas o aleatorias? Si son fijas, el agente podría memorizar la
   ruta en vez de navegar.
4. ¿La perturbación también aparece en el entrenamiento (por ejemplo con
   probabilidad 0.3)?
5. Calibrar los coeficientes de batería y de recompensa con episodios reales.
6. ¿Basta con el radio de visita de 0.6 m, o el robot también tiene que
   detenerse en la baliza?

**Cambios necesarios en el código (`robot_expedition/envs/mars_biped.py`) para
que coincida con esta ficha:**
- Agregar las paredes, la base, B1, B2 y las rocas R1–R5 del mapa (hoy el
  terreno es abierto, de 100 × 100 m, con 20 obstáculos al azar).
- Agregar la etapa, las balizas visitadas y la dirección y distancia al
  objetivo. Hoy la misión es solo `x ≥ 15 m`.
- Cambiar el "lidar" actual (distancia a los centros de los obstáculos) por 9
  rayos reales con `mujoco.mj_ray` y ruido.
- Quitar `x, y` absolutos de la observación.
- Contar choques con roca o pared y registrarlos en `info`.
- Usar la recompensa nueva y quitar el bono por estar de pie.
- `max_steps = 3000` y la batería `0.02 + 0.06·E`.
