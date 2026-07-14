# PlayerScope

Audio Player/Recorder with Oscilloscope and Spectrum Analyzer for Raspberry Pi 3/4/5 Debian Bookworm and similar - python3, pyqt5, pyqtgraph, pyaudio, pydub OR soundfile.

## Screenshot

![PlayerScope screen grab](playerscope.png)

## Description

I needed an audio player with oscilloscope and spectrum display to run on my Raspberry Pi.  Having failed to find one that worked on the web, I tried to "vibe code" one using AI.  When this didn't work either I ended up writing one myself.  (Bits of the GUI and the soundfile support are still by AI; the rest is human coded.)  I'm putting it on GitHub in case it's useful to anyone else.  

## Installing

To install on Debian Bookwork using pydub for audio load and save use install_bookworm.sh.  To install on Trixie using soundfile for load and save (because pydub doesn't work) use install_trixie.sh.

## Executing program

Use run.sh

## Limitations

When I put PlayerScope on GitHub on 30/5/26, it wasn't working on Trixie; this appeared to be due to problems with pyaudio support.  Having reinstalled Trixie from scratch on 11/06/26, it now appears to be working, though there remains an issue of audio output not being redirected to Bluetooth when this is set up on the desktop.  It remains fine on Debian Bookworm.

## Documentation

Inline in the code

## Authors

Dave Parkinson, dhparki@outlook.com

## Version History

* 0.5
    * First public release on GitHub

## License

MIT License - Feel free to modify and distribute
