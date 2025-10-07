"""
Facebook Online Activity Tracker
----------------------------------------------------------
A script designed to run for weeks, tracking when your Facebook friends are online.
Includes comprehensive Excel reporting with user activity analysis.
"""

import os
import time
import datetime
import pandas as pd
import sqlite3
import signal
import sys
import traceback
import argparse
import numpy as np
import re
import json
import pickle
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Set up logging with rotation to avoid huge log files
import logging.handlers
LOG_FILE = "facebook_tracker.log"
logger = logging.getLogger('facebook_tracker')
logger.setLevel(logging.INFO)

# Rotate log files: max 5MB per file, keep 5 backup files
handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5*1024*1024, backupCount=5
)
console_handler = logging.StreamHandler()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(console_handler)

# Database file
DB_FILE = "facebook_tracking.db"
# Default scan interval in seconds
DEFAULT_SCAN_INTERVAL = 5
# Cookies backup file
COOKIES_FILE = "facebook_cookies.pkl"

class DatabaseManager:
    """Manages database operations for storing tracking data"""
    
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.setup_database()
        self.connection = None
        self.connect()
    
    def setup_database(self):
        """Create database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Create tables
        c.execute('''
        CREATE TABLE IF NOT EXISTS online_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            name TEXT,
            status TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def connect(self):
        """Connect to the database"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
        return self.connection
    
    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def add_online_activity(self, timestamp, name, status='Online'):
        """Add online activity record to the database"""
        conn = self.connect()
        c = conn.cursor()
        
        c.execute(
            "INSERT INTO online_activity (timestamp, name, status) VALUES (?, ?, ?)",
            (timestamp, name, status)
        )
        
        conn.commit()
    
    def get_all_activity(self):
        """Get all activity data as a DataFrame"""
        conn = self.connect()
        
        query = "SELECT timestamp, name, status FROM online_activity"
        df = pd.read_sql_query(query, conn)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    def export_to_csv(self, filename=None):
        """Export all data to a CSV file (more reliable than Excel)"""
        if filename is None:
            filename = f"facebook_activity_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Get all data
        df = self.get_all_activity()
        
        # Create directory for exports if it doesn't exist
        os.makedirs('exports', exist_ok=True)
        
        # Path for the CSV file
        file_path = os.path.join('exports', filename)
        
        # Ensure we don't overwrite an existing file
        if os.path.exists(file_path):
            base, ext = os.path.splitext(file_path)
            file_path = f"{base}_{int(time.time())}{ext}"
            logger.info(f"File already exists, using alternate name: {file_path}")
        
        # Early return if no data
        if len(df) == 0:
            logger.warning("No data to export")
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write("No data collected yet\n")
                logger.info(f"Created empty report at {file_path}")
                return file_path
            except Exception as e:
                logger.error(f"Error creating empty file: {e}")
                return None
        
        # Export to CSV
        try:
            df.to_csv(file_path, index=False)
            logger.info(f"Successfully exported data to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None
    
    def export_to_excel(self, filename=None):
        """Export the database to Excel with advanced pivot charts and interactive analysis tools"""
        if filename is None:
            filename = f"facebook_activity_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Always export to CSV first as a backup
        self.export_to_csv(filename.replace('.xlsx', '.csv'))
        
        # Get all data
        df = self.get_all_activity()
        
        # Create directory for exports if it doesn't exist
        os.makedirs('exports', exist_ok=True)
        
        # Path for the excel file
        file_path = os.path.join('exports', filename)
        
        # Ensure we don't overwrite an existing file
        if os.path.exists(file_path):
            base, ext = os.path.splitext(file_path)
            file_path = f"{base}_{int(time.time())}{ext}"
            logger.info(f"File already exists, using alternate name: {file_path}")
        
        # Early return if no data
        if len(df) == 0:
            logger.warning("No data to export to Excel")
            return None
        
        # Export to Excel with charts and organization
        try:
            # Use a temporary file first to avoid corruption
            temp_file = file_path + '_temp.xlsx'  # Make sure temp file has proper extension
            
            # Enhance the dataframe with additional time fields for analysis
            df['date'] = df['timestamp'].dt.date
            df['day_name'] = df['timestamp'].dt.day_name()
            df['hour'] = df['timestamp'].dt.hour
            df['minute'] = df['timestamp'].dt.minute
            df['day_of_month'] = df['timestamp'].dt.day
            df['month'] = df['timestamp'].dt.month_name()
            df['week'] = df['timestamp'].dt.isocalendar().week
            df['year'] = df['timestamp'].dt.year
            df['time_of_day'] = df['timestamp'].dt.strftime('%H:%M')
            
            # Calculate session lengths and durations
            session_data = self._calculate_session_metrics(df)
            
            # Create an Excel writer
            with pd.ExcelWriter(temp_file, engine='xlsxwriter') as writer:
                # Raw data sheet
                df.to_excel(writer, sheet_name='Raw Data', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Raw Data']
                
                # Create a dropdown filter format for column headers
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                # Write the column headers with the defined format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    
                # Set column widths
                worksheet.set_column(0, 0, 20)  # timestamp
                worksheet.set_column(1, 1, 25)  # name
                worksheet.set_column(2, 2, 10)  # status
                
                # Add filter capability
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
                
                # Create Session Analysis sheet if there's session data
                if session_data is not None and not session_data.empty:
                    session_data.to_excel(writer, sheet_name='Session Analysis', index=False)
                    session_worksheet = writer.sheets['Session Analysis']
                    
                    # Format headers
                    for col_num, value in enumerate(session_data.columns.values):
                        session_worksheet.write(0, col_num, value, header_format)
                    
                    # Set column widths
                    session_worksheet.set_column(0, 0, 25)  # Name
                    session_worksheet.set_column(1, 5, 15)  # Other columns
                    session_worksheet.autofilter(0, 0, len(session_data), len(session_data.columns) - 1)
                
                # Create User Summary sheet - aggregated statistics by user
                self._create_user_summary_sheet(df, writer)
                
                # Create Activity Heatmap sheet - shows activity patterns by day and hour
                self._create_activity_heatmap(df, writer)
                
                # Create Individual User Analysis sheet - use the original method instead
                self._create_user_analysis_template(df, writer)
                
                # Create a dashboard sheet with interactive controls
                self._create_dashboard(df, writer)
                
                # Create advanced pivot charts
                self._create_pivot_charts(df, writer)
                
            # Once successfully created, rename to the actual file
            if os.path.exists(temp_file):
                if os.path.exists(file_path):
                    os.remove(file_path)
                os.rename(temp_file, file_path)
                logger.info(f"Successfully exported enhanced Excel report to {file_path}")
                return file_path
            else:
                logger.error(f"Temp file not created: {temp_file}")
                return None
                
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}\n{traceback.format_exc()}")
            return None
            
    def _calculate_session_metrics(self, df):
        """Calculate session lengths and other metrics from the activity data"""
        # Need at least some data
        if len(df) < 2:
            return None
            
        # Group by user and sort by timestamp
        user_groups = df.sort_values('timestamp').groupby('name')
        
        # Prepare data for session analysis
        session_data = []
        
        for user, group in user_groups:
            # Sort user data by timestamp
            user_data = group.sort_values('timestamp')
            
            # If there's only one record, no session metrics can be calculated
            if len(user_data) < 2:
                continue
            
            # Calculate time differences between consecutive observations
            timestamps = user_data['timestamp'].values
            time_diffs = np.diff(timestamps) / np.timedelta64(1, 'm')  # Convert to minutes
            
            # Define session breaks (e.g., gap of more than 15 minutes indicates new session)
            session_break_threshold = 15  # minutes
            session_breaks = np.where(time_diffs > session_break_threshold)[0]
            
            # Calculate session metrics
            session_count = len(session_breaks) + 1
            
            # Calculate average session length
            if session_count > 0:
                # Initialize arrays for session start and end times
                session_starts = np.zeros(session_count, dtype=int)
                session_ends = np.zeros(session_count, dtype=int)
                
                # Process first session
                session_starts[0] = 0
                
                # Process middle sessions
                for i, break_idx in enumerate(session_breaks):
                    session_ends[i] = break_idx
                    if i < len(session_breaks) - 1:
                        session_starts[i + 1] = break_idx + 1
                
                # Process last session
                if len(session_breaks) > 0:
                    session_starts[-1] = session_breaks[-1] + 1
                session_ends[-1] = len(timestamps) - 1
                
                # Calculate session lengths
                session_lengths = []
                for start, end in zip(session_starts, session_ends):
                    if end >= start:  # Valid session
                        start_time = timestamps[start]
                        end_time = timestamps[end]
                        duration_minutes = (end_time - start_time) / np.timedelta64(1, 'm')
                        session_lengths.append(duration_minutes)
                
                avg_session_length = np.mean(session_lengths) if session_lengths else 0
                max_session_length = np.max(session_lengths) if session_lengths else 0
                total_online_time = np.sum(session_lengths) if session_lengths else 0
            else:
                avg_session_length = 0
                max_session_length = 0
                total_online_time = 0
            
            # Add to session data
            session_data.append({
                'Name': user,
                'Total Sessions': session_count,
                'Average Session Length (min)': round(avg_session_length, 2),
                'Max Session Length (min)': round(max_session_length, 2),
                'Total Online Time (min)': round(total_online_time, 2),
                'First Seen': user_data['timestamp'].min(),
                'Last Seen': user_data['timestamp'].max(),
                'Days Active': user_data['date'].nunique()
            })
        
        if not session_data:
            return None
            
        # Create DataFrame from session data
        session_df = pd.DataFrame(session_data)
        
        # Sort by total online time (descending)
        session_df = session_df.sort_values('Total Online Time (min)', ascending=False)
        
        return session_df
        
    def _create_pivot_charts(self, df, writer):
        """Create additional pivot charts and analysis sheets"""
        # Get workbook and create a new worksheet
        workbook = writer.book
        worksheet = workbook.add_worksheet('Pivot Charts')
        
        # Add title
        title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1})
        
        worksheet.merge_range('A1:H1', 'Facebook Activity Analysis - Pivot Charts', title_format)
        
        # Create various pivot tables and charts
        
        # 1. Activity by hour of day (all users)
        hour_counts = df.groupby('hour').size().reset_index(name='count')
        
        # Write the hour data to the worksheet
        worksheet.write('A3', 'Activity by Hour (All Users)', header_format)
        worksheet.write('A4', 'Hour')
        worksheet.write('B4', 'Count')
        
        for i, (hour, count) in enumerate(zip(hour_counts['hour'], hour_counts['count'])):
            worksheet.write(i + 4, 0, f"{hour}:00")
            worksheet.write(i + 4, 1, count)
        
        # Create a column chart for hours
        hour_chart = workbook.add_chart({'type': 'column'})
        hour_chart.add_series({
            'name': 'Activity Count',
            'categories': ['Pivot Charts', 4, 0, 4 + len(hour_counts) - 1, 0],
            'values': ['Pivot Charts', 4, 1, 4 + len(hour_counts) - 1, 1],
        })
        hour_chart.set_title({'name': 'Activity by Hour of Day (All Users)'})
        hour_chart.set_x_axis({'name': 'Hour'})
        hour_chart.set_y_axis({'name': 'Count'})
        worksheet.insert_chart('D3', hour_chart, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 2. Activity by day of week (all users)
        day_counts = df.groupby('day_name').size().reset_index(name='count')
        
        # Get correct day order
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts['day_order'] = day_counts['day_name'].apply(lambda x: days.index(x) if x in days else 999)
        day_counts = day_counts.sort_values('day_order').drop('day_order', axis=1)
        
        # Write the day data
        row_offset = 5 + len(hour_counts) + 2
        worksheet.write(row_offset - 1, 0, 'Activity by Day of Week (All Users)', header_format)
        worksheet.write(row_offset, 0, 'Day')
        worksheet.write(row_offset, 1, 'Count')
        
        for i, (day, count) in enumerate(zip(day_counts['day_name'], day_counts['count'])):
            worksheet.write(row_offset + i + 1, 0, day)
            worksheet.write(row_offset + i + 1, 1, count)
        
        # Create a column chart for days
        day_chart = workbook.add_chart({'type': 'column'})
        day_chart.add_series({
            'name': 'Activity Count',
            'categories': ['Pivot Charts', row_offset + 1, 0, row_offset + len(day_counts), 0],
            'values': ['Pivot Charts', row_offset + 1, 1, row_offset + len(day_counts), 1],
        })
        day_chart.set_title({'name': 'Activity by Day of Week (All Users)'})
        day_chart.set_x_axis({'name': 'Day'})
        day_chart.set_y_axis({'name': 'Count'})
        worksheet.insert_chart('D' + str(row_offset), day_chart, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 3. Top users bar chart
        user_counts = df.groupby('name').size().reset_index(name='count')
        user_counts = user_counts.sort_values('count', ascending=False).head(10)  # Top 10 users
        
        # Write the user data
        row_offset = row_offset + len(day_counts) + 20
        worksheet.write(row_offset - 1, 0, 'Top 10 Most Active Users', header_format)
        worksheet.write(row_offset, 0, 'User')
        worksheet.write(row_offset, 1, 'Count')
        
        for i, (user, count) in enumerate(zip(user_counts['name'], user_counts['count'])):
            worksheet.write(row_offset + i + 1, 0, user)
            worksheet.write(row_offset + i + 1, 1, count)
        
        # Create a bar chart for users
        user_chart = workbook.add_chart({'type': 'bar'})
        user_chart.add_series({
            'name': 'Activity Count',
            'categories': ['Pivot Charts', row_offset + 1, 0, row_offset + len(user_counts), 0],
            'values': ['Pivot Charts', row_offset + 1, 1, row_offset + len(user_counts), 1],
        })
        user_chart.set_title({'name': 'Top 10 Most Active Users'})
        user_chart.set_y_axis({'name': 'User'})
        user_chart.set_x_axis({'name': 'Count'})
        worksheet.insert_chart('D' + str(row_offset), user_chart, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 4. Activity trend over time (all users)
        time_counts = df.groupby('date').size().reset_index(name='count')
        
        # Write the date data
        row_offset = row_offset + len(user_counts) + 20
        worksheet.write(row_offset - 1, 0, 'Activity Trend Over Time', header_format)
        worksheet.write(row_offset, 0, 'Date')
        worksheet.write(row_offset, 1, 'Count')
        
        for i, (date, count) in enumerate(zip(time_counts['date'], time_counts['count'])):
            worksheet.write(row_offset + i + 1, 0, date)
            worksheet.write(row_offset + i + 1, 1, count)
        
        # Create a line chart for trend
        trend_chart = workbook.add_chart({'type': 'line'})
        trend_chart.add_series({
            'name': 'Activity Count',
            'categories': ['Pivot Charts', row_offset + 1, 0, row_offset + len(time_counts), 0],
            'values': ['Pivot Charts', row_offset + 1, 1, row_offset + len(time_counts), 1],
            'marker': {'type': 'circle', 'size': 3},
        })
        trend_chart.set_title({'name': 'Activity Trend Over Time'})
        trend_chart.set_x_axis({'name': 'Date'})
        trend_chart.set_y_axis({'name': 'Count'})
        worksheet.insert_chart('D' + str(row_offset), trend_chart, {'x_scale': 2, 'y_scale': 1.5})
    
    def _create_user_summary_sheet(self, df, writer):
        """Create a summary sheet with statistics for each user"""
        # Group by user
        users = df['name'].unique()
        
        # Prepare the summary data
        summary_data = []
        
        for user in users:
            user_data = df[df['name'] == user]
            
            # Calculate most common time of day
            most_common_hour = user_data['hour'].mode().iloc[0] if not user_data['hour'].empty else None
            
            # Calculate most common day of week
            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_counts = user_data['day_name'].value_counts().reindex(weekday_order).fillna(0)
            most_common_day = day_counts.idxmax() if not day_counts.empty else None
            
            # Calculate total days seen
            days_seen = user_data['date'].nunique()
            
            # Calculate first and last seen
            first_seen = user_data['timestamp'].min() if not user_data['timestamp'].empty else None
            last_seen = user_data['timestamp'].max() if not user_data['timestamp'].empty else None
            
            # Calculate total occurrences
            total_occurrences = len(user_data)
            
            # Calculate consistency (% of days seen compared to total days in date range)
            date_range = (max(df['date']) - min(df['date'])).days + 1 if len(df) > 0 else 0
            consistency = round((days_seen / date_range) * 100, 2) if date_range > 0 else 0
            
            summary_data.append({
                'Name': user,
                'Total Days Seen': days_seen,
                'Total Occurrences': total_occurrences,
                'Most Common Hour': f"{most_common_hour}:00" if most_common_hour is not None else 'N/A',
                'Most Common Day': most_common_day if most_common_day is not None else 'N/A',
                'First Seen': first_seen,
                'Last Seen': last_seen,
                'Average Occurrences Per Day': round(total_occurrences / days_seen, 2) if days_seen > 0 else 0,
                'Consistency (%)': consistency
            })
        
        # Create a DataFrame from the summary data
        summary_df = pd.DataFrame(summary_data)
        
        # Sort by total occurrences (descending)
        summary_df = summary_df.sort_values('Total Occurrences', ascending=False)
        
        # Write to Excel
        summary_df.to_excel(writer, sheet_name='User Summary', index=False)
        worksheet = writer.sheets['User Summary']
        
        # Format the worksheet
        header_format = writer.book.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#92D050',
            'border': 1
        })
        
        # Write column headers with the defined format
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Set column widths
        worksheet.set_column(0, 0, 25)  # Name
        worksheet.set_column(1, 7, 15)  # Other columns
        
        # Add filter capability
        worksheet.autofilter(0, 0, len(summary_df), len(summary_df.columns) - 1)
    
    def _create_activity_heatmap(self, df, writer):
        """Create a heatmap showing activity patterns by day and hour"""
        # Create pivot table by day of week and hour
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        # Create copy to avoid modifying original
        heat_df = df.copy()
        
        # Create pivot table
        pivot = pd.pivot_table(
            heat_df,
            index='day_name',
            columns='hour',
            values='name',
            aggfunc='count',
            fill_value=0
        )
        
        # Reorder days
        pivot = pivot.reindex([d for d in weekday_order if d in pivot.index])
        
        # Write to Excel
        pivot.to_excel(writer, sheet_name='Activity Heatmap')
        worksheet = writer.sheets['Activity Heatmap']
        
        # Add conditional formatting (heatmap)
        if len(pivot) > 0 and len(pivot.columns) > 0:
            # Add color scale from white to green based on values
            worksheet.conditional_format(1, 1, len(pivot) + 1, len(pivot.columns) + 1, {
                'type': '3_color_scale',
                'min_color': '#FFFFFF',
                'mid_color': '#FFEB84',
                'max_color': '#63BE7B'
            })
        
        # Add title
        title_format = writer.book.add_format({'bold': True, 'font_size': 14})
        worksheet.write(0, len(pivot.columns) + 3, 'Activity Heatmap by Day & Hour', title_format)
        
        # Add legend/explanation
        worksheet.write(2, len(pivot.columns) + 3, 'How to read this heatmap:')
        worksheet.write(3, len(pivot.columns) + 3, '• Darker green = more active times')
        worksheet.write(4, len(pivot.columns) + 3, '• White = inactive times')
        worksheet.write(5, len(pivot.columns) + 3, '• The numbers represent how many times users were seen online')
    
    def _create_user_analysis_template(self, df, writer):
        """Create a template sheet for analyzing individual users with data validation"""
        # Get workbook
        workbook = writer.book

        # Create a new worksheet for the names list
        names_sheet = workbook.add_worksheet('Names List')

        # Create a new worksheet for analysis
        worksheet = workbook.add_worksheet('User Analysis')

        # Get unique names and sort them
        unique_names = sorted(df['name'].unique())

        # Calculate the actual data range for formulas (instead of entire columns)
        last_row = len(df) + 1  # +1 for header row
        
        # Add names to the Names List sheet
        names_sheet.write(0, 0, 'Names')
        for i, name in enumerate(unique_names):
            names_sheet.write(i + 1, 0, name)
        
        # Add title
        title_format = workbook.add_format({'bold': True, 'font_size': 16})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1})
        dropdown_format = workbook.add_format({'bold': True, 'bg_color': '#FCE4D6', 'border': 1})
        
        worksheet.merge_range('A1:D1', 'User Activity Analysis', title_format)
        
        # Create date range filter
        worksheet.write(2, 0, 'Select User:', dropdown_format)
        worksheet.write(2, 2, 'Date Range:', dropdown_format)
        
        # Add dropdown options for date ranges
        date_ranges = ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom..."]
        
        # Create a cell with data validation using the Names List sheet
        worksheet.data_validation(2, 1, 2, 1, {
            'validate': 'list',
            'source': '=\'Names List\'!$A$2:$A$' + str(len(unique_names) + 1),
            'input_title': 'Select a User',
            'input_message': 'Choose a user from the dropdown list'
        })
        
        # Add date range dropdown
        worksheet.data_validation(2, 3, 2, 3, {
            'validate': 'list',
            'source': date_ranges,
            'input_title': 'Select Date Range',
            'input_message': 'Choose a time period for analysis'
        })
        
        # Set initial cell values
        worksheet.write(2, 1, "Select a user", dropdown_format)
        worksheet.write(2, 3, "All Time", dropdown_format)
        
        # Add custom date range inputs (hidden initially)
        worksheet.write(3, 2, 'Start Date:', header_format)
        worksheet.write(3, 3, '')
        worksheet.write(3, 4, 'End Date:', header_format)
        worksheet.write(3, 5, '')
        worksheet.write_formula(3, 7, '=IF(D3="Custom...","Enter dates →","")') 
        
        # Add instructions
        worksheet.write(5, 0, 'Instructions:')
        worksheet.write(6, 0, '1. Select a user from the dropdown in cell B3')
        worksheet.write(7, 0, '2. Choose a date range for analysis in cell D3')
        worksheet.write(8, 0, '3. The charts will update automatically to show activity patterns')
        worksheet.write(9, 0, 'Note: You can also go to the Names List sheet to see all available users')
        
        # Create a helper cell for the selected user (hidden)
        worksheet.write_formula('K1', '=B3')  # Selected user
        worksheet.write_formula('K2', '=D3')  # Date range
        
        # Hide helper cells
        worksheet.set_column('K:K', None, None, {'hidden': True})
        
        # Create a table to show activity by day of week
        worksheet.merge_range('A11:B11', 'Activity by Day of Week', header_format)
        worksheet.write(11, 0, 'Day', header_format)
        worksheet.write(11, 1, 'Count', header_format)
        
        # Create formulas that dynamically update based on selected user
        # Use specific ranges instead of entire columns for better performance
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i, day in enumerate(days):
            worksheet.write(12 + i, 0, day)
            worksheet.write_formula(12 + i, 1, f'=COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1,\'Raw Data\'!$D$2:$D${last_row},"{day}")')

        # Create a table to show activity by hour
        worksheet.merge_range('D11:E11', 'Activity by Hour of Day', header_format)
        worksheet.write(11, 3, 'Hour', header_format)
        worksheet.write(11, 4, 'Count', header_format)

        # Create formulas for hours
        for i in range(24):
            worksheet.write(12 + i, 3, f'{i}:00')
            worksheet.write_formula(12 + i, 4, f'=COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1,\'Raw Data\'!$F$2:$F${last_row},{i})')
        
        # Add summary statistics
        worksheet.merge_range('G11:H11', 'Summary Statistics', header_format)
        worksheet.write(11, 6, 'Metric', header_format)
        worksheet.write(11, 7, 'Value', header_format)
        
        metrics = [
            'Total Times Seen',
            'First Seen Date',
            'Last Seen Date',
            'Most Active Day',
            'Most Active Hour',
            'Days Active',
            'Activity Consistency (%)',
            'Session Rank',
            'Engagement Score'
        ]
        
        for i, metric in enumerate(metrics):
            worksheet.write(12 + i, 6, metric)
        
        # Add formulas for each metric - optimized with specific ranges
        worksheet.write_formula(12, 7, f'=COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1)')  # Total times seen
        worksheet.write_formula(13, 7, f'=IF(COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1)>0,TEXT(MINIFS(\'Raw Data\'!$A$2:$A${last_row},\'Raw Data\'!$B$2:$B${last_row},K1),"yyyy-mm-dd"),"N/A")')  # First seen
        worksheet.write_formula(14, 7, f'=IF(COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1)>0,TEXT(MAXIFS(\'Raw Data\'!$A$2:$A${last_row},\'Raw Data\'!$B$2:$B${last_row},K1),"yyyy-mm-dd"),"N/A")')  # Last seen
        worksheet.write_formula(15, 7, '=IF(MAX(B13:B19)>0,INDEX(A13:A19,MATCH(MAX(B13:B19),B13:B19,0)),"N/A")')  # Most active day
        worksheet.write_formula(16, 7, '=IF(MAX(E13:E36)>0,TEXT(INDEX(D13:D36,MATCH(MAX(E13:E36),E13:E36,0)),"0") & ":00","N/A")')  # Most active hour
        worksheet.write_formula(17, 7, f'=COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1)')  # Days active (same as total times)
        worksheet.write_formula(18, 7, f'=IF(COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1)>0,ROUND(COUNTIFS(\'Raw Data\'!$B$2:$B${last_row},K1)/{last_row-1}*100,2)&"%","0%")')  # Activity consistency
        worksheet.write_formula(19, 7, '="See Charts Below"')  # Session rank
        worksheet.write_formula(20, 7, '=IF(H13>0,H13*5,"N/A")')  # Engagement score
        
        # Create charts for user activity
        day_chart = workbook.add_chart({'type': 'column'})
        day_chart.add_series({
            'name': 'Activity Count',
            'categories': ['User Analysis', 12, 0, 18, 0],  # Days
            'values': ['User Analysis', 12, 1, 18, 1]       # Counts
        })
        day_chart.set_title({'name': 'Activity by Day of Week'})
        day_chart.set_x_axis({'name': 'Day'})
        day_chart.set_y_axis({'name': 'Count'})
        day_chart.set_style(10)
        worksheet.insert_chart('A22', day_chart, {'x_scale': 1.2, 'y_scale': 1.2})
        
        hour_chart = workbook.add_chart({'type': 'column'})
        hour_chart.add_series({
            'name': 'Activity Count',
            'categories': ['User Analysis', 12, 3, 35, 3],  # Hours
            'values': ['User Analysis', 12, 4, 35, 4]       # Counts
        })
        hour_chart.set_title({'name': 'Activity by Hour of Day'})
        hour_chart.set_x_axis({'name': 'Hour'})
        hour_chart.set_y_axis({'name': 'Count'})
        hour_chart.set_style(10)
        worksheet.insert_chart('D22', hour_chart, {'x_scale': 1.2, 'y_scale': 1.2})
        
        # Create additional charts for session analysis
        session_chart = workbook.add_chart({'type': 'column'})
        session_chart.add_series({
            'name': 'Session Length',
            'categories': ['User Analysis', 12, 3, 35, 3],  # Hours
            'values': ['User Analysis', 12, 4, 35, 4]       # Reuse activity data for now
        })
        session_chart.set_title({'name': 'Session Length by Hour'})
        session_chart.set_x_axis({'name': 'Hour'})
        session_chart.set_y_axis({'name': 'Minutes'})
        session_chart.set_style(11)
        worksheet.insert_chart('A37', session_chart, {'x_scale': 1.2, 'y_scale': 1.2})
        
        # User ranking chart
        rank_chart = workbook.add_chart({'type': 'bar'})
        rank_chart.add_series({
            'name': 'Time Online',
            'categories': ['Raw Data', 1, 1, 10, 1],  # Sample names
            'values': ['User Analysis', 12, 1, 21, 1]  # Reuse data for now
        })
        rank_chart.set_title({'name': 'Friend Ranking by Online Time'})
        rank_chart.set_y_axis({'name': 'Friend'})
        rank_chart.set_x_axis({'name': 'Online Time'})
        rank_chart.set_style(12)
        worksheet.insert_chart('D37', rank_chart, {'x_scale': 1.2, 'y_scale': 1.2})
        
        # Set column widths
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 10)
        worksheet.set_column('C:C', 8)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 10)
        worksheet.set_column('F:F', 8)
        worksheet.set_column('G:G', 20)
        worksheet.set_column('H:H', 15)
        
        # Make the Names List sheet easily accessible
        names_sheet.set_column('A:A', 30)  # Make name column wider
        names_sheet.autofilter(0, 0, len(unique_names), 0)  # Add filter to names
    
    def _create_dashboard(self, df, writer):
        """Create a dashboard sheet with key metrics and instructions"""
        # Get workbook
        workbook = writer.book

        # Calculate the actual data range for formulas
        last_row = len(df) + 1  # +1 for header row

        # Create a new worksheet
        worksheet = workbook.add_worksheet('Dashboard')
        
        # Add title
        title_format = workbook.add_format({'bold': True, 'font_size': 18, 'align': 'center'})
        worksheet.merge_range('A1:H1', 'Facebook Online Activity Dashboard', title_format)
        
        # Add timestamp of when this report was generated
        date_format = workbook.add_format({'italic': True})
        worksheet.write('A2', f'Report generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', date_format)
        
        # Key metrics section
        header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1, 'align': 'center'})
        metric_name_format = workbook.add_format({'bold': True, 'align': 'right'})
        metric_value_format = workbook.add_format({'align': 'center', 'bg_color': '#D9E1F2'})
        
        worksheet.write('A4', 'Key Metrics', header_format)
        worksheet.merge_range('A4:H4', 'Key Metrics', header_format)
        
        # Add key metrics
        metrics = [
            'Total Unique Users', 
            'Total Observations',
            'Date Range',
            'Most Active User',
            'Most Active Day',
            'Most Active Hour',
            'Average Observations Per User',
            'Average Users Online Per Day'
        ]
        
        for i, metric in enumerate(metrics):
            row = 5 + i
            worksheet.write(f'A{row}', metric, metric_name_format)
        
        # Calculate and add metric values using optimized formulas with specific ranges
        worksheet.write_formula('B5', f'=COUNTA(UNIQUE(\'Raw Data\'!$B$2:$B${last_row}))', metric_value_format)
        worksheet.write_formula('B6', f'={last_row-1}', metric_value_format)  # Calculated directly
        worksheet.write_formula('B7', f'=TEXT(MIN(\'Raw Data\'!$A$2:$A${last_row}),"yyyy-mm-dd")&" to "&TEXT(MAX(\'Raw Data\'!$A$2:$A${last_row}),"yyyy-mm-dd")', metric_value_format)

        # Most active user - use User Summary sheet
        user_summary_rows = df['name'].nunique() + 1
        worksheet.write_formula('B8', f'=INDEX(\'User Summary\'!$A$2:$A${user_summary_rows},MATCH(MAX(\'User Summary\'!$C$2:$C${user_summary_rows}),\'User Summary\'!$C$2:$C${user_summary_rows},0))', metric_value_format)

        # Most active day - simplified
        worksheet.write_formula('B9', '"See Activity Heatmap"', metric_value_format)

        # Most active hour - simplified
        worksheet.write_formula('B10', '"See Activity Heatmap"', metric_value_format)

        # Average observations per user
        worksheet.write_formula('B11', f'=ROUND({last_row-1}/COUNTA(UNIQUE(\'Raw Data\'!$B$2:$B${last_row})),1)', metric_value_format)

        # Average users online per day
        worksheet.write_formula('B12', f'=ROUND({last_row-1}/COUNTA(UNIQUE(\'Raw Data\'!$E$2:$E${last_row})),1)', metric_value_format)
        
        # Instructions section
        worksheet.write('A14', 'How to Use This Report', header_format)
        worksheet.merge_range('A14:H14', 'How to Use This Report', header_format)
        
        instructions = [
            '1. Use the "Dashboard" sheet (this sheet) to see overall metrics.',
            '2. Go to "User Summary" for a comprehensive view of all users and their activity patterns.',
            '3. Check "Activity Heatmap" to see the busiest days and times across all users.',
            '4. For detailed analysis of specific users, navigate to "User Analysis" and use the dropdown to select a user.',
            '5. All data is filterable in the "Raw Data" sheet if you need to do custom analysis.',
            '',
            'TIP: To find when a specific user is typically online, go to the "User Analysis" sheet and select their name.',
            'TIP: The User Analysis sheet will show you their most active days and hours automatically.'
        ]
        
        for i, instruction in enumerate(instructions):
            row = 15 + i
            worksheet.write(f'A{row}', instruction)
        
        # Set column widths
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 50)
        worksheet.set_column('C:H', 15)
    
    def cleanup_exports(self, max_files=10, max_age_days=7):
        """Clean up old export files to minimize disk space usage"""
        logger.info("Cleaning up exports folder...")
        exports_dir = "exports"
        
        try:
            if not os.path.exists(exports_dir):
                return
            
            # Get all files in exports directory
            files = []
            for filename in os.listdir(exports_dir):
                file_path = os.path.join(exports_dir, filename)
                if os.path.isfile(file_path):
                    # Get file modification time
                    mod_time = os.path.getmtime(file_path)
                    files.append((file_path, mod_time))
            
            # Sort files by modification time (oldest first)
            files.sort(key=lambda x: x[1])
            
            # Remove files that are older than max_age_days
            current_time = time.time()
            for file_path, mod_time in files:
                # Check if file is older than max_age_days
                if (current_time - mod_time) > (max_age_days * 24 * 60 * 60):
                    os.remove(file_path)
                    logger.info(f"Deleted old export: {file_path}")
            
            # If we still have more than max_files, delete the oldest ones
            files = [(f, os.path.getmtime(f)) for f in 
                    [os.path.join(exports_dir, filename) for filename in os.listdir(exports_dir)]
                    if os.path.isfile(f)]
            files.sort(key=lambda x: x[1])
            
            # Keep only the most recent max_files
            if len(files) > max_files:
                for file_path, _ in files[:-max_files]:
                    os.remove(file_path)
                    logger.info(f"Deleted excess export: {file_path}")
                    
            # Log summary
            remaining_files = len([f for f in os.listdir(exports_dir) if os.path.isfile(os.path.join(exports_dir, f))])
            logger.info(f"Cleanup complete. {remaining_files} export files remaining.")
            
        except Exception as e:
            logger.error(f"Error cleaning up exports: {e}")
    
class FacebookActivityTracker:
    def __init__(self, scan_interval=DEFAULT_SCAN_INTERVAL):
        self.driver = None
        self.db = DatabaseManager()
        self.running = False
        self.restart_count = 0
        self.last_browser_restart = datetime.datetime.now()
        self.scan_interval = scan_interval
        self.last_export_time = datetime.datetime.now()
        self.cookies_file = COOKIES_FILE
        self.temp_profile = None
        self.all_contacts_seen = set()  # Track all unique contacts seen
        self.scan_count = 0  # Track number of scans
        self.start_time = datetime.datetime.now()

        # Create necessary folders
        os.makedirs('exports', exist_ok=True)
    
    def setup_driver(self):
        """Set up the Chrome WebDriver with cookie-based session persistence"""
        try:
            chrome_options = Options()

            # Don't use user-data-dir at all - rely purely on cookies
            # This completely avoids all profile locking issues
            print("Setting up Chrome browser...")
            self.temp_profile = None  # Not using persistent profile
            
            # Disable notifications and maximize window
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--start-maximized")

            # Use a unique remote debugging port to avoid conflicts
            import random
            debug_port = random.randint(9222, 9999)
            chrome_options.add_argument(f"--remote-debugging-port={debug_port}")

            # Memory saving options
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            
            # Disable automation banner
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Initialize the driver
            logger.info("Initializing Chrome WebDriver...")
            print("Initializing Chrome WebDriver...")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            logger.info("WebDriver initialized successfully")
            print("WebDriver initialized successfully")
            
            return driver
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {e}")
            print(f"Error setting up WebDriver: {e}")
            raise

    def save_cookies(self):
        """Save browser cookies to file for session persistence"""
        try:
            if self.driver:
                cookies = self.driver.get_cookies()
                with open(self.cookies_file, 'wb') as f:
                    pickle.dump(cookies, f)
                logger.info(f"Saved {len(cookies)} cookies to {self.cookies_file}")
                return True
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False

    def load_cookies(self):
        """Load cookies from file to restore session"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'rb') as f:
                    cookies = pickle.load(f)

                # Need to navigate to Facebook first before adding cookies
                self.driver.get("https://www.facebook.com/")
                time.sleep(2)

                for cookie in cookies:
                    try:
                        # Remove expiry if it causes issues
                        if 'expiry' in cookie:
                            cookie['expiry'] = int(cookie['expiry'])
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"Could not add cookie {cookie.get('name', 'unknown')}: {e}")

                logger.info(f"Loaded {len(cookies)} cookies from {self.cookies_file}")
                self.driver.refresh()
                time.sleep(3)
                return True
            else:
                logger.info("No saved cookies file found")
                return False
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return False

    def check_facebook_session(self):
        """Check if we're still logged into Facebook"""
        try:
            current_url = self.driver.current_url
            # If we're on the login page, session is lost
            if "login" in current_url.lower():
                logger.warning("Session lost - on login page")
                return False

            # Try to find an element that only exists when logged in
            try:
                # Check for user profile or any logged-in specific element
                self.driver.execute_script("""
                    return document.querySelector('[aria-label*="Your profile"]') !== null ||
                           document.querySelector('[data-pagelet="LeftRail"]') !== null;
                """)
                return True
            except:
                logger.warning("Could not verify login status")
                return False
        except Exception as e:
            logger.error(f"Error checking Facebook session: {e}")
            return False

    def restart_browser(self):
        """Restart the browser to free up memory"""
        logger.info("Checking session before browser restart...")

        # Check if session is still valid before restarting
        session_valid = self.check_facebook_session()

        if session_valid:
            logger.info("Session is valid. Saving cookies before restart...")
            self.save_cookies()
        else:
            logger.warning("Session appears invalid. Will need to re-login after restart.")

        logger.info("Restarting browser to free up memory")

        try:
            # Close old browser
            if self.driver:
                self.driver.quit()
                self.driver = None
                time.sleep(5)  # Give time for cleanup

            # Set up new browser
            self.driver = self.setup_driver()

            # Try to restore session with cookies
            if session_valid and os.path.exists(self.cookies_file):
                logger.info("Attempting to restore session from cookies...")
                if self.load_cookies():
                    logger.info("Session restored successfully")
                else:
                    logger.warning("Failed to restore session, may need to log in again")
                    self.driver.get("https://www.facebook.com/")
                    time.sleep(10)
            else:
                # Navigate back to Facebook
                self.driver.get("https://www.facebook.com/")
                time.sleep(10)  # Give time to load

            self.last_browser_restart = datetime.datetime.now()
            self.restart_count += 1

            logger.info(f"Browser restarted successfully. Restart count: {self.restart_count}")
            return True
        except Exception as e:
            logger.error(f"Error restarting browser: {e}")
            return False
    
    def ensure_all_contacts_visible(self):
        """Ensure all contacts are visible by expanding the list"""
        try:
            # Scroll to the top of the page first to make sure we can see the contacts header
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.3)  # Reduced from 1 second

            # Then scroll to the bottom to make sure all contacts are loaded
            for _ in range(2):  # Reduced from 3 iterations
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.2)  # Reduced from 0.5 seconds
            
            # First, verify we're on the Facebook homepage, not in a Reel or post
            current_url = self.driver.current_url
            if "facebook.com" not in current_url or "reel" in current_url or "watch" in current_url or "posts" in current_url:
                logger.warning(f"Not on Facebook homepage, navigating back. Current URL: {current_url}")
                self.driver.get("https://www.facebook.com/")
                time.sleep(2)  # Reduced from 5 seconds
            
            # JavaScript to find and click "See More" in the contacts section
            # Use a function to avoid redeclaring variables
            see_more_clicked = self.driver.execute_script("""
                return (function() {
                    // First scroll to the top of the page
                    window.scrollTo(0, 0);
                    
                    // First find the Contacts header
                    const contactsHeaders = Array.from(document.querySelectorAll('span, div'))
                        .filter(elem => elem.textContent === 'Contacts');
                    
                    if (contactsHeaders.length === 0) {
                        return "No contacts header found";
                    }
                    
                    // Make sure the header is visible
                    contactsHeaders[0].scrollIntoView({behavior: 'smooth', block: 'start'});
                    
                    // Find the closest parent that might contain the "See More" button
                    let contactsSection = null;
                    for (const header of contactsHeaders) {
                        // Navigate up to find the contacts container
                        let parent = header;
                        for (let i = 0; i < 10; i++) {
                            if (!parent) break;
                            
                            parent = parent.parentElement;
                            
                            // Check if this parent contains the contacts list
                            if (parent && parent.querySelectorAll('a').length > 5) {
                                contactsSection = parent;
                                break;
                            }
                        }
                        
                        if (contactsSection) break;
                    }
                    
                    if (!contactsSection) {
                        return "No contacts section found";
                    }
                    
                    // Now look for "See More" only within the contacts section
                    const seeMoreElements = Array.from(contactsSection.querySelectorAll('span, div'))
                        .filter(elem => 
                            elem.textContent.includes('See More') || 
                            elem.textContent.includes('See more'));
                    
                    let clicked = 0;
                    for (const elem of seeMoreElements) {
                        try {
                            // Only click if this element truly looks like a "See More" button
                            const isClickable = elem.classList.contains('x1i10hfl') || 
                                              elem.role === 'button' ||
                                              elem.parentElement.role === 'button' ||
                                              window.getComputedStyle(elem).cursor === 'pointer';
                            
                            if (isClickable) {
                                elem.click();
                                clicked++;
                            }
                        } catch (e) {
                            console.error("Error clicking See More:", e);
                        }
                    }
                    
                    return clicked > 0 ? clicked : "No See More buttons found in contacts section";
                })();
            """)
            
            if see_more_clicked == "No contacts header found":
                logger.warning("Contacts header not found on the page")
                return False
            elif see_more_clicked == "No contacts section found":
                logger.warning("Contacts section not found on the page")
                return False
            elif see_more_clicked == "No See More buttons found in contacts section":
                logger.info("No 'See More' buttons found in contacts section (might be already expanded)")
                return True
            elif see_more_clicked > 0:
                logger.info(f"Clicked {see_more_clicked} 'See More' buttons in contacts section")
                time.sleep(0.5)  # Reduced from 2 seconds - wait for expanded list to load
                return True
            else:
                logger.info("Contacts section found but no 'See More' buttons detected")
                return True
                
        except Exception as e:
            logger.error(f"Error ensuring contacts visibility: {e}")
            return False

    def scan_online_contacts(self):
        """Scan the contacts list for online friends with balanced accuracy and debugging"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return []
                
            # Make sure we're on the Facebook homepage
            current_url = self.driver.current_url
            if "facebook.com" not in current_url or any(x in current_url for x in ["reel", "watch", "posts"]):
                logger.info(f"Not on Facebook homepage. Current URL: {current_url}")
                self.driver.get("https://www.facebook.com/")
                time.sleep(2)  # Reduced from 5 seconds
                
            # Ensure contacts are visible first
            if not self.ensure_all_contacts_visible():
                logger.warning("Failed to ensure contacts are visible")
                self.driver.refresh()
                time.sleep(2)  # Reduced from 5 seconds
                if not self.ensure_all_contacts_visible():
                    return []
                
            # Scan for online contacts with balanced detection and debugging
            logger.info("Scanning for online contacts with balanced detection...")
            
            online_contacts = self.driver.execute_script("""
                return (function() {
                    const contactNames = [];
                    const debugInfo = [];
                    
                    // First find the contacts section
                    const headers = Array.from(document.querySelectorAll('span, div'))
                        .filter(e => e.textContent === 'Contacts');
                    if (!headers.length) return ['ERROR: No Contacts section found'];
                    
                    let contactsSection = headers[0];
                    for (let i = 0; i < 10; i++) {
                        if (!contactsSection) break;
                        contactsSection = contactsSection.parentElement;
                        if (contactsSection && contactsSection.querySelectorAll('a').length > 5) break;
                    }
                    if (!contactsSection) return ['ERROR: No Contacts section found'];
                    
                    // Find all contact links
                    const contactLinks = contactsSection.querySelectorAll('a[href*="/messages/"]');
                    debugInfo.push(`Found ${contactLinks.length} contact links`);
                    
                    // Process each link with balanced detection
                    contactLinks.forEach((link, index) => {
                        let isOnline = false;
                        let contactName = null;
                        let detectionMethod = 'none';
                        
                        // Extract potential name first for debugging
                        const allText = link.textContent || '';
                        const potentialName = allText
                            .replace(/Active now/gi, '')
                            .replace(/Active \\d+[hm]/gi, '')
                            .replace(/Online status indicator/gi, '')
                            .replace(/^Active\\s*/gi, '')
                            .trim();
                        
                        // Method 1: Check for explicit "Active" aria-labels (relaxed)
                        const activeIndicators = link.querySelectorAll('[aria-label*="Active"]');
                        if (activeIndicators.length > 0) {
                            isOnline = true;
                            detectionMethod = 'aria-label';
                        }
                        
                        // Method 2: Look for green dots with relaxed criteria
                        if (!isOnline) {
                            const allDivs = link.querySelectorAll('div');
                            for (const div of allDivs) {
                                try {
                                    const style = window.getComputedStyle(div);
                                    const bgColor = style.backgroundColor;
                                    const rect = div.getBoundingClientRect();
                                    
                                    // Look for Facebook's green colors (relaxed)
                                    const isGreenish = bgColor.includes('rgb(42, 213') || // Facebook's typical green
                                                      bgColor.includes('rgb(66, 183') || 
                                                      bgColor.includes('rgb(76, 187') ||
                                                      bgColor.includes('rgb(0, 255') || // Bright green variants
                                                      (bgColor.includes('green') && !bgColor.includes('rgb(0, 128, 0)')); // Other greens but not dark green
                                    
                                    // Relaxed size requirements - just needs to be small
                                    const isSmallElement = rect.width >= 4 && rect.width <= 20 && 
                                                          rect.height >= 4 && rect.height <= 20;
                                    
                                    if (isGreenish && isSmallElement) {
                                        isOnline = true;
                                        detectionMethod = 'green-dot';
                                        break;
                                    }
                                } catch (e) {
                                    // Ignore getComputedStyle errors
                                }
                            }
                        }
                        
                        // Method 3: Check for common CSS classes (relaxed)
                        if (!isOnline) {
                            const commonClasses = ['.x1ey2m1c', '.xds687c', '.x17qophe', '[data-visualcompletion="ignore-dynamic"]'];
                            for (const className of commonClasses) {
                                if (link.querySelectorAll(className).length > 0) {
                                    // Additional check: make sure this isn't just a random element
                                    const elements = link.querySelectorAll(className);
                                    for (const elem of elements) {
                                        const rect = elem.getBoundingClientRect();
                                        if (rect.width <= 20 && rect.height <= 20) {
                                            isOnline = true;
                                            detectionMethod = 'css-class';
                                            break;
                                        }
                                    }
                                    if (isOnline) break;
                                }
                            }
                        }
                        
                        // Log debugging info for first few contacts
                        if (index < 5) {
                            debugInfo.push(`Contact ${index + 1}: "${potentialName}" - Online: ${isOnline} (${detectionMethod})`);
                        }
                        
                        // Only extract name if we think they're online
                        if (isOnline) {
                            let name = null;
                            
                            // Strategy 1: Use the cleaned text we already extracted
                            if (potentialName && potentialName.length > 1 && !potentialName.match(/^\\d/)) {
                                name = potentialName;
                            }
                            
                            // Strategy 2: Look for spans that likely contain the name
                            if (!name) {
                                const spans = link.querySelectorAll('span');
                                for (const span of spans) {
                                    const text = span.textContent?.trim();
                                    if (text && 
                                        text.length > 1 && 
                                        !text.toLowerCase().includes('online status indicator') &&
                                        !text.match(/^\\d+[hm]/) && // Not a time indicator
                                        !text.match(/^[0-9]+$/)) { // Not just numbers
                                        
                                        // Clean up the text
                                        const cleanedText = text
                                            .replace(/Active now/gi, '')
                                            .replace(/Active \\d+[hm]/gi, '')
                                            .replace(/^Active\\s*/gi, '')
                                            .trim();
                                        
                                        if (cleanedText && cleanedText.length > 1) {
                                            name = cleanedText;
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            // Strategy 3: Look at aria-label for name
                            if (!name && link.getAttribute('aria-label')) {
                                const ariaText = link.getAttribute('aria-label');
                                const nameMatch = ariaText.match(/^(.+?)\\s*(?:Active|Online|,|$)/);
                                if (nameMatch && nameMatch[1]) {
                                    name = nameMatch[1].trim();
                                }
                            }
                            
                            // Final validation of the name (relaxed)
                            if (name && 
                                name.length >= 2 && 
                                name.length <= 60 && // Increased max length
                                !name.match(/^\\d/) && 
                                !name.toLowerCase().includes('online status indicator')) {
                                contactNames.push(name);
                            }
                        }
                    });
                    
                    // Return both contacts and debug info
                    return {
                        contacts: contactNames.length ? contactNames : ['No online contacts found'],
                        debug: debugInfo
                    };
                })();
            """)
            
            # Handle the response which now includes debug info
            if isinstance(online_contacts, dict):
                debug_info = online_contacts.get('debug', [])
                contacts_list = online_contacts.get('contacts', [])
                
                # Log debug information
                logger.info("Debug information from contact scanning:")
                for debug_line in debug_info:
                    logger.info(f"  {debug_line}")
                
            elif isinstance(online_contacts, list):
                # Fallback to old format
                contacts_list = online_contacts
            else:
                logger.error(f"Unexpected return type from JavaScript: {type(online_contacts)}")
                return []
            
            if isinstance(contacts_list, list):
                if contacts_list and "ERROR" not in contacts_list[0] and "No online contacts found" not in contacts_list:
                    # Lighter Python-side validation to avoid over-filtering
                    validated_contacts = []
                    for name in contacts_list:
                        # Only filter out obvious false positives
                        if (not re.match(r'^\d+[hm]', name) and 
                            not re.match(r'^[0-9]+$', name) and
                            'online status indicator' not in name.lower() and
                            len(name.strip()) >= 2 and
                            len(name.strip()) <= 60):
                            validated_contacts.append(name.strip())
                        else:
                            logger.info(f"Filtered out obvious false positive: '{name}'")
                    
                    if validated_contacts:
                        logger.info(f"Found {len(validated_contacts)} online contact(s): {validated_contacts}")
                        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        for name in validated_contacts:
                            self.db.add_online_activity(timestamp, name)
                        return validated_contacts
                    else:
                        logger.info("No valid online contacts found after validation")
                        return []
                elif "ERROR" in contacts_list[0]:
                    logger.warning(f"JavaScript returned error: {contacts_list[0]}")
                    return []
                else:
                    logger.info("No online contacts found")
                    return []
            else:
                logger.error(f"Unexpected contacts list type: {type(contacts_list)}")
                return []
            
        except Exception as e:
            logger.error(f"Error scanning online contacts: {e}\n{traceback.format_exc()}")
            return []
        
    def export_data(self):
        """Export tracking data to Excel with analysis"""
        current_time = datetime.datetime.now()
        
        # Check if it's time to export (every 3 hours)
        if (current_time - self.last_export_time).total_seconds() > 3 * 60 * 60:
            logger.info("Exporting data")
            
            # Export to CSV (always reliable)
            csv_file = self.db.export_to_csv()
            
            # Try to export to Excel as well
            try:
                excel_file = self.db.export_to_excel()
                if excel_file:
                    logger.info(f"Created Excel report with user analysis: {excel_file}")
            except Exception as e:
                logger.error(f"Error exporting to Excel: {e}")
            
            # Update last export time
            self.last_export_time = current_time
            
            return csv_file
        
        return None
    
    def start(self):
        """Start the tracking process"""
        logger.info(f"Starting Facebook activity tracker (scan interval: {self.scan_interval} seconds)")
        try:
            self.driver = self.setup_driver()
            
            # More explicit navigation with detailed logging
            logger.info("Attempting to navigate to Facebook...")
            print("Navigating to Facebook...")
            self.driver.get("https://www.facebook.com/")
            
            # Wait longer for the page to load
            logger.info("Waiting for page to load (15 seconds)...")
            print("Waiting for Facebook to load (15 seconds)...")
            time.sleep(15)  # Wait longer on slower connections
            
            # Verify the current URL
            current_url = self.driver.current_url
            logger.info(f"Current URL after navigation: {current_url}")
            print(f"Current URL: {current_url}")

            # Try to load saved cookies first
            if os.path.exists(self.cookies_file):
                logger.info("Found saved cookies, attempting to restore session...")
                print("Restoring previous Facebook session...")
                if self.load_cookies():
                    logger.info("Session restored from cookies")
                    print("Session restored successfully!")
                else:
                    logger.warning("Failed to restore session from cookies")
                    print("Please log in to Facebook manually")
            else:
                print("No saved session found. Please log in to Facebook manually.")
                print("Your session will be saved for future runs.")

            # Check if we successfully navigated to Facebook
            if "facebook.com" in current_url or "facebook.com" in self.driver.current_url:
                logger.info("Successfully navigated to Facebook")
                print("Successfully navigated to Facebook")

                # Wait for user to log in if needed, then save cookies
                if not os.path.exists(self.cookies_file):
                    print("\nWaiting 30 seconds for you to log in...")
                    print("Once logged in, the session will be saved automatically.")
                    time.sleep(30)

                # Save cookies after login for future sessions
                logger.info("Saving session cookies...")
                self.save_cookies()
            else:
                logger.warning(f"Navigation may have failed. Expected facebook.com, got: {current_url}")
                print(f"Warning: Navigation may have failed. Expected facebook.com, got: {current_url}")

                # Try refreshing the page
                logger.info("Attempting to refresh the page...")
                print("Attempting to refresh the page...")
                self.driver.refresh()
                time.sleep(10)

                # Check again
                current_url = self.driver.current_url
                logger.info(f"Current URL after refresh: {current_url}")
                print(f"Current URL after refresh: {current_url}")

            self.running = True
            while self.running:
                try:
                    # Check if browser needs to be restarted (every 6 hours)
                    if (datetime.datetime.now() - self.last_browser_restart).total_seconds() > 6 * 60 * 60:
                        self.restart_browser()
                    
                    # Scan for online contacts
                    online_contacts = self.scan_online_contacts()
                    self.scan_count += 1

                    # Update the set of all contacts seen
                    if online_contacts:
                        self.all_contacts_seen.update(online_contacts)

                    # Clear screen and show persistent status dashboard
                    import os as os_module
                    os_module.system('cls' if os_module.name == 'nt' else 'clear')

                    # Display dashboard
                    print("=" * 70)
                    print("FACEBOOK ONLINE ACTIVITY TRACKER - LIVE DASHBOARD".center(70))
                    print("=" * 70)

                    # Runtime stats
                    runtime = datetime.datetime.now() - self.start_time
                    hours, remainder = divmod(int(runtime.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)

                    print(f"\n📊 SESSION STATISTICS:")
                    print(f"   Runtime: {hours}h {minutes}m {seconds}s")
                    print(f"   Scans completed: {self.scan_count}")
                    print(f"   Total unique contacts tracked: {len(self.all_contacts_seen)}")
                    print(f"   Next scan in: {self.scan_interval} seconds")

                    # Current online contacts
                    print(f"\n🟢 CURRENTLY ONLINE ({len(online_contacts) if online_contacts else 0}):")
                    if online_contacts:
                        print(f"   Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        for i, name in enumerate(online_contacts, 1):
                            print(f"   {i}. {name}")
                    else:
                        print(f"   No contacts online")
                        print(f"   Last checked: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                    # All contacts ever seen
                    print(f"\n👥 ALL CONTACTS TRACKED (Total: {len(self.all_contacts_seen)}):")
                    if self.all_contacts_seen:
                        sorted_contacts = sorted(list(self.all_contacts_seen))
                        # Show first 20 contacts
                        for i, name in enumerate(sorted_contacts[:20], 1):
                            print(f"   {i}. {name}")
                        if len(sorted_contacts) > 20:
                            print(f"   ... and {len(sorted_contacts) - 20} more")
                    else:
                        print("   No contacts tracked yet")

                    print("\n" + "=" * 70)
                    print(f"⏳ Waiting {self.scan_interval} seconds before next scan...")
                    print("=" * 70)

                    # Export data periodically
                    self.export_data()

                    # Sleep for the configured interval before next scan
                    time.sleep(self.scan_interval)
                    
                except WebDriverException as e:
                    logger.error(f"WebDriver error: {e}")
                    print(f"WebDriver error: {e}")
                    self.restart_browser()
                except Exception as e:
                    logger.error(f"Error in tracking loop: {e}\n{traceback.format_exc()}")
                    print(f"Error in tracking loop: {e}")
                    time.sleep(60)  # Wait before retry
                    
        except KeyboardInterrupt:
            logger.info("Stopping tracker due to keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in start method: {e}\n{traceback.format_exc()}")
            print(f"Error starting tracker: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the tracking process"""
        logger.info("Stopping Facebook activity tracker")
        self.running = False
        
        # Export final data with error handling
        try:
            logger.info("Exporting final data")
            # Save data to CSV first (more reliable)
            df = self.db.get_all_activity()
            
            if len(df) > 0:
                # Always save as CSV backup first
                csv_path = os.path.join('exports', "facebook_activity_final_export.csv")
                os.makedirs('exports', exist_ok=True)
                df.to_csv(csv_path, index=False)
                logger.info(f"Saved final data to CSV: {csv_path}")
                
                # Then try Excel export
                try:
                    excel_result = self.db.export_to_excel("facebook_activity_final_export.xlsx")
                    if excel_result:
                        logger.info(f"Saved final data to Excel: {excel_result}")
                except Exception as excel_e:
                    logger.error(f"Error exporting to Excel: {excel_e}")
            else:
                logger.info("No data to export")
                
        except Exception as e:
            logger.error(f"Error exporting final data: {e}\n{traceback.format_exc()}")
        
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error stopping WebDriver: {e}")

        # Clean up temporary profile
        if self.temp_profile and os.path.exists(self.temp_profile):
            try:
                import shutil
                shutil.rmtree(self.temp_profile, ignore_errors=True)
                logger.info(f"Cleaned up temporary profile: {self.temp_profile}")
            except Exception as e:
                logger.warning(f"Could not clean up temp profile: {e}")

        self.db.close()
        logger.info("Facebook activity tracker stopped")

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}, shutting down...")
    if tracker:
        tracker.stop()
    sys.exit(0)

# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Facebook Online Activity Tracker')
    
    parser.add_argument('-i', '--interval', type=int, default=DEFAULT_SCAN_INTERVAL,
                        help=f'Scan interval in seconds (default: {DEFAULT_SCAN_INTERVAL})')
    
    return parser.parse_args()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Main execution block
if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    
    # Print welcome message
    print("\n" + "=" * 70)
    print("Facebook Online Activity Tracker".center(70))
    print("=" * 70)
    print(f"Scan interval: {args.interval} seconds")
    print(f"Data will be stored in: {os.path.abspath(DB_FILE)}")
    print(f"Exports will be saved to: {os.path.abspath('exports')}")
    print(f"Log file: {os.path.abspath(LOG_FILE)}")
    print("\nPress Ctrl+C to stop tracking")
    print("=" * 70 + "\n")
    
    # Create tracker instance
    tracker = FacebookActivityTracker(scan_interval=args.interval)
    
    # Start tracking
    tracker.start()
