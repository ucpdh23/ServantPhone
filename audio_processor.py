import asyncio
import json
import time
import numpy as np
import wave
import os
from openai import OpenAI

import requests

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_PROMPT = os.getenv('LLM_PROMPT')
STT_APIKEY = os.getenv('STT_APIKEY')
STT_URL

class VAD: 
    def __init__(self, 
                 sample_rate: int = 16000, 
                 frame_len_ms: int = 20,
                 energy_threshold: float = 0.005, # Umbral de energía (0.0 a 1.0, normalizado)
                 zcr_threshold: float = 0.05     # Umbral de ZCR (0.0 a 1.0, normalizado)
                ):
        """
        Inicializa el VAD.

        Args:
            sample_rate (int): Frecuencia de muestreo del audio (Hz).
            frame_len_ms (int): Duración de cada frame de audio para el análisis (ms).
            energy_threshold (float): Umbral de energía normalizada. Frames con energía por encima
                                      de esto se consideran potencialmente "activos".
            zcr_threshold (float): Umbral de ZCR normalizada. Se usa en combinación con la energía.
        """
        self.sample_rate = sample_rate
        self.frame_len_ms = frame_len_ms
        self.frame_len_samples = int(sample_rate * frame_len_ms / 1000)
        self.bytes_per_frame = self.frame_len_samples * 2 # 16-bit audio (2 bytes por muestra)

        self.energy_threshold = energy_threshold
        self.zcr_threshold = zcr_threshold

        print(f"VAD (WAV Input, Custom) initialized: SR={self.sample_rate}Hz, Frame={self.frame_len_ms}ms, "
              f"Energy_Th={self.energy_threshold:.4f}, ZCR_Th={self.zcr_threshold:.2f}")

    def _calculate_energy(self, audio_frame_np: np.ndarray) -> float:
        """
        Calcula la energía de un frame de audio.
        Se normaliza a un rango de -1.0 a 1.0 para el cálculo.
        """
        if audio_frame_np.size == 0:
            return 0.0
        normalized_frame = audio_frame_np / 32768.0 
        energy = np.sum(normalized_frame**2) / normalized_frame.size
        return energy

    def _calculate_zcr(self, audio_frame_np: np.ndarray) -> float:
        """
        Calcula la tasa de cruces por cero (Zero-Crossing Rate - ZCR) de un frame de audio.
        """
        if audio_frame_np.size < 2:
            return 0.0
        zcr = np.sum(np.abs(np.diff(np.sign(audio_frame_np)))) / (2.0 * audio_frame_np.size)
        return zcr

    def is_speech(self, wav_file_path: str) -> list[bool]:
        """
        Analiza un archivo WAV completo y devuelve una lista de booleanos,
        donde True indica que el frame correspondiente contiene habla, basado en energía y ZCR.

        Args:
            wav_file_path (str): Ruta al archivo WAV de entrada.
                                 Debe ser mono, 16-bit PCM, con la frecuencia de muestreo configurada.

        Returns:
            list[bool]: Una lista de booleanos indicando la actividad de voz para cada frame.
        """
        if not os.path.exists(wav_file_path):
            raise FileNotFoundError(f"El archivo WAV no se encontró: {wav_file_path}")

        try:
            with wave.open(wav_file_path, 'rb') as wf:
                num_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()

                if num_channels != 1 or sample_width != 2 or sample_rate != self.sample_rate:
                    raise ValueError(f"El archivo WAV debe ser mono, 16-bit PCM, y {self.sample_rate}Hz. "
                                     f"Encontrado: {num_channels} canales, {sample_width*8}-bit, {sample_rate}Hz.")

                speech_activity_per_frame = []
                while True:
                    data_bytes = wf.readframes(self.frame_len_samples)
                    if not data_bytes:
                        break
                    
                    # Rellenar con silencio si el último frame es más corto
                    if len(data_bytes) < self.bytes_per_frame:
                        data_bytes += b'\x00' * (self.bytes_per_frame - len(data_bytes))
                    
                    audio_frame_np = np.frombuffer(data_bytes, dtype=np.int16)
                    energy = self._calculate_energy(audio_frame_np)
                    zcr = self._calculate_zcr(audio_frame_np)

                    # Lógica de detección de voz: simplemente si la energía supera el umbral.
                    # Puedes añadir más complejidad aquí si lo necesitas (ej. combinando con ZCR).
                    is_active_frame = energy > self.energy_threshold 
                    
                    speech_activity_per_frame.append(is_active_frame)
                
                print(f"Analizado {len(speech_activity_per_frame)} frames del archivo '{wav_file_path}'.")
                return speech_activity_per_frame

        except wave.Error as e:
            raise IOError(f"Error al leer el archivo WAV: {e}")
        except Exception as e:
            raise RuntimeError(f"Ocurrió un error inesperado durante el análisis VAD: {e}")

    def reset(self):
        """No se requiere un reset para VAD basado en archivos, ya que no mantiene estado
        entre llamadas a `is_speech` con diferentes archivos."""
        print("VAD reset (no-op for WAV-based VAD).")


async def generate_output(input_text, client) -> str:
    """
    Generate a response based on the input text using the provided agent.
    """
    return await client.execute(input_text)


async def process_audio(input_file, agent) -> str:
    """
    Process the audio file and generate a response using the agent.
    This function handles the entire lifecycle of audio processing:
    1. Speech-to-text transcription
    2. Generating a response by using the agent.
    3. Text-to-speech synthesis and generation of the audio file.

    This method returns the path to the generated audio file.
    """

    url = STT_URL

    ai_token = STT_APIKEY
    headers = {
        "Authorization": f"Bearer {ai_token}",
        "Content-Type": "audio/wav"
    }

    input_text = "texto por defecto"
    with open(input_file, 'rb') as audio_data:
        response = requests.post(url, headers=headers, data=audio_data)

        response.raise_for_status()  # Lanza una excepción HTTPError para respuestas 4xx/5xx

        stt_body = response.text
        segments = stt_body.split("\n}")
        
        item = segments[-2]
        stt = json.loads(item + "}")
        input_text = stt['text']     


    try:
        client = OpenAI(api_key=LLM_API_KEY)
    except Exception as e:
        return f"Error al inicializar el cliente de OpenAI: {e}"

    print(f"Building the output from the input: '{input_text}'")
    output_text = await generate_output(input_text, agent)


    timestr = time.strftime("%Y%m%d%H%M%S")
    nombre_archivo_salida = f"chat_files/ai_generated_{timestr}.wav"

    try:
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=output_text,
            response_format="wav",
            speed=1.0
        )

        speech_response.stream_to_file(nombre_archivo_salida)

        print(f"Audio generado exitosamente en: {nombre_archivo_salida}")
        return nombre_archivo_salida

    except Exception as e:
        return f"Error durante la generación de audio con OpenAI: {e}"
    
    return nombre_archivo_salida

def concat_wav_files(input_files, output_file):
    print("concat_wav_files", input_files, output_file)

    data = []

    # Abrir cada archivo y extraer los frames
    for infile in input_files:
        print("processing", infile)
        with wave.open(infile, 'rb') as wav:
            if not data:
                params = wav.getparams()  # Guardar formato original
            data.append(wav.readframes(wav.getnframes()))

    # Escribir archivo combinado
    with wave.open(output_file, 'wb') as out_wav:
        out_wav.setparams(params)
        for frames in data:
            out_wav.writeframes(frames)

    print(f"✅ Archivo combinado guardado como: {output_file}")
