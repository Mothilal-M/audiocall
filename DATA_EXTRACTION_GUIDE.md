# Data Extraction & Analytics Guide - Construction Agent

## Overview
This guide explains how to extract, structure, and analyze data from construction site manager calls.

## Data Extraction Pipeline

### Step 1: Call Recording & Transcription
The Google ADK Gemini Live API automatically captures:
- **Audio**: Full call recording (stored by Twilio)
- **Transcript**: Automatically transcribed by Gemini
- **Metadata**: 
  - Phone number called
  - Call duration
  - Call date/time
  - Language used

### Step 2: Structured Data Parsing
Extract from transcripts using:
- **Pattern matching**: Regex for numbers, percentages, dates
- **NLP extraction**: Entity recognition for names, locations
- **LLM extraction**: Ask Gemini to extract structured data from transcript

### Step 3: Storage Schema

```sql
-- Project Information
CREATE TABLE projects (
    project_id INT PRIMARY KEY,
    project_name VARCHAR(255),
    location VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    latitude DECIMAL(10,8),
    longitude DECIMAL(10,8),
    project_type VARCHAR(50), -- residential, commercial, infrastructure
    total_value DECIMAL(15,2),
    created_date TIMESTAMP
);

-- Site Managers
CREATE TABLE site_managers (
    manager_id INT PRIMARY KEY,
    name VARCHAR(255),
    phone VARCHAR(20),
    whatsapp VARCHAR(20),
    email VARCHAR(255),
    designation VARCHAR(100),
    project_id INT FOREIGN KEY,
    call_frequency VARCHAR(50) -- weekly, monthly, as-needed
);

-- Call Records
CREATE TABLE call_records (
    call_id INT PRIMARY KEY,
    project_id INT FOREIGN KEY,
    manager_id INT FOREIGN KEY,
    call_date TIMESTAMP,
    call_duration INT, -- in seconds
    language_used VARCHAR(50),
    transcript_text TEXT,
    transcript_url VARCHAR(500)
);

-- Project Status Snapshots
CREATE TABLE project_status (
    status_id INT PRIMARY KEY,
    call_id INT FOREIGN KEY,
    project_id INT FOREIGN KEY,
    
    -- Progress Metrics
    completion_percentage DECIMAL(5,2),
    schedule_status ENUM('ahead', 'on-time', 'behind'),
    days_ahead_behind INT,
    next_milestone VARCHAR(255),
    target_completion_date DATE,
    
    -- Workforce
    workers_on_site INT,
    skilled_workers_available BOOLEAN,
    labor_challenges TEXT,
    
    -- Materials
    material_status ENUM('all-on-time', 'some-delayed', 'major-delays'),
    delayed_materials TEXT,
    
    -- Budget
    budget_status ENUM('under-budget', 'on-budget', 'over-budget'),
    budget_variance_percentage DECIMAL(5,2),
    budget_comments TEXT,
    
    -- Safety & Quality
    safety_incidents_recent INT,
    safety_incident_severity VARCHAR(50),
    quality_status VARCHAR(255),
    
    -- Critical Issues
    biggest_challenge TEXT,
    blockers TEXT,
    recommendations TEXT,
    
    -- Contact Info
    preferred_contact_method VARCHAR(50),
    contact_value VARCHAR(20),
    
    -- Timestamps
    captured_date TIMESTAMP
);

-- Aggregated Metrics (by project)
CREATE TABLE project_metrics (
    metric_id INT PRIMARY KEY,
    project_id INT FOREIGN KEY,
    metric_month DATE, -- YYYY-MM format
    
    -- Averages
    avg_completion_percentage DECIMAL(5,2),
    avg_schedule_variance_days DECIMAL(5,2),
    avg_workforce_count INT,
    avg_budget_variance_percentage DECIMAL(5,2),
    
    -- Trends
    completion_trend VARCHAR(50), -- accelerating, stable, decelerating
    schedule_trend VARCHAR(50),
    budget_trend VARCHAR(50),
    
    -- Issues Count
    total_incidents_reported INT,
    total_unique_challenges INT,
    
    -- Data Quality
    calls_received INT,
    data_completeness_percentage DECIMAL(5,2)
);
```

### Step 4: Extraction Prompts for Gemini

```python
# Example: Extract structured data from transcript using Gemini

def extract_project_data(transcript: str) -> dict:
    """Use Gemini to extract structured data from call transcript"""
    
    extraction_prompt = """
    Extract the following information from the construction site call transcript.
    Return as JSON. If information is not available, use null.
    
    {
        "site_manager_name": "string",
        "project_name": "string",
        "project_location": "string",
        "project_phase": "string",
        "completion_percentage": "number (0-100)",
        "schedule_status": "ahead|on-time|behind",
        "days_ahead_behind": "number (negative = behind)",
        "workers_on_site": "number",
        "labor_available": "boolean",
        "material_status": "all-on-time|some-delayed|major-delays",
        "delayed_materials": ["string"],
        "budget_status": "under-budget|on-budget|over-budget",
        "budget_variance_percentage": "number",
        "safety_incidents_count": "number",
        "safety_concerns": "string or null",
        "quality_issues": "string or null",
        "biggest_challenge": "string",
        "blockers": ["string"],
        "preferred_contact": "phone|whatsapp|email",
        "contact_value": "string"
    }
    
    Transcript:
    {transcript}
    """
    
    # Send to Gemini API for extraction
    response = gemini_client.generate(extraction_prompt)
    return json.loads(response.text)


# Example 2: Trend Analysis
def analyze_project_trends(project_id: str, months: int = 3) -> dict:
    """Analyze trends for a project over time"""
    
    trend_prompt = f"""
    Based on the following project status records over the last {months} months,
    provide trend analysis:
    
    {fetch_project_status_records(project_id, months)}
    
    Analyze and return:
    {
        "completion_trend": "accelerating|stable|decelerating|at-risk",
        "schedule_trend": "improving|stable|worsening",
        "budget_trend": "improving|stable|worsening",
        "workforce_trend": "increasing|stable|decreasing",
        "risk_level": "low|medium|high|critical",
        "key_issues": ["string"],
        "recommendations": ["string"],
        "forecast_completion_date": "YYYY-MM-DD or null",
        "estimated_final_budget_variance": "percentage"
    }
    """
    
    response = gemini_client.generate(trend_prompt)
    return json.loads(response.text)
```

---

## Data Dashboards & Visualizations

### Dashboard 1: Real-Time Project Status
```
┌─────────────────────────────────────────────────────┐
│            PROJECT DASHBOARD - LIVE                 │
├─────────────────────────────────────────────────────┤
│ Project: Bangalore Tech Park                         │
│ Location: Whitefield, Bangalore                      │
│ Last Updated: 2024-01-15 14:30                       │
├─────────────────────────────────────────────────────┤
│                                                       │
│  Progress     ████████░░░░░  45%                     │
│  Schedule     ▰▰▰▰░░░░░░░░░   1 week behind         │
│  Budget       ▰▰▰░░░░░░░░░░   3% over              │
│                                                       │
│  Workers: 350 daily | Materials: Delayed            │
│  Safety: No incidents | Quality: On track           │
│                                                       │
│  ⚠️  ALERT: Steel deliveries delayed (1 week)       │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Dashboard 2: Portfolio Overview
```
┌────────────────────────────────────────────────────┐
│        CONSTRUCTION PORTFOLIO DASHBOARD             │
├────────────────────────────────────────────────────┤
│  Total Projects: 8                                  │
│  Portfolio Value: ₹2,450 Crore                      │
│                                                     │
│  On Schedule:    5 projects  (62.5%)  ✓            │
│  At Risk:        2 projects  (25%)    ⚠️ │  Behind Schedule: 1 project   (12.5%)  ✗
│                                                     │
│  Budget Status:                                     │
│    Under Budget:  3 projects                        │
│    On Budget:     4 projects                        │
│    Over Budget:   1 project  (avg +8%)              │
│                                                     │
│  Recent Issues: Material delays, Labor shortage     │
│  Total Workers Deployed: 2,847                      │
│                                                     │
└────────────────────────────────────────────────────┘
```

### Dashboard 3: Alerts & Escalations
```
┌────────────────────────────────────────────────────┐
│         ALERTS & ESCALATIONS (Last 7 days)         │
├────────────────────────────────────────────────────┤
│                                                     │
│ 🔴 CRITICAL (2)                                    │
│   • Tech Park: Budget overrun 8-12% (soil issues)  │
│   • Hospital: 3 weeks behind (foundation delays)   │
│                                                     │
│ 🟡 WARNING (4)                                     │
│   • Apartment Complex: Material delays (steel)     │
│   • Airport: Labor shortage (50 workers needed)    │
│   • Mall: Quality issue (concrete curing)          │
│   • Bridge: Permit delay (1 week)                  │
│                                                     │
│ 🟢 INFO (8)                                        │
│   • Various routine updates captured               │
│                                                     │
│ 📊 Action Items: 3 escalations pending review      │
│                                                     │
└────────────────────────────────────────────────────┘
```

---

## Analytics Use Cases

### 1. Completion Forecast
```python
def forecast_completion(project_id: str) -> dict:
    """Predict project completion date based on trends"""
    historical_data = query_project_metrics(project_id)
    
    # Calculate velocity
    completion_velocity = calculate_completion_velocity(historical_data)
    remaining_work = 100 - current_completion_percentage
    
    days_remaining = remaining_work / completion_velocity
    forecast_date = today + timedelta(days=days_remaining)
    
    return {
        "forecast_completion_date": forecast_date,
        "confidence_level": calculate_confidence(historical_data),
        "risk_factors": identify_risks(project_id)
    }
```

### 2. Budget Tracking
```python
def analyze_budget_variance(project_id: str) -> dict:
    """Track budget performance over time"""
    status_records = query_project_status(project_id)
    
    variance_trend = [s.budget_variance_percentage for s in status_records]
    
    return {
        "current_variance": variance_trend[-1],
        "variance_trend": "improving" if variance_trend[-1] < variance_trend[-2] else "worsening",
        "forecasted_final_variance": project_final_variance(),
        "cost_drivers": identify_cost_drivers(project_id),
        "corrective_actions": recommend_actions(project_id)
    }
```

### 3. Issue Detection
```python
def detect_project_issues(project_id: str) -> list:
    """Automatically identify emerging issues"""
    
    issues = []
    recent_status = query_recent_status(project_id, days=14)
    
    # Check for deteriorating trends
    if is_accelerating_delay(recent_status):
        issues.append({
            "type": "schedule_risk",
            "severity": "high",
            "description": "Project falling further behind schedule"
        })
    
    # Check budget trends
    if is_budget_overrun_increasing(recent_status):
        issues.append({
            "type": "budget_risk",
            "severity": "high",
            "description": "Budget variance increasing month-over-month"
        })
    
    # Check safety trends
    if incident_count_increasing(recent_status):
        issues.append({
            "type": "safety_concern",
            "severity": "critical",
            "description": "Safety incidents increasing - needs investigation"
        })
    
    return issues
```

---

## Reporting Templates

### Weekly Status Report
```
WEEKLY PROJECT STATUS REPORT
Week of: 2024-01-15

PROJECT SUMMARY
├─ Name: Bangalore Tech Park
├─ Overall Completion: 45% (↑5% vs last week)
├─ Schedule: 1 week behind (stable)
└─ Budget: 3% over (↓0.5% improvement)

KEY METRICS
├─ Workers: 350 on-site
├─ Material Status: Steel delayed, Concrete on-time
├─ Quality: Good
├─ Safety: No incidents
└─ Blockers: Steel delivery (1 week wait)

ACTIONS TAKEN
├─ Escalated material delays to procurement
├─ Allocated additional labor crew
└─ Scheduled follow-up call for next week

FORECAST
├─ Completion (if delays resolved): June 2025
├─ Budget (if no new overruns): ₹350 Cr (3% over)
└─ Risk Level: MEDIUM

NEXT REVIEW: 2024-01-22
```

---

## Integration with Project Management Software

```python
# Example: Export data to common PM tools

def export_to_jira(project_id: str, status_data: dict):
    """Create/update Jira issues from call data"""
    jira = JiraAPI(config)
    
    for issue in status_data['blockers']:
        jira.create_issue(
            project=project_id,
            summary=issue,
            description=f"Identified during site manager call",
            priority="HIGH",
            assignee="Project_Manager"
        )

def export_to_asana(project_id: str, status_data: dict):
    """Update Asana tasks with latest status"""
    asana = AsanaAPI(config)
    
    asana.update_task(
        task_id=f"project_{project_id}_status",
        fields={
            "completion_percentage": status_data['completion_percentage'],
            "schedule_status": status_data['schedule_status'],
            "notes": f"Latest update: {status_data['biggest_challenge']}"
        }
    )

def export_to_sheets(project_id: str, status_data: dict):
    """Append to Google Sheets for tracking"""
    sheets = GoogleSheetsAPI(config)
    
    sheets.append_row(
        spreadsheet_id=config.portfolio_sheet_id,
        range="ProjectStatus!A:M",
        values=[
            datetime.now(),
            project_id,
            status_data['completion_percentage'],
            status_data['schedule_status'],
            status_data['budget_status'],
            # ... more fields
        ]
    )
```

---

## Key Metrics to Track

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| **Completion vs Schedule** | Within 1 week | 1-2 weeks behind | >2 weeks behind |
| **Budget Variance** | Within 2% | 2-5% over | >5% over |
| **Safety Incidents** | 0 per month | 1-2 per month | >2 per month |
| **Material Delays** | 0 items delayed | 1-2 items delayed | >2 items or critical item |
| **Workforce Availability** | 95%+ available | 85-95% available | <85% available |
| **Quality Issues** | 0 reported | 1-2 minor issues | Major quality problems |

---

## Data Privacy & Security

- **GDPR Compliance**: Site manager names and contact info are PII
- **Data Retention**: Keep call transcripts for compliance (6-12 months)
- **Access Control**: Only project managers can view site-specific data
- **Encryption**: All call recordings encrypted at rest and in transit
- **Audit Trail**: Log all data access for compliance

---

## Next Steps for Implementation

1. Design database schema (see above)
2. Set up extraction pipeline with Gemini
3. Build dashboards in BI tool (Tableau, Looker, etc.)
4. Create alert system for critical issues
5. Integrate with existing PM tools
6. Train project managers on dashboard usage
7. Establish data governance policies
