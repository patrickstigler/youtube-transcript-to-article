from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import os

app = Flask(__name__)

# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_transcript(video_id, target_lang=None):
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    text = " ".join([t['text'] for t in transcript])
    return text

def generate_article(transcript, detail_level="short", target_lang=None):
    prompt = f"Schreibe einen {'detaillierten' if detail_level == 'detailed' else 'kurzen'} professionellen Artikel basierend auf diesem Transkript:\n\n{transcript}"
    
    if target_lang:
        prompt += f"\n\nSchreibe den Artikel in {target_lang}."
    
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=500 if detail_level == "short" else 1500,
        temperature=0.7
    )
    return response.choices[0].text.strip()

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    video_id = data.get('video_id')
    detail_level = data.get('detail_level', 'short')
    target_lang = data.get('target_lang', None)
    
    transcript = get_transcript(video_id)
    article = generate_article(transcript, detail_level, target_lang)
    
    return jsonify({"article": article})

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
