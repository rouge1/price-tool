import streamlit as st
import ollama
import base64
from PIL import Image
import io
import os
import tempfile

st.set_page_config(
    page_title="Llama 3.2 Vision with Ollama",
    page_icon="🦙",
    layout="wide"
)

def process_image(image, prompt):
    """Process image with Ollama's Python library"""
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
        # Use the Ollama Python library to send request
        response = ollama.chat(
            model='llama3.2-vision',
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [temp_filename]
            }]
        )
        
        # Clean up temporary file
        os.unlink(temp_filename)
        
        return response
    except Exception as e:
        # Clean up temporary file even if there's an error
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        return {"error": str(e)}

def main():
    st.title("🦙 Llama 3.2 Vision with Ollama")
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("Upload Image")
        
        # Drag and drop image upload
        uploaded_file = st.file_uploader("Choose an image...", 
            type=["jpg", "jpeg", "png", "bmp", "webp", "tiff"])
        
        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)
            
            # Get prompt from user
            prompt = st.text_area("Enter your prompt:", 
                                 value="What's in this image? Describe it in detail.")
            
            # Process button
            process_button = st.button("Process with Llama 3.2")
            
            if process_button:
                with st.spinner("Processing image with Llama 3.2..."):
                    # Process with Ollama
                    with col2:
                        st.header("Model Response")
                        response = process_image(image, prompt)
                        
                        if isinstance(response, dict) and "error" in response:
                            st.error(f"Error: {response['error']}")
                        else:
                            # Display the response message
                            st.markdown(response['message']['content'])
                            
                            # Display additional info if available
                            with st.expander("Response Details"):
                                st.json({
                                    "model": response.get("model", ""),
                                    "created_at": response.get("created_at", ""),
                                    "role": response['message'].get("role", ""),
                                    "total_duration": response.get("total_duration", ""),
                                    "eval_count": response.get("eval_count", ""),
                                    "prompt_eval_count": response.get("prompt_eval_count", "")
                                })

if __name__ == "__main__":
    main()