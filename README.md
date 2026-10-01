# Atascos en silos 2D con mezclas binarias de formas

Simulación y análisis del flujo y atascamiento de medios granulares bidispersos (discos y polígonos) en un silo 2D vibrado. Se estudian avalanchas, arcos, fuerzas de contacto y el tensor de tensiones / presión en función de la fracción de área de partículas chicas (χ), la razón de tamaños y la forma.

- **Simulador:** C++ con **Box2D 2.4.2** (`simulation/`, ejecutable `eo-silo`).
- **Análisis:** Python (numpy, pandas, networkx, matplotlib, pyarrow) y algunos scripts de gnuplot.

## Estructura

```text
sim-binary-shapes-2d/
├── simulation/                     # Código C++ del simulador (Box2D)
│   ├── Makefile                    # make -> bin/eo-silo (bin/ y obj/ no se versionan)
│   └── src/
├── run_scripts/                    # Lanzar simulaciones
│   ├── params_template.in          # Plantilla de parámetros
│   ├── run_slurm_cluster_utn.sh    # Barridos en el cluster (SLURM)
│   ├── sweep_*.sh                  # Barridos locales (altura, ancho, orificio, mezcla)
│   ├── pack_simulations.sh, renderizar_all.sh
│   └── viejo.tar.gz                # Versión anterior del paquete UTN
├── analysis/
│   ├── 1_avalanchas_y_arcos/       # Pipeline principal (main_pipeline.py)
│   ├── 2_fuerzas/                  # Fuerza normal en arco / ROI por tipo de contacto
│   ├── 3_presion_y_mapas/          # Tensor de tensiones, presión y mapas de calor
│   ├── 4_correlaciones_gnuplot/    # Gráficos cruzados (avalanchas vs tortuosidad, Fn, ...)
│   └── utils/                      # Diagnósticos puntuales
└── processed_data/                 # Resultados (figuras); los CSV/npz/parquet quedan solo en disco
    ├── 5_graficos_finales/
    ├── fuerzas/   (pdf_v4/, pdf_en_paper/, datos_v4/*)
    ├── presion/
    └── mapas_calor/ (heatmap_*.png, frames_v4/*)
```
`*`: solo en disco local, no se versiona.

Cada carpeta de `analysis/` y `processed_data/` puede tener un `viejo.tar.gz` con las versiones anteriores de los scripts o figuras (para ver qué hay adentro: `tar tzf viejo.tar.gz`; para extraerlo: `tar xzf viejo.tar.gz`).

## Flujo de trabajo

1. **Compilar y simular**
   ```bash
   cd simulation && make            # requiere Box2D en ../../box2d y GSL
   # copiar bin/eo-silo junto a run_scripts/ y lanzar un barrido
   ```
2. **Avalanchas y arcos** (indexa simulaciones, detecta avalanchas y arcos, consolida y grafica)
   ```bash
   python analysis/1_avalanchas_y_arcos/main_pipeline.py
   python analysis/1_avalanchas_y_arcos/graficos_finales.py
   ```
   Genera `master_sim_index.csv` y `processed_data/1_avalanche_data/`.
3. **Fuerzas**
   ```bash
   python analysis/2_fuerzas/force_arch_v4.py --idx master_sim_index.csv --out processed_data/fuerzas/datos_v4
   bash   analysis/2_fuerzas/graficar_todas_configuraciones.sh   # -> processed_data/fuerzas/pdf_v4
   ```
4. **Presión y mapas de calor**
   ```bash
   python analysis/3_presion_y_mapas/presion_tensor_arch.py ...      # -> presion_por_particula.csv
   python analysis/3_presion_y_mapas/dividir_particulas_por_forma.py --csv presion_por_particula.csv --out_dir por_forma/
   python analysis/3_presion_y_mapas/hacer_mapas.py                  # todos los mapas de una vez
   python analysis/3_presion_y_mapas/comparar_presion_por_chi.py --csv resumen_presion_por_atasco.csv
   ```

Los scripts dentro de una misma carpeta de `analysis/` se importan entre sí: hay que mantenerlos juntos.

## Notas

- Varios scripts del paso 1 usan rutas absolutas a `/home/juli/work/lab/project/sim-binary-shapes-2d/...`.
- `migrar_datos_locales.sh`: correrlo una vez después del pull de la reorganización para recuperar los archivos pesados y acomodar los datos locales.
- `AUDITORIA_REORGANIZACION.md`: detalle de qué se movió, a dónde y por qué.
