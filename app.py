import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import xlsxwriter
import json
import os
from datetime import datetime
from utils import format_currency
from auth import authentication_page, require_authentication, load_user_session_data, save_user_session_data, logout
from database import save_scenario, load_scenarios, delete_scenario

# Page configuration
st.set_page_config(
    page_title="Salon Profit Planner",
    page_icon="✂️",
    layout="wide"
)

# Check authentication first
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    authentication_page()
    st.stop()

# Load user data into session
load_user_session_data()

# Initialize undo system
if 'undo_stack' not in st.session_state:
    st.session_state.undo_stack = []

def save_state_for_undo():
    """Save current state for undo functionality"""
    import copy
    current_state = {
        'stylists': copy.deepcopy(st.session_state.stylists),
        'retail_percentage': st.session_state.retail_percentage,
        'fixed_costs': copy.deepcopy(st.session_state.fixed_costs),
        'variable_costs_percentages': copy.deepcopy(st.session_state.variable_costs_percentages),
        'salary_settings': copy.deepcopy(st.session_state.salary_settings),
        'trainees': copy.deepcopy(st.session_state.trainees),
        'receptionists': copy.deepcopy(st.session_state.receptionists)
    }
    
    # Keep only last 10 states to avoid memory issues
    if len(st.session_state.undo_stack) >= 10:
        st.session_state.undo_stack.pop(0)
    
    st.session_state.undo_stack.append(current_state)

def undo_last_change():
    """Restore the previous state"""
    if st.session_state.undo_stack:
        previous_state = st.session_state.undo_stack.pop()
        
        # Restore all session state variables
        st.session_state.stylists = previous_state['stylists']
        st.session_state.retail_percentage = previous_state['retail_percentage']
        st.session_state.fixed_costs = previous_state['fixed_costs']
        st.session_state.variable_costs_percentages = previous_state['variable_costs_percentages']
        st.session_state.salary_settings = previous_state['salary_settings']
        st.session_state.trainees = previous_state['trainees']
        st.session_state.receptionists = previous_state['receptionists']
        
        return True
    return False

# Initialize session state variables if they don't exist
if 'stylists' not in st.session_state:
    st.session_state.stylists = [{'name': 'Stylist 1', 'sales': 0, 'guarantee': 0}]

if 'retail_percentage' not in st.session_state:
    st.session_state.retail_percentage = 0.0

if 'fixed_costs' not in st.session_state:
    st.session_state.fixed_costs = {
        'Rent': 0,
        'Rates, Refuse & Bid': 0,
        'Water & sewerage': 0,
        'R & R': 0,
        'Utilities': 0,
        'Telephone': 0,
        'Insurance': 0,
        'Cleaning, laundry etc': 0,
        'Card fees': 0,
        'Stationery & printing': 0,
        'Advertising budget': 0,
        'PR & promotions budget': 0,
        'Sundries': 0,
        'Legal, prof & accountancy': 0,
        'Bank charges': 0,
        'Other 1': 0,
        'Other 2': 0
    }

# Note about costs:
# - Team & Sales page: All sales figures are WEEKLY
# - Salaries page: All calculations are WEEKLY
# - Costs page: All costs are MONTHLY (weekly values * 52/12)
# - To convert weekly to monthly: multiply by 52/12 (approx 4.33)

if 'variable_costs_percentages' not in st.session_state:
    st.session_state.variable_costs_percentages = {
        'Wages/Salaries (excluding retail commission)': 0.0,
        'Retail Commission': 0.0,
        'Professional Stock': 0.0,
        'Retail Stock': 0.0,
        'Royalties/Franchise Fee': 0.0
    }

# Initialize salary settings if they don't exist
if 'salary_settings' not in st.session_state:
    st.session_state.salary_settings = {
        'service_commission_percentage': 0.0,
        'retail_commission_percentage': 0.0,
        'national_insurance_percentage': 0.0,
        'pension_contribution_percentage': 0.0
    }

# Initialize trainees if they don't exist
if 'trainees' not in st.session_state:
    st.session_state.trainees = [{'name': 'Trainee 1', 'wage': 0}]

# Initialize receptionists if they don't exist
if 'receptionists' not in st.session_state:
    st.session_state.receptionists = [{'name': 'Reception 1', 'wage': 0}]

# Initialize additional income if it doesn't exist
if 'additional_income' not in st.session_state:
    st.session_state.additional_income = {
        'Marketing Support': 0,
        'Retro Payments': 0,
        'Training Income': 0,
        'Rental Income': 0,
        'Other 1': 0,
        'Other 2': 0
    }
    
# Functions for scenario persistence - works in both standalone and embedded modes
def save_scenarios_to_file():
    """Save scenarios using multiple methods for different environments"""
    try:
        # Always try to save to file system (works in standalone mode)
        with open('scenarios.json', 'w') as f:
            json.dump(st.session_state.scenarios, f, indent=2, default=str)
    except:
        # Silently handle file system errors when embedded
        pass

def load_scenarios_from_file():
    """Load scenarios from file system"""
    try:
        if os.path.exists('scenarios.json'):
            with open('scenarios.json', 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

# Enhanced scenario management for embedded environments
def get_embedded_storage_key(scenario_name):
    """Generate a unique key for scenario storage"""
    return f"salon_scenario_{scenario_name.replace(' ', '_')}"

def save_scenario_to_session_cache(scenario_name, scenario_data):
    """Save individual scenario to session cache for embedded mode"""
    cache_key = get_embedded_storage_key(scenario_name)
    if 'scenario_cache' not in st.session_state:
        st.session_state.scenario_cache = {}
    st.session_state.scenario_cache[cache_key] = scenario_data

def load_scenario_from_session_cache(scenario_name):
    """Load individual scenario from session cache"""
    cache_key = get_embedded_storage_key(scenario_name)
    if 'scenario_cache' not in st.session_state:
        st.session_state.scenario_cache = {}
    return st.session_state.scenario_cache.get(cache_key, None)

# Initialize scenarios with database-backed multi-user support
if 'scenarios_loaded' not in st.session_state:
    st.session_state.scenarios_loaded = True
    user_id = st.session_state.get('user_id')
    if user_id:
        st.session_state.scenarios = load_scenarios(user_id)
    else:
        st.session_state.scenarios = {}

# Ensure scenarios exist in session state
if 'scenarios' not in st.session_state:
    st.session_state.scenarios = {}
    
# Current scenario name
if 'current_scenario_name' not in st.session_state:
    st.session_state.current_scenario_name = "Current Plan"

# Create a nice header layout with columns - logo on the right
header_col1, header_col2, header_col3, header_col4 = st.columns([2, 1, 0.5, 1])

# Column 1: Title only - compact layout
with header_col1:
    st.title("Salon Profit Planner")

# Column 2: User info and menu
with header_col2:
    username = st.session_state.get('username', 'User')
    st.write(f"**{username}**")
    
    # Three dots menu with logout
    with st.popover("⋮", use_container_width=False):
        if st.button("Logout", key="logout_menu_btn", use_container_width=True):
            logout()

# Column 3: Undo button - just symbol
with header_col3:
    undo_available = len(st.session_state.undo_stack) > 0
    if st.button("↶", key="undo_btn", disabled=not undo_available, help="Undo last change"):
        if undo_last_change():
            st.success("Last change undone!")
            st.rerun()
        else:
            st.error("No changes to undo")

# Column 4: Logo on the right
with header_col4:
    # Use a container to apply styling
    with st.container():
        # Add a bit of padding at the top to align with the title
        st.write("")
        # Display the logo at an appropriate size
        st.image("assets/hanna_logo.png", width=120)

# Remove separator for tighter layout

# Function to recalculate values when changes are made
def calculate_core_values():
    # Note: Stylist sales are weekly figures, but we work in monthly values for overall calculations
    # First, calculate the weekly values
    weekly_service_sales = sum(stylist['sales'] for stylist in st.session_state.stylists)
    
    # Calculate weekly retail sales as percentage of weekly service sales
    retail_percentage = st.session_state.retail_percentage
    weekly_retail_sales = weekly_service_sales * (retail_percentage / 100)
    
    # Calculate weekly total sales
    weekly_total_sales = weekly_service_sales + weekly_retail_sales
    
    # Convert weekly values to monthly for the Costs page calculations
    weekly_to_monthly = 52/12  # More accurate weeks per month
    
    # Monthly values
    total_service_sales = weekly_service_sales * weekly_to_monthly  # Monthly service sales
    retail_sales = weekly_retail_sales * weekly_to_monthly  # Monthly retail sales
    
    # Additional monthly income (not from services/retail)
    total_additional_income = sum(st.session_state.additional_income.values())
    
    # Calculate total monthly sales including additional income
    monthly_service_retail_sales = weekly_total_sales * weekly_to_monthly  # Monthly sales from services and retail
    total_sales = monthly_service_retail_sales + total_additional_income  # Total monthly sales including additional income
    
    # Calculate fixed costs (already monthly)
    total_fixed_costs = sum(st.session_state.fixed_costs.values())
    
    # Calculate variable costs
    variable_costs = {}
    total_variable_costs = 0
    
    # Get salary settings for calculations
    salary_settings = st.session_state.salary_settings
    service_commission_percentage = salary_settings['service_commission_percentage']
    retail_commission_percentage = salary_settings['retail_commission_percentage']
    national_insurance_percentage = salary_settings['national_insurance_percentage']
    pension_contribution_percentage = salary_settings['pension_contribution_percentage']
    
    # Calculate weekly retail sales
    retail_sales_weekly = retail_sales / weekly_to_monthly
    
    # Calculate total salary costs - working with weekly values
    total_weekly_salary_cost = 0
    total_weekly_retail_commission = 0
    
    # Stylists salary calculations
    stylist_weekly_salary_cost = 0
    for stylist in st.session_state.stylists:
        # Weekly sales figures
        weekly_stylist_sales = stylist['sales']
        
        # Service commission calculation - weekly
        service_commission_amount = weekly_stylist_sales * (service_commission_percentage / 100)
        
        # Individual retail sales based on proportion of service sales - weekly
        if weekly_service_sales > 0:
            proportion_of_sales = weekly_stylist_sales / weekly_service_sales
            stylist_retail_sales_weekly = retail_sales_weekly * proportion_of_sales
        else:
            stylist_retail_sales_weekly = 0
            
        retail_commission_amount = stylist_retail_sales_weekly * (retail_commission_percentage / 100)
        
        # Determine final salary (higher of stylist's guarantee or service commission, plus retail commission) - weekly
        stylist_guarantee = stylist['guarantee']
        service_earnings = max(stylist_guarantee, service_commission_amount)
        total_earnings = service_earnings + retail_commission_amount
        
        stylist_weekly_salary_cost += total_earnings
        total_weekly_retail_commission += retail_commission_amount
    
    # Trainees salary calculations
    trainee_weekly_salary_cost = 0
    for trainee in st.session_state.trainees:
        trainee_weekly_salary_cost += trainee['wage']
    
    # Receptionists salary calculations
    receptionist_weekly_salary_cost = 0
    for receptionist in st.session_state.receptionists:
        receptionist_weekly_salary_cost += receptionist['wage']
    
    # Total weekly salary cost combines stylists, trainees, and receptionists
    total_weekly_salary_cost = stylist_weekly_salary_cost + trainee_weekly_salary_cost + receptionist_weekly_salary_cost
    
    # Calculate additional costs from NI and pension
    national_insurance_cost = total_weekly_salary_cost * (national_insurance_percentage / 100)
    pension_contribution_cost = total_weekly_salary_cost * (pension_contribution_percentage / 100)
    total_additional_costs = national_insurance_cost + pension_contribution_cost
    grand_total_weekly_cost = total_weekly_salary_cost + total_additional_costs
    
    # Convert weekly salary costs to monthly for variable costs and profit calculations
    total_salary_cost = grand_total_weekly_cost * weekly_to_monthly  # Use the total including NI and pension
    monthly_retail_commission = total_weekly_retail_commission * weekly_to_monthly
    
    # Update variable costs percentages based on calculated salary costs
    if total_sales > 0:
        st.session_state.variable_costs_percentages['Wages/Salaries (excluding retail commission)'] = (total_salary_cost - monthly_retail_commission) / total_sales * 100
    if retail_sales > 0:
        st.session_state.variable_costs_percentages['Retail Commission'] = monthly_retail_commission / retail_sales * 100
    
    # Calculate all variable costs with updated percentages
    for cost_name, percentage in st.session_state.variable_costs_percentages.items():
        if cost_name == "Retail Commission" or cost_name == "Retail Stock":
            base_value = retail_sales  # Monthly retail sales
        elif cost_name == "Professional Stock":
            base_value = total_service_sales  # Monthly service sales
        else:
            base_value = total_sales  # Monthly total sales
        
        cost_value = base_value * (percentage / 100)
        variable_costs[cost_name] = cost_value
        total_variable_costs += cost_value
    
    # Calculate profit (monthly)
    profit = total_sales - total_fixed_costs - total_variable_costs
    profit_margin = (profit / total_sales * 100) if total_sales > 0 else 0
    
    return {
        # Weekly values
        'weekly_service_sales': weekly_service_sales,  # Weekly service sales
        'weekly_retail_sales': weekly_retail_sales,    # Weekly retail sales
        'weekly_total_sales': weekly_total_sales,      # Weekly total sales
        'weekly_salary_cost': total_weekly_salary_cost,  # Weekly base salary (before NI and pension)
        'weekly_stylist_salary_cost': stylist_weekly_salary_cost,  # Weekly stylist cost 
        'weekly_trainee_salary_cost': trainee_weekly_salary_cost,  # Weekly trainee cost
        'weekly_receptionist_salary_cost': receptionist_weekly_salary_cost,  # Weekly receptionist cost
        'weekly_retail_commission': total_weekly_retail_commission,  # Weekly
        'weekly_ni_cost': national_insurance_cost,  # Weekly NI cost
        'weekly_pension_cost': pension_contribution_cost,  # Weekly pension cost
        'weekly_total_salary_cost': grand_total_weekly_cost,  # Weekly total including NI and pension
        
        # Monthly values (weekly * 52/12)
        'total_service_sales': total_service_sales,  # Monthly service sales
        'retail_sales': retail_sales,  # Monthly retail sales
        'monthly_service_retail_sales': monthly_service_retail_sales,  # Monthly sales from services and retail
        'total_additional_income': total_additional_income,  # Additional monthly income
        'total_sales': total_sales,  # Total monthly sales including additional income
        'total_fixed_costs': total_fixed_costs,  # Monthly
        'total_variable_costs': total_variable_costs,  # Monthly
        'profit': profit,  # Monthly
        'profit_margin': profit_margin,  # Percentage
        'variable_costs': variable_costs,  # Monthly breakdown
        'total_salary_cost': total_salary_cost,  # Monthly including NI and pension
        'monthly_retail_commission': monthly_retail_commission,  # Monthly
        'total_wage_cost_percentage': (total_salary_cost / total_sales * 100) if total_sales > 0 else 0  # Total wage cost as percentage of total sales
    }

# Function to handle stylist sales changes
def update_stylist_sales(i, new_value):
    # Save state before making changes
    save_state_for_undo()
    # Update the stylist sales
    st.session_state.stylists[i]['sales'] = new_value
    
    # Rerun to update calculations
    st.rerun()

# Function to handle retail percentage changes
def update_retail_percentage(new_value):
    # Save state before making changes
    save_state_for_undo()
    st.session_state.retail_percentage = new_value
    st.rerun()

# Calculate values to use throughout the app
core_values = calculate_core_values()

# Use the Streamlit sidebar for the profit potential box which is always visible
with st.sidebar:
    st.markdown("### Current Profit Potential")
    
    # Make the metrics more compact
    st.metric("Total Monthly Revenue", format_currency(core_values['total_sales']))
    st.metric("Total Monthly Costs", format_currency(core_values['total_fixed_costs'] + core_values['total_variable_costs']))
    st.metric("Monthly Profit", format_currency(core_values['profit']))
    
    # Calculate annual profit (monthly profit × 12)
    annual_profit = core_values['profit'] * 12
    st.metric("Annual Profit", format_currency(annual_profit))
    st.metric("Profit Margin", f"{core_values['profit_margin']:.1f}%")
    
    # Add total wage cost as percentage of total sales
    st.metric("Total Wage %", f"{core_values['total_wage_cost_percentage']:.1f}%")

st.markdown("---")

# Create a function to generate Excel report
def generate_excel_report():
    # Create an in-memory output file
    output = io.BytesIO()
    
    # Get latest values
    latest_values = calculate_core_values()
    
    # Create workbook and add worksheets
    workbook = xlsxwriter.Workbook(output)
    
    # Add formatting
    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#D9EAD3'})
    header_format = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center', 'bg_color': '#E6F2FF'})
    currency_format = workbook.add_format({'num_format': '£#,##0.00'})
    percent_format = workbook.add_format({'num_format': '0.0%'})
    bold_format = workbook.add_format({'bold': True})
    
    # Summary Sheet
    summary_sheet = workbook.add_worksheet('Summary')
    summary_sheet.set_column('A:A', 30)
    summary_sheet.set_column('B:D', 15)
    
    # Add title and date
    summary_sheet.merge_range(0, 0, 0, 3, 'Salon Profit Planner Summary', title_format)
    summary_sheet.write('A2', f'Generated on: {datetime.now().strftime("%d %B %Y")}')
    
    # Summary metrics
    summary_sheet.write('A4', 'MONTHLY SUMMARY', bold_format)
    summary_sheet.write('A5', 'Total Revenue:')
    summary_sheet.write_number('B5', latest_values['total_sales'], currency_format)
    
    summary_sheet.write('A6', 'Total Costs:')
    summary_sheet.write_number('B6', latest_values['total_fixed_costs'] + latest_values['total_variable_costs'], currency_format)
    
    summary_sheet.write('A7', 'Monthly Profit:')
    summary_sheet.write_number('B7', latest_values['profit'], currency_format)
    
    summary_sheet.write('A8', 'Annual Profit:')
    summary_sheet.write_number('B8', latest_values['profit'] * 12, currency_format)
    
    summary_sheet.write('A9', 'Profit Margin:')
    if latest_values['total_sales'] > 0:
        summary_sheet.write_number('B9', latest_values['profit'] / latest_values['total_sales'], percent_format)
    else:
        summary_sheet.write('B9', '0.0%')
    
    # Team & Sales Sheet
    team_sheet = workbook.add_worksheet('Team & Sales')
    team_sheet.set_column('A:A', 20)
    team_sheet.set_column('B:D', 15)
    
    team_sheet.merge_range(0, 0, 0, 2, 'TEAM & SALES', title_format)
    
    # Stylist section
    team_sheet.write('A3', 'STYLISTS', header_format)
    team_sheet.write('A4', 'Stylist Name')
    team_sheet.write('B4', 'Weekly Sales')
    
    row = 5
    for i, stylist in enumerate(st.session_state.stylists):
        team_sheet.write(f'A{row}', stylist['name'])
        team_sheet.write_number(f'B{row}', stylist['sales'], currency_format)
        row += 1
    
    # Retail percentage
    team_sheet.write(f'A{row+1}', 'Retail Percentage:')
    team_sheet.write_number(f'B{row+1}', st.session_state.retail_percentage/100, percent_format)
    
    # Sales summary
    team_sheet.write(f'A{row+3}', 'WEEKLY SALES SUMMARY', header_format)
    team_sheet.write(f'A{row+4}', 'Weekly Service Sales:')
    team_sheet.write_number(f'B{row+4}', latest_values['weekly_service_sales'], currency_format)
    team_sheet.write(f'A{row+5}', 'Weekly Retail Sales:')
    team_sheet.write_number(f'B{row+5}', latest_values['weekly_retail_sales'], currency_format)
    team_sheet.write(f'A{row+6}', 'Weekly Total Sales:')
    team_sheet.write_number(f'B{row+6}', latest_values['weekly_total_sales'], currency_format)
    
    # Salaries Sheet
    salary_sheet = workbook.add_worksheet('Salaries')
    salary_sheet.set_column('A:A', 25)
    salary_sheet.set_column('B:E', 15)
    
    salary_sheet.merge_range(0, 0, 0, 4, 'SALARY DETAILS', title_format)
    
    # Salary settings
    salary_sheet.write('A3', 'SALARY SETTINGS', header_format)
    salary_sheet.write('A4', 'Service Commission:')
    salary_sheet.write_number('B4', st.session_state.salary_settings['service_commission_percentage']/100, percent_format)
    salary_sheet.write('A5', 'Retail Commission:')
    salary_sheet.write_number('B5', st.session_state.salary_settings['retail_commission_percentage']/100, percent_format)
    salary_sheet.write('A7', 'National Insurance:')
    salary_sheet.write_number('B7', st.session_state.salary_settings['national_insurance_percentage']/100, percent_format)
    salary_sheet.write('A8', 'Pension Contribution:')
    salary_sheet.write_number('B8', st.session_state.salary_settings['pension_contribution_percentage']/100, percent_format)
    
    # Stylists earnings
    salary_sheet.write('A10', 'STYLISTS', header_format)
    salary_sheet.write('A11', 'Stylist')
    salary_sheet.write('B11', 'Weekly Service Sales')
    salary_sheet.write('C11', 'Weekly Retail Sales')
    salary_sheet.write('D11', 'Weekly Earnings')
    salary_sheet.write('E11', 'Monthly Earnings')
    
    row = 12
    for i, stylist in enumerate(st.session_state.stylists):
        weekly_sales = stylist['sales']
        service_commission = weekly_sales * (st.session_state.salary_settings['service_commission_percentage'] / 100)
        
        stylist_retail_sales = 0
        if latest_values['weekly_service_sales'] > 0:
            proportion_of_sales = weekly_sales / latest_values['weekly_service_sales']
            stylist_retail_sales = latest_values['weekly_retail_sales'] * proportion_of_sales
        
        retail_commission = stylist_retail_sales * (st.session_state.salary_settings['retail_commission_percentage'] / 100)
        service_earnings = max(stylist['guarantee'], service_commission)
        total_earnings = service_earnings + retail_commission
        monthly_earnings = total_earnings * 52 / 12
        
        salary_sheet.write(f'A{row}', stylist['name'])
        salary_sheet.write_number(f'B{row}', weekly_sales, currency_format)
        salary_sheet.write_number(f'C{row}', stylist_retail_sales, currency_format)
        salary_sheet.write_number(f'D{row}', total_earnings, currency_format)
        salary_sheet.write_number(f'E{row}', monthly_earnings, currency_format)
        row += 1
    
    # Trainees earnings
    row += 2
    salary_sheet.write(f'A{row}', 'TRAINEES', header_format)
    row += 1
    salary_sheet.write(f'A{row}', 'Trainee')
    salary_sheet.write(f'B{row}', 'Weekly Wage')
    salary_sheet.write(f'C{row}', 'Monthly Wage')
    row += 1
    
    for trainee in st.session_state.trainees:
        weekly_wage = trainee['wage']
        monthly_wage = weekly_wage * 52 / 12
        
        salary_sheet.write(f'A{row}', trainee['name'])
        salary_sheet.write_number(f'B{row}', weekly_wage, currency_format)
        salary_sheet.write_number(f'C{row}', monthly_wage, currency_format)
        row += 1
    
    # Reception earnings
    row += 2
    salary_sheet.write(f'A{row}', 'RECEPTION TEAM', header_format)
    row += 1
    salary_sheet.write(f'A{row}', 'Reception')
    salary_sheet.write(f'B{row}', 'Weekly Wage')
    salary_sheet.write(f'C{row}', 'Monthly Wage')
    row += 1
    
    for receptionist in st.session_state.receptionists:
        weekly_wage = receptionist['wage']
        monthly_wage = weekly_wage * 52 / 12
        
        salary_sheet.write(f'A{row}', receptionist['name'])
        salary_sheet.write_number(f'B{row}', weekly_wage, currency_format)
        salary_sheet.write_number(f'C{row}', monthly_wage, currency_format)
        row += 1
    
    # Salary totals
    row += 2
    salary_sheet.write(f'A{row}', 'SALARY TOTALS', header_format)
    row += 1
    salary_sheet.write(f'A{row}', 'Total Weekly Salary Cost:')
    salary_sheet.write_number(f'B{row}', latest_values['weekly_total_salary_cost'], currency_format)
    row += 1
    salary_sheet.write(f'A{row}', 'Total Monthly Salary Cost:')
    salary_sheet.write_number(f'B{row}', latest_values['weekly_total_salary_cost'] * 52 / 12, currency_format)
    
    # Costs Sheet
    costs_sheet = workbook.add_worksheet('Costs')
    costs_sheet.set_column('A:A', 25)
    costs_sheet.set_column('B:C', 15)
    
    costs_sheet.merge_range(0, 0, 0, 2, 'MONTHLY COSTS', title_format)
    
    # Fixed costs
    costs_sheet.write('A3', 'FIXED COSTS', header_format)
    costs_sheet.write('A4', 'Cost Item')
    costs_sheet.write('B4', 'Amount')
    
    row = 5
    total_fixed_costs = 0
    for cost_name, cost_value in st.session_state.fixed_costs.items():
        costs_sheet.write(f'A{row}', cost_name)
        costs_sheet.write_number(f'B{row}', cost_value, currency_format)
        total_fixed_costs += cost_value
        row += 1
    
    costs_sheet.write(f'A{row}', 'Total Fixed Costs:')
    costs_sheet.write_number(f'B{row}', total_fixed_costs, currency_format)
    
    # Variable costs
    row += 2
    costs_sheet.write(f'A{row}', 'VARIABLE COSTS', header_format)
    row += 1
    costs_sheet.write(f'A{row}', 'Cost Item')
    costs_sheet.write(f'B{row}', 'Percentage')
    costs_sheet.write(f'C{row}', 'Amount')
    row += 1
    
    total_variable_costs = 0
    for cost_name, percentage in st.session_state.variable_costs_percentages.items():
        if cost_name == "Retail Commission" or cost_name == "Retail Stock":
            base_value = latest_values['retail_sales']  # Monthly retail sales
        elif cost_name == "Professional Stock":
            base_value = latest_values['total_service_sales']  # Monthly service sales
        else:
            base_value = latest_values['total_sales']  # Monthly total sales
        
        cost_value = base_value * (percentage / 100)
        
        costs_sheet.write(f'A{row}', cost_name)
        costs_sheet.write_number(f'B{row}', percentage/100, percent_format)
        costs_sheet.write_number(f'C{row}', cost_value, currency_format)
        total_variable_costs += cost_value
        row += 1
    
    costs_sheet.write(f'A{row}', 'Total Variable Costs:')
    costs_sheet.write_number(f'C{row}', total_variable_costs, currency_format)
    
    # Profit Summary
    row += 2
    costs_sheet.write(f'A{row}', 'PROFIT SUMMARY', header_format)
    row += 1
    costs_sheet.write(f'A{row}', 'Total Sales:')
    costs_sheet.write_number(f'B{row}', latest_values['total_sales'], currency_format)
    row += 1
    costs_sheet.write(f'A{row}', 'Total Costs:')
    costs_sheet.write_number(f'B{row}', total_fixed_costs + total_variable_costs, currency_format)
    row += 1
    costs_sheet.write(f'A{row}', 'Monthly Profit:')
    costs_sheet.write_number(f'B{row}', latest_values['profit'], currency_format)
    row += 1
    costs_sheet.write(f'A{row}', 'Annual Profit:')
    costs_sheet.write_number(f'B{row}', latest_values['profit'] * 12, currency_format)
    row += 1
    costs_sheet.write(f'A{row}', 'Profit Margin:')
    if latest_values['total_sales'] > 0:
        costs_sheet.write_number(f'B{row}', latest_values['profit'] / latest_values['total_sales'], percent_format)
    else:
        costs_sheet.write(f'B{row}', '0.0%')
    
    # Close the workbook
    workbook.close()
    
    # Reset file pointer to beginning
    output.seek(0)
    
    return output


# Main content container
main_container = st.container()

with main_container:
    # Add download button at the top
    export_col1, export_col2 = st.columns([5, 1])
    with export_col2:
        excel_file = generate_excel_report()
        st.download_button(
            label="📊 Export to Excel",
            data=excel_file,
            file_name=f"salon_profit_planner_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Create tabs for different sections
    team_tab, salaries_tab, costs_tab, profit_tab, scenarios_tab = st.tabs(["Team & Sales", "Salaries", "Costs", "Profit Analysis", "Scenarios"])
    
    with team_tab:
        st.header("Team & Sales Projections")
        
        # Add/remove stylist functionality
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader("Stylists")
        with col2:
            if st.button("➕ Add Stylist"):
                # Save state before making changes
                save_state_for_undo()
                # Add new stylist
                st.session_state.stylists.append({
                    'name': f'Stylist {len(st.session_state.stylists) + 1}',
                    'sales': 0,
                    'guarantee': 0
                })
                st.rerun()
        
        # Create a container for better alignment
        stylist_container = st.container()
        
        # Create three columns for the headers to match the new layout with guarantee
        header_col1, header_col2, header_col3 = stylist_container.columns([1, 1, 1])
        with header_col1:
            st.write("Stylist Name")
        with header_col2:
            st.write("Guarantee (£)")
        with header_col3:
            st.write("Weekly Sales (£)")
        
        # Display stylists and collect sales projections
        for i, stylist in enumerate(st.session_state.stylists):
            with stylist_container:
                # Create a row for each stylist
                input_col1, input_col2, input_col3, input_col4 = st.columns([1, 1, 1, 0.2])
                
                with input_col1:
                    name = st.text_input(
                        "Stylist Name",
                        value=stylist['name'],
                        key=f"name_{i}",
                        label_visibility="collapsed"
                    )
                    stylist['name'] = name
                
                with input_col2:
                    guarantee = st.number_input(
                        "Guarantee",
                        min_value=0,
                        value=stylist['guarantee'],
                        step=10,
                        key=f"guarantee_{i}",
                        label_visibility="collapsed"
                    )
                    if guarantee != stylist['guarantee']:
                        save_state_for_undo()
                        stylist['guarantee'] = guarantee
                        st.rerun()
                    
                with input_col3:
                    sales = st.number_input(
                        "Weekly Sales",
                        min_value=0,
                        value=stylist['sales'],
                        step=100,
                        key=f"sales_{i}",
                        label_visibility="collapsed"
                    )
                    if sales != stylist['sales']:
                        update_stylist_sales(i, sales)
                    
                with input_col4:
                    if len(st.session_state.stylists) > 1 and st.button("🗑️", key=f"delete_{i}"):
                        # Save state before making changes
                        save_state_for_undo()
                        # Delete stylist
                        st.session_state.stylists.pop(i)
                        st.rerun()
        
        # Retail sales calculation
        st.subheader("Retail Sales")
        col1, col2 = st.columns([2, 2])
        with col1:
            # Initialize a specific key for the retail percentage widget
            if 'retail_input_value' not in st.session_state:
                st.session_state.retail_input_value = st.session_state.retail_percentage
                
            # The retail percentage input uses a different key
            retail_pct = st.number_input(
                "Retail sales as percentage of service sales (%)",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.retail_input_value,
                step=0.1,
                format="%.1f",
                key="retail_input_value"
            )
            
            # Only update the session state if the value has changed
            if retail_pct != st.session_state.retail_percentage:
                save_state_for_undo()
                st.session_state.retail_percentage = retail_pct
        
        # Recalculate core values to ensure latest data
        latest_values = calculate_core_values()
        
        # Display sales summary - WEEKLY values
        st.subheader("Weekly Sales Summary")
        sales_col1, sales_col2, sales_col3 = st.columns(3)
        with sales_col1:
            st.metric("Weekly Service Sales", format_currency(latest_values['weekly_service_sales']))
        with sales_col2:
            st.metric("Weekly Retail Sales", format_currency(latest_values['weekly_retail_sales']))
        with sales_col3:
            st.metric("Weekly Salon Sales", format_currency(latest_values['weekly_total_sales']))
            
        # Add Monthly Sales Summary
        st.subheader("Monthly Sales Summary")
        monthly_col1, monthly_col2, monthly_col3 = st.columns(3)
        with monthly_col1:
            monthly_service_sales = latest_values['weekly_service_sales'] * 52 / 12
            st.metric("Monthly Service Sales", format_currency(monthly_service_sales))
        with monthly_col2:
            monthly_retail_sales = latest_values['weekly_retail_sales'] * 52 / 12
            st.metric("Monthly Retail Sales", format_currency(monthly_retail_sales))
        with monthly_col3:
            monthly_total_sales = latest_values['weekly_total_sales'] * 52 / 12
            st.metric("Monthly Salon Sales", format_currency(monthly_total_sales))
            
        # Additional Monthly Income Section
        st.markdown("---")
        st.subheader("Additional Monthly Income")
        st.markdown("Enter any additional monthly income not related to salon services or retail sales.")
        
        # Create a layout with 3 columns for better organization
        income_col1, income_col2 = st.columns(2)
        
        # Track total additional income
        total_additional_income = 0
        
        # First column of income sources
        with income_col1:
            for income_name in list(st.session_state.additional_income.keys())[:3]:  # First 3 items
                income_value = st.number_input(
                    f"{income_name} (£)",
                    min_value=0,
                    value=st.session_state.additional_income[income_name],
                    step=100,
                    key=f"income_{income_name}"
                )
                if income_value != st.session_state.additional_income[income_name]:
                    st.session_state.additional_income[income_name] = income_value
                    st.rerun()
                total_additional_income += income_value
        
        # Second column of income sources
        with income_col2:
            for income_name in list(st.session_state.additional_income.keys())[3:]:  # Last 3 items
                income_value = st.number_input(
                    f"{income_name} (£)",
                    min_value=0,
                    value=st.session_state.additional_income[income_name],
                    step=100,
                    key=f"income_{income_name}"
                )
                if income_value != st.session_state.additional_income[income_name]:
                    st.session_state.additional_income[income_name] = income_value
                    st.rerun()
                total_additional_income += income_value
        
        # Display total additional income
        st.metric("Total Additional Monthly Income", format_currency(total_additional_income))
        
        # Display updated total monthly revenue (salon sales + additional income)
        st.metric("Total Monthly Revenue", format_currency(monthly_total_sales + total_additional_income))

    with salaries_tab:
        st.header("Salon Team Salaries")
        
        # Calculations dropdown
        with st.expander("Calculations", expanded=False):
            st.markdown("""
            This page calculates all team member salaries:
            - **Stylists** earn the higher of either minimum wage or service commission, plus retail commission
            - **Trainees** receive a fixed weekly wage
            - **Receptionists** receive a fixed weekly wage
            
            National Insurance and Pension contributions apply to all team members.
            
            **Note: All sales figures and salary calculations on this page are weekly**
            """)
        
        # Salary settings in dropdown
        with st.expander("Salary Settings", expanded=False):
            # Create compact layout with smaller input fields
            settings_col1, settings_col2, settings_col3 = st.columns([1, 1, 1])
        
            with settings_col1:
                st.markdown("##### Base Settings")
                st.info("Individual guarantees for stylists are now set on the Team & Sales page.")
            
            with settings_col2:
                st.markdown("##### Commission Rates")
                service_commission = st.number_input(
                    "Service Commission (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=st.session_state.salary_settings['service_commission_percentage'],
                    step=0.1,
                    format="%.1f",
                    key=f"service_comm_field"
                )
                if service_commission != st.session_state.salary_settings['service_commission_percentage']:
                    save_state_for_undo()
                    st.session_state.salary_settings['service_commission_percentage'] = service_commission
                    st.rerun()
                
                retail_commission = st.number_input(
                    "Retail Commission (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=st.session_state.salary_settings['retail_commission_percentage'],
                    step=0.1,
                    format="%.1f",
                    key=f"retail_comm_field"
                )
                if retail_commission != st.session_state.salary_settings['retail_commission_percentage']:
                    save_state_for_undo()
                    st.session_state.salary_settings['retail_commission_percentage'] = retail_commission
                    st.rerun()
                
            with settings_col3:
                st.markdown("##### Additional Costs")
                national_insurance = st.number_input(
                    "National Insurance (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=st.session_state.salary_settings['national_insurance_percentage'],
                    step=0.1,
                    format="%.1f",
                    key=f"ni_field"
                )
                if national_insurance != st.session_state.salary_settings['national_insurance_percentage']:
                    save_state_for_undo()
                    st.session_state.salary_settings['national_insurance_percentage'] = national_insurance
                    st.rerun()
                
                pension_contribution = st.number_input(
                    "Pension Contrib. (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=st.session_state.salary_settings['pension_contribution_percentage'],
                    step=0.1,
                    format="%.1f",
                    key=f"pension_field"
                )
                if pension_contribution != st.session_state.salary_settings['pension_contribution_percentage']:
                    save_state_for_undo()
                    st.session_state.salary_settings['pension_contribution_percentage'] = pension_contribution
                    st.rerun()
        
        # Calculate salaries for each stylist
        st.subheader("Weekly Stylist Earnings")
        
        # Get values from updated core values
        latest_values = calculate_core_values()
        
        # Create a table for calculations
        salary_data = []
        
        for i, stylist in enumerate(st.session_state.stylists):
            # Weekly sales and calculations
            weekly_service_sales = stylist['sales']  # Already weekly
            
            # Service commission calculation
            service_commission_amount = weekly_service_sales * (service_commission / 100)
            
            # Individual retail sales based on proportion of service sales
            stylist_retail_sales = 0
            if latest_values['weekly_service_sales'] > 0:
                proportion_of_sales = weekly_service_sales / latest_values['weekly_service_sales']
                stylist_retail_sales = latest_values['weekly_retail_sales'] * proportion_of_sales
                
            retail_commission_amount = stylist_retail_sales * (retail_commission / 100)
            
            # Determine final salary (higher of minimum wage or service commission, plus retail commission)
            # Get the stylist's guarantee from the Team & Sales page
            stylist_guarantee = stylist['guarantee']
            service_earnings = max(stylist_guarantee, service_commission_amount)
            total_weekly_earnings = service_earnings + retail_commission_amount
            
            # Add to table with numbering starting from 1
            salary_data.append({
                '#': i + 1,  # Start numbering from 1
                'Stylist': stylist['name'],
                'Weekly Service Sales': format_currency(weekly_service_sales),
                'Service Commission': format_currency(service_commission_amount),
                'Guarantee': format_currency(stylist_guarantee),
                'Service Earnings': format_currency(service_earnings),
                'Retail Sales': format_currency(stylist_retail_sales),
                'Retail Commission': format_currency(retail_commission_amount),
                'Total Weekly Earnings': format_currency(total_weekly_earnings)
            })
        
        # Create DataFrame with proper column ordering
        salary_df = pd.DataFrame(salary_data)
        
        # Ensure the # column is first, followed by Stylist, then the rest
        column_order = ['#', 'Stylist', 'Weekly Service Sales', 'Service Commission', 
                       'Guarantee', 'Service Earnings', 'Retail Sales', 'Retail Commission', 
                       'Total Weekly Earnings']
        salary_df = salary_df[column_order]
        
        # Create a function to highlight rows where sales are less than 3x guarantee
        def highlight_low_performers(row):
            # Extract the numeric values from currency strings
            try:
                sales_str = row['Weekly Service Sales'].replace('£', '').replace(',', '')
                guarantee_str = row['Guarantee'].replace('£', '').replace(',', '')
                
                sales = float(sales_str)
                guarantee = float(guarantee_str)
                
                # If guarantee is 0, avoid division by zero
                if guarantee == 0:
                    return [''] * len(row)
                
                # If sales are less than 3x guarantee, highlight the entire row in red
                if sales < guarantee * 3:
                    return ['background-color: #ffcccc'] * len(row)
                
            except (ValueError, AttributeError):
                pass
                
            return [''] * len(row)
            
        # Apply the styling with much larger fonts for presentations
        styled_df = salary_df.style.apply(highlight_low_performers, axis=1).set_table_styles([
            {'selector': 'th', 'props': [('font-size', '28px'), ('font-weight', 'bold')]},
            {'selector': 'td', 'props': [('font-size', '24px')]},
            {'selector': 'table', 'props': [('font-family', 'Arial, sans-serif')]}
        ])
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=400,
            hide_index=True
        )
        
        # Add subtotal for stylist earnings section
        stylist_col1, stylist_col2 = st.columns(2)
        with stylist_col1:
            total_weekly_stylist = latest_values['weekly_stylist_salary_cost']
            st.metric("Total Weekly Stylist Earnings", format_currency(total_weekly_stylist))
        with stylist_col2:
            total_monthly_stylist = total_weekly_stylist * 52 / 12
            st.metric("Total Monthly Stylist Earnings", format_currency(total_monthly_stylist))
        
        # TRAINEES SECTION
        st.markdown("---")
        st.subheader("Trainees")
        
        # Add/remove trainee functionality
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("##### Trainee Wages")
        with col2:
            if st.button("➕ Add Trainee"):
                st.session_state.trainees.append({
                    'name': f'Trainee {len(st.session_state.trainees) + 1}',
                    'wage': 0
                })
                st.rerun()
        
        # Create a container for better alignment
        trainee_container = st.container()
        
        # Create two columns for the headers to match the exact layout in the image
        header_col1, header_col2 = trainee_container.columns([1, 1])
        with header_col1:
            st.write("Trainee Name")
        with header_col2:
            st.write("Weekly Wage (£)")
        
        # Display trainees and collect wage information
        for i, trainee in enumerate(st.session_state.trainees):
            with trainee_container:
                # Create a row for each trainee
                input_col1, input_col2, input_col3 = st.columns([1, 1, 0.2])
                
                with input_col1:
                    name = st.text_input(
                        "Trainee Name",
                        value=trainee['name'],
                        key=f"trainee_name_{i}",
                        label_visibility="collapsed"
                    )
                    trainee['name'] = name
                    
                with input_col2:
                    wage = st.number_input(
                        "Weekly Wage",
                        min_value=0,
                        value=trainee['wage'],
                        step=10,
                        key=f"trainee_wage_{i}",
                        label_visibility="collapsed"
                    )
                    if wage != trainee['wage']:
                        save_state_for_undo()
                        trainee['wage'] = wage
                        st.rerun()
                    
                with input_col3:
                    if len(st.session_state.trainees) > 1 and st.button("🗑️", key=f"delete_trainee_{i}"):
                        save_state_for_undo()
                        st.session_state.trainees.pop(i)
                        st.rerun()
        
        # Create a table for trainee calculations
        trainee_data = []
        for trainee in st.session_state.trainees:
            weekly_wage = trainee['wage']
            monthly_wage = weekly_wage * 52 / 12
            
            trainee_data.append({
                'Trainee': trainee['name'],
                'Weekly Wage': format_currency(weekly_wage),
                'Monthly Equivalent': format_currency(monthly_wage)
            })
        
        # Create a DataFrame for display
        trainee_df = pd.DataFrame(trainee_data)
        st.dataframe(trainee_df, use_container_width=True)
        
        # Calculate totals for trainees
        total_weekly_trainee_earnings = latest_values['weekly_trainee_salary_cost']
        total_monthly_trainee_earnings = total_weekly_trainee_earnings * 52 / 12
        
        # Display the totals
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Weekly Trainee Wages", format_currency(total_weekly_trainee_earnings))
        with col2:
            st.metric("Total Monthly Trainee Wages", format_currency(total_monthly_trainee_earnings))
        
        # RECEPTIONISTS SECTION
        st.markdown("---")
        st.subheader("Reception Team")
        
        # Add/remove receptionist functionality
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("##### Reception Wages")
        with col2:
            if st.button("➕ Add Receptionist"):
                # Simply add the receptionist without touching retail percentage
                st.session_state.receptionists.append({
                    'name': f'Reception {len(st.session_state.receptionists) + 1}',
                    'wage': 0
                })
                st.rerun()
        
        # Create a container for better alignment
        reception_container = st.container()
        
        # Create two columns for the headers to match the exact layout in the image
        header_col1, header_col2 = reception_container.columns([1, 1])
        with header_col1:
            st.write("Reception Name")
        with header_col2:
            st.write("Weekly Wage (£)")
        
        # Display receptionists and collect wage information
        for i, receptionist in enumerate(st.session_state.receptionists):
            with reception_container:
                # Create a row for each receptionist
                input_col1, input_col2, input_col3 = st.columns([1, 1, 0.2])
                
                with input_col1:
                    name = st.text_input(
                        "Reception Name",
                        value=receptionist['name'],
                        key=f"reception_name_{i}",
                        label_visibility="collapsed"
                    )
                    receptionist['name'] = name
                    
                with input_col2:
                    wage = st.number_input(
                        "Weekly Wage",
                        min_value=0,
                        value=receptionist['wage'],
                        step=10,
                        key=f"reception_wage_{i}",
                        label_visibility="collapsed"
                    )
                    if wage != receptionist['wage']:
                        save_state_for_undo()
                        receptionist['wage'] = wage
                        st.rerun()
                    
                with input_col3:
                    if len(st.session_state.receptionists) > 1 and st.button("🗑️", key=f"delete_reception_{i}"):
                        save_state_for_undo()
                        st.session_state.receptionists.pop(i)
                        st.rerun()
        
        # Create a table for receptionist calculations
        reception_data = []
        for receptionist in st.session_state.receptionists:
            weekly_wage = receptionist['wage']
            monthly_wage = weekly_wage * 52 / 12
            
            reception_data.append({
                'Reception': receptionist['name'],
                'Weekly Wage': format_currency(weekly_wage),
                'Monthly Equivalent': format_currency(monthly_wage)
            })
        
        # Create a DataFrame for display
        reception_df = pd.DataFrame(reception_data)
        st.dataframe(reception_df, use_container_width=True)
        
        # Calculate totals for receptionists
        total_weekly_reception_earnings = latest_values['weekly_receptionist_salary_cost']
        total_monthly_reception_earnings = total_weekly_reception_earnings * 52 / 12
        
        # Display the totals
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Weekly Reception Wages", format_currency(total_weekly_reception_earnings))
        with col2:
            st.metric("Total Monthly Reception Wages", format_currency(total_monthly_reception_earnings))
        
        # Display breakdown of costs
        st.markdown("---")
        st.subheader("Salary Costs Breakdown")
        
        cost_row1_col1, cost_row1_col2, cost_row1_col3 = st.columns(3)
        with cost_row1_col1:
            st.metric("Stylists", format_currency(latest_values['weekly_stylist_salary_cost']))
        with cost_row1_col2:
            st.metric("Trainees", format_currency(latest_values['weekly_trainee_salary_cost']))
        with cost_row1_col3:
            st.metric("Reception Team", format_currency(latest_values['weekly_receptionist_salary_cost']))
            
        cost_row2_col1, cost_row2_col2, cost_row2_col3 = st.columns(3)
        with cost_row2_col1:
            st.metric("Base Salary Cost (Total)", format_currency(latest_values['weekly_salary_cost']))
        with cost_row2_col2:
            ni_pct = st.session_state.salary_settings['national_insurance_percentage']
            st.metric(f"National Insurance ({ni_pct}%)", format_currency(latest_values['weekly_ni_cost']))
        with cost_row2_col3:
            pension_pct = st.session_state.salary_settings['pension_contribution_percentage']
            st.metric(f"Pension Contribution ({pension_pct}%)", format_currency(latest_values['weekly_pension_cost']))
        
        # Display both weekly and monthly totals
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("Total Weekly Salary Cost")
            st.markdown(f"## {format_currency(latest_values['weekly_total_salary_cost'])}")
        with col2:
            st.subheader("Total Monthly Salary Cost")
            monthly_salary_cost = latest_values['weekly_total_salary_cost'] * 52 / 12
            st.markdown(f"## {format_currency(monthly_salary_cost)}")
        with col3:
            st.subheader("% of Total Sales")
            wage_cost_percentage = latest_values['total_wage_cost_percentage']
            st.markdown(f"## {wage_cost_percentage:.1f}%")
        
        # Add explanation of calculations
        with st.expander("How are the calculations done?"):
            st.markdown(f"""
            ### Salary Calculation
            Each stylist earns the **higher** of:
            - Their individual weekly guarantee (set on Team & Sales page)
            - {service_commission}% commission on their service sales
            
            Plus:
            - {retail_commission}% commission on their retail sales
            - Retail sales are allocated to stylists based on their proportion of total service sales
            
            ### Impact on Monthly Costs
            The weekly salary costs are converted to monthly (× 52/12) for the Variable Costs section:
            - Monthly Wages/Salaries: {format_currency(latest_values['total_salary_cost'] - latest_values['monthly_retail_commission'])} ({st.session_state.variable_costs_percentages['Wages/Salaries (excluding retail commission)']:.1f}% of total sales)
            - Monthly Retail Commission: {format_currency(latest_values['monthly_retail_commission'])} ({st.session_state.variable_costs_percentages['Retail Commission']:.1f}% of retail sales)
            """)
        
        percentage_of_sales = (latest_values['total_salary_cost'] / latest_values['total_sales'] * 100) if latest_values['total_sales'] > 0 else 0
        st.info(f"Adjusting salary settings directly impacts profit potential. Monthly salary cost is {format_currency(latest_values['total_salary_cost'])}, which is {percentage_of_sales:.1f}% of total monthly sales.")

    with costs_tab:
        st.header("Monthly Costs Management")
        
        # Get monthly values from core_values
        latest_values = calculate_core_values()
        total_sales = latest_values['total_sales']
        retail_sales = latest_values['retail_sales']
        total_service_sales = latest_values['total_service_sales']
        
        # Show monthly sales summary
        st.subheader("Monthly Sales Summary")
        monthly_sales_col1, monthly_sales_col2, monthly_sales_col3 = st.columns(3)
        with monthly_sales_col1:
            st.metric("Monthly Service Sales", format_currency(total_service_sales))
        with monthly_sales_col2:
            st.metric("Monthly Retail Sales", format_currency(retail_sales))
        with monthly_sales_col3:
            st.metric("Monthly Total Sales", format_currency(total_sales))
            
        st.info("Monthly values are calculated as weekly values × 52/12 (approximately 4.33 weeks per month)")
        
        fixed_col, variable_col = st.columns(2)
        
        with fixed_col:
            st.subheader("Fixed Costs")
            
            # Calculate and display total fixed costs
            total_fixed_costs = 0
            for cost_name in st.session_state.fixed_costs:
                cost_value = st.number_input(
                    cost_name,
                    min_value=0,
                    value=st.session_state.fixed_costs[cost_name],
                    step=10,
                    key=f"fixed_{cost_name}"
                )
                if cost_value != st.session_state.fixed_costs[cost_name]:
                    save_state_for_undo()
                    st.session_state.fixed_costs[cost_name] = cost_value
                    st.rerun()
                total_fixed_costs += cost_value
            
            st.metric("Total Fixed Costs", format_currency(total_fixed_costs))
        
        with variable_col:
            st.subheader("Variable Costs (% of sales)")
            
            variable_costs = latest_values['variable_costs']
            total_variable_costs = 0
            
            for cost_name in st.session_state.variable_costs_percentages:
                # Determine which sales base to use for this variable cost
                if cost_name == "Retail Commission" or cost_name == "Retail Stock":
                    base_text = "% of retail sales"
                    base_value = retail_sales  # Monthly retail sales
                elif cost_name == "Professional Stock":
                    base_text = "% of service sales"
                    base_value = total_service_sales  # Monthly service sales
                else:
                    base_text = "% of total sales"
                    base_value = total_sales  # Monthly total sales
                
                # Special handling for salary-related costs that are calculated automatically
                is_editable = True
                if cost_name == "Wages/Salaries (excluding retail commission)" or cost_name == "Retail Commission":
                    is_editable = False
                
                if is_editable:
                    # Input for percentage
                    cost_percentage = st.number_input(
                        f"{cost_name} ({base_text})",
                        min_value=0.0,
                        max_value=100.0,
                        value=min(float(st.session_state.variable_costs_percentages[cost_name]), 100.0),
                        step=0.1,
                        format="%.1f",
                        key=f"var_{cost_name}"
                    )
                    if cost_percentage != st.session_state.variable_costs_percentages[cost_name]:
                        save_state_for_undo()
                        st.session_state.variable_costs_percentages[cost_name] = cost_percentage
                        st.rerun()
                else:
                    # Just display the calculated percentage
                    st.text(f"{cost_name} ({base_text})")
                    cost_percentage = st.session_state.variable_costs_percentages[cost_name]
                    st.text(f"{cost_percentage:.1f}%")
                
                # Display monetary value (monthly)
                cost_value = base_value * (cost_percentage / 100)
                st.text(f"{format_currency(cost_value)}")
                total_variable_costs += cost_value
            
            st.metric("Total Variable Costs", format_currency(total_variable_costs))
        
        # Display total costs and profit
        st.subheader("Monthly Profit Summary")
        profit_col1, profit_col2, profit_col3 = st.columns(3)
        with profit_col1:
            st.metric("Total Costs", format_currency(total_fixed_costs + total_variable_costs))
        with profit_col2:
            profit = total_sales - total_fixed_costs - total_variable_costs
            st.metric("Monthly Profit", format_currency(profit))
        with profit_col3:
            profit_margin = (profit / total_sales * 100) if total_sales > 0 else 0
            st.metric("Profit Margin", f"{profit_margin:.1f}%")
        
        # Create a breakdown chart
        st.subheader("Cost Breakdown")
        
        # Prepare data for visualization
        cost_categories = list(st.session_state.fixed_costs.keys()) + list(variable_costs.keys())
        cost_values = list(st.session_state.fixed_costs.values()) + list(variable_costs.values())
        cost_types = ["Fixed"] * len(st.session_state.fixed_costs) + ["Variable"] * len(variable_costs)
        
        # Create a DataFrame for the costs
        costs_df = pd.DataFrame({
            'Category': cost_categories,
            'Value': cost_values,
            'Type': cost_types
        })
        
        # Sort by cost value (descending)
        costs_df = costs_df.sort_values('Value', ascending=False)
        
        # Create a horizontal bar chart using Plotly
        fig = go.Figure()
        
        # Add fixed costs
        fixed_df = costs_df[costs_df['Type'] == 'Fixed']
        if not fixed_df.empty:
            fig.add_trace(go.Bar(
                y=fixed_df['Category'],
                x=fixed_df['Value'],
                orientation='h',
                name='Fixed Costs',
                marker=dict(color='rgba(55, 83, 109, 0.7)')
            ))
        
        # Add variable costs
        variable_df = costs_df[costs_df['Type'] == 'Variable']
        if not variable_df.empty:
            fig.add_trace(go.Bar(
                y=variable_df['Category'],
                x=variable_df['Value'],
                orientation='h',
                name='Variable Costs',
                marker=dict(color='rgba(26, 118, 255, 0.7)')
            ))
        
        # Customize layout
        fig.update_layout(
            title="Monthly Cost Breakdown",
            xaxis_title="Cost (£)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            height=600
        )
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)

    with scenarios_tab:
        st.header("Scenario Comparison")
        
        # Create two columns for side-by-side actions
        scenario_col1, scenario_col2 = st.columns([3, 2])
        
        with scenario_col1:
            st.subheader("Save Current Plan as Scenario")
            
            # Show scenario count status
            scenario_count = len(st.session_state.scenarios)
            if scenario_count == 0:
                st.info("💡 You can save up to 3 scenarios for comparison")
            else:
                st.info(f"📊 {scenario_count}/3 scenarios saved")
            
            # Input for scenario name
            new_scenario_name = st.text_input(
                "Scenario Name",
                value=st.session_state.current_scenario_name,
                key="new_scenario_name"
            )
            
            # Add description
            scenario_description = st.text_area(
                "Scenario Description (optional)",
                placeholder="Enter a brief description of this scenario...",
                key="scenario_description"
            )
            
            # Save button
            if st.button("💾 Save Current Plan as Scenario"):
                if new_scenario_name:
                    # Check if we already have 3 scenarios and this is a new one
                    if len(st.session_state.scenarios) >= 3 and new_scenario_name not in st.session_state.scenarios:
                        st.error("Maximum 3 scenarios allowed. Please delete an existing scenario first or overwrite an existing one.")
                    else:
                        # Record current state as a scenario
                        st.session_state.scenarios[new_scenario_name] = {
                            'description': scenario_description,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            'stylist_data': st.session_state.stylists.copy(),
                            'retail_percentage': st.session_state.retail_percentage,
                            'trainee_data': st.session_state.trainees.copy(),
                            'receptionist_data': st.session_state.receptionists.copy(),
                            'salary_settings': st.session_state.salary_settings.copy(),
                            'fixed_costs': st.session_state.fixed_costs.copy(),
                            'variable_costs_percentages': st.session_state.variable_costs_percentages.copy(),
                            'metrics': {
                                'monthly_service_sales': calculate_core_values()['total_service_sales'],
                                'monthly_retail_sales': calculate_core_values()['retail_sales'],
                                'monthly_total_sales': calculate_core_values()['total_sales'],
                                'monthly_fixed_costs': calculate_core_values()['total_fixed_costs'],
                                'monthly_variable_costs': calculate_core_values()['total_variable_costs'],
                                'monthly_profit': calculate_core_values()['profit'],
                                'profit_margin': calculate_core_values()['profit_margin']
                            }
                        }
                        # Save to database for multi-user support
                        user_id = st.session_state.get('user_id')
                        if user_id:
                            scenario_data = {
                                'stylist_data': st.session_state.scenarios[new_scenario_name]['stylist_data'],
                                'retail_percentage': st.session_state.scenarios[new_scenario_name]['retail_percentage'],
                                'trainee_data': st.session_state.scenarios[new_scenario_name]['trainee_data'],
                                'receptionist_data': st.session_state.scenarios[new_scenario_name]['receptionist_data'],
                                'salary_settings': st.session_state.scenarios[new_scenario_name]['salary_settings'],
                                'fixed_costs': st.session_state.scenarios[new_scenario_name]['fixed_costs'],
                                'variable_costs_percentages': st.session_state.scenarios[new_scenario_name]['variable_costs_percentages'],
                                'metrics': st.session_state.scenarios[new_scenario_name]['metrics']
                            }
                            success, message = save_scenario(user_id, new_scenario_name, scenario_description, scenario_data)
                            if not success:
                                st.error(message)
                        # Auto-save current session data
                        save_user_session_data()
                        
                        st.session_state.current_scenario_name = new_scenario_name
                        st.success(f"Scenario '{new_scenario_name}' saved successfully!")
                        st.rerun()
                else:
                    st.error("Please enter a name for your scenario.")
        
        with scenario_col2:
            st.subheader("Load & Compare")
            
            # Only show this if we have saved scenarios
            if st.session_state.scenarios:
                scenario_to_load = st.selectbox(
                    "Select a saved scenario to load",
                    options=list(st.session_state.scenarios.keys()),
                    key="scenario_to_load"
                )
                
                # Show scenario description if available
                if scenario_to_load and st.session_state.scenarios[scenario_to_load]['description']:
                    st.info(st.session_state.scenarios[scenario_to_load]['description'])
                
                # Load button
                if st.button("📂 Load Selected Scenario"):
                    if scenario_to_load in st.session_state.scenarios:
                        # Load all scenario data
                        scenario_data = st.session_state.scenarios[scenario_to_load]
                        st.session_state.stylists = scenario_data['stylist_data'].copy()
                        st.session_state.retail_percentage = scenario_data['retail_percentage']
                        st.session_state.trainees = scenario_data['trainee_data'].copy()
                        st.session_state.receptionists = scenario_data['receptionist_data'].copy()
                        st.session_state.salary_settings = scenario_data['salary_settings'].copy()
                        st.session_state.fixed_costs = scenario_data['fixed_costs'].copy()
                        st.session_state.variable_costs_percentages = scenario_data['variable_costs_percentages'].copy()
                        st.session_state.current_scenario_name = scenario_to_load
                        # Save updated state to file (in case the loaded scenario becomes the basis for further edits)
                        save_scenarios_to_file()
                        st.success(f"Scenario '{scenario_to_load}' loaded successfully!")
                        st.rerun()
                
                # Delete scenario button
                if st.button("🗑️ Delete Selected Scenario"):
                    if scenario_to_load in st.session_state.scenarios:
                        if scenario_to_load == st.session_state.current_scenario_name:
                            st.error("Cannot delete the currently active scenario.")
                        else:
                            del st.session_state.scenarios[scenario_to_load]
                            # Delete from database for multi-user support
                            user_id = st.session_state.get('user_id')
                            if user_id:
                                delete_scenario(user_id, scenario_to_load)
                            st.success(f"Scenario '{scenario_to_load}' deleted.")
                            st.rerun()
            else:
                st.info("No saved scenarios yet. Create a scenario by saving your current plan.")
        
        # Show comparison chart if we have scenarios
        if st.session_state.scenarios:
            st.markdown("---")
            st.subheader("Scenario Comparison")
            
            # Select scenarios to compare
            scenarios_to_compare = st.multiselect(
                "Select scenarios to compare",
                options=list(st.session_state.scenarios.keys()),
                default=[st.session_state.current_scenario_name] if st.session_state.current_scenario_name in st.session_state.scenarios else [],
                key="scenarios_to_compare"
            )
            
            if scenarios_to_compare:
                comparison_metric = st.selectbox(
                    "Compare by metric",
                    options=["Monthly Revenue", "Monthly Costs", "Monthly Profit", "Profit Margin"],
                    key="comparison_metric"
                )
                
                # Create comparison DataFrame
                data = []
                for scenario_name in scenarios_to_compare:
                    scenario = st.session_state.scenarios[scenario_name]
                    
                    if comparison_metric == "Monthly Revenue":
                        value = scenario['metrics']['monthly_total_sales']
                    elif comparison_metric == "Monthly Costs":
                        value = scenario['metrics']['monthly_fixed_costs'] + scenario['metrics']['monthly_variable_costs']
                    elif comparison_metric == "Monthly Profit":
                        value = scenario['metrics']['monthly_profit']
                    else:  # Profit Margin
                        value = scenario['metrics']['profit_margin']
                        
                    data.append({
                        'Scenario': scenario_name,
                        'Value': value,
                        'Date Created': scenario['timestamp']
                    })
                
                comparison_df = pd.DataFrame(data)
                
                # Create chart
                if comparison_metric == "Profit Margin":
                    # For percentage values
                    fig = go.Figure(data=[
                        go.Bar(
                            x=comparison_df['Scenario'],
                            y=comparison_df['Value'],
                            text=[f"{v:.1f}%" for v in comparison_df['Value']],
                            textposition='auto',
                            marker_color='lightgreen'
                        )
                    ])
                    fig.update_layout(
                        title=f"Comparison by {comparison_metric}",
                        yaxis=dict(title=f"{comparison_metric} (%)"),
                        height=500
                    )
                else:
                    # For currency values
                    fig = go.Figure(data=[
                        go.Bar(
                            x=comparison_df['Scenario'],
                            y=comparison_df['Value'],
                            text=[format_currency(v) for v in comparison_df['Value']],
                            textposition='auto',
                            marker_color='lightblue'
                        )
                    ])
                    fig.update_layout(
                        title=f"Comparison by {comparison_metric}",
                        yaxis=dict(title=f"{comparison_metric} (£)"),
                        height=500
                    )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Create detailed comparison table
                st.subheader("Detailed Comparison")
                
                detailed_data = []
                for scenario_name in scenarios_to_compare:
                    scenario = st.session_state.scenarios[scenario_name]
                    metrics = scenario['metrics']
                    
                    detailed_data.append({
                        'Scenario': scenario_name,
                        'Monthly Service Sales': format_currency(metrics['monthly_service_sales']),
                        'Monthly Retail Sales': format_currency(metrics['monthly_retail_sales']),
                        'Monthly Total Sales': format_currency(metrics['monthly_total_sales']),
                        'Monthly Fixed Costs': format_currency(metrics['monthly_fixed_costs']),
                        'Monthly Variable Costs': format_currency(metrics['monthly_variable_costs']),
                        'Monthly Profit': format_currency(metrics['monthly_profit']),
                        'Profit Margin': f"{metrics['profit_margin']:.1f}%",
                        'Date Created': scenario['timestamp']
                    })
                
                detailed_df = pd.DataFrame(detailed_data)
                st.dataframe(detailed_df, use_container_width=True)
            
                # Option to download comparison
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    detailed_df.to_excel(writer, sheet_name="Scenario Comparison", index=False)
                    workbook = writer.book
                    worksheet = writer.sheets["Scenario Comparison"]
                    
                    # Set column widths
                    worksheet.set_column('A:A', 20)
                    worksheet.set_column('B:H', 15)
                    worksheet.set_column('I:I', 20)
                
                buffer.seek(0)
                
                st.download_button(
                    label="Download Comparison as Excel",
                    data=buffer,
                    file_name=f"scenario_comparison_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    with profit_tab:
        st.header("Profit Analysis")
        
        # Get latest values
        latest_values = calculate_core_values()
        
        # Extract key values for profit analysis
        monthly_total_sales = latest_values['total_sales']
        monthly_fixed_costs = latest_values['total_fixed_costs']
        monthly_variable_costs = latest_values['total_variable_costs']
        monthly_profit = latest_values['profit']
        profit_margin = latest_values['profit_margin']
        
        # Annual projections
        annual_sales = monthly_total_sales * 12
        annual_fixed_costs = monthly_fixed_costs * 12
        annual_variable_costs = monthly_variable_costs * 12
        annual_profit = monthly_profit * 12
        
        # Display profit summary for different time periods
        st.subheader("Profit Summary")
        summary_cols = st.columns(3)
        
        with summary_cols[0]:
            st.markdown("##### Monthly")
            st.metric("Total Sales", format_currency(monthly_total_sales))
            st.metric("Fixed Costs", format_currency(monthly_fixed_costs))
            st.metric("Variable Costs", format_currency(monthly_variable_costs))
            st.metric("Profit", format_currency(monthly_profit))
            st.metric("Profit Margin", f"{profit_margin:.1f}%")
            
        with summary_cols[1]:
            st.markdown("##### Annual")
            st.metric("Total Sales", format_currency(annual_sales))
            st.metric("Fixed Costs", format_currency(annual_fixed_costs))
            st.metric("Variable Costs", format_currency(annual_variable_costs))
            st.metric("Profit", format_currency(annual_profit))
            st.metric("Profit Margin", f"{profit_margin:.1f}%")
            
        with summary_cols[2]:
            st.markdown("##### Weekly Average")
            weekly_sales = monthly_total_sales * 12 / 52
            weekly_fixed_costs = monthly_fixed_costs * 12 / 52
            weekly_variable_costs = monthly_variable_costs * 12 / 52
            weekly_profit = monthly_profit * 12 / 52
            
            st.metric("Total Sales", format_currency(weekly_sales))
            st.metric("Fixed Costs", format_currency(weekly_fixed_costs))
            st.metric("Variable Costs", format_currency(weekly_variable_costs))
            st.metric("Profit", format_currency(weekly_profit))
            st.metric("Profit Margin", f"{profit_margin:.1f}%")
        
        # Create a pie chart of costs
        st.subheader("Cost Breakdown")
        
        # Prepare data for the pie chart
        pie_data = []
        pie_labels = []
        
        # Add fixed costs total
        if monthly_fixed_costs > 0:
            pie_data.append(monthly_fixed_costs)
            pie_labels.append("Fixed Costs")
            
        # Add variable costs total
        if monthly_variable_costs > 0:
            pie_data.append(monthly_variable_costs)
            pie_labels.append("Variable Costs")
            
        # Add profit
        if monthly_profit > 0:
            pie_data.append(monthly_profit)
            pie_labels.append("Profit")
        
        # Create the pie chart
        fig = go.Figure(data=[go.Pie(
            labels=pie_labels,
            values=pie_data,
            textinfo='label+percent',
            insidetextorientation='radial',
            hole=.3
        )])
        
        fig.update_layout(title="Monthly Sales Allocation")
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Break down variable costs
        st.subheader("Variable Costs Breakdown")
        
        # Create pie chart for variable costs
        variable_costs = latest_values['variable_costs']
        
        if variable_costs:
            fig = go.Figure(data=[go.Pie(
                labels=list(variable_costs.keys()),
                values=list(variable_costs.values()),
                textinfo='label+percent',
                insidetextorientation='radial'
            )])
            
            fig.update_layout(title="Variable Costs Distribution")
            st.plotly_chart(fig, use_container_width=True)
        
        # Add profit modeling/forecasting
        st.subheader("Profit Modeling")
        st.markdown("""
        Below you can see how different sales targets would affect your profit. 
        This shows the relationship between sales, costs, and profit based on your current cost structure.
        """)
        
        # Create data for the model
        sales_range = np.linspace(monthly_total_sales * 0.5, monthly_total_sales * 2, 100)
        
        # Calculate corresponding costs and profits
        # Assuming fixed costs remain constant, and variable costs are a percentage of sales
        variable_cost_percentage = (monthly_variable_costs / monthly_total_sales) if monthly_total_sales > 0 else 0
        fixed_costs_array = np.full_like(sales_range, monthly_fixed_costs)
        variable_costs_array = sales_range * variable_cost_percentage
        total_costs_array = fixed_costs_array + variable_costs_array
        profit_array = sales_range - total_costs_array
        
        # Create the chart
        fig = go.Figure()
        
        # Add sales line
        fig.add_trace(go.Scatter(
            x=sales_range,
            y=sales_range,
            mode='lines',
            name='Sales',
            line=dict(color='rgba(0, 128, 0, 0.8)', width=2)
        ))
        
        # Add total costs line
        fig.add_trace(go.Scatter(
            x=sales_range,
            y=total_costs_array,
            mode='lines',
            name='Total Costs',
            line=dict(color='rgba(255, 0, 0, 0.8)', width=2)
        ))
        
        # Add fixed costs line
        fig.add_trace(go.Scatter(
            x=sales_range,
            y=fixed_costs_array,
            mode='lines',
            name='Fixed Costs',
            line=dict(color='rgba(128, 0, 0, 0.5)', width=2, dash='dash')
        ))
        
        # Add profit area
        fig.add_trace(go.Scatter(
            x=sales_range,
            y=profit_array,
            mode='lines',
            name='Profit',
            line=dict(color='rgba(0, 0, 255, 0.8)', width=2),
            fill='tozeroy'
        ))
        
        # Add current position marker
        fig.add_trace(go.Scatter(
            x=[monthly_total_sales],
            y=[monthly_profit],
            mode='markers',
            name='Current Position',
            marker=dict(color='black', size=12, symbol='star')
        ))
        
        # Add break-even point
        break_even_index = np.where(profit_array >= 0)[0]
        if len(break_even_index) > 0:
            break_even_sales = sales_range[break_even_index[0]]
            fig.add_trace(go.Scatter(
                x=[break_even_sales],
                y=[0],
                mode='markers',
                name='Break-even Point',
                marker=dict(color='purple', size=10)
            ))
            
            # Add vertical line at break-even
            fig.add_shape(
                type="line",
                x0=break_even_sales,
                y0=0,
                x1=break_even_sales,
                y1=break_even_sales,
                line=dict(color="purple", width=1, dash="dot"),
            )
        
        # Customize layout
        fig.update_layout(
            title="Profit Model: Sales vs. Costs",
            xaxis_title="Monthly Sales (£)",
            yaxis_title="Amount (£)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            height=500
        )
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Add explanatory text
        st.markdown(f"""
        ### Key Insights
        
        - **Current Monthly Sales**: {format_currency(monthly_total_sales)}
        - **Current Monthly Profit**: {format_currency(monthly_profit)} ({profit_margin:.1f}%)
        - **Annual Projected Profit**: {format_currency(annual_profit)}
        
        Your profit margin of {profit_margin:.1f}% means that for every £100 in sales, you keep £{profit_margin:.1f} as profit after all costs.
        """)
        
        # If break-even point was found, add information about it
        if 'break_even_sales' in locals() and break_even_sales > 0:
            st.markdown(f"""
            - **Break-even Point**: {format_currency(break_even_sales)} monthly sales
            """)
            
            # Only calculate ratio if we have valid non-zero values
            if break_even_sales > 0:
                sales_to_breakeven_ratio = monthly_total_sales / break_even_sales
                st.markdown(f"- **Current Sales-to-Break-even Ratio**: {sales_to_breakeven_ratio:.2f}x")
            
            if monthly_total_sales < break_even_sales:
                sales_increase_needed = break_even_sales - monthly_total_sales
                st.warning(f"You need to increase monthly sales by {format_currency(sales_increase_needed)} to break even.")
            else:
                safety_margin = monthly_total_sales - break_even_sales
                st.success(f"You are operating with a safety margin of {format_currency(safety_margin)} above the break-even point.")