import pyarrow.parquet as pq

path = "por_forma/presion_por_particula_Disco.parquet"
pf = pq.ParquetFile(path)

areas_por_grupo = {}  # (sim_path, jam_id) -> set de areas, SOLO para chi~=0.0

n_batches = 0
for batch in pf.iter_batches(batch_size=200_000, columns=['sim_path', 'jam_id', 'chi', 'area']):
    df = batch.to_pandas()
    df = df[df['chi'].abs() < 1e-6]
    if df.empty:
        n_batches += 1
        continue
    for (sp, jid), sub in df.groupby(['sim_path', 'jam_id'], sort=False):
        key = (sp, jid)
        areas_por_grupo.setdefault(key, set()).update(sub['area'].round(6).unique().tolist())
    n_batches += 1
    if n_batches % 20 == 0:
        print(f"  {n_batches} trozos procesados, {len(areas_por_grupo)} atascos con chi=0.0 vistos hasta ahora...")

print()
print(f"Atascos con chi=0.0 totales: {len(areas_por_grupo)}")

no_monodisperso = {k: v for k, v in areas_por_grupo.items() if len(v) > 1}
print(f"Atascos con chi=0.0 que tienen MAS DE UNA area (no deberian): {len(no_monodisperso)}")
print()

# Agrupamos por sim_path para ver que FAMILIAS de carpeta estan afectadas,
# no atasco por atasco (puede haber miles del mismo sim_path)
sim_paths_afectados = {}
for (sp, jid), areas in no_monodisperso.items():
    sim_paths_afectados.setdefault(sp, set()).add(tuple(sorted(areas)))

print(f"sim_path distintos afectados: {len(sim_paths_afectados)}")
for sp, combos in list(sim_paths_afectados.items())[:20]:
    print(f"  {sp}")
    for c in combos:
        print(f"     areas: {c}")
