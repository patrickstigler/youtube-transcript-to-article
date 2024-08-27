import os
import re
from flask import Flask, request, jsonify, render_template
import openai  # Changed to lowercase
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

app = Flask(__name__)

# Initialize the OpenAI client with the API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")  # Updated to use openai

def extract_video_id(url_or_id):
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id

def get_transcript(video_id, target_lang=None):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang] if target_lang else [])
    except NoTranscriptFound:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = [transcript.language_code for transcript in transcript_list]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available_languages)

    text = " ".join([t['text'] for t in transcript])
    return text

def chat_gpt(prompt):
    try:
        response = openai.ChatCompletion.create(  # Updated to use openai
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Error processing your request."

def generate_article(transcript, detail_level="summary", target_lang=None):
    prompt = (
        f"You are a professional article author. Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on the following transcript:\n\n{transcript}"
    )
    if target_lang:
        prompt += f"\n\nWrite the article in {target_lang}."

    return chat_gpt(prompt)

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    video_input = data.get('video_id')
    detail_level = data.get('detail_level', 'summary')
    target_lang = data.get('target_lang', None)

    video_id = extract_video_id(video_input)
    transcript = get_transcript(video_id, target_lang)
    article = generate_article(transcript, detail_level, target_lang)

    return jsonify({"article": article})

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
