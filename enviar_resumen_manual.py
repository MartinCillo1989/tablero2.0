"""
Envío MANUAL del resumen diario a los supervisores que elijas.

Uso:
    python enviar_resumen_manual.py

Te muestra la lista de supervisores definidos en SUPERVISOR_VENDEDORES
(app.py) y te deja tildar a cuáles les querés mandar el resumen ahora mismo,
sin esperar al scheduler ni mandarle a todos.

Colocar este archivo en la raíz del proyecto (mismo nivel que app.py).
"""

import sys
import os

# Aseguramos que el proyecto esté en el path (por si se corre desde otro lado)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import VENDEDOR_MAP, SUPERVISOR_VENDEDORES
from utils.telegram_bot import enviar_resumen_supervisores, _cargar_chats


def elegir_supervisores():
    todos = list(SUPERVISOR_VENDEDORES.keys())
    chats = _cargar_chats()

    print("\nSupervisores disponibles:\n")
    for i, sup in enumerate(todos, start=1):
        estado = "✅ registrado" if sup in chats else "⚠️  NO registrado en Telegram"
        print(f"  {i}. {sup}  ({estado})")

    print("\nEscribí los números separados por coma (ej: 1,3) de a quién enviarle,")
    print("o 'todos' para mandarle a todos.\n")

    resp = input("Enviar a: ").strip().lower()

    if resp == "todos":
        return todos

    seleccionados = []
    for parte in resp.split(","):
        parte = parte.strip()
        if not parte.isdigit():
            continue
        idx = int(parte) - 1
        if 0 <= idx < len(todos):
            seleccionados.append(todos[idx])

    return seleccionados


def main():
    seleccionados = elegir_supervisores()

    if not seleccionados:
        print("\nNo se seleccionó ningún supervisor válido. Nada para enviar.")
        return

    print(f"\nSe va a enviar el resumen a: {', '.join(seleccionados)}")
    confirmar = input("Confirmás? (s/n): ").strip().lower()
    if confirmar != "s":
        print("Cancelado.")
        return

    # Armamos un sub-diccionario solo con los supervisores elegidos,
    # reutilizando la función existente sin tocar telegram_bot.py
    subset = {sup: SUPERVISOR_VENDEDORES[sup] for sup in seleccionados}

    enviados = enviar_resumen_supervisores(VENDEDOR_MAP, subset)
    print(f"\nListo. Resumen enviado a {enviados} de {len(seleccionados)} supervisor/es seleccionados.")


if __name__ == "__main__":
    main()