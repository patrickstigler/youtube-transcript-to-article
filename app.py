from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import openai
import os
import re

app = Flask(__name__)

# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_video_id(url_or_id):
    """
    Extracts the video ID from a YouTube URL or returns the input if it's already an ID.
    """
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id

def get_transcript(video_id, target_lang=None):
    try:
        # Try to get the transcript in the target language or default to available languages
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang] if target_lang else [])
    except NoTranscriptFound:
        # If the preferred language transcript is not found, fall back to available languages
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = [transcript.language_code for transcript in transcript_list]
        
        # Select the first available language if no preferred language is found
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available_languages)

    # Join all the pieces of transcript text
    text = " ".join([t['text'] for t in transcript])
    return text

def generate_article(transcript, detail_level="summary", target_lang=None):
    prompt = f"Write a {'detailed' if detail_level == 'detailed' else 'brief'} professional article based on this transcript:\n\n{transcript}"
    
    if target_lang:
        prompt += f"\n\nWrite the article in {target_lang}."
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500 if detail_level == "summary" else 1500,
        temperature=0.7
    )
    return response['choices'][0]['message']['content'].strip()

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    video_input = data.get('video_id')
    detail_level = data.get('detail_level', 'summary')
    target_lang = data.get('target_lang', None)
    
    # Extract video ID from input
    video_id = extract_video_id(video_input)
    
    transcript = get_transcript(video_id, target_lang)
    article = generate_article(transcript, detail_level, target_lang)
    
    return jsonify({"article": article})

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
