#!/bin/bash
# Wrapper: corre plot_fuerza_por_tipo_contacto.py dentro del contenedor con
# python+numpy/pandas/matplotlib. Mismos argumentos que el graficar_fuerza.sh
# viejo de forces_old/: modo geom1 ratio1 [geom2 ratio2] [geom3 ratio3] [geom4 ratio4]
CONTENEDOR="/home/juli/work/lab/containers/workstation_full.sif"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

apptainer exec "$CONTENEDOR" python3 "$DIR/plot_fuerza_por_tipo_contacto.py" "$@"
