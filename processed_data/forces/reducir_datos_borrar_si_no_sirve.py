import pandas as pd
import numpy as np

archivo_entrada = "muestras_cuad_disco_0.4.csv"

print("Cargando el archivo...")
df = pd.read_csv(archivo_entrada, usecols=["chi", "grupo", "f_norm"], dtype={"chi": float, "grupo": str, "f_norm": float})

df["grupo"] = df["grupo"].astype(str).str.strip().str.lower()
df = df[df["f_norm"] > 0] 

# --- EL TRUCO ESTÁ AQUÍ ---
# Elegimos exactamente qué concentraciones mostrar para que no se amontonen.
# Los valores intermedios (ej: 0.08, 0.09) simplemente se ignoran, no se promedian.
valores_permitidos = [0.02, 0.06, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

print("Filtrando para mantener solo los Chi seleccionados...")
# np.isclose asegura que coincida el float aunque haya decimales extra (ej: 0.1000001)
mask = np.isclose(df["chi"].values[:, None], valores_permitidos, atol=1e-4).any(axis=1)
df = df[mask]

def calcular_cajas(x):
    return pd.Series({
        'p05': x.quantile(0.05),
        'q1':  x.quantile(0.25),
        'median': x.quantile(0.50),
        'q3':  x.quantile(0.75),
        'p95': x.quantile(0.95)
    })

print("Calculando estadística pura para los Chi seleccionados...")
stats = df.groupby(["chi", "grupo"])["f_norm"].apply(calcular_cajas).unstack().reset_index()

stats_bulk = stats[stats["grupo"] == "bulk"].sort_values("chi")
stats_arco = stats[stats["grupo"] == "arco"].sort_values("chi")

stats_bulk.to_csv("stats_bulk.csv", index=False, header=False)
stats_arco.to_csv("stats_arco.csv", index=False, header=False)

print("¡Listo! Archivos generados solo con la información limpia y exacta.")