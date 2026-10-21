"""Política de contraseñas nuevas. El backend es la autoridad: el indicador visual del frontend
solo orienta a la persona mientras escribe."""

import re

from app.acceso.dominio.modelos import normalizar_nombre_usuario

LONGITUD_MINIMA = 10
LONGITUD_MAXIMA = 128

# Contraseñas frecuentes en filtraciones y variantes locales obvias.
COMUNES = frozenset(
    {
        "1234567890",
        "12345678910",
        "0123456789",
        "contrasena1",
        "contraseña1",
        "contrasena123",
        "contraseña123",
        "password123",
        "password1234",
        "qwerty12345",
        "qwertyuiop1",
        "abc1234567",
        "abcdef1234",
        "deconsta123",
        "deconsta2026",
        "peru123456",
        "lima123456",
        "admin12345",
        "iloveyou12",
        "1q2w3e4r5t",
    }
)


def evaluar(contrasena: str, *, nombre_usuario: str) -> dict[str, str]:
    """Devuelve los requisitos incumplidos como {código: mensaje}; vacío si la contraseña sirve."""
    incumplidos: dict[str, str] = {}
    if len(contrasena) < LONGITUD_MINIMA:
        incumplidos["LONGITUD_MINIMA"] = f"Usa al menos {LONGITUD_MINIMA} caracteres."
    if len(contrasena) > LONGITUD_MAXIMA:
        incumplidos["LONGITUD_MAXIMA"] = f"Usa como máximo {LONGITUD_MAXIMA} caracteres."
    if not re.search(r"[^\W\d_]", contrasena):
        incumplidos["SIN_LETRA"] = "Incluye al menos una letra."
    if not re.search(r"\d", contrasena):
        incumplidos["SIN_NUMERO"] = "Incluye al menos un número."
    if contrasena.strip() != contrasena:
        incumplidos["ESPACIOS_EXTREMOS"] = "No empieces ni termines con espacios."
    usuario = normalizar_nombre_usuario(nombre_usuario)
    if usuario and usuario in contrasena.lower():
        incumplidos["CONTIENE_USUARIO"] = "No incluyas tu nombre de usuario."
    if contrasena.lower() in COMUNES or len(set(contrasena)) <= 2:
        incumplidos["COMUN"] = "Es demasiado común o predecible; elige otra."
    return incumplidos
