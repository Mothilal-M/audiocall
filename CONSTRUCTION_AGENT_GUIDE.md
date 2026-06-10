# Construction Site Manager Call Agent - Usage Guide

## Overview
This voice agent is specifically designed to call Indian construction site managers and gather valuable project data through natural, conversational phone calls.

## Agent Details

### Agent Name
`construction_site_manager_call`

### Primary Function
Call site managers at construction projects to collect:
- Current project status
- Progress against schedule
- Budget information
- Workforce details
- Material procurement status
- Safety and quality metrics
- Critical issues and blockers

### Supported Languages
- Hindi
- Tamil
- Telugu
- Kannada
- Marathi
- English

The agent will automatically respond in whatever language the site manager uses.

---

## Data Collection Flow

### Phase 1: Introduction & Rapport (30 seconds)
```
Agent: "Hello! Is this [Site Manager Name]? Hi, I'm calling from the project management team. Do you have a few minutes to discuss the current site status?"
```

### Phase 2: Project Fundamentals
- Project name and location
- Current construction phase (foundation, framing, finishing, etc.)

### Phase 3: Schedule & Progress
- Project completion percentage
- Schedule status: on-time, ahead, or behind (by how many days)
- Next major milestone
- Target completion date

### Phase 4: Workforce & Resources
- Number of workers on site
- Availability of skilled workers
- Any labor shortages or challenges

### Phase 5: Materials & Procurement
- Current material inventory status
- Any delivery delays
- Upcoming deliveries

### Phase 6: Budget & Spending
- Budget tracking status
- Any budget overruns
- Unexpected costs or changes

### Phase 7: Safety & Quality
- Recent safety incidents or near-misses
- Quality assurance status

### Phase 8: Critical Issues
- Biggest current challenge
- Any blockers preventing progress

### Phase 9: Contact & Closure
- Best contact method (phone, WhatsApp, email)
- Next update schedule
- Thank you and confirmation

---

## Data Collection Checklist

The agent aims to capture:
- ☐ Site Manager Name
- ☐ Project Name & Location
- ☐ Project Phase
- ☐ % Complete
- ☐ Schedule Status (on-time/ahead/behind)
- ☐ Days Ahead/Behind
- ☐ Current Workforce Count
- ☐ Labor Availability Status
- ☐ Material Delivery Status
- ☐ Budget Status
- ☐ Safety Incidents (count, severity)
- ☐ Quality Status
- ☐ Key Challenges
- ☐ Contact Methods (Phone, WhatsApp, Email)

---

## Key Agent Characteristics

### Conversational Style
- Short, natural responses (1-2 sentences max)
- One question at a time
- Sounds like a professional colleague
- Acknowledges and summarizes information

### Context Awareness
- Respects site managers' time (they're busy)
- Shows genuine interest in their challenges
- Treats them as ground-truth experts
- Willing to reschedule if they're too busy

### Language Features
- Multi-lingual support (automatically detects)
- No language mixing unless user initiates
- Professional yet friendly tone
- Culturally appropriate for Indian construction industry

---

## Example Call Flow

```
Agent: "Hello! Is this Rajesh? Hi, I'm calling from the project management team. Do you have 5-10 minutes?"

Site Manager: "Yes, sure. What do you need?"

Agent: "Great, thank you! First, can you tell me which project you're currently managing?"

Site Manager: "I'm at the Bangalore Tech Park project in Whitefield."

Agent: "Perfect! And what phase of construction are you currently in?"

Site Manager: "We're in the framing stage right now."

Agent: "Excellent! What percentage would you say the project is complete at this point?"

Site Manager: "About 45% done."

Agent: "Got it, 45% complete. Are you on schedule, or running ahead or behind?"

Site Manager: "We're about a week behind schedule."

Agent: "Okay, so a week behind. What's been the main reason for the delay?"

Site Manager: "Material deliveries. The steel arrived late."

Agent: "I see. And do you have enough workers on site right now?"

[Call continues naturally through all data points...]
```

---

## Integration with Twilio & Google ADK

This agent uses:
- **Voice Provider**: Twilio
- **AI Model**: Google Gemini 2.5 Flash (native audio preview)
- **Voice Name**: "Puck" (crisp, professional)
- **Audio Format**: μ-law 8 kHz (Twilio) ↔ PCM-16 16/24 kHz (Google ADK)

The agent is called via voice and maintains a natural, bidirectional conversation with site managers.

---

## Configuration

### Environment Variables
```bash
AGENT_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
AGENT_VOICE=Puck
TWILIO_ACCOUNT_SID=<your_sid>
TWILIO_AUTH_TOKEN=<your_token>
TWILIO_PHONE_NUMBER=<your_number>
SERVER_HOST=<your_public_hostname>
USE_TLS=true
```

### Running the Agent
```bash
python -m audiocall
# or
audiocall
```

---

## What Changed from Original

| Aspect | Before | After |
|--------|--------|-------|
| **Agent Name** | job_matching_assistant | construction_site_manager_call |
| **Purpose** | Match job seekers with opportunities | Collect construction project data |
| **Target User** | Job seeker | Site Manager |
| **Tone** | Recruiter | Project coordinator |
| **Data Collected** | Job interests, skills, contact info | Project status, budget, safety, etc. |
| **Response Length** | 1-3 sentences | 1-2 sentences (respecting their time) |
| **Languages** | Regional (generic) | Hindi, Tamil, Telugu, Kannada, Marathi |
| **Key Focus** | Understanding preferences | Gathering operational metrics |

---

## Tips for Best Results

1. **Call Timing**: Avoid calling during peak work hours (usually 10am-4pm on weekdays)
2. **Rapport**: Start with a friendly greeting to establish trust
3. **Respect**: Site managers are busy - keep calls concise
4. **Active Listening**: Acknowledge information they provide before asking next question
5. **Follow-up**: Schedule next update call at end of conversation
6. **WhatsApp**: Many Indian site managers prefer WhatsApp for urgent updates
7. **Names**: Always ask for and use the site manager's name
8. **Local Context**: Show knowledge of Indian construction practices

---

## Error Handling

The agent is designed to:
- Offer to reschedule if the site manager is too busy
- Continue naturally if they skip a question
- Clarify information if they provide unclear answers
- Adapt to their communication style (formal vs casual)

---

## Next Steps

1. Configure Twilio credentials in `.env`
2. Deploy to a public server with the URL
3. Update Twilio webhook to point to `/voice` endpoint
4. Start making calls to site managers
5. Collect and aggregate the data from conversations
