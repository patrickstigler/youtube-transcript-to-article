
# YouTube Transcript to Article

**YouTube Transcript to Article** is a Docker-based Python project that provides an API for converting YouTube transcripts into professional articles using OpenAI's ChatGPT. This tool automates the creation of summaries or detailed articles from YouTube video content, making it easy to generate professional write-ups from video transcripts.

## Features

- **Automatic Transcript Retrieval**: Fetches the transcript of a YouTube video in its original language, handling both video URLs and IDs.
- **Article Generation**: Generates a professional article from the transcript, with options for brief or detailed formats.
- **Customizable Output Language**: Allows you to specify the output language, with the default being the video's language.
- **Minimalist Web Interface**: Provides a simple, user-friendly web interface to easily input video IDs or URLs and generate articles.
- **Dockerized Deployment**: Easy deployment with Docker, including integration options for Home Assistant and MQTT.

## MQTT Integration

The project includes support for MQTT, enabling integration with various IoT platforms like Home Assistant. This allows for automated processing of YouTube videos when a video link or ID is published to a specific MQTT topic.

### MQTT Features

- **Real-Time Processing**: Automatically processes YouTube video links or IDs when published to a subscribed MQTT topic.
- **Configurable Output**: Supports specifying `detail_level` (summary or detailed) and `target_lang` (output language) through MQTT.
- **Automatic Responses**: Publishes the generated article to a specified MQTT topic.
- **MQTT Authentication**: Supports username and password authentication for connecting to MQTT brokers.
- **Home Assistant Discovery**: Automatically registers availability and last processed message sensors in Home Assistant using MQTT Discovery.

### Environment Variables for MQTT

Ensure the following environment variables are set in your Docker setup:

- `MQTT_ACTIVE`: Set to `true` to enable MQTT functionality.
- `MQTT_BROKER`: The MQTT broker address (default: `localhost`).
- `MQTT_PORT`: The port for the MQTT broker (default: `1883`).
- `MQTT_USERNAME`: The username for MQTT authentication (optional).
- `MQTT_PASSWORD`: The password for MQTT authentication (optional).
- `MQTT_TOPIC_SUB`: The MQTT topic to subscribe to for incoming video links/IDs (default: `video/input`).
- `MQTT_TOPIC_PUB`: The MQTT topic to publish the generated articles to (default: `article/output`).
- `MQTT_CLIENT_ID`: A unique client ID for the MQTT connection.

### Example MQTT Payload

To trigger the processing of a video through MQTT, publish a JSON-formatted message to the subscribed topic (`MQTT_TOPIC_SUB`):

```json
{
  "video_id": "YOUR_YOUTUBE_VIDEO_URL_OR_ID",
  "detail_level": "summary", // Options: "summary", "detailed"
  "target_lang": "en" // Optional, specify if you want a different language
}
```

The generated article will be published to the `MQTT_TOPIC_PUB` topic.

### Home Assistant Integration

You can easily integrate this project with Home Assistant using MQTT Discovery, which automatically configures sensors in Home Assistant to monitor the service's availability and display the last processed video and article.

#### Home Assistant MQTT Discovery

When MQTT is enabled, the service will automatically register the following sensors in Home Assistant:

- **Service Availability**: A binary sensor that shows whether the service is online or offline.
- **Last Processed Message**: A sensor that displays the last processed video URL and the corresponding article.

### Docker Compose Example for Home Assistant Integration

If you are using `docker-compose`, here’s an example configuration for integrating this service with Home Assistant:

```yaml
version: '3'
services:
  youtube-transcript-to-article:
    image: patrickstigler/youtube-transcript-to-article
    container_name: youtube_transcript_to_article
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MQTT_ACTIVE=true
      - MQTT_BROKER=your_mqtt_broker_address
      - MQTT_PORT=1883
      - MQTT_USERNAME=your_mqtt_username
      - MQTT_PASSWORD=your_mqtt_password
      - MQTT_TOPIC_SUB=video/input
      - MQTT_TOPIC_PUB=article/output
      - MQTT_CLIENT_ID=youtube_article_generator
    ports:
      - "5000:5000"
```

## Docker Image and Installation

The Docker image for this project is available on Docker Hub:

- **Docker Hub:** `patrickstigler/youtube-transcript-to-article`

To pull and run the Docker image, use the following commands:

```bash
docker pull patrickstigler/youtube-transcript-to-article
docker run -p 5000:5000 patrickstigler/youtube-transcript-to-article
```

### unRAID Installation

This application is also available on unRAID as `youtube-transcript-to-article`. To install it on unRAID:

1. Open the unRAID web interface.
2. Navigate to the **Apps** tab.
3. Search for `youtube-transcript-to-article`.
4. Click **Install** and follow the prompts to set up the application.

## Prerequisites

- Docker installed on your system.
- OpenAI API key.

## Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/youtube-transcript-to-article.git
   cd youtube-transcript-to-article
   ```

2. **Set up your environment variables:**

   Ensure your OpenAI API key is set in your environment:

   ```bash
   export OPENAI_API_KEY=your_openai_api_key
   ```

3. **Build the Docker image:**

   ```bash
   docker build -t youtube-transcript-to-article .
   ```

4. **Run the Docker container:**

   ```bash
   docker run -p 5000:5000 youtube-transcript-to-article
   ```

## Usage

### API Endpoint

- **URL:** `http://localhost:5000/api/generate`
- **Method:** `POST`
- **Payload Example:**

  ```json
  {
    "video_id": "YOUR_YOUTUBE_VIDEO_URL_OR_ID",
    "detail_level": "summary", // Options: "summary", "detailed"
    "target_lang": "en" // Optional, specify if you want a different language
  }
  ```

- **Response Example:**

  ```json
  {
    "article": "Generated article text here..."
  }
  ```

### Web Interface

Access the minimalist web interface by navigating to `http://localhost:5000` in your browser. Here, you can input the YouTube video URL or ID, choose the detail level, and specify a target language if desired.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an issue.
