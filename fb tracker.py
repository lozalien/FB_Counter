"""
Facebook Online Activity Tracker - Long-Term Stable Version
----------------------------------------------------------
A script designed to run for weeks, tracking when your Facebook friends are online.
"""

import os
import time
import datetime
import pandas as pd
import sqlite3
import threading
import signal
import sys
import psutil
import traceback
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
    
    def get_activity_since(self, hours=24):
        """Get activity data from the last N hours"""
        conn = self.connect()
        
        # Calculate timestamp for N hours ago
        time_ago = (datetime.datetime.now() - datetime.timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        query = "SELECT timestamp, name, status FROM online_activity WHERE timestamp > ?"
        df = pd.read_sql_query(query, conn, params=(time_ago,))
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df

class FacebookActivityTracker:
    def __init__(self):
        self.driver = None
        self.report_filename = f"facebook_activity_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        self.db = DatabaseManager()
        self.running = False
        self.restart_count = 0
        self.last_browser_restart = datetime.datetime.now()
    
    def setup_driver(self):
        """Set up the Chrome WebDriver using user profile for authentication"""
        try:
            chrome_options = Options()
            
            # Load user profile to maintain authentication
            user_data_dir = os.path.expanduser('~') + "\\AppData\\Local\\Google\\Chrome\\User Data"
            chrome_options.add_argument(f"user-data-dir={user_data_dir}")
            chrome_options.add_argument("--profile-directory=Default")
            
            # Disable notifications and maximize window
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--start-maximized")
            
            # Memory saving options
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            
            # Disable automation banner
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            logger.info("WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {e}")
            raise
    
    def restart_browser(self):
        """Restart the browser to free up memory"""
        logger.info("Restarting browser to free up memory")
        
        try:
            # Close old browser
            if self.driver:
                self.driver.quit()
                self.driver = None
                time.sleep(5)  # Give time for cleanup
            
            # Set up new browser
            self.driver = self.setup_driver()
            
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
            # Scroll to the bottom to make sure contacts are visible
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
            
            # First, verify we're on the Facebook homepage, not in a Reel or post
            current_url = self.driver.current_url
            if "facebook.com" not in current_url or "reel" in current_url or "watch" in current_url or "posts" in current_url:
                logger.warning(f"Not on Facebook homepage, navigating back. Current URL: {current_url}")
                self.driver.get("https://www.facebook.com/")
                time.sleep(5)
            
            # Improved JavaScript to only click "See More" in the contacts section
            see_more_clicked = self.driver.execute_script("""
                // First find the Contacts header
                const contactsHeaders = Array.from(document.querySelectorAll('span, div'))
                    .filter(elem => elem.textContent === 'Contacts');
                
                if (contactsHeaders.length === 0) {
                    return "No contacts header found";
                }
                
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
                        // Look for CSS classes or other attributes that suggest this is a button
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
                time.sleep(2)  # Wait for expanded list to load
                return True
            else:
                logger.info("Contacts section found but no 'See More' buttons detected")
                return True
                
        except Exception as e:
            logger.error(f"Error ensuring contacts visibility: {e}")
            return False
    
    def scan_online_contacts(self):
        """Scan the contacts list for online friends using multiple methods"""
        try:
            # Make sure we're on Facebook homepage
            current_url = self.driver.current_url
            if not self.driver or "facebook.com" not in current_url or "reel" in current_url or "watch" in current_url or "posts" in current_url:
                logger.info(f"Not on Facebook homepage. Current URL: {current_url}")
                self.driver.get("https://www.facebook.com/")
                logger.info("Navigated to Facebook homepage")
                time.sleep(5)
            
            # Ensure contacts are fully visible
            if not self.ensure_all_contacts_visible():
                logger.warning("Failed to ensure contacts are visible")
                # Try refreshing and trying again
                self.driver.refresh()
                time.sleep(5)
                if not self.ensure_all_contacts_visible():
                    return []
            
            # Improved JavaScript to find individual online contacts while excluding group chats
            online_contacts = self.driver.execute_script("""
                // Function to get all online contacts
                function getOnlineContacts() {
                    // Extract all potential contact links from the entire page
                    const allLinks = document.querySelectorAll('a');
                    const potentialContactLinks = [];
                    
                    // 1. First, collect all potential contact links from the entire page
                    for (const link of allLinks) {
                        // Only include links that look like individual chat/message links
                        if (link.href && link.href.includes('/messages/t/')) {
                            potentialContactLinks.push(link);
                        }
                    }
                    
                    // If we didn't find any contact links, return an error
                    if (potentialContactLinks.length === 0) {
                        return ["ERROR: No contact links found"];
                    }
                    
                    // 2. Process all potential contact links to find those that are online
                    const onlineNames = [];
                    const processedNames = new Set(); // To prevent duplicates
                    
                    // Specific list of names to exclude (interface elements, not real contacts)
                    const excludeNames = [
                        'See all in Messenger',
                        'Meta AI', 
                        'See More',
                        'See more',
                        'Create new group',
                        'New message',
                        'New Message',
                        'Messenger',
                        'Search in Messenger'
                    ];
                    
                    for (const link of potentialContactLinks) {
                        // Skip if this is clearly a group chat
                        // A link element with more than one img element is likely a group chat
                        const imageElements = link.querySelectorAll('img');
                        if (imageElements.length > 1) {
                            continue; // Skip group chats with multiple avatars
                        }
                        
                        // Check for text that indicates this is a group or community chat
                        const linkText = link.textContent.toLowerCase();
                        if (linkText.includes('group chat') || 
                            linkText.includes('community') || 
                            linkText.includes('group conversation') ||
                            linkText.includes('gaming') ||
                            linkText.includes('messenger room') ||
                            linkText.includes('see all in messenger') || // Add specific exclusions
                            linkText.includes('meta ai')) {
                            continue; // Skip groups/communities and interface elements
                        }
                        
                        // Skip elements that contain multiple people's names (likely groups)
                        const commaCount = linkText.split(',').length - 1;
                        const andCount = linkText.split(' and ').length - 1;
                        if (commaCount > 0 || andCount > 0) {
                            continue; // Skip multi-person chats
                        }
                        
                        // Skip if aria-label suggests a group
                        const ariaLabel = link.getAttribute('aria-label') || '';
                        if (ariaLabel.includes('group') || 
                            ariaLabel.includes('Group') || 
                            ariaLabel.includes('community') ||
                            ariaLabel.includes('Community')) {
                            continue;
                        }
                        
                        // Check for online status
                        let isOnline = false;
                        
                        // Method 1: Check for green dot (small colored div)
                        const divs = link.querySelectorAll('div');
                        for (const div of divs) {
                            const rect = div.getBoundingClientRect();
                            if (rect.width > 0 && rect.width <= 15 && 
                                rect.height > 0 && rect.height <= 15) {
                                
                                const style = window.getComputedStyle(div);
                                const bgColor = style.backgroundColor;
                                
                                // Check all possible green variations
                                if (bgColor && (
                                    bgColor.includes('rgb(0, 255') || 
                                    bgColor.includes('rgb(0,255') || 
                                    bgColor.includes('rgb(76, 187') || 
                                    bgColor.includes('rgb(76,187') ||
                                    bgColor.includes('rgb(66, 183') || 
                                    bgColor.includes('rgb(66,183') ||
                                    bgColor.includes('rgb(42, 213') || 
                                    bgColor.includes('rgb(42,213') ||
                                    bgColor.includes('rgb(31, 210') || 
                                    bgColor.includes('rgb(31,210') ||
                                    bgColor.includes('rgb(95, 162') || 
                                    bgColor.includes('rgb(95,162') ||
                                    bgColor.includes('rgb(24, 119') || 
                                    bgColor.includes('rgb(24,119') ||
                                    bgColor.includes('rgb(32, 120') || 
                                    bgColor.includes('rgb(32,120') ||
                                    bgColor.includes('rgb(48, 176') || 
                                    bgColor.includes('rgb(48,176')
                                )) {
                                    isOnline = true;
                                    break;
                                }
                            }
                        }
                        
                        // Method 2: Check for elements with "Active" in their attributes
                        if (!isOnline) {
                            const activeElements = link.querySelectorAll('[aria-label*="Active"], [aria-label*="active"]');
                            if (activeElements.length > 0) {
                                isOnline = true;
                            }
                        }
                        
                        // Method 3: Check for specific CSS classes used for online indicators
                        if (!isOnline) {
                            const dotClasses = [
                                'x1ey2m1c', 'xds687c', 'x17qophe', 'x92rtbv', 
                                'x1lq5wgf', 'xgqcy7u', 'x30kzoy', 'x9f619',
                                'xzsf02u', 'x1r8uery', 'x1ypdohk'
                            ];
                            
                            for (const className of dotClasses) {
                                if (link.querySelector('.' + className)) {
                                    isOnline = true;
                                    break;
                                }
                            }
                        }
                        
                        // If online, extract the contact name
                        if (isOnline) {
                            let contactName = null;
                            
                            // Method 1: Look for name in span elements
                            const spans = link.querySelectorAll('span');
                            for (const span of spans) {
                                const text = span.textContent.trim();
                                
                                // Filter out non-name text
                                if (text && 
                                    text.length > 1 && 
                                    text !== 'Contacts' && 
                                    text !== 'Online status indicator' &&
                                    !text.includes('Active') &&
                                    !text.includes('New') &&
                                    !text.includes('More') &&
                                    !text.includes('See') &&
                                    !text.includes('Group') &&
                                    !excludeNames.includes(text)) {
                                    
                                    // Check if visible
                                    const style = window.getComputedStyle(span);
                                    if (style.display !== 'none' && 
                                        style.visibility !== 'hidden' && 
                                        parseFloat(style.opacity) > 0) {
                                        
                                        contactName = text;
                                        break;
                                    }
                                }
                            }
                            
                            // Method 2: If no name found, try the aria-label
                            if (!contactName && link.getAttribute('aria-label')) {
                                let ariaLabel = link.getAttribute('aria-label');
                                
                                // Remove common prefixes
                                const prefixes = ['Message ', 'Chat with ', 'Contact ', 'New message from '];
                                for (const prefix of prefixes) {
                                    if (ariaLabel.startsWith(prefix)) {
                                        ariaLabel = ariaLabel.substring(prefix.length);
                                        break;
                                    }
                                }
                                
                                // Remove status indicators
                                ariaLabel = ariaLabel.replace(', Active', '');
                                ariaLabel = ariaLabel.replace(', active', '');
                                ariaLabel = ariaLabel.replace(', Online', '');
                                ariaLabel = ariaLabel.replace(', online', '');
                                
                                if (ariaLabel && ariaLabel.length > 1 && !excludeNames.includes(ariaLabel)) {
                                    contactName = ariaLabel;
                                }
                            }
                            
                            // Method 3: If still no name, try the title attribute
                            if (!contactName && link.getAttribute('title')) {
                                const title = link.getAttribute('title');
                                if (!excludeNames.includes(title)) {
                                    contactName = title;
                                }
                            }
                            
                            // If we found a valid contact name, add it to the results
                            if (contactName && !processedNames.has(contactName) && !excludeNames.includes(contactName)) {
                                // One final check to make sure we're not adding any excluded names
                                let shouldExclude = false;
                                for (const excludeName of excludeNames) {
                                    if (contactName.includes(excludeName)) {
                                        shouldExclude = true;
                                        break;
                                    }
                                }
                                
                                if (!shouldExclude) {
                                    onlineNames.push(contactName);
                                    processedNames.add(contactName);
                                }
                            }
                        }
                    }
                    
                    // 3. Specifically handle the first few contacts that might be missed
                    // Try looking at the very top of the right sidebar
                    const rightSidebarContainers = document.querySelectorAll('div[role="complementary"]');
                    for (const container of rightSidebarContainers) {
                        // Check first few links at the top of the sidebar
                        const topLinks = Array.from(container.querySelectorAll('a')).slice(0, 10);
                        
                        for (const link of topLinks) {
                            // Skip already processed links
                            if (link.dataset.processed) continue;
                            link.dataset.processed = "true";
                            
                            // Skip if clearly a group
                            const images = link.querySelectorAll('img');
                            if (images.length > 1) continue;
                            
                            // Skip links with excluded text
                            const linkText = link.textContent.trim();
                            let shouldSkip = false;
                            for (const excludeName of excludeNames) {
                                if (linkText.includes(excludeName)) {
                                    shouldSkip = true;
                                    break;
                                }
                            }
                            if (shouldSkip) continue;
                            
                            // Check for online status
                            let hasOnlineIndicator = false;
                            
                            // Look for green dots with broader criteria
                            const allElements = link.querySelectorAll('*');
                            for (const elem of allElements) {
                                const style = window.getComputedStyle(elem);
                                const bgColor = style.backgroundColor;
                                
                                // Check if this element has any green-ish background
                                if (bgColor && (
                                    bgColor.includes('rgb(0,') ||
                                    bgColor.includes('rgb(0, ') ||
                                    bgColor.includes('rgb(24,') ||
                                    bgColor.includes('rgb(24, ') ||
                                    bgColor.includes('rgb(42,') ||
                                    bgColor.includes('rgb(42, ') ||
                                    bgColor.includes('rgb(76,') ||
                                    bgColor.includes('rgb(76, ')
                                )) {
                                    hasOnlineIndicator = true;
                                    break;
                                }
                            }
                            
                            if (hasOnlineIndicator) {
                                // Extract name with broader criteria
                                let name = null;
                                
                                // Try span elements
                                const spans = link.querySelectorAll('span');
                                for (const span of spans) {
                                    const text = span.textContent.trim();
                                    if (text && text.length > 1 && 
                                        !text.includes('Group') && 
                                        !text.includes('Community') &&
                                        !excludeNames.includes(text)) {
                                        
                                        // Check for excluded terms
                                        let isExcluded = false;
                                        for (const excludeName of excludeNames) {
                                            if (text.includes(excludeName)) {
                                                isExcluded = true;
                                                break;
                                            }
                                        }
                                        
                                        if (!isExcluded) {
                                            name = text;
                                            break;
                                        }
                                    }
                                }
                                
                                // If still no name, try aria-label
                                if (!name) {
                                    const ariaLabel = link.getAttribute('aria-label');
                                    if (ariaLabel) {
                                        // Simple extraction - take first part before commas
                                        const parts = ariaLabel.split(',');
                                        let extractedName = parts[0].replace('Message ', '')
                                                          .replace('Chat with ', '')
                                                          .trim();
                                        
                                        // Check against excluded names
                                        let isExcluded = false;
                                        for (const excludeName of excludeNames) {
                                            if (extractedName.includes(excludeName)) {
                                                isExcluded = true;
                                                break;
                                            }
                                        }
                                        
                                        if (!isExcluded) {
                                            name = extractedName;
                                        }
                                    }
                                }
                                
                                // Add to results if not a duplicate and not excluded
                                if (name && !processedNames.has(name) && !excludeNames.includes(name)) {
                                    let isExcluded = false;
                                    for (const excludeName of excludeNames) {
                                        if (name.includes(excludeName)) {
                                            isExcluded = true;
                                            break;
                                        }
                                    }
                                    
                                    if (!isExcluded) {
                                        onlineNames.push(name);
                                        processedNames.add(name);
                                    }
                                }
                            }
                        }
                    }
                    
                    return onlineNames;
                }
                
                // Execute and return results
                return getOnlineContacts();
            """)
            
            if not online_contacts:
                logger.warning("No online contacts found")
                return []
                
            if isinstance(online_contacts, list) and len(online_contacts) > 0 and isinstance(online_contacts[0], str) and online_contacts[0].startswith("ERROR"):
                logger.error(online_contacts[0])
                return []
                
            logger.info(f"Found {len(online_contacts)} online contacts")
            for name in online_contacts:
                logger.info(f"Online: {name}")
                
            return online_contacts
            
        except Exception as e:
            logger.error(f"Error scanning online contacts: {e}")
            return []
            
            if not online_contacts:
                logger.warning("No online contacts found")
                return []
                
            if isinstance(online_contacts, list) and len(online_contacts) > 0 and isinstance(online_contacts[0], str) and online_contacts[0].startswith("ERROR"):
                logger.error(online_contacts[0])
                return []
                
            logger.info(f"Found {len(online_contacts)} online contacts")
            for name in online_contacts:
                logger.info(f"Online: {name}")
                
            return online_contacts
            
        except Exception as e:
            logger.error(f"Error scanning online contacts: {e}")
            return []
            
            if not online_contacts:
                logger.warning("No online contacts found")
                return []
                
            if isinstance(online_contacts, list) and len(online_contacts) > 0 and isinstance(online_contacts[0], str) and online_contacts[0].startswith("ERROR"):
                logger.error(online_contacts[0])
                return []
                
            logger.info(f"Found {len(online_contacts)} online contacts")
            for name in online_contacts:
                logger.info(f"Online: {name}")
                
            return online_contacts
            
        except Exception as e:
            logger.error(f"Error scanning online contacts: {e}")
            return []
            
            if not online_contacts:
                logger.warning("No online contacts found")
                return []
                
            if isinstance(online_contacts, list) and len(online_contacts) > 0 and isinstance(online_contacts[0], str) and online_contacts[0].startswith("ERROR"):
                logger.error(online_contacts[0])
                return []
                
            logger.info(f"Found {len(online_contacts)} online contacts")
            for name in online_contacts:
                logger.info(f"Online: {name}")
                
            return online_contacts
            
        except Exception as e:
            logger.error(f"Error scanning online contacts: {e}")
            return []
    
    def record_online_contacts(self, online_contacts):
        """Record currently online contacts to database"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for name in online_contacts:
            self.db.add_online_activity(timestamp, name, 'Online')
    
    def generate_excel_report(self):
        """Generate a comprehensive Excel report from the database"""
        try:
            # Get data from database
            df = self.db.get_all_activity()
            
            if df.empty:
                logger.warning("No data available for report")
                return False
            
            # Create a Pandas Excel writer using the predefined filename
            with pd.ExcelWriter(self.report_filename, engine='xlsxwriter') as writer:
                # Raw Data Sheet
                df.to_excel(writer, sheet_name='Raw Data', index=False)
                
                # Summary by User
                user_summary = df.groupby('name').size().reset_index()
                user_summary.columns = ['Name', 'Times Seen Online']
                user_summary = user_summary.sort_values('Times Seen Online', ascending=False)
                user_summary.to_excel(writer, sheet_name='User Summary', index=False)
                
                # Activity by Hour
                df['Hour'] = df['timestamp'].dt.hour
                hour_summary = df.groupby(['name', 'Hour']).size().reset_index()
                hour_summary.columns = ['Name', 'Hour', 'Count']
                
                # Create pivot for better visualization
                hour_pivot = pd.pivot_table(
                    hour_summary, 
                    values='Count', 
                    index='Hour', 
                    columns='name',
                    fill_value=0
                )
                hour_pivot.to_excel(writer, sheet_name='Hourly Activity')
                
                # Activity by Day
                df['Date'] = df['timestamp'].dt.date
                daily_summary = df.groupby(['name', 'Date']).size().reset_index()
                daily_summary.columns = ['Name', 'Date', 'Count']
                daily_summary.to_excel(writer, sheet_name='Daily Activity', index=False)
                
                # Latest activity (last 24 hours)
                recent_df = self.db.get_activity_since(hours=24)
                if not recent_df.empty:
                    recent_df.to_excel(writer, sheet_name='Last 24 Hours', index=False)
                
                # Get the workbook and add charts
                workbook = writer.book
                
                # Total activity chart
                chart_sheet = workbook.add_worksheet('Activity Charts')
                chart = workbook.add_chart({'type': 'bar'})
                
                # Only chart top 15 users to keep it readable
                top_users = min(15, len(user_summary))
                
                # Configure the series for the chart
                chart.add_series({
                    'name': 'Times Seen Online',
                    'categories': ['User Summary', 1, 0, top_users, 0],
                    'values': ['User Summary', 1, 1, top_users, 1],
                })
                
                # Configure chart
                chart.set_title({'name': 'Online Activity by User'})
                chart.set_x_axis({'name': 'User'})
                chart.set_y_axis({'name': 'Times Seen Online'})
                
                # Insert the chart in the chart sheet
                chart_sheet.insert_chart('B2', chart, {'x_scale': 1.5, 'y_scale': 1.5})
                
                # Hourly activity chart
                hourly_chart = workbook.add_chart({'type': 'line'})
                
                # Add a series for each user (up to 5 most active users)
                top_names = user_summary['Name'].head(5).tolist()
                for i, name in enumerate(top_names):
                    if name in hour_pivot.columns:
                        col_idx = hour_pivot.columns.get_loc(name) + 1  # +1 for Excel's 1-based indexing
                        hourly_chart.add_series({
                            'name': name,
                            'categories': ['Hourly Activity', 1, 0, 24, 0],
                            'values': ['Hourly Activity', 1, col_idx, 24, col_idx],
                        })
                
                # Configure chart
                hourly_chart.set_title({'name': 'Activity by Hour of Day (Top 5 Users)'})
                hourly_chart.set_x_axis({'name': 'Hour'})
                hourly_chart.set_y_axis({'name': 'Times Seen Online'})
                
                # Insert hourly chart
                chart_sheet.insert_chart('B20', hourly_chart, {'x_scale': 1.5, 'y_scale': 1.5})
            
            logger.info(f"Generated report: {self.report_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return False
    
    def check_and_manage_resources(self):
        """Check and manage system resources"""
        try:
            # Check if browser needs to be restarted (every 8 hours)
            hours_since_restart = (datetime.datetime.now() - self.last_browser_restart).total_seconds() / 3600
            
            if hours_since_restart >= 8:
                logger.info("Scheduled browser restart after 8 hours of running")
                return self.restart_browser()
            
            # Check memory usage
            process = psutil.Process(os.getpid())
            memory_usage = process.memory_info().rss / (1024 * 1024)  # Convert to MB
            
            # If using more than 2GB RAM, restart browser
            if memory_usage > 2000:
                logger.warning(f"High memory usage detected: {memory_usage:.2f} MB. Restarting browser...")
                return self.restart_browser()
            
            return True
        except Exception as e:
            logger.error(f"Error checking resources: {e}")
            return False
    
    def check_session_valid(self):
        """Check if the Facebook session is still valid"""
        try:
            if not self.driver:
                logger.error("No active WebDriver")
                return False
                
            # Check if we're still on Facebook homepage (not in a reel, post, etc.)
            current_url = self.driver.current_url
            
            if "facebook.com" not in current_url:
                logger.warning(f"Not on Facebook, current URL: {current_url}")
                self.driver.get("https://www.facebook.com/")
                time.sleep(5)
            elif "reel" in current_url or "watch" in current_url or "posts" in current_url:
                logger.warning(f"Not on Facebook homepage, current URL: {current_url}")
                self.driver.get("https://www.facebook.com/")
                time.sleep(5)
            
            # Check for login form which would indicate session expired
            login_elements = self.driver.find_elements("id", "email")
            if login_elements:
                logger.warning("Session expired - login form detected")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking session: {e}")
            return False
    
    def track_continuously(self, interval_seconds=60):
        """Track online status continuously with robust error handling"""
        self.running = True
        iteration = 0
        consecutive_errors = 0
        
        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            print("\nReceived shutdown signal. Finishing gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize browser if not already set up
        if not self.driver:
            try:
                self.driver = self.setup_driver()
                self.driver.get("https://www.facebook.com/")
                time.sleep(5)
                self.last_browser_restart = datetime.datetime.now()
            except Exception as e:
                logger.error(f"Failed to initialize browser: {e}")
                self.running = False
                return
        
        logger.info("Starting continuous tracking. Press Ctrl+C to stop.")
        print("\nStarting continuous tracking. Press Ctrl+C to stop.")
        print(f"All data will be saved to database and exported to: {self.report_filename}")
        
        # Main tracking loop
        while self.running:
            try:
                # Get current timestamp
                current_time = datetime.datetime.now()
                print(f"\n[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Scanning... (Iteration {iteration})")
                
                # Check and manage system resources
                self.check_and_manage_resources()
                
                # Check if session is still valid and on the right page
                if not self.check_session_valid():
                    logger.warning("Facebook session invalid or not on homepage - attempting to restart browser")
                    if not self.restart_browser():
                        logger.error("Failed to restart browser - session may need manual login")
                        print("\n!!! SESSION EXPIRED: Please manually log back into Facebook !!!")
                        print("The script will continue running, but will not collect data until you log in")
                        time.sleep(interval_seconds)
                        continue
                
                # Perform periodic browser refresh (every 20 iterations)
                if iteration > 0 and iteration % 20 == 0:
                    print("Performing page refresh...")
                    try:
                        # First ensure we're on the homepage
                        current_url = self.driver.current_url
                        if "facebook.com" not in current_url or "reel" in current_url or "watch" in current_url or "posts" in current_url:
                            logger.info(f"Not on Facebook homepage. Current URL: {current_url}")
                            self.driver.get("https://www.facebook.com/")
                        else:
                            self.driver.refresh()
                        time.sleep(5)
                    except WebDriverException:
                        logger.warning("Error during page refresh - attempting browser restart")
                        self.restart_browser()
                
                # Scan for online contacts
                online_contacts = self.scan_online_contacts()
                
                # Record data
                if online_contacts:
                    self.record_online_contacts(online_contacts)
                    
                    print(f"Found {len(online_contacts)} online contacts:")
                    for name in online_contacts:
                        print(f"- {name}")
                    
                    # Reset error counter on success
                    consecutive_errors = 0
                else:
                    print("No online contacts found.")
                    
                    # If we're having trouble finding contacts, check if we're on the right page
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        logger.warning(f"Multiple consecutive failures to find contacts ({consecutive_errors}) - checking page state")
                        current_url = self.driver.current_url
                        if "facebook.com" not in current_url or "reel" in current_url or "watch" in current_url or "posts" in current_url:
                            logger.warning(f"Not on Facebook homepage. Current URL: {current_url}")
                            self.driver.get("https://www.facebook.com/")
                            time.sleep(5)
                        elif consecutive_errors >= 5:
                            logger.warning(f"Persistent failures to find contacts ({consecutive_errors}) - restarting browser")
                            self.restart_browser()
                            consecutive_errors = 0
                
                # Update the report every 30 iterations
                if iteration > 0 and iteration % 30 == 0:
                    print("Updating Excel report...")
                    self.generate_excel_report()
                
                iteration += 1
                
                # Wait for next interval
                next_scan_time = datetime.datetime.now() + datetime.timedelta(seconds=interval_seconds)
                time_to_wait = (next_scan_time - datetime.datetime.now()).total_seconds()
                
                if time_to_wait > 0:
                    print(f"Next scan in {time_to_wait:.0f} seconds...")
                    
                    # Break the wait into smaller chunks to allow for graceful shutdown
                    chunks = 10
                    chunk_time = time_to_wait / chunks
                    
                    for _ in range(chunks):
                        if not self.running:
                            break
                        time.sleep(chunk_time)
                
            except WebDriverException as e:
                consecutive_errors += 1
                logger.error(f"WebDriver error: {e}")
                
                # If we get multiple consecutive errors, restart the browser
                if consecutive_errors >= 3:
                    logger.warning(f"Multiple consecutive errors ({consecutive_errors}) - restarting browser")
                    self.restart_browser()
                    consecutive_errors = 0
                
                time.sleep(10)  # Wait before retrying
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                logger.error(traceback.format_exc())
                
                # Try to recover from unexpected errors
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    logger.critical(f"Too many consecutive errors ({consecutive_errors}) - attempting full restart")
                    self.restart_browser()
                    consecutive_errors = 0
                
                time.sleep(30)  # Longer wait after unexpected error
        
        # Final cleanup
        try:
            # Final report generation
            print("Generating final report...")
            self.generate_excel_report()
            print(f"Final report saved to: {self.report_filename}")
            
            # Close browser and database
            print("Closing browser and database...")
            if self.driver:
                self.driver.quit()
            
            self.db.close()
            logger.info("Tracking stopped gracefully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main function to run the tracker"""
    print("Facebook Online Activity Tracker - Long-Term Stable Version")
    print("----------------------------------------------------------")
    print("A script designed to run for weeks, tracking when your Facebook friends are online.")
    print("IMPORTANT: You must already be logged into Facebook in Chrome.")
    
    try:
        tracker = FacebookActivityTracker()
        
        print("\n1. Start continuous tracking")
        print("2. Generate report from existing data")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            interval = int(input("Enter check interval in seconds (default 60): ") or "60")
            tracker.track_continuously(interval)
        elif choice == '2':
            if tracker.generate_excel_report():
                print(f"Report generated successfully: {tracker.report_filename}")
            else:
                print("Error generating report or no data available.")
        else:
            print("Exiting program.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
