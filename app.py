from flask import Flask, request, render_template, send_file
from pydub import AudioSegment
from pytube import YouTube

import glob
import io
import os
import re
import zipfile

app = Flask(__name__)
TARGET = -10.5

# Output directories
DOWNLOAD_TARGET = '/tmp/target/songs'
CONVERTED_TARGET = '/tmp/target/converted'

@app.route('/')
def index():
    return render_template('input_form.html')

@app.route('/generate-songs', methods=['POST'])
def convert_songs():
    songs_list = request.form['songs'].split(',')
    for song in songs_list:
        YouTube(song).streams.filter(only_audio=True)[0].download(DOWNLOAD_TARGET)

    # Convert songs and save to converted directory
    for song in glob.glob(f"{DOWNLOAD_TARGET}/*.mp4"):
        # Extract filename
        filename = extract_filename(DOWNLOAD_TARGET, song)

        # Convert audio
        orig = AudioSegment.from_file(song)
        orig += (TARGET - orig.dBFS)

        # Export file
        orig.export(f"{CONVERTED_TARGET}/{filename}.mp3", format='mp3')

    # Create zip file from converted songs
    file = io.BytesIO()
    with zipfile.ZipFile(file, 'w') as zip_file:
        for song in glob.glob(f"{CONVERTED_TARGET}/*.mp3"):
            # Extract filename
            filename = extract_filename(CONVERTED_TARGET, song, "mp3")

            # Create zip entry for file
            zip_file.write(song, arcname=f"{filename}.mp3", compress_type=zipfile.ZIP_DEFLATED)

    # Seek to beginning of memory file
    file.seek(0)

    # Clear downloaded / converted songs
    clear_directory(DOWNLOAD_TARGET)
    clear_directory(CONVERTED_TARGET)

    # Send zip file back to user
    return send_file(file, attachment_filename='songs.zip', as_attachment=True)

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

# Remove all files within a directory
def clear_directory(directory_path):
    for file in glob.glob(f"{directory_path}/*"):
        os.remove(file)

if __name__ == "__main__":
    app.run(host='0.0.0.0')
