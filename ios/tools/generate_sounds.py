#!/usr/bin/env python3
"""Genera los sonidos de notificación de la app.

iOS solo admite WAV, CAF o AIFF de menos de 30 segundos, y tienen que ir
dentro del paquete de la app. Se sintetizan aquí para no depender de un banco
de sonidos con licencia, y para poder retocarlos cambiando cuatro números.

Uso:  python3 tools/generate_sounds.py
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "SleeperScore"
FRECUENCIA = 44_100


def nota(hz: float, duracion: float, inicio: float, volumen: float = 0.5) -> list:
    """Una nota suave, de campana lejana.

    Estos sonidos se oyen decenas de veces una tarde de domingo, así que están
    hechos para pasar desapercibidos a la décima vez:

    - Ataque lento (25 ms). Un ataque seco suena a alerta; uno lento, a que
      algo aparece.
    - Un solo armónico y flojo. Con tres, la nota suena a juguete.
    - Caída larga y suave, sin cola metálica.
    """
    muestras = []
    total = int(duracion * FRECUENCIA)
    for i in range(total):
        t = i / FRECUENCIA
        envolvente = math.exp(-t * 4.5)
        ataque = min(1.0, t / 0.025)
        onda = (
            math.sin(2 * math.pi * hz * t)
            + 0.12 * math.sin(2 * math.pi * hz * 2 * t) * math.exp(-t * 9)
        )
        muestras.append((inicio + t, onda * envolvente * ataque * volumen))
    return muestras


def mezclar(capas: list, duracion: float) -> bytes:
    """Suma las capas en una sola pista y la pasa a 16 bits."""
    total = int(duracion * FRECUENCIA)
    pista = [0.0] * total
    for capa in capas:
        for t, valor in capa:
            indice = int(t * FRECUENCIA)
            if 0 <= indice < total:
                pista[indice] += valor

    pico = max((abs(v) for v in pista), default=1.0) or 1.0
    datos = bytearray()
    for valor in pista:
        # Al 55%: por debajo de los sonidos del sistema, que es la idea.
        muestra = int(max(-1.0, min(1.0, valor / pico * 0.55)) * 32767)
        datos += struct.pack("<h", muestra)
    return bytes(datos)


def escribir(nombre: str, capas: list, duracion: float) -> None:
    ruta = DESTINO / nombre
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(FRECUENCIA)
        archivo.writeframes(mezclar(capas, duracion))
    print(f"  {nombre}  {duracion:.2f} s  {ruta.stat().st_size / 1024:.0f} KB")


def main() -> None:
    print("Sonidos:")

    # Anotación: dos notas subiendo una quinta, en registro medio-grave. Lo
    # justo para reconocerlo sin que parezca una fanfarria.
    escribir(
        "anotacion.wav",
        [
            nota(392.00, 0.55, 0.00, 0.5),     # sol
            nota(587.33, 0.75, 0.09, 0.42),    # re
        ],
        0.95,
    )

    # Aviso: una sola nota grave, apagada. Para lesiones y noticias.
    escribir(
        "aviso.wav",
        [
            nota(329.63, 0.8, 0.00, 0.42),     # mi grave
        ],
        0.9,
    )

    # Adelantamiento: dos notas iguales, separadas. Llama la atención sin
    # celebrar y sin sobresaltar.
    escribir(
        "alerta.wav",
        [
            nota(493.88, 0.45, 0.00, 0.45),    # si
            nota(493.88, 0.6, 0.16, 0.38),
        ],
        0.85,
    )


if __name__ == "__main__":
    main()
