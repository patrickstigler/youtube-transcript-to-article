
# YouTube Transcript to Article

**YouTube Transcript to Article** is a Docker-based Python project that provides an API for converting YouTube transcripts into professional articles using OpenAI's ChatGPT. This tool automates the creation of summaries or detailed articles from YouTube video content, making it easy to generate professional write-ups from video transcripts.

## Features

- **Automatic Transcript Retrieval**: Fetches the transcript of a YouTube video in its original language, handling both video URLs and IDs.
- **Article Generation**: Generates a professional article from the transcript, with options for brief or detailed formats.
- **Customizable Output Language**: Allows you to specify the output language, with the default being the video's language.
- **Minimalist Web Interface**: Provides a simple, user-friendly web interface to easily input video IDs or URLs and generate articles.
- **Dockerized Deployment**: Easy deployment with Docker, including integration options for Home Assistant.

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

## Home Assistant Integration

To integrate with Home Assistant, add the following service to your `docker-compose.yml` or use a RESTful API configuration:

```yaml
version: '3'
services:
  youtube-transcript-to-article:
    image: youtube-transcript-to-article
    container_name: youtube_transcript_to_article
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "5000:5000"
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an issue.


