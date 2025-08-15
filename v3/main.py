import speech_recognition as sr
import pyttsx3
import re
import math
import threading
import time
import json
import os
from datetime import datetime
import queue
import sys

class CalculadoraVozLinux:
    def __init__(self):
        # Configuración inicial
        self.config = self.cargar_configuracion()
        
        # Variables de estado
        self.ultimo_resultado = 0
        self.historial = []
        self.modo_continuo = False
        self.pausado = False
        
        # Cola para manejo de comandos
        self.cola_comandos = queue.Queue()
        
        # Inicializar componentes de audio
        self.inicializar_audio()
        
        # Patrones de operaciones
        self.inicializar_patrones()
        
        # Palabras de activación para modo manos libres
        self.palabras_activacion = ['calculadora', 'oye calculadora', 'hey calculadora']
    
    def cargar_configuracion(self):
        """Carga configuración desde archivo JSON"""
        config_default = {
            'velocidad_voz': 180,
            'volumen_voz': 0.9,
            'timeout_escucha': 10,
            'guardar_historial': True,
            'modo_verboso': True,
            'idioma_reconocimiento': 'es-ES',
            'precision_decimales': 4,
            'usar_hotkeys': False  # Deshabilitado por defecto en Linux
        }
        
        try:
            if os.path.exists('calculadora_config.json'):
                with open('calculadora_config.json', 'r', encoding='utf-8') as f:
                    config_guardada = json.load(f)
                    config_default.update(config_guardada)
        except Exception as e:
            print(f"Info: Usando configuración por defecto ({e})")
        
        return config_default
    
    def inicializar_audio(self):
        """Inicializa los componentes de audio con manejo de errores para Linux"""
        print("🔧 Configurando audio...")
        
        # Configurar síntesis de voz con manejo de errores
        try:
            self.tts_engine = pyttsx3.init()
            self.configurar_voz()
            print("✅ Síntesis de voz configurada correctamente")
        except Exception as e:
            print(f"⚠️  Advertencia TTS: {e}")
            print("📝 Usando salida de texto como respaldo")
            self.tts_engine = None
        
        # Configurar reconocimiento de voz
        try:
            self.recognizer = sr.Recognizer()
            # Configurar parámetros para mejor rendimiento en Linux
            self.recognizer.energy_threshold = 4000
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.5
            
            # Intentar inicializar micrófono
            self.inicializar_microfono()
            print("✅ Micrófono configurado correctamente")
            
        except Exception as e:
            print(f"❌ Error configurando micrófono: {e}")
            print("💡 Soluciones sugeridas:")
            print("   1. sudo usermod -a -G audio $USER")
            print("   2. pulseaudio --start")
            print("   3. sudo apt-get install portaudio19-dev python3-pyaudio")
            raise
        
        # Configurar teclas rápidas solo si es posible
        if self.config['usar_hotkeys']:
            self.configurar_hotkeys()
    
    def inicializar_microfono(self):
        """Inicializa el micrófono con múltiples intentos"""
        mic_inicializado = False
        
        # Intentar diferentes índices de micrófono
        for mic_index in [None, 0, 1, 2]:
            try:
                if mic_index is None:
                    self.microphone = sr.Microphone()
                else:
                    self.microphone = sr.Microphone(device_index=mic_index)
                
                # Probar el micrófono
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                mic_inicializado = True
                if mic_index is not None:
                    print(f"🎤 Usando micrófono índice: {mic_index}")
                break
                
            except Exception as e:
                if mic_index is None:
                    print(f"⚠️  Micrófono por defecto falló: {e}")
                continue
        
        if not mic_inicializado:
            print("📋 Dispositivos de audio disponibles:")
            try:
                for i, mic_name in enumerate(sr.Microphone.list_microphone_names()):
                    print(f"   {i}: {mic_name}")
            except:
                print("   No se pudieron listar los dispositivos")
            
            raise Exception("No se pudo inicializar ningún micrófono")
    
    def configurar_voz(self):
        """Configura las propiedades de la voz"""
        if not self.tts_engine:
            return
            
        try:
            voices = self.tts_engine.getProperty('voices')
            
            if voices:
                # Buscar voz en español
                for voice in voices:
                    if voice and hasattr(voice, 'id'):
                        if any(lang in voice.id.lower() for lang in ['es', 'spanish', 'español']):
                            self.tts_engine.setProperty('voice', voice.id)
                            print(f"🗣️  Usando voz: {voice.id}")
                            break
            
            # Configurar propiedades
            self.tts_engine.setProperty('rate', self.config['velocidad_voz'])
            self.tts_engine.setProperty('volume', self.config['volumen_voz'])
            
        except Exception as e:
            print(f"⚠️  Error configurando voz: {e}")
    
    def configurar_hotkeys(self):
        """Configura teclas de acceso rápido con manejo seguro"""
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+shift+space', self.toggle_escucha)
            keyboard.add_hotkey('ctrl+shift+h', self.leer_historial)
            keyboard.add_hotkey('ctrl+shift+c', self.limpiar_historial)
            keyboard.add_hotkey('ctrl+shift+p', self.toggle_pausa)
            keyboard.add_hotkey('esc', self.salir_seguro)
            print("⌨️  Teclas rápidas configuradas (requiere permisos de administrador)")
        except ImportError:
            print("📦 keyboard no instalado. Teclas rápidas deshabilitadas.")
            print("   Instalar con: pip install keyboard")
        except Exception as e:
            print(f"⚠️  Teclas rápidas no disponibles: {e}")
            print("💡 En Linux, las teclas rápidas requieren ejecutar como root:")
            print("   sudo python3 calculadora_voz.py")
    
    def inicializar_patrones(self):
        """Inicializa patrones de reconocimiento de operaciones"""
        self.patrones_operaciones = {
            # Operaciones básicas con más variaciones
            r'\b(\d+(?:\.\d+)?)\s*(?:más|mas|suma|sumado|plus|\+)\s*(\d+(?:\.\d+)?)\b': 
                lambda x, y: (float(x) + float(y), 'suma'),
            
            r'\b(\d+(?:\.\d+)?)\s*(?:menos|resta|restado|restar|-)\s*(\d+(?:\.\d+)?)\b': 
                lambda x, y: (float(x) - float(y), 'resta'),
            
            r'\b(\d+(?:\.\d+)?)\s*(?:por|multiplicado|multiplicar|times|\*|x)\s*(?:por\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x, y: (float(x) * float(y), 'multiplicación'),
            
            r'\b(\d+(?:\.\d+)?)\s*(?:entre|dividido|dividir|division|/)\s*(?:por\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x, y: (float(x) / float(y) if float(y) != 0 else None, 'división'),
            
            r'\b(\d+(?:\.\d+)?)\s*(?:elevado|potencia|exponente|\^|\*\*)\s*(?:a\s*(?:la\s*)?)?(\d+(?:\.\d+)?)\b': 
                lambda x, y: (float(x) ** float(y), 'potencia'),
            
            # Operaciones con resultado anterior
            r'\b(?:resultado|anterior)\s*(?:más|mas|\+)\s*(\d+(?:\.\d+)?)\b':
                lambda x: (self.ultimo_resultado + float(x), 'suma con resultado anterior'),
            
            r'\b(?:resultado|anterior)\s*(?:menos|-)\s*(\d+(?:\.\d+)?)\b':
                lambda x: (self.ultimo_resultado - float(x), 'resta con resultado anterior'),
            
            r'\b(?:resultado|anterior)\s*(?:por|\*)\s*(\d+(?:\.\d+)?)\b':
                lambda x: (self.ultimo_resultado * float(x), 'multiplicación con resultado anterior'),
            
            # Operaciones unarias
            r'\braíz\s*cuadrada\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.sqrt(float(x)), 'raíz cuadrada'),
            
            r'\braíz\s*cúbica\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (float(x) ** (1/3), 'raíz cúbica'),
            
            r'\bseno\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.sin(math.radians(float(x))), 'seno'),
            
            r'\bcoseno\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.cos(math.radians(float(x))), 'coseno'),
            
            r'\btangente\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.tan(math.radians(float(x))), 'tangente'),
            
            r'\blogaritmo\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.log10(float(x)) if float(x) > 0 else None, 'logaritmo base 10'),
            
            r'\blogaritmo\s*natural\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.log(float(x)) if float(x) > 0 else None, 'logaritmo natural'),
            
            r'\bfactorial\s*(?:de\s*)?(\d+)\b': 
                lambda x: (math.factorial(int(x)) if int(x) >= 0 and int(x) <= 170 else None, 'factorial'),
            
            # Porcentajes
            r'\b(\d+(?:\.\d+)?)\s*porciento\s*(?:de\s*)?(\d+(?:\.\d+)?)\b':
                lambda x, y: (float(x) * float(y) / 100, 'porcentaje'),
            
            # Conversiones básicas
            r'\b(\d+(?:\.\d+)?)\s*grados\s*(?:celsius\s*)?a\s*fahrenheit\b':
                lambda x: (float(x) * 9/5 + 32, 'conversión celsius a fahrenheit'),
            
            r'\b(\d+(?:\.\d+)?)\s*grados\s*fahrenheit\s*a\s*celsius\b':
                lambda x: ((float(x) - 32) * 5/9, 'conversión fahrenheit a celsius'),
        }
    
    def hablar(self, texto, prioridad='normal'):
        """Convierte texto a voz con respaldo a texto"""
        if self.pausado and prioridad != 'alta':
            return
        
        # Siempre mostrar en consola
        print(f"🔊 {texto}")
        
        # Intentar síntesis de voz si está disponible
        if self.tts_engine:
            try:
                self.tts_engine.say(texto)
                self.tts_engine.runAndWait()
            except Exception as e:
                if self.config['modo_verboso']:
                    print(f"⚠️  Error TTS: {e}")
        else:
            # Respaldo: pausa para simular tiempo de habla
            time.sleep(len(texto) * 0.05)
    
    def escuchar(self, timeout=None):
        """Escucha con manejo robusto de errores"""
        if timeout is None:
            timeout = self.config['timeout_escucha']
        
        intentos = 3
        for intento in range(intentos):
            try:
                print(f"🎤 Escuchando... (intento {intento + 1}/{intentos})")
                
                with self.microphone as source:
                    # Ajuste rápido al ruido ambiente
                    if intento == 0:
                        print("🔧 Ajustando al ruido ambiente...")
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Escuchar con timeout reducido en reintentos
                    current_timeout = timeout if intento == 0 else timeout // 2
                    audio = self.recognizer.listen(source, timeout=current_timeout, phrase_time_limit=10)
                
                print("🔄 Procesando audio...")
                
                # Intentar reconocimiento con Google primero
                try:
                    texto = self.recognizer.recognize_google(
                        audio, 
                        language=self.config['idioma_reconocimiento']
                    )
                    print(f"📝 Escuchado: {texto}")
                    return texto.lower()
                
                except sr.UnknownValueError:
                    if intento < intentos - 1:
                        print("🔄 No se entendió, reintentando...")
                        continue
                    return "no_entendido"
                
                except sr.RequestError as e:
                    print(f"⚠️  Error del servicio de reconocimiento: {e}")
                    # Intentar reconocimiento offline si está disponible
                    try:
                        texto = self.recognizer.recognize_sphinx(audio)
                        print(f"📝 Escuchado (offline): {texto}")
                        return texto.lower()
                    except:
                        if intento < intentos - 1:
                            continue
                        return "error_servicio"
                
            except sr.WaitTimeoutError:
                if intento < intentos - 1:
                    print("⏱️  Timeout, reintentando...")
                    continue
                return "timeout"
            
            except Exception as e:
                print(f"❌ Error en escucha (intento {intento + 1}): {e}")
                if intento < intentos - 1:
                    time.sleep(0.5)
                    continue
                return "error"
        
        return "error"
    
    def procesar_operacion(self, texto):
        """Procesamiento de operaciones con mejor manejo de errores"""
        texto_original = texto
        texto = re.sub(r'[,.]', '.', texto)  # Normalizar decimales
        
        # Convertir números escritos en palabras
        texto = self.convertir_numeros_texto(texto)
        
        for patron, operacion in self.patrones_operaciones.items():
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                try:
                    grupos = match.groups()
                    
                    if len(grupos) == 1:  # Operaciones unarias
                        resultado_tupla = operacion(grupos[0])
                    else:  # Operaciones binarias
                        resultado_tupla = operacion(grupos[0], grupos[1])
                    
                    if isinstance(resultado_tupla, tuple):
                        resultado, tipo_operacion = resultado_tupla
                    else:
                        resultado, tipo_operacion = resultado_tupla, "operación"
                    
                    if resultado is None:
                        return None, "Error: Operación no válida (división por cero, logaritmo negativo, etc.)"
                    
                    # Verificar si el resultado es válido
                    if math.isnan(resultado) or math.isinf(resultado):
                        return None, "Error: El resultado no es un número válido"
                    
                    # Guardar en historial
                    self.ultimo_resultado = resultado
                    entrada_historial = {
                        'operacion': texto_original,
                        'resultado': resultado,
                        'tipo': tipo_operacion,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    self.historial.append(entrada_historial)
                    
                    # Limitar historial
                    if len(self.historial) > 50:
                        self.historial = self.historial[-50:]
                    
                    return resultado, f"El resultado de la {tipo_operacion} es {self.formatear_numero(resultado)}"
                    
                except (ValueError, ZeroDivisionError, OverflowError, ArithmeticError) as e:
                    return None, f"Error matemático: {str(e)}"
                except Exception as e:
                    return None, f"Error procesando operación: {str(e)}"
        
        return None, "No reconocí la operación. Prueba con algo como 'cinco más tres' o 'diez por dos'."
    
    def convertir_numeros_texto(self, texto):
        """Convierte números escritos en palabras a dígitos"""
        numeros_texto = {
            'cero': '0', 'uno': '1', 'dos': '2', 'tres': '3', 'cuatro': '4',
            'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9',
            'diez': '10', 'once': '11', 'doce': '12', 'trece': '13', 'catorce': '14',
            'quince': '15', 'dieciséis': '16', 'diecisiete': '17', 'dieciocho': '18',
            'diecinueve': '19', 'veinte': '20', 'treinta': '30', 'cuarenta': '40',
            'cincuenta': '50', 'sesenta': '60', 'setenta': '70', 'ochenta': '80',
            'noventa': '90', 'cien': '100'
        }
        
        for palabra, numero in numeros_texto.items():
            texto = re.sub(r'\b' + palabra + r'\b', numero, texto, flags=re.IGNORECASE)
        
        return texto
    
    def formatear_numero(self, numero):
        """Formateo mejorado de números"""
        try:
            if abs(numero - int(numero)) < 1e-10:
                return str(int(numero))
            else:
                precision = self.config['precision_decimales']
                formatted = f"{numero:.{precision}f}".rstrip('0').rstrip('.')
                return formatted
        except:
            return str(numero)
    
    def leer_historial(self):
        """Lee las últimas operaciones del historial"""
        if not self.historial:
            self.hablar("El historial está vacío")
            return
        
        ultimas_5 = self.historial[-5:]
        self.hablar("Estas son tus últimas operaciones:")
        
        for i, entrada in enumerate(ultimas_5, 1):
            resultado_formateado = self.formatear_numero(entrada['resultado'])
            mensaje = f"Operación {i}: {entrada['operacion']}, resultado: {resultado_formateado}"
            self.hablar(mensaje)
            time.sleep(0.5)
    
    def limpiar_historial(self):
        """Limpia el historial"""
        self.historial.clear()
        self.ultimo_resultado = 0
        self.hablar("Historial limpiado")
    
    def toggle_escucha(self):
        """Activa/desactiva el modo de escucha continua"""
        self.modo_continuo = not self.modo_continuo
        if self.modo_continuo:
            self.hablar("Modo de escucha continua activado. Di 'calculadora' para activarme.")
            threading.Thread(target=self.escuchar_continuo, daemon=True).start()
        else:
            self.hablar("Modo de escucha continua desactivado")
    
    def toggle_pausa(self):
        """Pausa/reanuda la calculadora"""
        self.pausado = not self.pausado
        if self.pausado:
            self.hablar("Calculadora pausada", 'alta')
        else:
            self.hablar("Calculadora reactivada", 'alta')
    
    def escuchar_continuo(self):
        """Modo de escucha continua"""
        self.hablar("Escucha continua iniciada. Di 'calculadora' seguido de tu operación.")
        
        while self.modo_continuo:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                
                texto = self.recognizer.recognize_google(
                    audio, 
                    language=self.config['idioma_reconocimiento']
                )
                
                if any(activacion in texto.lower() for activacion in self.palabras_activacion):
                    self.hablar("Te escucho", 'alta')
                    comando = self.escuchar(timeout=8)
                    if comando not in ['timeout', 'no_entendido', 'error', 'error_servicio']:
                        self.cola_comandos.put(comando)
                        
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                continue
            except Exception as e:
                if self.config['modo_verboso']:
                    print(f"Error en escucha continua: {e}")
                time.sleep(1)
    
    def mostrar_ayuda_completa(self):
        """Ayuda completa del sistema"""
        ayuda_texto = """
🧮 CALCULADORA DE VOZ - AYUDA COMPLETA

📊 OPERACIONES BÁSICAS:
• Suma: "cinco más tres", "5 + 3"
• Resta: "diez menos cuatro", "10 - 4"  
• Multiplicación: "seis por siete", "6 * 7"
• División: "veinte entre cuatro", "20 / 4"
• Potencias: "dos elevado a tres", "2 ^ 3"

🔬 OPERACIONES AVANZADAS:
• Raíz cuadrada: "raíz cuadrada de 16"
• Raíz cúbica: "raíz cúbica de 8"
• Trigonometría: "seno de 30", "coseno de 60"
• Logaritmos: "logaritmo de 100", "logaritmo natural de 10"
• Factorial: "factorial de 5"
• Porcentaje: "30 porciento de 200"

🌡️ CONVERSIONES:
• Temperatura: "25 grados celsius a fahrenheit"

📝 COMANDOS ESPECIALES:
• "historial" - Ver operaciones anteriores
• "limpiar historial" - Borrar historial
• "resultado más 10" - Usar resultado anterior
• "configuración" - Cambiar ajustes
• "escucha continua" - Modo manos libres
• "pausar" - Pausar temporalmente
• "salir" - Cerrar calculadora

⌨️ TECLAS RÁPIDAS (si están disponibles):
• Ctrl+Shift+Espacio: Escucha continua
• Ctrl+Shift+H: Leer historial
• Ctrl+Shift+C: Limpiar historial  
• Ctrl+Shift+P: Pausar
• Esc: Salir

💡 CONSEJOS:
• Habla claro y cerca del micrófono
• Puedes decir números como "cinco" o "5"
• El resultado se guarda para la siguiente operación
        """
        print(ayuda_texto)
        
        self.hablar("Te explico las funciones principales.")
        self.hablar("Operaciones básicas: suma, resta, multiplicación, división y potencias.")
        self.hablar("Funciones avanzadas: raíces, trigonometría, logaritmos, factorial y porcentajes.")
        self.hablar("Comandos especiales: historial, limpiar, configuración, y puedes usar el resultado anterior.")
        self.hablar("Para más detalles, revisa el texto en pantalla.")
    
    def configurar_ajustes(self):
        """Configuración de ajustes por voz"""
        opciones = [
            "velocidad de voz",
            "volumen", 
            "timeout de escucha",
            "modo verboso",
            "precisión de decimales"
        ]
        
        self.hablar("¿Qué quieres configurar? Opciones: " + ", ".join(opciones))
        respuesta = self.escuchar()
        
        if 'velocidad' in respuesta:
            self.ajustar_velocidad_voz()
        elif 'volumen' in respuesta:
            self.ajustar_volumen()
        elif 'timeout' in respuesta:
            self.ajustar_timeout()
        elif 'verboso' in respuesta:
            self.toggle_modo_verboso()
        elif 'precision' in respuesta or 'decimal' in respuesta:
            self.ajustar_precision()
        else:
            self.hablar("No reconocí esa opción de configuración.")
    
    def ajustar_velocidad_voz(self):
        """Ajusta la velocidad de la voz"""
        self.hablar("Di un número entre 100 y 300 para la velocidad")
        respuesta = self.escuchar()
        
        try:
            match = re.search(r'\d+', respuesta)
            if match:
                nueva_velocidad = int(match.group())
                if 100 <= nueva_velocidad <= 300:
                    self.config['velocidad_voz'] = nueva_velocidad
                    if self.tts_engine:
                        self.tts_engine.setProperty('rate', nueva_velocidad)
                    self.hablar(f"Velocidad cambiada a {nueva_velocidad}")
                    self.guardar_configuracion()
                else:
                    self.hablar("La velocidad debe estar entre 100 y 300")
            else:
                self.hablar("No detecté un número válido")
        except Exception as e:
            self.hablar("Error ajustando la velocidad")
    
    def ajustar_volumen(self):
        """Ajusta el volumen de la voz"""
        self.hablar("Di un número entre 1 y 10 para el volumen")
        respuesta = self.escuchar()
        
        try:
            match = re.search(r'\d+', respuesta)
            if match:
                nuevo_volumen = float(match.group()) / 10
                if 0.1 <= nuevo_volumen <= 1.0:
                    self.config['volumen_voz'] = nuevo_volumen
                    if self.tts_engine:
                        self.tts_engine.setProperty('volume', nuevo_volumen)
                    self.hablar(f"Volumen cambiado a {int(nuevo_volumen * 10)}")
                    self.guardar_configuracion()
                else:
                    self.hablar("El volumen debe estar entre 1 y 10")
            else:
                self.hablar("No detecté un número válido")
        except Exception as e:
            self.hablar("Error ajustando el volumen")
    
    def toggle_modo_verboso(self):
        """Activa/desactiva el modo verboso"""
        self.config['modo_verboso'] = not self.config['modo_verboso']
        estado = "activado" if self.config['modo_verboso'] else "desactivado"
        self.hablar(f"Modo verboso {estado}")
        self.guardar_configuracion()
    
    def guardar_configuracion(self):
        """Guarda la configuración actual"""
        try:
            with open('calculadora_config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            if self.config['modo_verboso']:
                print("✅ Configuración guardada")
        except Exception as e:
            print(f"⚠️  Error guardando configuración: {e}")
    
    def salir_seguro(self):
        """Salida segura de la aplicación"""
        self.modo_continuo = False
        
        if self.config['guardar_historial'] and self.historial:
            self.guardar_historial()
        
        self.guardar_configuracion()
        self.hablar("¡Hasta luego! Que tengas un excelente día.", 'alta')
        
        # Cleanup de recursos
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        sys.exit(0)
    
    def guardar_historial(self):
        """Guarda el historial en archivo"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"historial_calculadora_{timestamp}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.historial, f, indent=4, ensure_ascii=False)
            print(f"📄 Historial guardado en {filename}")
        except Exception as e:
            print(f"⚠️  Error guardando historial: {e}")
    
    def manejar_errores_escucha(self, tipo_error):
        """Maneja diferentes tipos de errores de escucha"""
        errores = {
            "timeout": "No escuché nada. ¿Sigues ahí? Habla más cerca del micrófono.",
            "no_entendido": "No pude entender lo que dijiste. Por favor habla más claro.",
            "error_servicio": "Hay un problema con el reconocimiento de voz. Verifica tu conexión a internet.",
            "error": "Error técnico de audio. Vamos a intentarlo de nuevo."
        }
        mensaje = errores.get(tipo_error, "Error desconocido en el audio")
        self.hablar(mensaje)
    
    def procesar_comandos_especiales(self, comando):
        """Procesa comandos especiales y devuelve True si se procesó uno"""
        # Comandos de salida
        if any(palabra in comando for palabra in ['salir', 'cerrar', 'terminar', 'adiós', 'chao', 'exit']):
            self.salir_seguro()
            return True
        
        # Comandos de ayuda
        if any(palabra in comando for palabra in ['ayuda completa', 'ayuda total', 'help']):
            self.mostrar_ayuda_completa()
            return True
        
        if 'ayuda' in comando:
            self.mostrar_ayuda_basica()
            return True
        
        # Comandos de historial
        if 'historial' in comando and 'limpiar' not in comando:
            self.leer_historial()
            return True
        
        if any(palabra in comando for palabra in ['limpiar historial', 'borrar historial', 'clear']):
            self.limpiar_historial()
            return True
        
        # Comandos de configuración
        if any(palabra in comando for palabra in ['configuración', 'configurar', 'ajustes', 'settings']):
            self.configurar_ajustes()
            return True
        
        # Comandos de control
        if any(palabra in comando for palabra in ['escucha continua', 'modo continuo']):
            self.toggle_escucha()
            return True
        
        if any(palabra in comando for palabra in ['pausar', 'pausa', 'pause']):
            self.toggle_pausa()
            return True
        
        # Comando de estado
        if any(palabra in comando for palabra in ['estado', 'status', 'info']):
            self.mostrar_estado()
            return True
        
        return False
    
    def mostrar_ayuda_basica(self):
        """Ayuda básica más concisa"""
        self.hablar("Puedo hacer operaciones básicas como suma, resta, multiplicación y división.")
        self.hablar("También raíz cuadrada, trigonometría y logaritmos.")
        self.hablar("Di 'historial' para ver operaciones anteriores.")
        self.hablar("Di 'ayuda completa' para escuchar todas las opciones.")
        self.hablar("Di 'salir' para cerrar la calculadora.")
    
    def mostrar_estado(self):
        """Muestra el estado actual del sistema"""
        estado_tts = "funcionando" if self.tts_engine else "solo texto"
        estado_continuo = "activado" if self.modo_continuo else "desactivado"
        estado_pausa = "pausado" if self.pausado else "activo"
        
        self.hablar(f"Estado del sistema: Voz {estado_tts}, modo continuo {estado_continuo}, estado {estado_pausa}.")
        
        if self.ultimo_resultado != 0:
            self.hablar(f"Último resultado: {self.formatear_numero(self.ultimo_resultado)}")
        
        if self.historial:
            self.hablar(f"Operaciones en historial: {len(self.historial)}")
    
    def ejecutar(self):
        """Bucle principal mejorado con mejor manejo de errores"""
        print("=" * 60)
        print("🧮 CALCULADORA DE VOZ ACCESIBLE PARA LINUX")
        print("=" * 60)
        print("✨ Versión optimizada para sistemas Linux")
        print("🔊 Audio configurado correctamente")
        print("=" * 60)
        
        # Mensaje de bienvenida
        self.hablar("¡Hola! Soy tu calculadora de voz para Linux.")
        self.hablar("Estoy lista para ayudarte con tus cálculos.")
        self.hablar("Di 'ayuda' para conocer las operaciones disponibles, o simplemente dime una operación.")
        
        contador_errores = 0
        max_errores_consecutivos = 5
        
        while True:
            try:
                # Verificar comandos en cola (de escucha continua)
                comando = None
                if not self.cola_comandos.empty():
                    comando = self.cola_comandos.get()
                    print(f"🎯 Procesando comando de escucha continua: {comando}")
                else:
                    self.hablar("¿Qué operación necesitas?")
                    comando = self.escuchar()
                
                # Manejar errores de escucha
                if comando in ["timeout", "no_entendido", "error_servicio", "error"]:
                    self.manejar_errores_escucha(comando)
                    contador_errores += 1
                    
                    # Si hay muchos errores consecutivos, ofrecer ayuda
                    if contador_errores >= max_errores_consecutivos:
                        self.hablar("Parece que hay problemas con el audio.")
                        self.hablar("Verifica que el micrófono esté funcionando y habla más cerca.")
                        self.hablar("Di 'estado' para ver información del sistema.")
                        contador_errores = 0
                    
                    continue
                
                # Resetear contador de errores en comando exitoso
                contador_errores = 0
                
                # Procesar comandos especiales
                if self.procesar_comandos_especiales(comando):
                    continue
                
                # Procesar operación matemática
                resultado, mensaje = self.procesar_operacion(comando)
                
                # Dar respuesta
                self.hablar(mensaje)
                
                # Mostrar información adicional en modo verboso
                if resultado is not None and self.config['modo_verboso']:
                    print(f"💡 Resultado numérico: {resultado}")
                    print(f"📊 Resultado guardado como: {self.ultimo_resultado}")
                    print(f"📝 Operaciones en historial: {len(self.historial)}")
                
            except KeyboardInterrupt:
                print("\n👋 Interrupción detectada...")
                self.salir_seguro()
                
            except Exception as e:
                print(f"❌ Error inesperado: {e}")
                if self.config['modo_verboso']:
                    import traceback
                    print("🔍 Detalles del error:")
                    traceback.print_exc()
                
                self.hablar("Ocurrió un error inesperado, pero puedo continuar.")
                contador_errores += 1
                
                # Si hay demasiados errores, sugerir reinicio
                if contador_errores >= max_errores_consecutivos:
                    self.hablar("Hay demasiados errores. Considera reiniciar la aplicación.")
                    contador_errores = 0

def verificar_dependencias():
    """Verifica que las dependencias estén instaladas"""
    dependencias = {
        'speech_recognition': 'SpeechRecognition',
        'pyttsx3': 'pyttsx3',
    }
    
    faltantes = []
    for modulo, nombre_pip in dependencias.items():
        try:
            __import__(modulo)
        except ImportError:
            faltantes.append(nombre_pip)
    
    # Verificar PyAudio por separado (más complicado en Linux)
    try:
        import pyaudio
    except ImportError:
        faltantes.append('pyaudio')
    
    return faltantes

def mostrar_instrucciones_instalacion():
    """Muestra instrucciones de instalación para Linux"""
    print("""
🔧 INSTALACIÓN EN LINUX:

📦 1. Instalar dependencias del sistema:
   sudo apt-get update
   sudo apt-get install python3-pyaudio portaudio19-dev
   sudo apt-get install espeak espeak-data libespeak1 libespeak-dev
   sudo apt-get install flac

📦 2. Instalar librerías Python:
   pip3 install SpeechRecognition pyttsx3 pyaudio

🎤 3. Configurar permisos de audio:
   sudo usermod -a -G audio $USER
   
🔊 4. Verificar PulseAudio:
   pulseaudio --check
   pulseaudio --start

⚡ 5. Para teclas rápidas (opcional):
   pip3 install keyboard
   # Nota: Requiere ejecutar como sudo para funcionar

🎯 6. Ejecutar:
   python3 calculadora_voz.py

💡 SOLUCIÓN DE PROBLEMAS:
   • Si hay errores ALSA: sudo apt-get install alsa-utils
   • Si no funciona el micrófono: alsamixer (verificar niveles)
   • Si TTS no funciona: sudo apt-get install festival speech-dispatcher
""")

def main():
    """Función principal con diagnóstico completo"""
    print("🚀 Iniciando Calculadora de Voz para Linux...")
    
    # Verificar dependencias
    faltantes = verificar_dependencias()
    if faltantes:
        print(f"❌ Faltan dependencias: {', '.join(faltantes)}")
        mostrar_instrucciones_instalacion()
        return
    
    # Verificar permisos de audio
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        if p.get_device_count() == 0:
            print("⚠️  No se detectaron dispositivos de audio")
        else:
            print(f"✅ Dispositivos de audio detectados: {p.get_device_count()}")
        p.terminate()
    except Exception as e:
        print(f"⚠️  Advertencia de audio: {e}")
    
    try:
        print("🔧 Inicializando calculadora...")
        calculadora = CalculadoraVozLinux()
        print("✅ Calculadora inicializada correctamente")
        calculadora.ejecutar()
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        mostrar_instrucciones_instalacion()
        
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        print("\n🔍 Información de diagnóstico:")
        
        # Diagnóstico básico
        import sys
        print(f"   Python: {sys.version}")
        print(f"   Sistema: {sys.platform}")
        
        try:
            import speech_recognition as sr
            print(f"   SpeechRecognition: {sr.__version__}")
        except:
            print("   SpeechRecognition: ❌ No disponible")
        
        try:
            import pyttsx3
            print("   pyttsx3: ✅ Disponible")
        except:
            print("   pyttsx3: ❌ No disponible")
        
        try:
            import pyaudio
            print("   pyaudio: ✅ Disponible")
        except:
            print("   pyaudio: ❌ No disponible")
        
        print("\n💡 Ejecuta las instrucciones de instalación mostradas arriba.")

if __name__ == "__main__":
    main()