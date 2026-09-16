from structure.bst import BST
from datetime import datetime
from models.event import Evento

arbolBST = BST()

eventos_basicos = [
    Evento(
        id_evento=10, magnitud=5.2, profundidad=40.0,
        x=200.0, y=300.0,
        fecha_hora=datetime(2026, 9, 7, 10, 0, 0),
        revision=1, estado="pendiente", zona_poblada=True
    ),
    Evento(
        id_evento=20, magnitud=6.5, profundidad=15.0,
        x=500.0, y=500.0,
        fecha_hora=datetime(2026, 9, 7, 11, 0, 0),
        revision=1, estado="pendiente", zona_poblada=True
    ),
    Evento(
        id_evento=30, magnitud=4.0, profundidad=60.0,
        x=700.0, y=200.0,
        fecha_hora=datetime(2026, 9, 7, 12, 0, 0),
        revision=1, estado="pendiente", zona_poblada=True
    ),
    Evento(
        id_evento=40, magnitud=4.8, profundidad=25.0,
        x=300.0, y=400.0,
        fecha_hora=datetime(2026, 9, 7, 13, 0, 0),
        revision=1, estado="pendiente", zona_poblada=True
    ),
    Evento(
        id_evento=50, magnitud=5.8, profundidad=10.0,
        x=100.0, y=100.0,
        fecha_hora=datetime(2026, 9, 7, 14, 0, 0),
        revision=1, estado="pendiente", zona_poblada=True
    ),
    Evento(
        id_evento=60, magnitud=7.2, profundidad=20.0,
        x=800.0, y=800.0,
        fecha_hora=datetime(2026, 9, 7, 15, 0, 0),
        revision=1, estado="pendiente", zona_poblada=True
    ),
]

for evento in eventos_basicos:
    arbolBST.insert(evento)
 
arbolBST.dibujar()

print("\n--- Inorden (menor a mayor) ---")
for e in arbolBST.in_order():
    print(f"  ID:{e.id_evento} → K={e.calcular_clave()}")