"""
Script de testing para el Anonimizador Judicial

Simula el proceso completo:
1. Upload de documento de prueba
2. Verificación de procesamiento
3. Download del resultado
4. Impresión de resultados y warnings
"""
import requests
import json
import time
from pathlib import Path

# Configuración
API_BASE = "http://localhost:8000"
TEST_FILE = Path(__file__).parent / "documento_prueba.docx"

def print_section(title):
    """Imprime un separador visual"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def check_health():
    """Verifica que el servidor esté corriendo"""
    print_section("1. VERIFICANDO SERVIDOR")

    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        data = response.json()

        print(f"✓ Servidor: {data['status']}")
        print(f"✓ LLM endpoint: {data['llm_endpoint']}")
        return True
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: No se puede conectar al servidor")
        print(f"  Asegúrate de que el servidor esté corriendo:")
        print(f"  cd backend && python main.py")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def upload_document():
    """Sube documento de prueba"""
    print_section("2. SUBIENDO DOCUMENTO")

    if not TEST_FILE.exists():
        print(f"✗ ERROR: Archivo no encontrado: {TEST_FILE}")
        print(f"  Ejecuta primero: python create_test_doc.py")
        return None

    print(f"Archivo: {TEST_FILE.name}")
    print(f"Tamaño: {TEST_FILE.stat().st_size:,} bytes")

    try:
        with open(TEST_FILE, "rb") as f:
            files = {"file": (TEST_FILE.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

            print("\n⏳ Procesando (esto puede tomar varios segundos)...")
            start_time = time.time()

            response = requests.post(
                f"{API_BASE}/upload",
                files=files,
                timeout=300  # 5 minutos timeout
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                print(f"\n✓ Procesamiento exitoso ({elapsed:.2f}s)")
                return data
            else:
                error = response.json()
                print(f"\n✗ ERROR {response.status_code}: {error.get('detail', 'Error desconocido')}")
                return None

    except requests.exceptions.Timeout:
        print("\n✗ ERROR: Timeout (el servidor tardó demasiado)")
        print("  Posibles causas:")
        print("  - El LLM no está respondiendo")
        print("  - El documento es muy grande")
        print("  - Verifica logs del servidor")
        return None
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return None

def show_results(data):
    """Muestra resultados del procesamiento"""
    print_section("3. RESULTADOS")

    # Información básica
    print("📄 Documento:")
    print(f"  - File ID: {data['file_id']}")
    print(f"  - Nombre original: {data['original_name']}")
    print(f"  - Formato: {data['format'].upper()}")
    print(f"  - Estado: {data['status']}")
    print(f"  - Mensaje: {data['message']}")

    # Estadísticas
    stats = data.get('stats', {})
    print("\n📊 Estadísticas:")
    print(f"  - Entidades encontradas: {stats.get('entities_found', 0)}")
    print(f"  - Reemplazos realizados: {stats.get('replacements_made', 0)}")
    print(f"  - Tiempo de procesamiento: {stats.get('processing_time_seconds', 0):.2f}s")
    print(f"  - Caracteres originales: {stats.get('original_chars', 0):,}")
    print(f"  - Caracteres anonimizados: {stats.get('anonymized_chars', 0):,}")

    # Warnings
    warnings = data.get('warnings', [])
    if warnings:
        print(f"\n⚠️  Advertencias ({len(warnings)}):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    else:
        print("\n✓ Sin advertencias")

    return data['file_id']

def download_result(file_id):
    """Descarga documento anonimizado"""
    print_section("4. DESCARGA")

    try:
        response = requests.get(f"{API_BASE}/download/{file_id}", timeout=30)

        if response.status_code == 200:
            # Guardar archivo
            output_path = Path(__file__).parent / f"resultado_test_{file_id[:8]}.docx"
            with open(output_path, "wb") as f:
                f.write(response.content)

            print(f"✓ Documento anonimizado guardado:")
            print(f"  {output_path}")
            print(f"  Tamaño: {len(response.content):,} bytes")

            return output_path
        else:
            error = response.json()
            print(f"✗ ERROR {response.status_code}: {error.get('detail', 'Error desconocido')}")
            return None

    except Exception as e:
        print(f"✗ ERROR: {e}")
        return None

def check_status():
    """Verifica estado del sistema"""
    print_section("5. ESTADO DEL SISTEMA")

    try:
        response = requests.get(f"{API_BASE}/api/status", timeout=5)
        data = response.json()

        print(f"Estado: {data['status']}")
        print(f"Archivos activos: {data['active_files']}")
        print(f"Espacio usado: {data['total_size_mb']} MB")
        print(f"Directorio temporal: {data['tmp_dir']}")
        print(f"Tamaño máximo de archivo: {data['max_file_size_mb']:.0f} MB")

    except Exception as e:
        print(f"✗ ERROR: {e}")

def main():
    """Ejecuta test completo"""
    print("\n" + "🔬 TEST DEL ANONIMIZADOR JUDICIAL".center(60, " "))

    # 1. Verificar servidor
    if not check_health():
        return

    # 2. Subir documento
    result = upload_document()
    if not result:
        return

    # 3. Mostrar resultados
    file_id = show_results(result)

    # 4. Descargar resultado
    output_file = download_result(file_id)

    # 5. Estado del sistema
    check_status()

    # Resumen final
    print_section("✅ TEST COMPLETADO")

    if output_file:
        print("📝 Revisión manual:")
        print(f"  1. Abre el archivo: {output_file}")
        print("  2. Verifica que las partes estén anonimizadas:")
        print("     - Actor: Juan Carlos Pérez → [ACTOR]")
        print("     - Demandado: María Laura González → [DEMANDADO]")
        print("     - Testigos: Pedro López, Ana Fernández → [TESTIGO_X]")
        print("     - DNI, CUIL, domicilios, emails, teléfonos → [DOCUMENTO], [DOMICILIO], etc.")
        print("  3. Verifica que se preserven:")
        print("     - Doctrinarios: Lorenzetti")
        print("     - Jurisprudencia: CSJN, Fallos")
        print("     - Magistrado: Dr. Juan Martínez")

    print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    main()
