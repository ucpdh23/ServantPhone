import os
import threading
import pjsua2 as pj
import time
from audio_processor import VAD, concat_wav_files, process_audio 
import queue
import asyncio
from agent import MCPAgent

from dotenv import load_dotenv

load_dotenv()

STUN_PROXY = os.getenv('STUN_PROXY')
SIP_ID = os.getenv('SID_ID')
SID_REGISTRAR = os.getenv('SID_REGISTRAR')
SID_DOMAIN = os.getenv('SID_DOMAIN')
SIP_PROXY = os.getenv('SID_PROXY')
AUTH_DOMAIN = os.getenv('AUTH_DOMAIN')
AUTH_USERNAME = os.getenv('AUTH_USERNAME')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD')


class MyCall(pj.Call):
    """
    MyCall class handles the call media and recording.
    """

    def __init__(self, acc, dest_uri, ep_instance: pj.Endpoint, agent):
        pj.Call.__init__(self, acc)
        self.dest_uri = dest_uri
        self.ep = ep_instance # Store the Endpoint instance
        self.recorder = None
        self.aud_med = None
        self.segment_index = 0
        self.last_voice_time = time.time()
        self.silence_threshold = 500  # adjust based on experiments
        self.silence_timeout = 0.5    # seconds of silence to split segments
        self.vad = VAD(energy_threshold=0.0002, zcr_threshold=0.04)
        self.pre_silence_detected = True
        self.last_segment_index = 0
        self.to_reproduce = queue.Queue()
        self.players = []
        self.agent = agent

    def onCallState(self, prm):
        call_info = self.getInfo()
        print(f"Call state: {call_info.stateText}, last reason: {call_info.lastReason}")

    def onCallMediaState(self, prm):
        ci = self.getInfo()
        print("*****************onCallMediaState")
        print(ci.state)
        for mi in ci.media:
            print("type")
            print(mi.type)
            print(mi.index)
            if mi.type == 1 and ci.state == 4:
                self.aud_med = pj.AudioMedia.typecastFromMedia(self.getMedia(mi.index))
                self.start_new_segment()

                self.start_backloop()

    def _worker(self):
        """
        Audio playback worker thread. This thread will continuously check the queue to_reproduce
        for audio files to play and manage the playback state.
        """

        # --- PJLIB THREAD REGISTRATION ---
        self.ep.libRegisterThread("MyCallPlaybackWorker")
        print("Playback worker registered with PJLIB.")
        # --- END REGISTRATION ---

        print("worker started...")
        while True:
            item = self.to_reproduce.get()
            print("item", item)
            self.playFile(item)
            self.to_reproduce.task_done()


    def start_backloop(self):
        """
        Start the audio playback worker thread.
        """
        threading.Thread(target=self._worker, daemon=True).start()

    
    def playFile(self, filename):
        print("playing ", filename)

        new_player = pj.AudioMediaPlayer()
        new_player.createPlayer(filename, pj.PJMEDIA_FILE_NO_LOOP)

        if len(self.players) > 0:
            curr_player = self.players.pop()
            curr_player.stopTransmit(self.aud_med)

        new_player.startTransmit(self.aud_med)
        self.players.append(new_player)


    def start_new_segment(self):
        """
        Start a new audio segment for recording. 
        """
        if self.recorder:
            self.recorder = None  # Close previous
        file_name = f"chat_files/segment_{self.segment_index}.wav"
        self.recorder = pj.AudioMediaRecorder()
        self.recorder.createRecorder(file_name)
        self.aud_med.startTransmit(self.recorder)
        print(f"Started recording {file_name}")
        self.segment_index += 1
        self.last_voice_time = time.time()


    async def check_audio_level(self):
        """
        Check the audio level and manage silence detection.
        """
        if not self.aud_med:
            return

        level = self.aud_med.getRxLevel()
        #print(f"Audio level: {level}")

        if level > self.silence_threshold: # level is returning 0
            self.last_voice_time = time.time()
        else:
            # Generates a new audio segment
            self.start_new_segment()

            # check the last (and previous) audio files
            await self.check_incomming_audio(self.segment_index - 2)
                

    async def check_incomming_audio(self, current_segment_index):
        """
        Check the incoming audio for silence detection.
        If silence is detected and the previous segment was speech,
        process the audio segment and generate a response.
        """
        print("check_incoming_message...")
        silence_detected = self.evaluate_energy(current_segment_index)
        print("silence detected", silence_detected)

        if silence_detected and not self.pre_silence_detected:
            print("found pause...", silence_detected, self.pre_silence_detected)
            self.to_reproduce.put("Ring04.wav")
            audio_file = self.join_audio(self.last_segment_index, current_segment_index)
            self.last_segment_index = current_segment_index
            response_file = await process_audio(audio_file, self.agent)
            self.to_reproduce.put(response_file)
        elif not silence_detected and self.pre_silence_detected:
            self.last_segment_index = current_segment_index

        self.pre_silence_detected = silence_detected


    def join_audio(self, min_segment, max_segment):
        """
        Auxiliary function to join audio segments. This method is used to concatenate
        multiple audio files into a single file.
        Then this new file can be used to process the audio data, for example for transcription.
        """

        inputfiles = [f"chat_files/segment_{i}.wav"  for i in range(min_segment, max_segment)]
        outputfile = f"chat_files/concat_{min_segment}_{max_segment}.wav"

        concat_wav_files(inputfiles, outputfile)

        return outputfile

    
    def evaluate_energy(self, current_segment_index):
        if current_segment_index < 0:
            return True

        # Give some time to ensure the file is written and is available
        time.sleep(0.1)
        
        file_name = f"chat_files/segment_{current_segment_index}.wav"
        print("evaluate_energy ", file_name)

        if not os.path.exists(file_name):
            raise FileNotFoundError(f"File not found: {file_name}")

        speech_results = self.vad.is_speech(file_name)
        self.vad.reset()

        # count speech and silence frames
        speech_counter = 0
        silence_counter = 0
        for i, is_speech_frame in enumerate(speech_results):
            #print(f"{i}->{is_speech_frame}")
            
            if is_speech_frame:
                speech_counter += 1
            else:
                silence_counter += 1

        print(f"{silence_counter}||{speech_counter}")

        # Calculate the silence ratio to determine if the segment is silent
        return (silence_counter / (speech_counter + silence_counter)) > 0.95


    async def poll(self):
        """
        Polling function to check audio levels and manage segments.
        This function should be executed periodically to ensure
        timely processing of audio data.
        """

        await self.check_audio_level()

# Subclass to extend the Account and get notifications etc.
class Account(pj.Account):
  def onRegState(self, prm):
    print("***OnRegState: " + prm.reason)
    if prm.code == 200:
       print("Registration successful!")
    else:
       print(f"Registration failed: {prm.code} {prm.reason}")


async def pjsua2_test(telephone):
  # Create and configure the endpoint
  ep = pj.Endpoint()
  ep.libCreate()

  ep_cfg = pj.EpConfig()
  ep_cfg.logConfig.level = 5

  # Configure User Agent settings (uaConfig)
  ua_cfg = pj.UaConfig()
  ua_cfg.maxCalls = 1
  # Set a public STUN server.
  proxies = pj.StringVector()
  proxies.append(STUN_PROXY)
  ua_cfg.stunServer = proxies 
  ep_cfg.uaConfig = ua_cfg

  # Configure Media settings
  media_cfg = pj.MediaConfig()
  ep_cfg.medConfig = media_cfg

  ep.libInit(ep_cfg)

  # SIP Transport (UDP)
  transport_cfg = pj.TransportConfig()
  ep.transportCreate(pj.PJSIP_TRANSPORT_UDP, transport_cfg)

  # Account Configuration
  acc_cfg = pj.AccountConfig()
  acc_cfg.idUri = SIP_ID
  acc_cfg.regConfig.registrarUri = SID_REGISTRAR

  # Proxy for outbound
  proxies = pj.StringVector()
  proxies.append(SIP_PROXY)
  acc_cfg.sipConfig.proxies = proxies

  # Credentials
  cred = pj.AuthCredInfo("digest", AUTH_DOMAIN, AUTH_USERNAME, 0, AUTH_PASSWORD)
  acc_cfg.sipConfig.authCreds.append(cred)

  # Configure NAT settings
  acc_cfg.natConfig.iceEnabled = False
  acc_cfg.natConfig.stunEnabled = True
  acc_cfg.natConfig.contactRewriteUse = 0

  acc_cfg.natConfig.sdpNatRewriteUse = 0
  acc_cfg.natConfig.viaRewriteUse = 0
  acc_cfg.natConfig.sdpNatRewriteUsePublicAddress = 1

  # Start the PJSUA2 library
  ep.libStart()
  print("*** PJSUA2 STARTED ***")

  # Create the account
  acc = Account()
  acc.create(acc_cfg)
  print(f"Account {acc_cfg.idUri} created.")

  print("Waiting 5 secs...")
  time.sleep(5)
  print("continue...")

  # Haz la llamada
  dest_number = f"<sip:{telephone}@{SID_DOMAIN}>"

  agent = MCPAgent()
  role = "Tú eres un asistente. Utiliza las tools si piensas que te pueden dar información util, si no utiliza tu conocimiento interno. Contesta siempre en español"
  await agent._ainitialize(role=role)

  call = MyCall(acc, dest_number, ep, agent)
  call_prm = pj.CallOpParam(True)
  
  call.makeCall(dest_number, call_prm)

  # Loop while the call is active
  while True:
      print("Waiting the call to finish...")
      ci = call.getInfo()
      if ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
          break

      await call.poll()  # Check audio level and handle segments
      time.sleep(0.5)


  # Here we don't have anything else to do..
  time.sleep(5)

  # Destroy the library
  ep.libDestroy()

#
# main()
#
if __name__ == "__main__":
  args = sys.argv[1:]
  asyncio.run(pjsua2_test(args[0]))

