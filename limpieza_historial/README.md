# Limpieza del historial (uso único)

Saca del historial de git las figuras y datos pesados que ya no están en el repo (~1.7 GB → ~46 MB), **exportando antes todas sus versiones** a `processed_data/_historico/` (ignorada por git).

| Paso | Dónde | Qué hace |
|---|---|---|
| `python3 limpieza_historial/1_exportar_historico.py` | tu máquina principal | Exporta todas las versiones a `processed_data/_historico/`. No toca git. |
| `bash limpieza_historial/2_limpiar_historial.sh` | la misma | Backup completo (`../sim-binary-shapes-2d_BACKUP_<fecha>.git`), limpia una copia, verifica que `main` no cambie y, si escribís `SI`, hace el force-push y borra de GitHub las ramas con historial viejo. |
| `bash limpieza_historial/3_actualizar_clon.sh` | **cada** máquina con el repo | Pasa el clon al historial nuevo sin re-clonar; los datos locales no se tocan. |

Requisito del paso 2: `sudo apt install git-filter-repo` (o `pip install --user git-filter-repo`).

Después de la limpieza, `migrar_datos_locales.sh` ya no puede recuperar archivos del historial (su commit de referencia deja de existir). Esta carpeta y ese script se pueden borrar una vez terminado todo.
