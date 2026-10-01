#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Barre los atascos de una geometría (forma de grano grande) en
presion_por_particula.csv, genera una imagen --heatmap por atasco, y las
combina en mapas de presión promedio — separados por chi si se pide, todo
en UNA sola pasada por el archivo (no relee el archivo una vez por chi).

Internamente usa las mismas funciones que graficar_presion_atasco.py y
sumar_heatmaps.py (los importa como módulos), así que tienen que estar
en la misma carpeta que este script.

Uso:
    # Un solo heatmap, mezclando todos los chi de esa forma, silo completo:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --out_dir heatmaps_disco --out_final heatmap_Disco.png --workers 8

    # Un heatmap separado por cada chi de una lista puntual:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --chis 0.01 0.1 0.2 0.3 0.4 \
        --out_dir heatmaps_disco --out_final heatmap_Disco.png --workers 8
    # (genera heatmap_Disco_chi0p01.png, heatmap_Disco_chi0p1.png, etc.)

    # Que detecte solo los chi que hay en el archivo y separe por cada uno:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --chis auto \
        --out_dir heatmaps_disco --out_final heatmap_Disco.png --workers 8

    # Separar ademas por razon de areas (chica/grande). Genera un mapa por
    # cada combinacion (ratio, chi), ej. heatmap_Disco_ratio0p1_chi0p2.png:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --ratios 0.1 0.4 --chis 0.0 0.1 0.2 0.4 \
        --out_dir heatmaps_disco_ratio --out_final heatmap_Disco.png --workers 8

    # Detectar solos los ratios presentes (y los chi) y separar por todos:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --ratios auto --chis auto \
        --out_dir heatmaps_disco_ratio --out_final heatmap_Disco.png --workers 8

    # Solo una franja del silo (ej. el cuarto inferior, zona de la salida):
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --chis 0.0 0.1 0.2 0.4 --fraccion_altura 0.25 --desde abajo \
        --out_dir heatmaps_disco_region --out_final heatmap_Disco.png --workers 8
    # IMPORTANTE: usar una --out_dir distinta a la del silo completo, porque
    # el combinado toma TODOS los PNG de la carpeta que coinciden con el
    # patron, y frames de regiones distintas no se pueden promediar juntos.

    # Retomar una corrida que se corto (ej. por falta de RAM) sin rehacer
    # los frames que ya estan en --out_dir:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Disco.parquet \
        --forma Disco --chis 0.0 0.1 0.2 0.4 --fraccion_altura 0.25 --desde abajo \
        --out_dir heatmaps_disco_region --out_final heatmap_Disco.png \
        --workers 6 --chunksize 50000 --reanudar
    # Antes de reanudar, borrar los ultimos PNG escritos (ls -t <out_dir> | head),
    # porque el frame que se estaba guardando al cortarse puede estar truncado.
    # Los argumentos de escala/region tienen que ser los MISMOS que en la
    # corrida original, si no se mezclan frames con escalas distintas.

Mezclas con grano grande poligonal (--csv_chicos):
    Con el parquet dividido por 'shape', los granos grandes de un poligono
    estan en su archivo (ej. _Triangulo.parquet) y los discos CHICOS de esas
    mismas simulaciones quedaron en el archivo _Disco.parquet. Para que el
    mapa incluya a los dos:
    python3 barrido_heatmap.py --csv por_forma/presion_por_particula_Triangulo.parquet \
        --csv_chicos por_forma/presion_por_particula_Disco.parquet \
        --forma Triangulo --ratios 0.1 --chis 0.0 0.2 --fraccion_altura 0.25 \
        --out_dir heatmaps_triangulo_v3 --out_final heatmap_Triangulo.png --workers 6
    Se procesa simulacion por simulacion (grandes + chicos del mismo
    sim_path, juntados por jam_id).

Forma del grano GRANDE:
    - Si el archivo tiene la columna 'forma_grande', se filtra por ella y
      listo: --forma se refiere siempre al grano grande de la mezcla.
    - Si no la tiene (parquet armado filtrando por 'shape' de cada
      particula), en el archivo 'Disco' (--forma_chicos) se cuelan los discos CHICOS de
      mezclas con granos grandes de otra forma. Esos atascos quedan con un
      solo tamaño de particula. Antes de generar nada, el script hace una
      pasada liviana y descarta todo atasco con chi > 0 en el que
      area_min/area_max >= --umbral_tamanos (0.95): o sea, sin grandes.
      Los atascos con chi = 0 (solo grandes) se aceptan siempre.
    - Al arrancar lista los sim_path afectados y el area maxima tipica de
      validos vs descartados, para verificar que el criterio separa bien.
    - --sin_validar_grande desactiva este descarte.
    - Esta validacion SOLO se aplica cuando --forma es la forma de los chicos
      (Disco). En el archivo de un poligono todas las particulas son granos
      grandes (un solo tamaño aunque chi > 0), asi que no se valida nada.
    - Limitacion: con ratio >= --umbral_tamanos (ej. 1.0) grandes y chicos
      tienen el mismo tamaño y el criterio los descarta aunque sean validos.

Nombres de los frames:
    heatmap_<forma>_<bucket>_<basename del sim_path>-<hash>_<jam_id>.png
    El hash (6 caracteres de la ruta completa) evita que dos sim_path con
    el mismo nombre de carpeta en lugares distintos se pisen. Frames de
    versiones anteriores del script (sin hash) NO se reconocen con
    --reanudar: usar una --out_dir nueva.

Razon de areas (--ratios):
    - Si el archivo tiene una columna con la razon de areas, se usa esa
      (se busca automaticamente entre: area_ratio, ratio_area,
      area_ratio_nominal, ratio; o se fuerza con --col_ratio NOMBRE).
    - Si no, se lee del sim_path: 'Ratio_0p4' -> 0.4. Las carpetas viejas
      'Chi_X_W_Y' sin prefijo 'Ratio_' se toman como --ratio_sin_etiqueta
      (default 0.1). Los sim_path que no encajan en ninguno de los dos
      formatos quedan SIN ratio y se descartan al filtrar por ratio; el
      script los lista al arrancar para que se puedan revisar.
    - Al arrancar se imprime una tabla con las combinaciones (ratio, chi)
      encontradas y cuantas simulaciones hay en cada una, para verificar
      que la asignacion de ratios sea la correcta antes de generar frames.
    - Sin --ratios, los nombres de archivo son los mismos que antes (solo
      chi), asi que --reanudar sigue funcionando con corridas viejas.
    - No mezclar en la misma --out_dir corridas con y sin --ratios: el
      combinado de un bucket 'ratio0p1' tomaria tambien los frames
      'ratio0p1_chi...' de otra corrida.

Escala de color del mapa promediado:
    - Los frames se generan con vmin/vmax de percentiles de la presion POR
      PARTICULA (hace falta para decodificar color -> valor). El mapa final
      (promedio sobre atascos) tiene un rango mucho mas angosto, asi que por
      defecto (--escala_mapa mapa) se grafica con percentiles de los propios
      valores promediados (--mapa_pct 1 99), compartidos por todos los
      buckets de la corrida.
    - Para comparar formas distintas (corridas separadas) con la MISMA
      escala: --vmin_mapa / --vmax_mapa (el script imprime los valores que
      uso, para copiarlos a la otra corrida).
    - --solo_combinar rearma los mapas desde los frames existentes, sin
      regenerarlos (ej. para cambiar la escala).

Otras magnitudes (--col_p):
    Cualquier columna numerica del archivo, ej. tau / tau_reducida si el
    archivo tiene el esfuerzo de corte por particula.

Memoria:
    - --chunksize: filas por trozo de lectura (csv y parquet). Bajarlo
      (ej. 50000) reduce el pico de RAM al leer.
    - --max_en_vuelo: cuantos atascos leidos-pero-no-dibujados puede haber
      a la vez (default 2x --workers).
    - --max_tareas_worker: cada worker se reinicia despues de esa cantidad
      de frames (default 200), liberando la memoria que matplotlib/pandas
      van acumulando en corridas largas.
    - Con --fraccion_altura, a cada worker solo se le mandan las particulas
      de la region (mas un margen de un radio), no el atasco completo.
    - Con --chis y/o --ratios, las lecturas pesadas se restringen a las
      simulaciones de las combinaciones pedidas (filtro de pyarrow al leer),
      en vez de recorrer y decodificar el archivo entero.
    - Los workers se crean con 'forkserver', asi no heredan la memoria del
      proceso principal.
"""
import argparse
import os
import re
import glob
import itertools
import hashlib
import multiprocessing as mp

import matplotlib
matplotlib.use('Agg')  # headless, imprescindible al generar en paralelo
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from PIL import Image

import graficar_presion_atasco as gpa
import sumar_heatmaps as sh

TOL_CHI = 1e-6


def _liberar_memoria_arrow():
    """pyarrow guarda en su pool la memoria de los batches ya leidos para
    reusarla; esto se la devuelve al sistema operativo."""
    try:
        import pyarrow as pa
        pa.default_memory_pool().release_unused()
    except Exception:
        pass


def _iterar_chunks(path, chunksize, columnas=None, sim_paths=None):
    """Generador de chunks (DataFrames) desde un csv o un parquet, sin
    cargar el archivo entero de una. 'columnas' (si se pasa) limita que
    columnas se leen -- en parquet esto es una lectura columnar real
    (mucho mas liviana), en csv al menos evita materializar 'coords'.

    sim_paths: si se pasa, solo se devuelven filas de esos sim_path. En
    parquet el filtro lo aplica pyarrow al leer (y saltea grupos de filas
    enteros usando sus estadisticas min/max cuando puede), asi que las
    columnas pesadas (coords) de las simulaciones que no interesan ni
    siquiera llegan a pandas."""
    if path.endswith('.parquet') and sim_paths is not None:
        import pyarrow.dataset as ds
        dataset = ds.dataset(path, format='parquet')
        cols = columnas if columnas is not None else dataset.schema.names
        filtro = ds.field('sim_path').isin(sorted(sim_paths))
        # use_threads=False: mantiene el orden de las filas (necesario para
        # el 'carry' de atascos entre trozos) y no lee de mas por adelantado.
        scanner = dataset.scanner(columns=cols, filter=filtro, batch_size=chunksize,
                                  use_threads=False)
        for batch in scanner.to_batches():
            if batch.num_rows:
                yield batch.to_pandas()
        return
    if path.endswith('.parquet'):
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        cols = columnas if columnas is not None else [f.name for f in pf.schema_arrow]
        for batch in pf.iter_batches(batch_size=chunksize, columns=cols):
            yield batch.to_pandas()
    else:
        for chunk in pd.read_csv(path, dtype={'jam_id': str}, chunksize=chunksize, usecols=columnas):
            if sim_paths is not None:
                chunk = chunk[chunk['sim_path'].astype(str).isin(sim_paths)]
            yield chunk


def _detectar_col_filtro(path):
    if path.endswith('.parquet'):
        import pyarrow.parquet as pq
        cols = [f.name for f in pq.ParquetFile(path).schema_arrow]
    else:
        cols = pd.read_csv(path, nrows=0).columns.tolist()
    return 'forma_grande' if 'forma_grande' in cols else 'shape'


def _sin_excluidos(chunk, excluir_sim_path, invalidos=None):
    """Saca las filas de sim_path excluidos a mano (--excluir_sim_path) y
    las de atascos marcados como invalidos (sin particula grande de la
    forma pedida, ver detectar_atascos_sin_grande)."""
    if chunk.empty:
        return chunk
    if excluir_sim_path:
        mask = pd.Series(True, index=chunk.index)
        for frag in excluir_sim_path:
            mask &= ~chunk['sim_path'].astype(str).str.contains(frag, regex=False)
        chunk = chunk[mask]
    if invalidos is not None and len(invalidos) > 0 and not chunk.empty:
        idx = pd.MultiIndex.from_arrays([chunk['sim_path'].astype(str),
                                         chunk['jam_id'].astype(str)])
        chunk = chunk[~idx.isin(invalidos)]
    return chunk


def detectar_atascos_sin_grande(path, forma, col_filtro, chunksize, excluir_sim_path=None,
                                umbral_tamanos=0.95):
    """Cuando el archivo no tiene 'forma_grande', el filtro por 'shape' deja
    pasar los discos CHICOS de mezclas cuyo grano GRANDE es de otra forma
    (ej. poligonos grandes + discos chicos): esos atascos quedan con solo
    particulas chicas. Aca se detectan, atasco por atasco:

      - chi ~ 0  -> solo hay granos grandes, el atasco es valido.
      - chi > 0  -> tiene que haber DOS tamaños (grandes y chicos) de la
                    forma pedida: area_min / area_max < umbral_tamanos.
                    Si hay un solo tamaño, son solo los chicos -> invalido.

    Lectura liviana (sim_path, jam_id, chi, area). Devuelve
    (MultiIndex de (sim_path, jam_id) invalidos, DataFrame resumen por atasco)."""
    cols = list({col_filtro, 'sim_path', 'jam_id', 'chi', 'area'})
    parciales = []
    for chunk in _iterar_chunks(path, chunksize, columnas=cols):
        chunk = chunk[chunk[col_filtro] == forma]
        chunk = _sin_excluidos(chunk, excluir_sim_path)
        if chunk.empty:
            continue
        chunk = chunk.assign(sim_path=chunk['sim_path'].astype(str),
                             jam_id=chunk['jam_id'].astype(str))
        parciales.append(chunk.groupby(['sim_path', 'jam_id'], sort=False).agg(
            chi=('chi', 'first'), a_min=('area', 'min'), a_max=('area', 'max')))
    if not parciales:
        return pd.MultiIndex.from_tuples([], names=['sim_path', 'jam_id']), pd.DataFrame()

    # un atasco puede quedar partido entre dos chunks -> reagrupar
    agg = pd.concat(parciales).groupby(level=[0, 1], sort=False).agg(
        chi=('chi', 'first'), a_min=('a_min', 'min'), a_max=('a_max', 'max'))
    agg['min_sobre_max'] = agg['a_min'] / agg['a_max']
    sin_chicos = agg['chi'].abs() < TOL_CHI
    dos_tamanos = agg['min_sobre_max'] < umbral_tamanos
    agg['valido'] = sin_chicos | dos_tamanos
    return agg.index[~agg['valido']], agg


def _reportar_atascos_sin_grande(agg, forma, max_lineas=20):
    if agg.empty:
        return
    n_tot = len(agg)
    inval = agg[~agg['valido']]
    print(f"  {n_tot} atascos con particulas '{forma}', {len(inval)} descartados por no tener "
          f"granos grandes '{forma}' (solo un tamaño, con chi > 0).")
    if inval.empty:
        return
    val = agg[agg['valido']]
    if not val.empty:
        print(f"  area maxima tipica -- validos: {val['a_max'].median():.4g}   "
              f"descartados: {inval['a_max'].median():.4g}")
    por_sim = inval.groupby(level=0).size().sort_values(ascending=False)
    tot_sim = agg.groupby(level=0).size()
    print(f"  sim_path afectados ({len(por_sim)}):")
    for sp, n in por_sim.head(max_lineas).items():
        print(f"    {n:>5}/{tot_sim[sp]:<5} atascos  {sp}")
    if len(por_sim) > max_lineas:
        print(f"    ... y {len(por_sim) - max_lineas} mas")
    parciales = [sp for sp, n in por_sim.items() if n < tot_sim[sp]]
    if parciales:
        print(f"  OJO: {len(parciales)} sim_path tienen algunos atascos validos y otros no "
              f"(esperable solo si hay atascos con muy pocas particulas chicas). Revisar:")
        for sp in parciales[:max_lineas]:
            print(f"    {sp}")


_RE_RATIO = re.compile(r'Ratio_(\d+)p(\d+)')
_RE_CHI_VIEJO = re.compile(r'Chi_\d+p\d+_W_')
CANDIDATAS_COL_RATIO = ['area_ratio', 'ratio_area', 'area_ratio_nominal', 'ratio']


def _columnas_archivo(path):
    if path.endswith('.parquet'):
        import pyarrow.parquet as pq
        return [f.name for f in pq.ParquetFile(path).schema_arrow]
    return pd.read_csv(path, nrows=0).columns.tolist()


def _detectar_col_ratio(path, forzada=None):
    """Nombre de la columna con la razon de areas, o None si no hay y hay
    que sacarla del sim_path."""
    cols = _columnas_archivo(path)
    if forzada is not None:
        if forzada not in cols:
            raise SystemExit(f"--col_ratio {forzada!r} no esta en el archivo. Columnas: {cols}")
        return forzada
    for c in CANDIDATAS_COL_RATIO:
        if c in cols:
            return c
    return None


def ratio_desde_sim_path(sim_path, ratio_sin_etiqueta):
    """'.../Ratio_0p4_Chi_0p0_W_2p0/...' -> 0.4. Carpetas viejas
    'Chi_X_W_Y' sin 'Ratio_' -> ratio_sin_etiqueta. Otra cosa -> NaN.
    Si aparece mas de un 'Ratio_' en la ruta, vale el ultimo (el mas
    interno)."""
    s = str(sim_path)
    m = _RE_RATIO.findall(s)
    if m:
        ent, dec = m[-1]
        return round(float(f"{ent}.{dec}"), 6)
    if ratio_sin_etiqueta is not None and _RE_CHI_VIEJO.search(s):
        return round(float(ratio_sin_etiqueta), 6)
    return np.nan


def _agregar_ratio(chunk, col_ratio, ratio_sin_etiqueta):
    """Agrega la columna '_ratio' al chunk (desde la columna del archivo o
    parseando sim_path -- una vez por sim_path unico, no por fila)."""
    if col_ratio is not None:
        return chunk.assign(_ratio=chunk[col_ratio].astype(float).round(6))
    unicos = chunk['sim_path'].unique()
    mapa = {p: ratio_desde_sim_path(p, ratio_sin_etiqueta) for p in unicos}
    return chunk.assign(_ratio=chunk['sim_path'].map(mapa).astype(float))


def _coincide(valor, pedidos):
    """Devuelve el valor pedido que coincide con 'valor' (tolerancia
    TOL_CHI), o None. NaN nunca coincide."""
    for c in pedidos:
        if abs(valor - c) < TOL_CHI:
            return c
    return None


def _mascara_pedidos(chunk, chis_pedidos, ratios_pedidos):
    mask = np.ones(len(chunk), dtype=bool)
    if chis_pedidos is not None:
        chi = chunk['chi'].to_numpy()
        m = np.zeros(len(chunk), dtype=bool)
        for c in chis_pedidos:
            m |= np.abs(chi - c) < TOL_CHI
        mask &= m
    if ratios_pedidos is not None:
        r = chunk['_ratio'].to_numpy()
        m = np.zeros(len(chunk), dtype=bool)
        with np.errstate(invalid='ignore'):
            for c in ratios_pedidos:
                m |= np.abs(r - c) < TOL_CHI
        mask &= m
    return mask


def detectar_valores(path, forma, col_filtro, chunksize, excluir_sim_path=None,
                     usar_ratio=False, col_ratio=None, ratio_sin_etiqueta=0.1, invalidos=None):
    """Escaneo liviano (pocas columnas) de que valores de chi y de ratio
    existen para esta forma. Devuelve (chis, ratios, combos, sin_ratio):
    combos = {(ratio o None, chi): set de sim_path}, sin_ratio = set de sim_path
    a los que no se les pudo asignar ratio."""
    chis = set()
    combos = {}
    sin_ratio = set()
    cols = {col_filtro, 'chi', 'sim_path', 'jam_id'}
    if usar_ratio and col_ratio is not None:
        cols.add(col_ratio)
    for chunk in _iterar_chunks(path, chunksize, columnas=list(cols)):
        chunk = chunk[chunk[col_filtro] == forma]
        chunk = _sin_excluidos(chunk, excluir_sim_path, invalidos)
        if chunk.empty:
            continue
        chis.update(np.round(chunk['chi'].unique(), 6).tolist())
        if usar_ratio:
            chunk = _agregar_ratio(chunk, col_ratio, ratio_sin_etiqueta)
            sub = chunk[['sim_path', 'chi', '_ratio']].drop_duplicates()
            for sp, chi, r in sub.itertuples(index=False):
                if np.isnan(r):
                    sin_ratio.add(str(sp))
                else:
                    combos.setdefault((round(r, 6), round(chi, 6)), set()).add(str(sp))
        else:
            sub = chunk[['sim_path', 'chi']].drop_duplicates()
            for sp, chi in sub.itertuples(index=False):
                combos.setdefault((None, round(chi, 6)), set()).add(str(sp))
    ratios = sorted({r for r, _ in combos if r is not None})
    return sorted(chis), ratios, combos, sin_ratio


def chi_a_etiqueta(chi):
    return "chi" + f"{chi}".replace('.', 'p')


def ratio_a_etiqueta(ratio):
    return "ratio" + f"{ratio}".replace('.', 'p')


def asignar_bucket(chi_valor, chis_pedidos, ratio_valor=None, ratios_pedidos=None):
    """Etiqueta del bucket al que pertenece el atasco, o None si no
    coincide con lo pedido. Sin chis ni ratios pedidos -> 'todos'.
    Ej.: 'chi0p2', 'ratio0p1', 'ratio0p1_chi0p2'."""
    partes = []
    if ratios_pedidos is not None:
        r = _coincide(ratio_valor, ratios_pedidos)
        if r is None:
            return None
        partes.append(ratio_a_etiqueta(r))
    if chis_pedidos is not None:
        c = _coincide(chi_valor, chis_pedidos)
        if c is None:
            return None
        partes.append(chi_a_etiqueta(c))
    return "_".join(partes) if partes else "todos"


def bucket_a_titulo(bucket):
    """'ratio0p1_chi0p2' -> 'ratio=0.1, χ=0.2' (para el titulo del grafico)."""
    if bucket == "todos":
        return ""
    partes = []
    for p in bucket.split("_"):
        if p.startswith("ratio"):
            partes.append("ratio=" + p[len("ratio"):].replace('p', '.'))
        elif p.startswith("chi"):
            partes.append("χ=" + p[len("chi"):].replace('p', '.'))
    return ", ".join(partes)


def calcular_escala_liviana(path, forma, col_filtro, chis_pedidos, col_p,
                             vmin_pct, vmax_pct, chunksize, excluir_sim_path=None, margen_extra=1.0,
                             fraccion_altura=None, desde='abajo',
                             ratios_pedidos=None, col_ratio=None, ratio_sin_etiqueta=0.1,
                             invalidos=None, sim_paths=None, fuente_chicos=None):
    """vmin/vmax/xlim/ylim UNA sola vez, compartidos por todos los buckets
    de chi (para que sean comparables entre si) -- lectura columnar
    liviana, nunca carga 'coords'/'shape'/'region'.

    Si se pasa fraccion_altura, el ylim se restringe a esa fraccion de la
    altura total ocupada por particulas (medida desde abajo o desde
    arriba), y los percentiles de vmin/vmax se calculan SOLO con las
    particulas dentro de esa region, para que la escala de color
    aproveche el rango de presiones de la zona que se muestra.

    fuente_chicos: (path, col_filtro, valor) del archivo con las particulas
    chicas, si estan en otro archivo -- se incluyen en la escala (solo de
    las simulaciones en sim_paths)."""
    xmin = ymin = float('inf')
    xmax = ymax = float('-inf')
    rmax = 0.0
    muestras = []

    fuentes = [(path, col_filtro, forma, invalidos)]
    if fuente_chicos is not None:
        fuentes.append((fuente_chicos[0], fuente_chicos[1], fuente_chicos[2], None))

    for f_path, f_col, f_valor, f_invalidos in fuentes:
        cols = {f_col, 'chi', 'pos_x', 'pos_y', 'area', col_p, 'sim_path', 'jam_id'}
        if ratios_pedidos is not None and col_ratio is not None:
            cols.add(col_ratio)
        for chunk in _iterar_chunks(f_path, chunksize, columnas=list(cols), sim_paths=sim_paths):
            chunk = chunk[chunk[f_col] == f_valor]
            chunk = _sin_excluidos(chunk, excluir_sim_path, f_invalidos)
            if chunk.empty:
                continue
            if ratios_pedidos is not None:
                chunk = _agregar_ratio(chunk, col_ratio, ratio_sin_etiqueta)
            if chis_pedidos is not None or ratios_pedidos is not None:
                chunk = chunk[_mascara_pedidos(chunk, chis_pedidos, ratios_pedidos)]
            if chunk.empty:
                continue
            xmin = min(xmin, chunk['pos_x'].min()); xmax = max(xmax, chunk['pos_x'].max())
            ymin = min(ymin, chunk['pos_y'].min()); ymax = max(ymax, chunk['pos_y'].max())
            rmax = max(rmax, np.sqrt(chunk['area'].max() / np.pi))
            sub = chunk.loc[chunk[col_p] > 0, ['pos_y', col_p]]
            if len(sub) > 20_000:
                sub = sub.sample(20_000, random_state=0)
            muestras.append(sub)
        _liberar_memoria_arrow()

    if not muestras:
        raise SystemExit(f"No hay filas para forma={forma!r} en {path} (con los chi/ratios pedidos).")

    todos = pd.concat(muestras, ignore_index=True)

    y_lo, y_hi = ymin, ymax
    if fraccion_altura is not None:
        alto_region = (ymax - ymin) * fraccion_altura
        if desde == 'abajo':
            y_hi = ymin + alto_region
        else:
            y_lo = ymax - alto_region
        todos = todos[(todos['pos_y'] >= y_lo) & (todos['pos_y'] <= y_hi)]
        if todos.empty:
            raise SystemExit("No quedan particulas con presion > 0 dentro de la region pedida.")
        print(f"  Region: y en [{y_lo:.4g}, {y_hi:.4g}] "
              f"({fraccion_altura:.2f} de la altura total [{ymin:.4g}, {ymax:.4g}], desde {desde})")

    todos_p = todos[col_p]
    vmin = max(np.percentile(todos_p, vmin_pct), 1e-3)
    vmax = np.percentile(todos_p, vmax_pct)
    margen = rmax + margen_extra
    return vmin, vmax, (xmin - margen, xmax + margen), (y_lo - margen, y_hi + margen)


def etiqueta_sim(sim_path):
    """Basename del sim_path + hash corto de la ruta completa. El basename
    solo no alcanza: carpetas con el mismo nombre bajo distintas formas o
    campañas (ej. .../Disco/Ratio_0p1_Chi_0p2_W_2p0 y
    .../Pentagono/Ratio_0p1_Chi_0p2_W_2p0) se pisarian los frames."""
    s = str(sim_path)
    h = hashlib.md5(s.encode('utf-8')).hexdigest()[:6]
    return f"{os.path.basename(s.rstrip('/')).replace(' ', '_')}-{h}"


def _recortar_a_region(df_jam, ylim):
    """Se queda solo con las particulas que pueden verse dentro de ylim
    (centro dentro del rango, con un margen de un radio para no perder
    las que asoman desde afuera). Asi no se copia al worker el atasco
    entero cuando solo se va a dibujar una franja."""
    r = np.sqrt(df_jam['area'].max() / np.pi)
    m = (df_jam['pos_y'] >= ylim[0] - r) & (df_jam['pos_y'] <= ylim[1] + r)
    return df_jam[m]


def _generar_un_frame(tarea):
    df_jam, out_path, vmin, vmax, xlim, ylim, col_p = tarea
    fig = gpa.graficar_atasco(df_jam, col_p=col_p, heatmap=True,
                               vmin=vmin, vmax=vmax, xlim=xlim, ylim=ylim)
    fig.savefig(out_path, dpi=150, transparent=True)
    plt.close(fig)
    return out_path


def _armar_tarea(df_jam, cfg, stats):
    """Arma la tarea (o None si el atasco no va) para un atasco completo."""
    ratios_pedidos = cfg['ratios_pedidos']
    ratio_valor = df_jam['_ratio'].iloc[0] if ratios_pedidos is not None else None
    bucket = asignar_bucket(df_jam['chi'].iloc[0], cfg['chis_pedidos'], ratio_valor, ratios_pedidos)
    if bucket is None:
        return None  # chi/ratio que no pedimos, se descarta
    sim_label = etiqueta_sim(df_jam['sim_path'].iloc[0])
    jam_label = str(df_jam['jam_id'].iloc[0])
    out_path = os.path.join(cfg['out_dir'],
                            f"heatmap_{cfg['forma_nombre']}_{bucket}_{sim_label}_{jam_label}.png")
    if cfg['reanudar'] and os.path.exists(out_path):
        stats['salteados'] += 1
        return None
    if ratios_pedidos is not None:
        df_jam = df_jam.drop(columns='_ratio')
    if cfg['recortar']:
        df_jam = _recortar_a_region(df_jam, cfg['ylim'])
    return (df_jam, out_path, cfg['vmin'], cfg['vmax'], cfg['xlim'], cfg['ylim'], cfg['col_p'])


_DATASETS = {}


def _clave_jam(serie):
    """Normaliza jam_id para poder juntar archivos distintos: '00133',
    '133', 133 y 133.0 -> '133'. Los que no son numericos quedan como texto."""
    s = serie.astype(str).str.strip()
    num = pd.to_numeric(s, errors='coerce')
    es_num = num.notna() & (num == num.round())
    return s.where(~es_num, num.fillna(0).astype('int64').astype(str))


def _leer_sim(path, sim_path, chunksize=200_000):
    """Todas las filas de UNA simulacion de un archivo (parquet: filtro de
    pyarrow al leer; csv: recorrido por trozos)."""
    if path.endswith('.parquet'):
        import pyarrow.dataset as ds
        if path not in _DATASETS:
            _DATASETS[path] = ds.dataset(path, format='parquet')
        tabla = _DATASETS[path].to_table(filter=ds.field('sim_path') == sim_path,
                                         use_threads=False)
        return tabla.to_pandas()
    partes = [c[c['sim_path'].astype(str) == sim_path]
              for c in pd.read_csv(path, dtype={'jam_id': str}, chunksize=chunksize)]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def _generar_tareas_por_sim(path, col_filtro, forma, fuente_chicos, sim_paths, cfg, stats,
                            excluir_sim_path=None, invalidos=None, col_ratio=None,
                            ratio_sin_etiqueta=0.1):
    """Version para cuando las particulas CHICAS estan en otro archivo
    (ej. granos grandes en el parquet 'Triangulo', discos chicos en el
    parquet 'Disco'). Procesa simulacion por simulacion: lee los grandes
    de 'path' y los chicos de fuente_chicos para ese mismo sim_path, los
    junta, y arma un atasco completo por jam_id. Solo se usan los atascos
    que tienen granos grandes."""
    path_ch, col_ch, valor_ch = fuente_chicos
    stats.setdefault('salteados', 0)
    stats.setdefault('sin_chicos', [])
    stats.setdefault('chicos_huerfanos', [])
    for sp in sorted(sim_paths):
        grandes = _leer_sim(path, sp)
        if grandes.empty:
            continue
        grandes = grandes[grandes[col_filtro] == forma]
        grandes = _sin_excluidos(grandes, excluir_sim_path, invalidos)
        if grandes.empty:
            continue
        chicos = _leer_sim(path_ch, sp)
        if not chicos.empty:
            chicos = chicos[chicos[col_ch] == valor_ch]
            chicos = _sin_excluidos(chicos, excluir_sim_path)
        if chicos.empty and grandes['chi'].iloc[0] > TOL_CHI:
            stats['sin_chicos'].append(sp)

        # Se agrupa por una clave normalizada de jam_id (los dos archivos
        # pueden tener tipos distintos: '00133' en uno, 133 en otro), pero el
        # nombre del frame usa el jam_id original de los grandes.
        grandes = grandes.assign(jam_id=grandes['jam_id'].astype(str),
                                 _jam_key=_clave_jam(grandes['jam_id']))
        jams_con_grandes = set(grandes['_jam_key'].unique())
        if not chicos.empty:
            chicos = chicos.assign(_jam_key=_clave_jam(chicos['jam_id']))
            huerfanos = ~chicos['_jam_key'].isin(jams_con_grandes)
            if huerfanos.all():
                stats['chicos_huerfanos'].append(
                    (sp, str(grandes['jam_id'].iloc[0]), str(chicos['jam_id'].iloc[0])))
            df = pd.concat([grandes, chicos.drop(columns='jam_id')], ignore_index=True)
        else:
            df = grandes
        if cfg['ratios_pedidos'] is not None:
            df = _agregar_ratio(df, col_ratio, ratio_sin_etiqueta)

        del grandes, chicos
        for jam, df_jam in df.groupby('_jam_key', sort=False):
            if jam not in jams_con_grandes:
                continue
            # los chicos toman el jam_id (original) de los grandes del mismo atasco
            df_jam = df_jam.assign(jam_id=df_jam['jam_id'].dropna().iloc[0]).drop(columns='_jam_key')
            tarea = _armar_tarea(df_jam, cfg, stats)
            if tarea is not None:
                yield tarea
        del df
        _liberar_memoria_arrow()


def _generar_tareas_streaming(path, chunksize, col_filtro, forma, chis_pedidos,
                               vmin, vmax, xlim, ylim, col_p, out_dir, forma_nombre,
                               excluir_sim_path=None, recortar=False, reanudar=False,
                               stats=None, ratios_pedidos=None, col_ratio=None,
                               ratio_sin_etiqueta=0.1, invalidos=None, sim_paths=None):
    """Recorre el archivo en trozos UNA sola vez y entrega una tarea por
    cada atasco completo, ya etiquetada con a que bucket de chi
    pertenece. El ultimo grupo de cada trozo se 'acarrea' al siguiente
    (puede seguir del otro lado del corte) antes de confirmarlo.

    recortar: si True, manda al worker solo las particulas de la region ylim.
    reanudar: si True, saltea los atascos cuyo PNG ya existe en out_dir.
    ratios_pedidos: si no es None, separa/filtra tambien por razon de areas.
    stats: dict opcional donde se cuentan los frames salteados."""
    if stats is None:
        stats = {}
    stats.setdefault('salteados', 0)
    cfg = dict(chis_pedidos=chis_pedidos, ratios_pedidos=ratios_pedidos, out_dir=out_dir,
               forma_nombre=forma_nombre, reanudar=reanudar, recortar=recortar,
               vmin=vmin, vmax=vmax, xlim=xlim, ylim=ylim, col_p=col_p)

    def _tarea_para(df_jam):
        return _armar_tarea(df_jam, cfg, stats)

    carry = None

    for chunk in _iterar_chunks(path, chunksize, sim_paths=sim_paths):
        chunk = chunk[chunk[col_filtro] == forma]
        chunk = _sin_excluidos(chunk, excluir_sim_path, invalidos)
        if ratios_pedidos is not None and not chunk.empty:
            chunk = _agregar_ratio(chunk, col_ratio, ratio_sin_etiqueta)
        if carry is not None:
            chunk = pd.concat([carry, chunk], ignore_index=True)
            carry = None
        if chunk.empty:
            continue
        grupos = list(chunk.groupby(['sim_path', 'jam_id'], sort=False))
        for i, (_, df_jam) in enumerate(grupos):
            if i == len(grupos) - 1:
                carry = df_jam
                continue
            tarea = _tarea_para(df_jam)
            if tarea is not None:
                yield tarea
        del grupos, chunk

    if carry is not None:
        tarea = _tarea_para(carry)
        if tarea is not None:
            yield tarea


def _sumar_particion(args):
    """Decodifica y suma TODA una particion de imagenes en este proceso,
    devolviendo un solo resultado parcial -- asi la comunicacion entre
    procesos es un array por worker, no uno por imagen."""
    archivos_particion, vmin, vmax = args
    norm_dummy = type('N', (), {'vmin': vmin, 'vmax': vmax})()
    t_lut, rgb_lut = sh.construir_lut()
    arbol = cKDTree(rgb_lut)

    suma_P = None
    suma_alpha = None
    for path in archivos_particion:
        P, alpha = sh.decodificar_imagen(path, arbol, t_lut, norm_dummy)
        if suma_P is None:
            suma_P = np.zeros_like(P)
            suma_alpha = np.zeros_like(alpha)
        suma_P += P * alpha
        suma_alpha += alpha
    return suma_P, suma_alpha


ETIQUETAS_COL = {
    'P': ('Presión media $\\langle P \\rangle$', 'presión promedio'),
    'P_reducida': ('Presión reducida media $\\langle P/g \\rangle$', 'presión promedio'),
    'tau': ('Esfuerzo de corte medio $\\langle \\tau \\rangle$', 'esfuerzo de corte promedio'),
    'tau_reducida': ('Esfuerzo de corte reducido medio $\\langle \\tau/g \\rangle$',
                     'esfuerzo de corte promedio'),
}


def etiquetas_col(col):
    """(etiqueta de la barra de color, nombre para el titulo) de la columna graficada."""
    return ETIQUETAS_COL.get(col, (f'$\\langle$ {col} $\\rangle$', f'{col} promedio'))


def calcular_bucket(out_dir, forma_nombre, bucket, vmin, vmax, out_final_base, min_ocupacion,
                    workers=1):
    """Decodifica y promedia los frames de un bucket. Devuelve
    (mapa_medio, ocupacion, n_imagenes) o None si no hay frames, y guarda
    el .npz. vmin/vmax son los de los FRAMES (hacen falta para decodificar
    color -> valor), no los de la escala del mapa final."""
    patron = os.path.join(out_dir, f"heatmap_{forma_nombre}_{bucket}_*.png")
    archivos = sorted(glob.glob(patron))
    if not archivos:
        print(f"  (bucket {bucket}: sin frames, se salta)")
        return None

    n_imagenes = len(archivos)

    if workers > 1 and n_imagenes > 1:
        n_particiones = min(workers, n_imagenes)
        particiones = [archivos[i::n_particiones] for i in range(n_particiones)]
        particiones = [p for p in particiones if p]
        print(f"  {bucket}: decodificando {n_imagenes} imagenes en {len(particiones)} procesos...")
        with mp.Pool(processes=len(particiones)) as pool:
            resultados = pool.map(_sumar_particion, [(p, vmin, vmax) for p in particiones])
        suma_P_ponderada = sum(r[0] for r in resultados)
        suma_alpha = sum(r[1] for r in resultados)
    else:
        suma_P_ponderada, suma_alpha = _sumar_particion((archivos, vmin, vmax))

    ocupacion = suma_alpha / n_imagenes
    with np.errstate(invalid='ignore', divide='ignore'):
        P_media = np.where(suma_alpha > 0, suma_P_ponderada / suma_alpha, np.nan)
    P_media = np.where(ocupacion >= min_ocupacion, P_media, np.nan)

    base, _ = os.path.splitext(out_final_base)
    sufijo = "" if bucket == "todos" else f"_{bucket}"
    np.savez_compressed(f"{base}{sufijo}.npz", P_media=P_media.astype(np.float32),
                        ocupacion=ocupacion.astype(np.float32),
                        n_imagenes=n_imagenes, vmin=vmin, vmax=vmax)
    return P_media, ocupacion, n_imagenes


def escala_de_mapas(mapas, pct_min, pct_max):
    """vmin/vmax de la escala de color de los mapas PROMEDIADOS, a partir de
    percentiles de sus propios valores (todos los buckets juntos, para que
    sean comparables entre si). El promedio sobre atascos comprime mucho el
    rango respecto de los valores por particula, por eso la escala de los
    frames deja sin usar la parte baja (azul) de la paleta."""
    valores = np.concatenate([m[np.isfinite(m) & (m > 0)].ravel() for m in mapas])
    if valores.size == 0:
        raise SystemExit("Los mapas promediados no tienen valores > 0.")
    return float(np.percentile(valores, pct_min)), float(np.percentile(valores, pct_max))


def graficar_bucket(P_media, n_imagenes, forma_nombre, bucket, out_final_base, vmin_mapa,
                    vmax_mapa, col_p):
    base, ext = os.path.splitext(out_final_base)
    sufijo = "" if bucket == "todos" else f"_{bucket}"
    out_final = f"{base}{sufijo}{ext}"

    # Tamaño adaptado a la proporcion de la imagen (una region recortada,
    # mas ancha que alta, no queda con mucho espacio en blanco).
    alto_px, ancho_px = P_media.shape
    ancho_fig = 8.0
    alto_fig = ancho_fig * alto_px / ancho_px + 1.0

    etiqueta, nombre = etiquetas_col(col_p)
    norm = mcolors.LogNorm(vmin=vmin_mapa, vmax=vmax_mapa)
    fig, ax_p = plt.subplots(figsize=(ancho_fig, alto_fig))
    im1 = ax_p.imshow(P_media, origin='upper', cmap='viridis', norm=norm)
    fig.colorbar(im1, ax=ax_p, label=f'{etiqueta} (escala log)',
                 fraction=0.05, pad=0.02, extend='both')
    titulo_bucket = "" if bucket == "todos" else f", {bucket_a_titulo(bucket)}"
    ax_p.set_title(f'{forma_nombre}{titulo_bucket} — {nombre} ({n_imagenes} atascos)')
    ax_p.axis('off')
    fig.tight_layout()
    fig.savefig(out_final, dpi=200)
    plt.close(fig)
    print(f"  Guardado: {out_final}  ({n_imagenes} atascos)")


def _superponer_particion(args):
    """Apila (alpha-composite estandar) todas las imagenes de una
    particion, una encima de la otra, EN EL ORDEN QUE VIENEN -- sin
    decodificar presion ni promediar nada. Donde una imagen mas 'arriba'
    en el orden tiene un pixel opaco, tapa lo que hubiera antes ahi."""
    archivos_particion, tam = args
    base = Image.new('RGBA', tam, (0, 0, 0, 0))
    for path in archivos_particion:
        img = Image.open(path).convert('RGBA')
        base = Image.alpha_composite(base, img)
    return base


def superponer_bucket(out_dir, forma_nombre, bucket, out_final_base, workers=1):
    """Version 'simplemente pegar' para comparar contra el promedio real:
    apila las imagenes de a alfa-compositing, sin decodificar presion.
    El resultado depende del ORDEN de apilado (la ultima imagen que cubre
    un pixel es la que se ve ahi) -- no es un promedio, es nada mas la
    superposicion visual cruda."""
    patron = os.path.join(out_dir, f"heatmap_{forma_nombre}_{bucket}_*.png")
    archivos = sorted(glob.glob(patron))
    if not archivos:
        print(f"  (bucket {bucket}: sin frames para superponer, se salta)")
        return

    tam = Image.open(archivos[0]).size

    if workers > 1 and len(archivos) > 1:
        n_particiones = min(workers, len(archivos))
        particiones = [archivos[i::n_particiones] for i in range(n_particiones)]
        particiones = [p for p in particiones if p]
        with mp.Pool(processes=len(particiones)) as pool:
            parciales = pool.map(_superponer_particion, [(p, tam) for p in particiones])
        resultado = parciales[0]
        for img in parciales[1:]:
            resultado = Image.alpha_composite(resultado, img)
    else:
        resultado = _superponer_particion((archivos, tam))

    base_nombre, ext = os.path.splitext(out_final_base)
    sufijo = "" if bucket == "todos" else f"_{bucket}"
    out_final = f"{base_nombre}{sufijo}_superpuesto{ext}"
    fondo_blanco = Image.new('RGBA', tam, (255, 255, 255, 255))
    resultado_final = Image.alpha_composite(fondo_blanco, resultado)
    resultado_final.convert('RGB').save(out_final)
    print(f"  Guardado: {out_final}  (superposicion cruda, {len(archivos)} imagenes)")


def _promediar_color_particion(archivos_particion):
    """Suma RGB*alpha y alpha de toda una particion -- promedio directo
    de color, sin decodificar a presion (mas simple/rapido que el
    promedio fisico, pero solo sirve para explorar visualmente donde se
    superponen colores de atascos distintos, no como cantidad fisica)."""
    suma_rgb = None
    suma_alpha = None
    for path in archivos_particion:
        img = np.asarray(Image.open(path).convert('RGBA'), dtype=np.float32) / 255.0
        rgb = img[:, :, :3]
        alpha = img[:, :, 3]
        if suma_rgb is None:
            suma_rgb = np.zeros_like(rgb)
            suma_alpha = np.zeros_like(alpha)
        suma_rgb += rgb * alpha[:, :, None]
        suma_alpha += alpha
    return suma_rgb, suma_alpha


def promediar_color_bucket(out_dir, forma_nombre, bucket, out_final_base, workers=1):
    """Promedia directamente los colores (RGB), pesado por alpha, sin
    pasar por la decodificacion a presion -- para que dos atascos que se
    superponen en un pixel se MEZCLEN (en vez de que el ultimo tape al
    anterior, como en superponer_bucket). Vista exploratoria: para la
    cantidad fisica real (presion promedio) usar combinar_bucket."""
    patron = os.path.join(out_dir, f"heatmap_{forma_nombre}_{bucket}_*.png")
    archivos = sorted(glob.glob(patron))
    if not archivos:
        print(f"  (bucket {bucket}: sin frames para promediar color, se salta)")
        return

    n_imagenes = len(archivos)
    if workers > 1 and n_imagenes > 1:
        n_particiones = min(workers, n_imagenes)
        particiones = [archivos[i::n_particiones] for i in range(n_particiones)]
        particiones = [p for p in particiones if p]
        with mp.Pool(processes=len(particiones)) as pool:
            resultados = pool.map(_promediar_color_particion, particiones)
        suma_rgb = sum(r[0] for r in resultados)
        suma_alpha = sum(r[1] for r in resultados)
    else:
        suma_rgb, suma_alpha = _promediar_color_particion(archivos)

    alpha_3d = suma_alpha[:, :, None]
    with np.errstate(invalid='ignore', divide='ignore'):
        rgb_medio = np.where(alpha_3d > 0, suma_rgb / np.maximum(alpha_3d, 1e-12), 1.0)
    ocupacion = np.clip(suma_alpha / n_imagenes, 0, 1)

    rgb_sobre_blanco = rgb_medio * ocupacion[:, :, None] + 1.0 * (1 - ocupacion[:, :, None])
    img_final = (np.clip(rgb_sobre_blanco, 0, 1) * 255).astype(np.uint8)

    base_nombre, ext = os.path.splitext(out_final_base)
    sufijo = "" if bucket == "todos" else f"_{bucket}"
    out_final = f"{base_nombre}{sufijo}_colores{ext}"
    Image.fromarray(img_final, mode='RGB').save(out_final)
    print(f"  Guardado: {out_final}  (promedio de color directo, {n_imagenes} imagenes -- "
          f"vista exploratoria, no reemplaza al promedio de presion real)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True,
                         help='presion_por_particula.csv o .parquet (idealmente ya dividido por '
                              'geometria con dividir_particulas_por_forma.py)')
    parser.add_argument('--forma', required=True, help='forma de grano grande a barrer, ej. Disco')
    parser.add_argument('--chis', nargs='+', default=None,
                         help="Valores de chi a procesar por separado (ej. 0.01 0.1 0.2), o la "
                              "palabra 'auto' para detectar y separar todos los que haya. Sin "
                              "este argumento, mezcla todos los chi en un solo heatmap.")
    parser.add_argument('--ratios', nargs='+', default=None,
                         help="Razones de areas (chica/grande) a procesar por separado (ej. 0.1 0.4), "
                              "o 'auto' para detectar todas. Se combina con --chis: un mapa por "
                              "cada par (ratio, chi). Sin este argumento no se separa por ratio.")
    parser.add_argument('--col_ratio', default=None,
                         help='Nombre de la columna con la razon de areas, si no se detecta sola. '
                              'Sin columna, el ratio se lee del sim_path (Ratio_0p4 -> 0.4).')
    parser.add_argument('--ratio_sin_etiqueta', type=float, default=0.1,
                         help="Ratio asignado a carpetas viejas 'Chi_X_W_Y' sin prefijo 'Ratio_' "
                              "(default: 0.1).")
    parser.add_argument('--csv_chicos', default=None,
                         help="Archivo con las particulas CHICAS (discos), cuando --forma es un "
                              "poligono y los chicos quedaron en otro parquet (ej. "
                              "por_forma/presion_por_particula_Disco.parquet). Se juntan con los "
                              "grandes atasco por atasco. Se ignora si --forma == --forma_chicos.")
    parser.add_argument('--forma_chicos', default='Disco',
                         help="Valor de 'shape' de las particulas chicas (default: Disco).")
    parser.add_argument('--sin_validar_grande', action='store_true',
                         help="Desactiva el descarte de atascos sin granos grandes de --forma "
                              "(solo se aplica si el archivo no tiene columna 'forma_grande' y "
                              "--forma es la forma de los chicos, ej. Disco).")
    parser.add_argument('--umbral_tamanos', type=float, default=0.95,
                         help='Con chi > 0, un atasco es valido si area_min/area_max < este valor '
                              '(o sea, hay grandes y chicos). Default: 0.95.')
    parser.add_argument('--out_dir', required=True, help='carpeta donde guardar los frames individuales')
    parser.add_argument('--out_final', required=True,
                         help='archivo base del/los mapa(s) de calor combinado(s) -- si hay varios '
                              'chi, se les agrega el sufijo _chi<valor> antes de la extension')
    parser.add_argument('--col_p', default='P_reducida',
                         help="Columna a graficar (default: P_reducida). Cualquier columna "
                              "numerica del archivo, ej. P, P_reducida, tau, tau_reducida.")
    parser.add_argument('--escala_mapa', choices=['mapa', 'frames'], default='mapa',
                         help="Escala de color del mapa promediado: 'mapa' (default) = "
                              "percentiles de los valores promediados, compartida entre todos "
                              "los buckets de la corrida; 'frames' = la misma de los frames "
                              "individuales (comportamiento anterior).")
    parser.add_argument('--mapa_pct', type=float, nargs=2, default=[1, 99],
                         metavar=('PCT_MIN', 'PCT_MAX'),
                         help='Percentiles para --escala_mapa mapa (default: 1 99).')
    parser.add_argument('--vmin_mapa', type=float, default=None,
                         help='Fuerza el minimo de la escala del mapa promediado (para usar la '
                              'MISMA escala en corridas de formas distintas).')
    parser.add_argument('--vmax_mapa', type=float, default=None,
                         help='Fuerza el maximo de la escala del mapa promediado.')
    parser.add_argument('--solo_combinar', action='store_true',
                         help='No genera frames: rearma los mapas promediados a partir de los '
                              'frames que ya estan en --out_dir (ej. para cambiar la escala de '
                              'color). Usar los MISMOS argumentos de escala/region/filtros que '
                              'la corrida que genero los frames.')
    parser.add_argument('--vmin_pct', type=float, default=2)
    parser.add_argument('--vmax_pct', type=float, default=98)
    parser.add_argument('--vmin', type=float, default=None, help='fuerza un vmin en vez de calcularlo')
    parser.add_argument('--vmax', type=float, default=None, help='fuerza un vmax en vez de calcularlo')
    parser.add_argument('--xlim', type=float, nargs=2, default=None, metavar=('XMIN', 'XMAX'))
    parser.add_argument('--ylim', type=float, nargs=2, default=None, metavar=('YMIN', 'YMAX'),
                         help='Fuerza el ylim a mano (tiene prioridad sobre --fraccion_altura).')
    parser.add_argument('--fraccion_altura', type=float, default=None,
                         help='Fraccion de la altura del silo a mostrar (ej. 0.25 para un cuarto). '
                              'Sin este argumento se muestra todo el silo.')
    parser.add_argument('--desde', choices=['abajo', 'arriba'], default='abajo',
                         help="Desde que extremo se mide --fraccion_altura (default: 'abajo', "
                              "la zona de la salida si el orificio esta en y minimo).")
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 4)
    parser.add_argument('--min_ocupacion', type=float, default=0.0)
    parser.add_argument('--chunksize', type=int, default=200_000,
                         help='Filas por trozo al leer el csv o parquet. Bajalo si se queda sin '
                              'RAM (ej. 50000).')
    parser.add_argument('--max_en_vuelo', type=int, default=None,
                         help='Maxima cantidad de atascos leidos-pero-no-escritos a la vez '
                              '(default: 2x --workers). Bajalo si se sigue quedando sin RAM.')
    parser.add_argument('--max_tareas_worker', type=int, default=200,
                         help='Cada worker se reinicia despues de generar esta cantidad de '
                              'frames, liberando la memoria acumulada (default: 200).')
    parser.add_argument('--reanudar', action='store_true',
                         help='Saltea los atascos cuyo PNG ya existe en --out_dir (para retomar '
                              'una corrida cortada). Usar los mismos argumentos de escala y region '
                              'que la corrida original.')
    parser.add_argument('--excluir_sim_path', nargs='+', default=None,
                         help='Fragmentos de sim_path a excluir del barrido (coincidencia de '
                              'substring, no hace falta la ruta completa).')
    parser.add_argument('--tambien_superponer', action='store_true',
                         help='Ademas del promedio real, genera una version "cruda" apilando '
                              'las imagenes por alpha-compositing simple.')
    parser.add_argument('--tambien_color', action='store_true',
                         help='Ademas del promedio real, genera una version con los colores '
                              'promediados directamente -- vista exploratoria.')
    args = parser.parse_args()

    if args.fraccion_altura is not None and not (0 < args.fraccion_altura <= 1):
        raise SystemExit("--fraccion_altura tiene que estar en (0, 1].")

    columnas_csv = _columnas_archivo(args.csv)
    if args.col_p not in columnas_csv:
        raise SystemExit(f"--col_p {args.col_p!r} no esta en {args.csv}. Columnas disponibles: "
                         f"{columnas_csv}")

    os.makedirs(args.out_dir, exist_ok=True)
    ya_hay = glob.glob(os.path.join(args.out_dir, f"heatmap_{args.forma}_*.png"))
    if ya_hay and not args.reanudar:
        print(f"AVISO: {args.out_dir} ya tiene {len(ya_hay)} frames de {args.forma}. Se van a "
              f"sobreescribir los que coincidan, pero los que no (ej. de otra region o de chi "
              f"que ahora no pediste) van a quedar y mezclarse en el promedio. Usa otra carpeta, "
              f"vacia esta, o pasa --reanudar si queres retomar una corrida cortada.")
    elif args.reanudar:
        print(f"Modo --reanudar: {len(ya_hay)} frames ya existentes en {args.out_dir} se van a saltear.")

    print(f"Detectando columna de filtro en {args.csv}...")
    col_filtro = _detectar_col_filtro(args.csv)
    if col_filtro == 'shape':
        print("(archivo sin columna 'forma_grande' -- se filtra por 'shape' de cada particula, "
              "y despues se descartan los atascos que no tienen granos GRANDES de la forma "
              "pedida (ver --umbral_tamanos / --sin_validar_grande). Lo ideal igual es "
              "regenerar el archivo con la columna 'forma_grande'.)")

    # Con el archivo dividido por 'shape', solo el archivo de la forma de los
    # CHICOS (Disco) puede tener atascos "contaminados" (discos chicos de
    # mezclas con grandes poligonales). En el archivo de un poligono todas
    # las particulas son granos grandes, y lo que falta son los chicos.
    es_forma_chicos = args.forma == args.forma_chicos
    fuente_chicos = None
    if col_filtro == 'forma_grande' and args.csv_chicos is not None:
        print("(--csv_chicos se ignora: el archivo tiene 'forma_grande', asi que ya trae los "
              "granos grandes y los chicos de cada mezcla.)")
    elif not es_forma_chicos:
        if args.csv_chicos is not None:
            col_ch = _detectar_col_filtro(args.csv_chicos)
            valor_ch = args.forma if col_ch == 'forma_grande' else args.forma_chicos
            fuente_chicos = (args.csv_chicos, col_ch, valor_ch)
            print(f"Particulas chicas: se toman de {args.csv_chicos} "
                  f"(filtro {col_ch} == {valor_ch!r}) y se juntan con los grandes por atasco.")
        elif col_filtro == 'shape':
            print(f"AVISO: --forma {args.forma} sin --csv_chicos: los mapas van a tener SOLO los "
                  f"granos grandes; los {args.forma_chicos} chicos de estas mezclas estan en otro "
                  f"archivo. Pasa --csv_chicos por_forma/presion_por_particula_{args.forma_chicos}.parquet "
                  f"para incluirlos.")

    invalidos = None
    if col_filtro == 'shape' and es_forma_chicos and not args.sin_validar_grande:
        print(f"Buscando atascos sin granos grandes '{args.forma}' (lectura liviana)...")
        invalidos, resumen_atascos = detectar_atascos_sin_grande(
            args.csv, args.forma, col_filtro, args.chunksize,
            excluir_sim_path=args.excluir_sim_path, umbral_tamanos=args.umbral_tamanos)
        _reportar_atascos_sin_grande(resumen_atascos, args.forma)
        if len(invalidos) == 0:
            invalidos = None

    usar_ratio = args.ratios is not None
    col_ratio = None
    if usar_ratio:
        col_ratio = _detectar_col_ratio(args.csv, args.col_ratio)
        if col_ratio is not None:
            print(f"Razon de areas: columna {col_ratio!r} del archivo.")
        else:
            print(f"Razon de areas: sin columna en el archivo, se lee del sim_path "
                  f"(Ratio_XpY; carpetas 'Chi_X_W_Y' sin 'Ratio_' -> {args.ratio_sin_etiqueta}).")

    chi_auto = args.chis is not None and len(args.chis) == 1 and args.chis[0] == 'auto'
    ratio_auto = usar_ratio and len(args.ratios) == 1 and args.ratios[0] == 'auto'

    chis_det = ratios_det = None
    if chi_auto or usar_ratio or fuente_chicos is not None:
        print("Detectando valores de chi/ratio presentes (lectura liviana)...")
        chis_det, ratios_det, combos, sin_ratio = detectar_valores(
            args.csv, args.forma, col_filtro, args.chunksize,
            excluir_sim_path=args.excluir_sim_path, usar_ratio=usar_ratio,
            col_ratio=col_ratio, ratio_sin_etiqueta=args.ratio_sin_etiqueta,
            invalidos=invalidos)
        print(f"  chi presentes: {chis_det}")
        if usar_ratio:
            print(f"  ratios presentes: {ratios_det}")
            print("  combinaciones (ratio, chi) -> cantidad de simulaciones:")
            for (r, c) in sorted(combos):
                print(f"    ratio={r:<8g} chi={c:<8g} {len(combos[(r, c)])} sim_path")
            if sin_ratio:
                print(f"  AVISO: {len(sin_ratio)} sim_path sin ratio reconocible (se descartan "
                      f"al filtrar por ratio). Ejemplos:")
                for sp in sorted(sin_ratio)[:10]:
                    print(f"    {sp}")

    chis_pedidos = None
    if args.chis is not None:
        chis_pedidos = chis_det if chi_auto else [round(float(c), 6) for c in args.chis]
        if chis_det is not None:
            faltan_chi = [c for c in chis_pedidos if _coincide(c, chis_det) is None]
            if faltan_chi:
                print(f"  AVISO: chi pedidos que no aparecen en el archivo: {faltan_chi}")

    ratios_pedidos = None
    if usar_ratio:
        ratios_pedidos = ratios_det if ratio_auto else [round(float(r), 6) for r in args.ratios]
        if not ratios_pedidos:
            raise SystemExit("No se encontro ningun ratio para esta forma.")
        faltan = [r for r in ratios_pedidos if _coincide(r, ratios_det) is None]
        if faltan:
            print(f"  AVISO: ratios pedidos que no aparecen en el archivo: {faltan}")

    # Simulaciones que realmente hacen falta: las de las combinaciones
    # (ratio, chi) pedidas. Las lecturas pesadas se restringen a estas, asi
    # no se decodifica 'coords' de cientos de simulaciones que se descartan.
    sim_paths = None
    if chis_det is not None and (chis_pedidos is not None or ratios_pedidos is not None
                                 or fuente_chicos is not None):
        sim_paths = set()
        for (r, c), sps in combos.items():
            if asignar_bucket(c, chis_pedidos, r, ratios_pedidos) is not None:
                sim_paths |= sps
        if not sim_paths:
            raise SystemExit("Ninguna simulacion coincide con los chi/ratios pedidos.")
        print(f"Se van a leer {len(sim_paths)} simulaciones (de las "
              f"{len(set().union(*combos.values()))} con atascos validos de esta forma).")
    _liberar_memoria_arrow()

    print("Calculando escala de color y limites de ejes (lectura liviana, compartida entre todos los chi)...")
    vmin_calc, vmax_calc, xlim_calc, ylim_calc = calcular_escala_liviana(
        args.csv, args.forma, col_filtro, chis_pedidos, args.col_p,
        args.vmin_pct, args.vmax_pct, args.chunksize, excluir_sim_path=args.excluir_sim_path,
        fraccion_altura=args.fraccion_altura, desde=args.desde,
        ratios_pedidos=ratios_pedidos, col_ratio=col_ratio,
        ratio_sin_etiqueta=args.ratio_sin_etiqueta, invalidos=invalidos,
        sim_paths=sim_paths, fuente_chicos=fuente_chicos)
    _liberar_memoria_arrow()
    vmin = args.vmin if args.vmin is not None else vmin_calc
    vmax = args.vmax if args.vmax is not None else vmax_calc
    xlim = tuple(args.xlim) if args.xlim is not None else xlim_calc
    ylim = tuple(args.ylim) if args.ylim is not None else ylim_calc
    print(f"Escala usada: vmin={vmin:.4g}  vmax={vmax:.4g}  xlim={xlim}  ylim={ylim}")

    # Solo tiene sentido recortar las particulas si se esta mostrando una
    # franja del silo (con el silo completo el recorte no saca nada).
    recortar = args.fraccion_altura is not None or args.ylim is not None

    if args.solo_combinar:
        print("--solo_combinar: se usan los frames que ya estan en --out_dir.")
    else:
        print("Generando frames (una sola pasada por el archivo, separando por chi al vuelo)...")
        stats = {'salteados': 0}
        if fuente_chicos is not None:
            cfg = dict(chis_pedidos=chis_pedidos, ratios_pedidos=ratios_pedidos, out_dir=args.out_dir,
                       forma_nombre=args.forma, reanudar=args.reanudar, recortar=recortar,
                       vmin=vmin, vmax=vmax, xlim=xlim, ylim=ylim, col_p=args.col_p)
            tareas = _generar_tareas_por_sim(args.csv, col_filtro, args.forma, fuente_chicos,
                                             sim_paths, cfg, stats,
                                             excluir_sim_path=args.excluir_sim_path,
                                             invalidos=invalidos, col_ratio=col_ratio,
                                             ratio_sin_etiqueta=args.ratio_sin_etiqueta)
        else:
            tareas = _generar_tareas_streaming(
                args.csv, args.chunksize, col_filtro, args.forma,
                chis_pedidos, vmin, vmax, xlim, ylim, args.col_p,
                args.out_dir, args.forma, excluir_sim_path=args.excluir_sim_path,
                recortar=recortar, reanudar=args.reanudar, stats=stats,
                ratios_pedidos=ratios_pedidos, col_ratio=col_ratio,
                ratio_sin_etiqueta=args.ratio_sin_etiqueta,
                invalidos=invalidos, sim_paths=sim_paths)

        # apply_async + un tope de tareas "en vuelo": nunca hay mas de
        # max_en_vuelo atascos leidos-pero-no-escritos a la vez.
        # maxtasksperchild: recicla cada worker periodicamente para que no
        # acumule memoria a lo largo de miles de figuras.
        max_en_vuelo = args.max_en_vuelo if args.max_en_vuelo is not None else max(args.workers * 2, 2)
        # 'forkserver': los workers NO heredan la memoria del proceso principal
        # (con 'fork', cada worker nuevo arranca como copia del principal, con
        # todo lo que tenga cargado en ese momento).
        ctx = mp.get_context('forkserver')
        with ctx.Pool(processes=args.workers, maxtasksperchild=args.max_tareas_worker) as pool:
            en_vuelo = []
            n_frames = 0
            for tarea in tareas:
                if len(en_vuelo) >= max_en_vuelo:
                    en_vuelo.pop(0).get()
                    n_frames += 1
                    if n_frames % 100 == 0:
                        print(f"  {n_frames} frames generados...")
                en_vuelo.append(pool.apply_async(_generar_un_frame, (tarea,)))
            for r in en_vuelo:
                r.get()
                n_frames += 1
        msg_salteados = f" ({stats.get('salteados', 0)} salteados por ya existir)" if args.reanudar else ""
        print(f"Total: {n_frames} frames generados{msg_salteados}.")
        if stats.get('sin_chicos'):
            print(f"AVISO: {len(stats['sin_chicos'])} simulaciones con chi > 0 no tienen particulas "
                  f"chicas en {args.csv_chicos} (sus mapas quedan solo con granos grandes):")
            for sp in stats['sin_chicos'][:20]:
                print(f"    {sp}")
        if stats.get('chicos_huerfanos'):
            print(f"AVISO: {len(stats['chicos_huerfanos'])} simulaciones tienen particulas chicas en "
                  f"{args.csv_chicos}, pero NINGUNA coincide en jam_id con los atascos de los grandes "
                  f"(sus mapas quedan solo con granos grandes). Ejemplos (sim_path, jam_id grandes, "
                  f"jam_id chicos):")
            for item in stats['chicos_huerfanos'][:20]:
                print(f"    {item}")

    lista_r = [ratio_a_etiqueta(r) for r in ratios_pedidos] if ratios_pedidos is not None else [None]
    lista_c = [chi_a_etiqueta(c) for c in chis_pedidos] if chis_pedidos is not None else [None]
    buckets = ["_".join(p for p in par if p) or "todos"
               for par in itertools.product(lista_r, lista_c)]
    print(f"Combinando {len(buckets)} bucket(s)...")
    resultados_buckets = {}
    for bucket in buckets:
        res = calcular_bucket(args.out_dir, args.forma, bucket, vmin, vmax, args.out_final,
                              args.min_ocupacion, workers=args.workers)
        if res is not None:
            resultados_buckets[bucket] = res
        if args.tambien_superponer:
            superponer_bucket(args.out_dir, args.forma, bucket, args.out_final, workers=args.workers)
        if args.tambien_color:
            promediar_color_bucket(args.out_dir, args.forma, bucket, args.out_final, workers=args.workers)

    if not resultados_buckets:
        print("No hay mapas para graficar.")
        return

    # Escala de color de los mapas promediados, compartida entre buckets.
    if args.escala_mapa == 'frames':
        vmin_mapa, vmax_mapa = vmin, vmax
    else:
        vmin_mapa, vmax_mapa = escala_de_mapas([r[0] for r in resultados_buckets.values()],
                                               args.mapa_pct[0], args.mapa_pct[1])
    if args.vmin_mapa is not None:
        vmin_mapa = args.vmin_mapa
    if args.vmax_mapa is not None:
        vmax_mapa = args.vmax_mapa
    print(f"Escala de los mapas promediados: vmin={vmin_mapa:.4g}  vmax={vmax_mapa:.4g}  "
          f"(para usar la misma en otra forma: --vmin_mapa {vmin_mapa:.4g} --vmax_mapa {vmax_mapa:.4g})")
    for bucket, (P_media, _, n_imagenes) in resultados_buckets.items():
        graficar_bucket(P_media, n_imagenes, args.forma, bucket, args.out_final,
                        vmin_mapa, vmax_mapa, args.col_p)


if __name__ == '__main__':
    main()
