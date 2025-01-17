import requests
import base64
import json
import time
import random
import azure.cognitiveservices.speech as speechsdk
from io import BytesIO
from pydub import AudioSegment
from openai import AzureOpenAI
from flask import Flask, jsonify, render_template, request, make_response
from flask import Flask, request, jsonify, stream_with_context, Response
from dotenv import load_dotenv 
import os
import uuid
app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

subscription_key = os.getenv('SUBSCRIPTION_KEY')
openai_api = os.getenv('OPENAI_API')
whisper_api_key = os.getenv('WHISPER_API_KEY')
region = "southeastasia"
language = "en-US"
voice = "Microsoft Server Speech Text to Speech Voice (en-US, JennyNeural)"
whisper_url = "https://enfluent-eastus2.openai.azure.com/openai/deployments/enfluent-whisper/audio/translations?api-version=2024-06-01"

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/gettoken", methods=["POST"])
def gettoken():
    fetch_token_url = 'https://%s.api.cognitive.microsoft.com/sts/v1.0/issueToken' %region
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key
    }
    response = requests.post(fetch_token_url, headers=headers)
    access_token = response.text
    return jsonify({"at":access_token})

# Predefined topics
topics = [
    "My Favorite Hobby",
    "Why I Love Reading",
    "The Best Day of My Life",
    "My Favorite Food"
]

@app.route("/get-topic", methods=["GET"])
def get_topic():
    topic = random.choice(topics)
    return jsonify({"topic": topic})

@app.route("/ackaud", methods=["POST"])
def ackaud():
    f = request.files['audio']
    audio_stream = BytesIO(f.read())

    # Whisper API Request using the in-memory file
    whisper_response = requests.post(
        url=whisper_url,
        files={"file": ("audio_wh.wav", audio_stream, f.content_type)},
        headers={"api-key": whisper_api_key}
    )
    
    if whisper_response.status_code != 200:
        print(f"Whisper API Error: {whisper_response.status_code} - {whisper_response.text}")
        return {"error": "Whisper API transcription failed"}, 500
    whisper_result = whisper_response.json()
    referenceText = whisper_result.get("text", "")
    print(referenceText)
    audio_stream.seek(0)
    #referenceText = "wake up to reality. nothing goes as planned"
    # Convert the uploaded file to WAV format with PCM encoding and 16kHz sample rate for pronunciation assessment
    try:
        # Load the audio file into a pydub AudioSegment
        audio_pron = AudioSegment.from_file(audio_stream)
        audio_pron = audio_pron.set_frame_rate(16000).set_channels(1).set_sample_width(2)

        # Export the audio as WAV to an in-memory file
        wav_buffer = BytesIO()
        audio_pron.export(wav_buffer, format="wav")
        wav_buffer.seek(0)
    except Exception as e:
        return {"error": f"Audio conversion failed: {str(e)}"}, 500
    

    def generate_response(whisper_result, wav_buffer, referenceText):
    # Send transcript immediately
        whisper_data = {"whisper_result": whisper_result}
        yield f"{json.dumps(whisper_data)}\n"

        # Process other assessments asynchronously
        response_pronun, pronunScore = get_pronun_score(wav_buffer, referenceText)
        ielts_band_score = get_ielts_band_score(pronunScore, referenceText)

        other_results = {
            "pronunciation_result": response_pronun,
            "IELTS_band_score": ielts_band_score,
        }
        yield f"{json.dumps(other_results)}\n"
    
    f.close()

    return Response(
        stream_with_context(generate_response(whisper_result, wav_buffer, referenceText)),
        content_type="text/event-stream"  # Correct MIME type for streamed responses
    )


def get_pronun_score(wav_buffer, referenceText):
    try: 
        # Azure Speech SDK configuration
        speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
                # Create a PushAudioInputStream to push the WAV data to the Azure SDK
        push_stream = speechsdk.audio.PushAudioInputStream()

        # Push the data from the BytesIO buffer to the PushAudioInputStream
        push_stream.write(wav_buffer.read())
        push_stream.close()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        enable_miscue = False
        enable_prosody_assessment = True

        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=referenceText,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=enable_miscue
        )
        if enable_prosody_assessment:
            pronunciation_config.enable_prosody_assessment()

        # Create Speech Recognizer and apply pronunciation assessment configuration
        language = 'en-US'
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, language=language, audio_config=audio_config)
        pronunciation_config.apply_to(speech_recognizer)

        # Perform recognition
        speech_recognition_result = speech_recognizer.recognize_once()

        # Extract pronunciation assessment result
        pronunciation_assessment_result_json = speech_recognition_result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        
        if pronunciation_assessment_result_json:
            pronunciation_assessment_result_json = json.loads(pronunciation_assessment_result_json)
            #pronunciation_assessment_result_json = pronunciation_assessment_result_json.json()
            print(type(pronunciation_assessment_result_json))
            print({"pronunciation_result": pronunciation_assessment_result_json})
            pronunScore = pronunciation_assessment_result_json["NBest"][0]["PronunciationAssessment"]["PronScore"]
            print(pronunScore)

            return pronunciation_assessment_result_json, pronunScore
        else:
            return jsonify({"error": "No pronunciation assessment result found."}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500





def get_ielts_band_score(pronunScore, referenceText):
    # Define the system message once
    system_message = """
    You are a IELTS speaking test examiner. 
    """

    # Prepare the dynamic user input
    user_message = f"""
    I need you to evaluate the IELTS band score for the whole speech based on the grammar and lexical resources
    aspect of the following speech transcript:

    {referenceText}

    And following pronunciation score out of 100, as evaluated by experts, is:

    {pronunScore}
    and output only the single value of the IELTS band score. follows possible output values and assessment criteria
    0.0 -  does not attend(only no submission)
    1.0 -  no communication possible, no ratable language, pronunciation score < 20
    2.0 -  only produces isolated words or memorised utterances, cannot produce basic sentence forms, 10< pronunciation score <40
    3.0 -  uses simple vocabulary to convey personal information, has insufficient vocabulary for less familiar topics, ttempts basic sentence forms but with limited success, or relies on apparently memorised utterances, makes numerous errors except in memorized expressions,  10< pronunciation score <60
    4.0 -  is able to talk about familiar topics but can only convey basic meaning on unfamiliar topics and makes frequent errors in word choice, rarely attempts paraphrase,  produces basic sentence forms and some correct simple sentences but subordinate structures are rare, errors are frequent and may lead to misunderstanding, 15< pronunciation score <70
    5.0 - manages to talk about familiar and unfamiliar topics but uses vocabulary with limited flexibility, attempts to use paraphrase but with mixed success , produces basic sentence forms with reasonable accuracy, uses a limited range of more complex structures, but these usually contain errors and may cause some comprehension problems ,20< pronunciation score <75 
    6.0 -uses a mix of simple and complex structures, but with limited flexibility, may make frequent mistakes with complex structures, though these rarely cause comprehension problems ,20< pronunciation score <85
    7.0 -uses vocabulary resource flexibly to discuss a variety of topics, uses some less common and idiomatic vocabulary and shows some awareness of style and collocation, with some inappropriate choices, uses paraphrase effectively ,uses a range of complex structures with some flexibility, frequently produces error free sentences, though some grammatical mistakes persist,  50< pronunciation score <95
    8.0 - uses a wide vocabulary resource readily and flexibly to convey precise meaning, uses less common and idiomatic vocabulary skilfully, with occasional inaccuracies, uses paraphrase effectively as required,uses a wide range of structures flexibly, produces a majority of errorfree sentences with only very occasional inappropriacies or basic/nonsystematic errors  , 65< pronunciation score <95
    9.0 - uses vocabulary with full flexibility and precision in all topics, uses idiomatic language naturally and accurately, uses a full range of structures naturally and appropriately, produces consistently accurate structures apart from ‘slips’ characteristic of native speaker speech , 85< pronunciation score <100
    """

    # Initialize the Azure OpenAI client
    client = AzureOpenAI(
        azure_endpoint="https://enfluent-eastus2.openai.azure.com/",  # Your Azure OpenAI endpoint
        api_key=openai_api,  # Your Azure OpenAI API key
        api_version="2023-03-15-preview"
    )

    # Sending a request to the Azure OpenAI API to evaluate grammar and lexical resources
    response = client.chat.completions.create(
        model="enfluent-gpt-4o",  # Use the correct model deployed on your Azure environment
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    )

    # Extract the IELTS band score from the response
    ielts_band_score = response.choices[0].message.content.strip()
    print("IELTS Band Score:", ielts_band_score)
    return ielts_band_score


    # print(whisper_result)
    # print(response_pronun)





@app.route("/gettts", methods=["POST"])
def gettts():
    reftext = request.form.get("reftext")
    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
    speech_config.speech_synthesis_voice_name = voice

    offsets=[]

    def wordbound(evt):
        offsets.append( evt.audio_offset / 10000)

    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    speech_synthesizer.synthesis_word_boundary.connect(wordbound)

    result = speech_synthesizer.speak_text_async(reftext).get()
    # Check result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        #print("Speech synthesized for text [{}]".format(reftext))
        #print(offsets)
        audio_data = result.audio_data
        #print(audio_data)
        #print("{} bytes of audio data received.".format(len(audio_data)))
        
        response = make_response(audio_data)
        response.headers['Content-Type'] = 'audio/wav'
        response.headers['Content-Disposition'] = 'attachment; filename=sound.wav'
        # response.headers['reftext'] = reftext
        response.headers['offsets'] = offsets
        return response
        
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))
        return jsonify({"success":False})

@app.route("/getttsforword", methods=["POST"])
def getttsforword():
    word = request.form.get("word")

    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
    speech_config.speech_synthesis_voice_name = voice

    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    result = speech_synthesizer.speak_text_async(word).get()
    # Check result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:

        audio_data = result.audio_data
        response = make_response(audio_data)
        response.headers['Content-Type'] = 'audio/wav'
        response.headers['Content-Disposition'] = 'attachment; filename=sound.wav'
        # response.headers['word'] = word
        return response
        
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))
        return jsonify({"success":False})

if __name__ == "__main__":
    app.run(debug=True)