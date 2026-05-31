""" PlayerScope audio player using pyaudio, and pydub or soundfile, DaveP V0.5 April-May 26
    Original using pydub by Dave Parkinson, davep@dhparki.com
    Modified to use soundfile instead of pydub to support Python 3.13 by GitHub AI
    AI bugs fixed, merged, simplified and speeded up by DaveP.

    NOTE pydub supports MPEG4 formats (aac and m4a) and isn't bugged for WAVs, but soundfile is faster.
         But pydub but won't run on Python 3.13 - so not Debian Trixie (boo!)

    Requires sudo apt install python3-pyaudio
             sudo apt install python3-pydub     (Python < 3.13)
        OR   sudo apt install python3-soundfile
"""

from our_utils import stfu, timeit
from pyaudio import PyAudio, paInt16
try:
    #raise Exception('Pydub inhibited')
    from pydub import AudioSegment
    print('audio_ps is using pydub')
except:
    import soundfile as sf
    AudioSegment = None
    print('audio_ps is using soundfile')
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
import numpy as np
from time import sleep

@stfu
def open_pyaudio():
    """ Open PyAudio quietly! """
    return PyAudio()

class AudioPlayer(QThread):
    DEFAULT_CHUNK_SIZE = 4096   # Samples per data frame
    if AudioSegment:            # These facilities currently pydub only (but see old AI version)
        FORCE_CHANNELS = 0      # 1 or 2 to force stereo or mono
        FORCE_FRAME_RATE = 0    # eg 44100 to force 44100 frames per second

    audio_signal = pyqtSignal(np.ndarray)

    def __init__(self, pyaudio, chunk_size=DEFAULT_CHUNK_SIZE):
        super().__init__()

        self.chunk_size = chunk_size

        self.channels = 0
        self.sample_width = 0
        self.frame_width = 0
        self.frame_rate = 0
        self.duration_seconds = 0
        self.raw_data = None
  
        self.thread_running = False
        self.is_playing = False
        self.index = 0
        self.new_index = -1     # For thread-safe seeking

        self.pa = pyaudio       # Interface to PortAudio    

    def __del__(self):
        self.thread_running = False

    # DON'T FORGET - the run method runs in its own thread; everything else is on the main QT thread.
    # (Getting this wrong can really screw things up!)
    @pyqtSlot()
    def run(self):
        # print("Thread start")
        # Open a .Stream object to write the file to
        stream = self.pa.open(format = self.pa.get_format_from_width(self.sample_width),
                              channels = self.channels,
                              rate = self.frame_rate,
                              #output_device_index = None # just take the system default
                              output = True)
        self.index = 0
        try:
            # Play the sound by writing the audio data to the stream
            while self.thread_running:
                newpos = False
                if self.new_index >= 0: # Handle seeking in a thread-safe (and not at all hacky!) way
                    self.index = self.new_index 
                    self.new_index = -1
                    newpos = True

                if self.is_playing:                      
                    start = self.index
                    end = start + self.chunk_size * self.frame_width
                    if end >= len(self.raw_data):
                        end = len(self.raw_data)
                        self.is_playing = False
                        self.thread_running = False
                    
                    if start < end-1:   # Avoid writing empty data - not sure if this is really needed
                        data = self.raw_data[start:end]
                        emission = np.frombuffer(data, dtype=np.int16)  # make integer array
                        if self.channels == 2:  # 2D if stereo
                            emission.shape = (-1, 2)
                        self.audio_signal.emit(emission)    # Emit the audio data for visualization
                        stream.write(data)   # This blocks!
                        self.index = end
                else:
                    if newpos:
                        start = self.index
                        end = min(len(self.raw_data), start + self.chunk_size * self.frame_width)
                        self.audio_signal.emit(np.frombuffer(self.raw_data[start:end], dtype=np.int16))  # Signal to update display on seek even when paused

                    sleep(0.1)  # Avoid busy-waiting when paused
    
        finally:
            self.index = 0
            self.is_playing = False
            self.thread_running = False
            stream.close()
            # print("Thread stop")
            return  # Exit thread - this will also signal the GUI

    def supportedFormats(self):
        """List supported formats (dumb version) - maybe make this smarter?"""
        if AudioSegment:
            return "*.aac *.aiff *.flac *.m4a *.mp3 *.ogg *.wav"
        else:
            return "*.aiff *.flac *.mp3 *.ogg *.wav"

    #@timeit
    def load(self, filename):
        """Load an audio file"""
        try:
            if AudioSegment:
                # Read audio file using pydub
                aseg = AudioSegment.from_file(filename)    # Open the sound file

                # Finagle to 16-bit; also force mono or stereo and/or frame-rate if specified
                aseg = aseg.set_sample_width(2)
                if self.FORCE_CHANNELS:
                    aseg = aseg.set_channels(self.FORCE_CHANNELS)
                if self.FORCE_FRAME_RATE:
                    aseg = aseg.set_frame_rate(self.FORCE_FRAME_RATE)

                #print(f"AudioSegment Channels: {aseg.channels}, Sample Width: {aseg.sample_width}," \
                #      f" Frame Width: {aseg.frame_width}, Frame Rate: {aseg.frame_rate}, Frame Count: {aseg.frame_count()}")

                self.channels = aseg.channels
                self.sample_width = aseg.sample_width
                self.frame_width = aseg.frame_width
                self.frame_rate = aseg.frame_rate
                self.duration_seconds = aseg.duration_seconds
                self.raw_data = aseg.raw_data    # Get the raw audio data as a bytestring
            else:
                # Read audio file using soundfile
                # Simple DaveP code runs 20% to 100% faster than AI's, but doesn't support forcing channels or frame rate
                data, sample_rate = sf.read(filename, dtype='int16')
                if len(data.shape) == 1:
                    channels = 1
                else:
                    channels = data.shape[1]

                # Convert to raw bytes
                self.raw_data = data.tobytes()
                
                # Set audio properties
                self.channels = channels
                self.sample_width = 2  # 16-bit = 2 bytes
                self.frame_width = channels * self.sample_width
                self.frame_rate = sample_rate
                self.duration_seconds = len(data) / sample_rate
 
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            return False

    def play(self):
        """Play the loaded audio file"""

        if not self.thread_running:
            self.start()  # Start the audio player thread
            self.thread_running = True
            
        self.is_playing = True

    def pause(self):
        """Pause playback"""
        self.is_playing = False

    def stop(self):
        """Stop playback"""
        self.is_playing = False
        self.thread_running = False

    def rewind(self, secs):
        """Rewind playback"""
        self.new_index = max(0, self.index - int(secs * self.frame_rate) * self.frame_width)  # Note we need to keep this frame-aligned!

    def fast_forward(self, secs):
        """Fast forward playback"""
        self.new_index = min(len(self.raw_data), self.index + int(secs * self.frame_rate) * self.frame_width)

    def seek(self, secs):
        """Seek to a specific position in seconds"""
        self.new_index = max(0, min(len(self.raw_data), int(secs * self.frame_rate) * self.frame_width))  

    def get_duration(self):
        """Get total duration in seconds"""
        return self.duration_seconds

    def get_position(self):
        """Get current play position in seconds"""
        return self.index / (self.frame_rate * self.frame_width)
    
    def set_chunk_size(self, chunk_size):
        """Set the chunk size - may need to do more than this in future"""
        self.chunk_size = chunk_size

class AudioRecorder(QThread):
    DEFAULT_CHUNK_SIZE = 4096   # Samples per data chunk
    DEFAULT_FRAME_RATE = 44100  # Frames per second
    DEFAULT_MAX_TIME = 120      # Max record time in seconds

    audio_signal = pyqtSignal(np.ndarray)

    def __init__(self, pyaudio, chunk_size=DEFAULT_CHUNK_SIZE, frame_rate=DEFAULT_FRAME_RATE, max_time=DEFAULT_MAX_TIME):
        super().__init__()

        self.chunk_size = chunk_size
        self.frame_rate = frame_rate
        self.max_chunks = (frame_rate * max_time) // chunk_size
        self.data_chunks = []
        self.thread_running = False
        self.is_recording = False

        self.pa = pyaudio # Interface to PortAudio    

    def __del__(self):
        self.thread_running = False

    # DON'T FORGET - the run method runs in its own thread; everything else is on the main QT thread.
    # (Getting this wrong can really screw things up!)
    @pyqtSlot()
    def run(self):
        #print("Record thread start")

        stream = self.pa.open(format = paInt16,    
                                   rate = self.frame_rate,
                                   channels = 1, 
                                   #input_device_index = None # just take the system default
                                   input = True,
                                   frames_per_buffer=self.chunk_size)

        try:
            while self.thread_running:
                data = stream.read(self.chunk_size)
                self.audio_signal.emit(np.frombuffer(data, dtype=np.int16))    # Emit the audio data for visualization
                if self.is_recording:
                    self.data_chunks.append(data)
                    if self.max_chunks and (len(self.data_chunks) >= self.max_chunks):
                        self.thread_running = False
    
        finally:
            stream.stop_stream()
            stream.close()

            self.is_recording = False
            self.thread_running = False
            #print("Record thread stop")
            return  # Exit thread - this will also signal the GUI

    def supportedFormats(self):
        """List supported formats (dumb version) - maybe make this smarter?"""
        return "*.aiff *.flac *.mp3 *.ogg *.wav"    # Same for pydub and soundfile

    def monitor(self):
        """Start monitor"""
        if not self.thread_running:
            self.start()  # Start the audio player thread
            self.thread_running = True

    def record(self):
        """Start recording"""
        if not self.thread_running:
            self.start()  # Start the audio player thread
            self.thread_running = True

        self.is_recording = True

    def pause(self):
        """Pause recording"""
        self.is_recording = False

    def stop(self):
        """Stop monitor/recording"""
        self.is_recording = False
        self.thread_running = False

    def save(self, fname, format):
        """Save recording"""
        try:
            if AudioSegment:
                seg = AudioSegment(
                    data = b''.join(self.data_chunks),  # raw PCM data
                    sample_width=2,                     # 16-bit audio
                    frame_rate=self.frame_rate,  
                    channels=1                          # mono
                )
                seg.export(fname, format) 
            else:
                # Combine all recorded chunks
                raw_data = b''.join(self.data_chunks)
                
                # Convert raw bytes back to numpy array (16-bit PCM, mono)
                audio_data = np.frombuffer(raw_data, dtype=np.int16)
                            
                # Write audio file using soundfile (DaveP simple version)
                sf.write(fname, audio_data, self.frame_rate, format=format.upper())

            return True
        except Exception as e:
            print(f"Error exporting file: {e}")
            return False

    def clear(self):
        """Clear recording"""
        self.data_chunks = []

    def get_record_time(self):
        """Get current record time in seconds"""
        return len(self.data_chunks) * self.chunk_size / self.frame_rate

    def set_chunk_size(self, chunk_size):
        """Set the chunk size - may need to do more than this in future"""
        self.chunk_size = chunk_size

def test_play():
    """Test play routine - set filename as required"""
    #filename = "../music/I'd Rather Go Blind.m4a"  Not supported by soundfile - boo!
    filename = "../music/Grey Clouds (Original).mp3"

    pyaudio = open_pyaudio()
    ap = AudioPlayer(pyaudio)

    filepath = os.path.join(os.path.dirname(__file__), filename)  
    if ap.load(filepath):
        ap.play()

        # Main loop just sleeps
        try:
            print(f'Playing {filename}, ^C to quit')
            while True:
                sleep(3600)
        finally:
            print('Quitting')

def test_record():
    """Test record routine - set filename as required"""
    filename = "test.wav"
    filetype = "wav"

    pyaudio = open_pyaudio()
    ap = AudioRecorder(pyaudio)

    input("Press Enter to record (2 minutes max)...")
    ap.record()

    input("Press Enter again to stop...")
    ap.stop()
    sleep(0.2)  # Just in case!

    filepath = os.path.join(os.path.dirname(__file__), filename)  
    ap.save(filepath, filetype)
    print(f'Saved as {filetype}:  {filepath}')

if __name__ == "__main__":    
    import os

    test_play()
    #test_record()
