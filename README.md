# Facebook Online Activity Tracker
<img width="615" height="456" alt="Names" src="https://github.com/user-attachments/assets/14ac2568-04b9-425e-ad66-c1ce03ba01de" />

A comprehensive Python-based tool for tracking and analyzing Facebook friends' online activity patterns. This project provides automated data collection, advanced analytics, and interactive visualizations to understand social media usage patterns.

<img width="1675" height="521" alt="image" src="https://github.com/user-attachments/assets/523344be-71ac-43d8-a657-01132b96ff54" />

<img width="1632" height="525" alt="image" src="https://github.com/user-attachments/assets/cf2bf060-fed5-42b2-b17f-1c1799ecbcff" />

<img width="1572" height="515" alt="image" src="https://github.com/user-attachments/assets/372b7436-f476-4ef4-b35d-8653e7d9e178" />

<img width="990" height="1082" alt="Untitled" src="https://github.com/user-attachments/assets/b3990961-8a3d-4408-80ad-d8e46a02c56b" />



## ⚠️ Important Disclaimer

This tool is for **educational and research purposes only**. Please ensure you:
- Have explicit consent from friends whose activity you're tracking
- Comply with Facebook's Terms of Service and your local privacy laws
- Use this responsibly and ethically
- Respect others' privacy and digital boundaries

## QUICKSTART:
1. Download FB_Counter.py & FaceBoard.py
2. Ensure all dependencies are installed
3. Run FB_Counter.py. This opens a fresh chrome profile that you need to log into facebook with.
4. Close the browser and terminal that is running FB_Counter.py
5. Run it again and it should start collecting names!
6. You can run FaceBoard.py to view some related graphs like above. There are also some interesting charts in the .xls files in the /exports folder Keep in mind this is still a work in progress and FaceBoard.py is buggy.
7. Please contribute to this project if you are interested!

**Note:** This program only counts the contacts that appear in the small messenger pop-up at the bottom-right of the FB website. It takes samples every 5 seconds to record active users. The most active users that will appear at once is 17. The user list will periodically cycle through active users so typically only the most active users or most common contacts will appear more often. You must also have your status visible to others for this program to work. This is a proof of concept for educational purposes on how sharing sharing active FB status is not a safe practice for privacy!!!***


## 🚀 Features

### Core Functionality
- **Automated Activity Tracking**: Continuously monitors Facebook friends' online status
- **Smart Contact Detection**: Automatically expands and scans full contact lists
- **Robust Error Handling**: Includes browser restart mechanisms and retry logic
- **Data Persistence**: SQLite database storage with backup mechanisms

### Advanced Analytics
- **Session Analysis**: Calculates session lengths, patterns, and user engagement metrics
- **Time Pattern Recognition**: Identifies most active hours, days, and usage consistency
- **User Ranking System**: Ranks friends by activity levels and engagement
- **Comprehensive Reporting**: Generates detailed Excel reports with pivot tables and charts

### Interactive Dashboard
- **Real-time Visualization**: Live web dashboard with interactive charts
- **Multi-dimensional Analysis**: Activity heatmaps, timeline views, and comparison tools
- **Filtering Capabilities**: Date range and user-specific filtering
- **Export Functionality**: Multiple export formats (CSV, Excel, JSON)

## 📊 Analytics Features

### Data Visualizations
- **Activity Heatmaps**: Day/hour activity patterns
- **Timeline Analysis**: User activity over time
- **Session Duration Charts**: Online session length analysis
- **Comparative Analytics**: Multi-user activity comparisons
- **Radar Charts**: 24-hour activity patterns
- **Trend Analysis**: Long-term usage pattern identification

### Reporting Capabilities
- **User Summary Reports**: Individual user statistics and patterns
- **Pivot Chart Analysis**: Interactive Excel charts and tables
- **Dashboard Metrics**: Real-time KPIs and activity summaries
- **Export Options**: CSV, Excel, and database exports

## 🛠️ Installation

### Prerequisites
- Python 3.7 or higher
- Google Chrome browser
- ChromeDriver (automatically managed)
- Active Facebook account

### Required Dependencies
Create a `requirements.txt` file with:
```
selenium>=4.0.0
webdriver-manager>=3.8.0
pandas>=1.3.0
numpy>=1.21.0
plotly>=5.0.0
dash>=2.0.0
dash-bootstrap-components>=1.0.0
xlsxwriter>=3.0.0
psutil>=5.8.0
```

### Core Dependencies
```
selenium>=4.0.0          # Web automation
webdriver-manager>=3.8.0 # Chrome driver management
pandas>=1.3.0            # Data manipulation
numpy>=1.21.0            # Numerical computing
plotly>=5.0.0            # Interactive visualizations
dash>=2.0.0              # Web dashboard framework
dash-bootstrap-components>=1.0.0  # Dashboard styling
xlsxwriter>=3.0.0        # Excel export functionality
psutil>=5.8.0            # System monitoring
```



