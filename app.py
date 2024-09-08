def on_connect(client, userdata, flags, reason_code, properties=None):
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
