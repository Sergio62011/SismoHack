"""
SismoLab AVL - Demo y pruebas de integración.

Cubre las secciones del enunciado que ya están implementadas:
- Mapa y zonas (sección 3)
- Cálculo de prioridad (sección 4)
- Clave y comparación (sección 5)
- Creación, consulta, corrección, eliminación (sección 6)
- Cola FIFO de reportes (sección 8)
- Rotaciones y recuperación (sección 8)
- Comparación BST vs AVL (sección 12, parcial)
"""

from datetime import datetime, timezone

from structure.avl import AVL
from structure.bst import BST
from models.event import Evento
from models.map import MapaSismico, Zona
from models.report import Reporte
from services.sistema_sismico import SistemaSismico


# =========================================================
# UTILIDADES
# =========================================================

def titulo(texto):
    print("\n" + "=" * 65)
    print(texto)
    print("=" * 65)


def subtitulo(texto):
    print("\n--- " + texto + " ---")


def fecha_utc(y, mo, d, h=0, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


def ev(id_evento, magnitud=5.0, profundidad=50.0,
       x=100.0, y=100.0, poblada=False, hora=10):
    return Evento(
        id_evento=id_evento,
        magnitud=magnitud,
        profundidad=profundidad,
        x=x,
        y=y,
        fecha_hora=fecha_utc(2026, 9, 7, hora, 0, 0),
        zona_poblada=poblada,
    )


def mostrar_evento(evento):
    if evento is None:
        print("  (sin evento)")
        return
    print(
        f"  ID={evento.id_evento} "
        f"M={evento.magnitud} H={evento.profundidad} "
        f"P={evento.prioridad} "
        f"clave={evento.calcular_clave()} "
        f"estado={evento.estado} "
        f"ubicacion={evento.ubicacion} "
        f"rev={evento.revision}"
    )


# =========================================================
# 1. MAPA Y ZONAS
# =========================================================

def demo_mapa_y_zonas():
    titulo("1. MAPA Y ZONAS (sección 3)")

    mapa = MapaSismico(filas=10, columnas=10)
    mapa.agregar_zona(Zona("Ciudad Norte", 100, 600, 450, 900, True))
    mapa.agregar_zona(Zona("Reserva Sur", 550, 100, 900, 350, False))
    mapa.agregar_zona(Zona("Ciudad Centro", 250, 250, 550, 550, True))

    casos = [
        # (x, y, descripción)
        (300.0, 700.0, "dentro de Ciudad Norte"),
        (700.0, 200.0, "dentro de Reserva Sur"),
        (500.0, 500.0, "borde de Ciudad Centro"),
        (100.0, 600.0, "borde de Ciudad Norte"),
        (250.0, 250.0, "borde esquina de Ciudad Centro"),
        (0.0, 0.0, "fuera de toda zona"),
        (450.0, 900.0, "borde superior de Ciudad Norte"),
        (450.0, 600.0, "borde entre Ciudad Norte y Ciudad Centro"),
    ]

    for x, y, desc in casos:
        pob = mapa.esta_en_zona_poblada(x, y)
        print(f"  ({x}, {y}) -> zona_poblada={pob}  [{desc}]")

    subtitulo("Matriz del mapa con eventos")
    eventos = [
        ev(101, 4.7, 20.0, 300.0, 700.0),
        ev(102, 5.1, 40.0, 700.0, 200.0),
        ev(103, 6.2, 15.0, 500.0, 500.0),
    ]
    for e in eventos:
        mapa.asignar_zona_a_evento(e)
        print(
            f"  Evento {e.id_evento}: poblada={e.en_zona_poblada} "
            f"P={e.prioridad} clave={e.calcular_clave()}"
        )

    matriz = mapa.crear_matriz_con_eventos(eventos)
    mapa.imprimir_matriz(matriz)


# =========================================================
# 2. PRIORIDAD Y CLAVE
# =========================================================

def demo_prioridad_y_clave():
    titulo("2. PRIORIDAD Y CLAVE (secciones 4 y 5)")

    subtitulo("Límites exactos")
    casos = [
        (6.0, 100.0, False, 3, "M=6.0 exacto"),
        (5.9, 100.0, False, 2, "M=5.9, no alta"),
        (4.5, 30.0, True, 3, "M=4.5, H=30, poblada -> 3"),
        (4.5, 30.0, False, 2, "M=4.5, H=30, no poblada -> 2"),
        (4.5, 30.1, True, 2, "M=4.5, H=30.1, poblada -> 2"),
        (4.5, 70.0, True, 2, "M=4.5, H=70, poblada -> 2"),
        (4.4, 10.0, True, 1, "M=4.4 -> 1"),
        (-2.0, 0.0, False, 1, "M=-2.0 -> 1"),
        (10.0, 700.0, False, 3, "M=10.0 -> 3"),
    ]

    for m, h, pob, esperado, desc in casos:
        e = ev(1, m, h, poblada=pob)
        ok = "OK" if e.prioridad == esperado else "FALLO"
        print(
            f"  [{ok}] {desc}: P={e.prioridad} (esperado {esperado})"
        )

    subtitulo("Comparación lexicográfica (ejemplo del PDF)")
    raiz = ev(10, 5.2, 40.0)
    raiz.prioridad = 3
    raiz.magnitud = 5.2

    entrantes = [
        (ev(20, 5.8, 40.0), "izquierda", "(2, 5.8, 20) < (3, 5.2, 10)"),
        (ev(30, 6.1, 40.0), "derecha",   "(3, 6.1, 30) > (3, 5.2, 10)"),
        (ev(5, 5.2, 40.0),  "izquierda", "(3, 5.2, 5) < (3, 5.2, 10)"),
        (ev(25, 5.2, 40.0), "derecha",   "(3, 5.2, 25) > (3, 5.2, 10)"),
    ]

    for e, esperado, motivo in entrantes:
        e.prioridad = 2 if "2," in motivo else 3
        e.magnitud = float(motivo.split(",")[1].strip())
        real = "izquierda" if e < raiz else "derecha"
        ok = "OK" if real == esperado else "FALLO"
        print(f"  [{ok}] {motivo}: {real}")


# =========================================================
# 3. AVL: ROTACIONES
# =========================================================

def demo_rotaciones():
    titulo("3. ROTACIONES AVL (sección 5)")

    casos = [
        ("LL", [30, 20, 10]),
        ("RR", [10, 20, 30]),
        ("LR", [30, 10, 20]),
        ("RL", [10, 30, 20]),
    ]

    for nombre, ids in casos:
        subtitulo(f"Caso {nombre}: insertar {ids}")
        avl = AVL()
        for i in ids:
            avl.insert(ev(i))
        avl.dibujar(mostrar_info=True)
        print(f"  Altura: {avl.height()}")
        print(f"  Rotaciones registradas: {avl.rotaciones_ultima_operacion}")
        print(f"  Inorden: {[e.id_evento for e in avl.in_order()]}")
        print(f"  ¿AVL válido? {avl._is_avl(avl.root)}")


# =========================================================
# 4. AVL: ELIMINACIÓN
# =========================================================

def demo_eliminacion():
    titulo("4. ELIMINACIÓN AVL (secciones 6 y 10)")

    subtitulo("Eliminar raíz con dos hijos")
    avl = AVL()
    for i in [20, 10, 30, 5, 15, 25, 35]:
        avl.insert(ev(i))

    print("  Antes:")
    avl.dibujar(mostrar_info=True)

    avl.delete((2, 5.0, 20))
    print("  Después de eliminar la raíz (20):")
    avl.dibujar(mostrar_info=True)
    print(f"  Inorden: {[e.id_evento for e in avl.in_order()]}")
    print(f"  ¿AVL válido? {avl._is_avl(avl.root)}")

    subtitulo("Eliminar hoja")
    avl.delete((2, 5.0, 5))
    print(f"  Inorden: {[e.id_evento for e in avl.in_order()]}")
    print(f"  ¿AVL válido? {avl._is_avl(avl.root)}")

    subtitulo("Eliminar nodo con un solo hijo")
    avl2 = AVL()
    for i in [20, 10, 30, 25]:
        avl2.insert(ev(i))
    avl2.delete((2, 5.0, 30))
    print(f"  Inorden: {[e.id_evento for e in avl2.in_order()]}")
    print(f"  ¿AVL válido? {avl2._is_avl(avl2.root)}")


# =========================================================
# 5. MODO ESTRÉS Y RECUPERACIÓN
# =========================================================

def demo_modo_estres():
    titulo("5. MODO ESTRÉS Y RECUPERACIÓN GLOBAL (sección 8)")

    avl = AVL()
    avl.activar_modo_estres()
    print(f"  Modo estrés activo: {avl.modo_estres}")

    for i in [10, 20, 30, 40, 50, 60, 70, 80]:
        avl.insert(ev(i))

    subtitulo("Árbol en estrés (sin rotaciones)")
    avl.dibujar(mostrar_info=True)
    print(f"  Altura: {avl.height()}")
    print(f"  ¿AVL válido? {avl._is_avl(avl.root)}")

    subtitulo("Recuperación global")
    avl.recuperar_balance()
    avl.dibujar(mostrar_info=True)
    print(f"  Altura: {avl.height()}")
    print(f"  ¿AVL válido? {avl._is_avl(avl.root)}")
    print(f"  Inorden: {[e.id_evento for e in avl.in_order()]}")

    subtitulo("Desbalance mayor que 2")
    avl2 = AVL()
    avl2.activar_modo_estres()
    for i in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        avl2.insert(ev(i))
    print(f"  Altura en estrés: {avl2.height()}")
    raiz = avl2.root
    print(f"  Factor de balance de la raíz: {raiz.balance_factor}")
    avl2.recuperar_balance()
    print(f"  Altura tras recuperar: {avl2.height()}")
    print(f"  ¿AVL válido? {avl2._is_avl(avl2.root)}")


# =========================================================
# 6. COMPARACIÓN BST VS AVL
# =========================================================

def demo_bst_vs_avl():
    titulo("6. COMPARACIÓN BST vs AVL (sección 12)")

    ids = list(range(1, 16))

    bst = BST()
    avl = AVL()

    for i in ids:
        e1 = ev(i)
        e2 = ev(i)
        bst.insert(e1)
        avl.insert(e2)

    subtitulo("BST")
    bst.dibujar()
    print(f"  Altura BST: {bst.height()}")
    print(f"  Hojas BST: {bst.number_of_leaves()}")
    print(f"  Nodos BST: {bst.size()}")

    subtitulo("AVL")
    avl.dibujar(mostrar_info=True)
    print(f"  Altura AVL: {avl.height()}")
    print(f"  Hojas AVL: {avl.number_of_leaves()}")
    print(f"  Nodos AVL: {avl.size()}")
    print(f"  Rotaciones totales: {avl.rotaciones_realizadas}")

    subtitulo("Comparación")
    print(f"  BST altura = {bst.height()}, AVL altura = {avl.height()}")
    print(
        f"  Inorden BST == Inorden AVL: "
        f"{[e.id_evento for e in bst.in_order()] == [e.id_evento for e in avl.in_order()]}"
    )


# =========================================================
# 7. SISTEMA: CREAR, CONSULTAR, CORREGIR, ELIMINAR
# =========================================================

def demo_sistema_crud():
    titulo("7. CRUD EN EL SISTEMA (sección 6)")

    sistema = SistemaSismico()
    fecha = fecha_utc(2026, 9, 7, 10, 0, 0)

    subtitulo("Crear eventos")
    sistema.crear_evento(10, 5.2, 40.0, 200.0, 300.0, fecha, "ST-01")
    sistema.crear_evento(20, 6.5, 15.0, 500.0, 500.0, fecha, "ST-01")
    sistema.crear_evento(30, 4.0, 60.0, 700.0, 200.0, fecha, "ST-02")

    for eid in [10, 20, 30]:
        mostrar_evento(sistema.buscar_por_id(eid))

    subtitulo("Consultar evento activo")
    consulta = sistema.consultar_evento(20)
    print(f"  Estado: {consulta['estado']}")
    mostrar_evento(consulta["evento"])

    subtitulo("Corregir evento 10 (M 5.2 -> 6.2, H 40 -> 15)")
    sistema.corregir_evento(10, magnitud=6.2, profundidad=15.0)
    mostrar_evento(sistema.buscar_por_id(10))

    subtitulo("Marcar revisado evento 20")
    sistema.marcar_revisado(20)
    mostrar_evento(sistema.buscar_por_id(20))

    subtitulo("Eliminar evento 30")
    sistema.eliminar_evento(30)
    print(f"  Consulta 30: {sistema.consultar_evento(30)['estado']}")

    subtitulo("Intentar reutilizar ID eliminado")
    try:
        sistema.crear_evento(30, 5.0, 10.0, 100.0, 100.0, fecha, "ST-03")
        print("  ERROR: no debería permitir reutilizar el ID")
    except ValueError as e:
        print(f"  OK: {e}")

    subtitulo("Intentar duplicar ID activo")
    try:
        sistema.crear_evento(10, 5.0, 10.0, 100.0, 100.0, fecha, "ST-04")
        print("  ERROR: no debería permitir duplicar")
    except ValueError as e:
        print(f"  OK: {e}")


# =========================================================
# 8. COLA FIFO DE REPORTES
# =========================================================

def imprimir_resultado_reporte(numero, resultado):
    evento = resultado["evento"]
    eid = evento.id_evento if evento is not None else "None"
    print(f"\n  Paso {numero}")
    print(f"    Decisión: {resultado['decision']}")
    print(f"    Mensaje:  {resultado['mensaje']}")
    print(f"    Evento:   {eid}")
    print(f"    Rotaciones: {resultado['rotaciones']}")
    if "reporte" in resultado:
        print(f"    Reporte: {resultado['reporte']}")
        print(f"    Pendientes restantes: {resultado['pendientes_restantes']}")


def demo_reportes():
    titulo("8. COLA FIFO DE REPORTES (secciones 6 y 8)")

    sistema = SistemaSismico()
    fecha = fecha_utc(2026, 9, 7, 10, 0, 0)

    reportes = [
        Reporte(10, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-01"),
        Reporte(10, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-02"),  # confirmación
        Reporte(10, 6.2, 15.0, 100.0, 100.0, fecha, 2, "ST-03"),  # corrección
        Reporte(10, 6.5, 15.0, 100.0, 100.0, fecha, 2, "ST-04"),  # conflicto
        Reporte(10, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-05"),  # antiguo
        Reporte(20, 6.0, 10.0, 200.0, 200.0, fecha, 1, "ST-06"),  # nuevo
    ]

    for r in reportes:
        sistema.encolar_reporte(r)

    print(f"  Reportes en cola: {sistema.cantidad_reportes_pendientes()}")

    resultados = sistema.procesar_continuo()
    for i, res in enumerate(resultados, start=1):
        imprimir_resultado_reporte(i, res)

    subtitulo("Estado final del evento 10")
    e = sistema.buscar_por_id(10)
    mostrar_evento(e)
    print(f"    Estaciones: {sorted(e.estaciones)}")

    subtitulo("Métricas")
    for k, v in sistema.metricas.items():
        print(f"    {k}: {v}")


# =========================================================
# 9. REPORTES CON ARCHIVADO Y REACTIVACIÓN
# =========================================================

def demo_archivado_reactivacion():
    titulo("9. ARCHIVADO Y REACTIVACIÓN (sección 6)")

    sistema = SistemaSismico()
    fecha = fecha_utc(2026, 9, 7, 10, 0, 0)

    # Crear y archivar manualmente para la demo
    sistema.crear_evento(70, 4.8, 40.0, 200.0, 200.0, fecha, "ST-01")
    evento = sistema.buscar_por_id(70)

    sistema.avl.delete(evento.calcular_clave())
    del sistema._eventos_activos[70]
    evento.ubicacion = "archivado"
    sistema._historicos[70] = evento

    print(f"  Evento 70 archivado: {sistema.consultar_evento(70)['estado']}")

    subtitulo("Reporte antiguo sobre archivado")
    r1 = Reporte(70, 4.8, 40.0, 200.0, 200.0, fecha, 1, "ST-02")
    res1 = sistema.procesar_reporte(r1)
    print(f"  Decisión: {res1['decision']}")
    print(f"  Mensaje:  {res1['mensaje']}")

    subtitulo("Reporte con revisión mayor sobre archivado")
    r2 = Reporte(70, 6.1, 20.0, 200.0, 200.0, fecha, 2, "ST-03")
    res2 = sistema.procesar_reporte(r2)
    print(f"  Decisión: {res2['decision']}")
    print(f"  Mensaje:  {res2['mensaje']}")
    mostrar_evento(sistema.buscar_por_id(70))
    print(f"  Consulta 70: {sistema.consultar_evento(70)['estado']}")


# =========================================================
# 10. VALIDACIONES
# =========================================================

def demo_validaciones():
    titulo("10. VALIDACIONES (secciones 3 y 6)")

    sistema = SistemaSismico()
    fecha = fecha_utc(2026, 9, 7, 10, 0, 0)

    casos = [
        ("ID 0", dict(id_evento=0, magnitud=5.0, profundidad=10.0,
                      x=100.0, y=100.0)),
        ("ID 1000000", dict(id_evento=1000000, magnitud=5.0, profundidad=10.0,
                            x=100.0, y=100.0)),
        ("M = -2.5", dict(id_evento=1, magnitud=-2.5, profundidad=10.0,
                          x=100.0, y=100.0)),
        ("M = 10.5", dict(id_evento=1, magnitud=10.5, profundidad=10.0,
                          x=100.0, y=100.0)),
        ("H = -1", dict(id_evento=1, magnitud=5.0, profundidad=-1.0,
                        x=100.0, y=100.0)),
        ("H = 701", dict(id_evento=1, magnitud=5.0, profundidad=701.0,
                         x=100.0, y=100.0)),
        ("x = 1001", dict(id_evento=1, magnitud=5.0, profundidad=10.0,
                          x=1001.0, y=100.0)),
        ("y = -1", dict(id_evento=1, magnitud=5.0, profundidad=10.0,
                        x=100.0, y=-1.0)),
        ("M con dos decimales", dict(id_evento=1, magnitud=5.25,
                                     profundidad=10.0, x=100.0, y=100.0)),
    ]

    for desc, kwargs in casos:
        try:
            sistema.crear_evento(
                estacion="ST-01", fecha_hora=fecha, **kwargs
            )
            print(f"  [FALLO] {desc}: debería haber rechazado")
        except ValueError as e:
            print(f"  [OK] {desc}: {e}")

    subtitulo("Fechas sin zona horaria")
    from datetime import datetime as dt
    try:
        sistema.crear_evento(
            999, 5.0, 10.0, 100.0, 100.0,
            dt(2026, 9, 7, 10, 0, 0),  # sin tzinfo
            "ST-01",
        )
        print("  [FALLO] debería rechazar fecha sin tz")
    except ValueError as e:
        print(f"  [OK] {e}")


# =========================================================
# EJECUCIÓN PRINCIPAL
# =========================================================

if __name__ == "__main__":
    demo_mapa_y_zonas()
    demo_prioridad_y_clave()
    demo_rotaciones()
    demo_eliminacion()
    demo_modo_estres()
    demo_bst_vs_avl()
    demo_sistema_crud()
    demo_reportes()
    demo_archivado_reactivacion()
    demo_validaciones()

    titulo("FIN DE LAS PRUEBAS")