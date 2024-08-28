import os
import re
import json
from flask import Flask, request, jsonify, render_template
import openai  # Import OpenAI library
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound  # For fetching YouTube transcripts
import paho.mqtt.client as mqtt  # Import MQTT library

app = Flask(__name__)  # Initialize Flask application

# Initialize OpenAI client with the API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")  # Get OpenAI API key

# MQTT related environment variables
MQTT_ACTIVE = os.getenv("MQTT_ACTIVE", "false").lower() == "true"
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)  # MQTT username
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)  # MQTT password
MQTT_TOPIC_SUB = os.getenv("MQTT_TOPIC_SUB", "video/input")
MQTT_TOPIC_PUB = os.getenv("MQTT_TOPIC_PUB", "article/output")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "youtube_article_generator")

def extract_video_id(url_or_id):
    """
    Extracts the video ID from a YouTube URL or returns the input if it's already an ID.
    """
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id  # Return video ID

def get_transcript(video_id, target_lang=None):
    """
    Fetches the transcript for the given YouTube video ID.
    """
    try:
        # Try to fetch the transcript in the specified language
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang] if target_lang else [])
    except NoTranscriptFound:
        # If no transcript is found, list available transcripts and fetch one
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = [transcript.language_code for transcript in transcript_list]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available_languages)

    # Combine all text segments to create a complete transcript
    text = " ".join([t['text'] for t in transcript])
    return text  # Return transcript text

def chat_gpt(prompt):
    """
    Sends a prompt to the OpenAI Chat API and returns the response.
    """
    try:
        # Call the OpenAI API with the prompt
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Select model
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},  # Assistant context
                {"role": "user", "content": prompt}  # User prompt
            ]
        )
        return response['choices'][0]['message']['content'].strip()  # Return AI response
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")  # Print error
        return "Error processing your request."  # Return error message

def generate_article(transcript, detail_level="summary", target_lang=None):
    """
    Generates an article or summary based on the provided transcript.
    """
    prompt = (
        f"You are a professional article author. Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on the following transcript:\n\n{transcript}"
    )
    if target_lang:
        prompt += f"\n\nWrite the article in {target_lang}."  # Add language preference if provided

    return chat_gpt(prompt)  # Get generated article from chat_gpt function

@app.route('/api/generate', methods=['POST'])
def generate():
    """
    API endpoint for generating an article from a YouTube video transcript.
    """
    data = request.json  # Get JSON data from the request
    video_input = data.get('video_id')  # Extract video ID from input
    detail_level = data.get('detail_level', 'summary')  # Get detail level, default is 'summary'
    target_lang = data.get('target_lang', None)  # Get target language, if provided

    video_id = extract_video_id(video_input)  # Extract video ID
    transcript = get_transcript(video_id, target_lang)  # Fetch transcript for the video
    article = generate_article(transcript, detail_level, target_lang)  # Generate article

    return jsonify({"article": article})  # Return generated article as JSON

@app.route('/')
def home():
    """
    Renders the home page.
    """
    return render_template('index.html')  # Render index.html template

def on_connect(client, userdata, flags, rc):
    """
    Callback for when the client connects to the broker.
    """
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC_SUB)  # Subscribe to the input topic

def on_message(client, userdata, msg):
    """
    Callback for when a message is received on the subscribed topic.
    """
    try:
        data = json.loads(msg.payload.decode())  # Decode and parse the received message
        video_input = data.get('video_id')  # Extract video ID
        detail_level = data.get('detail_level', 'summary')  # Get detail level, default is 'summary'
        target_lang = data.get('target_lang', None)  # Get target language, if provided

        video_id = extract_video_id(video_input)  # Extract video ID
        transcript = get_transcript(video_id, target_lang)  # Fetch transcript
        article = generate_article(transcript, detail_level, target_lang)  # Generate article
        client.publish(MQTT_TOPIC_PUB, article)  # Publish the article to the output topic
    except Exception as e:
        error_message = f"Error processing message: {e}"
        print(error_message)
        client.publish(MQTT_TOPIC_PUB, error_message)  # Publish error message to the output topic

def setup_mqtt():
    """
    Set up MQTT client and Home Assistant discovery.
    """
    client = mqtt.Client(MQTT_CLIENT_ID)  # Create MQTT client
    client.on_connect = on_connect  # Assign on_connect callback
    client.on_message = on_message  # Assign on_message callback

    # Set MQTT username and password if provided
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Home Assistant MQTT Discovery
    discovery_topic = f"homeassistant/sensor/{MQTT_CLIENT_ID}/config"
    discovery_payload = {
        "name": "YouTube Article Generator",
        "state_topic": MQTT_TOPIC_PUB,
        "command_topic": MQTT_TOPIC_SUB,
        "device": {
            "identifiers": [MQTT_CLIENT_ID],
            "name": "YouTube Article Generator",
            "model": "Custom",
            "manufacturer": "Your Company"
        }
    }
    client.will_set(discovery_topic, payload=json.dumps(discovery_payload), qos=1, retain=True)

    client.connect(MQTT_BROKER, MQTT_PORT, 60)  # Connect to the MQTT broker
    client.loop_start()  # Start the MQTT loop

if __name__ == '__main__':
    if MQTT_ACTIVE:
        setup_mqtt()  # Set up MQTT if enabled
    app.run(host='0.0.0.0', port=5000)  # Run Flask app on all interfaces and port 5000
