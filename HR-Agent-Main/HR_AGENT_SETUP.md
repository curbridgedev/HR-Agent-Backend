# HR Agent Setup Guide

## 🎯 Overview

This guide covers the setup and configuration for the HR Agent - a Canadian Employment Standards AI Assistant specialized in Manitoba, Ontario, Saskatchewan, Alberta, and British Columbia employment law.

## ✨ What's New in HR Agent

### Removed Features (from Compaytence)
- ❌ Slack integration
- ❌ WhatsApp integration
- ❌ Telegram integration
- ❌ Chat platform webhooks

### New HR-Specific Features
- ✅ **Province-specific filtering** (MB, ON, SK, AB, BC)
- ✅ **Document tagging system** (province, type, topic, approval status)
- ✅ **Airtable integration** for escalations and analytics
- ✅ **Legal disclaimer banners** in chat UI
- ✅ **Citation-based answers** with source references
- ✅ **Escalation workflow** to human HR specialists
- ✅ **HR-specific prompts** tailored for Canadian employment standards

## 🔧 Required Environment Variables

### New HR Agent Variables

Add these to your `.env` file:

```bash
# Airtable Integration (for escalations & analytics)
AIRTABLE_API_KEY=keyXXXXXXXXXXXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
AIRTABLE_ESCALATIONS_TABLE=Escalations
AIRTABLE_ANALYTICS_TABLE=Analytics
```

### Airtable Setup

1. **Create an Airtable Base** with the following tables:

#### Escalations Table
| Field Name | Type | Description |
|------------|------|-------------|
| User ID | Single line text | User who created the escalation |
| Session ID | Single line text | Chat session reference |
| Query | Long text | Original user question |
| AI Response | Long text | AI's response being escalated |
| Confidence Score | Number | AI confidence (0.0-1.0) |
| Status | Single select | New, In Progress, Resolved, Closed |
| Province | Single select | MB, ON, SK, AB, BC |
| Topic | Single line text | Question category |
| Metadata | Long text | Additional context JSON |
| Created At | Date | Auto-set on creation |
| Resolved At | Date | Set when resolved |
| Resolution | Long text | HR specialist's response |

#### Analytics Table
| Field Name | Type | Description |
|------------|------|-------------|
| Event Type | Single select | query, resolution, feedback |
| Province | Single select | MB, ON, SK, AB, BC |
| Topic | Single line text | Question category |
| Timestamp | Date | Event timestamp |
| Metadata | Long text | Additional event data JSON |

2. **Get your API key**:
   - Go to https://airtable.com/account
   - Click "Generate API key"
   - Copy the key starting with `key...`

3. **Get your Base ID**:
   - Open your Airtable base
   - Go to https://airtable.com/api
   - Select your base
   - The Base ID is shown at the top (starts with `app...`)

## 📊 Database Migrations

Run the new HR Agent migrations:

```sql
-- In Supabase SQL Editor, run these in order:

-- 1. Province tagging system
\i supabase/migrations/005_add_province_tagging.sql

-- 2. Updated HR prompts
\i supabase/migrations/006_update_hr_prompts.sql
```

Or copy the SQL from each file and paste into the Supabase SQL Editor.

### New Database Columns

The `documents` table now includes:
- `province` - TEXT (MB, ON, SK, AB, BC, ALL)
- `document_type` - TEXT (employment_standard, policy, template, sop, other)
- `topic` - TEXT (vacation, termination, overtime, etc.)
- `version` - INTEGER (for document versioning)
- `original_filename` - TEXT
- `approval_status` - TEXT (pending, approved, banned, flagged)

## 🎨 Frontend Setup

### New Components

1. **ProvinceSelector** (`components/ProvinceSelector.tsx`)
   - Dropdown to select MB, ON, SK, AB, BC
   - Defaults to Manitoba
   - Persists selection in localStorage

2. **LegalDisclaimerBanner** (`components/LegalDisclaimerBanner.tsx`)
   - Shows "not legal advice" warning
   - Dismissible per session
   - Persistent mini-disclaimer in responses

3. **EscalateButton** (`components/EscalateButton.tsx`)
   - Allows users to escalate questions to HR specialists
   - Creates ticket in Airtable
   - Shows confirmation and next steps

### Integration

The province selector and legal disclaimer are automatically shown in the chat interface via `ChatLayout.tsx`.

To add the escalate button to messages, update your message components to include:

```tsx
import EscalateButton from "@/components/EscalateButton";

// In your message component:
<EscalateButton
  messageId={message.id}
  query={message.query}
  response={message.response}
  province={selectedProvince}
  confidenceScore={message.confidence}
/>
```

## 🔐 Security & Compliance

### PIPEDA Compliance (Canada)
- User data stored in Supabase (Canadian servers recommended)
- PII anonymization enabled by default
- Row-Level Security (RLS) on all tables
- Audit logs for escalations and document access

### Province Filtering
- Queries are filtered by selected province
- Documents tagged with `ALL` are shown across provinces
- Retrieval locked to selected province (prevents cross-province contamination)

## 🚀 Deployment Checklist

- [ ] Backend `.env` configured with Airtable credentials
- [ ] Database migrations run (005, 006)
- [ ] Frontend built and deployed
- [ ] Airtable base created with correct tables
- [ ] Test escalation flow (create test ticket)
- [ ] Test province filtering (upload docs for different provinces)
- [ ] Legal disclaimer visible on all chat pages
- [ ] Admin console configured for document approval

## 📝 Next Steps (Future Phases)

### Phase 2
- Google Drive integration for policy sync
- Microsoft 365 SSO
- CanLII case law integration (toggle)
- Advanced analytics dashboard
- Multi-language support (French)

### Phase 3
- Monday.com integration for ticketing
- GHL CRM integration
- VoIP/AI phone intake
- Public community portal
- Mobile app (React Native)

## 🆘 Troubleshooting

### Airtable 401 Unauthorized
- Check API key is correct
- Ensure API key has read/write permissions
- Verify Base ID matches your base

### Province selector not showing
- Check imports in `ChatLayout.tsx`
- Ensure `ProvinceSelector.tsx` is in `components/`
- Clear browser localStorage and refresh

### Escalations not creating
- Check Airtable credentials in `.env`
- Verify Escalations table exists with correct fields
- Check backend logs for errors

### Documents not filtering by province
- Run migration 005 to add province columns
- Re-index existing documents with province tags
- Check `hybrid_search()` function includes province filter

## 📚 Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Airtable API Docs](https://airtable.com/developers/web/api/introduction)
- [Manitoba Employment Standards](https://www.gov.mb.ca/labour/standards/)
- [Ontario Employment Standards](https://www.ontario.ca/document/your-guide-employment-standards-act-0)
- [Saskatchewan Labour Standards](https://www.saskatchewan.ca/business/employment-standards)
- [Alberta Employment Standards](https://www.alberta.ca/employment-standards)
- [BC Employment Standards](https://www2.gov.bc.ca/gov/content/employment-business/employment-standards-advice)

## 🙋 Support

For issues or questions:
1. Check logs: `tail -f logs/app.log`
2. Check Supabase database for errors
3. Verify all migrations ran successfully
4. Test with sample documents per province

