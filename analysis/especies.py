"""
Clasificacion grande/chico ('B'/'S') de los granos de un atasco.

Se usa la columna `tipo` del .xy (la especie exacta de cada grano, el indice
del tipo en params.in), no un umbral de radio. Los umbrales de radio fallaban
con mezclas de formas: el inradio o el circunradio de un poligono no se
comparan bien con el radio de un disco (ej. un triangulo grande con inradio
0.39 contra un umbral de 0.41 quedaba como chico; un cuadrado chico con
circunradio 1.12 r_grande quedaba como grande).

Regla:
  - Si chi == 0 o hay una sola especie en el atasco: todo es 'B'.
  - Si no, la especie de mayor area mediana es 'B' y el resto 'S'.
  - Si las areas son iguales (diferencia < 1 %, ratio 1.0) no hay grande ni
    chico: todo es 'B', igual que el criterio anterior.

Uso desde un script de analysis/<carpeta>/:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from especies import especie_por_tipo
"""
import numpy as np
import pandas as pd

TOL_AREA_RELATIVA = 0.01


def especie_por_tipo(tipos, areas, chi=None):
    """tipos, areas: un valor por grano. Devuelve {tipo: 'B' | 'S'}."""
    df = pd.DataFrame({'tipo': np.asarray(tipos), 'area': np.asarray(areas, dtype=float)})
    if df.empty:
        return {}
    area_med = df.groupby('tipo')['area'].median()
    todo_B = {t: 'B' for t in area_med.index}
    if len(area_med) < 2 or (chi is not None and pd.notna(chi) and float(chi) == 0.0):
        return todo_B
    a_max = area_med.max()
    if (a_max - area_med.min()) / a_max < TOL_AREA_RELATIVA:
        return todo_B
    grande = area_med.idxmax()
    return {t: ('B' if t == grande else 'S') for t in area_med.index}


def area_grano(p):
    """Area de un grano de un dict de particula con 'r_eff' (discos) o
    'coords' (poligonos, vertices (n, 2))."""
    coords = p.get('coords')
    if coords is None:
        return float(np.pi * p['r_eff'] ** 2)
    x, y = coords[:, 0], coords[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))
