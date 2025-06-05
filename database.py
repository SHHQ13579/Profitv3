fimport os
import json
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import streamlit as st

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Handle SSL and connection pooling for PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"sslmode": "prefer"}
    )
else:
    raise ValueError("DATABASE_URL environment variable not found")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    salon_name = Column(String, default="My Salon")

class UserData(Base):
    __tablename__ = "user_data"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    data_type = Column(String)  # 'stylists', 'costs', 'settings', 'scenarios'
    data_json = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Scenario(Base):
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String)
    description = Column(Text)
    data_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def get_db_session():
    """Get a database session for direct use"""
    return SessionLocal()

def hash_password(password: str) -> str:
    """Hash a password for storing"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(username: str, email: str, password: str, salon_name: str = "My Salon"):
    """Create a new user"""
    db = get_db_session()
    
    try:
        # Check if user exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            return None, "Username or email already exists"
        
        # Create new user
        hashed_pw = hash_password(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_pw,
            salon_name=salon_name
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Initialize default data for new user
        initialize_user_data(user.id)
        
        return user, "User created successfully"
    
    except Exception as e:
        db.rollback()
        return None, f"Error creating user: {str(e)}"
    finally:
        db.close()

def authenticate_user(username: str, password: str):
    """Authenticate a user"""
    db = get_db_session()
    
    try:
        user = db.query(User).filter(User.username == username).first()
        
        if not user or not verify_password(password, user.hashed_password):
            return None
        
        return user
    except Exception as e:
        return None
    finally:
        db.close()

def initialize_user_data(user_id: int):
    """Initialize default data for a new user"""
    db = next(get_db())
    
    default_data = {
        'stylists': [{'name': 'Stylist 1', 'sales': 0, 'guarantee': 0}],
        'retail_percentage': 0.0,
        'trainees': [{'name': 'Trainee 1', 'wage': 0}],
        'receptionists': [{'name': 'Reception 1', 'wage': 0}],
        'fixed_costs': {
            'Rent': 0, 'Rates, Refuse & Bid': 0, 'Water & sewerage': 0,
            'R & R': 0, 'Utilities': 0, 'Telephone': 0, 'Insurance': 0,
            'Cleaning, laundry etc': 0, 'Card fees': 0, 'Stationery & printing': 0,
            'Advertising budget': 0, 'PR & promotions budget': 0, 'Sundries': 0,
            'Legal, prof & accountancy': 0, 'Bank charges': 0, 'Other 1': 0, 'Other 2': 0
        },
        'variable_costs_percentages': {
            'Wages/Salaries (excluding retail commission)': 0.0,
            'Retail Commission': 0.0, 'Professional Stock': 0.0,
            'Retail Stock': 0.0, 'Royalties/Franchise Fee': 0.0
        },
        'salary_settings': {
            'service_commission_percentage': 0.0, 'retail_commission_percentage': 0.0,
            'national_insurance_percentage': 0.0, 'pension_contribution_percentage': 0.0
        },
        'additional_income': {
            'Marketing Support': 0, 'Retro Payments': 0, 'Training Income': 0,
            'Rental Income': 0, 'Other 1': 0, 'Other 2': 0
        }
    }
    
    for data_type, data in default_data.items():
        user_data = UserData(
            user_id=user_id,
            data_type=data_type,
            data_json=json.dumps(data)
        )
        db.add(user_data)
    
    db.commit()

def save_user_data(user_id: int, data_type: str, data):
    """Save user data to database"""
    db = next(get_db())
    
    # Check if data exists
    existing_data = db.query(UserData).filter(
        UserData.user_id == user_id,
        UserData.data_type == data_type
    ).first()
    
    if existing_data:
        existing_data.data_json = json.dumps(data)
        existing_data.updated_at = datetime.utcnow()
    else:
        user_data = UserData(
            user_id=user_id,
            data_type=data_type,
            data_json=json.dumps(data)
        )
        db.add(user_data)
    
    db.commit()

def load_user_data(user_id: int, data_type: str):
    """Load user data from database"""
    db = next(get_db())
    user_data = db.query(UserData).filter(
        UserData.user_id == user_id,
        UserData.data_type == data_type
    ).first()
    
    if user_data:
        return json.loads(user_data.data_json)
    return None

def save_scenario(user_id: int, name: str, description: str, data):
    """Save a scenario for a user"""
    db = next(get_db())
    
    # Check if scenario exists (update) or create new
    existing_scenario = db.query(Scenario).filter(
        Scenario.user_id == user_id,
        Scenario.name == name
    ).first()
    
    if existing_scenario:
        existing_scenario.description = description
        existing_scenario.data_json = json.dumps(data)
        existing_scenario.updated_at = datetime.utcnow()
    else:
        # Check if user already has 3 scenarios
        scenario_count = db.query(Scenario).filter(Scenario.user_id == user_id).count()
        if scenario_count >= 3:
            return False, "Maximum 3 scenarios allowed"
        
        scenario = Scenario(
            user_id=user_id,
            name=name,
            description=description,
            data_json=json.dumps(data)
        )
        db.add(scenario)
    
    db.commit()
    return True, "Scenario saved successfully"

def load_scenarios(user_id: int):
    """Load all scenarios for a user"""
    db = next(get_db())
    scenarios = db.query(Scenario).filter(Scenario.user_id == user_id).all()
    
    result = {}
    for scenario in scenarios:
        result[scenario.name] = {
            'description': scenario.description,
            'timestamp': scenario.updated_at.strftime("%Y-%m-%d %H:%M"),
            **json.loads(scenario.data_json)
        }
    
    return result

def delete_scenario(user_id: int, name: str):
    """Delete a scenario for a user"""
    db = next(get_db())
    scenario = db.query(Scenario).filter(
        Scenario.user_id == user_id,
        Scenario.name == name
    ).first()
    
    if scenario:
        db.delete(scenario)
        db.commit()
        return True
    return False