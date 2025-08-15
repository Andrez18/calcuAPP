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

class CalculadoraVozOffline:
    def __init__(self):
        # Configuración inicial
        self.config = self.cargar_configuracion()
        
        # Variables de estado
        self.ultimo_resultado = 0
        self.historial = []
        self.modo_continuo = False
        self.pausado = False
        self.modo_offline = True
        
        # Cola para manejo de comandos
        self.cola_comandos = queue.Queue()
        
        # Inicializar componentes de audio
        self.inicializar_audio()
        
        # Patrones de operaciones
        self.inicializar_patrones()
        
        # Palabras de activación para modo manos libres
        self.palabras_activacion = ['calculadora', 'oye calculadora', 'hey calculadora']
        
        # Verificar modelos offline disponibles
        self.verificar_modelos_offline()
    
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
            'usar_hotkeys': False,
            'modo_offline_preferido': True,
            'motor_tts': 'pyttsx3',  # pyttsx3, espeak, festival
            'voz_seleccionada': 'auto',
            'usar_reconocimiento_offline': True
        }
        
        try:
            if os.path.exists('calculadora_config.json'):
                with open('calculadora_config.json', 'r', encoding='utf-8') as f:
                    config_guardada = json.load(f)
                    config_default.update(config_guardada)
        except Exception as e:
            print(f"Info: Usando configuración por defecto ({e})")
        
        return config_default
    
    def verificar_modelos_offline(self):
        """Verifica qué modelos de reconocimiento offline están disponibles"""
        self.modelos_disponibles = []
        
        # Verificar PocketSphinx
        try:
            # Intentar importar y verificar si funciona
            import speech_recognition as sr
            r = sr.Recognizer()
            # Crear un audio de prueba muy corto
            test_audio = sr.AudioData(b'\x00' * 3200, 16000, 2)
            try:
                r.recognize_sphinx(test_audio)
                self.modelos_disponibles.append('sphinx')
                print("✅ PocketSphinx disponible para reconocimiento offline")
            except sr.UnknownValueError:
                # Esto es esperado con audio vacío, significa que funciona
                self.modelos_disponibles.append('sphinx')
                print("✅ PocketSphinx disponible para reconocimiento offline")
            except Exception:
                print("⚠️  PocketSphinx no está completamente configurado")
        except ImportError:
            print("📦 PocketSphinx no instalado. Instalar con: pip install pocketsphinx")
        
        # Verificar Vosk (si está disponible)
        try:
            import vosk
            self.modelos_disponibles.append('vosk')
            print("✅ Vosk disponible para reconocimiento offline")
        except ImportError:
            print("📦 Vosk no instalado. Instalar con: pip install vosk")
        
        if not self.modelos_disponibles:
            print("⚠️  Sin modelos offline. Usando modo híbrido (online cuando sea posible)")
            self.modo_offline = False
    
    def inicializar_audio(self):
        """Inicializa los componentes de audio con múltiples opciones TTS"""
        print("🔧 Configurando sistema de audio offline...")
        
        # Configurar síntesis de voz con múltiples motores
        self.inicializar_tts()
        
        # Configurar reconocimiento de voz
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 4000
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.5
            
            self.inicializar_microfono()
            print("✅ Sistema de reconocimiento configurado")
            
        except Exception as e:
            print(f"❌ Error configurando reconocimiento: {e}")
            raise
    
    def inicializar_tts(self):
        """Inicializa el motor TTS con múltiples opciones"""
        self.tts_engine = None
        self.motor_tts_actual = None
        
        # Lista de motores TTS disponibles en orden de preferencia
        motores_tts = [
            ('pyttsx3', self.init_pyttsx3),
            ('espeak', self.init_espeak),
            ('festival', self.init_festival),
        ]
        
        motor_preferido = self.config.get('motor_tts', 'pyttsx3')
        
        # Intentar primero el motor preferido
        for nombre, init_func in motores_tts:
            if nombre == motor_preferido:
                if init_func():
                    self.motor_tts_actual = nombre
                    print(f"✅ Motor TTS: {nombre} (preferido)")
                    break
        
        # Si el preferido no funcionó, intentar otros
        if not self.tts_engine:
            for nombre, init_func in motores_tts:
                if nombre != motor_preferido:
                    if init_func():
                        self.motor_tts_actual = nombre
                        print(f"✅ Motor TTS: {nombre} (alternativo)")
                        break
        
        if not self.tts_engine:
            print("⚠️  Sin motor TTS disponible. Usando solo texto.")
    
    def init_pyttsx3(self):
        """Inicializa pyttsx3"""
        try:
            engine = pyttsx3.init()
            
            # Configurar voz
            voices = engine.getProperty('voices')
            if voices:
                self.configurar_voz_pyttsx3(engine, voices)
            
            engine.setProperty('rate', self.config['velocidad_voz'])
            engine.setProperty('volume', self.config['volumen_voz'])
            
            self.tts_engine = engine
            return True
        except Exception as e:
            print(f"⚠️  pyttsx3 no disponible: {e}")
            return False
    
    def configurar_voz_pyttsx3(self, engine, voices):
        """Configura la voz para pyttsx3"""
        print("\n🎙️  VOCES DISPONIBLES:")
        voces_espanol = []
        
        for i, voice in enumerate(voices):
            if voice and hasattr(voice, 'name'):
                print(f"   {i}: {voice.name} ({voice.id})")
                # Detectar voces en español
                if any(lang in voice.id.lower() for lang in ['es', 'spanish', 'español', 'mexico', 'spain']):
                    voces_espanol.append((i, voice))
        
        # Seleccionar voz
        voz_config = self.config.get('voz_seleccionada', 'auto')
        
        if voz_config == 'auto':
            # Preferir voces en español
            if voces_espanol:
                # Preferir voces femeninas para mejor claridad
                voz_femenina = None
                for i, voice in voces_espanol:
                    if any(fem in voice.name.lower() for fem in ['female', 'woman', 'maria', 'carmen', 'sabina']):
                        voz_femenina = voice
                        break
                
                voz_seleccionada = voz_femenina if voz_femenina else voces_espanol[0][1]
                engine.setProperty('voice', voz_seleccionada.id)
                print(f"🗣️  Voz seleccionada automáticamente: {voz_seleccionada.name}")
        
        elif voz_config.isdigit():
            # Selección manual por número
            indice = int(voz_config)
            if 0 <= indice < len(voices):
                engine.setProperty('voice', voices[indice].id)
                print(f"🗣️  Voz seleccionada manualmente: {voices[indice].name}")
    
    def init_espeak(self):
        """Inicializa espeak como alternativa"""
        try:
            import subprocess
            # Verificar si espeak está disponible
            result = subprocess.run(['espeak', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.tts_engine = 'espeak'
                print("🗣️  Usando eSpeak para síntesis de voz")
                return True
        except Exception as e:
            print(f"⚠️  eSpeak no disponible: {e}")
        return False
    
    def init_festival(self):
        """Inicializa festival como alternativa"""
        try:
            import subprocess
            result = subprocess.run(['festival', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.tts_engine = 'festival'
                print("🗣️  Usando Festival para síntesis de voz")
                return True
        except Exception as e:
            print(f"⚠️  Festival no disponible: {e}")
        return False
    
    def inicializar_microfono(self):
        """Inicializa el micrófono"""
        mic_inicializado = False
        
        for mic_index in [None, 0, 1, 2]:
            try:
                if mic_index is None:
                    self.microphone = sr.Microphone()
                else:
                    self.microphone = sr.Microphone(device_index=mic_index)
                
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                mic_inicializado = True
                if mic_index is not None:
                    print(f"🎤 Micrófono configurado (índice: {mic_index})")
                break
                
            except Exception:
                continue
        
        if not mic_inicializado:
            raise Exception("No se pudo inicializar el micrófono")
    
    def hablar(self, texto, prioridad='normal'):
        """TTS con múltiples motores"""
        if self.pausado and prioridad != 'alta':
            return
        
        print(f"🔊 {texto}")
        
        if not self.tts_engine:
            time.sleep(len(texto) * 0.05)  # Simular tiempo de habla
            return
        
        try:
            if self.motor_tts_actual == 'pyttsx3':
                self.tts_engine.say(texto)
                self.tts_engine.runAndWait()
            
            elif self.motor_tts_actual == 'espeak':
                import subprocess
                # Configurar espeak en español
                cmd = ['espeak', '-v', 'es+f3', '-s', str(self.config['velocidad_voz']), texto]
                subprocess.run(cmd, check=False, timeout=30)
            
            elif self.motor_tts_actual == 'festival':
                import subprocess
                # Usar festival con voz en español si está disponible
                cmd = ['festival', '--tts']
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
                process.communicate(input=texto)
                
        except Exception as e:
            if self.config['modo_verboso']:
                print(f"⚠️  Error TTS: {e}")
    
    def escuchar_offline(self, timeout=None):
        """Reconocimiento de voz completamente offline"""
        if timeout is None:
            timeout = self.config['timeout_escucha']
        
        try:
            print("🎤 Escuchando (modo offline)...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
            
            print("🔄 Procesando offline...")
            
            # Intentar con diferentes motores offline
            if 'sphinx' in self.modelos_disponibles:
                try:
                    texto = self.recognizer.recognize_sphinx(audio, language='es-ES')
                    print(f"📝 Escuchado (Sphinx): {texto}")
                    return texto.lower()
                except sr.UnknownValueError:
                    print("🔄 Sphinx no entendió, probando otro método...")
                except Exception as e:
                    print(f"⚠️  Error Sphinx: {e}")
            
            if 'vosk' in self.modelos_disponibles:
                try:
                    # Implementar Vosk si está disponible
                    texto = self.reconocer_con_vosk(audio)
                    if texto:
                        print(f"📝 Escuchado (Vosk): {texto}")
                        return texto.lower()
                except Exception as e:
                    print(f"⚠️  Error Vosk: {e}")
            
            return "no_entendido"
            
        except sr.WaitTimeoutError:
            return "timeout"
        except Exception as e:
            print(f"❌ Error en reconocimiento offline: {e}")
            return "error"
    
    def reconocer_con_vosk(self, audio):
        """Reconocimiento con Vosk (si está disponible)"""
        try:
            import vosk
            import json
            
            # Buscar modelo de español
            model_paths = [
                './vosk-model-es',
                './models/vosk-model-es-0.42',
                '/usr/share/vosk-models/es',
            ]
            
            model = None
            for path in model_paths:
                if os.path.exists(path):
                    model = vosk.Model(path)
                    break
            
            if not model:
                print("⚠️  Modelo Vosk en español no encontrado")
                return None
            
            rec = vosk.KaldiRecognizer(model, audio.sample_rate)
            
            # Convertir audio para Vosk
            audio_data = audio.get_raw_data(convert_rate=audio.sample_rate, convert_width=2)
            
            if rec.AcceptWaveform(audio_data):
                result = json.loads(rec.Result())
                return result.get('text', '')
            else:
                result = json.loads(rec.PartialResult())
                return result.get('partial', '')
                
        except Exception as e:
            print(f"Error Vosk: {e}")
            return None
    
    def escuchar_hibrido(self, timeout=None):
        """Modo híbrido: offline primero, online como respaldo"""
        if timeout is None:
            timeout = self.config['timeout_escucha']
        
        # Intentar offline primero
        if self.modelos_disponibles:
            resultado = self.escuchar_offline(timeout)
            if resultado not in ['no_entendido', 'timeout', 'error']:
                return resultado
            print("🌐 Probando reconocimiento online como respaldo...")
        
        # Respaldo online
        try:
            print("🎤 Escuchando (modo online)...")
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout//2, phrase_time_limit=10)
            
            texto = self.recognizer.recognize_google(audio, language=self.config['idioma_reconocimiento'])
            print(f"📝 Escuchado (Google): {texto}")
            return texto.lower()
            
        except sr.WaitTimeoutError:
            return "timeout"
        except sr.UnknownValueError:
            return "no_entendido"
        except sr.RequestError:
            print("🌐 Sin conexión a internet para reconocimiento online")
            return "sin_internet"
        except Exception as e:
            print(f"Error reconocimiento híbrido: {e}")
            return "error"
    
    def escuchar(self, timeout=None):
        """Punto de entrada principal para reconocimiento"""
        if self.config['usar_reconocimiento_offline'] and self.modelos_disponibles:
            return self.escuchar_offline(timeout)
        else:
            return self.escuchar_hibrido(timeout)
    
    def cambiar_voz_interactivo(self):
        """Permite cambiar la voz de forma interactiva"""
        if self.motor_tts_actual != 'pyttsx3':
            self.hablar("El cambio de voz solo está disponible con el motor pyttsx3")
            return
        
        try:
            voices = self.tts_engine.getProperty('voices')
            if not voices:
                self.hablar("No hay voces disponibles para cambiar")
                return
            
            self.hablar("Te voy a mostrar las voces disponibles. Después me dices el número de la que prefieras.")
            
            # Mostrar voces
            print("\n🎙️  VOCES DISPONIBLES:")
            for i, voice in enumerate(voices):
                if voice and hasattr(voice, 'name'):
                    print(f"   {i}: {voice.name}")
                    # Demo de cada voz
                    self.tts_engine.setProperty('voice', voice.id)
                    self.tts_engine.say(f"Voz número {i}")
                    self.tts_engine.runAndWait()
                    time.sleep(0.5)
            
            # Restaurar voz actual
            voz_actual = self.config.get('voz_seleccionada', '0')
            if voz_actual.isdigit():
                indice_actual = int(voz_actual)
                if 0 <= indice_actual < len(voices):
                    self.tts_engine.setProperty('voice', voices[indice_actual].id)
            
            self.hablar("¿Qué número de voz prefieres?")
            respuesta = self.escuchar()
            
            # Extraer número de la respuesta
            match = re.search(r'\d+', respuesta)
            if match:
                nuevo_indice = int(match.group())
                if 0 <= nuevo_indice < len(voices):
                    self.tts_engine.setProperty('voice', voices[nuevo_indice].id)
                    self.config['voz_seleccionada'] = str(nuevo_indice)
                    self.guardar_configuracion()
                    self.hablar(f"Voz cambiada a número {nuevo_indice}. ¿Te gusta cómo sueno ahora?")
                else:
                    self.hablar("Número de voz no válido")
            else:
                self.hablar("No entendí el número de voz")
                
        except Exception as e:
            self.hablar("Error cambiando la voz")
            if self.config['modo_verboso']:
                print(f"Error: {e}")
    
    def cambiar_motor_tts(self):
        """Cambia el motor TTS"""
        motores = ['pyttsx3', 'espeak', 'festival']
        
        self.hablar("Motores disponibles: pyttsx3, espeak, festival. ¿Cuál prefieres?")
        respuesta = self.escuchar()
        
        for motor in motores:
            if motor in respuesta:
                if motor != self.motor_tts_actual:
                    self.config['motor_tts'] = motor
                    self.hablar(f"Cambiando a motor {motor}. Reinicia la aplicación para aplicar el cambio.")
                    self.guardar_configuracion()
                else:
                    self.hablar(f"Ya estás usando {motor}")
                return
        
        self.hablar("No reconocí el motor. Opciones: pyttsx3, espeak, festival")
    
    def configurar_reconocimiento(self):
        """Configura el modo de reconocimiento"""
        self.hablar("¿Prefieres reconocimiento offline, online, o híbrido?")
        respuesta = self.escuchar()
        
        if 'offline' in respuesta:
            if self.modelos_disponibles:
                self.config['usar_reconocimiento_offline'] = True
                self.hablar("Reconocimiento cambiado a modo offline")
            else:
                self.hablar("Reconocimiento offline no disponible. Instala pocketsphinx o vosk")
        elif 'online' in respuesta:
            self.config['usar_reconocimiento_offline'] = False
            self.hablar("Reconocimiento cambiado a modo online")
        elif 'híbrido' in respuesta or 'hibrido' in respuesta:
            self.config['usar_reconocimiento_offline'] = False
            self.hablar("Reconocimiento cambiado a modo híbrido: offline primero, online como respaldo")
🎤 Esperando comando...
        
        self.guardar_configuracion()
    
    def mostrar_info_offline(self):
        """Muestra información sobre capacidades offline"""
        info = f"""
🔧 CONFIGURACIÓN OFFLINE:

📡 Reconocimiento de voz:
   • Modelos disponibles: {', '.join(self.modelos_disponibles) if self.modelos_disponibles else 'Ninguno'}
   • Modo actual: {'Offline' if self.config['usar_reconocimiento_offline'] else 'Híbrido/Online'}

🗣️  Síntesis de voz:
   • Motor actual: {self.motor_tts_actual or 'Ninguno'}
   • Voz seleccionada: {self.config.get('voz_seleccionada', 'Auto')}

🌐 Estado de internet: {'No requerido' if self.modelos_disponibles else 'Requerido para reconocimiento'}

💡 PARA MEJOR EXPERIENCIA OFFLINE:
   • Instalar: pip install pocketsphinx vosk
   • Descargar modelo Vosk: wget https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip
   • Instalar eSpeak: sudo apt-get install espeak espeak-data
"""
        print(info)
        
        self.hablar("Información offline mostrada en pantalla.")
        if not self.modelos_disponibles:
            self.hablar("Para funcionar completamente offline, necesitas instalar modelos de reconocimiento.")
    
    def inicializar_patrones(self):
        """Patrones de reconocimiento de operaciones"""
        self.patrones_operaciones = {
            # Operaciones básicas
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
            
            # Operaciones unarias
            r'\braíz\s*cuadrada\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.sqrt(float(x)), 'raíz cuadrada'),
            
            r'\bseno\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.sin(math.radians(float(x))), 'seno'),
            
            r'\bcoseno\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.cos(math.radians(float(x))), 'coseno'),
            
            r'\btangente\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.tan(math.radians(float(x))), 'tangente'),
            
            r'\blogaritmo\s*(?:de\s*)?(\d+(?:\.\d+)?)\b': 
                lambda x: (math.log10(float(x)) if float(x) > 0 else None, 'logaritmo'),
        }
    
    def procesar_operacion(self, texto):
        """Procesa operaciones matemáticas"""
        texto_original = texto
        texto = re.sub(r'[,.]', '.', texto)
        texto = self.convertir_numeros_texto(texto)
        
        for patron, operacion in self.patrones_operaciones.items():
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                try:
                    grupos = match.groups()
                    
                    if len(grupos) == 1:
                        resultado_tupla = operacion(grupos[0])
                    else:
                        resultado_tupla = operacion(grupos[0], grupos[1])
                    
                    if isinstance(resultado_tupla, tuple):
                        resultado, tipo_operacion = resultado_tupla
                    else:
                        resultado, tipo_operacion = resultado_tupla, "operación"
                    
                    if resultado is None:
                        return None, "Error: Operación no válida"
                    
                    if math.isnan(resultado) or math.isinf(resultado):
                        return None, "Error: Resultado no válido"
                    
                    self.ultimo_resultado = resultado
                    entrada_historial = {
                        'operacion': texto_original,
                        'resultado': resultado,
                        'tipo': tipo_operacion,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    self.historial.append(entrada_historial)
                    
                    if len(self.historial) > 50:
                        self.historial = self.historial[-50:]
                    
                    return resultado, f"El resultado de la {tipo_operacion} es {self.formatear_numero(resultado)}"
                    
                except Exception as e:
                    return None, f"Error matemático: {str(e)}"
        
        return None, "No reconocí la operación. Prueba con 'cinco más tres' o 'diez por dos'."
    
    def convertir_numeros_texto(self, texto):
        """Convierte números escritos a dígitos"""
        numeros_texto = {
            'cero': '0', 'uno': '1', 'dos': '2', 'tres': '3', 'cuatro': '4',
            'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9',
            'diez': '10', 'once': '11', 'doce': '12', 'trece': '13', 'catorce': '14',
            'quince': '15', 'veinte': '20', 'treinta': '30', 'cuarenta': '40',
            'cincuenta': '50', 'sesenta': '60', 'setenta': '70', 'ochenta': '80',
            'noventa': '90', 'cien': '100'
        }
        
        for palabra, numero in numeros_texto.items():
            texto = re.sub(r'\b' + palabra + r'\b', numero, texto, flags=re.IGNORECASE)
        
        return texto
    
    def formatear_numero(self, numero):
        """Formatea números para pronunciación"""
        try:
            if abs(numero - int(numero)) < 1e-10:
                return str(int(numero))
            else:
                precision = self.config['precision_decimales']
                formatted = f"{numero:.{precision}f}".rstrip('0').rstrip('.')
                return formatted
        except:
            return str(numero)
    
    def procesar_comandos_especiales(self, comando):
        """Procesa comandos especiales"""
        comandos_especiales = {
            ('salir', 'cerrar', 'terminar', 'adiós', 'chao'): self.salir_seguro,
            ('ayuda',): self.mostrar_ayuda,
            ('cambiar voz', 'voz'): self.cambiar_voz_interactivo,
            ('cambiar motor', 'motor'): self.cambiar_motor_tts,
            ('reconocimiento', 'configurar reconocimiento'): self.configurar_reconocimiento,
            ('info offline', 'información offline', 'estado offline'): self.mostrar_info_offline,
            ('historial',): self.leer_historial,
            ('limpiar historial',): self.limpiar_historial,
            ('último resultado', 'resultado anterior'): self.decir_ultimo_resultado,
            ('borrar resultado', 'limpiar resultado'): self.borrar_resultado,
            ('pausar', 'silencio'): self.pausar_calculadora,
            ('reanudar', 'continuar'): self.reanudar_calculadora,
            ('configuración', 'ajustes'): self.mostrar_configuracion,
            ('guardar configuración',): self.guardar_configuracion,
            ('modo continuo',): self.activar_modo_continuo,
            ('modo normal',): self.desactivar_modo_continuo,
            ('velocidad más rápida', 'hablar más rápido'): lambda: self.cambiar_velocidad_voz(20),
            ('velocidad más lenta', 'hablar más lento'): lambda: self.cambiar_velocidad_voz(-20),
            ('volumen más alto',): lambda: self.cambiar_volumen(0.1),
            ('volumen más bajo',): lambda: self.cambiar_volumen(-0.1),
        }
        
        for palabras_clave, accion in comandos_especiales.items():
            for palabra in palabras_clave:
                if palabra in comando:
                    try:
                        if callable(accion):
                            accion()
                        return True
                    except Exception as e:
                        self.hablar(f"Error ejecutando comando: {str(e)}")
                        return True
        
        return False
    
    def leer_historial(self):
        """Lee el historial de operaciones"""
        if not self.historial:
            self.hablar("No hay operaciones en el historial")
            return
        
        self.hablar(f"Tienes {len(self.historial)} operaciones en el historial. Te leo las últimas 5:")
        
        ultimas = self.historial[-5:]
        for entrada in ultimas:
            texto = f"A las {entrada['timestamp']}: {entrada['operacion']} = {self.formatear_numero(entrada['resultado'])}"
            self.hablar(texto)
            time.sleep(0.5)
    
    def limpiar_historial(self):
        """Limpia el historial"""
        self.historial.clear()
        self.hablar("Historial limpiado")
    
    def decir_ultimo_resultado(self):
        """Dice el último resultado calculado"""
        if self.ultimo_resultado is not None:
            self.hablar(f"El último resultado es {self.formatear_numero(self.ultimo_resultado)}")
        else:
            self.hablar("No hay resultado anterior")
    
    def borrar_resultado(self):
        """Borra el último resultado"""
        self.ultimo_resultado = 0
        self.hablar("Resultado borrado")
    
    def pausar_calculadora(self):
        """Pausa la calculadora"""
        self.pausado = True
        self.hablar("Calculadora pausada. Di 'reanudar' para continuar", prioridad='alta')
    
    def reanudar_calculadora(self):
        """Reanuda la calculadora"""
        self.pausado = False
        self.hablar("Calculadora reanudada", prioridad='alta')
    
    def mostrar_configuracion(self):
        """Muestra la configuración actual"""
        config_texto = f"""
Configuración actual:
- Velocidad de voz: {self.config['velocidad_voz']}
- Volumen: {self.config['volumen_voz']}
- Timeout de escucha: {self.config['timeout_escucha']} segundos
- Motor TTS: {self.motor_tts_actual}
- Reconocimiento offline: {'Sí' if self.config['usar_reconocimiento_offline'] else 'No'}
- Modo verboso: {'Sí' if self.config['modo_verboso'] else 'No'}
        """
        print(config_texto)
        self.hablar("Configuración mostrada en pantalla")
    
    def guardar_configuracion(self):
        """Guarda la configuración actual"""
        try:
            with open('calculadora_config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.hablar("Configuración guardada")
        except Exception as e:
            self.hablar("Error guardando configuración")
            if self.config['modo_verboso']:
                print(f"Error: {e}")
    
    def activar_modo_continuo(self):
        """Activa el modo continuo"""
        self.modo_continuo = True
        self.hablar("Modo continuo activado. Di 'salir' para terminar")
    
    def desactivar_modo_continuo(self):
        """Desactiva el modo continuo"""
        self.modo_continuo = False
        self.hablar("Modo continuo desactivado")
    
    def cambiar_velocidad_voz(self, cambio):
        """Cambia la velocidad de la voz"""
        nueva_velocidad = max(50, min(300, self.config['velocidad_voz'] + cambio))
        self.config['velocidad_voz'] = nueva_velocidad
        
        if self.motor_tts_actual == 'pyttsx3' and self.tts_engine:
            self.tts_engine.setProperty('rate', nueva_velocidad)
        
        self.hablar(f"Velocidad ajustada a {nueva_velocidad}")
    
    def cambiar_volumen(self, cambio):
        """Cambia el volumen de la voz"""
        nuevo_volumen = max(0.1, min(1.0, self.config['volumen_voz'] + cambio))
        self.config['volumen_voz'] = nuevo_volumen
        
        if self.motor_tts_actual == 'pyttsx3' and self.tts_engine:
            self.tts_engine.setProperty('volume', nuevo_volumen)
        
        self.hablar(f"Volumen ajustado")
    
    def mostrar_ayuda(self):
        """Muestra ayuda sobre comandos disponibles"""
        ayuda = """
🎯 COMANDOS DISPONIBLES:

📊 OPERACIONES:
   • "cinco más tres"
   • "diez por dos"  
   • "veinte entre cuatro"
   • "dos elevado a tres"
   • "raíz cuadrada de nueve"
   • "seno de treinta"
   • "resultado más cinco"

🎛️  CONTROLES:
   • "ayuda" - Esta ayuda
   • "historial" - Ver cálculos anteriores
   • "último resultado" - Repetir último resultado
   • "limpiar historial" - Borrar historial
   • "pausar/reanudar" - Control de pausa
   • "salir" - Cerrar calculadora

🔧 CONFIGURACIÓN:
   • "cambiar voz" - Seleccionar voz
   • "cambiar motor" - Cambiar motor TTS
   • "reconocimiento" - Configurar reconocimiento
   • "info offline" - Ver estado offline
   • "velocidad más rápida/lenta"
   • "volumen más alto/bajo"
   • "modo continuo" - Escucha continua

🎤 USO:
   1. Habla claramente
   2. Espera la respuesta
   3. Puedes usar números o palabras
   4. Di "salir" para terminar
        """
        
        print(ayuda)
        self.hablar("Ayuda mostrada en pantalla. Puedes hacer operaciones como 'cinco más tres' o 'diez por dos'")
    
    def salir_seguro(self):
        """Sale de forma segura guardando configuración"""
        self.hablar("Guardando configuración y cerrando...")
        
        if self.config['guardar_historial'] and self.historial:
            try:
                historial_archivo = {
                    'fecha': datetime.now().isoformat(),
                    'operaciones': self.historial
                }
                with open('historial_calculadora.json', 'w', encoding='utf-8') as f:
                    json.dump(historial_archivo, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error guardando historial: {e}")
        
        self.guardar_configuracion()
        self.hablar("¡Hasta luego!")
        sys.exit(0)
    
    def procesar_comando_voz(self, texto):
        """Procesa un comando de voz completo"""
        if not texto or texto in ['timeout', 'error', 'no_entendido', 'sin_internet']:
            if texto == 'timeout':
                if self.config['modo_verboso']:
                    print("⏱️  Timeout de escucha")
                return "timeout"
            elif texto == 'no_entendido':
                self.hablar("No te entendí. ¿Puedes repetir?")
                return "no_entendido"
            elif texto == 'sin_internet':
                self.hablar("Sin conexión a internet. Usando solo capacidades offline")
                return "sin_internet"
            else:
                self.hablar("Error de reconocimiento. Inténtalo de nuevo")
                return "error"
        
        if self.config['modo_verboso']:
            print(f"💬 Procesando: '{texto}'")
        
        # Verificar comandos especiales primero
        if self.procesar_comandos_especiales(texto):
            return "comando_especial"
        
        # Procesar operaciones matemáticas
        resultado, mensaje = self.procesar_operacion(texto)
        self.hablar(mensaje)
        
        if resultado is not None:
            return "operacion_exitosa"
        else:
            return "operacion_fallida"
    
    def modo_interactivo(self):
        """Modo interactivo principal"""
        self.hablar("Calculadora de voz offline iniciada. Di 'ayuda' para ver comandos disponibles")
        
        while True:
            try:
                if self.pausado:
                    time.sleep(0.5)
                    continue
                
                print("\n🎤 Esperando comando...")
                texto = self.escuchar()
                
                if texto:
                    resultado = self.procesar_comando_voz(texto)
                    
                    if resultado == "timeout" and not self.modo_continuo:
                        continue
                
                if not self.modo_continuo:
                    self.hablar("¿Alguna otra operación?")
                    
            except KeyboardInterrupt:
                self.hablar("Interrupción detectada")
                self.salir_seguro()
            except Exception as e:
                print(f"❌ Error en modo interactivo: {e}")
                self.hablar("Hubo un error. Continuando...")
                time.sleep(1)
    
    def modo_comando_unico(self, comando=None):
        """Modo para ejecutar un solo comando"""
        if comando:
            print(f"🎯 Ejecutando comando: {comando}")
            resultado = self.procesar_comando_voz(comando)
            return resultado
        else:
            print("🎤 Escuchando un comando...")
            texto = self.escuchar(timeout=15)
            if texto:
                return self.procesar_comando_voz(texto)
            else:
                print("❌ No se detectó comando")
                return None
    
    def diagnostico_sistema(self):
        """Ejecuta un diagnóstico del sistema"""
        print("\n🔍 DIAGNÓSTICO DEL SISTEMA:")
        print("=" * 50)
        
        # Verificar reconocimiento
        print("📡 RECONOCIMIENTO DE VOZ:")
        if self.modelos_disponibles:
            print(f"   ✅ Modelos offline: {', '.join(self.modelos_disponibles)}")
        else:
            print("   ⚠️  Sin modelos offline disponibles")
        
        # Verificar TTS
        print("🗣️  SÍNTESIS DE VOZ:")
        if self.tts_engine:
            print(f"   ✅ Motor TTS: {self.motor_tts_actual}")
        else:
            print("   ⚠️  Sin motor TTS disponible")
        
        # Verificar micrófono
        print("🎤 MICRÓFONO:")
        try:
            with self.microphone as source:
                print("   ✅ Micrófono funcional")
        except Exception as e:
            print(f"   ❌ Error de micrófono: {e}")
        
        # Prueba de reconocimiento
        print("\n🧪 PRUEBA DE RECONOCIMIENTO:")
        self.hablar("Di algo para probar el reconocimiento")
        texto = self.escuchar(timeout=5)
        if texto and texto not in ['timeout', 'error', 'no_entendido']:
            print(f"   ✅ Reconocido: '{texto}'")
        else:
            print(f"   ⚠️  Resultado: {texto}")
        
        print("\n" + "=" * 50)


def main():
    """Función principal"""
    print("🧮 CALCULADORA DE VOZ OFFLINE")
    print("=" * 40)
    
    # Verificar argumentos de línea de comandos
    if len(sys.argv) > 1:
        if sys.argv[1] == '--diagnostico':
            calc = CalculadoraVozOffline()
            calc.diagnostico_sistema()
            return
        elif sys.argv[1] == '--comando':
            calc = CalculadoraVozOffline()
            if len(sys.argv) > 2:
                comando = ' '.join(sys.argv[2:])
                calc.modo_comando_unico(comando)
            else:
                calc.modo_comando_unico()
            return
        elif sys.argv[1] == '--ayuda':
            print("""
🎯 USO:
    python calculadora_voz.py                  # Modo interactivo
    python calculadora_voz.py --comando        # Un solo comando
    python calculadora_voz.py --comando "5+3"  # Comando específico
    python calculadora_voz.py --diagnostico    # Diagnóstico del sistema
    python calculadora_voz.py --ayuda         # Esta ayuda

📦 INSTALACIÓN DE DEPENDENCIAS OFFLINE:
    pip install speechrecognition pyttsx3
    pip install pocketsphinx  # Para reconocimiento offline
    pip install vosk         # Alternativa offline (opcional)
    
🌍 INSTALACIÓN SISTEMA (Ubuntu/Debian):
    sudo apt-get install espeak espeak-data
    sudo apt-get install festival
            """)
            return
    
    try:
        calc = CalculadoraVozOffline()
        calc.modo_interactivo()
        
    except KeyboardInterrupt:
        print("\n👋 Salida forzada")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        print("💡 Ejecuta con --diagnostico para verificar el sistema")


if __name__ == "__main__":
    main()