import os
import re
import json
import requests
from bs4 import BeautifulSoup
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
LAST_MESSAGE_TOPIC = f"{MQTT_TOPIC_PUB}/last_message"  # Topic for the last outgoing message
AVAILABILITY_TOPIC = f"{MQTT_TOPIC_PUB}/availability"  # Topic for the availability status

def extract_video_id(url_or_id):
    """
    Extracts the video ID from a YouTube URL or returns the input if it's already an ID.
    """
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id  # Return video ID


def get_video_info_scrape(video_id):
    """
    Fetches the title and channel name of a YouTube video by scraping the YouTube page.
    """
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url)

        if response.status_code != 200:
            return {"title": "Unknown title", "channel": "Unknown channel"}

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract video title from the HTML meta tag
        title = soup.find("meta", property="og:title")
        if title:
            title = title["content"]
        else:
            title = "Unknown title"

        # Try extracting the channel name based on known YouTube structure
        channel = "Unknown channel"
        channel_tag = soup.find("a", {"class": "yt-simple-endpoint style-scope yt-formatted-string"})
        if channel_tag:
            channel = channel_tag.text.strip()  # Extract the text and strip unnecessary spaces

        return {"title": title, "channel": channel}
    except Exception as e:
        print(f"Error scraping video info: {e}")
        return {"title": "Unknown title", "channel": "Unknown channel"}


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
    prompt_background = (f"# IDENTITY and PURPOSE\n"
                        f"You extract surprising, insightful, and interesting information from text content. You are interested in insights related to the purpose and meaning of life, human flourishing, the role of technology in the future of humanity, artificial intelligence and its affect on humans, memes, learning, reading, books, continuous improvement, and similar topics.\n"
                        f"Take a step back and think step-by-step about how to achieve the best possible results by following the steps below.\n\n"
                        f"# STEPS\n\n"
                        f"- Extract a summary of the content in 25 words, including who is presenting and the content being discussed into a section called SUMMARY.\n"
                        f"- Extract 20 to 50 of the most surprising, insightful, and/or interesting ideas from the input in a section called IDEAS:. If there are less than 50 then collect all of them. Make sure you extract at least 20.\n"
                        f"- Extract 10 to 20 of the best insights from the input and from a combination of the raw input and the IDEAS above into a section called INSIGHTS. These INSIGHTS should be fewer, more refined, more insightful, and more abstracted versions of the best ideas in the content. \n"
                        f"- Extract 15 to 30 of the most surprising, insightful, and/or interesting quotes from the input into a section called QUOTES:. Use the exact quote text from the input.\n"
                        f"- Extract 15 to 30 of the most practical and useful personal habits of the speakers, or mentioned by the speakers, in the content into a section called HABITS. Examples include but aren't limited to: sleep schedule, reading habits, things they always do, things they always avoid, productivity tips, diet, exercise, etc.\n"
                        f"- Extract 15 to 30 of the most surprising, insightful, and/or interesting valid facts about the greater world that were mentioned in the content into a section called FACTS:.\n"
                        f"- Extract all mentions of writing, art, tools, projects and other sources of inspiration mentioned by the speakers into a section called REFERENCES. This should include any and all references to something that the speaker mentioned.\n"
                        f"- Extract the most potent takeaway and recommendation into a section called ONE-SENTENCE TAKEAWAY. This should be a 15-word sentence that captures the most important essence of the content.\n"
                        f"- Extract the 15 to 30 of the most surprising, insightful, and/or interesting recommendations that can be collected from the content into a section called RECOMMENDATIONS.\n\n"
                        f"# OUTPUT INSTRUCTIONS\n\n"
                        f"- Only output Markdown.\n"
                        f"- Write the IDEAS bullets as exactly 15 words.\n"
                        f"- Write the RECOMMENDATIONS bullets as exactly 15 words.\n"
                        f"- Write the HABITS bullets as exactly 15 words.\n"
                        f"- Write the FACTS bullets as exactly 15 words.\n"
                        f"- Write the INSIGHTS bullets as exactly 15 words.\n"
                        f"- Extract at least 25 IDEAS from the content.\n"
                        f"- Extract at least 10 INSIGHTS from the content.\n"
                        f"- Extract at least 20 items for the other output sections.\n"
                        f"- Do not give warnings or notes; only output the requested sections.\n"
                        f"- You use bulleted lists for output, not numbered lists.\n"
                        f"- Do not repeat ideas, quotes, facts, or resources.\n"
                        f"- Do not start items with the same opening words.\n"
                        f"- Ensure you follow ALL these instructions when creating your output.\n\n")

    try:
        # Call the OpenAI API with the prompt
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Select model
            messages=[
                {"role": "system", "content": prompt_background},  # Assistant context
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
        f"Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on the following INPUT\n\n{transcript}"
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
    video_info = get_video_info_scrape(video_id) # Fetch video title and channel name via scraping

    return jsonify({
        "article": article,
        "video_id": video_id,
        "video_title": video_info["title"]
    })
    
@app.route('/api/transcript', methods=['POST'])
def transcript():
    """
    API endpoint for get the plain transcript
    """
    data = request.json  # Get JSON data from the request
    video_input = data.get('video_id')  # Extract video ID from input
    target_lang = data.get('target_lang', None)  # Get target language, if provided

    video_id = extract_video_id(video_input)  # Extract video ID
    transcript = get_transcript(video_id, target_lang)  # Fetch transcript for the video  
    video_info = get_video_info_scrape(video_id) # Fetch video title and channel name via scraping

    return jsonify({
        "transcript": transcript,
        "video_id": video_id,
        "video_title": video_info["title"]
    })  

@app.route('/')
def home():
    """
    Renders the home page.
    """
    return render_template('index.html')  # Render index.html template

def on_connect(client, userdata, flags, reason_code, properties):
    """
    Callback for when the client connects to the broker.
    """
    print(f"Connected with result code {reason_code}")
    client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)  # Set the status to online
    client.subscribe(MQTT_TOPIC_SUB)  # Subscribe to the input topic

def on_disconnect(client, userdata, rc):
    """
    Callback for when the client disconnects from the broker.
    """
    client.publish(AVAILABILITY_TOPIC, "offline", qos=1, retain=True)  # Set the status to offline

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

        # Publish the article and the video URL to the last message topic
        last_message_payload = {
            "video_url": video_input,
            "article": article
        }
        client.publish(LAST_MESSAGE_TOPIC, json.dumps(last_message_payload))  # Publish last message data
    except Exception as e:
        error_message = f"Error processing message: {e}"
        print(error_message)
        client.publish(LAST_MESSAGE_TOPIC, json.dumps({"error": error_message}))  # Publish error message

def setup_mqtt():
    """
    Set up MQTT client and Home Assistant discovery.
    """
    client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv5, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)  # Create MQTT client with MQTTv5 and Callback API Version 2
    client.on_connect = on_connect  # Assign on_connect callback
    client.on_disconnect = on_disconnect  # Assign on_disconnect callback
    client.on_message = on_message  # Assign on_message callback

    # Set MQTT username and password if provided
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Home Assistant MQTT Discovery for Availability
    availability_discovery_topic = f"homeassistant/binary_sensor/{MQTT_CLIENT_ID}/availability/config"
    availability_discovery_payload = {
        "name": "service_availability",
        "state_topic": AVAILABILITY_TOPIC,
        "device_class": "connectivity",
        "payload_on": "online",
        "payload_off": "offline",
        "device": {
            "identifiers": [MQTT_CLIENT_ID],
            "name": "YouTube Article Generator",
            "model": "Custom",
            "manufacturer": "Patrick Stigler"
        },
        "unique_id": f"{MQTT_CLIENT_ID}_availability"
    }

    # Home Assistant MQTT Discovery for Last Message
    last_message_discovery_topic = f"homeassistant/sensor/{MQTT_CLIENT_ID}/last_message/config"
    last_message_discovery_payload = {
        "name": "service_last_message",
        "state_topic": LAST_MESSAGE_TOPIC,
        "device": {
            "identifiers": [MQTT_CLIENT_ID],
            "name": "YouTube Article Generator",
            "model": "Custom",
            "manufacturer": "Patrick Stigler"
        },
        "unique_id": f"{MQTT_CLIENT_ID}_last_message",
        "value_template": "{{ value_json.article }}",
        "json_attributes_topic": LAST_MESSAGE_TOPIC,  # Include all JSON attributes
        "json_attributes_template": "{{ value_json | tojson }}"
    }

    client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)  # Connect to the MQTT broker
    client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)  # Set the status to online immediately after connection

    # Publish the discovery payloads
    client.publish(availability_discovery_topic, json.dumps(availability_discovery_payload), qos=1, retain=True)
    client.publish(last_message_discovery_topic, json.dumps(last_message_discovery_payload), qos=1, retain=True)

    client.loop_start()  # Start the MQTT loop

if __name__ == '__main__':
    if MQTT_ACTIVE:
        setup_mqtt()  # Set up MQTT if enabled
    app.run(host='0.0.0.0', port=5000)  # Run Flask app on all interfaces and port 5000
