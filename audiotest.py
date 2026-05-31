# Elementary pyaudio test, works on Pi5 Debian Bookworm
# Fails on Trixie following a reboot at line 8 with OSError: [Errno -9994] Sample format not supported
import pyaudio
import wave

filename = 'test.wav'
wf = wave.open(filename, 'rb')
p = pyaudio.PyAudio()
stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                 channels=wf.getnchannels(),
                 rate=wf.getframerate(),
                 output=True)

data = wf.readframes(1024)
while data:
    stream.write(data)
    data = wf.readframes(1024)

stream.stop_stream()
stream.close()
p.terminate()
