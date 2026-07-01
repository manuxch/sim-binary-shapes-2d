
# Documentación: Cálculo del Tensor de Tensiones y Presión Granular


---

## 1. El Tensor de Tensiones desde las Fuerzas de Contacto

El tensor de tensiones continuo $\sigma_{\alpha\beta}$ en un volumen $V$ (o área $A$, en 2D) se obtiene a partir de los esfuerzos microscópicos. En un sistema cuasiestático donde el material se encuentra estructurado, la ecuación es:

$$\sigma_{\alpha\beta} \approx \frac{1}{2V} \sum_{i=1}^{N} \sum_{j=1}^{N} f_{ij\alpha} r_{ij\beta}$$

Donde $f_{ij\alpha}$ es la componente $\alpha$ de la fuerza y $r_{ij\beta}$ es la componente $\beta$ del "branch vector" (vector rama).

---

## 2. Geometría del Contacto: Vectores Normales y Tangenciales

El código determina el vector normal unitario $\hat{n} = (n_x, n_y)$ que apunta desde el centro de la partícula hacia el punto de contacto. La lógica varía según la forma geométrica de la partícula. El vector tangencial $\hat{t} = (t_x, t_y)$ se obtiene rotando la normal $90^\circ$.

**Expresión matemática:**
Para discos:
$$n_x = \frac{p_x - X_i}{|| \vec{r} ||}, \quad n_y = \frac{p_y - Y_i}{|| \vec{r} ||}$$

Para el plano tangencial:
$$t_x = -n_y, \quad t_y = n_x$$

**Implementación en código:**
```python
# Cálculo vectorial para Discos
nx_disk = df.loc[mask_disk, 'px'] - df.loc[mask_disk, 'pos_x_A']
ny_disk = df.loc[mask_disk, 'py'] - df.loc[mask_disk, 'pos_y_A']
norma = np.hypot(nx_disk, ny_disk)

df.loc[mask_disk, 'nx_v'] = np.where(valid, nx_disk / norma, 0.0).astype(np.float32)
df.loc[mask_disk, 'ny_v'] = np.where(valid, ny_disk / norma, 0.0).astype(np.float32)

# Vector tangencial (perpendicular a la normal)
df['tx_v'] = -df['ny_v']
df['ty_v'] = df['nx_v']

```

> **Nota:** Para los polígonos, el código utiliza la función `obtener_vector_normal_poly` que proyecta el punto de contacto sobre la arista más cercana para encontrar la normal real de la cara plana.

---

## 3. Descomposición de Fuerzas y Tasa de Impulso

El solver de simulación entrega impulsos (fuerzas integradas en el tiempo). El paso consiste en transformar estos impulsos normales ($f_{\text{norm}}$) y tangenciales ($f_{\text{tan}}$) en fuerzas medias cartesianas $F_x$ y $F_y$ ejercidas sobre la partícula $A$. El signo negativo asume que la fuerza normal entrante empuja a la partícula.

**Expresión matemática:**

$$F_{x} = \frac{-(f_{\text{norm}} n_x + f_{\text{tan}} t_x)}{\Delta t}$$

$$F_{y} = \frac{-(f_{\text{norm}} n_y + f_{\text{tan}} t_y)}{\Delta t}$$

**Implementación en código:**

```python
df['Fx_A'] = ((-df['f_norm'] * df['nx_v'] - df['f_tan'] * df['tx_v']) / dt).astype(np.float32)
df['Fy_A'] = ((-df['f_norm'] * df['ny_v'] - df['f_tan'] * df['ty_v']) / dt).astype(np.float32)

```

---

## 4. El Brazo de Palanca (Vector Rama) y Tercera Ley de Newton

Para el tensor virial, necesitamos el vector desde el centro de masa de la partícula $(X_i, Y_i)$ hasta el punto de contacto $(p_x, p_y)$.

**Expresión matemática:**

$$r_{x} = p_x - X_i$$

$$r_{y} = p_y - Y_i$$

La fuerza sobre la partícula B es igual y opuesta a la fuerza sobre A (Tercera Ley de Newton): $\vec{F}_B = -\vec{F}_A$.

---

## 5. Tensor de Tensiones (Por Contacto)

Se calculan las componentes de la diagonal principal del tensor (esfuerzos normales $S_{xx}$ y $S_{yy}$) generadas por un contacto individual, equivalente al producto $f_{ij\alpha} r_{ij\beta}$.

**Expresión matemática para la partícula A y B:**

$$S_{xx}^{(A)} = F_x^{(A)} (p_x - X_A)$$

$$S_{xx}^{(B)} = -F_x^{(A)} (p_x - X_B)$$

**Implementación en código:**

```python
# Contribución al tensor de la partícula A
df['S00_A'] = (df['Fx_A'] * (df['px'] - df['pos_x_A'])).astype(np.float32)
df['S11_A'] = (df['Fy_A'] * (df['py'] - df['pos_y_A'])).astype(np.float32)

# Contribución al tensor de la partícula B (Fuerza invertida)
df['S00_B'] = (-df['Fx_A'] * (df['px'] - df['pos_x_B'])).astype(np.float32)
df['S11_B'] = (-df['Fy_A'] * (df['py'] - df['pos_y_B'])).astype(np.float32)

```

---

## 6. Consolidación del Tensor por Partícula

El esfuerzo total sobre una partícula es la suma de las contribuciones de todos sus contactos $N_c$. Se agrupa por el ID de la partícula.

**Expresión matemática:**

$$S_{xx}^{(i)} = \sum_{c=1}^{N_c} F_{c,x} (p_{c,x} - X_i)$$

**Implementación en código:**

```python
tensor_A = df.groupby('id_a')[['S00_A', 'S11_A']].sum().rename(columns={'S00_A':'S00', 'S11_A':'S11'})
tensor_B = df.groupby('id_b')[['S00_B', 'S11_B']].sum().rename(columns={'S00_B':'S00', 'S11_B':'S11'})

# Se suman las contribuciones actuando como partícula 'a' y como partícula 'b'
tensor_total = tensor_A.add(tensor_B, fill_value=0)

```

---

## 7. Cálculo de la Presión Escalar Individual

La presión hidrostática (o presión media 2D) $P$ se define como la traza del tensor virial normalizada por el área $A$ de la partícula, cambiando el signo para que la compresión sea positiva.

**Expresión matemática:**

$$P = -\frac{1}{2 A} (S_{xx} + S_{yy})$$

**Implementación en código:**

```python
# Se une el tensor total al DataFrame de partículas y se calcula P
p_df = df_particles.join(tensor_total).fillna({'S00': 0, 'S11': 0})
p_df['P'] = np.where(p_df['area'] > 0, -0.5 * (p_df['S00'] + p_df['S11']) / p_df['area'], 0.0)

```

---

## 8. Homogeneización Espacial: Presión Macroscópica por Región

Para evaluar la presión a nivel macro (ya sea en el bulk, en un arco o en la región de interés), no se promedian directamente las presiones individuales, sino que se promedia ponderando por el área (suma total de la traza dividida por el área total de la región).

**Expresión matemática (Promedio ponderado en área de la Región $R$):**

$$P_{\text{macro}} = \frac{\sum_{i \in R} P_i A_i}{\sum_{i \in R} A_i}$$

**Implementación en código:**

```python
# En la fase de recolección de métricas:
res[f"SumP_{region}"] = sub_df['P_A'].sum() # Numerador (P_i * A_i)
res[f"Area_{region}"] = sub_df['area'].sum() # Denominador (A_i)

# En la agregación final:
df_config[f'mean_P_{reg}'] = df_config[f'SumP_{reg}'] / df_config[f'Area_{reg}']

```

---

## 9. Detección Topológica del Arco Primario (Teoría de Grafos)

El algoritmo va más allá del cálculo local e identifica la estructura mecánica que sostiene el sistema (el arco) usando teoría de grafos. Define un grafo no dirigido $G = (V, E)$ donde los vértices $V$ son partículas por encima de cierto umbral de tamaño en la zona de descarga, y las aristas $E$ son los contactos válidos.

**Implementación en código:**

```python
# Matriz de adyacencia dispersa
adj_matrix = sp.coo_matrix((np.ones(len(row), dtype=np.int8), (row, col)), 
                           shape=(len(unique_nodes), len(unique_nodes)))

# Identificación de la componente conexa más grande (el arco principal)
n_comp, labels = csgraph.connected_components(csgraph=adj_matrix, directed=False)

```

Esto permite aislar la presión que soporta exclusivamente el clúster de partículas que obstruye el flujo.

---
