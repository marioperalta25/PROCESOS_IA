"""Ejecucion cooperativa y cierre de una salida del procesamiento local."""


def ejecutar_trabajo(hilo) -> None:
    """Cierra archivos antes de clasificar la carpeta y notificar el resultado."""
    error = None
    try:
        hilo._coordinador.iniciar_o_reanudar()
        while not hilo._cancelado:
            hilo._mutex.lock()
            while hilo._pausado and not hilo._cancelado:
                hilo._condicion_pausa.wait(hilo._mutex)
            cancelado = hilo._cancelado
            hilo._mutex.unlock()
            if cancelado or not hilo._coordinador.procesar_siguiente_lote():
                break
        if hilo._cancelado:
            hilo._coordinador.cancelar()
    except Exception as fallo:
        error = fallo
    finally:
        try:
            hilo._coordinador.cerrar()
        except Exception as fallo:
            error = error or fallo

    estado = "fallidos" if error else ("cancelados" if hilo._cancelado else "completados")
    if hilo._salida is not None:
        try:
            ruta = hilo._salida.finalizar(estado)
            hilo.senial_mensaje.emit(f"[INFO] Salida del trabajo: {ruta}")
        except Exception as fallo:
            error = error or fallo
    if error is not None:
        hilo.senial_fase_cambiada.emit("[ERROR]")
        hilo.senial_error.emit(f"[ERROR] Fallo en la ejecucion: {error}")
    elif hilo._cancelado:
        hilo.senial_fase_cambiada.emit("[CANCELADO]")
        hilo.senial_finalizado.emit(False, "[ALERTA] Procesamiento cancelado por el usuario")
    else:
        hilo.senial_fase_cambiada.emit("[COMPLETADO]")
        hilo.senial_finalizado.emit(True, "[OK] Procesamiento finalizado y confirmado en disco")
