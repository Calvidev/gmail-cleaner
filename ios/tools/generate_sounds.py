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
    """Una nota con timbre de marimba: la fundamental más dos armónicos que
    se apagan antes, que es lo que da la sensación de golpe y no de pitido."""
    muestras = []
    total = int(duracion * FRECUENCIA)
    for i in range(total):
        t = i / FRECUENCIA
        # Caída exponencial: fuerte al principio, cola corta.
        envolvente = math.exp(-t * 9)
        # Los primeros milisegundos suben desde cero para que no chasquee.
        ataque = min(1.0, t / 0.004)
        onda = (
            math.sin(2 * math.pi * hz * t)
            + 0.35 * math.sin(2 * math.pi * hz * 2 * t) * math.exp(-t * 16)
            + 0.15 * math.sin(2 * math.pi * hz * 3 * t) * math.exp(-t * 24)
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
        # Se normaliza al 85% para dejar aire y no saturar en el altavoz.
        muestra = int(max(-1.0, min(1.0, valor / pico * 0.85)) * 32767)
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

    # Anotación: tres notas subiendo (do-mi-sol), rápido y alegre.
    escribir(
        "anotacion.wav",
        [
            nota(523.25, 0.5, 0.00),           # do
            nota(659.25, 0.5, 0.075),          # mi
            nota(1046.50, 0.7, 0.15, 0.6),     # do agudo
        ],
        0.9,
    )

    # Aviso: dos notas bajando, más apagado. Para lesiones y noticias, que no
    # son para celebrar.
    escribir(
        "aviso.wav",
        [
            nota(587.33, 0.45, 0.00, 0.45),    # re
            nota(440.00, 0.6, 0.11, 0.45),     # la
        ],
        0.8,
    )

    # Adelantamiento: dos notas iguales, secas. Llama la atención sin celebrar.
    escribir(
        "alerta.wav",
        [
            nota(783.99, 0.3, 0.00, 0.5),      # sol
            nota(783.99, 0.4, 0.13, 0.5),
        ],
        0.6,
    )


if __name__ == "__main__":
    main()
