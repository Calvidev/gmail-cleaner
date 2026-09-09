# Alojar Fantasy Tool en la Raspberry Pi

La herramienta web de Python ya está preparada para contenedor, así que en la
Pi no hace falta nada especial más allá de que la imagen sea `arm64`.

Esto **no lo he podido ejecutar**: no tengo acceso a tu Pi. Son las
instrucciones y los archivos, no una instalación comprobada.

## Qué hace falta

- Raspberry Pi 4 o 5 (la 3 va justa con el catálogo de 5 MB en memoria).
- Raspberry Pi OS de 64 bits — importante: con la de 32 bits, `arm64` no arranca.
- Docker: `curl -fsSL https://get.docker.com | sh`

## Puesta en marcha

```bash
git clone https://github.com/Calvidev/gmail-cleaner.git
cd gmail-cleaner
cp .env.example .env        # y ajusta lo que quieras
docker compose up -d --build
```

El `Dockerfile` parte de `python:3.12-slim`, que tiene imagen `arm64`, así que
compila en la Pi sin tocar nada. La caché del catálogo queda en un volumen, que
en la Pi conviene que esté en el SSD y no en la microSD si tienes uno.

Comprobación: `curl http://localhost:8000/api/health` debe responder
`{"status":"ok"}`.

## Que se vea desde fuera

Tres caminos, de menos a más expuesto:

1. **Tailscale** (lo que yo haría). `curl -fsSL https://tailscale.com/install.sh | sh`
   y la Pi queda accesible desde tu iPhone sin abrir un solo puerto del router.
   Gratis para uso personal.
2. **Cloudflare Tunnel**: dominio propio con HTTPS y sin abrir puertos.
   `cloudflared tunnel --url http://localhost:8000`.
3. **Puerto abierto + Caddy**: en `deploy/Caddyfile.example` tienes la
   configuración. Es la que más cuidado pide: si expones esto a internet, pon
   `ADMIN_TOKEN` en el `.env` (protege el vaciado de caché) y ajusta
   `CORS_ORIGINS` a tu dominio.

## Y para los avisos push del futuro

El día que pagues los 99 USD de Apple y quieras avisos con el móvil bloqueado,
la Pi puede ser quien los mande. El esquema sería:

```
Pi (cada 60 s durante los partidos)
  └─ mira el marcador en Sleeper
     └─ si alguien anotó → APNs → Live Activity del iPhone
```

Lo que hace falta: una clave `.p8` de APNs (se genera en developer.apple.com),
el token de la Live Activity que el iPhone manda al arrancarla, y un JWT
firmado con esa clave. Son unas 100 líneas de Python encima de lo que ya hay.

Ojo con una cosa: la Pi tendría que estar encendida y con red durante los
partidos. Si se cae un domingo, te quedas sin avisos. Un Cloudflare Worker en
plan gratuito hace lo mismo sin depender de tu casa, aunque entonces no es "en
la Pi".
