# Tensor de esfuerzos, presión y deviador: el código comparado con el material de clase

Este documento compara el cálculo de `presion_tensor_arch.py` con las clases de
**L. A. Pugnaloni, "Descripción del estado tensional de empaquetamientos
granulares"** (Física y Aplicaciones de la Materia Granular, UNLPam, 2022) y
**M. Carlevaro, "Descripción estructural de empaquetamientos granulares"**
(Introducción a la Física de los Materiales Granulares, UTN FRLP, 2025).

La guía línea por línea del código está en `README_tensor_deviador.md`. Los
números de línea de abajo corresponden a `presion_tensor_arch.py` en este
mismo directorio (si el script cambia, actualizarlos).

**Resumen:** el tensor de cada grano es la fórmula de **Born–Huang** de las
clases (diap. 24) tomando como volumen el área del grano; la presión y el
deviador son el **centro** y el **radio del círculo de Mohr** (diap. 14–16); y
la simetría del tensor es la condición de **equilibrio de rotación** (diap.
11–12), verificada con datos. Las diferencias están en cómo se promedia por
región (sección 5).

---

## 1. El tensor: Born–Huang con el volumen de un grano

### En las clases (Pugnaloni, diap. 21–24)

Partiendo de la conservación de la masa y del momento, con una función de
suavizado $\phi(\mathbf R) = 1/V$ dentro del volumen $V$ y $0$ afuera, se
obtiene la fórmula de Born–Huang:

$$
\sigma_{\alpha\beta} = \frac{1}{2V}\sum_{i}\sum_{j} f_{ij\alpha}\, b_{ij\beta}
\;-\; \frac{1}{V}\sum_i m_i\, v_{i\alpha}\, v_{i\beta}
$$

con $f_{ij}$ la fuerza que $j$ ejerce sobre $i$ y $b_{ij}$ el vector rama
("branch vector"), del que solo cuenta **la porción dentro de $V$**.

### En el código (`calcular_tensor_y_presion_vectorizado()`, líneas 446–552)

Para cada grano $p$, sumando sobre sus contactos $c$:

$$
\sigma^{(p)}_{ij} = -\frac{1}{A_p}\sum_{c\,\in\,p} (x^c - x^p)_i\, f^c_j
$$

| Código | Líneas | Qué hace |
|---|---|---|
| `fuerzas_contacto()` | 423–444 | Fuerza de cada contacto sobre A: `F_A = (−fn·n̂ + ft·t̂)/dt` (línea 439). Sobre B: `−F_A`. |
| `S_ij = Σ r_i F_j` | 461–464 | `r = punto de contacto − centro del grano`. Sobre A con `F_A`, sobre B con `−F_A`; la pared no suma. |
| `σ = −S/área` | 487–489 | Signo menos: compresión positiva. |

### Por qué es lo mismo

1. **Término cinético.** En un atasco las velocidades son ≈ 0: el segundo
   término se anula. El código no lo incluye.
2. **Vector rama repartido en el punto de contacto.** Para dos granos $i$, $j$
   que se tocan en $\mathbf x_c$:
   $\mathbf b_{ij} = \mathbf x_i - \mathbf x_j = (\mathbf x_c - \mathbf x_j) - (\mathbf x_c - \mathbf x_i)$.
   Cada grano se queda con el tramo que va de su centro al punto de contacto,
   que es exactamente "la porción de $b_{ij}$ dentro de $V$" cuando $V$ es el
   grano.
3. **Sumando todos los granos de una región**, cada contacto interno aporta
   $(\mathbf x_c-\mathbf x_i)\otimes \mathbf f_{ij} + (\mathbf x_c-\mathbf x_j)\otimes(-\mathbf f_{ij})
   = -\,\mathbf b_{ij}\otimes \mathbf f_{ij}$, y con el signo menos del código:
   $$\sum_p A_p\,\sigma^{(p)} = \sum_{\rm contactos} \mathbf b_{ij}\otimes \mathbf f_{ij},$$
   que es Born–Huang (el $\tfrac12$ de la diap. 24 compensa que la doble suma
   cuenta cada par dos veces).
4. **Signo.** Con $\mathbf b_{ij}=\mathbf x_i-\mathbf x_j$ y una fuerza
   repulsiva, Born–Huang da compresión positiva. El código usa la misma
   convención (la de Nedderman y de las diap. 17–18, donde $\sigma_{yy}=W/S$).
5. **Orden de los índices.** Las clases escriben $f_\alpha b_\beta$ y el código
   $r_i F_j$: es el tensor transpuesto. No cambia nada porque la parte
   simétrica es la misma y la antisimétrica es ≈ 0 (sección 2).
6. **Gravedad.** No hace falta corrección: el peso actúa en el centro de masa y
   el código usa ese punto como centro (en polígonos regulares el promedio de
   vértices, línea 55, coincide con el centroide).

---

## 2. Simetría del tensor = equilibrio de rotación

### En las clases (Pugnaloni, diap. 11–12)

Si un cuerpo no tiene aceleración angular, el torque neto se anula y de ahí
$\sigma_{12} = \sigma_{21}$.

### En el código

Para un grano, $S_{01} - S_{10} = \sum_c (r_x F_y - r_y F_x)$ es su **torque
neto**. En equilibrio estático vale 0, así que el tensor tiene que salir
simétrico. El código lo simetriza (línea 489, $\sigma_{xy} = -\tfrac12(S_{01}+S_{10})/A$),
pero **no lo da por supuesto**: se verifica con datos.

| Verificación (`analysis/utils/verificar_contactos.py`) | Resultado |
|---|---|
| Torque neto relativo $\lvert S_{01}-S_{10}\rvert/\lvert S\rvert$, discos | mediana 0.0000, percentil 90 0.0000 |
| Ídem, cuadrados (cuadrado–disco, $R_{\rm a}=0.1$, $\chi=0.2$, atascos 1–5) | mediana 0.0000, percentil 90 **0.0004** |
| Ídem, cuadrados con la normal anterior | percentil 90 **0.68** (error corregido en la normal de contacto) |
| Equilibrio de fuerzas $\lvert\sum F - mg\rvert/(mg)$ | 0.0003 (discos), 0.0008 (polígonos) |

Que el torque dé ≈ 0 confirma que las normales, el signo de la fuerza
tangencial y los puntos de contacto están bien: es la misma condición física
de la diapositiva 12.

---

## 3. Presión y deviador = círculo de Mohr

### En las clases (Pugnaloni, diap. 13–16)

- El tensor se descompone en una parte hidrostática y un **deviador**:
  $\sigma_{ij} = \tfrac13\,{\rm Tr}(\sigma)\,\delta_{ij} + s_{ij}$ (3D, diap. 13).
- En 2D, con esfuerzos principales $\sigma_1 > \sigma_2$, el círculo de Mohr
  tiene **centro** $(\sigma_1+\sigma_2)/2$ y **radio** $(\sigma_1-\sigma_2)/2$
  (diap. 16). Los puntos $(\sigma_{xx}, \sigma_{xy})$ y $(\sigma_{yy}, -\sigma_{xy})$
  están sobre el círculo.

### En el código

| Magnitud | Fórmula | Línea | Relación con las clases |
|---|---|---|---|
| Presión | $P = \tfrac12(\sigma_{xx}+\sigma_{yy})$ | 475 | Centro del círculo. En 2D la traza se divide por 2 (no por 3 como en la diap. 13, que es 3D). |
| Deviador | $\tau = \sqrt{\left(\tfrac{\sigma_{xx}-\sigma_{yy}}{2}\right)^2 + \sigma_{xy}^2}$ | 492 | Radio del círculo: la distancia entre los dos puntos de la diap. 16 dividida por 2. |
| Esfuerzos principales | $\sigma_{1,2} = P \pm \tau$ | — | Extremos del círculo. |

**Relación con el tensor deviador.** En 2D, $s = \sigma - P\,\mathbb I$ tiene
autovalores $\pm\tau$: $\tau$ es la magnitud del deviador. Otros trabajos usan
$q = \sigma_1 - \sigma_2 = 2\tau$ o $\sqrt{s:s} = \sqrt2\,\tau$; conviene
aclarar en el paper cuál se usa.

**Invariancia.** $P$ y $\tau$ no dependen de los ejes (son el centro y el radio
del círculo). Verificado con `verificar_tensor.py`: girando un atasco real o un
conjunto aleatorio de granos, $P$ y $\tau$ no cambian y $\sigma$ rota como
$R\,\sigma R^{T}$.

**Ejemplos de la diap. 16.** Con $\mathbf n=(1,0)$, $\tau_n = \sigma_{xy}$; con
$\mathbf n=(0,1)$, $\tau_n = -\sigma_{xy}$. Coincide con los casos de
`verificar_tensor.py --sintetico`: un disco comprimido a lo largo de la
diagonal $y=x$ da $\sigma_{xy}>0$, y a lo largo de $y=-x$, $\sigma_{xy}<0$.

---

## 4. Mohr–Coulomb y Janssen (Pugnaloni, diap. 17–19)

- **Mohr–Coulomb (diap. 17–18).** El material desliza cuando el círculo toca
  la recta de fricción: $\tau/P = \sin\phi$, con $\mu = \tan\phi$. Con la
  fricción de los granos ($\mu = 0.5$), $\sin(\arctan 0.5) \approx 0.45$.
  Ojo: el $\tau/P$ **de un grano** (~0.7–0.8 en los datos) no es la fricción
  movilizada del material. Para compararlo con Mohr–Coulomb hay que usar el
  tensor promedio de la región (sección 5).
- **Janssen (diap. 19).** Las paredes sostienen parte del peso por fricción
  ($\sigma_{rz} = \mu_s\sigma_{rr}$ en la pared). En 2D eso da $\sigma_{xy}>0$
  junto a la pared izquierda y $<0$ junto a la derecha, con
  $\lvert\sigma_{xy}\rvert/\sigma_{xx} \le \mu_{\rm pared}$.
  `verificar_tensor.py --parquet` lo chequea con los datos (espejo
  izquierda–derecha y signo junto a las paredes).

---

## 5. Diferencias con las clases: cómo se promedia por región

El cálculo por grano coincide con las clases. Lo que hay que tener en cuenta
al **interpretar los promedios** de `resumen_por_configuracion()`
(líneas 874–903):

1. **Normalización por área.** Born–Huang divide por el área **de la región**,
   incluidos los huecos. El código promedia pesando por el área **de los
   granos**: `mean_P = Σ P_p A_p / Σ A_p`. Por eso
   `mean_P` = $P_{\rm Born–Huang}/\phi$, con $\phi$ la fracción de
   empaquetamiento (≈ 0.8, o sea ~20 % más alto). Para comparar con teoría
   (Janssen, por ejemplo), multiplicar por $\phi$.
2. **`mean_tau` no es el radio de Mohr de la región.** Es el promedio de los
   $\tau$ de cada grano, y cada grano tiene sus ejes principales orientados
   distinto, así que $\langle\tau_p\rangle \ge \tau(\langle\sigma\rangle)$.
   Sirve para comparar configuraciones entre sí. Para el deviador del
   material (y para Mohr–Coulomb) primero hay que promediar
   $\sigma_{xx}$, $\sigma_{yy}$ y $\sigma_{xy}$ por área (columnas
   `sigma_*_reducida` del parquet por partícula) y después aplicar la fórmula
   de la línea 492. `estres_arco_vs_roi.py` lo hace (columnas `P_m` y `tau_m`).
3. **Por grano, $\tau$ puede ser mayor que $P$** (~8 % de los granos). No es
   un error: un contacto con fricción genera en el tensor del grano un esfuerzo
   principal levemente negativo, y en granos con pocos contactos y mucha
   fricción movilizada $\tau$ supera a $P$.

---

## 6. Tensor de trama (Carlevaro, "Descripción estructural", diap. 14)

La clase de Carlevaro no trata el tensor de esfuerzos, pero define el
**tensor de trama** (*fabric tensor*):

$$
F = \sum_{\rm contactos} \hat n^c \otimes \hat n^c, \qquad {\rm Tr}(F) = N_c ,
$$

que tiene la misma estructura que el de esfuerzos pero solo con las
**direcciones** de los contactos, sin fuerzas ni brazos. También se descompone
en parte isótropa y deviador ($F = F_{\rm I} + F_{\rm D}$). El código no lo
calcula hoy; con las normales que ya obtiene `normales_contacto()`
(línea 357) sería directo, y permitiría comparar la anisotropía geométrica de
los contactos (deviador de $F$) con la de los esfuerzos ($\tau/P$).

---

## 7. Cómo repetir las verificaciones

```bash
# equilibrio de fuerzas, simetría del tensor (torque), P<0 y tau/P por tipo de grano
python analysis/utils/verificar_contactos.py --sim_path <carpeta_simulacion> --jam_id 1 2 3 4 5

# casos con resultado conocido, rotación de un atasco real y chequeo físico con los datos
python analysis/utils/verificar_tensor.py --sintetico
python analysis/utils/verificar_tensor.py --sim_path <carpeta_simulacion> --jam_id 1 2
python analysis/utils/verificar_tensor.py --parquet <out>/presion_por_particula_Disco.parquet --incluir '<config>'
```
