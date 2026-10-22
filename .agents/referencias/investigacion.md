# Investigación del esquema de agentes

Consulta: 21 de octubre de 2026. Alcance: instrucciones para desarrollar el proyecto,
sin selección de modelos ni implementación de la aplicación.

## Hallazgos en los archivos anteriores

| Hallazgo | Consecuencia | Resolución del esquema |
| --- | --- | --- |
| Revisión de consumidores ligada sobre todo a crear o reemplazar funciones | Un cambio de retorno o excepción podía saltarse el análisis | Protocolo proporcional antes de editar código |
| Ausencia de memoria verificable | Repetición de lecturas y pérdida de restricciones | Estado breve y un índice duradero con fuentes |
| Propuestas usadas como requisitos | Qt, paleta y etapas podían asumirse aprobados | Estados explícitos y biblioteca condicionada a decisión |
| Reglas sin medición de contexto | Más instrucciones podían aumentar coste sin mejorar resultados | Carga selectiva y evaluación con tareas equivalentes |
| Validación únicamente estructural | Un archivo válido no demostraba decisiones correctas | Escenarios conductuales y resultados separados |

## Fuentes primarias consultadas

F-01. [AGENTS.md](https://agents.md/) y
[su repositorio oficial](https://github.com/agentsmd/agents.md).
Formato abierto para orientación de agentes y ámbitos de instrucciones. Su
portabilidad depende de que la herramienta lo lea; no es una capacidad de todo LLM.
Aplicación local: un núcleo común y una alternativa de carga manual.

F-02. [Especificación de Agent Skills](https://agentskills.io/specification) y
[repositorio oficial](https://github.com/agentskills/agentskills).
Define metadatos requeridos y carga progresiva de instrucciones y recursos.
Aplicación local: habilidades con activación precisa y referencias bajo demanda,
sin metadatos exclusivos de un proveedor en el contenido compartido.

F-03. [Habilidades en OpenAI](https://learn.chatgpt.com/docs/build-skills).
Documenta descubrimiento por nombre y descripción y carga del cuerpo al utilizar
la habilidad. Aplicación local: no cargar todos los procedimientos por rutina.

F-04. [Ingeniería de contexto de Anthropic](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents).
Describe recuperación selectiva, compactación y notas persistentes; compactar puede
perder información relevante. Aplicación local: conservar restricciones, evidencia
y pendientes, con referencias recuperables en lugar de transcripciones completas.

F-05. [Memoria y compactación en OpenAI](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction).
Distingue contexto de ejecución, memoria reutilizable y artefactos revisados.
Aplicación local: la nota del agente no sustituye código vigente ni una decisión
aprobada. No se adopta su SDK ni su dominio de ejemplo.

F-06. [Instrucciones de GitHub Copilot](https://docs.github.com/en/copilot/concepts/prompting-and-context/custom-instructions) y
[habilidades de proyecto](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills).
El soporte varía por superficie y la respuesta no es determinista. Admite habilidades
en `.agents/skills`. Aplicación local: comprobar integración y comportamiento, sin
duplicar carpetas ni confundir instrucciones con controles de ejecución.

F-07. [Memoria e instrucciones de Claude Code](https://code.claude.com/docs/en/memory).
AGENTS.md depende de versión y configuración; ciertos archivos CLAUDE.md cambian
su carga predeterminada. Aplicación local: verificar la sesión real y documentar
adaptación solo si hace falta, sin prometer descubrimiento universal.

F-08. [Contexto de Gemini CLI](https://geminicli.com/docs/cli/gemini-md/) y
[documentación en GitHub](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md).
Documenta contexto jerárquico y configuración del nombre de archivo con
`context.fileName`. Aplicación local: reutilizar el núcleo donde sea posible.

Las páginas y ramas principales son referencias cambiantes, consultadas en la fecha
indicada. Verificar de nuevo versiones y soporte al integrar una herramienta.
No se copiaron paquetes externos ni se ejecutaron scripts de esos repositorios.

## Criterios de diseño derivados

Los siguientes son decisiones de este esquema, no estándares universales publicados
por las fuentes: separar memoria breve e índice duradero; presupuestos editoriales
en palabras; ficha compacta de impacto; requisitos de evidencia y evaluación local.

- Núcleo: restricciones que influyen en casi toda tarea; procedimientos por necesidad.
- Impacto: confirmar la relación entre definición, consumidores, datos y efectos.
- Evidencia: separar observado, inferido y pendiente; verificar APIs según versión.
- Memoria: registrar fuente, fecha, ámbito y motivo de revisión; corregir obsolescencia.
- Eficiencia: reducir repetición y salidas irrelevantes, sin omitir comprobaciones.
- Evaluación: comparar cumplimiento, regresiones, lecturas y tokens reales si existen.

## Límites de las conclusiones

Estas prácticas reducen riesgos; no eliminan alucinaciones ni garantizan ahorro.
No se ha medido un porcentaje de mejora entre modelos. Las palabras y caracteres
son indicadores editoriales, no tokens equivalentes entre tokenizadores.
Un formato neutral no prueba que todos los entornos lo carguen o lo sigan.
La memoria permanece en archivos; no implica entrenamiento ni cambio de pesos del LLM.
