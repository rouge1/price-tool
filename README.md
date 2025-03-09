# Streamlit Ollama Vision App

This is a Streamlit application that connects to the Ollama Llama3.2-vision model for image processing with drag-and-drop capabilities.

## Prerequisites

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Make sure Ollama is running
3. Pull the Llama3.2-vision model:
   ```bash
   ollama pull llama3.2-vision
   ```

## Setup

1. Clone the repository or create a new project with the provided files
2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the App

Start the Streamlit app:
```bash
streamlit run app.py
```

The app will be available at http://localhost:8501 in your web browser.

## Usage

1. Drag and drop an image into the upload area or click to select an image
2. Enter a prompt about what you'd like the model to analyze in the image
3. Click "Process with Llama 3.2"
4. View the model's response on the right side of the interface

## Note

This application requires Ollama to be running locally. The default Ollama API endpoint is set to `http://localhost:11434/api/generate`. If your Ollama instance is running on a different address, update the `ollama_url` variable in the `query_ollama` function.