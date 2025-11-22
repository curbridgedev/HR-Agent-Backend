# Sources Display Guide

## 📋 What's Shown in Sources

When the AI provides an answer, it displays **citations** showing where the information came from. Here's what each source shows:

---

## 🎯 Source Information Displayed

### 1. **Source Name** (Top Left)
**What it shows:**
- **Document filename** (e.g., "Ontario_Employment_Standards.docx")
- Extracted from chunk title: `"filename (chunk X/Y)"` → shows just `"filename"`
- If no filename available, shows source type: "Admin Upload", "Document", etc.

**Example:**
```
Ontario_Employment_Standards.docx
```

### 2. **Similarity Score** (Top Right)
**What it shows:**
- **Match percentage** (0-100%)
- How similar the chunk is to your query
- Higher = more relevant

**Example:**
```
85% match
```

### 3. **Content Preview** (Main Area)
**What it shows:**
- **First 200 characters** of the relevant chunk
- The actual text from the document that was used
- Truncated with "..." if longer
- Shows 2 lines max (line-clamped)

**Example:**
```
**35.2** An employer shall pay vacation pay to an employee who is entitled to vacation under section 33 or 34, equal to at least, (a) 4 per cent of the wages...
```

### 4. **Timestamp** (Bottom, if available)
**What it shows:**
- **Date when the document was created/uploaded**
- Formatted as locale date string
- Only shown if timestamp exists

**Example:**
```
11/22/2025
```

---

## 📊 Source Data Structure

Each source contains:

```typescript
{
  content: string,           // First 200 chars of chunk content
  source: string,            // Document filename (e.g., "Ontario_Employment_Standards.docx")
  timestamp?: Date,          // Document creation date (optional)
  metadata: object,          // Additional metadata (chunk index, document ID, etc.)
  similarity_score: number  // 0.0 to 1.0 (shown as percentage)
}
```

---

## 🎨 Frontend Display

**Location:** Below the AI response, above feedback buttons

**Visual Design:**
- Gray background card (`bg-[var(--color-bg-tertiary)]`)
- Border that highlights on hover
- Compact layout with:
  - Header: Source name + similarity score
  - Body: Content preview (2 lines max)
  - Footer: Timestamp (if available)

**Example UI:**
```
┌─────────────────────────────────────────┐
│ Ontario_Employment_Standards.docx  85% │
├─────────────────────────────────────────┤
│ **35.2** An employer shall pay         │
│ vacation pay to an employee...          │
│                                         │
│ 11/22/2025                              │
└─────────────────────────────────────────┘
```

---

## 🔍 How Sources Are Generated

### Step 1: Search
- User query → Vector search → Finds relevant chunks

### Step 2: Format
- Each chunk becomes a source
- Extracts filename from chunk title
- Truncates content to 200 chars
- Includes similarity score

### Step 3: Display
- Frontend shows all sources
- Sorted by relevance (highest similarity first)
- Clickable/expandable (future enhancement)

---

## 💡 Example Sources Display

**Query:** "How much vacation pay must employers provide?"

**Sources Shown:**
```
Sources (3):

1. Ontario_Employment_Standards.docx - 87% match
   **35.2** An employer shall pay vacation pay to an employee who is entitled to vacation under section 33 or 34, equal to at least, (a) 4 per cent of the wages...

2. Ontario_Employment_Standards.docx - 82% match
   **36** (1) Subject to subsections (2) to (4), the employer shall pay vacation pay to the employee in a lump sum before the employee commences his or her vacation.

3. Ontario_Employment_Standards.docx - 75% match
   When to pay vacation pay. The employer may pay the employee vacation pay that accrues during a pay period...
```

---

## 🎯 What Makes a Good Source?

**High Quality Source:**
- ✅ High similarity score (>80%)
- ✅ Relevant content preview
- ✅ Clear document name
- ✅ Recent timestamp (if applicable)

**Low Quality Source:**
- ⚠️ Low similarity score (<60%)
- ⚠️ Unclear or truncated content
- ⚠️ Generic source name

---

## 🔧 Technical Details

### Backend (format_output_node)
- Extracts sources from `context_documents`
- Formats each source with:
  - Content (200 char preview)
  - Source name (from chunk title)
  - Similarity score
  - Timestamp
  - Metadata

### Frontend (ChatMessage.tsx)
- Displays sources in collapsible section
- Shows count: "Sources (3):"
- Each source in a card
- Hover effects for better UX

---

## 📝 Current Limitations

1. **Content Preview:** Only 200 chars (may truncate important info)
2. **No Expand:** Can't see full chunk content (future enhancement)
3. **No Link:** Can't click to view full document (future enhancement)
4. **Generic Names:** Some sources show "document" instead of filename (being fixed)

---

## 🚀 Future Enhancements

- [ ] Expandable sources (click to see full chunk)
- [ ] Link to full document view
- [ ] Highlight matching text in preview
- [ ] Show section numbers (e.g., "Section 35.2")
- [ ] Group sources by document
- [ ] Filter sources by similarity threshold

---

**Last Updated:** 2025-11-22

