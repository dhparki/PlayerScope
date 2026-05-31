""" Entry Point and Main Application Window for PlayerScope V0.5
    GUI code originally by GitHub AI, substantially rewritten by DaveP April-May 26
    Oscilloscope and Spectrum Analyser using pyqtgraph added by DaveP
    Dave Parkinson, davep@dhparki.com
    Requires sudo apt install python3-pyqtgraph
"""

import os
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy, QMessageBox, 
                             QPushButton, QSlider, QLabel, QFileDialog, QTabWidget, QProgressBar, QCheckBox,
                             QRadioButton, QButtonGroup, QComboBox, QApplication)
from PyQt5.QtCore import Qt 
from PyQt5.QtGui import QFont
import pyqtgraph as pg
from audio_ps import open_pyaudio, AudioPlayer, AudioRecorder
from our_utils import stfu, timeit
import numpy as np
from time import sleep
# from scipy import signal  # Required if using Hann window for spectrum

class PlayerScope(QMainWindow):

    DEFAULT_CHUNK_SIZE = 2048    # Samples per data chunk
    DEFAULT_SAMPLE_RATE = 44100  # Default audio sample rate
    MAX_RECORD_MINUTES = 2       # Maximum record time 

    # Visibility flags - may have SCOPE_VISIBLE | SPECTRUM_VISIBLE to show both
    SCOPE_VISIBLE = 1
    SPECTRUM_VISIBLE = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlayerScope")
        
        # Initialize audio player
        self.pyaudio = open_pyaudio()   # Only want one of these
        self.player = AudioPlayer(self.pyaudio, self.DEFAULT_CHUNK_SIZE)
        self.recorder = AudioRecorder(self.pyaudio, self.DEFAULT_CHUNK_SIZE, 
                                      self.DEFAULT_SAMPLE_RATE, self.MAX_RECORD_MINUTES*60)
        
        # Setup UI
        self.twin_beam = False          # Default to single beam
        self.setup_ui()

        # Apply signals
        # NOTE There are two main threads in this app, this one handling the GUI and graphical display,
        # and the one started in audio_ps.py which handles actual audio i/o.  Communication from the
        # audio thread to this one is via these signals.  Communication the other way is by setting
        # atomic flags and variables.  AI tells me this is a kludge, but I thnk it is relatively safe 
        # because of the way Python handles multi-threading (see Python GIL = Global Interpeter Lock).
        # (Anyway, AI's version suffered from audio break-up and kept crashing, so nerr.)
    
        self.player.audio_signal.connect(self.update_play)
        self.player.finished.connect(self.thread_has_finished)

        self.recorder.audio_signal.connect(self.update_record) 
        self.recorder.finished.connect(self.rec_thread_has_finished)

    def __del__(self):
        if self.pyaudio:
            self.pyaudio.terminate()     # Clean up PortAudio resources

    def closeEvent(self, event):
        """Stop audio before closing"""
        if self.player:
            self.player.stop()     
        if self.recorder:
            self.player.stop()    
        sleep(0.2)  # To be on the safe side!
        event.accept()
        
    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Title label
        title_label = QLabel("Audio Player/Recorder with Oscilloscope and Spectrum Analyzer")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        self.visibility = self.SCOPE_VISIBLE    # Default to showing scope

        # Oscilloscope plot
        self.scope = pg.PlotWidget()

        # Colours are based on a Tektronix 515A scope
        # (No AI, I didn't have one as a child and love it dearly.  I just think it looks nice.)
        self.scope.setBackground("#034A0A")                 # Dark green background
        self.scope.setTitle("Oscilloscope", color="#E28B48", size="20pt")
        self.scope.setXRange(0, self.DEFAULT_CHUNK_SIZE, padding=0) # Adjust to audio_player chunk size

        self.scope.setYRange(-32768, 32767, padding=0)        # Assuming 16-bit audio

        axis_pen = pg.mkPen(color="#E28B4800", width=1)     # Transparent Orange axes - hidden
        self.scope.getAxis('left').setPen(axis_pen)
        self.scope.getAxis('bottom').setPen(axis_pen)
        self.scope.showGrid(x=True, y=True, alpha=0.7)        # Non-transparent grid - shown
        #self.scope.showAxes(False, False)                    # Sadly, this also hides the grid lines :-(

        waveform_pen = pg.mkPen(color="#AEFFA2", width=2) # Bright green waveform  
        if self.twin_beam:
            self.scope_data1 = self.scope.plot([16383 for x in range(self.DEFAULT_CHUNK_SIZE)], pen=waveform_pen)
            self.scope_data2 = self.scope.plot([-16384 for x in range(self.DEFAULT_CHUNK_SIZE)], pen=waveform_pen)
        else:
            self.scope_data1 = self.scope.plot([0 for x in range(self.DEFAULT_CHUNK_SIZE)], pen=waveform_pen)
            self.scope_data2 = self.scope.plot([], pen=waveform_pen)

        self.scope.setMinimumHeight(250)  
        main_layout.addWidget(self.scope)

        # Spectrum analyzer plot
        self.spectrum_frame = QWidget()
        spectrum_layout = QHBoxLayout(self.spectrum_frame)

        self.vscale_slider = QSlider(Qt.Vertical)                   # Slider adjusts verical scale
        self.vscale_slider.setSliderPosition(50)
        self.vscale_slider.setEnabled(True)
        self.vscale_slider.sliderMoved.connect(self.vscale_slider_moved)
        spectrum_layout.addWidget(self.vscale_slider)

        self.spectrum = pg.PlotWidget()
        self.spectrum.setBackground("w")                             # White background
        self.spectrum.setTitle("Spectrum Analyzer", color="k", size="20pt")   # black title
                   
        axis_pen = pg.mkPen(color="k", width=1)                      # Black axes 
        self.spectrum.getAxis('left').setPen(axis_pen)
        self.spectrum.getAxis('bottom').setPen(axis_pen)

        self.spectrum.setXRange(1.0, 4.5, padding=0)    # Approx 10Hz to 30KHz log scale
        self.spectrum_ymax = 20_000_000                 # Trial and error!  
        self.spectrum.setYRange(0, self.spectrum_ymax * 50 // 100, padding=0)  

        # Histogram plot
        freqs = np.fft.rfftfreq(self.DEFAULT_CHUNK_SIZE+1, d=1/self.DEFAULT_SAMPLE_RATE)    
        spectrum_pen = pg.mkPen(color="k", width=1)  # Black pen
        spectrum_brush = pg.mkBrush(color="#7CA6D8")  # Blue fill
        self.spectrum_data =self.spectrum.plot(freqs, [0 for x in range(len(freqs)-1)], stepMode=True, fillLevel=0, pen=spectrum_pen, brush=spectrum_brush)

        self.spectrum.setMinimumHeight(250) 
        spectrum_layout.addWidget(self.spectrum)

        self.spectrum_frame.hide()    # Initially hidden
        main_layout.addWidget(self.spectrum_frame)

        # Settings layout
        settings_layout = QHBoxLayout()

        button_group = QButtonGroup(self)

        button = QRadioButton("Scope")
        button.setChecked(True)
        settings_layout.addWidget(button)
        button_group.addButton(button, self.SCOPE_VISIBLE)

        button = QRadioButton("Spectrum")
        settings_layout.addWidget(button)
        button_group.addButton(button, self.SPECTRUM_VISIBLE)

        button = QRadioButton("Both")
        settings_layout.addWidget(button)
        button_group.addButton(button, self.SCOPE_VISIBLE | self.SPECTRUM_VISIBLE)

        button_group.idClicked.connect(self.set_visibility)

        settings_layout.addStretch()    # Gap between radio buttons and twin beam check box

        checkbox = QCheckBox("Twin Beam")
        #checkbox.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        checkbox.stateChanged.connect(self.twin_beam_changed)
        settings_layout.addWidget(checkbox)

        settings_layout.addStretch()    # Gap between twin beam checkbox and buffer size selector

        bufsize_label = QLabel("Buffer size:")
        settings_layout.addWidget(bufsize_label)
        
        self.bufsize_combo = QComboBox()
        self.bufsize_options = [256, 512, 1024, 2048, 4096, 8192, 16384]  # samples
        for bs in self.bufsize_options:
            self.bufsize_combo.addItem(f"{bs} samples", bs)
        self.bufsize_combo.setCurrentIndex(self.bufsize_options.index(self.DEFAULT_CHUNK_SIZE)) # Set default selection
        self.bufsize_combo.currentIndexChanged.connect(self.on_bufsize_changed)
        settings_layout.addWidget(self.bufsize_combo)

        main_layout.addLayout(settings_layout)

        # Record / Play tabs
        tabs_widget = QTabWidget()
        tabs_widget.setTabPosition(QTabWidget.North)
        tabs_widget.currentChanged.connect(self.tab_changed)

        # Play tab
        play_tab = QWidget()
        play_layout = QVBoxLayout(play_tab)

        # File selection and info row
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file loaded")
        file_layout.addWidget(self.file_label)
        
        open_button = QPushButton("Open audio File")
        open_button.clicked.connect(self.open_file)
        file_layout.addWidget(open_button)
        play_layout.addLayout(file_layout)
        
        # Position slider and time display
        position_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        position_layout.addWidget(self.time_label)
        
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setSliderPosition(0)
        self.position_slider.setEnabled(False)
        self.position_slider.sliderMoved.connect(self.on_slider_moved)
        position_layout.addWidget(self.position_slider)
        
        play_layout.addLayout(position_layout)
                
        # Control buttons layout
        controls_layout = QHBoxLayout()
        
        # Play/Pause button
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.play_pause_button.setEnabled(False)
        controls_layout.addWidget(self.play_pause_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.stop_button)
        
        # Rewind button
        self.rewind_button = QPushButton("Rewind (5s)")
        self.rewind_button.clicked.connect(self.rewind)
        self.rewind_button.setEnabled(False)
        controls_layout.addWidget(self.rewind_button)
        
        # Fast forward button
        self.ff_button = QPushButton("Fast Forward (5s)")
        self.ff_button.clicked.connect(self.fast_forward)
        self.ff_button.setEnabled(False)
        controls_layout.addWidget(self.ff_button)
        
        play_layout.addLayout(controls_layout)

        tabs_widget.addTab(play_tab, 'Play')

        # Record tab
        record_tab = QWidget()
        record_layout = QVBoxLayout(record_tab)

        # Progress bar
        record_inner = QHBoxLayout()
        rec_progress_label = QLabel(f"Max {self.MAX_RECORD_MINUTES} minutes:")
        record_inner.addWidget(rec_progress_label)

        self.rec_progress_bar = QProgressBar()
        self.rec_progress_bar.setValue(0)
        record_inner.addWidget(self.rec_progress_bar)

        record_layout.addLayout(record_inner)

        # Record butttons
        record_inner3 = QHBoxLayout()

        # Record monitor button
        self.rec_monitor_button = QPushButton("Monitor")
        self.rec_monitor_button.clicked.connect(self.rec_monitor)
        record_inner3.addWidget(self.rec_monitor_button)
        
        # Record/pause record button
        self.record_pause_button = QPushButton("Record")
        self.record_pause_button.clicked.connect(self.record_pause)
        record_inner3.addWidget(self.record_pause_button)

        # Record stop button
        self.rec_stop_button = QPushButton("Stop")
        self.rec_stop_button.clicked.connect(self.rec_stop)
        self.rec_stop_button.setEnabled(False)
        record_inner3.addWidget(self.rec_stop_button)

        record_layout.addLayout(record_inner3)
        #record_layout.addStretch()    # Gap at bottom

        tabs_widget.addTab(record_tab, 'Record')
        tabs_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)   # Don't want tabs to stretch vertically

        main_layout.addWidget(tabs_widget)

    def tab_changed(self, index):
        """Change between play and record"""
        if index == 0: 
            self.recorder.stop()
        elif index == 1:
            self.player.stop()

    @stfu   # suppress libpng warning: iCCP: known incorrect sRGB profile
    def get_file_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Audio File",
            None,   #os.path.expanduser("~"),
            f"Audio Files ({self.player.supportedFormats()});;All Files (*)" # 
        )
        return file_path
    
    def play_buttons(self, pp_enabled, rest_enabled):
        # Enable or disable all buttons
        self.play_pause_button.setEnabled(pp_enabled)
        self.stop_button.setEnabled(rest_enabled)
        self.rewind_button.setEnabled(rest_enabled)
        self.ff_button.setEnabled(rest_enabled)
        self.position_slider.setEnabled(rest_enabled)

    def open_file(self):
        """Open an audio file"""

        if self.player.thread_running:
            self.stop_playback()
            sleep(0.2)   # Yield to the event loop so the audio thread can finish

        self.file_label.setText("Loading...")   # A sleep cursor would be better!
        file_path = self.get_file_path()
        
        if file_path:
            if self.player.load(file_path):
                self.file_label.setText(f"File: {os.path.basename(file_path)}")
                
                # Enable controls
                self.play_buttons(True, False)
               
                # Update slider
                duration = self.player.get_duration()
                self.position_slider.setMaximum(int(duration * 1000))   # Slider in milliseconds

                self.update_time_display()
                
            else:
                self.file_label.setText("Error loading file")

    def toggle_play_pause(self):
        """Toggle play/pause"""        
        if self.player.is_playing:
            self.player.pause()
            self.play_pause_button.setText("Play")
        else:
            self.player.play()
            self.play_pause_button.setText("Pause")
            self.play_buttons(True, True)
    
    def stop_playback(self):
        """Stop playback"""
        self.player.stop()
        self.play_pause_button.setText("Play")

    def rewind(self):
        """Rewind 5 seconds"""
        self.player.rewind(5)
    
    def fast_forward(self):
        """Fast forward 5 seconds"""
        self.player.fast_forward(5)
    
    def on_slider_moved(self, value):
        """Handle slider movement for seeking"""
        self.player.seek(value / 1000.0)
    
    def on_bufsize_changed(self, index):
        """Handle buffer size selection change"""
        bufsize = self.bufsize_combo.itemData(index)
        self.player.set_chunk_size(bufsize)

        if self.visibility & self.SCOPE_VISIBLE:
            self.scope.setXRange(0, bufsize, padding=0)

    def update_time_display(self):
        """Update time display and slider"""
        position = self.player.get_position()
        duration = self.player.get_duration()
        
        # Format time display
        pos_minutes = int(position) // 60
        pos_seconds = int(position) % 60
        dur_minutes = int(duration) // 60
        dur_seconds = int(duration) % 60

        time_str = f"{pos_minutes:02d}:{pos_seconds:02d} / {dur_minutes:02d}:{dur_seconds:02d}"
        self.time_label.setText(time_str)
        
        # Update slider position
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(int(position * 1000))
        self.position_slider.blockSignals(False)

    #@timeit
    def stereo_to_mono(self, data):
        """Convert 2D stereo numpy array to 1D mono"""
    
        #newdata = np.empty(len(data), np.int16)
        #for i, d in enumerate(data):
        #    newdata[i] = (int(d[0])+int(d[1])) // 2
        #return newdata

        # Less accurate but MUCH faster!
        return data[:, 0] // 2 + data[:, 1] // 2

    def clear_waveforms(self):
        """Clear scope and spectrum dispays"""
        if self.twin_beam:
            self.scope_data1.setData([16383 for x in range(self.DEFAULT_CHUNK_SIZE)] )
            self.scope_data2.setData([-16384 for x in range(self.DEFAULT_CHUNK_SIZE)] )
        else:
            self.scope_data1.setData([0 for x in range(self.DEFAULT_CHUNK_SIZE)] )
            self.scope_data2.setData([])

        freqs = np.fft.rfftfreq(self.DEFAULT_CHUNK_SIZE+1, d=1/self.DEFAULT_SAMPLE_RATE)  
        self.spectrum_data.setData(freqs, [0 for x in range(self.DEFAULT_CHUNK_SIZE//2)])

    def update_waveforms(self, data, frame_rate):
        """Update the scope and spectrum displays with new audio data"""

        if self.visibility & self.SCOPE_VISIBLE:
            if self.twin_beam:
                if len(data.shape) == 2:    # Stereo signal
                    self.scope_data1.setData(data[:, 0] // 2 + 16383)
                    self.scope_data2.setData(data[:, 1] // 2 - 16384)
                else:
                    self.scope_data1.setData(data // 2 + 16383)
                    self.scope_data2.setData(data // 2 - 16384) # Duplicate beams
                    #Alternatively clear beam2?
                    #self.scope_data2.setData([-16384 for x in range(self.DEFAULT_CHUNK_SIZE)] ) 
            else:
                if len(data.shape) == 2:    # Stereo convert
                    data = self.stereo_to_mono(data)

                self.scope_data1.setData(data)

        if self.visibility & self.SPECTRUM_VISIBLE:
            if len(data.shape) == 2:    # Always want mono for spectrum
                data = self.stereo_to_mono(data)

            # Apply Hann window - an idea by AI, which doesn't seem to make much difference
            # Requires from scipy import signal
            # data = data * signal.hann(len(data))

            fft = np.abs(np.fft.rfft(data))
            freqs = np.fft.rfftfreq(len(data)+2, d=1/frame_rate)  # +2 gives extra x-value for histogram plot
            # fft = 20 * np.log10(fft + 1e-10)  # A terrible idea by AI! (+1e-10 is to avoid log(0) )
            freqs = np.log10(freqs + 1e-10)     # A somewhat better idea I think.
            self.spectrum_data.setData(freqs, fft)

    def update_play(self, data):
        """Update the waveform display for play"""
        #print(f"Received audio data chunk of length {len(data)}")
 
        self.update_waveforms(data, self.player.frame_rate)
        self.update_time_display()

    def thread_has_finished(self):
        #print("Play thread has finished.")

        self.clear_waveforms()
            
        self.update_time_display()
        self.play_pause_button.setText("Play")
        self.play_buttons(True, False)
            
    def set_visibility(self, value):
        self.visibility = value
        
        self.spectrum_frame.setVisible(bool(value & self.SPECTRUM_VISIBLE))
        self.scope.setVisible(bool(value & self.SCOPE_VISIBLE))

    def twin_beam_changed(self, state):
        """Handle change between single and twin-beam scope"""
        self.twin_beam = (state == Qt.Checked)
        self.clear_waveforms()

    def vscale_slider_moved(self, value):
        """Handle vertical scale slider movement"""
        self.spectrum.setYRange(0, self.spectrum_ymax * (100-value) // 100, padding=0)  

    def rec_buttons(self, enabled):
        self.rec_monitor_button.setEnabled(enabled[0])
        self.record_pause_button.setEnabled(enabled[1])
        self.rec_stop_button.setEnabled(enabled[2])

    def rec_monitor(self):
        """Start record monitoring"""
        self.recorder.monitor()
        self.rec_buttons((False, True, True))

    def record_pause(self):
        """Star/pause record recording"""

        if self.recorder.is_recording:
            self.recorder.pause()
            self.record_pause_button.setText("Record")
        else:
            self.recorder.record()
            self.record_pause_button.setText("Pause")
            self.rec_buttons((False, True, True))
 
    def rec_stop(self):
        """Stop record and monitor"""
        self.recorder.stop()

    def update_record(self, data):
        """Update the record waveform display """
        #print(f"Received audio data chunk of length {len(data)}")
        self.update_waveforms(data, self.recorder.frame_rate) 
        progress = int((self.recorder.get_record_time() / (self.MAX_RECORD_MINUTES * 60)) * 100)
        self.rec_progress_bar.setValue(progress)

    @stfu   # suppress libpng warning: iCCP: known incorrect sRGB profile
    def get_save_path(self):
        file_name, _ = QFileDialog.getSaveFileName(    # Returns file_name, filter
            self, 
            "Save Audio File", 
            None,   #os.path.expanduser("~"),
            f"Audio Files ({self.recorder.supportedFormats()});;All Files (*)") 
        return file_name
    
    def rec_thread_has_finished(self):
        #print("Record thread has finished.")

        self.record_pause_button.setText("Record")
        self.rec_buttons((True, True, False))
        self.rec_progress_bar.setValue(0)

        self.clear_waveforms()

        # This is a good point to save, once the thread has stopped
        if self.recorder.data_chunks:
            keep_trying = True
            while keep_trying:
                keep_trying = False
                file_name = self.get_save_path()
                if file_name:
                    # This version assumes format in file extension - e.g. myfile.mp3
                    ext = os.path.splitext(file_name)[1][1:]
                    format = ext if ext else 'wav'  # Default to wav
                    if format.lower() == 'aif':     # Bodge for Windows!
                        format = 'aiff'
                    if not self.recorder.save(file_name, format):
                        QMessageBox.warning(self, "Save failed", f"Could't save {file_name} as {format} format")
                        keep_trying = True
                
        self.recorder.clear()

# Main function to run the application
def main():
    app = QApplication([])
    #app.setStyle('Fusion') #'cleanlooks', 'gtk2', 'cde', 'motif', 'plastique', 'qt5ct-style', 'Windows', 'Fusion'

    window = PlayerScope()
    window.show()
    app.exec_()

if __name__ == "__main__":
    main()
