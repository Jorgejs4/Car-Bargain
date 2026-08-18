# Reanálisis local de anuncios

El reanálisis se puede ejecutar desde el ordenador del operador sin llenar la
cola Celery. El script procesa un anuncio cada vez, espera entre peticiones y
recalcula la valoración al terminar.

La base de datos usada es la definida en `.env`. Para que el frontend online
vea los resultados, `DATABASE_URL` debe apuntar a la base de datos del backend
online, no a una base local.

Antes de empezar, aplicar las migraciones del backend desplegado:

```powershell
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

Reanalizar todos los anuncios de una fuente:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\reanalyze_all_listings.py --source coches_net --delay 1
backend\.venv\Scripts\python.exe backend\scripts\reanalyze_all_listings.py --source autoscout24 --delay 1
backend\.venv\Scripts\python.exe backend\scripts\reanalyze_all_listings.py --source mobile_de --delay 1
```

Sin `--source` procesa todas las fuentes. `--limit N` permite probar primero
con una muestra.

## Reconciliación de estados

El beat ya no marca anuncios como `STALE` o `REMOVED` por reloj. Los estados
solo se reconcilian después de un barrido completo y confirmado:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\reconcile_source_status.py coches_net --max-pages N --confirm-complete
```

No usar este comando si `N` no cubre todas las páginas de la fuente. Las
ejecuciones fallidas, bloqueadas, vacías o parciales no cambian estados.
