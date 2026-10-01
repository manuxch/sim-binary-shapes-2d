# Auditoría y plan de reorganización del repositorio

> Estado: **propuesta, todavía no se movió nada.**
> Fechas tomadas del historial de git: primer commit en que aparece cada archivo y último commit que lo modificó.
> (Las fechas del sistema de archivos no sirven: el clon las pone todas iguales.)

---

## 1. Diagnóstico: qué hay hoy

| Carpeta | Archivos | Problema |
|---|---|---|
| `analysis_scripts/` | 61 sueltos + ~1550 PNG | Mezcla 4 temas distintos (avalanchas, fuerzas, presión, mapas de calor) con figuras, `.npz` y `.svg` de salida |
| `analysis_scripts/heatmaps_*_v4/` | 1546 PNG, **~600 MB** | Frames intermedios (uno por atasco), son salidas, no código |
| `analysis_scripts/old.tar` | 19 scripts viejos | Versiones viejas empaquetadas, invisibles |
| `analysis_scripts/resultados_viejos/` | 16 (`.npz` + `.png`) | Mapas de calor de una corrida anterior |
| `processed_data/forces_new_19-08/` | **código** + PDFs | El script principal de fuerzas (`force_arch_v4.py`) está escondido en la carpeta de datos |
| `processed_data/forces_old/` | código + PDFs | Pipeline gnuplot viejo **pero** contiene `graficos_fuerzas_pdf_actuales_en_paper/` (¡no es viejo!) |
| `processed_data/old_para_borrar/` | 4 `.gp` | Ya marcado como viejo |
| raíz | `lista_atascos.txt`, `lista_atascos_H.txt` (30 MB c/u) | Misma lista con rutas de Windows (`E:\` vs `H:\`); ningún script los lee |
| `simulation/bin`, `simulation/obj` | binario + `.o` | Artefactos de compilación versionados |
| `render` | — | Submódulo git roto (hay gitlink pero no existe `.gitmodules`) |
| `README.md` | — | Describe LIGGGHTS y una estructura de carpetas que no existe; el simulador es **Box2D** (`simulation/src/eo-silo.cpp`) |
| `.vscode/settings.json` | — | JSON inválido (falta una coma después de `defaultEnvManager`) |

---

## 2. Duplicados detectados (viejo → nuevo)

| Viejo | Fecha | Nuevo que lo reemplaza | Fecha | Evidencia |
|---|---|---|---|---|
| `analysis_scripts/force_arch_contact.py` (internamente "force_arch_v3", antes `force_arch_v3_contact.py`) | 05-17 | `processed_data/forces_new_19-08/force_arch_v4.py` | 08-31 | Mismo docstring y mismos argumentos; v4 agrega `--min-n-contactos` y SEM pooled (800 → 1033 líneas) |
| `analysis_scripts/grafico_tension_silo.py` | 09-24 | `analysis_scripts/graficar_presion_atasco.py` | 09-24 | Docstring idéntico; el nuevo es un superconjunto (agrega `--heatmap`, `--vmin/--vmax`, `--xlim/--ylim`) |
| `processed_data/forces_old/graficar_todas_configuraciones.sh` | 06-16 | `processed_data/forces_new_19-08/graficar_todas_configuraciones.sh` | 08-31 | El nuevo dice explícitamente "Análogo a ... de forces_old/, adaptado" |
| `forces_old/` pipeline gnuplot (`filtrar_datos.py`, `preparar_datos_para_gnuplot.py`, `graficar_fuerza.sh`, `graficar_fuerza_vs_lado.gp`, `graficos_fuerza_old/*.sh/.gp`) | 06-09 → 07-01 | `forces_new_19-08/plot_fuerza_por_tipo_contacto.py` (+ `.sh`) | 08-31 | Hacen el mismo gráfico de fuerza por tipo de contacto; el nuevo usa las columnas de v4 |
| `processed_data/old_para_borrar/presion*/*.gp` | 06-25 | `analysis_scripts/comparar_presion_por_chi.py` | 09-30 | Presión arco/bulk vs χ |
| `old.tar` → `force_arch.py`, `force_arch_v1.py`, `force_arch_v2.py` | 04-29 → 06-08 | `force_arch_v4.py` | 08-31 | Versiones anteriores |
| `old.tar` → `tensor_arch.py`, `analisis_tensorial.py` | 06-02 → 06-22 | `presion_tensor_arch.py` | 09-28 | Cálculo del tensor de tensiones |
| `old.tar` → `processor`, `indexer`, `flow_analysis`, `density_map`, `temporal_chi`, `arch_consolidator`, `histogram_arch`, `generar_csv_arcos`, `main_pipeline`, `graficar_arco_fuerza` | 04-13 → 04-29 | los del mismo nombre en `analysis_scripts/` | 05-17 → 09-30 | Mismo nombre, versión anterior |
| `old.tar` → `graficos_finales_old.py`, `graficos_finales_espanol.py` | 04-13, 05-10 | `graficos_finales.py` | 09-24 | Versiones anteriores / en español |
| `old.tar` → `tail_distribution_chi.py` | 04-14 | — (sin reemplazo; salía a `3_tail_distributions`) | — | Ya no se usa en `main_pipeline.py` |
| `run_scripts/codigo_mezcla_poligono_UTN.zip` (binario `eo-silo` + `run_slurm.sh` del 04-17) | 04-17 | `run_scripts/run_slurm_cluster_utn.sh` + `params_template.in` | 05-20 | Versión anterior del lanzador SLURM |
| `analysis_scripts/resultados_viejos/heatmap_*` | 09-28 | `analysis_scripts/heatmap_*` (mismos nombres) | 09-28 | Misma figura, corrida anterior |

**No son duplicados (se mantienen como activos):**
- `sumar_heatmaps.py` y `graficar_presion_atasco.py`: parecen superados por `barrido_heatmap.py`, pero éste **los importa como módulos**.
- `graficar_arco_fuerza.py`: dibuja un atasco puntual con arco + fuerzas (SVG). `force_arch_v4 --save-images` hace algo parecido pero no igual.
- `sweep_*.sh`: cada uno barre un parámetro distinto (altura, ancho, orificio, mezcla), son lanzadores locales; `run_slurm_cluster_utn.sh` es para el cluster.
- `check.py`, `graficar_rapido.sh`: utilidades puntuales de diagnóstico, se guardan en `utils/`.

---

## 3. Estructura propuesta

```text
sim-binary-shapes-2d/
├── README.md                     # reescrito: Box2D + pipeline real
├── NOTAS.txt
├── simulation/                   # C++ / Box2D (bin/ y obj/ pasan a .gitignore)
│   ├── Makefile
│   └── src/
├── run_scripts/                  # lanzadores de simulaciones
│   ├── params_template.in
│   ├── run_slurm_cluster_utn.sh
│   ├── sweep_*.sh, pack_simulations.sh, renderizar_all.sh
│   └── viejo/codigo_mezcla_poligono_UTN.zip
├── analysis/
│   ├── 1_avalanchas_y_arcos/     # pipeline principal (main_pipeline.py y todo lo que importa)
│   │   ├── main_pipeline.py, indexer.py, processor.py, flow_analysis.py,
│   │   ├── density_map.py, temporal_chi.py, generar_csv_arcos.py,
│   │   ├── arch_consolidator.py, histogram_arch.py, graficos_finales.py
│   │   └── viejo/                # versiones de old.tar
│   ├── 2_fuerzas/
│   │   ├── force_arch_v4.py, plot_fuerza_por_tipo_contacto.py/.sh,
│   │   ├── graficar_todas_configuraciones.sh, graficar_arco_fuerza.py
│   │   ├── README_auditoria_fuerzas.md
│   │   └── viejo/                # force_arch v1/v2/v3, pipeline gnuplot de forces_old
│   ├── 3_presion_y_mapas/        # juntos porque se importan entre sí
│   │   ├── presion_tensor_arch.py (+ .md), comparar_presion_por_chi.py,
│   │   ├── graficar_presion_atasco.py, dividir_particulas_por_forma.py,
│   │   ├── barrido_heatmap.py, sumar_heatmaps.py, graficar_npz_misma_escala.py, hacer_mapas.py
│   │   └── viejo/                # grafico_tension_silo.py, tensor_arch.py, analisis_tensorial.py, .gp viejos
│   ├── 4_correlaciones_gnuplot/  # los .gp de processed_data/correlation
│   └── utils/                    # check.py, graficar_rapido.sh
└── processed_data/               # SOLO resultados (se mantiene el nombre: los scripts escriben ahí con ruta absoluta)
    ├── 5_graficos_finales/
    ├── fuerzas/
    │   ├── pdf_v4/               # ex forces_new_19-08/graficos_fuerzas_pdf
    │   ├── pdf_en_paper/         # ex forces_old/graficos_fuerzas_pdf_actuales_en_paper  (¡NO se marca viejo!)
    │   └── viejo/                # graficos_fuerza_old, graficos_fuerzas_promediando_fuerzas_totales
    ├── presion/                  # .svg de presion_atasco y comparacion_chi_*.png
    └── mapas_calor/
        ├── heatmap_*.png/.npz    # promedios finales
        ├── frames_v4/            # ex heatmaps_*_v4
        └── viejo/                # ex resultados_viejos
```

Se elimina: `processed_data/old_para_borrar/` (contenido va a `3_presion_y_mapas/viejo/`), `old.tar` (se extrae), `render` (submódulo roto).

---

## 4. Cosas que se rompen al mover y cómo las cubro

1. **Imports entre scripts.** `main_pipeline.py` importa 8 módulos; `barrido_heatmap.py` importa `graficar_presion_atasco` y `sumar_heatmaps`; `graficar_npz_misma_escala.py` importa `barrido_heatmap`; `hacer_mapas.py` los llama por ruta relativa a sí mismo. → Cada grupo queda en la **misma carpeta**, así que siguen funcionando.
2. **Rutas absolutas** `/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/...` en ~10 scripts y en los `.gp` de correlación. → Por eso **no renombro `processed_data/`**: esas rutas siguen siendo válidas.
3. **Datos locales que no están en git** (ignorados por `.gitignore`: `*.csv`, `por_forma/`, `master_sim_index.csv`, `processed_data/1_avalanche_data/`, etc.). `git mv` no los mueve: cuando hagas `git pull` en tu máquina, esos archivos se quedan en la carpeta vieja. Casos concretos:
   - `plot_fuerza_por_tipo_contacto.py` lee `resumen_fuerza_normal_por_configuracion.csv` **de su propia carpeta** → hay que mover ese CSV a mano a `analysis/2_fuerzas/` (o cambio el script para que lo tome por argumento).
   - `check.py` y los ejemplos de `barrido_heatmap.py` usan `por_forma/` relativo.
   - Te dejo un script `mover_datos_locales.sh` que hace esos movimientos en tu máquina.
4. **`.gitignore`**: tiene `analysis_scripts/por_forma` → se actualiza a la nueva ruta.

---

## 5. Decisiones pendientes (las tenés que tomar vos)

- **Archivos pesados en git**: ~600 MB de frames PNG + ~80 MB de `.npz` + 60 MB de `lista_atascos*` + binarios. ¿Los saco del control de versiones (quedan en tu disco, se agregan a `.gitignore`) o los sigo versionando?
- **`old.tar` y el `.zip`**: ¿los extraigo en las carpetas `viejo/` o los dejo como archivo comprimido?
- **`lista_atascos.txt` / `_H.txt`**: ningún script los usa. ¿`viejo/`, `processed_data/`, o borrar uno de los dos?

## 6. Extras que propongo (fuera de la reorganización)

- Reescribir el `README.md` con la estructura real y el orden de ejecución.
- Arreglar `.vscode/settings.json` (coma faltante).
- Más adelante: centralizar las rutas absolutas en un `config.py` (no lo hago ahora para no tocar lógica).
