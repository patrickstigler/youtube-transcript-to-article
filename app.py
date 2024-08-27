import os
import re
from flask import Flask, request, jsonify, render_template
import openai
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

app = Flask(__name__)

# Initialize the OpenAI client with the API key from environment variable
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_video_id(url_or_id):
    """
    Extracts the video ID from a YouTube URL or returns the input if it's already an ID.
    """
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

def generate_article(transcript, detail_level="summary", target_lang=None):
    assistant = client.beta.assistants.create(
        name="Article Author",
        instructions="You are a professional article author. Generate a concise or detailed article based on the provided transcript.",
        model="gpt-4-1106-preview",
    )

    thread = client.beta.threads.create()

    message_content = f"Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on this transcript:\n\n{transcript}"
    if target_lang:
        message_content += f"\n\nWrite the article in {target_lang}."

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=message_content,
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        article_content = ""
        for message in messages:
            if message.content[0].type == "text":
                article_content += message.content[0].text.value + "\n"

        client.beta.assistants.delete(assistant.id)
        return article_content.strip()

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
