def format_currency(amount):
    """
    Format a number as GBP currency
    """
    return f"£{amount:,.2f}"

def calculate_profit(service_sales, retail_percentage, fixed_costs, variable_costs_percentages):
    """
    Calculate profit based on sales and costs
    
    Args:
        service_sales (float): Total service sales
        retail_percentage (float): Retail sales percentage of service sales
        fixed_costs (dict): Dictionary of fixed costs
        variable_costs_percentages (dict): Dictionary of variable costs percentages
        
    Returns:
        float: Total profit
    """
    # Calculate total sales
    retail_sales = service_sales * (retail_percentage / 100)
    total_sales = service_sales + retail_sales
    
    # Calculate total fixed costs
    total_fixed_costs = sum(fixed_costs.values())
    
    # Calculate variable costs
    total_variable_costs = 0
    for cost_name, percentage in variable_costs_percentages.items():
        if cost_name == "Retail Commission" or cost_name == "Retail Stock":
            base_value = retail_sales
        else:
            base_value = total_sales
        
        cost_value = base_value * (percentage / 100)
        total_variable_costs += cost_value
    
    # Calculate profit
    profit = total_sales - total_fixed_costs - total_variable_costs
    
    return profit
