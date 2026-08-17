# Estado de implementación y siguiente hoja de ruta

Este documento distingue entre código ejecutado en local, funcionalidades
parcialmente operativas y trabajo que necesita datos o infraestructura externa.

## Entrega actual

- Alertas: los filtros configurados fallan cerrado si falta una métrica, se
  respeta `notify_web` y la base de datos impide duplicados por listing.
- Workers: los locks de Redis se liberan siempre; el TTL queda como protección
  ante procesos terminados abruptamente.
- Seguridad: producción rechaza las claves de desarrollo por defecto.
- Email: los valores procedentes de anuncios se escapan antes de generar HTML.
- Frontend: lint, TypeScript y build pasan; el formulario incluye tipo de
  vendedor.
- CI: GitHub Actions ejecuta migraciones, tests, Ruff, lint, typecheck y build.
- Migraciones: la restricción de deduplicación de notificaciones está incluida
  en Alembic.

## Pendientes por prioridad

### P0: operación segura

1. Incorporar autenticación real y sustituir el usuario implícito `me` por un
   `user_id` autenticado.
2. Crear Compose de producción con API, frontend, worker, beat, proxy HTTPS,
   volúmenes y backups.
3. Añadir rate limiting, rotación de claves y métricas persistentes de jobs.
4. Probar el flujo real de emails con un proveedor SMTP de pruebas.

**Aceptación:** un usuario no puede leer ni modificar las alertas de otro,
los servicios se levantan con un único comando y un fallo de scraping queda
visible con métricas y logs estructurados.

### P1: valoración y economía del deal

1. Persistir comparables ES en una tabla de observaciones de mercado.
2. Calcular P10/P50/P90 con un mínimo de comparables y guardar la versión de la
   valoración en `price_predictions`.
3. Separar temporalmente entrenamiento, validación y test; nunca evaluar sobre
   las mismas observaciones usadas para predecir.
4. Crear `tax_rules`, `transport_rates` y `repair_estimates` versionadas por
   país y año.
5. Completar el beneficio neto y ROI con reparaciones, preparación, costes
   financieros y liquidez.

**Aceptación:** cada predicción expone mercado, fecha, versión, intervalo,
confianza y número de comparables; un caso de prueba reproduce el ejemplo del
`README.md` y cambia al variar una regla fiscal.

### P2: robustez de datos

1. Añadir tests de contrato con fixtures nuevas cuando cambie el HTML de cada
   fuente.
2. Registrar ejecución, páginas, anuncios descartados, latencia y motivo de
   bloqueo por scraper.
3. Optimizar consultas N+1 de valoración, matching y alertas mediante joins y
   precarga.
4. Añadir revisión manual persistente para contradicciones de texto y CV.

**Aceptación:** una ejecución parcial no marca anuncios como retirados, no
   duplica snapshots y permite reproducir una ingesta desde raw.

### P3: cobertura de fuentes y despliegue

1. Verificar AutoScout24 Alemania con una ejecución real independiente.
2. Implementar Otomoto con fixture, parser, mapper, task y endpoint interno.
3. Mantener mobile.de live detrás de una IP/proxy permitida; Wayback seguirá
   siendo el fallback histórico.
4. Añadir smoke tests post-despliegue y rollback de migraciones.

**Aceptación:** el pipeline Alemania→España funciona durante 24 horas con
reintentos, límites de frecuencia y datos raw conservados.

## No se debe hacer todavía

- Entrenar un modelo ML antes de disponer de suficientes observaciones
  históricas etiquetadas y un split temporal.
- Interpretar una desaparición como venta.
- Presentar un anuncio sin descripción o con señales desconocidas como libre de
  daños.
- Desplegar PostgreSQL o Redis expuestos a Internet.
- Ejecutar simultáneamente Celery beat y el workflow de disparo periódico de
  GitHub Actions.
