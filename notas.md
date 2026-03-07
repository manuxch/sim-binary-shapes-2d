# Apuntes Técnicos: Justificación del Mínimo de Avalancha

## 1. El Fenómeno: Curva en "U" del flujo
Se observa que al agregar pequeñas fracciones de aditivo ($\chi$ entre 0.01 y 0.04), el tamaño medio de avalancha ($S$) disminuye hasta un valor mínimo (punto de mayor atascamiento), para luego crecer sistemáticamente a mayores concentraciones.

## 2. Justificación del Mínimo (Régimen de Refuerzo)
En este régimen, el aditivo actúa como un **agente de estabilidad**.

* **Mecánica de Encastre:** A bajas concentraciones, las partículas chicas no forman una fase continua. Se alojan en los intersticios (poros) de las partículas grandes. En simulaciones 2D estáticas, esto aumenta el número de contactos por partícula y restringe las rotaciones.
* **Ángulos de contacto:** Aunque se introduzcan ángulos de contacto $> 180^\circ$ (puntos de falla teórica), la ausencia de vibración externa y la presión de la columna de granos permiten que estos contactos se bloqueen por fricción. La "falla" geométrica funciona como una traba mecánica.
* **Sustento con Datos (Figura C y Tabla):** * El sistema **Cuadrado-Cuadrado** muestra un $\epsilon \approx 2.74$ en $\chi = 0.02$.
    * Este valor de $\epsilon > 1$ confirma un **secuestro estructural**: el arco incorpora más aditivo del que hay en el resto del silo porque esas partículas chicas estabilizan la estructura.
    * Al ser arcos más estables, alcanzan el criterio de 5 segundos más rápido, resultando en avalanchas $S$ más cortas.



## 3. Justificación del Crecimiento (Régimen de Lubricación)
A partir de $\chi \approx 0.05$, el rol del aditivo cambia de "refuerzo" a "separador".

* **Efecto de Dilución:** El exceso de partículas chicas separa a las partículas grandes entre sí. Se pierde el contacto "Grande-Grande" (el más estable por superficie de fricción).
* **Inestabilidad Dominante:** Aquí la inestabilidad por ángulos $> 180^\circ$ se vuelve masiva. El arco ya no está formado por partículas grandes reforzadas, sino por una mezcla donde las partículas chicas (con menor masa y estabilidad) dominan la red de fuerzas.
* **Sustento con Datos (Figura B):** * La curva de $f_{real}$ se satura y $\epsilon$ cae hacia 1.0. 
    * El arco pierde su "capacidad de selección" y la estructura se vuelve más dinámica (inestable).
    * Los arcos colapsan antes de llegar a los 5 segundos, incrementando el valor medio de $S$.

## 4. Influencia de la Forma (Desplazamiento del Mínimo)
La geometría de las partículas determina la profundidad y la posición de este mínimo en el eje $\chi$.

* **Aditivos con caras planas (Cuadrados):** Maximizan el interlocking. Generan un $\epsilon$ alto ($\approx 2.8$) y un mínimo de flujo muy profundo porque el encastre es muy eficiente incluso con pocos aditivos.
* **Aditivos circulares (Discos):** No ofrecen caras planas para el encastre. Su $\epsilon$ es bajo ($\approx 0.8$ en el caso Disco-Disco), lo que indica que son excluidos del arco. Al no haber refuerzo estructural, el mínimo de flujo es mucho menos pronunciado o inexistente.
* **Caso Crítico (Disco-Triángulo):** Con un $\epsilon \approx 0.16$, los triángulos son expulsados casi totalmente del arco. Al no participar de la estructura, no hay refuerzo y el sistema fluye libremente sin mostrar un mínimo claro.



## 5. Validación Estadística (Figura H)
* Al observar la **PDF de avalanchas** en el punto del mínimo ($\chi = 0.02$), se debe verificar que el pico de la distribución se desplaza hacia valores de $S$ menores y que la "cola" de la distribución (eventos largos) desaparece en comparación con el sistema puro ($\chi = 0$).