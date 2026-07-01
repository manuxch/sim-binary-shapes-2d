import pandas as pd
import os

def normalizar_sistema(txt):
    txt = str(txt).lower()
    if 'cuad' in txt: return 'Cuadrado'
    if 'tri' in txt: return 'Triangulo'
    if 'pent' in txt: return 'Pentagono'
    if 'disc' in txt: return 'Disco'
    return 'Otros'

print("[+] Extrayendo la matriz completa de fuerzas para Gnuplot...")

# 1. Cargar tamaño de avalancha <s> (S_mean)
df_flujo = pd.read_csv("../1_avalanche_data/estadisticas_flujo_agregadas.csv")
df_flujo['sistema_corto'] = df_flujo['sistema'].apply(normalizar_sistema)
df_flujo_clean = df_flujo.groupby(['sistema_corto', 'chi'])['S_mean'].mean().reset_index()

# 2. Cargar arcos y calcular la Tortuosidad media
df_arcos = pd.read_csv("../1_avalanche_data/resultados_completos_arcos.csv")
df_arcos['sistema_corto'] = df_arcos['system_type'].apply(normalizar_sistema)
df_arcos_mean = df_arcos.groupby(['sistema_corto', 'chi'])['Tortuosidad'].mean().reset_index()

# 3. Cargar las fuerzas de contacto (Bulk y ROI completos)
fuerzas_list = []
archivos_fuerzas = {
    'Disco': 'filtrado_disco_disco.csv',
    'Cuadrado': 'filtrado_cuadrados_disco.csv',
    'Triangulo': 'filtrado_triangulos_disco.csv',
    'Pentagono': 'filtrado_pentagonos_disco.csv'
}

columnas_fuerzas = [
    'chi', 
    'mean_Fn_bulk', 'mean_Fn_bulk_BB', 'mean_Fn_bulk_SS',  # Datos del Bulk completo
    'mean_Fn_roi',  'mean_Fn_roi_BB',  'mean_Fn_roi_SS'    # Datos del ROI completo
]

for sis, archivo in archivos_fuerzas.items():
    if os.path.exists(archivo):
        df_f = pd.read_csv(archivo)
        # Extraemos solo las columnas deseadas
        df_f = df_f[columnas_fuerzas].copy()
        df_f['sistema_corto'] = sis
        fuerzas_list.append(df_f)
    else:
        print(f"[-] Advertencia: No se encontró {archivo}")

df_fuerzas = pd.concat(fuerzas_list, ignore_index=True)

# 4. Fusionar todo
m1 = pd.merge(df_flujo_clean, df_arcos_mean, on=['sistema_corto', 'chi'], how='inner')
df_final = pd.merge(m1, df_fuerzas, on=['sistema_corto', 'chi'], how='inner')

# Guardar con formato plano para Gnuplot
df_final.to_csv("datos_combinados.csv", sep=",", index=False)
print("[+] ¡Archivo 'datos_combinados.csv' generado con éxito con sus columnas reales!")