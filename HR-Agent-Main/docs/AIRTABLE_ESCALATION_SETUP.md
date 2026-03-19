# Airtable Escalation Setup

This guide explains how to set up Airtable for the HR Agent escalation feature. When users click "Escalate to HR Specialist" under a chat response, the query and AI response are sent to an Airtable base for human review.

## 1. Create an Airtable Base

1. Go to [airtable.com](https://airtable.com) and sign in.
2. Create a new base or use an existing one.
3. Create a table named **Escalations** (or use a different name and set `AIRTABLE_ESCALATIONS_TABLE` in `.env`).

## 2. Create Table Fields

Add the following fields to the Escalations table:

| Field Name       | Type          | Notes                                              |
|------------------|---------------|----------------------------------------------------|
| User ID          | Single line   | User who escalated                                 |
| Session ID       | Single line   | Chat session reference                             |
| Query            | Long text     | Original user question                             |
| AI Response      | Long text     | AI's response being escalated                      |
| Confidence Score | Number        | 0.0–1.0 (AI confidence when response was generated)|
| Status           | Single select | Options: New, In Progress, Resolved, Closed         |
| Province         | Single select | MB, ON, SK, AB, BC (optional)                      |
| Topic            | Single line   | Question category (optional)                       |
| Metadata         | Long text     | Additional context JSON (optional)                 |
| Created At       | Date          | Auto-set on creation                               |
| Resolved At      | Date          | Set when resolved                                  |
| Resolution       | Long text     | HR specialist's response                           |

## 3. Get API Credentials

### API Key

1. Go to [airtable.com/account](https://airtable.com/account)
2. Click **Generate API key**
3. Copy the key (starts with `key...`)

### Base ID

1. Open your Airtable base
2. Go to [airtable.com/api](https://airtable.com/api)
3. Select your base
4. Copy the Base ID (starts with `app...`)

## 4. Configure Backend

Add to your `.env` file:

```env
AIRTABLE_API_KEY=keyXXXXXXXXXXXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
AIRTABLE_ESCALATIONS_TABLE=Escalations
```

Restart the backend after updating `.env`.

## 5. Verify Setup

1. Start a chat in the HR Agent frontend
2. Ask a question and receive a response
3. Click **Escalate to HR Specialist** under the response
4. Add optional context and submit
5. Check your Airtable Escalations table for the new record

## Troubleshooting

### Escalations not appearing in Airtable

- Verify `AIRTABLE_API_KEY` and `AIRTABLE_BASE_ID` are set correctly
- Ensure the table name matches `AIRTABLE_ESCALATIONS_TABLE`
- Check backend logs for Airtable API errors

### 401 Unauthorized

- Regenerate your Airtable API key
- Ensure the key has access to the base

### Field name mismatches

The backend sends these exact field names. If your Airtable table uses different names, update [app/services/airtable.py](app/services/airtable.py) to match.
