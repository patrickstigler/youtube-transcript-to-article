import os
import re
from flask import Flask, request, jsonify, render_template
import openai  # Import OpenAI library for API calls
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound  # Import for fetching YouTube transcripts

app = Flask(__name__)  # Initialize Flask application

# Initialize the OpenAI client with the API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")  # Get the OpenAI API key from environment variables

def extract_video_id(url_or_id):
    """
    Extracts the video ID from a YouTube URL or returns the input if it's already an ID.
    """
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id  # Return the extracted video ID

def get_transcript(video_id, target_lang=None):
    """
    Fetches the transcript for a given YouTube video ID.
    """
    try:
        # Try to get the transcript in the specified language
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang] if target_lang else [])
    except NoTranscriptFound:
        # If no transcript found, list available transcripts and fetch one
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = [transcript.language_code for transcript in transcript_list]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available_languages)

    # Join all text segments to form a complete transcript
    text = " ".join([t['text'] for t in transcript])
    return text  # Return the transcript text

def chat_gpt(prompt):
    """
    Sends a prompt to the OpenAI Chat API and returns the response.
    """
    try:
        # Call the OpenAI API with the prompt
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content'].strip()  # Return the AI's response
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")  # Print any errors that occur
        return "Error processing your request."  # Return an error message

def generate_article(transcript, detail_level="summary", target_lang=None):
    """
    Generates an article or summary based on the provided transcript.
    """
    prompt = (
        f"You are a professional article author. Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on the following transcript:\n\n{transcript}"
    )
    if target_lang:
        prompt += f"\n\nWrite the article in {target_lang}."  # Add language instruction if provided

    return chat_gpt(prompt)  # Get the generated article from the chat_gpt function

@app.route('/api/generate', methods=['POST'])
def generate():
    """
    API endpoint to generate an article from a YouTube video transcript.
    """
    data = request.json  # Get JSON data from the request
    video_input = data.get('video_id')  # Extract video ID from the input
    detail_level = data.get('detail_level', 'summary')  # Get detail level, default to 'summary'
    target_lang = data.get('target_lang', None)  # Get target language, if specified

    video_id = extract_video_id(video_input)  # Extract the video ID
    transcript = get_transcript(video_id, target_lang)  # Get the transcript for the video
    article = generate_article(transcript, detail_level, target_lang)  # Generate the article

    return jsonify({"article": article})  # Return the generated article as JSON

@app.route('/')
def home():
    """
    Renders the home page.
    """
    return render_template('index.html')  # Render the index.html template

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # Run the Flask app on all interfaces at port 5000
