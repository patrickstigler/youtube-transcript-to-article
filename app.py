import os
import re
import json
from flask import Flask, request, jsonify, render_template
import openai  # Import OpenAI library
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound  # For fetching YouTube transcripts
import paho.mqtt.client as mqtt  # Import MQTT library
import emoji  # To clean emojis

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

# Function to clean and format the video title (remove emojis and special characters)
def clean_title(title):
    title = emoji.replace_emoji(title, replace='')  # Remove emojis
    title = re.sub(r'[^\w\s\-]', '', title)  # Remove non-alphanumeric characters
    return title.strip()

# Function to save the video article as a Markdown file
def save_article_as_markdown(video_info, article, output_folder):
    # Extract the YouTuber's name and clean it
    youtuber_name = clean_title(video_info.get('channel_name', 'Unknown_Youtuber'))
    
    # Create a folder for the YouTuber if it doesn't exist
    youtuber_folder = os.path.join(output_folder, youtuber_name)
    if not os.path.exists(youtuber_folder):
        os.makedirs(youtuber_folder)
    
    # Clean the video title for a valid file name
    video_title = clean_title(video_info.get('video_title', 'Unknown_Video'))
    
    # Create the file path for the Markdown file
    markdown_file_path = os.path.join(youtuber_folder, f"{video_title}.md")
    
    # Prepare the content for the Markdown file
    markdown_content = f"""
# {video_info.get('video_title', 'No Title')}
**Uploader:** {video_info.get('channel_name', 'Unknown Channel')}
**Video-ID:** {video_info.get('video_id', 'Unknown ID')}
**Veröffentlicht am:** {video_info.get('publish_date', 'Unknown Date')}

**Artikel:**

{article}
    """
    
    # Write the content to the Markdown file
    with open(markdown_file_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"Markdown file saved: {markdown_file_path}")

# Function to extract the video ID from a URL or ID
def extract_video_id(url_or_id):
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id

# Function to fetch the transcript of a YouTube video
def get_transcript(video_id, target_lang=None):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang] if target_lang else [])
    except NoTranscriptFound:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = [transcript.language_code for transcript in transcript_list]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available_languages)

    text = " ".join([t['text'] for t in transcript])
    return text

# Function to interact with OpenAI API to generate an article
def chat_gpt(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Error processing your request."

# Function to generate an article or summary based on the transcript
def generate_article(transcript, detail_level="summary", target_lang=None):
    prompt = (
        f"You are a professional article author. Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on the following transcript:\n\n{transcript}"
    )
    if target_lang:
        prompt += f"\n\nWrite the article in {target_lang}."
    return chat_gpt(prompt)

# API endpoint to generate an article
@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    video_input = data.get('video_id')
    detail_level = data.get('detail_level', 'summary')
    target_lang = data.get('target_lang', None)
    
    video_id = extract_video_id(video_input)
    transcript = get_transcript(video_id, target_lang)
    article = generate_article(transcript, detail_level, target_lang)

    # Additional information about the video for Markdown generation
    video_info = {
        "video_title": data.get('video_title', 'Unknown_Video'),
        "channel_name": data.get('channel_name', 'Unknown_Channel'),
        "video_id": video_id,
        "publish_date": data.get('publish_date', 'Unknown Date'),
        "description": data.get('description', 'Keine Beschreibung')
    }

    # Save the generated article as a Markdown file
    output_folder = os.getenv('OUTPUT_FOLDER', './output')  # Default output folder
    save_article_as_markdown(video_info, article, output_folder)

    # Return the generated article as JSON
    return jsonify({"article": article})

# Function to handle MQTT messages
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        video_input = data.get('video_id')
        detail_level = data.get('detail_level', 'summary')
        target_lang = data.get('target_lang', None)

        video_id = extract_video_id(video_input)
        transcript = get_transcript(video_id, target_lang)
        article = generate_article(transcript, detail_level, target_lang)

        # Additional information for Markdown
        video_info = {
            "video_title": data.get('video_title', 'Unknown_Video'),
            "channel_name": data.get('channel_name', 'Unknown_Channel'),
            "video_id": video_id,
            "publish_date": data.get('publish_date', 'Unknown Date'),
            "description": data.get('description', 'Keine Beschreibung')
        }

        # Save the article to a Markdown file
        output_folder = os.getenv('OUTPUT_FOLDER', './output')
        save_article_as_markdown(video_info, article, output_folder)

        client.publish(MQTT_TOPIC_PUB, article)

        last_message_payload = {
            "video_url": video_input,
            "article": article
        }
        client.publish(LAST_MESSAGE_TOPIC, json.dumps(last_message_payload))
    except Exception as e:
        error_message = f"Error processing message: {e}"
        client.publish(LAST_MESSAGE_TOPIC, json.dumps({"error": error_message}))

# MQTT setup and connection functions...

if __name__ == '__main__':
    if MQTT_ACTIVE:
        setup_mqtt()
    app.run(host='0.0.0.0', port=5000)
