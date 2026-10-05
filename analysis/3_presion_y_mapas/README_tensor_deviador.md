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
                                           ├─ parse_paredes()                paredes (gID < 0), para la normal
                                           └─ calcular_tensor_y_presion_vectorizado()   ← tensor, P, τ
           Registro.guardar_lote()   →  partes/*.parquet + resumen_presion_por_atasco.csv
           combinar_partes()         →  presion_por_particula_<Forma>.parquet
           resumen_por_configuracion() → resumen_presion_por_configuracion.csv
```

---

## 3. Entradas

### 3.1 Partículas — `parse_xy()` (líneas 39–60)

Lee `atasco_XXXXX.xy` (snapshot del atasco, escrito por el simulador):

| Formato de línea | Significado |
|---|---|
| `id 1 x y r tipo` | disco: centro `(x, y)`, radio `r` |
| `id n x1 y1 … xn yn tipo` | polígono de `n` lados: vértices absolutos |
| `id < 0` | paredes/piso: se ignoran como partículas (línea 46) |

| Líneas | Qué hace |
|---|---|
| 49–52 | Disco: `area = π r²`, `r_eff = r`, `coords = None`. |
| 54–59 | Polígono: centro = **promedio de los vértices** (línea 55); `r_eff` = distancia máxima centro–vértice (circunradio, línea 57); `area` con la fórmula del zapato (`poly_area`, líneas 24–27). |

El promedio de vértices coincide con el centro de masa solo para polígonos regulares, que es el caso de este proyecto.

### 3.2 Contactos (líneas 675–677)

Lee `atasco_contacts_XXXXX.dat` con 6 columnas:

| Columna | Significado asumido por el código |
|---|---|
| `id_a`, `id_b` | cuerpos en contacto (A = fixture A de Box2D; `< 0` = pared) |
| `px`, `py` | punto de contacto (world manifold) |
| `f_norm` | **impulso** normal del paso (se divide por `dt` en las líneas 547–548) |
| `f_tan` | **impulso** tangencial (ídem) |

> Estos archivos los escribe el binario del cluster, cuyo código fuente no está en el repo. Con el diagnóstico de la sección 8 se confirmó que `f_norm`/`f_tan` son impulsos y que `f_tan` conserva el signo (la función `saveContacts` del repo, en cambio, guarda `fabs(tang)`). El archivo **no** trae la normal del contacto (`worldManifold.normal`): hay que reconstruirla (sección 5.2).

### 3.3 Parámetros por atasco — `process_one_jam_task()` (líneas 656–730)

| Líneas | Qué hace |
|---|---|
| 662–673 | **Grande/chico por especie** (`especie_por_tipo`, `analysis/especies.py`): la columna `type` del `.xy`. La especie de mayor área mediana es `B` y la otra `S`. Con χ = 0, una sola especie o áreas iguales (ratio 1.0), todo es `B`. `r_chica` es el radio del índice maestro o, si falta, el radio de igual área de la especie chica. |
| 679–680 | `r_salida` y `g` de `params.in` (`parse_radio_salida`, `parse_g`, líneas 62–94). `g` se toma en valor absoluto. |
| 681–683 | Detecta el arco; si no hay arco, el atasco se descarta (`"No arco detectado"`). |
| 685–686 | Lee la geometría de las paredes del `.xy` (`parse_paredes`) y llama al cálculo del tensor (sección 5). |
| 688–728 | Agrega metadatos (formas, χ, `jam_id`, `sim_path`) al resumen y a las filas por partícula. |

`dt` llega por argumento (`--dt`, default `0.001`, línea 1017) y tiene que coincidir con `timeStep` de la simulación.

---

## 4. Detección del arco — `detectar_arco_primario()` (líneas 97–197)

Define qué partículas son la región `arco`.

| Líneas | Qué hace |
|---|---|
| 119–128 | Un par por cada dos partículas en contacto, sin paredes. Si un par tiene 2 puntos de contacto, queda una sola arista. |
| 130–142 | Grafo con costo de arista `10^{y_max}` del par: favorece mucho los caminos bajos. |
| 176–179 | Candidatos a extremos: partículas apoyadas en el piso (`y − r < 0.2`) a la izquierda (`x < 0`) y a la derecha (`x > 0`). |
| 187–197 | Un Dijkstra por cada extremo izquierdo; se queda con el camino de costo mínimo hacia cualquier extremo derecho. |
| 142–157, 159–170 | `purgar_cimientos`: recorta de cada punta los granos que solo son cimiento (apoyados en el piso fuera del orificio o con ≥ 2 apoyos inferiores ajenos al arco). |

---

## 5. Núcleo: `calcular_tensor_y_presion_vectorizado()` (líneas 523–651)

### 5.1 Unir contactos con partículas (líneas 527–533)

| Líneas | Qué hace |
|---|---|
| 529–530 | Une cada contacto con la posición, forma y vértices de A (`_A`) y de B (`_B`). `how='left'`: los contactos con pared no se pierden. |
| 532–533 | `a_valida`/`b_valida`: el lado es un grano real (no pared). |

### 5.2 Normal del contacto — `normales_contactos()` (líneas 451–520)

El archivo de contactos no trae `worldManifold.normal`, así que se reconstruye con la geometría del `.xy`. La normal va **siempre de A hacia B** (la misma convención que Box2D), también cuando A es una pared.

| Caso | Normal | Exactitud |
|---|---|---|
| A disco | $\hat n = (\mathbf p_c - \mathbf c_A)/\lvert\cdot\rvert$ | exacta: en un contacto con un círculo la normal pasa por su centro |
| B disco (A polígono o pared) | $\hat n = (\mathbf c_B - \mathbf p_c)/\lvert\cdot\rvert$ | exacta (en Box2D el polígono o la pared es siempre A y el círculo B) |
| polígono–polígono | `normales_poligono_poligono()` (líneas 368–388): replica `b2CollidePolygons`. Para cada cara de A, separación = mín. sobre vértices de B de $\hat m_i\cdot(\mathbf v^B_j-\mathbf v^A_i)$; ídem con B. La cara de referencia es la de B si `sepB > sepA + 0.1·linearSlop`; si no, la de A. $\hat n$ = normal saliente de la cara de A, o menos la de la cara de B. | exacta (salvo empates numéricos, entre caras paralelas que dan la misma normal) |
| pared–polígono | `normal_pared_poligono()` (líneas 404–448): replica `b2CollideEdgeAndPolygon` sobre el segmento de pared más cercano al punto de contacto: compara el eje de la pared con los ejes de las caras del polígono (histéresis 0.98 / 0.001) y aplica el "snap" de las cadenas en esquinas cóncavas. | exacta si el `.xy` trae las paredes (`saveAtascoFrame` las escribe con gID −104/−114) |
| polígono contra algo sin geometría (pared ausente del `.xy`, grano fuera del `.xy`) | lado del polígono más cercano al punto de contacto (`normales_poligonos()`, criterio anterior) | aproximada |

> **Corregido (versión anterior: siempre "el lado más cercano del polígono A").** Cuando el punto de contacto cae en un **vértice** de A, ese criterio elige un lado vecino y la normal sale girada 60–120°. Pasa en todos los contactos vértice(A)–lado(B) y en los extremos de los contactos cara–cara. En el contacto polígono–disco, además, el polígono es siempre A: si el disco toca una esquina, la normal correcta pasa por el centro del disco, no por la cara. Con atascos sintéticos de Box2D 2.4.2 (sección 8), la versión anterior daba errores de P y τ mayores al 1 % en 40–85 % de los granos de mezclas con polígonos (en los peores, ~100 %). La versión actual coincide con el tensor exacto de Box2D a 1e-5. **Hay que recalcular todos los resultados de P y τ con polígonos.** Los de discos puros no cambian.

### 5.3 Fuerza sobre A (líneas 541–548)

```python
541  tx = -ny                       # t = n rotada +94°
542  ty =  nx
547  Fx_A = (-f_norm*nx + f_tan*tx) / dt
548  Fy_A = (-f_norm*ny + f_tan*ty) / dt
```

- **Parte normal:** `-f_norm·n̂` es la fuerza que B ejerce sobre A. Empuja a A hacia su centro.
- **Parte tangencial:** `+f_tan·t̂` con `t̂ = (−n_y, n_x)`. En Box2D la tangente es `b2Cross(n, 1) = (n_y, −n_x) = −t̂`, y el impulso sobre B es `fn·n̂ + ft·(n_y, −n_x)`. Sobre A va el opuesto: `−fn·n̂ − ft·(n_y, −n_x) = −fn·n̂ + ft·t̂`.
- **`/ dt`:** convierte el impulso del paso en fuerza.

> **Corregido antes (versión anterior: `− f_tan·t̂`).** El signo tangencial estaba invertido. Se confirmó con el equilibrio estático de cada grano en datos reales (`BARRIDO_2D_DISK_DISK/Chi_0p2_W_2p0`, atascos 1–5): con el signo actual el residuo |ΣF − mg|/(mg) es 0.0002; con el anterior era 15.

### 5.4 Contribución de cada contacto al tensor (líneas 550–565)

Para cada partícula se suma $S_{ij} = \sum_c r_i f_j$, con $\mathbf r = \mathbf p_c - \mathbf c_p$:

| Componente | Lado A (553–556) | Lado B (557–560) |
|---|---|---|
| `S00` = $r_x f_x$ | `Fx_A · rxA` | `−Fx_A · rxB` |
| `S11` = $r_y f_y$ | `Fy_A · ryA` | `−Fy_A · ryB` |
| `S01` = $r_x f_y$ | `Fy_A · rxA` | `−Fy_A · rxB` |
| `S10` = $r_y f_x$ | `Fx_A · ryA` | `−Fx_A · ryB` |

- Como la normal va siempre de A hacia B, la fuerza sobre B es siempre la reacción −F_A (3ª ley de Newton), también cuando A es una pared. (La versión anterior calculaba la normal desde B cuando A era pared y necesitaba un `signo_B` especial; ya no hace falta.)
- Un lado que no es grano (pared) aporta 0.

### 5.5 Suma por partícula (líneas 568–576)

| Líneas | Qué hace |
|---|---|
| 570–572 | Suma las contribuciones de todos los contactos donde la partícula es A y donde es B. |
| 576 | Une con la tabla de partículas. Las partículas sin contactos quedan con `S = 0`. |

### 5.6 Presión (líneas 577–581)

```python
577  P = -0.5 * (S0 + S11) / area          # = (σxx + σyy)/2, compresión > 0
581  P_reducida = P / g
```

### 5.7 Tensor y deviador (líneas 587–598)

```python
589  σxx = -S0 / area
590  σyy = -S11 / area
591  σxy = -0.5 * (S1 + S10) / area         # se simetriza
594  τ   = sqrt( ((σxx − σyy)/2)**2 + σxy**2 )
595  τ_reducida = τ / g
596–598  σxx/g, σyy/g, σxy/g                 # se guardan para recalcular invariantes después
```

| Línea | Detalle |
|---|---|
| 587–588 | Si `area = 0` (no debería pasar), el tensor vale 0 en vez de dividir por cero. |
| 591 | **Simetrización:** con torques balanceados (equilibrio estático) `S1 ≈ S10`. La parte antisimétrica se descarta. |
| 594 | Radio del círculo de Mohr = $(\sigma_1 - \sigma_2)/2$ = magnitud del deviador 2D. Es invariante ante rotación de ejes. **No** es lo mismo que $\sigma_{xy}$ solo, que depende de los ejes. |

Relaciones útiles:
- Esfuerzos principales: $\sigma_{1,2} = P \pm \tau$.
- Relación de esfuerzos (fricción movilizada): $\mu^* = \tau/P$.

Algunos trabajos llaman deviador a $q = \sigma_1-\sigma_2 = 2\tau$; conviene aclarar en el paper cuál se usa.

### 5.8 Regiones y especies (líneas 600–608)

| Líneas | Qué hace |
|---|---|
| 600–602 | ROI: franja con `y` entre el grano más bajo del arco y el más alto **+ 10** (en metros: ~10 diámetros de grano grande). Sin arco: `[0, 24]`. |
| 604–605 | `region = 'arco'` si está en el arco; si no, `'roi'` si está en la franja; si no, `'bulk'`. |
| 607–608 | `tipo` (`B`/`S`) viene de `process_one_jam_task`, por especie (sección 3.3). |

### 5.9 Resumen por atasco (líneas 609–635)

Para cada región (`arco`, `roi`, `bulk`) y por especie (`_B`, `_S`), guarda **sumas** y no promedios, así después se pueden juntar varios atascos:

| Columna | Valor |
|---|---|
| `SumP_<reg>[_tipo]` | $\sum_p P_p A_p$ |
| `SumTau_<reg>[_tipo]` | $\sum_p \tau_p A_p$ |
| `Area_<reg>[_tipo]` | $\sum_p A_p$ |
| (+ versiones `_reducida_`, divididas por g) | |

### 5.10 Salida por partícula (líneas 639–648)

`pos_x, pos_y, shape, tipo, region, area, P, P_reducida, tau, tau_reducida, sigma_xx_reducida, sigma_yy_reducida, sigma_xy_reducida, coords`. Los vértices van serializados a JSON (línea 646) para poder dibujar los polígonos.

---

## 6. Agregación por configuración — `resumen_por_configuracion()` (líneas 971–999)

| Líneas | Qué hace |
|---|---|
| 976–978 | Usa solo atascos de lotes completos (`lotes_ok.txt`). |
| 979–988 | Agrupa por forma grande/chica, χ, r_chica y carpeta de simulación; suma las columnas `SumP_*`, `SumTau_*`, `Area_*`. |
| 989–997 | `mean_P_<reg> = ΣSumP / ΣArea` y `mean_tau_<reg> = ΣSumTau / ΣArea`: promedios **pesados por área de partícula**, sobre todas las partículas de todos los atascos de la configuración. |

> `mean_tau` es el promedio de $\lvert\tau\rvert$ de cada partícula. **No** es el τ del tensor promedio de la región. Como cada partícula tiene su propia orientación principal, $\langle\tau_p\rangle \ge \tau(\langle\sigma\rangle)$. Para el deviador macroscópico (por ejemplo $\mu^*$ de la región), primero promediar $\sigma_{xx}, \sigma_{yy}, \sigma_{xy}$ pesados por área (columnas de la salida por partícula) y después aplicar la fórmula de la línea 588.

> El área usada es la del **sólido** (suma de áreas de partículas), no la de la región. El resultado es el esfuerzo medio dentro de los granos; el esfuerzo de continuo de la región es ≈ φ veces ese valor (φ = fracción de empaquetamiento).

---

## 7. Salidas en disco

| Archivo | Contenido |
|---|---|
| `<out>/presion_por_particula_<Forma>.parquet` | una fila por partícula y atasco (sección 5.10) |
| `<out>/resumen_presion_por_atasco.csv` | sumas por región/especie, una fila por atasco (5.9) |
| `<out>/resumen_presion_por_configuracion.csv` | promedios pesados por área (6) |
| `<out>/lotes_ok.txt`, `procesados.txt`, `partes/` | control de lotes para `--reanudar` (`Registro`, líneas 872–937) |

---

## 8. Verificaciones

### Ya confirmadas con datos (diagnóstico del 2026-10-02)

Con `verificar_contactos.py` sobre `BARRIDO_2D_DISK_DISK/Chi_0p2_W_2p0`, atascos 1–5:

| Pregunta | Resultado |
|---|---|
| ¿Signo de la tangencial? | Convención de Box2D. Residuo de equilibrio **0.0002** con el código actual (líneas 353–354); con el signo anterior era **15**. |
| ¿`f_tan` tiene signo? | Sí: ~50 % de valores negativos. |
| ¿Impulsos o fuerzas? | Impulsos: dividir por `dt` es correcto (sin dividir, el residuo es ≈ 1). |

Para repetir el chequeo en otra configuración, por ejemplo una con polígonos:

```bash
python analysis/utils/verificar_contactos.py --sim_path <carpeta_de_una_simulacion> --jam_id 1 2 3 4 5
```

La hipótesis `codigo_actual` tiene que dar residuo ≈ 0. Mirar también la columna `% > 1%` (porcentaje de granos fuera de equilibrio): la mediana sola puede esconder un error que afecta a una fracción de los granos. Con la normal anterior, en una mezcla triángulo–disco la mediana daba 0.0001, pero el p90 de la asimetría era 0.72.

### Validación con atascos sintéticos de Box2D (2026-10-05)

Se compiló Box2D 2.4.2 (la versión del `Makefile`) y se generaron empaquetamientos en reposo de 300–600 granos dentro de una caja con un pozo (esquinas convexas y cóncavas, chain gID −100) y una "tapa" edge (gID −110). Se probaron discos, cuadrados, triángulos, pentágonos, hexágonos y mezclas, con fricción 0.2, 0.5 y 0.8 y varias semillas. Por cada contacto se guardó además la normal exacta de Box2D y por cada grano el tensor exacto calculado en C++. Se comparó con `calcular_tensor_y_presion_vectorizado`:

| | versión anterior | versión actual |
|---|---|---|
| normales con error > 1° | 0 en discos; en polígonos la mayoría de los contactos con vértice | **0** en ~25 000 contactos (todas las formas y las paredes) |
| granos con error de P o τ > 1 % (relativo a P) | 0 % en discos; **37–86 %** en mezclas con polígonos | **0 %** (error máximo ~1e-4, precisión float32 / 6 cifras del `.xy`) |
| residuo de equilibrio (`verificar_contactos.py`) | 1.9 (cuadrados), 3.1 (triángulos) | 0.0000 en todas |

Si el `.xy` no trae las paredes, los contactos pared–polígono vuelven a la aproximación del lado más cercano: entre 30 % y 50 % de esos contactos salen mal y afectan a un 3–7 % de los granos, los que tocan pared.

### Corregido: clasificación grande/chico (2026-10-05)

Antes se comparaba el **inradio** de los polígonos (`r_eff·cos(π/n)`) con el punto medio de `r_large`/`r_small` del índice, que son radios de igual área. Un triángulo grande equivalente a un disco de r = 0.5 tiene inradio ≈ 0.39; con un disco chico de r = 0.32 (ratio 0.4) el umbral es ≈ 0.41, y los triángulos grandes quedaban como `S`. Con un atasco sintético Tri–Disco de ratio 0.4 se confirmó: 151 de 151 triángulos mal clasificados. Ahora se usa la especie del `.xy` (`analysis/especies.py`), igual en `force_arch_v4.py`, que tenía otro umbral (punto medio de circunradios) y en Disco–Cuad ratio 0.8 clasificaba al revés los 300 de 300 granos. **Hay que recalcular las columnas por especie (`_B`/`_S`, BB/BS/SS) de las mezclas con polígonos.**

### Pendientes

1. **Guardar la normal en el simulador.** La reconstrucción de la sección 5.2 replica la lógica de Box2D 2.4.2 y fue validada, pero lo más robusto es que el binario del cluster escriba `worldManifold.normal` (2 columnas más) en `atasco_contacts_*.dat`. Si se agrega, actualizar la lectura de la línea 675 y usarla directamente.
2. **`simulation/src/save_tensors.cpp`** tiene el mismo signo tangencial invertido. Hoy no se llama desde ningún lado del simulador, pero si se vuelve a usar hay que corregirlo.
