import requests
import base64
import json
import time
import random
import azure.cognitiveservices.speech as speechsdk
from io import BytesIO
from pydub import AudioSegment
from azure.cognitiveservices.speech.audio import AudioInputStream
from openai import AzureOpenAI
from flask import Flask, jsonify, render_template, request, make_response
from dotenv import load_dotenv 
import os

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



# @app.route("/ackaud", methods=["POST"])
# def ackaud():
#     f = request.files['audio']
#     referenceText = request.form.get("transcript")
#     print(f"Reference Text: {referenceText}")
#     audio_stream = BytesIO(f.read())

#     # Convert uploaded audio to WAV format (PCM encoding, 16kHz sample rate)
#     try:
#         audio_pron = AudioSegment.from_file(audio_stream)
#         audio_pron = audio_pron.set_frame_rate(16000).set_channels(1).set_sample_width(2)

#         # Export audio as WAV to an in-memory file
#         wav_buffer = BytesIO()
#         audio_pron.export(wav_buffer, format="wav")
#         wav_buffer.seek(0)
#     except Exception as e:
#         return {"error": f"Audio conversion failed: {str(e)}"}, 500

#     # Build pronunciation assessment parameters
#     pronAssessmentParamsJson = json.dumps({
#         "ReferenceText": referenceText,
#         "GradingSystem": "HundredMark",
#         "Dimension": "Comprehensive",
#         "EnableMiscue": True,
#         "EnableProsodyAssessment": True
#     })
#     pronAssessmentParamsBase64 = base64.b64encode(pronAssessmentParamsJson.encode('utf-8'))
#     pronAssessmentParams = pronAssessmentParamsBase64.decode("utf-8")

#     # Build the API request URL and headers
#     pronun_url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={language}&usePipelineVersion=0"
#     headers_pronun = {
#         'Accept': 'application/json;text/xml',
#         'Connection': 'Keep-Alive',
#         'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000',
#         'Ocp-Apim-Subscription-Key': subscription_key,
#         'Pronunciation-Assessment': pronAssessmentParams,
#         'Transfer-Encoding': 'chunked',
#         'Expect': '100-continue'
#     }

#     # Stream audio chunks for pronunciation assessment
#     def get_chunk(audio_source, chunk_size=1024):
#         while True:
#             chunk = audio_source.read(chunk_size)
#             if not chunk:
#                 break
#             yield chunk

#     response_pronun = requests.post(url=pronun_url, data=get_chunk(wav_buffer), headers=headers_pronun)
#     if response_pronun.status_code != 200:
#         print(f"Pronunciation API Error: {response_pronun.status_code} - {response_pronun.text}")
#         return {"error": f"Pronunciation API call failed with status {response_pronun.status_code}"}, 500

#     # Parse API response
#     try:
#         response_pronun = response_pronun.json()
#         print(response_pronun)
#         pronunScore = response_pronun["NBest"][0].get("PronScore", None)
#         fluencyScore = response_pronun["NBest"][0].get("FluencyScore", None)
#         print(f"Pronunciation Score: {pronunScore}, Fluency Score: {fluencyScore}")
#     except KeyError as e:
#         return {"error": f"Unexpected API response format: {str(e)}"}, 500

#     return {
#         "pronunciation_result": response_pronun
#     }
    
# # Use an in-memory stream for audio input

@app.route("/ackaud", methods=["POST"])
def ackaud():
    try:
        f = request.files['audio']  # Get the uploaded audio file
        referenceText = request.form.get("transcript")  # Get the reference text for pronunciation assessment
        if not referenceText:
            return jsonify({"error": "Reference text is required."}), 400

        # Read and process the audio file into an in-memory WAV file
        audio_stream = BytesIO(f.read())

        # Convert uploaded audio to WAV format (PCM encoding, 16kHz sample rate)
        try:
            audio_pron = AudioSegment.from_file(audio_stream)
            audio_pron = audio_pron.set_frame_rate(16000).set_channels(1).set_sample_width(2)

            # Export audio as WAV to an in-memory file
            wav_buffer = BytesIO()
            audio_pron.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
        except Exception as e:
            return jsonify({"error": f"Audio conversion failed: {str(e)}"}), 500
        
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
            print({"pronunciation_result": pronunciation_assessment_result_json})
            return {"pronunciation_result": pronunciation_assessment_result_json}
        else:
            return jsonify({"error": "No pronunciation assessment result found."}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500



@app.route("/gettts", methods=["POST"])
def gettts():
    reftext = request.form.get("transcript")
    print(reftext)
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
        #print("{} bytes of audio data received.".format(len(audio_data))
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
    word = request.form.get("transcript")

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