"""Composicion del procesamiento local y reserva comun de su salida."""

from dataclasses import replace

from procesos_ia.dominio.modelos import ConfiguracionTrabajo
from procesos_ia.aplicacion.reanudacion_local import buscar_continuacion_local
from procesos_ia.interfaz.continuacion_local import elegir_continuacion_local
from procesos_ia.interfaz.hilos import HiloCoordinadorTrabajo


def iniciar_trabajo_local(ventana, configuracion: ConfiguracionTrabajo) -> None:
    try:
        raiz = ventana.panel_archivos.raiz_salidas
        continuacion = buscar_continuacion_local(configuracion, ventana._enrutador, raiz)
        decision = elegir_continuacion_local(ventana, continuacion) if continuacion else "nuevo"
        if decision == "cancelar":
            return
        if decision == "continuar":
            ruta = continuacion.directorio / continuacion.nombre_archivo
            salida = ventana._enrutador.gestor_procesos(raiz).retomar("ia_local", ruta)
            directorio = salida.directorio if salida else continuacion.directorio
        else:
            salida = ventana._enrutador.reservar_salida(
                "ia_local", "resultado_procesado.csv", configuracion.ruta_entrada.stem,
                raiz_destino=raiz,
            )
            directorio = salida.directorio
        configuracion = replace(configuracion, directorio_salida=directorio)
        hilo = HiloCoordinadorTrabajo(
            configuracion=configuracion, coordinador=ventana._coordinador_inyectado,
            servicio_inferencia=ventana._obtener_servicio_inferencia(), parent=ventana, salida=salida,
        )
    except (OSError, ValueError) as error:
        ventana._al_fallar_trabajo(str(error))
        return
    ventana.pila_vistas.setCurrentWidget(ventana.vista_principal)
    ventana.panel_telemetria.reiniciar_indicadores()
    ventana.panel_controles.configurar_estado_ejecucion(en_ejecucion=True)
    ventana.panel_archivos.mostrar_destino_salida(directorio)
    ventana._hilo_trabajo = hilo
    for s, sl in ((ventana._hilo_trabajo.senial_progreso, ventana.panel_telemetria.actualizar_progreso),
                  (ventana._hilo_trabajo.senial_fase_cambiada, ventana.panel_telemetria.actualizar_fase),
                  (ventana._hilo_trabajo.senial_mensaje, ventana.panel_telemetria.agregar_log),
                  (ventana._hilo_trabajo.senial_finalizado, ventana._al_finalizar_trabajo),
                  (ventana._hilo_trabajo.senial_error, ventana._al_fallar_trabajo)):
        s.connect(sl)
    ventana._hilo_trabajo.start()
