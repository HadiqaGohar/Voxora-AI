from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts
import asyncio
import io
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    voice = data.get('voice', 'en-US-AriaNeural')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    async def generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])
        audio_data.seek(0)
        return audio_data
    
    audio_data = asyncio.run(generate())
    return send_file(audio_data, mimetype='audio/mpeg', as_attachment=True, download_name='tts_output.mp3')

@app.route('/api/voices', methods=['GET'])
def voices():
    async def get_voices():
        voices = await edge_tts.list_voices()
        return voices
    
    voices_list = asyncio.run(get_voices())
    return jsonify(voices_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
