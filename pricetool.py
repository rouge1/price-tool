#!/usr/bin/env python3
from quart import Quart, render_template, request, jsonify
from PIL import Image
from apps.database import init_db, add_or_update_website, get_all_websites, delete_website
from apps.ollama import process_image
from apps.browser_service import BrowserService
import base64
import io
import logging
import json

app = Quart(__name__)
init_db()

# Configure logging - only show WARNING and above
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize browser service
browser_service = BrowserService()

@app.template_filter('b64encode')
def b64encode_filter(data):
    if data is None:
        return None
    return base64.b64encode(data).decode()

@app.route('/')
async def index():
    websites = get_all_websites()
    return await render_template('index.html', 
                         title="Modern Price Tool",
                         websites=websites)

@app.route('/add-item', methods=['POST'])
async def add_item():
    try:
        data = await request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        url = data.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Invalid URL format. URL must start with http:// or https://'}), 400

        try:
            screenshot_bytes = await browser_service.get_screenshot(url)
            screenshot = Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            app.logger.error(f"Screenshot error: {str(e)}")
            return jsonify({'error': 'Failed to capture screenshot'}), 500

        ai_question = """Analyze the image and respond exclusively with a JSON object containing the following keys:
                'description': A brief description of the item in the image, or 'not found' if unavailable.
                'price': The item's price in the image, or 'not found' if unavailable.

                Do not include any additional text outside the JSON object."""

        ollama_response = process_image(
            image=screenshot,
            prompt=ai_question,
            stream=False
        )
        
        app.logger.debug(f"Ollama Response: {ollama_response}")
        
        # Parse JSON from the content string
        try:
            content = ollama_response["message"]["content"]
            app.logger.debug(f"\nContent: {content}")
            
            description = content["message"]["content"]["description"]
            price_str = content["message"]["content"]["price"]
            
            app.logger.debug(f"Description: {description}")
            app.logger.debug(f"Price: {price_str}")
            
            # add_or_update_website(
            #     url=url,
            #     description=description if description != 'not found' else url,
            #     price=0.0,
            #     image=screenshot
            # )
            
            # return jsonify({'success': True, 'message': 'Item added successfully'})
            
        except json.JSONDecodeError as e:
            app.logger.error(f"Failed to parse JSON response: {e}")
            return jsonify({'error': 'Failed to parse AI response'}), 500

    except Exception as e:
        app.logger.error(f"Error adding item: {str(e)}")
        return jsonify({'error': f'Error adding item: {str(e)}'}), 500

@app.route('/delete-item', methods=['POST'])
async def delete_item():
    try:
        data = await request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
            
        url = data['url']
        if delete_website(url):
            return jsonify({'success': True, 'message': 'Item deleted successfully'})
        else:
            return jsonify({'error': 'Item not found'}), 404
            
    except Exception as e:
        app.logger.error(f"Error deleting item: {str(e)}")
        return jsonify({'error': f'Error deleting item: {str(e)}'}), 500

@app.before_serving
async def startup():
    await browser_service.init_browser()

@app.after_serving
async def shutdown():
    await browser_service.cleanup()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)