from flask import Flask, request, render_template, send_file
from pydub import AudioSegment
from pytube import YouTube

import glob
import io
import os
import re
import threading
import time
import zipfile

app = Flask(__name__)
TARGET = -10.5

# Output directories
DOWNLOAD_TARGET = '/tmp/target/songs'
CONVERTED_TARGET = '/tmp/target/converted'

# Class to hold information about progress in converting a list of songs
class ConversionProgress:
    def __init__(self):
        # 0 - no conversion, 1 - downloading, 2 - converting
        self.state = 0
        self.zip_file = io.BytesIO()

    def get_state(self):
        return self.state

    def get_file(self):
        return self.zip_file

    def set_state(self, state):
        self.state = state

    def reset(self):
        self.state = 0
        self.zip_file = io.BytesIO()

# Static conversion progress object
conversion = ConversionProgress()

@app.route('/')
def index():
    return render_template('input_form.html')

@app.route('/_progress', methods=['GET'])
def get_progress():
    return {'state': conversion.get_state()}

@app.route('/generate-songs', methods=['POST'])
def kickoff_conversion():
    # Kickoff async conversion
    thread = threading.Thread(target=convert_songs, args=(request.form['songs'].split(','),))
    thread.start()

    return render_template('input_form.html')

@app.route('/download-songs', methods=['POST'])
def download_songs():
    thread = threading.Thread(target=reset)
    thread.start()

    return send_file(conversion.zip_file, attachment_filename='songs.zip', as_attachment=True)

# Converts songs, called asynchronously
def convert_songs(songs_list):
    conversion.set_state(1)
    for song in songs_list:
        YouTube(song).streams.filter(file_extension='mp4')[0].download(DOWNLOAD_TARGET)

    # Convert songs and save to converted directory
    conversion.set_state(2)
    for song in glob.glob(f"{DOWNLOAD_TARGET}/*.mp4"):
        # Extract filename
        filename = extract_filename(DOWNLOAD_TARGET, song)

        # Convert audio
        orig = AudioSegment.from_file(song)
        orig += (TARGET - orig.dBFS)

        # Export file
        orig.export(f"{CONVERTED_TARGET}/{filename}.mp3", format='mp3', parameters=["-b:a", "96k", "-map", "0:a:0"])

    # Create zip file from converted songs
    with zipfile.ZipFile(conversion.zip_file, 'w') as zip_file:
        for song in glob.glob(f"{CONVERTED_TARGET}/*.mp3"):
            # Extract filename
            filename = extract_filename(CONVERTED_TARGET, song, "mp3")

            # Create zip entry for file
            zip_file.write(song, arcname=f"{filename}.mp3", compress_type=zipfile.ZIP_DEFLATED)

    # Seek to beginning of memory file
    conversion.zip_file.seek(0)
    conversion.set_state(3)

@app.before_first_request
def bootstrap():
    create_directories()

def extract_filename(prefix, pattern, extension="mp4"):
    regex = re.compile(fr"{prefix}/(.*).{extension}")
    return regex.search(pattern).group(1)

# Initial bootstrapping to create directories for songs
def create_directories():
    os.makedirs(DOWNLOAD_TARGET, exist_ok=True)
    os.makedirs(CONVERTED_TARGET, exist_ok=True)

# Clear songs and reset conversion progress, called async
def reset():
    time.sleep(1)
    clear_directory(DOWNLOAD_TARGET)
    clear_directory(CONVERTED_TARGET)
    conversion.reset()

# Remove all files within a directory
def clear_directory(directory_path):
    for file in glob.glob(f"{directory_path}/*"):
        os.remove(file)

if __name__ == "__main__":
    app.run(host='0.0.0.0')
