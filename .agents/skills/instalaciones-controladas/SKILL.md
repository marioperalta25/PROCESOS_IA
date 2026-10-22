---
name: instalaciones-controladas
description: Diseñar o implementar detección, instalación y reparación de Ollama o dependencias en PROCESOS_IA. Aplicar a planes de instalación y comandos en segundo plano bajo control del usuario.
---

# Instalaciones controladas

Leer [las reglas comunes](../../reglas/AGENTS.md) y
[la arquitectura](../../proyecto/arquitectura.md).
Esta habilidad describe una funcionalidad futura; no autoriza instalar software
por el hecho de leerla o iniciar la aplicación.

## Flujo

1. Detectar lo necesario con consultas acotadas. Distinguir instalación ausente,
   servicio detenido, versión incompatible y fallo de conexión.
2. Reutilizar la instalación disponible si satisface la necesidad. Una comprobación
   inconclusa produce estado desconocido, no una orden automática de reinstalación.
3. Construir un plan concreto con origen oficial, versión objetivo, comandos,
   destino, tamaño si se conoce, efectos, privilegios y límites de cancelación.
4. Mostrar el plan y ejecutar cuando exista autorización para ese alcance. Reutilizar
   una autorización vigente; un plan distinto requiere una nueva decisión.
5. Ejecutar fuera del hilo visual, transmitir salida acotada y registrar estados.
6. Verificar código de salida y resultado real. Guardar evidencia mínima de la
   operación sin convertirla en un diagnóstico recurrente de cada arranque.

## Ejecución

- Centralizar procesos en un adaptador. Usar ejecutable y argumentos separados,
  `shell=False` cuando sea viable, rutas verificadas y entorno explícito.
- No concatenar texto del usuario o del modelo en comandos de shell.
- En Windows, usar el mecanismo apropiado para no abrir consolas accesorias;
  permitir la interacción del instalador o UAC cuando realmente sea necesaria.
- No elevar toda la aplicación. Solicitar privilegios solo para el paso que los necesite.
- Verificar procedencia y firma o suma oficial cuando estén disponibles.
- Evitar patrones que descargan un script remoto y lo ejecutan inmediatamente.
- Capturar errores sin exponer secretos. Limitar memoria de salida y tiempos de espera.
- Mantener como máximo una operación sobre el mismo destino; impedir instalaciones
  simultáneas del mismo componente.

## Estados y cancelación

Estados propuestos: detectado, planificado, autorizado, ejecutando, verificando,
completado, fallido, cancelacion_solicitada y cancelado.

Un timeout, permiso rechazado o interrupción no es éxito. Indicar si puede quedar
una instalación parcial y ofrecer recuperación explícita. No prometer reversión de
un instalador del sistema si no existe un mecanismo comprobado para ello.

Cancelar solo procesos que pertenezcan a la operación. Si un instalador no admite
cancelación segura, explicar esa condición antes de iniciar; no matar procesos
ajenos para forzar el resultado.

## Dependencias Python

Usar entorno aislado y manifiesto reproducible. Cuando exista empaquetado,
revisar cómo se distribuyen dependencias; no ejecutar `pip` automáticamente dentro
de una aplicación empaquetada. La gestión de desarrollo y la instalación del producto
deben tener destinos y responsabilidades diferenciados.

## Resultado verificable

La operación exige un plan autorizado, informa progreso real y comprueba su efecto.
Simular fallo, cancelación e instalación ya existente antes de probar mutaciones reales.
