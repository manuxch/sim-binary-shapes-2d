import pandas as pd
import matplotlib.pyplot as plt

# 1. Cargar los datos
ruta_archivo = '/home/juli/lab/project/sim-binary-shapes-2d/datos_simulaciones/simulation_data/R_2.0/TIRADA2/BARRIDO_2D_DISK_SQUARE/Chi_0p2_W_2p0/estadisticas_arcos.csv' 
df = pd.read_csv(ruta_archivo)

# Crear series que solo contengan valores mayores a 0
datos_tipo_0 = df[df['Particulas_Tipo_0'] > 0]['Particulas_Tipo_0']
datos_tipo_1 = df[df['Particulas_Tipo_1'] > 0]['Particulas_Tipo_1']

# 2. Configurar la figura
plt.figure(figsize=(10, 6))

# 3. Calcular el rango de bins empezando desde 1
max_val = int(max(datos_tipo_0.max() if not datos_tipo_0.empty else 0, 
                  datos_tipo_1.max() if not datos_tipo_1.empty else 0))

# Definir el rango empezando en 1 hasta max + 1
bins = range(1, max_val + 2)

# 4. Crear los histogramas superpuestos con los datos filtrados
plt.hist(datos_tipo_0, bins=bins, alpha=0.5, label='Partículas Tipo 0', align='left', rwidth=0.8, color='blue')
plt.hist(datos_tipo_1, bins=bins, alpha=0.5, label='Partículas Tipo 1', align='left', rwidth=0.8, color='orange')

# 5. Configurar títulos y etiquetas
plt.title('Distribución de Partículas en los Arcos')
plt.xlabel('Cantidad de Partículas en el Arco')
plt.ylabel('Frecuencia (Cantidad de Arcos)')

# Ajustamos los ticks del eje X para que empiecen en 1
plt.xticks(range(1, max_val + 1))

plt.legend()
plt.grid(axis='y', alpha=0.75)

# 6. Guardar el gráfico
plt.savefig('histograma_particulas.png', dpi=300)
