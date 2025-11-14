# Frontend Guide - 6 Distinct Prompt Types

**Date**: 2025-11-08
**Status**: ✅ Backend Updated - 6 Unique Prompt Types

---

## What Changed

Previously, we had 3 prompts all with `prompt_type='system'`, which made frontend filtering confusing.

**Now**: Each prompt has a **unique `prompt_type`** value!

---

## Complete Prompt Types

| Prompt Type | Name | Purpose |
|-------------|------|---------|
| `system` | `main_system_prompt` | Main AI assistant identity |
| `query_analysis_system` | `query_analysis_system` | Query analyzer identity |
| `tool_invocation` | `tool_invocation_system` | Tool selector identity |
| `retrieval` | `retrieval_context_prompt` | RAG context formatting |
| `confidence` | `confidence_evaluation_prompt` | Confidence scoring |
| `analysis` | `query_analysis_user` | Query classification |

---

## Frontend Implementation

### TypeScript Type
```typescript
type PromptType =
  | 'system'
  | 'query_analysis_system'
  | 'tool_invocation'
  | 'retrieval'
  | 'confidence'
  | 'analysis';
```

### Filter Dropdown
```typescript
const promptTypes = [
  { value: 'system', label: 'Main System' },
  { value: 'query_analysis_system', label: 'Query Analysis' },
  { value: 'tool_invocation', label: 'Tool Invocation' },
  { value: 'retrieval', label: 'Retrieval' },
  { value: 'confidence', label: 'Confidence' },
  { value: 'analysis', label: 'Analysis' }
];
```

### Fetch Prompts by Type
```typescript
// Each type returns exactly 1 active prompt
const response = await fetch(`/api/v1/prompts?prompt_type=system&active_only=true`);
const data = await response.json();
// data.prompts[0] will be the active main_system_prompt
```

---

## Key Benefits

✅ **No More Confusion**: Each type is unique and self-descriptive
✅ **Easy Filtering**: `?prompt_type=query_analysis_system` returns exactly what you need
✅ **Clear Categories**: Frontend can organize prompts into distinct sections
✅ **One-to-One Mapping**: Each type has exactly 1 active prompt

---

## Testing

```bash
curl "http://localhost:8000/api/v1/prompts?prompt_type=system"
curl "http://localhost:8000/api/v1/prompts?prompt_type=query_analysis_system"
curl "http://localhost:8000/api/v1/prompts?prompt_type=tool_invocation"
```

Each should return exactly 1 prompt!

---

## NEW: Dynamic Prompt Types Endpoint ✨

**Endpoint**: `GET /api/v1/prompts/types/list`

Get all available prompt types dynamically from the backend - no hardcoding needed!

### Response Structure
```json
{
  "types": [
    {
      "prompt_type": "system",
      "description": "Main AI assistant identity - defines Compaytence AI persona and guidelines",
      "category": "Core",
      "active_count": 1,
      "total_count": 1,
      "example_name": "main_system_prompt"
    },
    ...
  ],
  "total_types": 6
}
```

### Frontend Implementation

```typescript
// Fetch all prompt types on component mount
const [promptTypes, setPromptTypes] = useState([]);

useEffect(() => {
  fetch('/api/v1/prompts/types/list')
    .then(res => res.json())
    .then(data => setPromptTypes(data.types));
}, []);

// Build dynamic dropdown
<select>
  {promptTypes.map(type => (
    <option key={type.prompt_type} value={type.prompt_type}>
      {type.description} ({type.active_count} active)
    </option>
  ))}
</select>
```

### Group by Category

```typescript
const groupedTypes = promptTypes.reduce((acc, type) => {
  if (!acc[type.category]) acc[type.category] = [];
  acc[type.category].push(type);
  return acc;
}, {});

// Render as grouped dropdowns
Object.entries(groupedTypes).map(([category, types]) => (
  <optgroup key={category} label={category}>
    {types.map(type => (
      <option value={type.prompt_type}>{type.description}</option>
    ))}
  </optgroup>
));
```

### Benefits

✅ **Future-Proof**: New prompt types automatically appear in UI
✅ **No Hardcoding**: Descriptions come from backend
✅ **Category Grouping**: UI can group by Core, Analysis, Tools, etc.
✅ **Count Display**: Show how many active/total prompts per type

---

## Complete Example

```typescript
interface PromptTypeInfo {
  prompt_type: string;
  description: string;
  category: string;
  active_count: number;
  total_count: number;
  example_name: string;
}

const PromptManager = () => {
  const [promptTypes, setPromptTypes] = useState<PromptTypeInfo[]>([]);
  const [selectedType, setSelectedType] = useState('');
  const [prompts, setPrompts] = useState([]);

  // Fetch prompt types on mount
  useEffect(() => {
    fetch('/api/v1/prompts/types/list')
      .then(res => res.json())
      .then(data => {
        setPromptTypes(data.types);
        if (data.types.length > 0) {
          setSelectedType(data.types[0].prompt_type);
        }
      });
  }, []);

  // Fetch prompts when type changes
  useEffect(() => {
    if (selectedType) {
      fetch(`/api/v1/prompts?prompt_type=${selectedType}&active_only=true`)
        .then(res => res.json())
        .then(data => setPrompts(data.prompts));
    }
  }, [selectedType]);

  return (
    <div>
      <h2>Prompt Management</h2>

      {/* Dynamic type selector */}
      <select value={selectedType} onChange={e => setSelectedType(e.target.value)}>
        {promptTypes.map(type => (
          <option key={type.prompt_type} value={type.prompt_type}>
            {type.category}: {type.description} ({type.active_count}/{type.total_count})
          </option>
        ))}
      </select>

      {/* Prompts for selected type */}
      {prompts.map(prompt => (
        <div key={prompt.id}>
          <h3>{prompt.name} v{prompt.version}</h3>
          <textarea value={prompt.content} />
        </div>
      ))}
    </div>
  );
};
```

---

**Date Updated**: 2025-11-08
