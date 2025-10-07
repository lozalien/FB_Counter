# Simplified Facebook Activity Tracker Dashboard
import sqlite3
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import os
from functools import lru_cache
import time

# Connect to the database
DB_FILE = "facebook_tracking.db"

# Global cache with timestamp
_data_cache = {'data': None, 'timestamp': 0}
CACHE_DURATION = 10  # Cache data for 10 seconds

def get_activity_data():
    """Get activity data from database with caching"""
    global _data_cache

    current_time = time.time()

    # Return cached data if still valid
    if _data_cache['data'] is not None and (current_time - _data_cache['timestamp']) < CACHE_DURATION:
        return _data_cache['data'].copy()

    # Fetch fresh data with read-only mode and timeout
    db_uri = f'file:{DB_FILE}?mode=ro'
    try:
        # Try read-only mode first (doesn't lock the database)
        conn = sqlite3.connect(db_uri, uri=True, timeout=30.0)
    except:
        # Fallback to regular mode with long timeout if read-only fails
        conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)

    query = "SELECT timestamp, name, status FROM online_activity"
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Extract time components
    df['date'] = df['timestamp'].dt.date
    df['day_name'] = df['timestamp'].dt.day_name()
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute

    # Update cache
    _data_cache['data'] = df.copy()
    _data_cache['timestamp'] = current_time

    return df

def calculate_sessions(df, session_gap_minutes=15):
    """Calculate session data for users"""
    if len(df) < 2:
        return pd.DataFrame()
    
    # Group by user
    session_data = []
    for name, group in df.groupby('name'):
        # Sort timestamps
        user_data = group.sort_values('timestamp')
        timestamps = user_data['timestamp'].values
        
        # Calculate time diffs in minutes
        time_diffs = np.diff(timestamps) / np.timedelta64(1, 'm')
        
        # Identify session breaks
        session_breaks = np.where(time_diffs > session_gap_minutes)[0]
        session_count = len(session_breaks) + 1
        
        # Calculate session metrics
        if session_count > 0:
            # Initialize session arrays
            session_starts = [0] + [i + 1 for i in session_breaks]
            session_ends = list(session_breaks) + [len(timestamps) - 1]
            
            # Calculate lengths
            session_lengths = []
            for start_idx, end_idx in zip(session_starts, session_ends):
                start_time = timestamps[start_idx]
                end_time = timestamps[end_idx]
                duration_minutes = (end_time - start_time) / np.timedelta64(1, 'm')
                session_lengths.append(duration_minutes)
            
            avg_session = np.mean(session_lengths) if session_lengths else 0
            max_session = np.max(session_lengths) if session_lengths else 0
            total_time = np.sum(session_lengths) if session_lengths else 0
        else:
            avg_session = 0
            max_session = 0
            total_time = 0
        
        session_data.append({
            'Name': name,
            'Total Sessions': session_count,
            'Average Session (min)': round(avg_session, 2),
            'Max Session (min)': round(max_session, 2),
            'Total Online (min)': round(total_time, 2),
            'First Seen': user_data['timestamp'].min(),
            'Last Seen': user_data['timestamp'].max(),
            'Days Active': user_data['date'].nunique()
        })
    
    return pd.DataFrame(session_data).sort_values('Total Online (min)', ascending=False)

# Create the Dash app with dark theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

# Custom CSS for modern dark theme with glass-morphism
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Dark Theme Base */
            body {
                background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
                background-attachment: fixed;
                color: #e0e0e0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }

            /* Glass-morphism Container */
            .container-fluid {
                backdrop-filter: blur(10px);
                background: rgba(255, 255, 255, 0.03);
                border-radius: 20px;
                padding: 30px;
                margin: 20px auto;
                max-width: 98%;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }

            /* Header Styling */
            h1, h2, h3, h4 {
                color: #ffffff;
                font-weight: 600;
                text-shadow: 0 0 20px rgba(139, 92, 246, 0.5);
                letter-spacing: 0.5px;
            }

            h1 {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-size: 2.8rem;
                margin-bottom: 30px;
            }

            /* Card Styling with Glass-morphism */
            .card, .tab-content, .tab-pane {
                background: rgba(255, 255, 255, 0.05) !important;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                border-radius: 15px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                transition: all 0.3s ease;
            }

            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 12px 40px 0 rgba(139, 92, 246, 0.3);
            }

            /* Tab Styling */
            .nav-tabs {
                border-bottom: 2px solid rgba(139, 92, 246, 0.3);
                margin-bottom: 30px;
            }

            .nav-tabs .nav-link {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #a0a0a0;
                border-radius: 10px 10px 0 0;
                margin-right: 5px;
                transition: all 0.3s ease;
            }

            .nav-tabs .nav-link:hover {
                background: rgba(139, 92, 246, 0.2);
                color: #ffffff;
                border-color: rgba(139, 92, 246, 0.5);
            }

            .nav-tabs .nav-link.active {
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%);
                color: #ffffff;
                border-color: rgba(139, 92, 246, 0.5);
                font-weight: 600;
            }

            /* Dropdown Styling */
            .Select-control, .dropdown, div[class*="dropdown"] {
                background: rgba(255, 255, 255, 0.08) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                border-radius: 10px;
                color: #ffffff !important;
            }

            .Select-menu-outer, div[class*="menu"] {
                background: rgba(30, 30, 50, 0.95) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                border-radius: 10px;
                backdrop-filter: blur(10px);
                z-index: 9999 !important;
            }

            .Select-option, div[class*="option"] {
                background: transparent !important;
                color: #e0e0e0 !important;
            }

            .Select-option:hover, div[class*="option"]:hover {
                background: rgba(139, 92, 246, 0.3) !important;
                color: #ffffff !important;
            }

            /* Input Styling */
            .form-control, .input-group-text {
                background: rgba(255, 255, 255, 0.08) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                color: #ffffff !important;
                border-radius: 10px;
            }

            .form-control:focus {
                background: rgba(255, 255, 255, 0.12) !important;
                border-color: rgba(139, 92, 246, 0.6) !important;
                box-shadow: 0 0 15px rgba(139, 92, 246, 0.3);
            }

            /* Button Styling */
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 10px;
                padding: 10px 25px;
                font-weight: 600;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
            }

            /* Alert Styling */
            .alert {
                background: rgba(255, 255, 255, 0.08) !important;
                border: 1px solid rgba(139, 92, 246, 0.3);
                border-radius: 15px;
                backdrop-filter: blur(10px);
                color: #ffffff;
            }

            .alert-success {
                border-left: 4px solid #10b981;
                background: rgba(16, 185, 129, 0.1) !important;
            }

            .alert-warning {
                border-left: 4px solid #f59e0b;
                background: rgba(245, 158, 11, 0.1) !important;
            }

            .alert-info {
                border-left: 4px solid #3b82f6;
                background: rgba(59, 130, 246, 0.1) !important;
            }

            /* Table Styling */
            .dash-table-container {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 15px;
                overflow: hidden;
            }

            .dash-spreadsheet-container {
                background: transparent !important;
            }

            .dash-spreadsheet-container .dash-spreadsheet-inner table {
                color: #e0e0e0 !important;
            }

            /* Date Picker Styling */
            .DateInput, .DateInput_input {
                background: rgba(255, 255, 255, 0.08) !important;
                color: #ffffff !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
            }

            .DateInput_input::placeholder {
                color: rgba(255, 255, 255, 0.5) !important;
            }

            .DateRangePickerInput {
                background: rgba(255, 255, 255, 0.08) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                border-radius: 10px;
            }

            .DateRangePickerInput__withBorder {
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
            }

            .DateInput_fang {
                display: none !important;
            }

            /* Calendar Popup */
            .DayPickerKeyboardShortcuts_show__bottomRight::before {
                border-right: 33px solid rgba(30, 30, 50, 0.95) !important;
            }

            .DayPicker, .DayPicker__horizontal {
                background: rgba(30, 30, 50, 0.98) !important;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                border-radius: 10px !important;
            }

            .CalendarMonth {
                background: rgba(30, 30, 50, 0.98) !important;
                color: #e0e0e0 !important;
            }

            .CalendarMonth_caption {
                color: #ffffff !important;
                font-weight: 600;
            }

            .DayPicker_weekHeader {
                color: rgba(255, 255, 255, 0.7) !important;
            }

            .DayPicker_weekHeader_li small {
                color: rgba(255, 255, 255, 0.7) !important;
            }

            .CalendarDay, .CalendarDay__default {
                background: rgba(255, 255, 255, 0.05) !important;
                color: #e0e0e0 !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
            }

            .CalendarDay__default:hover {
                background: rgba(139, 92, 246, 0.3) !important;
                color: #ffffff !important;
                border: 1px solid rgba(139, 92, 246, 0.5) !important;
            }

            td.CalendarDay {
                background: rgba(255, 255, 255, 0.05) !important;
            }

            td.CalendarDay__default {
                background: rgba(255, 255, 255, 0.05) !important;
                color: #e0e0e0 !important;
            }

            .CalendarDay__selected, .CalendarDay__selected:active, .CalendarDay__selected:hover {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                color: #ffffff !important;
                border: 1px solid rgba(139, 92, 246, 0.5) !important;
            }

            .CalendarDay__selected_span {
                background: rgba(102, 126, 234, 0.3) !important;
                color: #ffffff !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
            }

            .CalendarDay__selected_span:hover {
                background: rgba(102, 126, 234, 0.5) !important;
                border: 1px solid rgba(139, 92, 246, 0.5) !important;
            }

            .CalendarDay__hovered_span, .CalendarDay__hovered_span:hover {
                background: rgba(139, 92, 246, 0.2) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                color: #ffffff !important;
            }

            .CalendarDay__blocked_out_of_range, .CalendarDay__blocked_out_of_range:active, .CalendarDay__blocked_out_of_range:hover {
                background: rgba(255, 255, 255, 0.02) !important;
                color: rgba(255, 255, 255, 0.3) !important;
                border: 1px solid rgba(255, 255, 255, 0.05) !important;
            }

            /* Force all calendar table cells to be dark */
            .CalendarMonth_table {
                background: rgba(30, 30, 50, 0.98) !important;
            }

            .CalendarMonth_table td {
                background: transparent !important;
            }

            /* Additional states */
            .CalendarDay__blocked_calendar, .CalendarDay__blocked_calendar:active, .CalendarDay__blocked_calendar:hover {
                background: rgba(255, 255, 255, 0.02) !important;
                color: rgba(255, 255, 255, 0.3) !important;
            }

            .CalendarDay__highlighted_calendar {
                background: rgba(102, 126, 234, 0.2) !important;
                color: #ffffff !important;
            }

            .CalendarDay__highlighted_calendar:hover {
                background: rgba(102, 126, 234, 0.3) !important;
            }

            .DayPickerNavigation_button {
                background: rgba(255, 255, 255, 0.08) !important;
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
            }

            .DayPickerNavigation_button:hover {
                background: rgba(139, 92, 246, 0.3) !important;
                border: 1px solid rgba(139, 92, 246, 0.5) !important;
            }

            .DayPickerNavigation_svg__horizontal {
                fill: #e0e0e0 !important;
            }

            .DateRangePickerInput_arrow {
                color: rgba(255, 255, 255, 0.5) !important;
            }

            .DateRangePickerInput_clearDates {
                background: rgba(255, 255, 255, 0.08) !important;
            }

            .DateRangePickerInput_clearDates:hover {
                background: rgba(139, 92, 246, 0.3) !important;
            }

            .DateRangePickerInput_clearDates_svg {
                fill: #e0e0e0 !important;
            }

            /* Override ANY white backgrounds in calendar */
            .CalendarMonth_table tbody tr td {
                background-color: rgba(255, 255, 255, 0.05) !important;
            }

            .DayPicker_transitionContainer {
                background: rgba(30, 30, 50, 0.98) !important;
            }

            /* Scrollbar Styling */
            ::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }

            ::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
            }

            ::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
            }

            ::-webkit-scrollbar-thumb:hover {
                background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
            }

            /* Chart Container - Simple styling without animations */
            .js-plotly-plot {
                border-radius: 15px;
                background: rgba(255, 255, 255, 0.03);
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            }

            /* Animation */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .row {
                animation: fadeIn 0.6s ease;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Define app layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Facebook Activity Tracker Dashboard", 
                         className="text-center my-4 text-primary"), width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            html.H4("Filter Data"),
            dcc.DatePickerRange(
                id='date-filter',
                start_date_placeholder_text="Start Date",
                end_date_placeholder_text="End Date",
                calendar_orientation='horizontal',
            ),
            html.Div(id='date-range-output', className="mt-2")
        ], width=4),
        
        dbc.Col([
            html.H4("Select User(s)"),
            dcc.Dropdown(
                id='user-dropdown',
                multi=True,
                placeholder="Select users to analyze",
            )
        ], width=8)
    ], className="mb-4"),
    
    dbc.Row([
        dbc.Col([
            html.H3("Current Online Status"),
            html.Div(id="current-status")
        ], width=12, className="mb-4")
    ]),
    
    dbc.Tabs([
        dbc.Tab(label="Activity Overview", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("Daily Activity Patterns", className="mt-3"),
                    dcc.Graph(id='daily-activity-chart')
                ], width=6),
                
                dbc.Col([
                    html.H4("Hourly Activity Patterns", className="mt-3"),
                    dcc.Graph(id='hourly-activity-chart')
                ], width=6)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.H4("Activity Heatmap", className="mt-3"),
                    dcc.Graph(id='activity-heatmap')
                ], width=12)
            ])
        ]),
        
        dbc.Tab(label="User Analysis", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("User Activity Timeline", className="mt-3"),
                    dcc.Graph(id='user-timeline')
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.H4("User Selection"),
                    dcc.Dropdown(
                        id='selected-user-dropdown',
                        placeholder="Select a user for detailed analysis",
                    ),
                ], width=12, className="mb-3")
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.H4("User Activity by Hour", className="mt-3"),
                    dcc.Graph(id='user-hour-chart')
                ], width=6),
                
                dbc.Col([
                    html.H4("User Activity by Day", className="mt-3"),
                    dcc.Graph(id='user-day-chart')
                ], width=6)
            ])
        ]),
        
        dbc.Tab(label="Session Analysis", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("Session Settings", className="mt-3"),
                    dbc.InputGroup([
                        dbc.InputGroupText("Session gap (minutes)"),
                        dbc.Input(id="session-gap", type="number", value=15, min=1, max=60),
                        dbc.Button("Calculate", id="calculate-sessions", color="primary")
                    ], className="mb-3")
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.H4("User Sessions", className="mt-3"),
                    dcc.Graph(id='session-chart')
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.H4("Session Data", className="mt-3"),
                    html.Div(id="session-table")
                ], width=12)
            ])
        ])
    ]),
    
    dbc.Row([
        dbc.Col([
            html.H3("Recent Activity Data", className="mt-4"),
            dash_table.DataTable(
                id='activity-table',
                style_table={'overflowX': 'auto'},
                style_cell={
                    'textAlign': 'left',
                    'padding': '12px',
                    'backgroundColor': 'rgba(255, 255, 255, 0.05)',
                    'color': '#e0e0e0',
                    'border': '1px solid rgba(255, 255, 255, 0.1)'
                },
                style_header={
                    'backgroundColor': 'rgba(102, 126, 234, 0.3)',
                    'fontWeight': 'bold',
                    'color': '#ffffff',
                    'border': '1px solid rgba(255, 255, 255, 0.2)',
                    'textAlign': 'left'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': 'rgba(255, 255, 255, 0.02)'
                    },
                    {
                        'if': {'state': 'active'},
                        'backgroundColor': 'rgba(102, 126, 234, 0.2)',
                        'border': '1px solid rgba(102, 126, 234, 0.5)'
                    }
                ],
                page_size=10
            )
        ], width=12)
    ])
], fluid=True)

# Callbacks to update plots

@app.callback(
    Output('user-dropdown', 'options'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date'),
    prevent_initial_call=False  # Allow initial load
)
def update_user_dropdown(start_date, end_date):
    df = get_activity_data()

    # If no date filter, use all data (faster)
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]

    # Use value_counts for faster unique extraction on large datasets
    users = sorted(df['name'].unique().tolist())
    return [{'label': user, 'value': user} for user in users]

@app.callback(
    Output('selected-user-dropdown', 'options'),
    Input('user-dropdown', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_selected_user_dropdown(selected_users, start_date, end_date):
    df = get_activity_data()
    
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    if selected_users and len(selected_users) > 0:
        users = [user for user in selected_users]
    else:
        users = sorted(df['name'].unique())
    
    return [{'label': user, 'value': user} for user in users]

@app.callback(
    Output('activity-table', 'data'),
    Output('activity-table', 'columns'),
    Input('user-dropdown', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_table(selected_users, start_date, end_date):
    df = get_activity_data()
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    if selected_users and len(selected_users) > 0:
        df = df[df['name'].isin(selected_users)]
    
    # Get most recent data
    df = df.sort_values('timestamp', ascending=False).head(100)
    
    # Format for display
    display_df = df[['timestamp', 'name', 'status']].copy()
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    columns = [{"name": i, "id": i} for i in display_df.columns]
    
    return display_df.to_dict('records'), columns

@app.callback(
    Output('daily-activity-chart', 'figure'),
    Input('user-dropdown', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_daily_chart(selected_users, start_date, end_date):
    df = get_activity_data()
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    if selected_users and len(selected_users) > 0:
        df = df[df['name'].isin(selected_users)]
    
    # Count activities by day
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Create a complete grid with all days
    all_days = pd.DataFrame({'day_name': day_order, 'count': 0})

    # Get actual counts
    actual_counts = df.groupby('day_name').size().reset_index(name='count')

    # Merge to ensure all days are present
    day_counts = all_days.merge(actual_counts, on='day_name', how='left', suffixes=('_default', '_actual'))
    day_counts['count'] = day_counts['count_actual'].fillna(0)

    # Ensure proper order
    day_counts['day_order'] = day_counts['day_name'].apply(lambda x: day_order.index(x))
    day_counts = day_counts.sort_values('day_order')

    # Create figure with colorblind-friendly colors (Tol colorscheme)
    fig = px.bar(
        day_counts,
        x='day_name',
        y='count',
        color='count',
        labels={'day_name': 'Day of Week', 'count': 'Activity Count'},
        color_continuous_scale=['#332288', '#117733', '#44AA99', '#88CCEE', '#DDCC77', '#CC6677', '#AA4499'],
        title='Activity by Day of Week'
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=60, b=40),
        coloraxis_showscale=False,
        font=dict(color='#e0e0e0', size=12),
        title=dict(
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.1)',
            linecolor='rgba(255,255,255,0.2)',
            categoryorder='array',
            categoryarray=day_order
        ),
        yaxis=dict(
            gridcolor='rgba(255,255,255,0.1)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white"
        )
    )

    # Add gradient effect to bars
    fig.update_traces(
        marker=dict(
            line=dict(color='rgba(255,255,255,0.3)', width=2)
        ),
        hovertemplate='<b>%{x}</b><br>Activity Count: %{y}<extra></extra>'
    )

    return fig

@app.callback(
    Output('hourly-activity-chart', 'figure'),
    Input('user-dropdown', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_hourly_chart(selected_users, start_date, end_date):
    df = get_activity_data()
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    if selected_users and len(selected_users) > 0:
        df = df[df['name'].isin(selected_users)]
    
    # Count activities by hour
    hour_counts = df.groupby('hour').size().reset_index(name='count')
    hour_counts = hour_counts.sort_values('hour')

    # Ensure all 24 hours are present
    all_hours = pd.DataFrame({'hour': range(24), 'count': 0})
    hour_counts = all_hours.merge(hour_counts, on='hour', how='left', suffixes=('_default', '_actual'))
    hour_counts['count'] = hour_counts['count_actual'].fillna(0)

    # Normalize counts to percentiles for color mapping
    max_count = hour_counts['count'].max()
    if max_count > 0:
        hour_counts['percentile'] = hour_counts['count'] / max_count
    else:
        hour_counts['percentile'] = 0

    # Create colorblind-friendly color scale (10 levels like OpsClock)
    colorscale = [
        '#440154', '#482475', '#414487', '#355f8d', '#2a788e',
        '#21918c', '#22a884', '#42be71', '#7ad151', '#fde724'
    ]

    def get_color(percentile):
        """Map percentile to color from 10-level scale"""
        idx = min(int(percentile * 10), 9)
        return colorscale[idx]

    # Create figure with radial bar chart (OpsClock style with segmented rings)
    fig = go.Figure()

    # Number of radial segments (rings) to display
    num_segments = 10

    # Add each hour as stacked radial segments
    for idx, row in hour_counts.iterrows():
        hour = int(row['hour'])
        count = float(row['count'])
        percentile = row['percentile']

        # Create wedge for each hour (15 degrees per hour = 360/24)
        theta_start = hour * 15
        theta_end = (hour + 1) * 15

        # Determine how many segments to fill based on count
        if max_count > 0:
            segments_to_fill = int(percentile * num_segments)
        else:
            segments_to_fill = 0

        # Add each radial segment (ring) for this hour
        for segment in range(num_segments):
            r_inner = segment
            r_outer = segment + 1

            # Determine if this segment should be filled
            if segment < segments_to_fill:
                # Calculate color based on segment position (darker inside, brighter outside)
                segment_percentile = (segment + 1) / num_segments
                color = get_color(segment_percentile)
                opacity = 0.9
            else:
                # Empty segment - very dark/transparent
                color = 'rgba(255, 255, 255, 0.05)'
                opacity = 0.3

            # Generate points for the ring segment
            theta_range = [theta_start, theta_end, theta_end, theta_start, theta_start]
            r_range = [r_inner, r_inner, r_outer, r_outer, r_inner]

            fig.add_trace(go.Scatterpolar(
                r=r_range,
                theta=theta_range,
                fill='toself',
                fillcolor=color,
                line=dict(color='rgba(255,255,255,0.2)', width=1),
                hovertemplate=f'<b>{hour:02d}:00</b><br>Count: {count:.0f}<br>Level: {segment+1}/{num_segments}<extra></extra>',
                showlegend=False,
                mode='lines',
                opacity=opacity
            ))

    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                visible=True,
                range=[0, num_segments],
                gridcolor='rgba(255,255,255,0.15)',
                gridwidth=1,
                linecolor='rgba(255,255,255,0.2)',
                tickfont=dict(color='#e0e0e0', size=10),
                showticklabels=False  # Hide labels for cleaner look
            ),
            angularaxis=dict(
                direction='clockwise',
                period=24,
                tickmode='array',
                tickvals=[i * 15 for i in range(24)],
                ticktext=[f"{i:02d}" for i in range(24)],
                gridcolor='rgba(255,255,255,0.15)',
                gridwidth=1,
                linecolor='rgba(255,255,255,0.2)',
                tickfont=dict(color='#e0e0e0', size=11),
                rotation=90  # Start at top (midnight)
            )
        ),
        title=dict(
            text='Activity by Hour of Day',
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        showlegend=False,
        margin=dict(l=80, r=80, t=80, b=80),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white",
            bordercolor='rgba(255,255,255,0.3)'
        ),
        height=500
    )

    return fig

@app.callback(
    Output('activity-heatmap', 'figure'),
    Input('user-dropdown', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_heatmap(selected_users, start_date, end_date):
    df = get_activity_data()
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    if selected_users and len(selected_users) > 0:
        df = df[df['name'].isin(selected_users)]
    
    # Create pivot table for heatmap
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Create a complete grid with all hours and days
    grid_data = []
    for day in day_order:
        for hour in range(24):
            grid_data.append({'day_name': day, 'hour': hour, 'count': 0})
    
    # Convert to DataFrame
    grid_df = pd.DataFrame(grid_data)
    
    # Get actual counts
    actual_counts = df.groupby(['day_name', 'hour']).size().reset_index(name='count')
    
    # Merge with grid to ensure all combinations exist
    merged_df = pd.merge(
        grid_df, 
        actual_counts, 
        on=['day_name', 'hour'], 
        how='left'
    )
    
    # Use actual count if available, otherwise use 0
    merged_df['count'] = merged_df['count_y'].fillna(merged_df['count_x'])

    # Pivot data for proper heatmap
    heatmap_data = merged_df.pivot(index='day_name', columns='hour', values='count')

    # Reorder rows to match day_order
    heatmap_data = heatmap_data.reindex(day_order)

    # Create heatmap with colorblind-friendly Viridis-like palette
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=[f"{h}:00" for h in range(24)],
        y=day_order,
        colorscale=['#440154', '#31688e', '#35b779', '#fde724'],  # Viridis colorblind-friendly
        hovertemplate='<b>%{y}</b><br>Hour: %{x}<br>Count: %{z}<extra></extra>',
        colorbar=dict(
            title=dict(text='Count', side='right', font=dict(color='#ffffff')),
            tickfont=dict(color='#e0e0e0'),
            outlinecolor='rgba(255,255,255,0.2)',
            outlinewidth=1,
            thickness=15,
            len=0.7
        )
    ))

    # Configure layout for square cells with responsive sizing
    fig.update_layout(
        title=dict(
            text='Activity Heatmap by Day and Hour',
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=120, r=120, t=80, b=100),
        font=dict(color='#e0e0e0', size=12),
        xaxis=dict(
            title='Hour of Day',
            side='bottom',
            tickangle=-45,
            tickmode='array',
            tickvals=list(range(24)),
            ticktext=[f"{h}:00" for h in range(24)],
            gridcolor='rgba(255,255,255,0.1)',
            showgrid=True,
            tickfont=dict(color='#e0e0e0', size=10)
        ),
        yaxis=dict(
            title='Day of Week',
            tickmode='array',
            tickvals=list(range(7)),
            ticktext=day_order,
            gridcolor='rgba(255,255,255,0.1)',
            showgrid=True,
            tickfont=dict(color='#e0e0e0', size=11)
        ),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white"
        ),
        autosize=True,
        height=400
    )

    return fig

@app.callback(
    Output('current-status', 'children'),
    Input('user-dropdown', 'value')
)
def update_current_status(selected_users):
    df = get_activity_data()
    
    # Get the most recent timestamp in the dataset
    latest_time = df['timestamp'].max()
    if pd.isna(latest_time):
        return html.Div("No recent data available")
    
    # Define "currently online" as active in the last 15 minutes
    current_time = datetime.now()
    
    if (current_time - latest_time).total_seconds() / 60 > 15:
        return html.Div([
            html.P(f"Last data update: {latest_time.strftime('%Y-%m-%d %H:%M:%S')}"),
            html.P("No real-time data available - system may not be actively scanning")
        ], className="alert alert-warning")
    
    # Get users who were online in the last 15 minutes
    recent_time = latest_time - timedelta(minutes=15)
    recent_df = df[df['timestamp'] >= recent_time]
    
    # Filter by selected users if applicable
    if selected_users and len(selected_users) > 0:
        recent_df = recent_df[recent_df['name'].isin(selected_users)]
    
    # Get unique names of recently online users
    online_users = sorted(recent_df['name'].unique())
    
    if len(online_users) == 0:
        return html.Div("No users are currently online", className="alert alert-info")
    
    return html.Div([
        html.P(f"As of {latest_time.strftime('%Y-%m-%d %H:%M:%S')}, {len(online_users)} users are online:"),
        html.Ul([html.Li(user) for user in online_users], className="list-group")
    ], className="alert alert-success")

@app.callback(
    Output('user-timeline', 'figure'),
    Input('user-dropdown', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_timeline(selected_users, start_date, end_date):
    df = get_activity_data()

    # Determine date range for filtering and display
    if start_date and end_date:
        # Use provided date filter
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df_filtered = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
        display_start = start_date
        display_end = end_date
    else:
        # Default to last 7 days
        latest_date = df['timestamp'].max()
        display_end = latest_date
        display_start = latest_date - timedelta(days=7)
        df_filtered = df[(df['timestamp'] >= display_start) & (df['timestamp'] <= display_end)]

    # Default to top users if none selected
    if not selected_users or len(selected_users) == 0:
        top_users = df_filtered['name'].value_counts().nlargest(5).index.tolist()
        selected_users = top_users
    else:
        # Limit to reasonable number for visualization
        selected_users = selected_users[:10]

    # Filter to selected users
    df_filtered = df_filtered[df_filtered['name'].isin(selected_users)]
    
    # Create timeline with colorblind-friendly colors (Tol bright palette)
    colors = ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB', '#EE7733', '#009988']

    fig = px.scatter(
        df_filtered,
        x='timestamp',
        y='name',
        color='name',
        color_discrete_sequence=colors,
        labels={'timestamp': 'Time', 'name': 'User'},
        title='User Online Activity Timeline (Last 7 Days)' if not (start_date and end_date) else 'User Online Activity Timeline',
        height=400 + (len(selected_users) * 40)  # Adjust height based on number of users
    )

    # Add trend lines with matching colors
    for idx, user in enumerate(selected_users):
        user_df = df_filtered[df_filtered['name'] == user]
        color = colors[idx % len(colors)]
        # Convert hex to rgba with transparency
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        rgba_color = f'rgba({r},{g},{b},0.2)'

        fig.add_trace(
            go.Scatter(
                x=user_df['timestamp'],
                y=[user] * len(user_df),
                mode='lines',
                line=dict(width=1, color=rgba_color),
                showlegend=False,
                hoverinfo='skip'
            )
        )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=60, b=100),
        legend_title_text='Users',
        xaxis_title='Time',
        yaxis_title='User',
        font=dict(color='#e0e0e0', size=12),
        title=dict(
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.1)',
            linecolor='rgba(255,255,255,0.2)',
            range=[display_start, display_end],
            rangeslider=dict(
                visible=True,
                bgcolor='rgba(255, 255, 255, 0.05)',
                bordercolor='rgba(139, 92, 246, 0.3)',
                borderwidth=2,
                thickness=0.08
            ),
            type='date'
        ),
        yaxis=dict(
            gridcolor='rgba(255,255,255,0.1)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        legend=dict(
            bgcolor='rgba(30, 30, 50, 0.8)',
            bordercolor='rgba(255,255,255,0.2)',
            borderwidth=1,
            font=dict(color='#e0e0e0')
        ),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white"
        )
    )

    # Update trace styling with 3D-style glowing markers
    fig.update_traces(
        marker=dict(
            size=12,
            line=dict(width=2, color='rgba(255,255,255,0.5)'),
            opacity=0.8
        ),
        selector=dict(mode='markers')
    )

    fig.update_layout(
        hovermode='closest'
    )

    return fig

@app.callback(
    [Output('user-hour-chart', 'figure'),
     Output('user-day-chart', 'figure')],
    [Input('selected-user-dropdown', 'value')],
    [State('date-filter', 'start_date'),
     State('date-filter', 'end_date')]
)
def update_user_charts(selected_user, start_date, end_date):
    df = get_activity_data()
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    # Filter to selected user
    if selected_user:
        df = df[df['name'] == selected_user]
    
    # Hour chart with gradient
    hour_counts = df.groupby('hour').size().reset_index(name='count')

    hour_fig = px.bar(
        hour_counts,
        x='hour',
        y='count',
        labels={'hour': 'Hour of Day', 'count': 'Count'},
        title=f"Activity by Hour of Day"
    )

    hour_fig.update_traces(
        marker=dict(
            color=hour_counts['count'],
            colorscale=['#332288', '#44AA99', '#DDCC77'],  # Colorblind-friendly Tol palette
            line=dict(color='rgba(255,255,255,0.3)', width=2),
            showscale=False
        ),
        hovertemplate='<b>Hour: %{x}:00</b><br>Count: %{y}<extra></extra>'
    )

    hour_fig.update_layout(
        xaxis=dict(
            tickmode='array',
            tickvals=list(range(24)),
            ticktext=[f"{h}:00" for h in range(24)],
            gridcolor='rgba(102, 126, 234, 0.15)',
            linecolor='rgba(255,255,255,0.2)',
            tickangle=-45
        ),
        yaxis=dict(
            gridcolor='rgba(102, 126, 234, 0.15)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(color='#e0e0e0', size=12),
        title=dict(
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white",
            bordercolor='rgba(102, 126, 234, 0.5)'
        ),
        bargap=0.15
    )

    # Day chart with gradient
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_counts = df.groupby('day_name').size().reset_index(name='count')

    # Ensure proper order
    day_counts['day_order'] = day_counts['day_name'].apply(lambda x: day_order.index(x) if x in day_order else -1)
    day_counts = day_counts.sort_values('day_order')

    day_fig = px.bar(
        day_counts,
        x='day_name',
        y='count',
        labels={'day_name': 'Day of Week', 'count': 'Count'},
        title=f"Activity by Day of Week"
    )

    day_fig.update_traces(
        marker=dict(
            color=day_counts['count'],
            colorscale=['#228833', '#66CCEE', '#CCBB44'],  # Colorblind-friendly Tol palette
            line=dict(color='rgba(255,255,255,0.3)', width=2),
            showscale=False
        ),
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    )

    day_fig.update_layout(
        xaxis=dict(
            categoryorder='array',
            categoryarray=day_order,
            gridcolor='rgba(67, 233, 123, 0.15)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        yaxis=dict(
            gridcolor='rgba(67, 233, 123, 0.15)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(color='#e0e0e0', size=12),
        title=dict(
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white",
            bordercolor='rgba(67, 233, 123, 0.5)'
        ),
        bargap=0.15
    )

    return hour_fig, day_fig

@app.callback(
    [Output('session-chart', 'figure'),
     Output('session-table', 'children')],
    [Input('calculate-sessions', 'n_clicks')],
    [State('session-gap', 'value'),
     State('user-dropdown', 'value'),
     State('date-filter', 'start_date'),
     State('date-filter', 'end_date')]
)
def update_session_analysis(n_clicks, session_gap, selected_users, start_date, end_date):
    # Default values
    if not session_gap:
        session_gap = 15
    
    df = get_activity_data()
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    if selected_users and len(selected_users) > 0:
        df = df[df['name'].isin(selected_users)]
    
    # Calculate session data
    session_df = calculate_sessions(df, session_gap)
    
    if len(session_df) == 0:
        return px.bar(title="No session data available"), html.Div("Not enough data to calculate sessions")
    
    # Session chart with colorblind-friendly gradient
    fig = px.bar(
        session_df.sort_values('Total Online (min)', ascending=False).head(10),
        y='Name',
        x='Total Online (min)',
        title='Top 10 Users by Total Online Time',
        color='Total Online (min)',
        color_continuous_scale=['#332288', '#117733', '#44AA99', '#88CCEE'],  # Colorblind-friendly
        labels={'Total Online (min)': 'Total Online Time (minutes)', 'Name': 'User'}
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=60, b=40),
        coloraxis_showscale=False,
        font=dict(color='#e0e0e0', size=12),
        title=dict(
            font=dict(size=18, color='#ffffff'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title='Total Online Time (minutes)',
            gridcolor='rgba(255,255,255,0.1)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        yaxis=dict(
            title='User',
            categoryorder='total ascending',
            gridcolor='rgba(255,255,255,0.1)',
            linecolor='rgba(255,255,255,0.2)'
        ),
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 50, 0.9)",
            font_size=13,
            font_color="white"
        )
    )

    fig.update_traces(
        marker=dict(
            line=dict(color='rgba(255,255,255,0.3)', width=2),
            opacity=0.9
        ),
        hovertemplate='<b>%{y}</b><br>Total Online: %{x} min<extra></extra>'
    )

    # Session table with dark styling
    table = dash_table.DataTable(
        data=session_df.to_dict('records'),
        columns=[
            {"name": "User", "id": "Name"},
            {"name": "Total Sessions", "id": "Total Sessions"},
            {"name": "Avg Session (min)", "id": "Average Session (min)"},
            {"name": "Max Session (min)", "id": "Max Session (min)"},
            {"name": "Total Online (min)", "id": "Total Online (min)"},
            {"name": "Days Active", "id": "Days Active"}
        ],
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '12px',
            'backgroundColor': 'rgba(255, 255, 255, 0.05)',
            'color': '#e0e0e0',
            'border': '1px solid rgba(255, 255, 255, 0.1)'
        },
        style_header={
            'backgroundColor': 'rgba(102, 126, 234, 0.3)',
            'fontWeight': 'bold',
            'color': '#ffffff',
            'border': '1px solid rgba(255, 255, 255, 0.2)',
            'textAlign': 'left'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgba(255, 255, 255, 0.02)'
            },
            {
                'if': {'state': 'active'},
                'backgroundColor': 'rgba(102, 126, 234, 0.2)',
                'border': '1px solid rgba(102, 126, 234, 0.5)'
            }
        ],
        page_size=10,
        sort_action='native'
    )

    return fig, table

@app.callback(
    Output('date-range-output', 'children'),
    [Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date')]
)
def update_date_range_text(start_date, end_date):
    if start_date and end_date:
        start = pd.to_datetime(start_date).strftime('%Y-%m-%d')
        end = pd.to_datetime(end_date).strftime('%Y-%m-%d')
        return f"Selected date range: {start} to {end}"
    return "Please select a date range"

# Initialize date picker with actual data range - removed circular dependency
# This now only runs once on page load, not when dropdowns change
@app.callback(
    [Output('date-filter', 'min_date_allowed'),
     Output('date-filter', 'max_date_allowed'),
     Output('date-filter', 'initial_visible_month')],
    [Input('activity-table', 'id')]  # Dummy input that only fires once
)
def initialize_date_picker(_):
    try:
        df = get_activity_data()

        if len(df) > 0:
            min_date = df['timestamp'].min().date()
            max_date = df['timestamp'].max().date()

            return min_date, max_date, max_date
        else:
            today = datetime.now().date()
            return today, today, today
    except Exception as e:
        print(f"Error initializing date picker: {e}")
        today = datetime.now().date()
        return today, today, today

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8050)  # Using the fixed run method
