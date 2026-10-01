"""
Script de prueba manual para verificar que la persistencia JSON funciona.
Los archivos de prueba se guardan en la carpeta data/ del proyecto.

Estructura esperada:
    Proyecto/
    ├── data/              <-- aquí se guardan los JSON
    └── src/
        └── probar_persistencia.py

Ejecuta desde src/: python probar_persistencia.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from services.sistema_sismico import SistemaSismico
from persistence.json_saver import JsonSaver
from persistence.json_loader import JsonLoader
from models.report import Reporte


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def ruta(nombre):
    """Devuelve la ruta completa a un archivo dentro de data/."""
    return str(DATA_DIR / nombre)


def fecha(h=10):
    """Fecha UTC del 7 de septiembre de 2026 a la hora indicada."""
    return datetime(2026, 9, 7, h, 0, 0, tzinfo=timezone.utc)


def separador(titulo):
    print("\n" + "=" * 60)
    print(titulo)
    print("=" * 60)


def imprimir_resultado(nombre, ok, detalle=""):
    if ok:
        print(f"\n  [OK] {nombre} PASÓ")
    else:
        print(f"\n  [FALLO] {nombre} {detalle}")


print(f"Carpeta de datos: {DATA_DIR}")
print(f"Existe: {DATA_DIR.exists()}")


separador("PRUEBA 1: Guardar y cargar 3 eventos")

sistema = SistemaSismico()
sistema.saltar_reloj(fecha(12))

sistema.crear_evento(100, 6.5, 10.0, 250.0, 750.0, fecha(8), "ST-01")
sistema.crear_evento(110, 5.5, 20.0, 250.0, 750.0, fecha(9), "ST-01")
sistema.crear_evento(120, 4.0, 50.0, 750.0, 250.0, fecha(10), "ST-01")

print("ANTES de guardar:")
print(f"  Cantidad: {sistema.avl.size()}, Altura: {sistema.avl.height()}")
print(f"  Inorden:  {[e.id_evento for e in sistema.avl.in_order()]}")
print(f"  Raíz:     {sistema.avl.root.event.id_evento}")

archivo1 = ruta("prueba1.json")
JsonSaver.guardar(sistema, archivo1)
print(f"\n  -> Guardado en: {archivo1}")

restaurado = JsonLoader.cargar_topologia(archivo1)

print("\nDESPUÉS de cargar:")
print(f"  Cantidad: {restaurado.avl.size()}, Altura: {restaurado.avl.height()}")
print(f"  Inorden:  {[e.id_evento for e in restaurado.avl.in_order()]}")
print(f"  Raíz:     {restaurado.avl.root.event.id_evento}")

ok = (
    sistema.avl.size() == restaurado.avl.size()
    and sistema.avl.height() == restaurado.avl.height()
    and [e.id_evento for e in sistema.avl.in_order()]
        == [e.id_evento for e in restaurado.avl.in_order()]
    and sistema.avl.root.event.id_evento == restaurado.avl.root.event.id_evento
)
imprimir_resultado("PRUEBA 1", ok)


separador("PRUEBA 2: Guardar y cargar en modo estrés")

sistema2 = SistemaSismico()
sistema2.saltar_reloj(fecha(23))
sistema2.activar_modo_estres()
for i in range(200, 215):
    sistema2.crear_evento(i, 4.0, 50.0, 800.0, 200.0, fecha(10), "ST-01")

print(f"  Modo estrés: {sistema2.avl.modo_estres}, Altura: {sistema2.avl.height()}")

archivo2 = ruta("prueba2.json")
JsonSaver.guardar(sistema2, archivo2)
restaurado2 = JsonLoader.cargar_topologia(archivo2)

print(f"  Tras cargar: Modo estrés={restaurado2.avl.modo_estres}, "
      f"Altura={restaurado2.avl.height()}")

ok = (
    restaurado2.avl.modo_estres == sistema2.avl.modo_estres
    and restaurado2.avl.height() == sistema2.avl.height()
)
imprimir_resultado("PRUEBA 2", ok)


separador("PRUEBA 3: Guardar y cargar cola + métricas")

sistema3 = SistemaSismico()
sistema3.saltar_reloj(fecha(12))
sistema3.crear_evento(300, 5.0, 20.0, 100.0, 100.0, fecha(10), "ST-01")
sistema3.metricas["correcciones_aceptadas"] = 42
sistema3.metricas["conflictos"] = 7
sistema3.encolar_reporte(Reporte(
    999, 5.5, 20.0, 100.0, 100.0, fecha(10), 1, "ST-01"
))

print(f"  Correcciones: {sistema3.metricas['correcciones_aceptadas']}")
print(f"  Conflictos:   {sistema3.metricas['conflictos']}")
print(f"  Cola:         {len(sistema3.cola_reportes)}")

archivo3 = ruta("prueba3.json")
JsonSaver.guardar(sistema3, archivo3)
restaurado3 = JsonLoader.cargar_topologia(archivo3)

print(f"\n  Tras cargar:")
print(f"  Correcciones: {restaurado3.metricas['correcciones_aceptadas']}")
print(f"  Conflictos:   {restaurado3.metricas['conflictos']}")
print(f"  Cola:         {len(restaurado3.cola_reportes)}")

ok = (
    restaurado3.metricas["correcciones_aceptadas"] == 42
    and restaurado3.metricas["conflictos"] == 7
    and len(restaurado3.cola_reportes) == 1
)
imprimir_resultado("PRUEBA 3", ok)


separador("PRUEBA 4: Rechazar JSON con estructura rota")

data = json.loads(Path(archivo1).read_text(encoding="utf-8"))
nodo0 = data["active_tree"]["nodes"][0]
nodo0["right"] = nodo0["left"]
nodo0["left"] = None

archivo_malo = ruta("prueba_mala_estructura.json")
Path(archivo_malo).write_text(json.dumps(data), encoding="utf-8")

try:
    JsonLoader.cargar_topologia(archivo_malo)
    imprimir_resultado("PRUEBA 4", False, "(debería haber rechazado)")
except Exception as e:
    print(f"  [OK] Rechazado: {type(e).__name__}")
    print(f"       {str(e)[:80]}")
    imprimir_resultado("PRUEBA 4", True)


separador("PRUEBA 5: El sistema no cambia si la carga falla")

sistema5 = SistemaSismico()
sistema5.saltar_reloj(fecha(12))
sistema5.crear_evento(500, 5.0, 20.0, 100.0, 100.0, fecha(10), "ST-01")

size_antes = sistema5.avl.size()
altura_antes = sistema5.avl.height()
inorden_antes = [e.id_evento for e in sistema5.avl.in_order()]

print(f"  ANTES:   size={size_antes}, altura={altura_antes}, inorden={inorden_antes}")

try:
    JsonLoader.cargar_topologia(archivo_malo, sistema_actual=sistema5)
except Exception:
    pass

size_despues = sistema5.avl.size()
altura_despues = sistema5.avl.height()
inorden_despues = [e.id_evento for e in sistema5.avl.in_order()]

print(f"  DESPUÉS: size={size_despues}, altura={altura_despues}, inorden={inorden_despues}")

ok = (
    size_antes == size_despues
    and altura_antes == altura_despues
    and inorden_antes == inorden_despues
)
imprimir_resultado("PRUEBA 5 (rollback)", ok)


separador("PRUEBA 6: Carga por inserciones (AVL vs BST)")

sistema6, bst = JsonLoader.cargar_por_inserciones(archivo1)

print(f"  AVL altura: {sistema6.avl.height()}")
print(f"  BST altura: {bst.height()}")
print(f"  AVL size:   {sistema6.avl.size()}")
print(f"  BST size:   {bst.size()}")

inorden_avl = [e.id_evento for e in sistema6.avl.in_order()]
inorden_bst = [e.id_evento for e in bst.in_order()]
print(f"  Inorden AVL: {inorden_avl}")
print(f"  Inorden BST: {inorden_bst}")

ok = (
    inorden_avl == inorden_bst
    and sistema6.avl.size() == bst.size()
    and sistema6.avl.modo_estres is False
)
imprimir_resultado("PRUEBA 6", ok)


separador("PRUEBA 7: Rechazar JSON con prioridad incorrecta")

data = json.loads(Path(archivo1).read_text(encoding="utf-8"))
for nodo in data["active_tree"]["nodes"]:
    if nodo["event"]["id_evento"] == 120:
        nodo["event"]["prioridad"] = 3
        break

archivo_malo_prio = ruta("prueba_mala_prio.json")
Path(archivo_malo_prio).write_text(json.dumps(data), encoding="utf-8")

try:
    JsonLoader.cargar_topologia(archivo_malo_prio)
    imprimir_resultado("PRUEBA 7", False, "(debería rechazar)")
except Exception as e:
    print(f"  [OK] Rechazado: {type(e).__name__}")
    print(f"       {str(e)[:100]}")
    imprimir_resultado("PRUEBA 7", True)



separador("PRUEBA 8: Rechazar JSON con altura incorrecta")

data = json.loads(Path(archivo1).read_text(encoding="utf-8"))
data["active_tree"]["nodes"][0]["height"] = 99

archivo_malo_alt = ruta("prueba_mala_altura.json")
Path(archivo_malo_alt).write_text(json.dumps(data), encoding="utf-8")

try:
    JsonLoader.cargar_topologia(archivo_malo_alt)
    imprimir_resultado("PRUEBA 8", False, "(debería rechazar)")
except Exception as e:
    print(f"  [OK] Rechazado: {type(e).__name__}")
    print(f"       {str(e)[:100]}")
    imprimir_resultado("PRUEBA 8", True)


separador("PRUEBA 9: Rechazar JSON con ciclo")

data = json.loads(Path(archivo1).read_text(encoding="utf-8"))
raiz_id = data["active_tree"]["root"]
for nodo in data["active_tree"]["nodes"]:
    if nodo["left"] is None and nodo["right"] is None:
        nodo["left"] = raiz_id
        break

archivo_malo_ciclo = ruta("prueba_mala_ciclo.json")
Path(archivo_malo_ciclo).write_text(json.dumps(data), encoding="utf-8")

try:
    JsonLoader.cargar_topologia(archivo_malo_ciclo)
    imprimir_resultado("PRUEBA 9", False, "(debería rechazar)")
except Exception as e:
    print(f"  [OK] Rechazado: {type(e).__name__}")
    print(f"       {str(e)[:100]}")
    imprimir_resultado("PRUEBA 9", True)


separador("PRUEBA 10: Guardar → cargar → guardar produce lo mismo")

archivo_a = ruta("doble_a.json")
archivo_b = ruta("doble_b.json")

JsonSaver.guardar(sistema, archivo_a)
restaurado10 = JsonLoader.cargar_topologia(archivo_a)
JsonSaver.guardar(restaurado10, archivo_b)

data_a = json.loads(Path(archivo_a).read_text(encoding="utf-8"))
data_b = json.loads(Path(archivo_b).read_text(encoding="utf-8"))

data_a.pop("meta", None)
data_b.pop("meta", None)

if data_a == data_b:
    imprimir_resultado("PRUEBA 10", True)
else:
    diferencias = [c for c in data_a if data_a[c] != data_b.get(c)]
    print(f"  Claves con diferencias: {diferencias}")
    imprimir_resultado("PRUEBA 10", False, f"(diferencias en {diferencias})")


separador("FIN DE LAS PRUEBAS")
print(f"Los archivos de prueba están en: {DATA_DIR}")
print("\nRevisa arriba qué pruebas dicen [OK] y cuáles [FALLO].")