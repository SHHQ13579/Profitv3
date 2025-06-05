import streamlit as st
from database import create_user, authenticate_user, load_user_data, save_user_data

def login_form():
    """Display login form"""
    st.subheader("Login to Your Salon Profit Planner")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username and password:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.user_id = user.id
                    st.session_state.username = user.username
                    st.session_state.salon_name = user.salon_name
                    st.session_state.authenticated = True
                    st.success(f"Welcome back, {user.username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Please enter both username and password")

def registration_form():
    """Display registration form"""
    st.subheader("Create Your Account")
    
    with st.form("registration_form"):
        username = st.text_input("Choose a Username")
        email = st.text_input("Email Address")
        salon_name = st.text_input("Salon Name", value="My Salon")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Create Account")
        
        if submit:
            if not all([username, email, salon_name, password, confirm_password]):
                st.error("Please fill in all fields")
            elif password != confirm_password:
                st.error("Passwords don't match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                user, message = create_user(username, email, password, salon_name)
                if user:
                    st.success("Account created successfully! Please login.")
                    st.session_state.show_login = True
                    st.rerun()
                else:
                    st.error(message)

def authentication_page():
    """Main authentication page"""
    # Header with logo on the right
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("Salon Profit Planner")
        st.markdown("### Professional financial planning for salon owners")
    with col2:
        try:
            st.image("attached_assets/HANNA Logo.png", width=150)
        except:
            pass
    
    # Initialize session state
    if 'show_login' not in st.session_state:
        st.session_state.show_login = True
    
    # Create tabs for login and registration
    if st.session_state.show_login:
        login_form()
        st.markdown("---")
        if st.button("Don't have an account? Sign up here"):
            st.session_state.show_login = False
            st.rerun()
    else:
        registration_form()
        st.markdown("---")
        if st.button("Already have an account? Login here"):
            st.session_state.show_login = True
            st.rerun()

def logout():
    """Logout user and clear session"""
    for key in ['user_id', 'username', 'salon_name', 'authenticated']:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear all user data from session
    data_keys = ['stylists', 'retail_percentage', 'trainees', 'receptionists', 
                 'fixed_costs', 'variable_costs_percentages', 'salary_settings', 
                 'additional_income', 'scenarios']
    for key in data_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

def load_user_session_data():
    """Load user's data into session state"""
    if 'user_id' not in st.session_state:
        return
    
    user_id = st.session_state.user_id
    
    # Load each data type
    data_types = {
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
    
    for data_type, default_value in data_types.items():
        if data_type not in st.session_state:
            loaded_data = load_user_data(user_id, data_type)
            st.session_state[data_type] = loaded_data if loaded_data is not None else default_value

def save_user_session_data():
    """Save current session data to database"""
    if 'user_id' not in st.session_state:
        return
    
    user_id = st.session_state.user_id
    
    # Save each data type
    data_types = ['stylists', 'retail_percentage', 'trainees', 'receptionists',
                  'fixed_costs', 'variable_costs_percentages', 'salary_settings', 
                  'additional_income']
    
    for data_type in data_types:
        if data_type in st.session_state:
            save_user_data(user_id, data_type, st.session_state[data_type])

def require_authentication(func):
    """Decorator to require authentication"""
    def wrapper(*args, **kwargs):
        if 'authenticated' not in st.session_state or not st.session_state.authenticated:
            authentication_page()
            return
        return func(*args, **kwargs)
    return wrapper