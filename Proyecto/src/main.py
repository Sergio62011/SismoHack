from datetime import datetime
from structure.avl import AVL
from structure.bst import BST
from models.event import Evento


def crear_eventos():
    return [
        Evento(id_evento=10, magnitud=5.2, profundidad=40.0,
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
for id_ev in [10, 20, 30, 40, 50, 60]:
    avl_estres.insert(crear_evento(id_ev))

print("\n--- AVL en modo ESTRÉS (sin rotaciones) ---")
avl_estres.dibujar()
print(f"Altura en estrés: {avl_estres.height()}")

print("\n--- Recuperando balance ---")
avl_estres.recuperar_balance()
avl_estres.dibujar()
print(f"Altura después de recuperar: {avl_estres.height()}")
print(f"Rotaciones realizadas: {avl_estres.rotaciones_realizadas}")