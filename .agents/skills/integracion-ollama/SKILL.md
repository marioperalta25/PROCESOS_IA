---
name: integracion-ollama
description: Integrar Ollama en PROCESOS_IA mediante contratos de disponibilidad, modelos e inferencia local. Aplicar a conexión, respuestas progresivas y estado de ejecución.
---

# Integración con Ollama

Leer [las reglas comunes](../../reglas/AGENTS.md),
[la arquitectura](../../proyecto/arquitectura.md) y
[los parámetros iniciales](../../proyecto/proyecto.toml).

## Procedimiento

1. Inspeccionar el adaptador y contratos existentes; ampliar sus capacidades sin
   introducir un segundo cliente para resolver la misma necesidad.
2. Verificar la versión local cuando la tarea lo requiera y consultar la documentación
   oficial vigente para los endpoints y opciones realmente necesarios.
3. Separar detección de instalación, disponibilidad del servicio y estado del modelo.
   Un timeout no basta para decidir que hace falta reinstalar.
4. Traducir respuestas, errores y datos del servidor al contrato de aplicación.
   La presentación recibe datos propios, sin depender del formato externo completo.
5. Definir tiempos límite de conexión, inactividad y operación según el flujo.
   Cerrar correctamente conexiones y flujos al terminar o cancelar.
6. Verificar el comportamiento con respuestas simuladas y, cuando corresponda,
   una prueba local explícita sin descargas ni instalaciones implícitas.

## Criterios específicos

- Dirección local predeterminada configurable; no exponer el servicio en la red
  como requisito de la aplicación.
- El SDK oficial o un cliente HTTP será una elección única documentada según
  necesidades de transmisión, cancelación y dependencias; no mantener ambos sin motivo.
- Procesar respuestas progresivas por mensajes completos; tolerar fragmentación
  del transporte sin confundirla con JSON inválido del servidor.
- Acotar reintentos; no repetir generaciones o descargas automáticamente cuando
  puedan duplicar trabajo o consumo. Un fallo no activa el instalador.
- No interpretar texto del modelo como instrucciones de sistema ni comandos.
- Diferenciar GPU detectada, backend compatible y uso real durante inferencia.
- Política de carga y permanencia de modelos explícita y ajustada al equipo.

## Resultado verificable

Disponibilidad, ausencia de modelo, flujo interrumpido y cancelación tienen salidas
distintas. La interfaz no se bloquea y el cliente compartido libera sus recursos.
No afirmar uso de GPU sin evidencia durante una ejecución real.

Fuente de consulta: [documentación oficial de Ollama](https://docs.ollama.com/).
