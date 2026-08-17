# Despliegue en Oracle Cloud Always Free

Guía para ejecutar Car-Bargains fuera del ordenador local usando Oracle Cloud
Always Free. El objetivo es mantener API, PostgreSQL/PostGIS, Redis, workers
Celery y Celery Beat funcionando de forma continua.

## 1. Arquitectura objetivo

```text
Internet
   |
   v
Nginx/Caddy + HTTPS
   |
   +--> Next.js frontend
   +--> FastAPI :8000
             |
             +--> PostgreSQL/PostGIS
             +--> Redis
             +--> Celery worker
             +--> Celery Beat
```

GitHub Actions se usará para CI/CD y, opcionalmente, para disparar scrapers.
No se debe usar GitHub Actions como servidor de PostgreSQL o Redis: los
runners son efímeros y sus IPs compartidas pueden ser bloqueadas por los
portales.

## 2. Crear la cuenta Oracle

1. Crear una cuenta en [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/).
2. Elegir una región cercana a España cuando haya disponibilidad.
3. Activar la autenticación multifactor de la cuenta.
4. Crear un **Compartment** para el proyecto, por ejemplo `car-bargains`.
5. Crear una instancia Compute Always Free:
   - Ubuntu 22.04 o Ubuntu 24.04.
   - `VM.Standard.E2.1.Micro` si se quiere la opción más conservadora.
   - `VM.Standard.A1.Flex` si hay cuota Ampere disponible.
   - Para CV local, Ampere con más memoria es preferible, pero sigue siendo
     necesario controlar el consumo de Torch.
6. Durante la creación, generar o subir una clave SSH.
7. Guardar la IP pública de la instancia y la clave privada SSH fuera del
   repositorio.

La clave SSH no forma parte del `.env`. Sirve únicamente para administrar la
máquina.

## 3. Red y firewall

En Oracle añade reglas de entrada únicamente para:

| Puerto | Uso | Origen recomendado |
|---|---|---|
| 22 | SSH | Solo tu IP pública |
| 80 | Redirección HTTP a HTTPS | Internet |
| 443 | Frontend/API | Internet |

No abras a Internet los puertos `5432` ni `6379`. PostgreSQL y Redis deben
comunicarse únicamente dentro de la red Docker.

En Ubuntu, activa también el firewall local:

```bash
sudo ufw allow from TU_IP_PUBLICA to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## 4. Instalar dependencias en Oracle

Conéctate por SSH:

```bash
ssh -i ~/.ssh/car-bargains-oracle.key ubuntu@IP_PUBLICA
```

Instala Docker y utilidades básicas:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git openssl
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

Cierra y vuelve a abrir la sesión SSH para que se aplique el grupo Docker.

Clona el repositorio:

```bash
sudo mkdir -p /opt/car-bargains
sudo chown -R "$USER":"$USER" /opt/car-bargains
git clone URL_DEL_REPOSITORIO /opt/car-bargains
cd /opt/car-bargains
```

## 5. Crear credenciales seguras

Genera valores aleatorios para las claves internas:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Usa el primer valor como `SECRET_KEY` y el segundo como
`INTERNAL_API_KEY`. No reutilices contraseñas personales ni los valores de
desarrollo del repositorio.

## 6. Configurar el `.env`

Copia la plantilla:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Configuración mínima para un Compose productivo. Los nombres `db` y `redis`
son los nombres DNS internos de Docker Compose:

```env
ENVIRONMENT=production

DATABASE_URL=postgresql+psycopg://carbargains:CONTRASENA_DB@db:5432/carbargains
REDIS_URL=redis://redis:6379/0

SECRET_KEY=VALOR_GENERADO_CON_OPENSSL
INTERNAL_API_KEY=VALOR_GENERADO_CON_OPENSSL

SCRAPER_SCHEDULER=celery
SCRAPER_PROXY=

CV_ENABLED=true
DAMAGE_PROB_MIN=0.65
CONTRADICTION_TOLERANCE=0.3

CORS_ORIGINS=["https://app.tu-dominio.es"]
```

### Significado y origen de cada credencial

| Variable | Cómo obtenerla | ¿Obligatoria? |
|---|---|---|
| `DATABASE_URL` | La defines tú. `carbargains` y la contraseña son credenciales internas de PostgreSQL. | Sí |
| `REDIS_URL` | No requiere credencial si Redis no se expone fuera de Docker. | Sí |
| `SECRET_KEY` | Generarla con `openssl rand -hex 32`. | Sí |
| `INTERNAL_API_KEY` | Generarla con `openssl rand -hex 32`. | Sí |
| `CORS_ORIGINS` | URL pública donde se servirá el frontend. | Sí en producción |
| `R2_ENDPOINT` | Cloudflare Dashboard → R2 → Overview → S3 API. | No, recomendado |
| `R2_ACCESS_KEY` | Cloudflare Dashboard → R2 → Manage R2 API Tokens → Create API token. | Solo si se usa R2 |
| `R2_SECRET_KEY` | Se muestra una sola vez al crear el token R2. | Solo si se usa R2 |
| `R2_BUCKET` | Nombre del bucket creado en R2. | Solo si se usa R2 |
| `SMTP_HOST` | Proveedor SMTP elegido. | Solo para email |
| `SMTP_USER` | Cuenta SMTP del proveedor. | Solo para email |
| `SMTP_PASSWORD` | Contraseña SMTP o app password. | Solo para email |
| `ALERT_EMAIL_TO` | Email que recibirá las alertas. | Solo para email |
| `SCRAPER_PROXY` | Proveedor de proxy residencial. | Solo mobile.de |

### Cloudflare R2 gratuito

R2 sirve para que raw HTML/JSON e imágenes no dependan del disco de la VM:

1. Crear una cuenta Cloudflare.
2. Abrir **R2 Object Storage**.
3. Crear un bucket privado, por ejemplo `car-bargains-raw`.
4. Crear un token API con permisos únicamente sobre ese bucket.
5. Copiar endpoint, Access Key ID y Secret Access Key al `.env`.

No publiques las claves R2 ni las guardes en GitHub salvo como Secrets.

### SMTP gratuito

Opciones posibles dependen de sus límites y políticas vigentes:

- Gmail: activar 2FA y crear una **App Password**. No uses la contraseña
  normal de Gmail.
- Brevo/Resend: crear una cuenta, verificar el remitente y usar sus credenciales
  SMTP gratuitas si siguen disponibles para tu cuenta.

Ejemplo Gmail:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-cuenta@gmail.com
SMTP_PASSWORD=APP_PASSWORD_DE_16_CARACTERES
SMTP_USE_TLS=true
SMTP_FROM=tu-cuenta@gmail.com
ALERT_EMAIL_TO=tu-cuenta@gmail.com
```

### Proxy de mobile.de

`mobile.de` está bloqueado por Akamai desde muchas IPs de datacenter. Oracle y
GitHub no solucionan ese bloqueo. Si se configura un proxy residencial:

```env
SCRAPER_PROXY=http://usuario:contraseña@host:puerto
```

No hay que inventar una credencial gratuita: los proxies residenciales suelen
ser servicios externos. Sin proxy, usa el fallback histórico de Wayback y
mantén AutoScout24/coches.net como fuentes live.

## 7. Migraciones y primer arranque

El Compose productivo incluye API, worker, Beat, frontend, Caddy, db y Redis.
Antes del primer arranque, configura `POSTGRES_PASSWORD` y `APP_DOMAIN`, apunta
el DNS del dominio a la IP pública de Oracle y ejecuta:

```bash
docker compose -f docker-compose.prod.yml up -d db redis
docker compose -f docker-compose.prod.yml run --rm api \
  alembic -c alembic.ini upgrade head
docker compose -f docker-compose.prod.yml up -d api worker beat frontend caddy
```

Debe existir **un solo proceso Beat**. Dos Beats duplicarían scrapers, análisis
y alertas.

Verifica:

```bash
docker compose -f docker-compose.prod.yml ps
curl -fsS https://api.tu-dominio.es/health
docker compose -f docker-compose.prod.yml logs --tail=100 worker
docker compose -f docker-compose.prod.yml logs --tail=100 beat
```

La primera conexión HTTPS puede tardar unos segundos mientras Caddy obtiene el
certificado. Debe existir un único proceso Beat.

## 8. GitHub Actions

Para CI añade el workflow incluido en `.github/workflows/ci.yml`. Para disparar
scrapers desde GitHub configura estos Secrets:

```text
CARBARGAINS_API_URL=https://api.tu-dominio.es
CARBARGAINS_INTERNAL_API_KEY=el_mismo_valor_de_INTERNAL_API_KEY
```

Si GitHub Actions será el scheduler, configura en Oracle:

```env
SCRAPER_SCHEDULER=github
```

Si Celery Beat está activo en Oracle, usa:

```env
SCRAPER_SCHEDULER=celery
```

No habilites ambos schedulers para los mismos scrapers.

## 9. Backups y observabilidad

Antes de producción real:

```bash
docker exec carbargains-db pg_dump \
  -U carbargains -d carbargains -Fc \
  > backups/carbargains-$(date +%F).dump
```

El script `scripts/backup_postgres.sh` automatiza el backup y elimina ficheros
con más de `RETENTION_DAYS` días:

```bash
BACKUP_DIR=/opt/backups/car-bargains RETENTION_DAYS=14 \
  bash scripts/backup_postgres.sh
```

Programa el script con cron y copia después los dumps a R2 o a otro destino
fuera de la VM. La restauración debe probarse periódicamente. También hay que
añadir:

- rotación de logs;
- métricas de éxito/fallo por scraper;
- número de anuncios creados, actualizados, stale y removed;
- duración de tareas Celery;
- alertas cuando Redis, PostgreSQL o el worker no respondan;
- monitorización de espacio de disco.

## 10. Orden de trabajo posterior

El MVP es funcional en local, pero todavía no debe considerarse un radar de
importación fiable para producción. El orden recomendado es:

1. Corregir y consolidar Ruff, lint, migraciones y CI.
2. Completar el Deal Engine con beneficio neto, reparaciones y reglas fiscales
   versionadas por país y año.
3. Mejorar la valoración con comparables, percentiles y validación temporal.
4. Implementar autenticación real y revisar deduplicación/reenvío de alertas.
5. Crear Compose de producción, HTTPS, backups y observabilidad.
6. Verificar fuentes adicionales y operación live continua.
7. Medir precisión de los chollos con revisiones manuales antes de automatizar
   decisiones de compra.

Nunca se debe interpretar una valoración como garantía de beneficio. Las
señales textuales, CV y motores de precio sirven para priorizar revisión
humana, no para cerrar una compra automáticamente.
