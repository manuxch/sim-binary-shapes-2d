# Tensor de estrés calculado en la simulación

En cada atasco, antes de romper el arco, `eo-silo` escribe en `frames_<dirID>/`:

| Archivo | Contenido |
|---|---|
| `atasco_<jam>.xy` | Granos activos y paredes (`saveAtascoFrame`, sin cambios). |
| `atasco_contacts_<jam>.dat` | Contactos en el formato de siempre: `ID_A ID_B PosX PosY NormalImpulse TangentImpulse`, una fila por punto de manifold, impulsos con signo. Es la entrada de `analysis/3_presion_y_mapas/presion_tensor_arch.py`. |
| `atasco_tensor_<jam>.dat` | **Nuevo.** Tensor de estrés de cada grano, calculado con la normal real de Box2D. |
| `atasco_contacts_full_<jam>.dat` | **Nuevo.** Los mismos contactos, en el mismo orden, con la normal de Box2D, las fuerzas y los centros. |

Las tres salidas corresponden al mismo instante: posiciones e impulsos del último `Step`.

El código está en `src/jam_output.cpp`. El escritor de `atasco_contacts` se reconstruyó a partir del binario de producción (`run_scripts/viejo.tar.gz`), cuyo fuente no estaba en el repositorio. Se reprodujeron la cabecera, el orden de las filas, el formato numérico (`%.6e`), la inclusión de los contactos con paredes y de los puntos con impulso nulo.

## Convenciones

Box2D 2.4 (`b2ContactSolver`):

- la normal `n` del manifold apunta del cuerpo A al cuerpo B;
- la tangente es `t = b2Cross(n, 1) = (n.y, -n.x)`;
- la fuerza media durante el paso sobre B es `F_B = (normalImpulse n + tangentImpulse t) / dt`, y sobre A es `F_A = -F_B`.

Tensor de cada grano (fórmula de Love, **compresión < 0**):

```
s_ij = (1/A) sum_c F_i l_j,     l = punto de contacto - centro de masa
```

- `A` es el área que usa Box2D para la masa (`ComputeMass`). Para los polígonos es el área de los vértices, sin la piel `b2_polygonRadius = 0.01`.
- `sn` es la parte debida solo a las fuerzas normales; la tangencial es `s - sn`.
- Con polígonos, `sn` no es simétrico y la fricción aporta a la traza: el brazo `l` no es paralelo a la normal.

Columnas de `atasco_tensor_<jam>.dat`:

```
gID tipo nLados x y A m sxx sxy syx syy snxx snxy snyx snyy Fx Fy tau z z_w z_f vx vy w
```

- `Fx`, `Fy` y `tau`: fuerza y torque netos de contacto. En reposo, `F + m g = 0` y `tau = 0`.
- `z`: contactos con fuerza normal total positiva. Cuenta manifolds, no puntos: un contacto cara–cara tiene dos puntos y cuenta una vez.
- `z_w`: de esos contactos, los que son con paredes.
- `z_f`: de esos contactos, los que tienen los dos puntos activos (cara–cara).
- `vx`, `vy`, `w`: velocidades lineal y angular. Sirven para descartar granos que no están en reposo.

Relación con `presion_tensor_arch.py`, que usa `S = sum r F` con el brazo primero:

```
A sxx = S00,  A sxy = S10,  A syx = S01,  A syy = S11,   P = -(sxx + syy)/2
```

## Comparación

```bash
python3 analysis/utils/comparar_tensor_simulacion.py --frames /ruta/frames_<dirID> --r_salida <Radio_salida>
```

El script hace cuatro comparaciones:

1. Compara, contacto por contacto, la normal que infiere el análisis con la de Box2D.
2. Compara, grano por grano, P, `sxx`, `syy` y las partes simétrica y antisimétrica de `sxy`.
3. Controla el tensor del simulador:
   - equilibrio de fuerzas con la gravedad;
   - torque nulo;
   - `A (syx - sxy) = tau`;
   - virial global contra las paredes.
4. Con `--r_salida`, calcula ⟨P⟩ pesado por área en el arco y en la ROI con los dos tensores.
