# Auditoría — Cambios al pipeline de fuerzas de contacto

**Alcance:** los 5 archivos que compartiste (`force_arch_v3_contact.py`, `filtrar_datos.py`,
`graficar_fuerza.sh`, `graficar_todas_configuraciones.sh`, `preparar_datos_para_gnuplot.py`).
**No incluye:** el `.plt`/script de gnuplot real que consume `datos_combinados.csv` — no fue
compartido, así que para esa rama del pipeline solo puedo auditar hasta el CSV combinado.

Este documento es solo el plan. No modifiqué ningún código todavía.

---

## Resumen ejecutivo

| # | Cambio pedido | Archivos que cambian | ¿Requiere re-correr `force_arch_v3_contact.py`? | Riesgo/incertidumbre |
|---|---|---|---|---|
| 1 | Incorporar χ=0.0 | Ninguno necesariamente (verificar datos) | Solo si faltan simulaciones/índice | **Alto** — depende de `grain_json` y de si ya corriste las sims |
| 2 | No promediar/sumar los 2 puntos de contacto Box2D en polígono-polígono | Posiblemente ninguno (ya existe `--contact-mode point`) | **Sí** | **Alto** — hay que verificar el `.dat` crudo primero |
| 3 | Normalizar por M·g | `graficar_fuerza.sh`, `preparar_datos_para_gnuplot.py` (recomendado) | No (si se normaliza en el plot) | Bajo, pero es una decisión a confirmar |
| 4 | Barras de error σ/√N_contactos | `force_arch_v3_contact.py`, `graficar_fuerza.sh` | **Sí** | Medio — falta una columna y hay que agregar bien (pooling) |
| 5 | Descartar puntos con N < 5–10 | `force_arch_v3_contact.py` (recomendado) | **Sí** (mismo re-run que #4) | Medio — ambigüedad en qué "N" contar |

Los cambios #2, #4 y #5 tocan la misma función (`make_configuration_summary` / `calc_stats`) y
requieren el mismo re-procesamiento pesado, así que conviene implementarlos juntos y correr
**una sola vez** el análisis completo al final.

---

## 1. Incorporar χ = 0.0

### Qué es lo mínimo necesario
Si ya tenés las simulaciones de χ=0.0 corridas (carpetas `frames_*` + `atasco_contacts_*.dat`)
y están listadas en el CSV que le pasás a `--idx`, en principio **no hace falta tocar código**:

- `select_simulations()` no excluye χ=0 por defecto (`args.chi_values` es un filtro opcional).
- `iter_task_groups()` agrupa por `chi` igual que cualquier otro valor — χ=0.0 se convierte en
  su propio grupo sin problema.
- La detección de arco (`detectar_arco_primario`) es puramente geométrica, no depende de que
  haya partículas chicas.

### Riesgo real: `geometry_label` puede romperse en χ=0
En `summarize_fn_one_jam`, el umbral B/S se calcula así:

```python
umbral_r = (max_r + min_r) / 2.0
```

Si en χ=0 **todas** las partículas son del mismo radio (sin partículas chicas), `max_r == min_r`,
`umbral_r` coincide con ese radio único, y la condición `r >= umbral_r` clasifica a todo como
`'B'`. Esto **no rompe nada matemáticamente** (BS y SS quedan en `N=0` → `NaN`, correcto).

El problema real está en `get_geometry_label_from_row()` / `extract_sides()`:

```python
grains = sorted(grains, key=lambda g: float(g.get("radius", 0.0)), reverse=True)
names = [shape_name_from_sides(g.get("sides", -1)) for g in grains]
return names[0] if len(names) == 1 else "-".join(names)
```

**Si el `grain_json` de las simulaciones χ=0 solo declara la especie grande** (porque no hay
partículas chicas en absoluto), `geometry_label` daría `"Cuad"` en vez de `"Cuad-Disco"`. Como
`filtrar_datos.py` y `graficar_fuerza.sh` hacen **comparación exacta** (`== 'Cuad-Disco'`), esas
filas quedarían silenciosamente excluidas de todo el pipeline downstream, sin ningún error.

➡️ **Verificar antes de nada:** abrí el índice CSV y mirá el `grain_json` de una fila con χ=0.0.
Si declara ambas especies (aunque la chica tenga población 0), no hay problema. Si no las declara,
hay que decidir un fallback (usar `category`/`system_type`, o forzar el label manualmente).

### Riesgo en `preparar_datos_para_gnuplot.py`
Este script hace dos `merge(..., how='inner')` entre tres fuentes distintas:
`estadisticas_flujo_agregadas.csv`, `resultados_completos_arcos.csv` y las fuerzas filtradas.
Si χ=0.0 **no existe** en alguna de esas tres fuentes (por ejemplo, si el análisis de avalanchas
no corrió para χ=0, o directamente no aplica el concepto de "avalancha" sin partículas chicas),
el `inner join` la va a descartar **sin avisar**. Esto no lo puedo auditar porque esos dos CSV de
entrada no están entre los archivos compartidos — hay que revisarlos aparte.

### Qué re-ejecutar
- Nada de código nuevo si los datos ya existen y `geometry_label` sale bien.
- Si `geometry_label` sale mal: ajustar `get_geometry_label_from_row` (o el generador del índice)
  y volver a correr `force_arch_v3_contact.py` sobre las simulaciones afectadas.
- Revisar manualmente que χ=0.0 sobreviva el merge de `preparar_datos_para_gnuplot.py`.

---

## 2. Puntos de contacto Box2D en polígono-polígono: no promediar ni sumar

### Buena noticia: probablemente ya existe
El script **ya tiene** un modo pensado exactamente para esto:

```python
parser.add_argument("--contact-mode", choices=["pair", "point"], default="pair")
```

- **`pair`** (el default actual): en `prepare_force_dataset`, agrupa por `(id_a, id_b)` y hace
  `f_norm.sum()` — si Box2D reportó 2 puntos de manifold para un contacto cara-a-cara
  polígono-polígono, se suman en una sola fila. Esto es justo lo que querés dejar de hacer.
- **`point`**: no agrupa nada — cada punto de manifold queda como su propia fila, con su propio
  `f_norm`/`f_tan`/posición. Esto trata cada punto como una muestra independiente, que es
  literalmente lo que describiste ("no se promedie el contacto ni se sume la fuerza").

Como disco-disco y disco-polígono normalmente solo tienen **un** punto de contacto (no hay
geometría de "cara contra cara" posible con un círculo), pasar a `--contact-mode point` **de
forma global** no les cambia nada — el cambio de comportamiento queda naturalmente concentrado en
los contactos BB (polígono-polígono) que sí pueden tener manifold de 2 puntos. No hace falta
lógica condicional por tipo de contacto: alcanza con el flag existente.

### Lo que sí cambia (y hay que documentar)
- **`aggregate_contacts_for_graph`** (usada solo para el grafo de detección de arco) sigue
  agregando siempre por par — está bien así, porque la topología del grafo necesita **una** arista
  por par de partículas, no depende de `contact_mode`. No tocar.
- El significado de `N_contactos_{región}_{tipo}` deja de ser "número de pares en contacto" y pasa
  a ser "número de puntos de contacto". Para BB puede casi duplicarse en los jams con contactos
  cara-a-cara; para BS/SS no cambia. Esto afecta directamente al filtro de N mínimo (#5) y a los
  denominadores de las barras de error (#4) — hay que tenerlo en cuenta al elegir el umbral.

### Lo único que necesito para confirmar esto
**No puedo verificar sin ver el `.dat` crudo** si `atasco_contacts_*.dat` realmente contiene una
fila por punto de manifold (hasta 2 para cara-a-cara), o si el lado C++ ya los pre-suma antes de
escribir el archivo. Si ya vienen pre-sumados en el `.dat`, entonces `--contact-mode point` no
cambiaría nada (no hay nada que desagregar) y el fix tendría que hacerse en el escritor C++, fuera
del alcance de estos 5 archivos.

➡️ **Verificar:** `grep` un par de IDs conocido como polígono-polígono en un `atasco_contacts_*.dat`
y confirmar si aparece en 1 o 2 líneas.

### Qué re-ejecutar
- Si se confirma que el `.dat` trae 2 filas por contacto cara-a-cara: correr
  `force_arch_v3_contact.py` con `--contact-mode point` en vez de `pair` (re-run completo, ya que
  cambia los números a nivel atasco).
- Si no: el fix va en el código C++/Box2D, no en Python.

---

## 3. Normalizar por M·g

M = 1 kg (partícula grande), g = 9.8 m/s² → constante de normalización **Mg = 9.8 N**.

### Dónde aplicar la división — decisión a confirmar
Dividir por una constante es una operación lineal: conmuta con media, suma, y con std/SEM
(`std(cX) = c·std(X)`, `sem(cX) = c·sem(X)`). Esto significa que **matemáticamente da lo mismo**
normalizar en el análisis pesado (`force_arch_v3_contact.py`) o al momento de graficar. La
diferencia es de diseño:

| Opción | Ventaja | Desventaja |
|---|---|---|
| **Normalizar en `force_arch_v3_contact.py`** (baked-in) | Un solo lugar, no hay riesgo de que un script de graficado se olvide de dividir | Los CSV crudos pierden las unidades físicas originales; si cambia M o g hay que re-correr el análisis pesado de nuevo |
| **Normalizar al graficar** (recomendado) | Los CSV quedan en unidades físicas reutilizables; cambiar M/g no requiere re-analizar, solo re-graficar | Hay que aplicar la constante en **dos lugares** (`graficar_fuerza.sh` y `preparar_datos_para_gnuplot.py`), con riesgo de desincronización |

**Mi recomendación:** normalizar al graficar, pero definir la constante `MG = 9.8` una sola vez y
reutilizarla igual en ambos scripts (aunque estén en lenguajes/procesos distintos, mantenerla como
un comentario/constante bien visible en la cabecera de cada uno). Como de todas formas vamos a
re-correr el análisis pesado por los cambios #2/#4/#5, si preferís bakearlo directamente en el CSV
también es viable sin costo extra — decisión tuya, avisame cuál preferís antes de implementar.

### Qué cambia en la práctica (si se normaliza al graficar)
En `graficar_fuerza.sh`: dividir `arch_bb, arch_bs, arch_ss, arch_total, roi_bb, roi_bs, roi_ss,
roi_total` (y sus `yerr` una vez agregadas las barras de error, ver #4) por `MG` antes de graficar.
En `preparar_datos_para_gnuplot.py`: dividir las columnas de `columnas_fuerzas` al extraerlas.

### Qué re-ejecutar
- Ninguna re-ejecución del análisis pesado si se hace al graficar — solo volver a correr los
  scripts de plotting.
- Si se decide bakear en el análisis: se incluye en el mismo re-run que #2/#4/#5.

---

## 4. Barras de error: σ/√N_contactos

Este es el cambio más profundo. Hay que entender primero qué existe hoy.

### Lo que ya existe (y es confuso)
Hoy hay **dos columnas distintas llamadas `sem_Fn_roi`** con significados diferentes:

1. **A nivel atasco** (`calc_stats`, solo para `prefix == 'roi'`): `std(fn)/√N_contactos_roi`
   calculado **dentro de un único atasco**. Esto no se calcula para `bulk` ni `arco`.
2. **A nivel configuración** (`make_configuration_summary`): `sem_from_series` aplicado sobre la
   columna `mean_Fn_roi` (una fila por atasco) — es decir, el error estándar **entre atascos** de
   sus promedios, no el error estándar de los contactos individuales.

Estas dos cosas miden fuentes de variabilidad distintas (contacto-a-contacto dentro de un jam, vs.
jam-a-jam) y hoy comparten nombre de columna, lo cual es confuso. Lo que pediste —
`σ/√N_contactos`— es la **primera** noción, pero aplicada a **toda la configuración** (todos los
atascos juntos), no a un solo atasco ni "promediada ingenuamente entre atascos".

### Lo que falta para calcularlo bien
Para region completa (`bulk`/`arco`/`roi`) ya existe todo lo necesario por atasco:
`N_contactos_{prefix}`, `mean_Fn_{prefix}`, `std_Fn_{prefix}`. **Para el desglose por tipo
(BB/BS/SS) falta el std** — hoy `calc_stats` guarda `N_contactos_{prefix}_{tipo}` y
`mean_Fn_{prefix}_{tipo}`, pero **no** `std_Fn_{prefix}_{tipo}`. Sin eso no se puede calcular un
SEM correcto para las curvas BB/BS/SS.

➡️ **Cambio de código necesario en `calc_stats`:** agregar

```python
d[f"std_Fn_{prefix}_{tipo}"] = std_or_nan(fn_tipo)
```

dentro del loop de tipos. Esto obliga a re-correr `force_arch_v3_contact.py` completo, porque es
un dato que no está guardado hoy en `resumen_fuerza_normal_por_atasco.csv`.

### Cómo combinar (pooling) correctamente entre atascos
No alcanza con promediar los `std_Fn` de cada atasco. Para combinar k grupos (atascos), cada uno
con `n_i` contactos, media `m_i` y desvío `s_i` (con ddof=1), el pooling exacto es:

```
N = Σ n_i
M = Σ(n_i · m_i) / N                                    # media combinada

SS_i = (n_i - 1) · s_i²     (tratar como 0 si n_i ≤ 1, NO como 0·NaN)
SS_total = Σ SS_i + Σ n_i·(m_i - M)²

var_pooled = SS_total / (N - 1)
std_pooled = √var_pooled
SEM_pooled = std_pooled / √N
```

Esto es exacto (no una aproximación) porque los `(n_i, m_i, s_i)` de cada atasco ya son exactos.
Se calcula una vez por región (`bulk`/`arco`/`roi`) y una vez por cada tipo (`BB`/`BS`/`SS`),
usando solo los atascos donde `n_i > 0` para ese tipo.

### Propuesta de columnas nuevas en `resumen_fuerza_normal_por_configuracion.csv`
- `N_contactos_total_{región}[_{tipo}]` — la N pooled (Σ n_i), reusable también para el filtro #5.
- `sem_pooled_Fn_{región}[_{tipo}]` — el SEM pedido, σ_pooled/√N.
- Mantener el SEM "entre atascos" que ya existe, pero **renombrarlo** a algo inequívoco como
  `sem_between_jams_Fn_{región}` para dejar de pisar el nombre con el nuevo. Ningún script de
  graficado usa hoy la columna `sem_Fn_*`, así que renombrarla no rompe nada existente.

### Cambios en `graficar_fuerza.sh`
- Reemplazar los `ax.plot(...)` de las 8 curvas por `ax.errorbar(chi, y, yerr=sem_pooled/MG, ...)`
  (con `capsize`, etc.).
- Ajustar el cálculo de `max_y_global` para considerar `y + yerr`, no solo `y`, para que el margen
  del 45% no termine cortando la punta de la barra de error.
- Ojo con `df_sub.groupby("chi").mean(numeric_only=True)`: si llegan a caer **varias filas reales**
  bajo el mismo χ (por el `atol=0.03` de `area_ratio_nominal`), promediar los SEM con un `.mean()`
  simple ya no es válido — habría que aplicar el mismo pooling ahí también. Si en la práctica cada
  χ tiene una sola fila tras el filtro, esto no es un problema real; si no, hay que revisarlo.

### Qué re-ejecutar
- `force_arch_v3_contact.py` completo (por el nuevo `std_Fn_{prefix}_{tipo}` y el pooling en
  `make_configuration_summary`).
- `filtrar_datos.py` (regenera los CSV filtrados con las columnas nuevas).
- `graficar_fuerza.sh` / `graficar_todas_configuraciones.sh`.

---

## 5. Descartar puntos con menos de 5–10 datos

### Ambigüedad a resolver
"Datos" podría referirse a:
- **`N_contactos`** (pooled, por región/tipo) — lo más coherente con que lo pediste junto al punto
  de las barras de error.
- **`n_atascos`** o **`n_simulaciones`** (ya existen como columnas) — número de jams/simulaciones
  que aportan a ese punto de χ.

**Propongo aplicar el filtro sobre `N_contactos_total_{región}_{tipo}`** (el mismo pooled N del
punto #4), por default `min = 10` (configurable). Si también querés un piso de `n_atascos` (para
evitar que un punto dependa de un solo jam aunque tenga muchos contactos), decime y lo agrego como
filtro adicional independiente.

### Dónde aplicar el filtro
Recomiendo hacerlo **una sola vez**, en `make_configuration_summary` (agregar un argumento
`--min-n-contactos`, default 10), en vez de repetirlo en cada script de graficado. Importante: el
filtro debe ser **por columna** (por combinación región×tipo), no por fila completa — una
configuración puede tener `N_contactos_bulk_BB` de sobra pero `N_contactos_arco_SS` insuficiente;
descartar la fila entera tiraría datos válidos. La implementación pone `NaN` en `mean_Fn`, `std_Fn`
y `sem_pooled_Fn` de esa combinación específica cuando su N pooled cae debajo del umbral, dejando
intactas las demás columnas de la fila. Tanto matplotlib como gnuplot ya saltean `NaN` al graficar
líneas, así que el punto simplemente no aparece (con un corte visible en la curva).

### Qué re-ejecutar
- Mismo re-run que #4 (es la misma función). No hay pasos adicionales.

---

## Plan de re-ejecución (orden recomendado)

1. **Verificar antes de programar nada:**
   - `grain_json` de una simulación χ=0.0 → confirmar que `geometry_label` sale bien.
   - Un `atasco_contacts_*.dat` con un par polígono-polígono conocido → confirmar 1 vs 2 filas.
   - Que χ=0.0 exista en `estadisticas_flujo_agregadas.csv` y `resultados_completos_arcos.csv`
     (si vas a usar el pipeline de gnuplot).
2. Implementar en `force_arch_v3_contact.py`:
   - `std_Fn_{prefix}_{tipo}` en `calc_stats`.
   - Función de pooling (N, mean, std) → `sem_pooled_Fn_*`, `N_contactos_total_*`.
   - Renombrar el SEM actual a `sem_between_jams_Fn_*`.
   - Filtro `--min-n-contactos` en `make_configuration_summary`.
   - (Opcional, a confirmar) normalización Mg baked-in.
3. Re-correr `force_arch_v3_contact.py --overwrite` con `--contact-mode point` (si se confirma en
   el paso 1) sobre el índice completo, incluyendo χ=0.0.
4. Re-correr `filtrar_datos.py`.
5. Actualizar y re-correr `graficar_fuerza.sh` (Mg, `errorbar`, ajuste de `max_y_global`).
6. Re-correr `graficar_todas_configuraciones.sh` (sin cambios propios, pero regenera todo).
7. Actualizar y re-correr `preparar_datos_para_gnuplot.py` (Mg, columnas BS faltantes si aplica,
   columnas de error si el gnuplot final las va a usar).
8. Pendiente: revisar el `.plt`/script real de gnuplot (no compartido) para sumar barras de error
   y normalización ahí también.

---

## Preguntas abiertas / a confirmar antes de implementar

1. ¿Ya corriste las simulaciones Box2D para χ=0.0, o hay que generarlas primero? (fuera del
   alcance de estos 5 archivos)
2. ¿Confirmás que `atasco_contacts_*.dat` trae 2 filas para contactos cara-a-cara polígono-polígono,
   o los pre-suma el lado C++?
3. Normalización Mg: ¿bakeada en el CSV de análisis, o aplicada solo al graficar (mi recomendación)?
4. Filtro de N mínimo: ¿solo sobre `N_contactos` pooled, o también un piso de `n_atascos`?
5. ¿Umbral 5 o 10? (lo dejo como argumento configurable, pero necesito un default)
6. Para el pipeline de gnuplot: ¿me podés pasar el `.plt`/script real que lee `datos_combinados.csv`
   para poder auditar los cambios de barras de error/normalización ahí también?
7. `preparar_datos_para_gnuplot.py` solo extrae `BB` y `SS` de fuerzas (falta `BS`) — ¿fue a
   propósito o hay que agregarla también?