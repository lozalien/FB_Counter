"""
Facebook Online Activity Tracker
-------------------------------
A script that tracks and analyzes when your Facebook friends are online.
"""

import os
import time
import json
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("facebook_tracker.log"),
        logging.StreamHandler()
    ]
)

class FacebookActivityTracker:
    def __init__(self):
        self.driver = self.setup_driver()
        self.online_friends = {}
        self.activity_data = {}
        self.data_file = 'facebook_activity_data.json'
        self.load_data()
        
    def setup_driver(self):
        """Set up the Chrome WebDriver using user profile for authentication"""
        chrome_options = Options()
        
        # Load user profile to maintain authentication
        user_data_dir = os.path.expanduser('~') + "\\AppData\\Local\\Google\\Chrome\\User Data"
        chrome_options.add_argument(f"user-data-dir={user_data_dir}")
        chrome_options.add_argument("--profile-directory=Default")
        
        # Disable notifications and maximize window
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--start-maximized")
        
        # Disable automation banner
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        logging.info("WebDriver initialized successfully")
        return driver
    
    def load_data(self):
        """Load existing activity data if available"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    self.activity_data = json.load(f)
                logging.info(f"Loaded data for {len(self.activity_data)} users")
        except Exception as e:
            logging.error(f"Error loading data: {e}")
    
    def save_data(self):
        """Save activity data to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.activity_data, f, indent=2)
            logging.info("Data saved successfully")
        except Exception as e:
            logging.error(f"Error saving data: {e}")
    
    def scan_online_contacts(self):
        """Scan the contacts list for online friends and return their names"""
        try:
            # Make sure we're on Facebook
            if "facebook.com" not in self.driver.current_url:
                self.driver.get("https://www.facebook.com/")
                logging.info("Navigated to Facebook homepage")
                time.sleep(5)
            
            # Scroll to bottom to ensure contacts are visible
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Take a screenshot periodically (every 5 scans)
            current_time = datetime.datetime.now()
            if current_time.minute % 5 == 0 and current_time.second < 10:
                timestamp = current_time.strftime('%Y%m%d_%H%M%S')
                screenshot_path = f"facebook_contacts_{timestamp}.png"
                self.driver.save_screenshot(screenshot_path)
                logging.info(f"Saved screenshot to {screenshot_path}")
            
            # Use JavaScript to find online contacts in the right sidebar
            online_contacts = self.driver.execute_script("""
                // Find the contacts section
                const spans = document.querySelectorAll('span');
                const contactsHeaders = Array.from(spans).filter(span => 
                    span.textContent === 'Contacts'
                );
                
                if (contactsHeaders.length === 0) {
                    return ["ERROR: No Contacts section found"];
                }
                
                // Find online contacts (those with green dots)
                const onlineNames = [];
                
                // For each Contacts header, try to find the contacts list
                for (const header of contactsHeaders) {
                    // Navigate up to find the container
                    let parent = header.parentElement;
                    for (let i = 0; i < 10; i++) {
                        if (!parent) break;
                        
                        // Look for contact elements 
                        const contactElements = parent.querySelectorAll('a');
                        if (contactElements.length > 2) {
                            // Found potential contacts container
                            for (const element of contactElements) {
                                // Skip elements that don't look like contacts
                                if (!element.href || !element.href.includes('/messages/t/')) continue;
                                
                                // Check for green dot/online status
                                let hasGreenDot = false;
                                
                                // Method 1: Check for small div elements that could be green dots
                                const divs = element.querySelectorAll('div');
                                for (const div of divs) {
                                    // Check if it's small (likely a dot)
                                    const rect = div.getBoundingClientRect();
                                    if (rect.width > 0 && rect.width <= 15 && 
                                        rect.height > 0 && rect.height <= 15) {
                                        
                                        // Get the computed style
                                        const style = window.getComputedStyle(div);
                                        const bgColor = style.backgroundColor;
                                        
                                        // Check if it has a green background color
                                        if (bgColor && (
                                            bgColor.includes('rgb(0, 255') || 
                                            bgColor.includes('rgb(0,255') || 
                                            bgColor.includes('rgb(76, 187') || 
                                            bgColor.includes('rgb(76,187') ||
                                            bgColor.includes('rgb(66, 183') || 
                                            bgColor.includes('rgb(66,183') ||
                                            bgColor.includes('rgb(42, 213') || 
                                            bgColor.includes('rgb(42,213')
                                        )) {
                                            hasGreenDot = true;
                                            break;
                                        }
                                    }
                                }
                                
                                // Method 2: Check for elements with "Active" in their aria-label
                                if (!hasGreenDot) {
                                    const activeElements = element.querySelectorAll('[aria-label*="Active"]');
                                    if (activeElements.length > 0) {
                                        hasGreenDot = true;
                                    }
                                }
                                
                                // Method 3: Check for specific classes often used for green dots
                                if (!hasGreenDot) {
                                    const dotElements = element.querySelectorAll('.x1ey2m1c, .xds687c, .x17qophe');
                                    if (dotElements.length > 0) {
                                        hasGreenDot = true;
                                    }
                                }
                                
                                // If online, get the name
                                if (hasGreenDot) {
                                    // Find the name in this contact
                                    const spans = element.querySelectorAll('span');
                                    for (const span of spans) {
                                        const name = span.textContent.trim();
                                        // Filter out non-name text and specific false positives
                                        if (name && 
                                            name.length > 1 && 
                                            name !== 'Contacts' && 
                                            name !== 'Online status indicator' &&
                                            !name.includes('Active') &&
                                            !name.includes('New')) {
                                            
                                            // Check if visible
                                            const style = window.getComputedStyle(span);
                                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                                // Only add if not already in the list
                                                if (!onlineNames.includes(name)) {
                                                    onlineNames.push(name);
                                                }
                                                break; // Found a name, move to next contact
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        parent = parent.parentElement;
                    }
                }
                
                return onlineNames;
            """)
            
            if not online_contacts:
                logging.warning("No online contacts found")
                return []
                
            if isinstance(online_contacts, list) and len(online_contacts) > 0 and online_contacts[0].startswith("ERROR"):
                logging.error(online_contacts[0])
                return []
                
            logging.info(f"Found {len(online_contacts)} online contacts")
            for name in online_contacts:
                logging.info(f"Online: {name}")
                
            return online_contacts
            
        except Exception as e:
            logging.error(f"Error scanning online contacts: {e}")
            return []
    
    def update_activity_data(self, online_contacts):
        """Update activity data with current online status"""
        current_time = datetime.datetime.now()
        timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Process currently online friends
        for name in online_contacts:
            user_id = name.lower().replace(' ', '_')
            
            # Add new user to tracking
            if user_id not in self.activity_data:
                self.activity_data[user_id] = {
                    'name': name,
                    'total_minutes': 0,
                    'online_since': timestamp,
                    'online_periods': [],
                    'daily_activity': {},
                    'weekly_activity': {},
                    'hourly_activity': {}
                }
                logging.info(f"Started tracking {name}")
            
            # User was offline but now online
            elif 'online_since' not in self.activity_data[user_id]:
                self.activity_data[user_id]['online_since'] = timestamp
                logging.info(f"{self.activity_data[user_id]['name']} is now online")
        
        # Check for users who went offline
        for user_id in list(self.activity_data.keys()):
            # Skip users who don't have an online_since timestamp (already offline)
            if 'online_since' not in self.activity_data[user_id]:
                continue
                
            # Check if user is still in the online list
            still_online = False
            for name in online_contacts:
                if name.lower().replace(' ', '_') == user_id:
                    still_online = True
                    break
            
            if not still_online:
                # Calculate session duration
                online_since = datetime.datetime.strptime(
                    self.activity_data[user_id]['online_since'], 
                    '%Y-%m-%d %H:%M:%S'
                )
                session_duration_minutes = (current_time - online_since).total_seconds() / 60
                
                # Update total minutes
                self.activity_data[user_id]['total_minutes'] += session_duration_minutes
                
                # Add to online periods list
                self.activity_data[user_id]['online_periods'].append({
                    'start': self.activity_data[user_id]['online_since'],
                    'end': timestamp,
                    'duration_minutes': session_duration_minutes
                })
                
                # Update daily activity stats
                day = online_since.strftime('%Y-%m-%d')
                if day not in self.activity_data[user_id]['daily_activity']:
                    self.activity_data[user_id]['daily_activity'][day] = 0
                self.activity_data[user_id]['daily_activity'][day] += session_duration_minutes
                
                # Update weekly activity stats
                week = online_since.strftime('%Y-W%U')
                if week not in self.activity_data[user_id]['weekly_activity']:
                    self.activity_data[user_id]['weekly_activity'][week] = 0
                self.activity_data[user_id]['weekly_activity'][week] += session_duration_minutes
                
                # Update hourly activity stats
                hour = online_since.strftime('%H')
                if hour not in self.activity_data[user_id]['hourly_activity']:
                    self.activity_data[user_id]['hourly_activity'][hour] = 0
                self.activity_data[user_id]['hourly_activity'][hour] += session_duration_minutes
                
                # Remove online_since property
                del self.activity_data[user_id]['online_since']
                
                logging.info(f"{self.activity_data[user_id]['name']} went offline after {session_duration_minutes:.1f} minutes")
        
        # Save the updated data
        self.save_data()
        
        # Return currently online users
        online_users = {}
        for name in online_contacts:
            user_id = name.lower().replace(' ', '_')
            if user_id in self.activity_data:
                online_users[user_id] = self.activity_data[user_id]
            else:
                online_users[user_id] = {'name': name}
        
        return online_users
    
    def export_to_excel(self):
        """Export activity data to Excel with multiple sheets and charts"""
        try:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'facebook_activity_report_{timestamp}.xlsx'
            
            # Create a Pandas Excel writer
            writer = pd.ExcelWriter(filename, engine='xlsxwriter')
            
            # Create summary dataframe
            summary_data = []
            for user_id, data in self.activity_data.items():
                is_online = 'online_since' in data
                
                # Get last seen time
                if is_online:
                    last_seen = "Currently Online"
                elif data.get('online_periods'):
                    last_seen = data['online_periods'][-1].get('end', 'Unknown')
                else:
                    last_seen = 'Never'
                
                # Get average session length
                periods = data.get('online_periods', [])
                avg_session = 0
                if periods:
                    total_duration = sum(p.get('duration_minutes', 0) for p in periods)
                    avg_session = total_duration / len(periods)
                
                summary_data.append({
                    'Name': data['name'],
                    'Total Minutes': data.get('total_minutes', 0),
                    'Session Count': len(periods),
                    'Average Session (min)': avg_session,
                    'Is Online': is_online,
                    'Last Seen': last_seen
                })
            
            # Create and save summary sheet
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Create and save daily activity sheet
            daily_data = []
            for user_id, data in self.activity_data.items():
                for day, minutes in data.get('daily_activity', {}).items():
                    daily_data.append({
                        'Name': data['name'],
                        'Date': day,
                        'Minutes': minutes
                    })
            
            if daily_data:
                daily_df = pd.DataFrame(daily_data)
                daily_df.to_excel(writer, sheet_name='Daily Activity', index=False)
            
            # Create and save hourly activity sheet
            hourly_data = []
            for user_id, data in self.activity_data.items():
                for hour, minutes in data.get('hourly_activity', {}).items():
                    hourly_data.append({
                        'Name': data['name'],
                        'Hour': hour,
                        'Minutes': minutes
                    })
            
            if hourly_data:
                hourly_df = pd.DataFrame(hourly_data)
                hourly_df.to_excel(writer, sheet_name='Hourly Activity', index=False)
            
            # Create and save session details sheet
            sessions_data = []
            for user_id, data in self.activity_data.items():
                for i, session in enumerate(data.get('online_periods', [])):
                    sessions_data.append({
                        'Name': data['name'],
                        'Session #': i + 1,
                        'Start Time': session.get('start'),
                        'End Time': session.get('end'),
                        'Duration (min)': session.get('duration_minutes', 0)
                    })
            
            if sessions_data:
                sessions_df = pd.DataFrame(sessions_data)
                sessions_df.to_excel(writer, sheet_name='Session Details', index=False)
            
            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            
            # Add a chart sheet for total activity by user
            if summary_data:
                chart_sheet = workbook.add_worksheet('Total Activity Chart')
                
                # Create a new chart object
                chart = workbook.add_chart({'type': 'bar'})
                
                # Add a series to the chart
                chart.add_series({
                    'name': 'Total Minutes Online',
                    'categories': ['Summary', 1, 0, len(summary_data), 0],
                    'values': ['Summary', 1, 1, len(summary_data), 1],
                })
                
                # Configure the chart
                chart.set_title({'name': 'Total Activity by User'})
                chart.set_x_axis({'name': 'User'})
                chart.set_y_axis({'name': 'Minutes'})
                
                # Insert the chart into the worksheet
                chart_sheet.insert_chart('A1', chart, {'x_scale': 2, 'y_scale': 2})
            
            # Add a chart sheet for hourly activity patterns
            if hourly_data:
                chart_sheet = workbook.add_worksheet('Hourly Patterns Chart')
                
                # Create a pivot table for hourly data
                pivot_table = pd.pivot_table(
                    pd.DataFrame(hourly_data),
                    values='Minutes',
                    index='Hour',
                    columns='Name',
                    aggfunc='sum'
                ).fillna(0)
                
                # Write the pivot table to a new sheet
                pivot_table.to_excel(writer, sheet_name='Hourly Pivot')
                
                # Create a new chart object
                chart = workbook.add_chart({'type': 'line'})
                
                # Add a series for each user
                for i, name in enumerate(pivot_table.columns):
                    chart.add_series({
                        'name': name,
                        'categories': ['Hourly Pivot', 1, 0, 24, 0],
                        'values': ['Hourly Pivot', 1, i+1, 24, i+1],
                    })
                
                # Configure the chart
                chart.set_title({'name': 'Activity by Hour of Day'})
                chart.set_x_axis({'name': 'Hour'})
                chart.set_y_axis({'name': 'Minutes'})
                
                # Insert the chart into the worksheet
                chart_sheet.insert_chart('A1', chart, {'x_scale': 2, 'y_scale': 2})
            
            # Save the Excel file
            writer.close()
            logging.info(f"Data exported to {filename}")
            
            return filename
            
        except Exception as e:
            logging.error(f"Error exporting to Excel: {e}")
            return None
    
    def track_continuously(self, interval_seconds=60):
        """Track online status continuously"""
        try:
            iteration = 0
            
            logging.info("Starting continuous tracking. Press Ctrl+C to stop.")
            print("\nStarting continuous tracking. Press Ctrl+C to stop.")
            
            while True:
                # Get current timestamp
                current_time = datetime.datetime.now()
                print(f"\n[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Scanning... (Iteration {iteration})")
                
                # Scan for online contacts
                online_contacts = self.scan_online_contacts()
                
                # Update activity data
                online_users = self.update_activity_data(online_contacts)
                
                # Display currently online users
                if online_users:
                    print(f"Found {len(online_users)} online contacts:")
                    for user_id, data in online_users.items():
                        print(f"- {data['name']}")
                else:
                    print("No online contacts found.")
                
                # Export data to Excel periodically (every 10 iterations)
                if iteration > 0 and iteration % 10 == 0:
                    filename = self.export_to_excel()
                    if filename:
                        print(f"Data exported to {filename}")
                
                iteration += 1
                
                # Wait for next interval
                next_scan_time = datetime.datetime.now() + datetime.timedelta(seconds=interval_seconds)
                time_to_wait = (next_scan_time - datetime.datetime.now()).total_seconds()
                
                if time_to_wait > 0:
                    print(f"Next scan in {time_to_wait:.0f} seconds...")
                    time.sleep(time_to_wait)
                
        except KeyboardInterrupt:
            print("\nTracking stopped by user")
        finally:
            # Final data export
            filename = self.export_to_excel()
            if filename:
                print(f"Final data exported to {filename}")
            
            print("Closing browser...")
            self.driver.quit()
            logging.info("Browser closed")

def main():
    """Main function to run the tracker"""
    print("Facebook Online Activity Tracker")
    print("-------------------------------")
    print("A script that tracks and analyzes when your Facebook friends are online.")
    print("IMPORTANT: You must already be logged into Facebook in Chrome.")
    
    try:
        tracker = FacebookActivityTracker()
        
        # Navigate to Facebook
        tracker.driver.get("https://www.facebook.com/")
        
        # Wait to ensure page is loaded
        time.sleep(5)
        
        # Check if we're logged in
        if "login" in tracker.driver.current_url:
            print("\nERROR: You are not logged into Facebook in Chrome.")
            print("Please login to Facebook in your Chrome browser first, then run this script again.")
            tracker.driver.quit()
            return
        
        print("\nSuccessfully connected to Facebook!")
        
        print("\n1. Start continuous tracking")
        print("2. Export current data to Excel")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            interval = int(input("Enter check interval in seconds (default 60): ") or "60")
            tracker.track_continuously(interval)
        elif choice == '2':
            filename = tracker.export_to_excel()
            if filename:
                print(f"Data exported to {filename}")
            else:
                print("Error exporting data. Check the log file for details.")
        else:
            print("Exiting program.")
            tracker.driver.quit()
                
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()