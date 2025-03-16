import ollama
import os
import tempfile
from PIL import Image

def process_image(image, prompt, stream=False):
    """Process image with Ollama's Python library
    
    Args:
        image: PIL Image object
        prompt: Text prompt to send with the image
        stream: Whether to stream the response (True) or get complete response (False)
    """
    # Convert image to RGB if necessary (handles PNG with alpha channel)
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        bg = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        bg.paste(image, mask=image.split()[3])
        image = bg
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    # Save image to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
        temp_filename = temp_file.name
        image.save(temp_filename, 'JPEG', quality=95)
    
    try:
        # Use the Ollama Python library to send request with stream parameter
        response = ollama.chat(
            model='llama3.2-vision',
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [temp_filename]
            }],
            stream=stream,
            options={'temperature': 0.3}    
        )
        
        # Clean up temporary file
        os.unlink(temp_filename)
        
        return response
    except Exception as e:
        # Clean up temporary file even if there's an error
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        return {"error": str(e)}
