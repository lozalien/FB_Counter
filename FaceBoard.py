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

# Connect to the database
DB_FILE = "facebook_tracking.db"

def get_activity_data():
    """Get activity data from database"""
    conn = sqlite3.connect(DB_FILE)
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

# Create the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

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
                    'padding': '10px'
                },
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold'
                },
                page_size=10
            )
        ], width=12)
    ])
], fluid=True)

# Callbacks to update plots

@app.callback(
    Output('user-dropdown', 'options'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_user_dropdown(start_date, end_date):
    df = get_activity_data()
    
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    users = sorted(df['name'].unique())
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
    day_counts = df.groupby('day_name').size().reset_index(name='count')
    
    # Ensure proper order
    day_counts['day_order'] = day_counts['day_name'].apply(lambda x: day_order.index(x) if x in day_order else -1)
    day_counts = day_counts.sort_values('day_order')
    
    # Create figure
    fig = px.bar(
        day_counts, 
        x='day_name', 
        y='count',
        color='count',
        labels={'day_name': 'Day of Week', 'count': 'Activity Count'},
        color_continuous_scale='Viridis',
        title='Activity by Day of Week'
    )
    
    fig.update_layout(
        xaxis={'categoryorder': 'array', 'categoryarray': day_order},
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        coloraxis_showscale=False
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
    
    # Create figure with radar chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=hour_counts['count'],
        theta=hour_counts['hour'].apply(lambda x: f"{x}:00"),
        fill='toself',
        name='Activity',
        line_color='rgb(60, 179, 113)',
        fillcolor='rgba(60, 179, 113, 0.3)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, hour_counts['count'].max() * 1.1]
            )
        ),
        title='Activity by Hour of Day',
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)'
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
    
    # Create heatmap
    fig = px.density_heatmap(
        merged_df,
        x='hour',
        y='day_name',
        z='count',
        labels={'hour': 'Hour of Day', 'day_name': 'Day of Week', 'count': 'Activity Count'},
        color_continuous_scale='Viridis',
        title='Activity Heatmap by Day and Hour'
    )
    
    # Ensure proper ordering of days
    fig.update_layout(
        yaxis={'categoryorder': 'array', 'categoryarray': day_order},
        xaxis_title='Hour of Day',
        yaxis_title='Day of Week',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        coloraxis=dict(
            colorbar=dict(
                title='Count',
                titleside='right'
            )
        )
    )
    
    # Format x-axis to show hours
    fig.update_xaxes(tickvals=list(range(24)), ticktext=[f"{h}:00" for h in range(24)])
    
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
    
    # Apply filters
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    # Default to top users if none selected
    if not selected_users or len(selected_users) == 0:
        top_users = df['name'].value_counts().nlargest(5).index.tolist()
        selected_users = top_users
    else:
        # Limit to reasonable number for visualization
        selected_users = selected_users[:10]
    
    # Filter to selected users
    df = df[df['name'].isin(selected_users)]
    
    # Create timeline
    fig = px.scatter(
        df,
        x='timestamp',
        y='name',
        color='name',
        labels={'timestamp': 'Time', 'name': 'User'},
        title='User Online Activity Timeline',
        height=400 + (len(selected_users) * 40)  # Adjust height based on number of users
    )
    
    # Add trend lines
    for user in selected_users:
        user_df = df[df['name'] == user]
        fig.add_trace(
            go.Scatter(
                x=user_df['timestamp'],
                y=[user] * len(user_df),
                mode='lines',
                line=dict(width=0.5, color='rgba(0,0,0,0.3)'),
                showlegend=False
            )
        )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        legend_title_text='Users',
        xaxis_title='Time',
        yaxis_title='User'
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
    
    # Hour chart
    hour_counts = df.groupby('hour').size().reset_index(name='count')
    
    hour_fig = px.bar(
        hour_counts,
        x='hour',
        y='count',
        labels={'hour': 'Hour of Day', 'count': 'Count'},
        title=f"Activity by Hour of Day",
        color_discrete_sequence=['#3498db']
    )
    
    hour_fig.update_layout(
        xaxis=dict(
            tickmode='array',
            tickvals=list(range(24)),
            ticktext=[f"{h}:00" for h in range(24)]
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    # Day chart
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
        title=f"Activity by Day of Week",
        color_discrete_sequence=['#2ecc71']
    )
    
    day_fig.update_layout(
        xaxis={'categoryorder': 'array', 'categoryarray': day_order},
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20)
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
    
    # Session chart
    fig = px.bar(
        session_df.sort_values('Total Online (min)', ascending=False).head(10),
        y='Name',
        x='Total Online (min)',
        title='Top 10 Users by Total Online Time',
        color='Total Online (min)',
        color_continuous_scale='Viridis',
        labels={'Total Online (min)': 'Total Online Time (minutes)', 'Name': 'User'}
    )
    
    fig.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title='Total Online Time (minutes)',
        yaxis_title='User',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        coloraxis_showscale=False
    )
    
    # Session table
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
            'padding': '10px'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
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

# Initialize date picker with actual data range
@app.callback(
    [Output('date-filter', 'min_date_allowed'),
     Output('date-filter', 'max_date_allowed'),
     Output('date-filter', 'initial_visible_month'),
     Output('date-filter', 'start_date'),
     Output('date-filter', 'end_date')],
    [Input('user-dropdown', 'options')]
)
def initialize_date_picker(available_options):
    try:
        df = get_activity_data()
        
        if len(df) > 0:
            min_date = df['timestamp'].min().date()
            max_date = df['timestamp'].max().date()
            
            # Set initial date range to last 30 days or full range if less
            end_date = max_date
            start_date = max(min_date, max_date - timedelta(days=30))
            
            return min_date, max_date, end_date, start_date, end_date
        else:
            today = datetime.now().date()
            return today, today, today, None, None
    except Exception as e:
        print(f"Error initializing date picker: {e}")
        today = datetime.now().date()
        return today, today, today, None, None

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8050)  # Using the fixed run method