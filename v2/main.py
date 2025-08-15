import speech_recognition as sr
import pyttsx3
import re
import math
import threading
import time

class CalculadoraVoz:
    def __init__(self):
        # Configurar reconocimiento de voz
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Configurar síntesis de voz
        self.tts_engine = pyttsx3.init()
        self.configurar_voz()
        
        # Ajustar micrófono para ruido ambiente
        self.ajustar_microfono()
        
        # Patrones para reconocer operaciones
        self.patrones_operaciones = {
            r'\b(\d+(?:\.\d+)?)\s*(?:más|mas|\+)\s*(\d+(?:\.\d+)?)\b': lambda x, y: float(x) + float(y),
            r'\b(\d+(?:\.\d+)?)\s*(?:menos|-)\s*(\d+(?:\.\d+)?)\b': lambda x, y: float(x) - float(y),
            r'\b(\d+(?:\.\d+)?)\s*(?:por|multiplicado\s*por|\*|x)\s*(\d+(?:\.\d+)?)\b': lambda x, y: float(x) * float(y),
            r'\b(\d+(?:\.\d+)?)\s*(?:entre|dividido\s*por|/)\s*(\d+(?:\.\d+)?)\b': lambda x, y: float(x) / float(y) if float(y) != 0 else None,
            r'\b(\d+(?:\.\d+)?)\s*(?:elevado\s*a|a\s*la|potencia|\^|\*\*)\s*(\d+(?:\.\d+)?)\b': lambda x, y: float(x) ** float(y),
            r'\braíz\s*cuadrada\s*de\s*(\d+(?:\.\d+)?)\b': lambda x: math.sqrt(float(x)),
            r'\bseno\s*de\s*(\d+(?:\.\d+)?)\b': lambda x: math.sin(math.radians(float(x))),
            r'\bcoseno\s*de\s*(\d+(?:\.\d+)?)\b': lambda x: math.cos(math.radians(float(x))),
            r'\btangente\s*de\s*(\d+(?:\.\d+)?)\b': lambda x: math.tan(math.radians(float(x))),
            r'\blogaritmo\s*de\s*(\d+(?:\.\d+)?)\b': lambda x: math.log10(float(x)) if float(x) > 0 else None
        }
    
    def configurar_voz(self):
        """Configura las propiedades de la voz"""
        # Obtener voces disponibles
        voices = self.tts_engine.getProperty('voices')
        
        # Buscar voz en español
        spanish_voice = None
        for voice in voices:
            if 'spanish' in voice.name.lower() or 'es' in voice.id.lower():
                spanish_voice = voice.id
                break
        
        if spanish_voice:
            self.tts_engine.setProperty('voice', spanish_voice)
        
        # Configurar velocidad y volumen
        self.tts_engine.setProperty('rate', 180)  # Velocidad de habla
        self.tts_engine.setProperty('volume', 0.9)  # Volumen
    
    def ajustar_microfono(self):
        """Ajusta el micrófono al ruido ambiente"""
        print("Ajustando micrófono al ruido ambiente...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Micrófono ajustado.")
    
    def hablar(self, texto):
        """Convierte texto a voz"""
        print(f"🔊 {texto}")
        self.tts_engine.say(texto)
        self.tts_engine.runAndWait()
    
    def escuchar(self, timeout=5):
        """Escucha y reconoce la voz del usuario"""
        try:
            print("🎤 Escuchando...")
            with self.microphone as source:
                # Escuchar con timeout
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            print("🔄 Procesando...")
            # Reconocer usando Google Speech Recognition
            texto = self.recognizer.recognize_google(audio, language='es-ES')
            print(f"📝 Escuchado: {texto}")
            return texto.lower()
            
        except sr.WaitTimeoutError:
            return "timeout"
        except sr.UnknownValueError:
            return "no_entendido"
        except sr.RequestError as e:
            print(f"Error en el servicio de reconocimiento: {e}")
            return "error_servicio"
    
    def procesar_operacion(self, texto):
        """Procesa el texto y extrae la operación matemática"""
        texto = texto.replace(',', '.')  # Reemplazar comas por puntos para decimales
        
        for patron, operacion in self.patrones_operaciones.items():
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                try:
                    grupos = match.groups()
                    if len(grupos) == 1:  # Operaciones unarias (como raíz cuadrada)
                        resultado = operacion(grupos[0])
                    else:  # Operaciones binarias
                        resultado = operacion(grupos[0], grupos[1])
                    
                    if resultado is None:
                        return None, "Error: No se puede dividir por cero o logaritmo de número no positivo"
                    
                    return resultado, f"El resultado es {self.formatear_numero(resultado)}"
                    
                except (ValueError, ZeroDivisionError, OverflowError) as e:
                    return None, f"Error en el cálculo: {str(e)}"
        
        return None, "No pude entender la operación. Intenta de nuevo."
    
    def formatear_numero(self, numero):
        """Formatea el número para que se escuche mejor"""
        if numero == int(numero):
            return str(int(numero))
        else:
            # Redondear a 4 decimales para evitar números muy largos
            return f"{numero:.4f}".rstrip('0').rstrip('.')
    
    def mostrar_ayuda(self):
        """Muestra las operaciones disponibles"""
        ayuda = """
        OPERACIONES DISPONIBLES:
        
        🔢 Operaciones básicas:
        - "5 más 3" o "5 + 3"
        - "10 menos 4" o "10 - 4"  
        - "6 por 7" o "6 multiplicado por 7"
        - "20 entre 4" o "20 dividido por 4"
        - "2 elevado a 3" o "2 a la 3"
        
        📐 Operaciones avanzadas:
        - "raíz cuadrada de 16"
        - "seno de 30"
        - "coseno de 60" 
        - "tangente de 45"
        - "logaritmo de 100"
        
        🎤 Comandos:
        - "ayuda" - Mostrar esta ayuda
        - "salir" - Cerrar la calculadora
        """
        print(ayuda)
        self.hablar("Te voy a explicar las operaciones disponibles.")
        
        operaciones_basicas = "Puedes usar operaciones básicas como: suma diciendo 'más', resta diciendo 'menos', multiplicación diciendo 'por', división diciendo 'entre', y potencias diciendo 'elevado a'."
        self.hablar(operaciones_basicas)
        
        operaciones_avanzadas = "También tienes funciones como raíz cuadrada, seno, coseno, tangente y logaritmo."
        self.hablar(operaciones_avanzadas)
        
        comandos = "Puedes decir 'ayuda' para escuchar esto de nuevo, o 'salir' para cerrar la calculadora."
        self.hablar(comandos)
    
    def ejecutar(self):
        """Bucle principal de la calculadora"""
        print("=" * 50)
        print("🧮 CALCULADORA DE VOZ ACCESIBLE")
        print("=" * 50)
        
        self.hablar("¡Hola! Soy tu calculadora de voz. Puedo ayudarte a realizar operaciones matemáticas. Di 'ayuda' para conocer las operaciones disponibles, o simplemente dime una operación para comenzar.")
        
        while True:
            try:
                self.hablar("¿Qué operación quieres realizar?")
                
                # Escuchar comando del usuario
                comando = self.escuchar(timeout=10)
                
                if comando == "timeout":
                    self.hablar("No escuché nada. ¿Sigues ahí? Intentémoslo de nuevo.")
                    continue
                elif comando == "no_entendido":
                    self.hablar("No pude entender lo que dijiste. Por favor, habla más claro y cerca del micrófono.")
                    continue
                elif comando == "error_servicio":
                    self.hablar("Hay un problema con el servicio de reconocimiento de voz. Verifica tu conexión a internet.")
                    continue
                
                # Procesar comandos especiales
                if any(word in comando for word in ['salir', 'cerrar', 'terminar', 'adiós', 'chao']):
                    self.hablar("¡Hasta luego! Que tengas un buen día.")
                    break
                elif 'ayuda' in comando:
                    self.mostrar_ayuda()
                    continue
                
                # Procesar operación matemática
                resultado, mensaje = self.procesar_operacion(comando)
                self.hablar(mensaje)
                
                if resultado is not None:
                    print(f"💡 Resultado: {resultado}")
                
            except KeyboardInterrupt:
                print("\n👋 Saliendo...")
                self.hablar("¡Hasta luego!")
                break
            except Exception as e:
                print(f"Error inesperado: {e}")
                self.hablar("Ocurrió un error inesperado. Intentémoslo de nuevo.")

def main():
    """Función principal"""
    try:
        calculadora = CalculadoraVoz()
        calculadora.ejecutar()
    except Exception as e:
        print(f"Error al inicializar la calculadora: {e}")
        print("Asegúrate de tener instaladas las librerías necesarias:")
        print("pip install SpeechRecognition pyttsx3 pyaudio")

if __name__ == "__main__":
    main()