import os
import re
from flask import Flask, request, jsonify, render_template
import openai  # OpenAI-Bibliothek importieren
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound  # Für das Abrufen von YouTube-Transkripten

app = Flask(__name__)  # Flask-Anwendung initialisieren

# OpenAI-Client mit dem API-Schlüssel aus der Umgebungsvariable initialisieren
openai.api_key = os.getenv("OPENAI_API_KEY")  # API-Schlüssel von OpenAI erhalten

def extract_video_id(url_or_id):
    """
    Extrahiert die Video-ID aus einer YouTube-URL oder gibt die Eingabe zurück, wenn es sich bereits um eine ID handelt.
    """
    video_id_match = re.match(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url_or_id)
    return video_id_match.group(1) if video_id_match else url_or_id  # Video-ID zurückgeben

def get_transcript(video_id, target_lang=None):
    """
    Ruft das Transkript für die angegebene YouTube-Video-ID ab.
    """
    try:
        # Versuchen, das Transkript in der angegebenen Sprache abzurufen
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang] if target_lang else [])
    except NoTranscriptFound:
        # Wenn kein Transkript gefunden wird, verfügbare Transkripte auflisten und eines abrufen
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = [transcript.language_code for transcript in transcript_list]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available_languages)

    # Alle Textsegmente zusammenfügen, um ein vollständiges Transkript zu erstellen
    text = " ".join([t['text'] for t in transcript])
    return text  # Transkripttext zurückgeben

def chat_gpt(prompt):
    """
    Sendet einen Prompt an die OpenAI Chat API und gibt die Antwort zurück.
    """
    try:
        # OpenAI API mit dem Prompt aufrufen
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Modell auswählen
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},  # Kontext für den Assistenten
                {"role": "user", "content": prompt}  # Benutzeranfrage
            ]
        )
        return response['choices'][0]['message']['content'].strip()  # AI-Antwort zurückgeben
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")  # Fehler ausgeben
        return "Error processing your request."  # Fehlermeldung zurückgeben

def generate_article(transcript, detail_level="summary", target_lang=None):
    """
    Generiert einen Artikel oder eine Zusammenfassung basierend auf dem bereitgestellten Transkript.
    """
    prompt = (
        f"You are a professional article author. Write a {'detailed professional article' if detail_level == 'detailed' else 'brief summary'} based on the following transcript:\n\n{transcript}"
    )
    if target_lang:
        prompt += f"\n\nWrite the article in {target_lang}."  # Sprachvorgabe hinzufügen, wenn angegeben

    return chat_gpt(prompt)  # Generierten Artikel von der chat_gpt-Funktion abrufen

@app.route('/api/generate', methods=['POST'])
def generate():
    """
    API-Endpunkt zum Generieren eines Artikels aus einem YouTube-Video-Transkript.
    """
    data = request.json  # JSON-Daten aus der Anfrage abrufen
    video_input = data.get('video_id')  # Video-ID aus der Eingabe extrahieren
    detail_level = data.get('detail_level', 'summary')  # Detailgrad abrufen, standardmäßig 'summary'
    target_lang = data.get('target_lang', None)  # Zielsprache abrufen, falls angegeben

    video_id = extract_video_id(video_input)  # Video-ID extrahieren
    transcript = get_transcript(video_id, target_lang)  # Transkript für das Video abrufen
    article = generate_article(transcript, detail_level, target_lang)  # Artikel generieren

    return jsonify({"article": article})  # Generierten Artikel als JSON zurückgeben

@app.route('/')
def home():
    """
    Rendert die Startseite.
    """
    return render_template('index.html')  # index.html-Vorlage rendern

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # Flask-App auf allen Schnittstellen und Port 5000 ausführen
