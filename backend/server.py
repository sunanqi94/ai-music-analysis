import os, sys, json, tempfile
from flask import Flask, request, jsonify, send_file

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyzer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)

@app.route('/')
def serve_frontend():
    return send_file(os.path.join(PROJECT_ROOT, 'backend_demo.html'))

@app.route('/api/formats')
def get_formats():
    fmts, mp3 = analyzer.supported_formats()
    return jsonify({
        'formats': fmts,
        'mp3_supported': mp3,
        'note': '' if mp3 else 'MP3/M4A requires ffmpeg',
        'chord_count': len(analyzer._build_chord_library()),
        'genres': analyzer.GENRES
    })

@app.route('/api/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file'}), 400
    file = request.files["file"]
    ext = os.path.splitext(file.filename)[1].lower()
    tmp = os.path.join(tempfile.gettempdir(), 'music_' + str(os.getpid()) + ext)
    file.save(tmp)
    try:
        result = analyzer.full_analysis(tmp)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

@app.route('/api/lyrics', methods=['POST'])
def match_lyrics():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data'}), 400
    lyrics = data.get("lyrics", "")
    melody = data.get("melody", [])
    duration = data.get("duration", 30)
    if not lyrics or not melody:
        return jsonify({'success': False, 'error': 'Need lyrics + melody'}), 400
    try:
        result = analyzer.match_lyrics_to_melody(lyrics, melody, duration)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
     app.run(host='127.0.0.1', port=5002, debug=False)
