"""Ejecución de tareas lentas fuera del hilo de la interfaz.

Tk no es seguro entre hilos: cualquier contacto con widgets o diálogos
debe ocurrir en el hilo que ejecuta ``mainloop``. Este módulo lanza el
trabajo pesado (backups, impresión, E/S de red...) en un hilo demonio y
entrega el resultado de vuelta mediante un sondeo con ``after``, de modo
que el hilo secundario jamás toca Tcl.
"""

import threading


def en_hilo(widget, trabajo, al_terminar):
    """Ejecuta *trabajo()* en un hilo secundario.

    Al terminar llama ``al_terminar(resultado, None)`` o
    ``al_terminar(None, excepcion)`` desde el bucle de eventos de Tk,
    usando *widget* solo como ancla para ``after``.

    El hilo es demonio: si la app se cierra a mitad de una tarea, el
    proceso no queda colgado esperándola.
    """
    contenedor = {}

    def envoltura():
        try:
            contenedor["resultado"] = trabajo()
            contenedor["error"] = None
        except Exception as e:  # el fallo viaja a la UI, no revienta aquí
            contenedor["resultado"] = None
            contenedor["error"] = e
        contenedor["listo"] = True

    threading.Thread(
        target=envoltura, daemon=True, name="reyger-tarea"
    ).start()

    def verificar():
        if contenedor.get("listo"):
            al_terminar(contenedor["resultado"], contenedor["error"])
        else:
            widget.after(60, verificar)

    widget.after(60, verificar)
