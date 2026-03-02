import pandas as pd
import matplotlib.pyplot as plt
import os

# 1. Definir la carpeta Raíz de búsqueda
# Ajusta esta ruta a la carpeta principal donde están todas las subcarpetas de la simulación
ruta_raiz = '/home/juli/lab/project/sim-binary-shapes-2d/datos_simulaciones/simulation_data/R_2.0/TIRADA2'

print(f"Iniciando procesamiento en: {ruta_raiz}")

# 2. Caminar por todas las subcarpetas
for root, dirs, files in os.walk(ruta_raiz):
    for file in files:
        # Buscamos exactamente el archivo que queremos
        if file == 'estadisticas_arcos.csv':
            ruta_completa_csv = os.path.join(root, file)
            print(f"Procesando: {ruta_completa_csv}")
            
            try:
                # 3. Cargar los datos
                df = pd.read_csv(ruta_completa_csv)

                # Filtrar valores mayores a 0
                datos_tipo_0 = df[df['Particulas_Tipo_0'] > 0]['Particulas_Tipo_0']
                datos_tipo_1 = df[df['Particulas_Tipo_1'] > 0]['Particulas_Tipo_1']

                # Verificar si hay datos para graficar
                if datos_tipo_0.empty and datos_tipo_1.empty:
                    print(f"Salteando {root}: No hay datos > 0.")
                    continue

                # 4. Configurar la figura
                plt.figure(figsize=(10, 6))

                # Calcular rango de bins
                max_0 = datos_tipo_0.max() if not datos_tipo_0.empty else 0
                max_1 = datos_tipo_1.max() if not datos_tipo_1.empty else 0
                max_val = int(max(max_0, max_1))
                
                bins = range(1, max_val + 2)

                # 5. Crear los histogramas
                plt.hist(datos_tipo_0, bins=bins, alpha=0.5, label='Partículas Tipo 0', align='left', rwidth=0.8, color='blue')
                plt.hist(datos_tipo_1, bins=bins, alpha=0.5, label='Partículas Tipo 1', align='left', rwidth=0.8, color='orange')

                # Títulos y etiquetas
                plt.title(f'Distribución de Partículas\n({os.path.relpath(root, ruta_raiz)})')
                plt.xlabel('Cantidad de Partículas en el Arco')
                plt.ylabel('Frecuencia (Cantidad de Arcos)')
                plt.xticks(range(1, max_val + 1))
                plt.legend()
                plt.grid(axis='y', alpha=0.75)

                # 6. GUARDAR EN LA MISMA CARPETA QUE EL CSV
                ruta_guardado = os.path.join(root, 'histograma_particulas.png')
                plt.savefig(ruta_guardado, dpi=300)
                
                # Cerramos la figura para no saturar la memoria RAM (importante con muchos archivos)
                plt.close()
                
            except Exception as e:
                print(f"Error procesando {ruta_completa_csv}: {e}")

print("¡Procesamiento finalizado con éxito!")