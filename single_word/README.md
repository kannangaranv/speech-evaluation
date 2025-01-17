# Pronunciation Assessment Module

This project provides an automatic pronunciation assessment module that evaluates the accuracy of spoken language by comparing user speech with a pronunciation model. It uses speech-to-text and natural language processing techniques to score pronunciation quality.

## Features

- **Automatic Pronunciation Evaluation**: Analyzes the pronunciation accuracy of user input speech.
- **API Integrations**: Uses external APIs like OpenAI and Whisper for transcription, speech recognition and grammar evaluation.

## Setup Instructions

Follow these steps to set up and run the project on your local machine.

### Prerequisites

Before running the module, you will need to have API keys for the following services:

- **Subscription Key** for the pronunciation assessment API
- **OpenAI API Key**
- **Whisper API Key** (for speech recognition)

You can obtain these keys by registering on their respective platforms:

- [Microsoft Azure Cognitive Services](https://azure.microsoft.com/en-us/services/cognitive-services/)
- [OpenAI API](https://platform.openai.com/)
- [Whisper API](https://github.com/openai/whisper)

### Step 1: Clone the repository

Clone this repository to your local machine:

```bash
git clone https://github.com/pesalaG/Automatic-speech-evaluation.git
cd Automatic-speech-evaluation
```

### Step 2: Install dependencies

create a Python virtual environment and install the necessary dependencies from the ```requirements.txt ```

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### Step 3: Set up the environment variables

Create a ```.env``` file in the root directory of the project with the following content:

```ini
SUBSCRIPTION_KEY=your_subscription_key
OPENAI_API=your_openai_api_key
WHISPER_API_KEY=your_whisper_api_key

```

Replace the placeholder values ```(your_Azure_STT_subscription_key, your_openai_api_key, your_whisper_api_key)``` with your actual API credentials

### Step 4: Run the Application

After setting up the environment and installing the dependencies, you can run the application:

```bash
python application.py
```

### Project Structure
Here’s an overview of the project directory:

```
/Automatic-speech-evaluation
│
├── static/                # Static files like JavaScript
│   └── index.js
│
├── template/              # HTML templates
│   └── index.html
│
├── requirements.txt       # List of Python dependencies
├── application.py         # Main application file
├── .env                   # Sensitive environment variables

```








