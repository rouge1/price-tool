from sqlalchemy import create_engine, Column, Integer, String, Float, LargeBinary, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import os
import hashlib
import re
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

# Association table for many-to-many relationship between users and websites
user_website = Table(
    'user_website', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('website_id', Integer, ForeignKey('websites.id'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone_number = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    websites = relationship("Website", secondary=user_website, back_populates="users")
    alerts = relationship("Alert", back_populates="user")

class Website(Base):
    __tablename__ = 'websites'
    
    id = Column(Integer, primary_key=True)
    description = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    current_price = Column(Float)
    currency = Column(String, default='$')  # Store currency symbol
    image_data = Column(LargeBinary)  # Store image binary data
    image_hash = Column(String)  # Store image hash for comparison
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Update relationships with cascade delete
    price_history = relationship("PriceHistory", back_populates="website", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="website", cascade="all, delete-orphan")
    users = relationship("User", secondary=user_website, back_populates="websites")

class PriceHistory(Base):
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey('websites.id'), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String, default='$')  # Store currency symbol
    scraped_description = Column(String)
    raw_price_string = Column(String)  # Store the original price string
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    website = relationship("Website", back_populates="price_history")

class Alert(Base):
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    website_id = Column(Integer, ForeignKey('websites.id'), nullable=False)
    target_price = Column(Float, nullable=False)
    is_below_target = Column(Boolean, default=True)  # True if alert when price falls below target
    is_active = Column(Boolean, default=True)
    is_triggered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    triggered_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="alerts")
    website = relationship("Website", back_populates="alerts")

def init_db():
    """Initialize the database, creating tables if they don't exist"""
    Base.metadata.create_all(engine)

def extract_price_info(price_str):
    """
    Extract both the numeric price value and the currency symbol from a price string.
    
    Args:
        price_str (str): The price string (e.g., '$29.99' or '29,99 €')
        
    Returns:
        tuple: (price_float, currency_symbol, raw_price_string)
    """
    if price_str is None or price_str == 'not found':
        return None, '$', None
        
    if not isinstance(price_str, str):
        # If already a number, return it with default currency
        try:
            return float(price_str), '$', str(price_str)
        except (ValueError, TypeError):
            return None, '$', None
    
    # Save the original string
    raw_price = price_str.strip()
    
    # Extract currency symbol
    currency_symbols = {
        '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY', '₩': 'KRW',
        'руб': 'RUB', '₹': 'INR', 'R$': 'BRL', 'CHF': 'CHF', 'A$': 'AUD',
        'C$': 'CAD', 'HK$': 'HKD', '₴': 'UAH', '₽': 'RUB'
    }
    
    # Check for currency symbols at start or end
    currency = '$'  # Default
    
    # Try to extract currency symbol
    for symbol in sorted(currency_symbols.keys(), key=len, reverse=True):
        if symbol in price_str:
            currency = symbol
            break
            
    # Remove currency symbols and other non-numeric characters
    # Keep only digits, dots, and commas
    cleaned = ''.join(c for c in price_str if c.isdigit() or c in '.,')
    
    # Handle European number format (comma as decimal separator)
    if ',' in cleaned and '.' not in cleaned:
        cleaned = cleaned.replace(',', '.')
    elif ',' in cleaned and '.' in cleaned:
        # If both are present, assume comma is thousand separator
        cleaned = cleaned.replace(',', '')
    
    try:
        price_float = float(cleaned)
        return price_float, currency, raw_price
    except ValueError:
        return None, currency, raw_price

def record_price_update(website_id, price_str, scraped_description=None):
    """Record a new price point in the price history"""
    session = Session()
    try:
        # Update current price
        website = session.query(Website).get(website_id)
        if website:
            # Extract price and currency
            price_float, currency, raw_price = extract_price_info(price_str)
            
            website.current_price = price_float
            website.currency = currency
            website.last_updated = datetime.now(timezone.utc)
            
            # Add to price history
            history = PriceHistory(
                website_id=website_id,
                price=price_float,
                currency=currency,
                raw_price_string=raw_price,
                scraped_description=scraped_description
            )
            session.add(history)
            
            # Check for triggered alerts
            if price_float is not None:
                check_alerts(session, website_id, price_float)
            
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def create_alert(user_id, website_id, target_price, is_below_target=True):
    """Create a new price alert"""
    session = Session()
    try:
        alert = Alert(
            user_id=user_id,
            website_id=website_id,
            target_price=target_price,
            is_below_target=is_below_target
        )
        session.add(alert)
        session.commit()
        return alert.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def check_alerts(session, website_id, current_price):
    """Check if any alerts should be triggered for this website and price"""
    alerts = session.query(Alert).filter_by(
        website_id=website_id, 
        is_active=True, 
        is_triggered=False
    ).all()
    
    for alert in alerts:
        should_trigger = False
        
        if alert.is_below_target and current_price <= alert.target_price:
            should_trigger = True
        elif not alert.is_below_target and current_price >= alert.target_price:
            should_trigger = True
            
        if should_trigger:
            alert.is_triggered = True
            alert.triggered_at = datetime.now(timezone.utc)

def get_triggered_alerts():
    """Get all newly triggered alerts that need notification"""
    session = Session()
    try:
        return session.query(Alert).filter_by(
            is_triggered=True, 
            is_active=True
        ).all()
    finally:
        session.close()

def get_price_history(website_id, days=30):
    """Get price history for a website for the specified number of days"""
    session = Session()
    try:
        from sqlalchemy import desc
        from datetime import timedelta
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        return session.query(PriceHistory).filter(
            PriceHistory.website_id == website_id,
            PriceHistory.timestamp >= cutoff_date
        ).order_by(desc(PriceHistory.timestamp)).all()
    finally:
        session.close()

def get_user_websites(user_id):
    """Get all websites tracked by a specific user"""
    session = Session()
    try:
        user = session.query(User).get(user_id)
        if user:
            return user.websites
        return []
    finally:
        session.close()

def delete_website(url):
    """Delete a website and all its related data"""
    session = Session()
    try:
        website = session.query(Website).filter_by(url=url).first()
        if website:
            session.delete(website)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()