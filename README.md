# Facebook Online Activity Tracker
<img width="615" height="456" alt="Names" src="https://github.com/user-attachments/assets/14ac2568-04b9-425e-ad66-c1ce03ba01de" />

A comprehensive Python-based tool for tracking and analyzing Facebook friends' online activity patterns. This project provides automated data collection, advanced analytics, and interactive visualizations to understand social media usage patterns.

<img width="1675" height="521" alt="image" src="https://github.com/user-attachments/assets/523344be-71ac-43d8-a657-01132b96ff54" />

<img width="1632" height="525" alt="image" src="https://github.com/user-attachments/assets/cf2bf060-fed5-42b2-b17f-1c1799ecbcff" />

<img width="1572" height="515" alt="image" src="https://github.com/user-attachments/assets/372b7436-f476-4ef4-b35d-8653e7d9e178" />

<img width="990" height="1082" alt="Untitled" src="https://github.com/user-attachments/assets/f70d41c4-bdea-49f4-83aa-c847418db798" />


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
6. You can run FaceBoard.py to view some related graphs like above. Keep in mind this is still a work in progress and FaceBoard.py is buggy.
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

### Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/lozalien/FB_Counter.git
   cd FB_Counter
   ```

2. **Install Dependencies**
   ```bash
   # Create requirements.txt first with the dependencies listed below
   pip install selenium webdriver-manager pandas numpy plotly dash dash-bootstrap-components xlsxwriter psutil
   
   # Or if you create a requirements.txt file:
   pip install -r requirements.txt
   ```

3. **Setup Files**
   ```bash
   # Rename the dashboard file for easier use
   mv "Fixed Dash Application.txt" dashboard.py
   ```

4. **Facebook Authentication**
   - The tool uses your existing Chrome profile for authentication
   - Ensure you're logged into Facebook in your default Chrome browser
   - No additional credentials required

5. **Directory Structure**
   ```
   FB_Counter/
   ├── Code 2                      # Main tracking script (improved version)
   ├── code 3                      # Advanced tracking script with analytics
   ├── Fixed Dash Application.txt  # Web dashboard application
   ├── exports/                    # Generated reports directory (created on first run)
   ├── facebook_tracking.db        # SQLite database (created on first run)
   ├── facebook_tracker.log        # Application logs (created on first run)
   └── README.md                   # Project documentation
   ```

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone https://github.com/lozalien/FB_Counter.git
   cd FB_Counter
   pip install selenium webdriver-manager pandas numpy plotly dash dash-bootstrap-components xlsxwriter psutil
   ```

2. **Start Tracking** (Recommended)
   ```bash
   python "code 3"
   ```

3. **Launch Dashboard** (Optional)
   ```bash
   mv "Fixed Dash Application.txt" dashboard.py
   python dashboard.py
   # Visit http://localhost:8050
   ```

## 🚀 Usage

### Basic Tracking
```bash
# Start tracking with default 5-second intervals
python "code 3"

# Custom scan interval (30 seconds)
python "code 3" --interval 30

# Help and options
python "code 3" --help
```

### Web Dashboard
```bash
# Launch interactive dashboard (rename file first)
# Rename "Fixed Dash Application.txt" to "dashboard.py"
python dashboard.py

# Access at http://localhost:8050
```

### Command Line Options
```bash
python "code 3" [OPTIONS]

Options:
  -i, --interval INTEGER  Scan interval in seconds (default: 5)
  --help                  Show help message and exit
```

## 📈 Data Analysis Features

### Automated Reports
- **Excel Reports**: Comprehensive analytics with pivot tables, charts, and user summaries
- **CSV Exports**: Raw data exports for custom analysis
- **Interactive Dashboards**: Real-time web-based visualization

### Key Metrics Tracked
- Total online sessions per user
- Average session duration
- Most active times and days
- Activity consistency patterns
- User engagement scores
- Social network activity trends

### Session Analysis
- **Session Detection**: Identifies continuous online periods
- **Duration Calculation**: Measures session lengths
- **Pattern Recognition**: Discovers usage habits
- **Comparative Analysis**: Ranks users by activity levels

## 🖥️ Dashboard Features

### Real-time Monitoring
- Current online status display
- Live activity updates
- User filtering and search
- Date range selection

### Interactive Visualizations
- **Activity Heatmaps**: Visual representation of usage patterns
- **Timeline Charts**: Chronological activity view
- **Comparison Tools**: Multi-user analysis
- **Trend Analysis**: Long-term pattern identification

### Export Capabilities
- PDF report generation
- CSV data exports
- Excel analytics packages
- JSON data dumps

## 📁 File Structure

```
FB_Counter/
├── Code 2                         # Improved tracking script
├── code 3                         # Advanced tracking engine with full analytics
├── Fixed Dash Application.txt     # Web dashboard application (rename to dashboard.py)
├── exports/                       # Generated reports (created automatically)
├── logs/                          # Application logs (created automatically)
├── facebook_tracking.db           # SQLite database (created on first run)
└── README.md                      # Project documentation
```

### File Descriptions

- **`code 3`**: The main tracking application with complete analytics, session detection, and Excel reporting
- **`Code 2`**: An improved version of the tracker with enhanced contact detection
- **`Fixed Dash Application.txt`**: Interactive web dashboard (rename to `dashboard.py` for use)
- **`exports/`**: Auto-generated directory containing CSV and Excel reports
- **`facebook_tracking.db`**: SQLite database storing all activity data
- **`facebook_tracker.log`**: Rotating log files with application activity

## ⚙️ Configuration

### Browser Settings
- Uses existing Chrome profile for authentication
- Automatic ChromeDriver management
- Memory optimization settings
- Anti-detection measures

### Data Collection
- Configurable scan intervals
- Automatic browser restarts
- Error recovery mechanisms
- Data validation and cleanup

### Export Settings
- Multiple format support
- Automated cleanup of old files
- Configurable retention policies
- Backup mechanisms

## 📊 Sample Analytics

### User Activity Summary
```
User: John Doe
├── Total Sessions: 45
├── Average Session: 23.4 minutes
├── Most Active Day: Wednesday
├── Peak Hours: 8:00 PM - 11:00 PM
├── Consistency Score: 78%
└── Activity Rank: #3 of 25 friends
```

### System Statistics
```
Database Statistics:
├── Total Records: 12,847
├── Unique Users: 25
├── Date Range: 2024-01-01 to 2024-03-15
├── Peak Activity Day: Saturday
├── Most Active Hour: 9:00 PM
└── Average Daily Users: 8.3
```

## 🔧 Advanced Features

### Data Processing
- **Duplicate Detection**: Prevents data redundancy
- **Session Merging**: Combines related activities
- **Pattern Recognition**: Identifies usage trends
- **Anomaly Detection**: Flags unusual activity patterns

### Automation Features
- **Scheduled Exports**: Automatic report generation
- **Memory Management**: Prevents resource exhaustion
- **Error Recovery**: Automatic retry mechanisms
- **Logging System**: Comprehensive activity tracking

## 🛡️ Privacy and Security

### Data Protection
- Local data storage only
- No cloud uploads or external APIs
- Encrypted database options
- Automatic log rotation

### Ethical Guidelines
- Always obtain consent before tracking
- Respect privacy boundaries
- Use for legitimate research only
- Follow applicable laws and regulations

## 🐛 Troubleshooting

### Common Issues

**Chrome Authentication Problems**
```bash
# Clear Chrome data and re-login to Facebook
# Ensure Chrome profile permissions are correct
```

**ChromeDriver Issues**
```bash
# Update ChromeDriver automatically handled
# Manual update: pip install --upgrade webdriver-manager
```

**Database Errors**
```bash
# Check file permissions
# Verify SQLite installation
# Review logs for specific errors
```

### Debug Mode
```bash
# Enable verbose logging
python "code 3" --debug

# Check log files
tail -f facebook_tracker.log
```

## 📝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add unit tests for new features
- Update documentation for changes
- Ensure cross-platform compatibility

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚖️ Legal Notice

This tool is provided "as is" for educational purposes. Users are responsible for:
- Complying with Facebook's Terms of Service
- Respecting privacy laws and regulations
- Obtaining appropriate consent for data collection
- Using the tool ethically and responsibly

The developers assume no liability for misuse of this software.

## 🤝 Support

- **Documentation**: Check this README and inline code comments
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions

## 🔮 Future Features

- [ ] Multi-platform support (Firefox, Safari)
- [ ] Machine learning activity prediction
- [ ] Advanced notification systems
- [ ] API integration capabilities
- [ ] Mobile companion app
- [ ] Real-time collaboration features

---

**Remember**: Use this tool responsibly and ethically. Always respect others' privacy and obtain proper consent before tracking anyone's online activity.
