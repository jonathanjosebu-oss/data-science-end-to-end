# PSet 1: Propuesta del proyecto y su ambiente

**Asignado:** Semana 2, Sesión 2. **Vence:** Semana 4, Sesión 1.

Formaliza, con la calidad de un documento profesional real (el que le mostrarías a un patrocinador para conseguir su aprobación, no un ejercicio de clase), la evaluación de viabilidad que empezaste en el laboratorio de la Semana 2, Sesión 2, y deja listo el ambiente donde va a correr el proyecto (Semana 3). Los tres primeros entregables van en [`psets/proyecto/docs/`](../proyecto/docs/), la carpeta de documentos del proyecto que vas a construir el resto del semestre; el cuarto, en la raíz de [`psets/proyecto/`](../proyecto/):

## 1. Canvas de Viabilidad y Riesgos (versión final)

Parte del `canvas-<tu-nombre>.md` que llenaste en el laboratorio (`laboratorios/semana-02-sesion-02/`) y guarda la versión final como `docs/canvas.md`. Revísalo con lo que aprendiste de la retroalimentación de tu pareja y de la puesta en común: corrige cualquier sección que haya quedado genérica, y confirma que los dos riesgos mínimos tengan evidencia real, no solo una intuición.

## 2. Documento de propuesta (1 a 2 páginas)

Un documento de texto (`docs/propuesta.pdf`, o en Markdown como `docs/propuesta.md`) que desarrolla el canvas en prosa, dirigido a alguien que no estuvo en la sesión de clase y necesita entender el proyecto desde cero. Debe cubrir, en este orden:

1. El problema de negocio y la métrica de éxito (de la Semana 2, Sesión 1).
2. La viabilidad técnica: qué se predice, qué datos existen y con qué estado de acceso.
3. La viabilidad de negocio: qué acción cambia, quién aplica juicio, cómo se mide el resultado.
4. Los riesgos principales, con el supuesto que rompen y cómo se mitigarían o se verificarían antes de invertir más tiempo.

Parte de la plantilla [`plantilla-documento-propuesta.md`](./plantilla-documento-propuesta.md) si quieres una estructura de arranque; no es obligatoria, pero cubre exactamente estas cuatro secciones en el orden pedido.

## 3. Presentación de negocio (5 a 8 diapositivas)

Una presentación visual, en el formato de una propuesta a un patrocinador o inversionista (no el formato de la presentación de clase, que es texto plano): problema y oportunidad, la solución propuesta, evidencia de viabilidad, riesgos principales y qué se necesita para avanzar. Herramienta libre (Google Slides, PowerPoint, Gamma, Canva); lo que se evalúa es la claridad y el rigor del contenido, no el diseño. Exporta la versión final a `docs/presentacion.pdf`.

Consulta [`plantilla-presentacion-negocio.md`](./plantilla-presentacion-negocio.md) para una guía de qué debe llevar cada diapositiva.

## 4. El ambiente del proyecto

Lo que construiste en el Ejercicio 3 de la Semana 3, Sesión 1, y el patrón de la Semana 3, Sesión 2, aplicados a tu proyecto:

- `Dockerfile` y `requirements.txt`, en la raíz de `proyecto/`: la imagen que corre tu ingesta, con las versiones de las librerías fijadas.
- `ingesta/`: el script que trae los datos de tu fuente y los deja en `data/raw/`.
- `infra/docker-compose.yml` o `infra/main.tf`: la base de datos de tu proyecto, levantada con un solo comando, a la que tu ingesta se conecta por nombre de servicio.

En `proyecto/README.md`, completa la sección **Datos**: de dónde salen, cómo se obtienen y en qué archivo de `data/raw/` quedan.

## Cómo se evalúa

Los cuatro entregables se evalúan como una sola entrega dentro del componente de PSets (25% de la nota final entre los 4 PSets). Para entregar, sigue la sección "Cómo entregar" de [`psets/README.md`](../README.md): el tag de este PSet es `pset-01`. El criterio central: que la viabilidad técnica y de negocio esté sustentada con evidencia concreta del proyecto propio, no con afirmaciones genéricas, y que los riesgos identificados sean específicos y verificables, siguiendo el mismo criterio de evidencia usado en la Semana 1, Sesión 2 y en el laboratorio de esta sesión.

La rúbrica completa, con los seis criterios de calificación y sus niveles, está en [`rubrica.md`](./rubrica.md). Revísala antes de entregar.
