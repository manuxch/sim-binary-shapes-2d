# -*- coding: utf-8 -*-
"""
Estilo comun de TODAS las figuras del proyecto, tomado de graficos_finales.py
(la referencia es 5b-matrix-normalized.pdf).

Uso:
    from estilo_figuras import aplicar_estilo, estilo_sistema, guardar_figura
    aplicar_estilo()          # una vez, antes de crear figuras

Si se cambia un color, un marcador o un tamaño de fuente, se cambia SOLO aca.
"""
import os

import matplotlib.pyplot as plt
import numpy as np

# =============================================================================
# SISTEMAS: color y marcador (paleta Wong, colorblind-safe) y nombre en ingles
# =============================================================================
SYSTEM_STYLE = {
    'Disco(G)-Disco(C)': ('#000000', 'o'),
    'Disco(G)-Tri(C)':   ('#E69F00', '^'),
    'Disco(G)-Cuad(C)':  ('#D55E00', 's'),
    'Disco(G)-Pent(C)':  ('#CC79A7', 'p'),
    'Tri(G)-Disco(C)':   ('#009E73', '^'),
    'Cuad(G)-Disco(C)':  ('#56B4E9', 's'),
    'Pent(G)-Disco(C)':  ('#0072B2', 'p'),
    'Oct(G)-Disco(C)':   ('#999999', '8'),
    'Disco(G)-Oct(C)':   ('#F0E442', '8'),
}

ENGLISH_LABELS = {
    'Disco(G)-Disco(C)': 'Disk-Disk',
    'Disco(G)-Tri(C)':   'Disk-Triangle',
    'Disco(G)-Cuad(C)':  'Disk-Square',
    'Disco(G)-Pent(C)':  'Disk-Pentagon',
    'Tri(G)-Disco(C)':   'Triangle-Disk',
    'Cuad(G)-Disco(C)':  'Square-Disk',
    'Pent(G)-Disco(C)':  'Pentagon-Disk',
    'Oct(G)-Disco(C)':   'Octagon-Disk',
    'Disco(G)-Oct(C)':   'Disk-Octagon',
}

# system_type del master_sim_index.csv -> nombre interno
SYSTEM_NAME_MAP = {
    'Disco-Disco': 'Disco(G)-Disco(C)',
    'Disco-Tri':   'Disco(G)-Tri(C)',
    'Disco-Cuad':  'Disco(G)-Cuad(C)',
    'Disco-Pent':  'Disco(G)-Pent(C)',
    'Tri-Disco':   'Tri(G)-Disco(C)',
    'Cuad-Disco':  'Cuad(G)-Disco(C)',
    'Pent-Disco':  'Pent(G)-Disco(C)',
    'Oct-Disco':   'Oct(G)-Disco(C)',
    'Disco-Oct':   'Disco(G)-Oct(C)',
    'Disco':       'Disco(G)',
    'Tri':         'Tri(G)',
    'Cuad':        'Cuad(G)',
    'Pent':        'Pent(G)',
    'Oct':         'Oct(G)',
}

# Forma del grano grande (como aparece en forma_grande / nombres de parquet)
# -> (nombre en ingles, marcador). Los marcadores son los mismos que usa
# SYSTEM_STYLE para esa forma.
SHAPE_STYLE = {
    'Disco':     ('Disk',     'o'),
    'Triangulo': ('Triangle', '^'),
    'Cuadrado':  ('Square',   's'),
    'Pentagono': ('Pentagon', 'p'),
    'Octogono':  ('Octagon',  '8'),
}

# Regiones (comparar_presion_por_chi.py): vermillion arco, azul roi (Wong)
REGION_STYLE = {
    'arco': ('#D55E00', 'Arch'),
    'roi':  ('#0072B2', 'ROI'),
}

# Mismos kwargs de errorbar que 5b
ERRORBAR_KW = dict(capsize=4)

# Lineas de referencia (chi = 0, valor nominal, homogeneo...)
REF_LINE_KW = dict(color='black', linestyle='--', zorder=1)

FORMATO = 'pdf'

# Curvas de una misma familia ordenada (distintos chi o distintos R_a dentro
# de un mismo sistema): inferno 0.1-0.7, como la figura 2 original.
SEQ_MARKERS = ['o', 's', '^', 'd', 'v', 'p', 'h', 'D']


# =============================================================================
# FUNCIONES
# =============================================================================
def set_plot_fonts(labels: int = 20, ticks: int = 16, legend: int = 14):
    plt.rcParams.update({
        'axes.labelsize': labels,
        'xtick.labelsize': ticks,
        'ytick.labelsize': ticks,
        'legend.fontsize': legend,
        # titulo de leyenda al mismo tamaño que la leyenda (si no, matplotlib
        # usa font.size = 10 y queda chico al lado del resto)
        'legend.title_fontsize': legend,
        'text.usetex': False,
        'mathtext.fontset': 'stix',
        'font.family': 'STIXGeneral',
    })


def _buscar_mplstyle(nombre='figs.mplstyle'):
    """graficos_finales.py usa figs.mplstyle si esta en la carpeta desde la que
    se corre. Aca se busca ahi y, si no, junto a este modulo."""
    for d in (os.getcwd(), os.path.dirname(os.path.abspath(__file__))):
        p = os.path.join(d, nombre)
        if os.path.exists(p):
            return p
    return None


def aplicar_estilo(verbose=False):
    """Mismo orden que main() de graficos_finales.py: fuentes, despues
    figs.mplstyle (si existe), despues usetex apagado."""
    set_plot_fonts()
    p = _buscar_mplstyle()
    if p:
        plt.style.use(p)
        plt.rcParams['text.usetex'] = False
    if verbose:
        print(f"[estilo] figs.mplstyle: {p if p else 'no encontrado (solo fuentes)'}")
    return p


def estilo_sistema(system_type):
    """(color, marcador, etiqueta en ingles) para un system_type del index
    ('Tri-Disco') o un nombre interno ('Tri(G)-Disco(C)')."""
    sistema = SYSTEM_NAME_MAP.get(str(system_type), str(system_type))
    color, marker = SYSTEM_STYLE.get(sistema, ('black', 'o'))
    return color, marker, ENGLISH_LABELS.get(sistema, str(system_type))


def estilo_forma(forma):
    """(etiqueta en ingles, marcador) de una forma de grano grande."""
    return SHAPE_STYLE.get(str(forma), (str(forma), 'o'))


def SEQ_STYLE(n):
    """(colores, marcadores) para n curvas de una familia ordenada."""
    colores = plt.cm.inferno(np.linspace(0.1, 0.7, n)) if n > 1 else plt.cm.inferno([0.1])
    return list(colores), [SEQ_MARKERS[i % len(SEQ_MARKERS)] for i in range(n)]


def anotar_chi(ax, chi, loc='best'):
    """Reemplaza al plt.title: pone chi en un recuadro con el mismo marco y
    tamaño de letra que la leyenda (figuras sin leyenda: violines, boxplots)."""
    return ax.legend(handles=[], title=rf'$\chi = {chi:g}$', loc=loc)


def guardar_figura(path, fig=None, formato=None, dpi=200):
    """Guarda con bbox tight. Si path no tiene extension se usa `formato`
    (default pdf, como save_plot() de graficos_finales.py)."""
    base, ext = os.path.splitext(path)
    if not ext:
        path = f"{base}.{formato or FORMATO}"
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fig = fig or plt.gcf()
    fig.savefig(path, bbox_inches='tight', dpi=dpi)
    plt.close(fig)
    return path
