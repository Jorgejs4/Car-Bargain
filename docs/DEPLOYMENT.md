# Despliegue gratuito y scraping periódico

## Recomendación

La opción principal debe ser una VM Oracle Cloud Always Free ejecutando
Docker Compose. El proyecto ya tiene la arquitectura adecuada para ello:

```text
Celery beat → Redis → workers Celery → scrapers → PostgreSQL
                                      └→ análisis texto/CV
```

En producción se deja un único proceso `celery beat` y al menos un worker. El
beat ya contiene las frecuencias del scraper y de los análisis; no hace falta
que GitHub Actions mantenga un proceso vivo.

GitHub Actions se usa para CI, despliegues y, opcionalmente, para disparar la
API. No es un buen lugar para alojar PostgreSQL/Redis: cada job es efímero, la
IP del runner puede ser bloqueada por Akamai y los cron de GitHub pueden
retrasarse.

## GitHub Actions opcional

`.github/workflows/scrape-trigger.yml` lanza cada 15 minutos:

- `autoscout24`;
- `coches-net`;
- `mobile-de`.

Configura estos secretos del repositorio:

```text
CARBARGAINS_API_URL=https://api.tu-dominio.example
CARBARGAINS_INTERNAL_API_KEY=<la misma clave del servidor>
```

El endpoint debe estar detrás de HTTPS. Si se usa este workflow, no se debe
mantener además un beat con esos mismos tres scrapers, porque se duplicarían
las ejecuciones. Para producción recomendamos beat en Oracle y dejar este
workflow solo como disparo manual o contingencia.

## Oracle Cloud

1. Crear una instancia Always Free y abrir únicamente `80/443` en el firewall.
2. Instalar Docker y clonar el repositorio.
3. Copiar `.env.example` a `.env` y configurar PostgreSQL, Redis, `SECRET_KEY`,
   `INTERNAL_API_KEY`, SMTP y, si hace falta, `SCRAPER_PROXY`.
4. Aplicar migraciones:

   ```powershell
   backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
   ```

5. Arrancar API, worker y beat como servicios supervisados por Docker Compose
   o systemd. No ejecutar dos beats.
6. Poner Nginx o Caddy delante de la API con HTTPS y limitar `/internal/*` por
   IP y por `X-Internal-Key`.

El `docker-compose.yml` actual es de desarrollo y solo levanta PostgreSQL y
Redis; queda como trabajo de despliegue crear el Compose de producción con
API, worker, beat, reverse proxy, backups y volúmenes persistentes.

## Análisis de texto sin coste

El filtro de seguridad usa un analizador local `lexicon-v2` y no envía
descripciones a terceros. Detecta averías, accidentes, daños de carrocería,
óxido, repintado, problemas mecánicos/cambio, falta de documentación,
vehículos no circulables y anuncios para piezas/exportación en ES, DE, FR, IT,
NL y EN.

Esto es preferible como primera barrera a una API LLM gratuita: no tiene cuota,
latencia ni fuga de datos y es reproducible. Un proveedor local como Ollama se
puede añadir después para enriquecer `highlights`, pero nunca debe ser el
único filtro de seguridad.

Un anuncio solo entra en la portada de chollos o en `Importar` cuando:

- tiene descripción de detalle guardada y analizada;
- no tiene problema textual explícito;
- no tiene daño visual confirmado;
- no está marcado para revisión manual;
- y supera el margen del motor correspondiente.

Los anuncios sin descripción permanecen visibles en histórico/detalle como
`unknown`, pero no se presentan como chollos.
