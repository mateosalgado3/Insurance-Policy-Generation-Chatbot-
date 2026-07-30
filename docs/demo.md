# Runbook de demo y QA

Este documento deja a Daisy una secuencia reproducible para validar, capturar
evidencia y preparar la presentación.

## 1. Preflight

```powershell
cd "C:\Users\pmate\ANYONEAI\PROYECTO FINAL"
git pull --ff-only origin main
docker compose config
docker compose up --build -d
docker compose ps
```

Validar:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/config
```

Esperado: API saludable, `status=ready`, `indexed_chunks=262` y frontend
disponible en `http://127.0.0.1:8001`.

## 2. Casos de demostración

### Pólizas

```text
/mode policies
¿Qué gastos de hospitalización cubre la póliza cuando ocurre un accidente?
```

Comprobar: ruta `policies`, fuentes PDF y citas `[Fuente N]`.

### Web actual

```text
/mode web
¿Cuáles son las noticias recientes más relevantes del sector asegurador en Ecuador?
```

Comprobar: ruta `web` y al menos una fuente con URL.

### Combinado

```text
/mode combined
Compara la cobertura catastrófica de las pólizas con información actual del sector.
```

Comprobar: secciones separadas “Evidencia de pólizas” e “Información web actual”.

### Fuera de alcance

```text
/mode auto
¿Cuál es la receta de una pizza?
```

Comprobar: rechazo breve, sin inventar fuentes.

### Borrador

```text
/draft POL320200071,POL320150503 | Combine las cláusulas de cobertura hospitalaria y señale los datos que requieren definición humana
```

Comprobar: encabezado `BORRADOR PARA REVISIÓN`, fuentes y disclaimer.

## 3. Evidencia para la presentación

Capturar:

1. `docker compose ps` con ambos servicios saludables.
2. `/ready` mostrando 262 chunks.
3. Una respuesta de póliza con fuentes.
4. Una respuesta web con URL.
5. Una respuesta combinada.
6. Un borrador con disclaimer.
7. Resultado de `python -m pytest -q`.
8. Diagrama de `docs/architecture.md`.

## 4. Cierre

```powershell
docker compose logs --tail 100
docker compose down
```

Registrar cualquier fallo con: pregunta exacta, modo, hora, código HTTP,
captura y últimas líneas de logs. No compartir `.env` ni la API key.
