# Tensor de esfuerzos, presión y deviador — `presion_tensor_arch.py`

Guía línea por línea del cálculo de presión `P` y esfuerzo de corte (deviador) `τ` por partícula en cada atasco. Los números de línea corresponden a `presion_tensor_arch.py` en este mismo directorio. Si el script cambia, actualizar esta tabla.

El documento `presion_tensor_arch.md` explica la teoría general. Este README sigue el código.

---

## 1. Qué calcula, en una línea

Para cada partícula `p` de un atasco, a partir de las fuerzas de contacto:

$$
\sigma^{(p)}_{ij} \;=\; -\frac{1}{A_p}\sum_{c\,\in\,p} r^{c}_i\, f^{c}_j
\qquad
P = \tfrac12(\sigma_{xx}+\sigma_{yy})
\qquad
\tau = \sqrt{\left(\tfrac{\sigma_{xx}-\sigma_{yy}}{2}\right)^2+\sigma_{xy}^2}
$$

- $r^c$ es el vector desde el centro de la partícula al punto de contacto.
- $f^c$ es la fuerza que recibe la partícula en ese contacto.
- $A_p$ es el área de la partícula.

El signo menos hace que la compresión sea positiva. `τ` es el radio del círculo de Mohr, $(\sigma_1-\sigma_2)/2$: es la magnitud del deviador en 2D y no depende de la orientación de los ejes.

---

## 2. Flujo general

```
main() ─┬─ cargar_master()              índice de simulaciones (radios, lados, chi)
        ├─ listar_atascos()/leer_lista()  pares (atasco_XXXXX.xy, atasco_contacts_XXXXX.dat)
        ├─ generar_tareas()              un atasco = una tarea
        └─ Pool → process_one_jam_task() ──┬─ parse_xy()                     partículas
                                           ├─ lee contactos (pd.read_csv)
                                           ├─ detectar_arco_primario()       región "arco"
                                           └─ calcular_tensor_y_presion_vectorizado()   ← tensor, P, τ
           Registro.guardar_lote()   →  partes/*.parquet + resumen_presion_por_atasco.csv
           combinar_partes()         →  presion_por_particula_<Forma>.parquet
           resumen_por_configuracion() → resumen_presion_por_configuracion.csv
```

---

## 3. Entradas

### 3.1 Partículas — `parse_xy()` (líneas 35–56)

Lee `atasco_XXXXX.xy` (snapshot del atasco, escrito por el simulador):

| Formato de línea | Significado |
|---|---|
| `id 1 x y r tipo` | disco: centro `(x, y)`, radio `r` |
| `id n x1 y1 … xn yn tipo` | polígono de `n` lados: vértices absolutos |
| `id < 0` | paredes/piso: se ignoran como partículas (línea 42) |

| Líneas | Qué hace |
|---|---|
| 45–48 | Disco: `area = π r²`, `r_eff = r`, `coords = None`. |
| 50–55 | Polígono: centro = **promedio de los vértices** (línea 51); `r_eff` = distancia máxima centro–vértice (circunradio, línea 53); `area` con la fórmula del zapato (`poly_area`, líneas 20–23). |

El promedio de vértices coincide con el centro de masa solo para polígonos regulares, que es el caso de este proyecto.

### 3.2 Contactos (líneas 497–499)

Lee `atasco_contacts_XXXXX.dat` con 6 columnas:

| Columna | Significado asumido por el código |
|---|---|
| `id_a`, `id_b` | cuerpos en contacto (A = fixture A de Box2D; `< 0` = pared) |
| `px`, `py` | punto de contacto (world manifold) |
| `f_norm` | **impulso** normal del paso (se divide por `dt` en la línea 349) |
| `f_tan` | **impulso** tangencial (ídem) |

> **A verificar:** estos archivos los escribe el binario del cluster, cuyo código fuente no está en el repo. No está confirmado si `f_norm`/`f_tan` son impulsos o fuerzas, ni si `f_tan` conserva el signo: la función `saveContacts` del repo guarda `fabs(tang)`. Ver la sección 8.

### 3.3 Parámetros por atasco — `process_one_jam_task()` (líneas 464–553)

| Líneas | Qué hace |
|---|---|
| 470–477 | `r_nominal = r_eff · cos(π/n)`: para polígonos pasa del circunradio al **inradio**; para discos queda igual. Se usa solo para separar grandes de chicos. |
| 479–494 | Umbral grande/chico: `umbral_r = (r_large + r_small)/2`, con radios del índice maestro o, si faltan, de los radios presentes en el atasco. Con χ = 0 o monodisperso, `umbral_r = 0` (todo es "B"). |
| 501–502 | `r_salida` y `g` de `params.in` (`parse_radio_salida`, `parse_g`, líneas 58–90). `g` se toma en valor absoluto. |
| 503–505 | Detecta el arco; si no hay arco, el atasco se descarta (`"No arco detectado"`). |
| 507 | Llama al cálculo del tensor (sección 5). |
| 509–552 | Agrega metadatos (formas, χ, `jam_id`, `sim_path`) al resumen y a las filas por partícula. |

`dt` llega por argumento (`--dt`, default `0.001`, línea 840) y tiene que coincidir con `timeStep` de la simulación.

---

## 4. Detección del arco — `detectar_arco_primario()` (líneas 93–193)

Define qué partículas son la región `arco`.

| Líneas | Qué hace |
|---|---|
| 115–124 | Un par por cada dos partículas en contacto, sin paredes. Si un par tiene 2 puntos de contacto, queda una sola arista. |
| 126–138 | Grafo con costo de arista `10^{y_max}` del par: favorece mucho los caminos bajos. |
| 172–175 | Candidatos a extremos: partículas apoyadas en el piso (`y − r < 0.2`) a la izquierda (`x < 0`) y a la derecha (`x > 0`). |
| 183–193 | Un Dijkstra por cada extremo izquierdo; se queda con el camino de costo mínimo hacia cualquier extremo derecho. |
| 142–157, 159–170 | `purgar_cimientos`: recorta de cada punta los granos que solo son cimiento (apoyados en el piso fuera del orificio o con ≥ 2 apoyos inferiores ajenos al arco). |

---

## 5. Núcleo: `calcular_tensor_y_presion_vectorizado()` (líneas 296–459)

### 5.1 Unir contactos con partículas (líneas 297–308)

| Líneas | Qué hace |
|---|---|
| 300–301 | Une cada contacto con la posición, forma y vértices de A (`_A`) y de B (`_B`). `how='left'`: los contactos con pared no se pierden. |
| 303–304 | `a_valida`/`b_valida`: el lado es un grano real (no pared). |
| 307–308 | De qué lado sale la normal: de A si A es grano (`usar_A`); si A es pared, de B (`usar_B`). |

### 5.2 Normal del contacto (líneas 310–341)

| Líneas | Caso | Normal |
|---|---|---|
| 313–320 | A es disco | $\hat n = (\mathbf p_c - \mathbf c_A)/\lvert\cdot\rvert$, de A hacia el contacto, es decir de A hacia B. |
| 322–329 | A es pared, B disco | $\hat n = (\mathbf p_c - \mathbf c_B)/\lvert\cdot\rvert$, de B hacia la pared. |
| 333–341 | Polígono (A o B) | `normales_poligonos()` (líneas 253–293): lado del polígono más cercano al punto de contacto, normal unitaria orientada hacia afuera del centro. |

> En un contacto vértice–lado, si el vértice es del polígono que se usa para la normal, el "lado más cercano" es ambiguo: hay dos lados adyacentes. La normal física es la del **otro** cuerpo. Box2D la tiene exacta en `worldManifold.normal`. Guardarla en el archivo de contactos eliminaría esta aproximación.

### 5.3 Fuerza sobre A (líneas 343–350)

```python
343  tx = -ny                       # t = n rotada +90°
344  ty =  nx
349  Fx_A = (-f_norm*nx + f_tan*tx) / dt
350  Fy_A = (-f_norm*ny + f_tan*ty) / dt
```

- **Parte normal:** `-f_norm·n̂` es la fuerza que B ejerce sobre A. Empuja a A hacia su centro.
- **Parte tangencial:** `+f_tan·t̂` con `t̂ = (−n_y, n_x)`. En Box2D la tangente es `b2Cross(n, 1) = (n_y, −n_x) = −t̂`, y el impulso sobre B es `fn·n̂ + ft·(n_y, −n_x)`. Sobre A va el opuesto: `−fn·n̂ − ft·(n_y, −n_x) = −fn·n̂ + ft·t̂`.
- **`/ dt`:** convierte el impulso del paso en fuerza.

> **Corregido (versión anterior: `− f_tan·t̂`).** El signo tangencial estaba invertido. Se confirmó con el equilibrio estático de cada grano en datos reales (`BARRIDO_2D_DISK_DISK/Chi_0p2_W_2p0`, atascos 1–5, ~5300 granos por atasco): con el signo actual el residuo |ΣF − mg|/(mg) es 0.0002; con el anterior era 15. La versión anterior afectaba a `τ` siempre y a `P` solo en polígonos (en discos $\mathbf r \parallel \hat n$ y la tangencial no aporta a la traza). **Los resultados de τ, y de P en polígonos, generados antes de esta corrección hay que recalcularlos.**

### 5.4 Contribución de cada contacto al tensor (líneas 352–374)

Para cada partícula se suma $S_{ij} = \sum_c r_i f_j$, con $\mathbf r = \mathbf p_c - \mathbf c_p$:

| Líneas | Componente | Expresión |
|---|---|---|
| 364 / 366 | `S00` = $r_x f_x$ | `Fx · (px − pos_x)` |
| 365 / 367 | `S11` = $r_y f_y$ | `Fy · (py − pos_y)` |
| 371 / 373 | `S01` = $r_x f_y$ | `Fy · (px − pos_x)` |
| 372 / 374 | `S10` = $r_y f_x$ | `Fx · (py − pos_y)` |

- **Lado A (364–365, 371–372):** usa `F_A` tal cual. Si A es pared, aporta 0.
- **Lado B (366–367, 373–374):** usa `signo_B · F_A` (línea 363).
  - Contacto grano–grano (`usar_A`): `signo_B = −1`, porque la fuerza sobre B es la reacción −F_A (3ª ley de Newton).
  - A es pared (`usar_B`): la normal se calculó desde B, así que `F_A` ya es la fuerza sobre B y `signo_B = +1`.

### 5.5 Suma por partícula (líneas 376–384)

| Líneas | Qué hace |
|---|---|
| 378–380 | Suma las contribuciones de todos los contactos donde la partícula es A y donde es B. |
| 384 | Une con la tabla de partículas. Las partículas sin contactos quedan con `S = 0`. |

### 5.6 Presión (líneas 385–389)

```python
385  P = -0.5 * (S00 + S11) / area          # = (σxx + σyy)/2, compresión > 0
389  P_reducida = P / g
```

### 5.7 Tensor y deviador (líneas 395–406)

```python
397  σxx = -S00 / area
398  σyy = -S11 / area
399  σxy = -0.5 * (S01 + S10) / area         # se simetriza
402  τ   = sqrt( ((σxx − σyy)/2)**2 + σxy**2 )
403  τ_reducida = τ / g
404–406  σxx/g, σyy/g, σxy/g                 # se guardan para recalcular invariantes después
```

| Línea | Detalle |
|---|---|
| 395–396 | Si `area = 0` (no debería pasar), el tensor vale 0 en vez de dividir por cero. |
| 399 | **Simetrización:** con torques balanceados (equilibrio estático) `S01 ≈ S10`. La parte antisimétrica se descarta. |
| 402 | Radio del círculo de Mohr = $(\sigma_1 - \sigma_2)/2$ = magnitud del deviador 2D. Es invariante ante rotación de ejes. **No** es lo mismo que $\sigma_{xy}$ solo, que depende de los ejes. |

Relaciones útiles:
- Esfuerzos principales: $\sigma_{1,2} = P \pm \tau$.
- Relación de esfuerzos (fricción movilizada): $\mu^* = \tau/P$.

Algunos trabajos llaman deviador a $q = \sigma_1-\sigma_2 = 2\tau$; conviene aclarar en el paper cuál se usa.

### 5.8 Regiones y especies (líneas 408–416)

| Líneas | Qué hace |
|---|---|
| 408–410 | ROI: franja con `y` entre el grano más bajo del arco y el más alto **+ 10** (en metros: ~10 diámetros de grano grande). Sin arco: `[0, 20]`. |
| 412–413 | `region = 'arco'` si está en el arco; si no, `'roi'` si está en la franja; si no, `'bulk'`. |
| 415–416 | `tipo = 'B'` (grande) si `r_nominal ≥ umbral_r`; si no, `'S'` (chico). |

### 5.9 Resumen por atasco (líneas 417–443)

Para cada región (`arco`, `roi`, `bulk`) y por especie (`_B`, `_S`), guarda **sumas** y no promedios, así después se pueden juntar varios atascos:

| Columna | Valor |
|---|---|
| `SumP_<reg>[_tipo]` | $\sum_p P_p A_p$ |
| `SumTau_<reg>[_tipo]` | $\sum_p \tau_p A_p$ |
| `Area_<reg>[_tipo]` | $\sum_p A_p$ |
| (+ versiones `_reducida_`, divididas por g) | |

### 5.10 Salida por partícula (líneas 447–456)

`pos_x, pos_y, shape, tipo, region, area, P, P_reducida, tau, tau_reducida, sigma_xx_reducida, sigma_yy_reducida, sigma_xy_reducida, coords`. Los vértices van serializados a JSON (línea 454) para poder dibujar los polígonos.

---

## 6. Agregación por configuración — `resumen_por_configuracion()` (líneas 794–822)

| Líneas | Qué hace |
|---|---|
| 799–801 | Usa solo atascos de lotes completos (`lotes_ok.txt`). |
| 802–811 | Agrupa por forma grande/chica, χ, r_chica y carpeta de simulación; suma las columnas `SumP_*`, `SumTau_*`, `Area_*`. |
| 812–820 | `mean_P_<reg> = ΣSumP / ΣArea` y `mean_tau_<reg> = ΣSumTau / ΣArea`: promedios **pesados por área de partícula**, sobre todas las partículas de todos los atascos de la configuración. |

> `mean_tau` es el promedio de $\lvert\tau\rvert$ de cada partícula. **No** es el τ del tensor promedio de la región. Como cada partícula tiene su propia orientación principal, $\langle\tau_p\rangle \ge \tau(\langle\sigma\rangle)$. Para el deviador macroscópico (por ejemplo $\mu^*$ de la región), primero promediar $\sigma_{xx}, \sigma_{yy}, \sigma_{xy}$ pesados por área (columnas de la salida por partícula) y después aplicar la fórmula de la línea 398.

> El área usada es la del **sólido** (suma de áreas de partículas), no la de la región. El resultado es el esfuerzo medio dentro de los granos; el esfuerzo de continuo de la región es ≈ φ veces ese valor (φ = fracción de empaquetamiento).

---

## 7. Salidas en disco

| Archivo | Contenido |
|---|---|
| `<out>/presion_por_particula_<Forma>.parquet` | una fila por partícula y atasco (sección 5.10) |
| `<out>/resumen_presion_por_atasco.csv` | sumas por región/especie, una fila por atasco (5.9) |
| `<out>/resumen_presion_por_configuracion.csv` | promedios pesados por área (6) |
| `<out>/lotes_ok.txt`, `procesados.txt`, `partes/` | control de lotes para `--reanudar` (`Registro`, líneas 695–760) |

---

## 8. Verificaciones

### Ya confirmadas con datos (diagnóstico del 2026-10-02)

Con `verificar_contactos.py` sobre `BARRIDO_2D_DISK_DISK/Chi_0p2_W_2p0`, atascos 1–5:

| Pregunta | Resultado |
|---|---|
| ¿Signo de la tangencial? | Convención de Box2D. Residuo de equilibrio **0.0002** con el código actual (líneas 349–350); con el signo anterior era **15**. |
| ¿`f_tan` tiene signo? | Sí: ~50 % de valores negativos. |
| ¿Impulsos o fuerzas? | Impulsos: dividir por `dt` es correcto (sin dividir, el residuo es ≈ 1). |

Para repetir el chequeo en otra configuración, por ejemplo una con polígonos:

```bash
python analysis/utils/verificar_contactos.py --sim_path <carpeta_de_una_simulacion> --jam_id 1 2 3 4 5
```

La hipótesis `codigo_actual` tiene que dar residuo ≈ 0.

### Pendientes

1. **Clasificación grande/chico (líneas 477, 494, 416).** Se compara el **inradio** de los polígonos (`r_eff·cos(π/n)`) con un umbral armado con `r_large`/`r_small` del índice. Si esos radios no están en la misma definición (circunradio o radio de igual área), un polígono grande puede quedar como "S" cuando los tamaños son parecidos. Ejemplo con radios de igual área: un triángulo grande equivalente a un disco de r = 0.5 tiene inradio ≈ 0.39; con un disco chico de r = 0.32 (ratio de áreas 0.4) el umbral es ≈ 0.41, así que el triángulo quedaría como chico. Alternativa sin umbral: usar la columna `tipo` del `.xy`, que es la especie exacta de cada grano.
2. **Normal en contactos vértice–lado de polígonos** (sección 5.2): es una aproximación geométrica; la normal exacta está en Box2D. Conviene correr el diagnóstico en una configuración con polígonos: si el residuo es bastante mayor que en discos, el origen es esta aproximación.
3. **`simulation/src/save_tensors.cpp`** tiene el mismo signo tangencial invertido. Hoy no se llama desde ningún lado del simulador, pero si se vuelve a usar hay que corregirlo.
