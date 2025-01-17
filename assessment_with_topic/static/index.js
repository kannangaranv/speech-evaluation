let mediaRecorder;
let audioChunks = [];
let audioBlob;
let transcriptText = "";
let topic = "";
const controlButton = document.getElementById('controlButton');
const learnPronunciationButton = document.getElementById('learnPronunciationButton');
const transcriptField = document.getElementById('transcript');
const audioPlayer = document.getElementById('audioPlayer');
const scoresTable = document.querySelector('#scoresTable tbody');
const phonemeButton = document.getElementById('phonemeButton');
const phonemeDetails = document.querySelector('.phoneme-details');
const phonemeTable = document.getElementById('phonemeTable');
const reftext = document.getElementById('topic-area');
const topics = [
    "My Favorite Hobby",
    "Why I Love Reading",
    "The Best Day of My Life",
    "My Favorite Food",
    "A Fun Fact About Me",
    "Why I Enjoy Walking",
    "The Benefits of Drinking Water",
    "How I Start My Day",
    "Why Pets Are Great",
    "A Place I Want to Visit",
    "The Importance of Smiling",
    "Why I Like Listening to Music",
    "How I Relax After a Busy Day",
    "The Best Movie I've Seen",
    "A Simple Act of Kindness"
  ];

function changeTopic() {
const randomTopic = topics[Math.floor(Math.random() * topics.length)];
document.getElementById("topic-area").value = randomTopic;
}

controlButton.addEventListener('click', async () => {
    if (controlButton.textContent === 'Start Recording') {
        await startRecording();
    } else if (controlButton.textContent === 'Stop Recording') {
        stopRecording();
    } else if (controlButton.textContent === 'Refresh') {
        resetUI();
    }
});

async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = event => audioChunks.push(event.data);

    mediaRecorder.start();
    controlButton.textContent = 'Stop Recording';
}

function stopRecording() {
    mediaRecorder.stop();
    mediaRecorder.onstop = async () => {
        audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        audioPlayer.src = URL.createObjectURL(audioBlob);
        audioPlayer.load();

        const formData = new FormData();
        topic = reftext.value;

        formData.append('audio', audioBlob, 'audio.wav');
        formData.append('topic', topic);

        try {
            const response = await fetch('/ackaud', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                alert(`Error: ${response.status} - ${response.statusText}`);
                return;
            }

            ////////
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            let pronunciationResult = null;
            let ieltsBandScore = null;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true }).trim();

                try {
                    const parsedChunk = JSON.parse(chunk);

                    // Process whisper result as soon as it arrives
                    if (parsedChunk.whisper_result) {
                        transcriptText = parsedChunk.whisper_result.text;
                        transcriptField.textContent = transcriptText; // Update UI immediately
                    }

                    // Process pronunciation result and IELTS score
                    if (parsedChunk.pronunciation_result && parsedChunk.IELTS_band_score) {
                        pronunciationResult = parsedChunk.pronunciation_result; // Directly assign the object
                        ieltsBandScore = parsedChunk.IELTS_band_score;
                    }
                } catch (e) {
                    console.error('Error parsing chunk:', chunk, e);
                }
            }

            // Ensure pronunciation result is valid before proceeding
            if (!pronunciationResult || !pronunciationResult.NBest || pronunciationResult.NBest.length === 0) {
                alert('Pronunciation result does not contain a valid NBest array.');
                return;
            }

            const nBest = pronunciationResult.NBest[0];

            // Update the IELTS Band Score section
            const ieltsBandElement = document.getElementById('ieltsBand');
            ieltsBandElement.textContent = `IELTS Band Score: ${ieltsBandScore}`;

            scoresTable.innerHTML = 
                `<tr>
                    <td>${nBest.PronunciationAssessment.AccuracyScore}</td>
                    <td>${nBest.PronunciationAssessment.CompletenessScore}</td>
                    <td>${nBest.PronunciationAssessment.FluencyScore}</td>
                    <td>${nBest.PronunciationAssessment.ProsodyScore}</td>
                    <td>${nBest.PronunciationAssessment.PronScore.toFixed(1)}</td>
                </tr>`;

            populatePhonemeTable(nBest.Words);

            phonemeButton.style.display = 'inline-block';
            learnPronunciationButton.style.display = 'inline-block';

        } catch (error) {
            alert('Error: ' + error.message);
        }
    };
    controlButton.textContent = 'Refresh';
}

learnPronunciationButton.addEventListener('click', async () => {
    if (!transcriptText) {
        alert('No transcript available for pronunciation.');
        return;
    }

    const formData = new FormData();
    formData.append('reftext', transcriptText);

    try {
        const response = await fetch('/gettts', {
            method: 'POST',
            body: formData,
        });

        if (response.ok) {
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            audioPlayer.src = audioUrl;
            audioPlayer.load();
            audioPlayer.play();
        } else {
            alert('Failed to fetch the pronunciation audio.');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
});

function populatePhonemeTable(words) {
    let tableHTML = '<thead><tr><th>Word</th><th>Word Accuracy</th><th>Phoneme</th><th>Phoneme Accuracy</th></tr></thead><tbody>';

    words.forEach(word => {
        tableHTML += `<tr><td rowspan="${word.Phonemes.length + 1}">${word.Word}</td><td rowspan="${word.Phonemes.length + 1}">${word.PronunciationAssessment.AccuracyScore}</td></tr>`;
        word.Phonemes.forEach(phoneme => {
            tableHTML += `<tr><td>${phoneme.Phoneme}</td><td>${phoneme.PronunciationAssessment.AccuracyScore}</td></tr>`;
        });
    });

    tableHTML += '</tbody>';
    phonemeTable.innerHTML = tableHTML;
}

phonemeButton.addEventListener('click', () => {
    if (phonemeDetails.style.display === 'none') {
        phonemeDetails.style.display = 'block';
    } else {
        phonemeDetails.style.display = 'none';
    }
});

function resetUI() {
    transcriptText = '';
    //transcriptField.value = '';
    transcriptField.textContent = '';
    audioPlayer.src = '';
    scoresTable.innerHTML = '';
    phonemeTable.innerHTML = '';
    phonemeDetails.style.display = 'none';
    phonemeButton.style.display = 'none';
    learnPronunciationButton.style.display = 'none';
    controlButton.textContent = 'Start Recording';
    controlButton.disabled = false;
}
