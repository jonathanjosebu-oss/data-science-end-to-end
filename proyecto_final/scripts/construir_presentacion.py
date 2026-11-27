"""Presentación ejecutiva del PSet 4 -> docs/PSet4_presentacion_Buenaño_Peñafiel.pdf

    python -m scripts.construir_presentacion

Audiencia: el patrocinador del pitch del PSet 1 (no técnico). Formato: Times New
Roman; títulos en rojo, negrita, 14 pt; subtítulos en rojo, negrita, 12 pt;
texto en negro, 10 pt. Diapositiva 16:9 de 25,4 × 14,29 cm. Toda cifra técnica
va con su consecuencia de negocio; el detalle técnico está en el anexo.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Frame, Paragraph, Table, TableStyle

from scripts.construir_memo import registrar_fuentes

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
SALIDA = DOCS / "PSet4_presentacion_Buenaño_Peñafiel.pdf"
W, H = 25.4 * cm, 14.2875 * cm
M = 1.2 * cm
ROJO, NEGRO, GRIS = colors.HexColor("#c00000"), colors.black, colors.HexColor("#6b6b6b")
SUAVE = colors.HexColor("#f6f4f1")

E = {
    "titulo": ParagraphStyle("t", fontName="TNR-Times-B", fontSize=14, leading=17, textColor=ROJO),
    "sub": ParagraphStyle("s", fontName="TNR-Times-B", fontSize=12, leading=14.5, textColor=ROJO, spaceAfter=3),
    "texto": ParagraphStyle("x", fontName="TNR-Times", fontSize=10, leading=13, textColor=NEGRO, spaceAfter=4),
    "centro": ParagraphStyle("c", fontName="TNR-Times", fontSize=10, leading=13, textColor=NEGRO, alignment=TA_CENTER),
    "cifra": ParagraphStyle("k", fontName="TNR-Times-B", fontSize=14, leading=17, textColor=ROJO, alignment=TA_CENTER),
    "celda": ParagraphStyle("cl", fontName="TNR-Times", fontSize=10, leading=12, textColor=NEGRO, alignment=TA_LEFT),
}


def p(texto: str, estilo: str = "texto") -> Paragraph:
    return Paragraph(texto, E[estilo])


def vinetas(items: list[str]) -> list[Paragraph]:
    return [Paragraph(t, E["texto"], bulletText="•") for t in items]


class Deck:
    def __init__(self, ruta: Path):
        self.c = Canvas(str(ruta), pagesize=(W, H))
        self.c.setTitle("QSRR-Predict · Presentación ejecutiva (PSet 4)")
        self.c.setAuthor("Jonatan Buenaño Peñafiel")
        self.n = 0

    def nueva(self, titulo: str, mensaje: str | None = None) -> None:
        if self.n:
            self.c.showPage()
        self.n += 1
        c = self.c
        c.setFillColor(colors.white); c.rect(0, 0, W, H, stroke=0, fill=1)
        c.setFillColor(ROJO); c.rect(0, H - 0.25 * cm, W, 0.25 * cm, stroke=0, fill=1)
        self.bloque([p(escape(titulo), "titulo")], M, H - 2.0 * cm, W - 2 * M, 1.4 * cm)
        if mensaje:
            self.bloque([p(mensaje, "sub")], M, H - 3.62 * cm, W - 2 * M, 1.6 * cm)
        c.setFont("TNR-Times", 10); c.setFillColor(GRIS)
        c.drawString(M, 0.55 * cm, "QSRR-Predict · Proyecto final · Buenaño Peñafiel")
        c.drawRightString(W - M, 0.55 * cm, str(self.n))

    def bloque(self, flujo: list, x: float, y: float, w: float, h: float, fondo=None) -> None:
        if fondo is not None:
            self.c.setFillColor(fondo); self.c.setStrokeColor(colors.HexColor("#dddddd"))
            self.c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
        f = Frame(x, y, w, h, leftPadding=6, rightPadding=6, topPadding=5, bottomPadding=4, showBoundary=0)
        pendiente = list(flujo)
        f.addFromList(pendiente, self.c)  # deja en la lista lo que no cupo
        if pendiente:
            raise ValueError(f"Diapositiva {self.n}: no cabe «{pendiente[0].getPlainText()[:60]}»")

    def imagen(self, ruta: Path, x: float, y: float, w: float, h: float) -> None:
        iw, ih = ImageReader(str(ruta)).getSize()
        escala = min(w / iw, h / ih)
        self.c.drawImage(str(ruta), x + (w - iw * escala) / 2, y + (h - ih * escala) / 2, iw * escala, ih * escala)

    def tabla(self, filas: list[list[str]], x: float, y_sup: float, anchos: list[float]) -> None:
        datos = [[Paragraph(("<b>%s</b>" if i == 0 else "%s") % c, E["celda"]) for c in f] for i, f in enumerate(filas)]
        t = Table(datos, colWidths=anchos)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#a0a0a0")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efefef")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        _, alto = t.wrapOn(self.c, sum(anchos), H)
        t.drawOn(self.c, x, y_sup - alto)

    def caja_flujo(self, etiquetas: list[tuple[str, str]], y: float, alto: float, colores_: list, flechas: bool = True) -> None:
        n = len(etiquetas)
        hueco = 0.55 * cm
        ancho = (W - 2 * M - hueco * (n - 1)) / n
        for i, ((tit, txt), col) in enumerate(zip(etiquetas, colores_)):
            x = M + i * (ancho + hueco)
            self.bloque([p(f"<b>{tit}</b>", "centro"), p(txt, "centro")], x, y, ancho, alto, fondo=col)
            if flechas and i < n - 1:
                cx, cy = x + ancho + 0.08 * cm, y + alto / 2
                self.c.setStrokeColor(GRIS); self.c.setFillColor(GRIS); self.c.setLineWidth(1.4)
                self.c.line(cx, cy, cx + hueco - 0.22 * cm, cy)
                camino = self.c.beginPath()
                punta = cx + hueco - 0.16 * cm
                camino.moveTo(punta, cy); camino.lineTo(punta - 0.18 * cm, cy + 0.12 * cm); camino.lineTo(punta - 0.18 * cm, cy - 0.12 * cm)
                camino.close(); self.c.drawPath(camino, stroke=0, fill=1)

    def guardar(self) -> None:
        self.c.showPage(); self.c.save()


def construir() -> int:
    registrar_fuentes()
    d = Deck(SALIDA)
    col = [colors.HexColor(h) for h in ("#eaf2fc", "#fdeee7", "#e8f6f0", "#fdecec", "#f3eefc")]
    ancho_util = W - 2 * M

    # 1 · Portada
    d.nueva("QSRR-Predict: menos corridas de prueba en el laboratorio de HPLC")
    d.bloque([p("Resultado del piloto simulado y recomendación para el patrocinador", "sub"),
              p("Proyecto final de Ciencia de Datos · USFQ · noviembre de 2026"),
              p("Jonatan Buenaño Peñafiel"),
              p("<br/>En una frase: <b>el sistema ya predice dónde saldrá cada compuesto y detecta solo cuando el equipo cambia, "
                "pero todavía no es lo bastante preciso para ahorrar corridas. Recomendamos ajustarlo con un piloto "
                "en un laboratorio real antes de escalar.</b>")],
            M, 2.2 * cm, ancho_util * 0.75, 8.2 * cm)

    # 2 · Problema
    d.nueva("Qué problema resolvemos y para quién",
            "Cada método nuevo exige corridas de prueba y error antes de saber si los compuestos se separan")
    d.bloque([p("Para quién", "sub")] + vinetas([
        "<b>Analistas de desarrollo analítico</b> de un laboratorio de control de calidad farmacéutico, que diseñan los métodos.",
        "<b>Jefatura de laboratorio</b>, que asigna el tiempo de equipo y el presupuesto de solventes.",
        "<b>Calidad y clientes</b>, que reciben el resultado: un pico mal separado es un resultado dudoso."]),
        M, 2 * cm, ancho_util * 0.48, 8.6 * cm)
    d.bloque([p("Qué cuesta hoy", "sub")] + vinetas([
        "Cada corrida exploratoria consume solvente (acetonitrilo, metanol), horas de equipo y horas de analista.",
        "El analista elige columna, fase móvil y gradiente por experiencia; solo sabe si funcionó después de inyectar.",
        "La pregunta del proyecto: <b>¿podemos saber antes de inyectar si los picos se van a separar, y saltarnos la corrida de prueba cuando sí?</b>"]),
        M + ancho_util * 0.52, 2 * cm, ancho_util * 0.48, 8.6 * cm, fondo=SUAVE)

    # 3 · Qué cambió en la decisión
    d.nueva("Qué cambió en la decisión", "Antes, siempre había corrida de prueba; ahora el sistema propone y el analista decide")
    d.tabla([["", "Antes", "Con QSRR-Predict"],
             ["Antes de inyectar", "El analista elige el método por experiencia.",
              "El analista envía el método y los compuestos; en menos de 0,1 s recibe dónde saldrá cada pico."],
             ["La decisión", "Siempre se hace una corrida exploratoria.",
              "<b>Aprobar</b> (saltar la corrida) solo si todos los picos quedan separados con 95 % de confianza; si no, <b>revisar</b>."],
             ["Quién decide", "El analista.", "El analista, siempre. El sistema recomienda; nunca inyecta solo."],
             ["Si algo falla", "—", "Botón de emergencia: vuelve a la regla actual en segundos, sin tocar el sistema."],
             ["Además", "—", "Orden en que saldrán los compuestos, para planificar la corrida de prueba."]],
            M, H - 3.6 * cm, [ancho_util * 0.18, ancho_util * 0.3, ancho_util * 0.52])

    # 4 · Cómo funciona (un solo diagrama simple)
    d.nueva("Cómo funciona", "Un solo circuito: datos, predicción, vigilancia y actualización con aprobación humana")
    d.caja_flujo([("1. Datos", "Más de 400 experimentos públicos de cromatografía (RepoRT), limpios y actualizados cada semana."),
                  ("2. Predicción", "Modelo que aprende de la estructura del compuesto y del método."),
                  ("3. Servicio", "El analista consulta y recibe: aprobar o revisar, y el orden de los picos."),
                  ("4. Vigilancia", "Cada semana compara lo predicho con lo medido y avisa si algo cambia."),
                  ("5. Actualización", "Si el error sube, se entrena una versión nueva; <b>una persona aprueba</b> el cambio.")],
                 5.2 * cm, 4.4 * cm, col)
    d.bloque([p("Por qué importa: cada predicción queda registrada con la versión que la produjo, y cualquier cambio de versión se "
                "puede deshacer en menos de un minuto. El detalle técnico está en el anexo y en el documento técnico.")],
             M, 1.6 * cm, ancho_util, 2.4 * cm)

    # 5 · Cómo lo probamos
    d.nueva("Cómo lo probamos: 10 semanas de operación simulada",
            "34 339 mediciones de laboratorios que el sistema nunca había visto, una semana a la vez")
    d.bloque(vinetas([
        "Cada semana llegó un grupo de métodos nuevos (de 1 a 26 experimentos) y el sistema respondió como lo haría en producción.",
        "La medición real llegó una semana después, como ocurre cuando el analista inyecta.",
        "<b>Desde la semana 6 cambiamos el equipo a propósito:</b> simulamos que el laboratorio pasa a un HPLC más lento, "
        "que retrasa todos los picos entre 1,7 y 3,6 minutos. El sistema no fue avisado.",
        "Objetivo: comprobar que el sistema <b>detecta solo</b> el cambio, avisa a las personas correctas y se actualiza con aprobación."]),
        M, 2.0 * cm, ancho_util * 0.5, 8.6 * cm)
    d.imagen(DOCS / "figuras" / "deriva_inducida.png", M + ancho_util * 0.52, 3.6 * cm, ancho_util * 0.48, 7.0 * cm)
    d.bloque([p("Minutos de retraso que simulamos en cada pico por el cambio de equipo (gris: semanas sin cambio).", "centro")],
             M + ancho_util * 0.52, 2.0 * cm, ancho_util * 0.48, 1.5 * cm)

    # 6 · Cuánto valor generó
    d.nueva("Cuánto valor generó: todavía cero corridas ahorradas",
            "El sistema no aprobó ningún método, y eso evitó pérdidas: confiar a ciegas habría costado hasta 0,87 corridas extra por método")
    d.imagen(DOCS / "figuras" / "negocio_por_lote.png", M, 2.0 * cm, ancho_util * 0.6, 8.4 * cm)
    d.bloque([p("0 corridas ahorradas", "cifra"),
              p("en 10 semanas, igual que el proceso actual: no ahorra, pero tampoco hace daño.", "centro"),
              p("<br/>0,23 a 0,87", "cifra"),
              p("corridas <b>extra</b> por método si se aprobara todo sin revisar: solo entre el 6 % y el 39 % de los métodos reales se separan bien.", "centro"),
              p("<br/>Techo: 19 %", "cifra"),
              p("de las corridas de prueba es lo máximo que se podría ahorrar con un sistema más preciso.", "centro")],
             M + ancho_util * 0.62, 2.0 * cm, ancho_util * 0.38, 8.4 * cm, fondo=SUAVE)

    # 7 · Qué sí aporta hoy
    d.nueva("Qué sí aporta hoy", "Ordena los picos y ubica cada compuesto mejor que la regla actual, pero no con el margen que exige saltarse la prueba")
    d.tabla([["Lo que medimos", "Resultado", "Qué significa para el laboratorio"],
             ["Orden de salida de los compuestos (pares separados por 2 min o más)", "86 % a 99 % correcto por semana",
              "El analista sabe qué compuesto sale primero y puede planificar una sola corrida de prueba mejor dirigida."],
             ["Error típico al ubicar un pico (laboratorios nuevos, equipo sin cambios)", "0,7 a 2,0 min",
              "Entre 2 y 11 veces menos error que la regla actual (promedio por condición); suficiente para orientar, no para aprobar."],
             ["Margen que necesita el analista para saltarse la prueba", "≈ 0,5 min",
              "Hoy el margen del sistema es de ±8 min entre dos picos: por eso no aprueba. Es la brecha que hay que cerrar."],
             ["Tiempo de respuesta", "Menos de 0,06 s",
              "La consulta no retrasa el trabajo del analista."]],
            M, H - 3.6 * cm, [ancho_util * 0.32, ancho_util * 0.2, ancho_util * 0.48])

    # 8 · Vigilancia: el sistema detectó el cambio
    d.nueva("La vigilancia funcionó: detectó el cambio de equipo sin que nadie le avisara",
            "Primera señal en el primer grupo afectado; actualización solo cuando una persona la aprobó")
    d.imagen(DOCS / "figuras" / "desempeno_por_lote.png", M, 2.0 * cm, ancho_util * 0.58, 8.4 * cm)
    d.bloque(vinetas([
        "<b>Semana 6:</b> aparece el desfase de 1,9 min (los picos salen más tarde de lo previsto). Alerta al laboratorio: revisar el equipo.",
        "<b>Semana 8:</b> dos semanas seguidas con error alto: se entrena una versión nueva. <b>Se rechazó</b>: mejoraba solo 0,03 min.",
        "<b>Semana 10:</b> la nueva versión reduce el error de 3,4 a 2,9 min. <b>Una persona la aprobó</b> y entró en servicio sin detener nada.",
        "Las semanas sin cambio (1–5) no generaron alertas de error; las pocas alertas fueron de datos y de baja severidad."]),
        M + ancho_util * 0.6, 2.0 * cm, ancho_util * 0.4, 8.4 * cm, fondo=SUAVE)

    # 9 · Riesgos
    d.nueva("Qué riesgos quedan y cómo se vigilan", "Cada riesgo tiene una señal medible, un umbral y una respuesta definida de antemano")
    d.tabla([["Riesgo", "Cómo lo vemos", "Qué pasa si ocurre"],
             ["La alerta de picos solapados todavía no los distingue bien (error de 2 a 3 min; se necesitan 0,5)",
              "Métodos aprobados y aciertos de la alerta por semana", "No se usa para saltarse la prueba, solo para ordenar los picos."],
             ["Columnas o laboratorios distintos a los conocidos (con columnas Agilent el error fue 3 veces mayor)",
              "Error por fabricante y aviso cuando el método está fuera de lo conocido", "El sistema marca \"revisar\" y esos métodos entran en la siguiente actualización."],
             ["Cambio de equipo o de condiciones (como el de la semana 6)", "Desfase sistemático de los picos durante 2 semanas",
              "Aviso al laboratorio y actualización con aprobación humana."],
             ["Aprobaciones equivocadas cuando el sistema empiece a aprobar", "Más del 2 % de aprobaciones que fallan en una semana",
              "Se apaga la aprobación: todo vuelve a \"revisar\"."],
             ["El sistema no supera al proceso actual aun después de actualizarlo", "Ahorro por debajo de cero 2 semanas seguidas",
              "Se activa el modo de respaldo (regla actual) y se revisa el modelo."],
             ["El servicio falla", "Errores o lentitud en las consultas", "Respaldo automático: el analista sigue trabajando."]],
            M, H - 3.6 * cm, [ancho_util * 0.36, ancho_util * 0.3, ancho_util * 0.34])

    # 10 · Recomendación
    d.nueva("Recomendación: AJUSTAR antes de escalar", "No retirarlo: la base funciona. No escalarlo: todavía no ahorra.")
    d.bloque([p("Por qué ajustar", "sub")] + vinetas([
        "La infraestructura, la vigilancia y la aprobación humana funcionaron de punta a punta.",
        "Lo que falta es precisión: pasar de ~2 min a ~0,5 min de error en los métodos del laboratorio.",
        "La simulación mostró la causa principal: cada equipo desplaza los picos. Eso se corrige midiendo 1 o 2 compuestos de "
        "referencia en el propio método (calibración), no con más datos públicos."]),
        M, 2.0 * cm, ancho_util * 0.48, 8.6 * cm)
    d.bloque([p("Cómo sabremos que funcionó (piloto de 3 meses)", "sub")] + vinetas([
        "Corridas de prueba por método aceptado, antes y después, con el mismo criterio de aceptación.",
        "mL de solvente por método, desde el inventario del laboratorio.",
        "Meta para escalar: <b>al menos 10 % de corridas ahorradas sin aprobaciones fallidas</b> (techo teórico: 19 %).",
        "Si no se alcanza en 3 meses, se retira la aprobación y queda solo como guía del orden de los picos."]),
        M + ancho_util * 0.52, 2.0 * cm, ancho_util * 0.48, 8.6 * cm, fondo=SUAVE)

    # 11 · Qué necesitamos
    d.nueva("Qué necesitamos para avanzar", "Tres recursos concretos para el piloto")
    d.caja_flujo([("Un laboratorio piloto", "Acceso a un equipo HPLC con columnas C18 y a su bitácora de corridas de los últimos 6 meses."),
                  ("Registro de solventes", "Consumo de acetonitrilo y metanol por método (inventario o compras) para medir el ahorro real."),
                  ("Tiempo del equipo humano", "Un analista 4 h por semana para calibrar con estándares y validar las recomendaciones.")],
                 5.4 * cm, 4.2 * cm, col[:3], flechas=False)
    d.bloque([p("Con esto, en 3 meses tendremos la cifra real de ahorro del laboratorio, en lugar del 30 % que planteamos como hipótesis al inicio.")],
             M, 2.0 * cm, ancho_util, 2.2 * cm)

    # 12 · Anexo técnico
    d.nueva("Anexo técnico", "Detalle para el equipo de ciencia de datos; cada cifra con su consecuencia")
    d.tabla([["Indicador técnico", "Valor", "Consecuencia de negocio"],
             ["Error de validación del modelo vigente (RMSE CV, versión 5)", "2,25 ± 0,03 min", "Ubica cada pico con ~2 min de margen: orienta, no aprueba."],
             ["Error en las semanas con cambio de equipo (RMSE por lote)", "2,2 a 8,3 min", "Disparó dos actualizaciones; una rechazada y una aprobada."],
             ["Umbral de alerta de error / desfase", "3,66 / 1,81 min", "Calibrado para no alarmar en semanas normales (0 falsas alarmas de error)."],
             ["Cambio en los datos de entrada (PSI calibrado, 2 descriptores)", "1 aviso en 5 semanas normales", "Aviso informativo; no reentrena si el error no sube."],
             ["Regla de promoción", "mejora > 1 desviación de la validación", "Evita cambiar de modelo por ruido; la decisión final es humana."],
             ["Rollback a la versión anterior", "≈ 35 s, sin reinstalar", "Cualquier cambio malo se deshace en menos de un minuto."]],
            M, H - 3.6 * cm, [ancho_util * 0.4, ancho_util * 0.22, ancho_util * 0.38])
    d.bloque([p("Documento técnico: docs/PSet4_memo_Buenaño_Peñafiel.pdf · Evidencia: notebooks 06 y 07, docs/*.csv · Tablero: localhost:8501")],
             M, 1.2 * cm, ancho_util, 1.2 * cm)

    d.guardar()
    return d.n


if __name__ == "__main__":
    print(f"{SALIDA.name}: {construir()} diapositivas")
