"""
Test de micrófono para macOS - Muestra nivel de audio en tiempo real
"""
import pyaudio
import struct
import math

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
THRESHOLD = 500  # Nivel mínimo para detectar sonido


def get_rms(data):
    """Calcula el nivel RMS del audio"""
    count = len(data) // 2
    format_str = "%dh" % count
    shorts = struct.unpack(format_str, data)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count) if count > 0 else 0


def main():
    print("=" * 60)
    print("🎙️  TEST DE MICRÓFONO EN TIEMPO REAL - macOS")
    print("=" * 60)
    
    p = pyaudio.PyAudio()
    
    # Mostrar micrófono por defecto
    try:
        default_input = p.get_default_input_device_info()
        print(f"\n✅ Micrófono: {default_input['name']}")
    except Exception as e:
        print(f"\n❌ No se puede acceder al micrófono: {e}")
        print("\n⚠️  SOLUCIÓN:")
        print("   1. Abre: Configuración del Sistema > Privacidad y Seguridad > Micrófono")
        print("   2. Activa el permiso para 'Terminal'")
        print("   3. Cierra y vuelve a abrir la Terminal")
        p.terminate()
        return
    
    print("\n🔊 Habla y deberías ver las barras moverse...")
    print("   Presiona Ctrl+C para salir\n")
    print("-" * 60)
    
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
    except Exception as e:
        print(f"❌ Error abriendo micrófono: {e}")
        p.terminate()
        return
    
    max_level = 0
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = get_rms(data)
            
            # Actualizar máximo
            if rms > max_level:
                max_level = rms
            
            # Calcular barras (normalizado)
            bar_length = min(int(rms / 100), 50)
            bar = "█" * bar_length + "░" * (50 - bar_length)
            
            # Color según nivel
            if rms > THRESHOLD:
                status = "🟢 DETECTADO"
            else:
                status = "🔴 silencio "
            
            print(f"\r   [{bar}] {int(rms):5d} {status}", end="", flush=True)
            
    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print(f"\n📊 Nivel máximo detectado: {int(max_level)}")
        
        if max_level < THRESHOLD:
            print("\n⚠️  El micrófono NO está capturando audio correctamente")
            print("\n🔧 SOLUCIONES:")
            print("   1. Ve a: Configuración del Sistema > Privacidad y Seguridad > Micrófono")
            print("   2. Busca 'Terminal' y ACTIVA el permiso")
            print("   3. CIERRA la Terminal completamente (Cmd+Q)")
            print("   4. Vuelve a abrir la Terminal y ejecuta este test de nuevo")
        else:
            print("\n✅ ¡El micrófono funciona correctamente!")
    
    stream.stop_stream()
    stream.close()
    p.terminate()


if __name__ == "__main__":
    main()
