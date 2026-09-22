from datetime import datetime, timezone
from structure.avl import AVL
from structure.bst import BST
from models.event import Evento
from models.map import MapaSismico, Zona
from models.report import Reporte
from services.sistema_sismico import SistemaSismico


def demo_mapa_y_zonas():
    print("=" * 60)
    print("MAPA Y ZONAS")
    print("=" * 60)

    mapa = MapaSismico(filas=10, columnas=10)

    mapa.agregar_zona(Zona("Ciudad Norte", 100, 600, 450, 900, True))
    mapa.agregar_zona(Zona("Reserva Sur", 550, 100, 900, 350, False))
    mapa.agregar_zona(Zona("Ciudad Centro", 250, 250, 550, 550, True))

    eventos = [
        Evento(id_evento=101, magnitud=4.7, profundidad=20.0,
               x=300.0, y=700.0,
               fecha_hora=datetime(2026, 9, 7, 10, 0, 0)),
        Evento(id_evento=102, magnitud=5.1, profundidad=40.0,
               x=700.0, y=200.0,
               fecha_hora=datetime(2026, 9, 7, 11, 0, 0)),
        Evento(id_evento=103, magnitud=6.2, profundidad=15.0,
               x=500.0, y=500.0,
               fecha_hora=datetime(2026, 9, 7, 12, 0, 0)),
    ]

    for evento in eventos:
        mapa.asignar_zona_a_evento(evento)
        print(
            f"Evento {evento.id_evento}: "
            f"zona_poblada={evento.en_zona_poblada}, "
            f"prioridad={evento.prioridad}, "
            f"clave={evento.calcular_clave()}"
        )

    print()
    matriz = mapa.crear_matriz_con_eventos(eventos)
    mapa.imprimir_matriz(matriz)
    print()


def crear_eventos():
    return [
        Evento(id_evento=10, magnitud=5.2, profundidad=40.0,
               x=200.0, y=300.0,
               fecha_hora=datetime(2026, 9, 7, 10, 0, 0),
               zona_poblada=True),
        Evento(id_evento=12, magnitud=5.3, profundidad=10.0,
                       x=200.0, y=300.0,
                       fecha_hora=datetime(2026, 9, 7, 10, 0, 0),
                       zona_poblada=True),
        Evento(id_evento=20, magnitud=6.5, profundidad=15.0,
               x=500.0, y=500.0,
               fecha_hora=datetime(2026, 9, 7, 11, 0, 0),
               zona_poblada=True),
        Evento(id_evento=30, magnitud=4.0, profundidad=60.0,
               x=700.0, y=200.0,
               fecha_hora=datetime(2026, 9, 7, 12, 0, 0),
               zona_poblada=True),
        Evento(id_evento=40, magnitud=4.8, profundidad=25.0,
               x=300.0, y=400.0,
               fecha_hora=datetime(2026, 9, 7, 13, 0, 0),
               zona_poblada=True),
        Evento(id_evento=50, magnitud=5.8, profundidad=10.0,
               x=100.0, y=100.0,
               fecha_hora=datetime(2026, 9, 7, 14, 0, 0),
               zona_poblada=True),
        Evento(id_evento=60, magnitud=7.2, profundidad=20.0,
               x=800.0, y=800.0,
               fecha_hora=datetime(2026, 9, 7, 15, 0, 0),
               zona_poblada=True),
    ]


demo_mapa_y_zonas()


def imprimir_resultado_reporte(numero, resultado):
    evento = resultado["evento"]
    evento_id = evento.id_evento if evento is not None else "None"

    print(f"\nPaso {numero}")
    print(f"Decision: {resultado['decision']}")
    print(f"Mensaje: {resultado['mensaje']}")
    print(f"Evento afectado: {evento_id}")
    print(f"Rotaciones: {resultado['rotaciones']}")

    if "reporte" in resultado:
        print(f"Reporte procesado: {resultado['reporte']}")
        print(f"Reportes pendientes: {resultado['pendientes_restantes']}")


def demo_reportes():
    print("=" * 60)
    print("REPORTES CON COLA FIFO")
    print("=" * 60)

    sistema = SistemaSismico()
    fecha = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)

    reportes = [
        Reporte(10, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-01"),
        Reporte(10, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-02"),
        Reporte(10, 6.2, 15.0, 100.0, 100.0, fecha, 2, "ST-03"),
        Reporte(10, 6.5, 15.0, 100.0, 100.0, fecha, 2, "ST-04"),
        Reporte(10, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-05"),
    ]

    for reporte in reportes:
        sistema.encolar_reporte(reporte)

    print(f"Reportes en cola al inicio: {sistema.cantidad_reportes_pendientes()}")

    resultados = sistema.procesar_continuo()
    for indice, resultado in enumerate(resultados, start=1):
        imprimir_resultado_reporte(indice, resultado)

    evento = sistema.buscar_por_id(10)
    print("\nEstado final del evento 10")
    print(f"Revision: {evento.revision}")
    print(f"Magnitud: {evento.magnitud}")
    print(f"Prioridad: {evento.prioridad}")
    print(f"Estaciones: {sorted(evento.estaciones)}")
    print(f"Metricas: {sistema.metricas}")

    print("\nRotaciones producidas por reportes nuevos")
    sistema_rotaciones = SistemaSismico()
    for event_id in [100, 200, 300]:
        resultado = sistema_rotaciones.procesar_reporte(
            Reporte(event_id, 5.0, 40.0, 100.0, 100.0, fecha, 1, "ST-R")
        )
        print(
            f"Evento {event_id}: "
            f"decision={resultado['decision']}, "
            f"rotaciones={resultado['rotaciones']}"
        )

    print("\nEliminados y archivados")
    sistema_estados = SistemaSismico()
    sistema_estados.crear_evento(50, 5.0, 40.0, 100.0, 100.0, fecha, "ST-01")
    sistema_estados.eliminar_evento(50)
    resultado_eliminado = sistema_estados.procesar_reporte(
        Reporte(50, 6.0, 10.0, 100.0, 100.0, fecha, 2, "ST-02")
    )
    imprimir_resultado_reporte(1, resultado_eliminado)
    print(f"Consulta evento 50: {sistema_estados.consultar_evento(50)}")

    sistema_estados.crear_evento(70, 4.8, 40.0, 200.0, 200.0, fecha, "ST-01")
    evento_archivado = sistema_estados.buscar_por_id(70)

    # Archive manually only for this console demo.
    sistema_estados.avl.delete(evento_archivado.calcular_clave())
    del sistema_estados._eventos_activos[70]
    evento_archivado.ubicacion = "archivado"
    sistema_estados._historicos[70] = evento_archivado

    resultado_archivado = sistema_estados.procesar_reporte(
        Reporte(70, 4.8, 40.0, 200.0, 200.0, fecha, 1, "ST-02")
    )
    imprimir_resultado_reporte(2, resultado_archivado)
    print(f"Consulta evento 70: {sistema_estados.consultar_evento(70)}")

    resultado_reactivado = sistema_estados.procesar_reporte(
        Reporte(70, 6.1, 20.0, 200.0, 200.0, fecha, 2, "ST-03")
    )
    imprimir_resultado_reporte(3, resultado_reactivado)
    print(f"Consulta evento 70: {sistema_estados.consultar_evento(70)}")
    print()


demo_reportes()


# ============================================
# COMPARACIÓN BST vs AVL
# ============================================

print("=" * 60)
print("COMPARACIÓN: BST vs AVL (mismos datos)")
print("=" * 60)

bst = BST()
for e in crear_eventos():
    bst.insert(e)

print("\n--- BST ---")
bst.dibujar()
print(f"Altura BST: {bst.height()}")

avl = AVL()
for e in crear_eventos():
    avl.insert(e)

print("\n--- AVL ---")
avl.dibujar()
print(f"Altura AVL: {avl.height()}")
print(f"Rotaciones realizadas: {avl.rotaciones_realizadas}")


# ============================================
# CASOS DE ROTACIÓN
# ============================================

def crear_evento(id_evento, magnitud=5.0, profundidad=50.0):
    return Evento(id_evento=id_evento, magnitud=magnitud,
                  profundidad=profundidad, x=100.0, y=100.0,
                  fecha_hora=datetime(2026, 9, 7, 10, 0, 0),
                  zona_poblada=False)


print("\n" + "=" * 60)
print("CASOS DE ROTACIÓN")
print("=" * 60)

# Caso LL
print("\n--- Caso LL (30, 20, 10) ---")
avl_ll = AVL()
for id_ev in [30, 20, 10]:
    avl_ll.insert(crear_evento(id_ev))
avl_ll.dibujar()

# Caso RR
print("\n--- Caso RR (10, 20, 30) ---")
avl_rr = AVL()
for id_ev in [10, 20, 30]:
    avl_rr.insert(crear_evento(id_ev))
avl_rr.dibujar()

# Caso LR
print("\n--- Caso LR (30, 10, 20) ---")
avl_lr = AVL()
for id_ev in [30, 10, 20]:
    avl_lr.insert(crear_evento(id_ev))
avl_lr.dibujar()

# Caso RL
print("\n--- Caso RL (10, 30, 20) ---")
avl_rl = AVL()
for id_ev in [10, 30, 20]:
    avl_rl.insert(crear_evento(id_ev))
avl_rl.dibujar()


# ============================================
# MODO ESTRÉS
# ============================================

print("\n" + "=" * 60)
print("MODO ESTRÉS + RECUPERACIÓN")
print("=" * 60)

avl_estres = AVL()
avl_estres.activar_modo_estres()

# Insertar en orden → degenera en lista
for id_ev in [10, 12, 9, 20, 30, 40, 50, 60]:
    avl_estres.insert(crear_evento(id_ev))

print("\n--- AVL en modo ESTRÉS (sin rotaciones) ---")
avl_estres.dibujar()
print(f"Altura en estrés: {avl_estres.height()}")

print("\n--- Recuperando balance ---")
avl_estres.recuperar_balance()
avl_estres.dibujar()
print(f"Altura después de recuperar: {avl_estres.height()}")
print(f"Rotaciones realizadas: {avl_estres.rotaciones_realizadas}")
