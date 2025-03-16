from sqlalchemy import create_engine, Column, Integer, String, Float, LargeBinary, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import hashlib
from PIL import Image
import io

# Create databases directory if it doesn't exist
db_dir = os.path.join(os.path.dirname(__file__), 'databases')
os.makedirs(db_dir, exist_ok=True)

# Update database path
db_path = os.path.join(db_dir, 'price_tool.db')
engine = create_engine(f'sqlite:///{db_path}')

# Initialize SQLAlchemy
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Website(Base):
    __tablename__ = 'websites'
    
    id = Column(Integer, primary_key=True)
    description = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    current_price = Column(Float)
    image_data = Column(LargeBinary)  # Store image binary data
    image_hash = Column(String)  # Store image hash for comparison
    last_updated = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Initialize the database, creating tables if they don't exist"""
    Base.metadata.create_all(engine)

def get_image_hash(image_data):
    """Generate hash for image data for comparison"""
    return hashlib.md5(image_data).hexdigest()

def process_image(image):
    """Process and resize image for storage"""
    # Convert to RGB if necessary
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        bg = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        bg.paste(image, mask=image.split()[3])
        image = bg
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize image to reasonable dimensions (e.g., max 800px width)
    max_size = 800
    if image.size[0] > max_size:
        ratio = max_size / image.size[0]
        new_size = (max_size, int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=85)
    return img_byte_arr.getvalue()

def add_or_update_website(url, description, price, image):
    """Add or update a website entry with image"""
    session = Session()
    try:
        # Process the image
        image_data = process_image(image)
        image_hash = get_image_hash(image_data)
        
        # Check if website exists
        website = session.query(Website).filter_by(url=url).first()
        
        if website:
            # Update existing website
            website.description = description
            website.current_price = price
            # Only update image if it's different
            if website.image_hash != image_hash:
                website.image_data = image_data
                website.image_hash = image_hash
            website.last_updated = datetime.utcnow()
        else:
            # Create new website entry
            website = Website(
                url=url,
                description=description,
                current_price=price,
                image_data=image_data,
                image_hash=image_hash
            )
            session.add(website)
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_website(url):
    """Retrieve website data by URL"""
    session = Session()
    try:
        return session.query(Website).filter_by(url=url).first()
    finally:
        session.close()

def get_all_websites():
    """Retrieve all website entries"""
    session = Session()
    try:
        return session.query(Website).all()
    finally:
        session.close()

def delete_website(url):
    """Delete a website entry"""
    session = Session()
    try:
        website = session.query(Website).filter_by(url=url).first()
        if website:
            session.delete(website)
            session.commit()
            return True
        return False
    finally:
        session.close()
