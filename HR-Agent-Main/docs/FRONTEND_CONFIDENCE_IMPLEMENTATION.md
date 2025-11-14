# Frontend Implementation Guide: Confidence Scoring System

**Date**: 2025-01-08
**For**: Frontend Team
**Status**: Ready for Implementation

---

## Overview

This guide provides complete specifications for implementing the new admin UI for the confidence scoring system. The system allows admins to:

1. **Choose calculation method**: Formula, LLM, or Hybrid
2. **Configure LLM provider and model**: OpenAI, Anthropic (Claude), or Azure
3. **Edit confidence evaluation prompt**: Full prompt editor with version management
4. **Adjust weights**: For hybrid mode (formula vs LLM weighting)

---

## Table of Contents

1. [Backend API Reference](#backend-api-reference)
2. [UI Component Specifications](#ui-component-specifications)
3. [State Management](#state-management)
4. [API Integration Examples](#api-integration-examples)
5. [User Flows](#user-flows)
6. [Validation Rules](#validation-rules)
7. [Cost Estimation](#cost-estimation)
8. [Testing Checklist](#testing-checklist)

---

## Backend API Reference

### 1. Agent Configuration Endpoints

#### Get Current Configuration
```http
GET /api/v1/admin/agent-config
```

**Response**:
```json
{
  "id": "uuid",
  "name": "default_agent_config",
  "version": 1,
  "environment": "development",
  "config": {
    "confidence_calculation": {
      "method": "formula",
      "hybrid_settings": {
        "formula_weight": 0.60,
        "llm_weight": 0.40
      },
      "llm_settings": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 100,
        "timeout_ms": 2000
      },
      "formula_weights": {
        "similarity": 0.80,
        "source_quality": 0.10,
        "response_length": 0.10
      }
    }
  }
}
```

#### Update Configuration
```http
PUT /api/v1/admin/agent-config
Content-Type: application/json

{
  "config": {
    "confidence_calculation": {
      "method": "hybrid",
      "hybrid_settings": {
        "formula_weight": 0.65,
        "llm_weight": 0.35
      },
      "llm_settings": {
        "provider": "anthropic",
        "model": "claude-3-haiku-20240307",
        "temperature": 0.1,
        "max_tokens": 100,
        "timeout_ms": 2000
      }
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "config_id": "uuid"
}
```

---

### 2. LLM Models Endpoint (Existing - Reuse)

**⚠️ IMPORTANT**: This endpoint already exists for system prompt configuration. Reuse it for consistency.

```http
GET /api/v1/admin/llm/models?provider={provider}
```

**Parameters**:
- `provider`: `openai` | `anthropic` | `azure`

**Response Example** (OpenAI):
```json
{
  "provider": "openai",
  "models": [
    {
      "id": "gpt-4",
      "name": "GPT-4",
      "description": "Most capable model, higher cost",
      "context_window": 8192,
      "cost_per_1k_tokens": 0.03
    },
    {
      "id": "gpt-4o",
      "name": "GPT-4 Optimized",
      "description": "Faster GPT-4 variant",
      "context_window": 128000,
      "cost_per_1k_tokens": 0.005
    },
    {
      "id": "gpt-4o-mini",
      "name": "GPT-4o Mini",
      "description": "Cost-effective GPT-4 variant",
      "context_window": 128000,
      "cost_per_1k_tokens": 0.00015
    }
  ]
}
```

**Response Example** (Anthropic):
```json
{
  "provider": "anthropic",
  "models": [
    {
      "id": "claude-3-5-sonnet-20241022",
      "name": "Claude 3.5 Sonnet",
      "description": "Most intelligent model",
      "context_window": 200000,
      "cost_per_1k_tokens": 0.003
    },
    {
      "id": "claude-3-haiku-20240307",
      "name": "Claude 3 Haiku",
      "description": "Fastest and most cost-effective",
      "context_window": 200000,
      "cost_per_1k_tokens": 0.00025
    }
  ]
}
```

---

### 3. Prompt Management Endpoints (Existing - Reuse)

**⚠️ IMPORTANT**: These endpoints already exist for other prompts. Reuse them for `confidence_evaluation_prompt`.

#### Get All Prompt Versions
```http
GET /api/v1/admin/prompts/confidence_evaluation_prompt
```

**Response**:
```json
{
  "prompt_name": "confidence_evaluation_prompt",
  "versions": [
    {
      "id": "uuid-1",
      "version": 1,
      "content": "Evaluate the confidence...",
      "active": false,
      "created_at": "2025-01-01T10:00:00Z",
      "created_by": "admin@example.com",
      "notes": "Initial version"
    },
    {
      "id": "uuid-2",
      "version": 2,
      "content": "Enhanced evaluation...",
      "active": true,
      "created_at": "2025-01-08T15:30:00Z",
      "created_by": "admin@example.com",
      "notes": "Improved scoring criteria"
    }
  ]
}
```

#### Get Active Prompt Version
```http
GET /api/v1/admin/prompts/confidence_evaluation_prompt/active
```

**Response**:
```json
{
  "id": "uuid-2",
  "version": 2,
  "content": "Enhanced evaluation...",
  "active": true,
  "template_variables": ["query", "context", "response"]
}
```

#### Create New Prompt Version
```http
POST /api/v1/admin/prompts/confidence_evaluation_prompt
Content-Type: application/json

{
  "content": "New confidence evaluation prompt...",
  "notes": "Updated to prioritize factual accuracy",
  "created_by": "admin@example.com"
}
```

**Response**:
```json
{
  "success": true,
  "version_id": "uuid-3",
  "version": 3,
  "message": "New prompt version created successfully"
}
```

#### Activate Prompt Version
```http
PUT /api/v1/admin/prompts/confidence_evaluation_prompt/{version_id}/activate
```

**Response**:
```json
{
  "success": true,
  "message": "Prompt version activated successfully",
  "active_version": 3
}
```

#### Preview Prompt with Sample Data
```http
POST /api/v1/admin/prompts/confidence_evaluation_prompt/preview
Content-Type: application/json

{
  "content": "Evaluate the confidence in the response...",
  "sample_data": {
    "query": "What is ACH payment?",
    "context": "ACH stands for Automated Clearing House...",
    "response": "ACH is a network used for electronic payments..."
  }
}
```

**Response**:
```json
{
  "rendered_prompt": "Evaluate the confidence in the response:\n\nQuery: What is ACH payment?\nContext: ACH stands for...\nResponse: ACH is a network..."
}
```

---

## UI Component Specifications

### Page Location
```
frontend/app/admin/agent-config/confidence/page.tsx
```

### Layout Structure

```tsx
import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function ConfidenceConfigPage() {
  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Confidence Scoring Configuration</h1>
        <p className="text-muted-foreground">
          Configure how the AI agent calculates confidence in its responses
        </p>
      </div>

      {/* Section 1: Method Selection */}
      <MethodSelector />

      {/* Section 2: LLM Configuration (shown for LLM and Hybrid modes) */}
      <LLMConfiguration />

      {/* Section 3: Hybrid Weights (shown only for Hybrid mode) */}
      <HybridWeights />

      {/* Section 4: Formula Weights (shown for Formula and Hybrid modes) */}
      <FormulaWeights />

      {/* Section 5: Confidence Prompt Editor (shown for LLM and Hybrid modes) */}
      <PromptEditor />

      {/* Section 6: Cost Estimator */}
      <CostEstimator />

      {/* Save Button */}
      <div className="flex justify-end space-x-4">
        <Button variant="outline" onClick={handleReset}>Reset to Defaults</Button>
        <Button onClick={handleSave}>Save Configuration</Button>
      </div>
    </div>
  );
}
```

---

### Component 1: Method Selector

```tsx
function MethodSelector() {
  const [method, setMethod] = useState<'formula' | 'llm' | 'hybrid'>('formula');

  return (
    <Card>
      <CardHeader>
        <CardTitle>Calculation Method</CardTitle>
        <CardDescription>
          Choose how confidence scores are calculated
        </CardDescription>
      </CardHeader>
      <CardContent>
        <RadioGroup value={method} onValueChange={setMethod} className="space-y-4">
          {/* Formula Option */}
          <div className="flex items-start space-x-3 border rounded-lg p-4 cursor-pointer hover:bg-accent">
            <RadioGroupItem value="formula" id="formula" className="mt-1" />
            <label htmlFor="formula" className="flex-1 cursor-pointer">
              <div className="flex items-center space-x-2">
                <span className="font-medium">Formula-Based</span>
                <Badge variant="secondary">Fast</Badge>
                <Badge variant="success">No Cost</Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Algorithmic calculation based on retrieval quality, source count, and response completeness.
                Instant results with zero LLM costs.
              </p>
              <div className="mt-2 text-xs text-muted-foreground">
                <strong>Factors:</strong> 80% similarity score + 10% source quality + 10% response length
              </div>
            </label>
          </div>

          {/* LLM Option */}
          <div className="flex items-start space-x-3 border rounded-lg p-4 cursor-pointer hover:bg-accent">
            <RadioGroupItem value="llm" id="llm" className="mt-1" />
            <label htmlFor="llm" className="flex-1 cursor-pointer">
              <div className="flex items-center space-x-2">
                <span className="font-medium">LLM-Based</span>
                <Badge variant="secondary">Accurate</Badge>
                <Badge variant="warning">LLM Cost</Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Semantic evaluation using AI to judge response quality, relevance, and confidence.
                More accurate but incurs LLM costs on every query.
              </p>
              <div className="mt-2 text-xs text-muted-foreground">
                <strong>Cost:</strong> ~$0.20-2.00 per 10K queries (depending on model)
              </div>
            </label>
          </div>

          {/* Hybrid Option */}
          <div className="flex items-start space-x-3 border rounded-lg p-4 cursor-pointer hover:bg-accent">
            <RadioGroupItem value="hybrid" id="hybrid" className="mt-1" />
            <label htmlFor="hybrid" className="flex-1 cursor-pointer">
              <div className="flex items-center space-x-2">
                <span className="font-medium">Hybrid (Recommended)</span>
                <Badge variant="default">Best Balance</Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Combines both formula and LLM scores with configurable weights.
                Balances retrieval quality with semantic understanding.
              </p>
              <div className="mt-2 text-xs text-muted-foreground">
                <strong>Default:</strong> 60% formula + 40% LLM
              </div>
            </label>
          </div>
        </RadioGroup>
      </CardContent>
    </Card>
  );
}
```

---

### Component 2: LLM Configuration

```tsx
function LLMConfiguration() {
  const [provider, setProvider] = useState<'openai' | 'anthropic' | 'azure'>('openai');
  const [model, setModel] = useState('gpt-4o-mini');
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [temperature, setTemperature] = useState(0.1);
  const [maxTokens, setMaxTokens] = useState(100);
  const [timeoutMs, setTimeoutMs] = useState(2000);

  // Fetch models when provider changes
  useEffect(() => {
    const fetchModels = async () => {
      setLoadingModels(true);
      try {
        const response = await fetch(`/api/v1/admin/llm/models?provider=${provider}`);
        const data = await response.json();
        setAvailableModels(data.models);

        // Auto-select default model for provider
        if (data.models.length > 0) {
          const defaultModel = data.models.find(m => m.id.includes('mini') || m.id.includes('haiku'))
            || data.models[0];
          setModel(defaultModel.id);
        }
      } catch (error) {
        console.error('Failed to fetch models:', error);
      } finally {
        setLoadingModels(false);
      }
    };

    if (provider) {
      fetchModels();
    }
  }, [provider]);

  // Only show if method is LLM or Hybrid
  if (method === 'formula') return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Configuration</CardTitle>
        <CardDescription>
          Configure the language model used for confidence evaluation
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Provider Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Provider</label>
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="openai">
                <div className="flex items-center space-x-2">
                  <span>OpenAI</span>
                  <Badge variant="outline" className="ml-2">GPT-4, GPT-4o</Badge>
                </div>
              </SelectItem>
              <SelectItem value="anthropic">
                <div className="flex items-center space-x-2">
                  <span>Anthropic</span>
                  <Badge variant="outline" className="ml-2">Claude 3.5</Badge>
                </div>
              </SelectItem>
              <SelectItem value="azure">
                <div className="flex items-center space-x-2">
                  <span>Azure OpenAI</span>
                  <Badge variant="outline" className="ml-2">Enterprise</Badge>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Model Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Model</label>
          <Select value={model} onValueChange={setModel} disabled={loadingModels}>
            <SelectTrigger>
              <SelectValue placeholder={loadingModels ? "Loading models..." : "Select model"} />
            </SelectTrigger>
            <SelectContent>
              {availableModels.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  <div className="flex flex-col">
                    <span className="font-medium">{m.name}</span>
                    <span className="text-xs text-muted-foreground">{m.description}</span>
                    <span className="text-xs text-muted-foreground">
                      ${m.cost_per_1k_tokens.toFixed(5)} per 1K tokens
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Advanced Settings */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">
              Temperature: {temperature.toFixed(1)}
            </label>
            <Slider
              value={[temperature]}
              onValueChange={([v]) => setTemperature(v)}
              min={0}
              max={2}
              step={0.1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Lower = more deterministic (recommended: 0.1)
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Max Tokens: {maxTokens}
            </label>
            <Slider
              value={[maxTokens]}
              onValueChange={([v]) => setMaxTokens(v)}
              min={50}
              max={500}
              step={10}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Response length limit (recommended: 100)
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">
            Timeout: {timeoutMs}ms
          </label>
          <Slider
            value={[timeoutMs]}
            onValueChange={([v]) => setTimeoutMs(v)}
            min={1000}
            max={10000}
            step={500}
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            If LLM doesn't respond in time, fallback to formula (recommended: 2000ms)
          </p>
        </div>

        <Alert>
          <AlertDescription>
            💡 <strong>Recommendation:</strong> Use GPT-4o-mini or Claude Haiku for cost-effective confidence evaluation.
            These models provide excellent accuracy at ~$0.20 per 10K queries.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
```

---

### Component 3: Hybrid Weights

```tsx
function HybridWeights() {
  const [formulaWeight, setFormulaWeight] = useState(0.60);
  const [llmWeight, setLLMWeight] = useState(0.40);

  // Auto-adjust LLM weight to ensure sum = 1.0
  const handleFormulaWeightChange = (value: number) => {
    setFormulaWeight(value);
    setLLMWeight(1.0 - value);
  };

  // Only show if method is Hybrid
  if (method !== 'hybrid') return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hybrid Weighting</CardTitle>
        <CardDescription>
          Adjust the balance between formula and LLM scores
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">
              Formula Weight: {(formulaWeight * 100).toFixed(0)}%
            </label>
            <span className="text-xs text-muted-foreground">
              Retrieval quality metrics
            </span>
          </div>
          <Slider
            value={[formulaWeight]}
            onValueChange={([v]) => handleFormulaWeightChange(v)}
            min={0}
            max={1}
            step={0.05}
            className="w-full"
          />
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">
              LLM Weight: {(llmWeight * 100).toFixed(0)}%
            </label>
            <span className="text-xs text-muted-foreground">
              Semantic quality evaluation
            </span>
          </div>
          <Slider
            value={[llmWeight]}
            onValueChange={([v]) => handleFormulaWeightChange(1.0 - v)}
            min={0}
            max={1}
            step={0.05}
            className="w-full"
          />
        </div>

        <Alert>
          <AlertDescription>
            📊 <strong>Final Score:</strong> (Formula × {(formulaWeight * 100).toFixed(0)}%) +
            (LLM × {(llmWeight * 100).toFixed(0)}%)
          </AlertDescription>
        </Alert>

        <div className="grid grid-cols-3 gap-4 text-center">
          <Button
            variant="outline"
            onClick={() => handleFormulaWeightChange(0.80)}
            className="text-xs"
          >
            Favor Formula<br/>(80/20)
          </Button>
          <Button
            variant="outline"
            onClick={() => handleFormulaWeightChange(0.60)}
            className="text-xs"
          >
            Balanced<br/>(60/40)
          </Button>
          <Button
            variant="outline"
            onClick={() => handleFormulaWeightChange(0.40)}
            className="text-xs"
          >
            Favor LLM<br/>(40/60)
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

---

### Component 4: Formula Weights

```tsx
function FormulaWeights() {
  const [similarityWeight, setSimilarityWeight] = useState(0.80);
  const [sourceQualityWeight, setSourceQualityWeight] = useState(0.10);
  const [responseLengthWeight, setResponseLengthWeight] = useState(0.10);

  // Auto-adjust to ensure sum = 1.0
  const handleWeightChange = (
    setter: (v: number) => void,
    value: number,
    otherSetter1: (v: number) => void,
    otherSetter2: (v: number) => void
  ) => {
    setter(value);
    const remaining = 1.0 - value;
    // Distribute remaining equally
    otherSetter1(remaining / 2);
    otherSetter2(remaining / 2);
  };

  // Only show if method is Formula or Hybrid
  if (method === 'llm') return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Formula Weights</CardTitle>
        <CardDescription>
          Adjust the algorithmic confidence factors
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Alert>
          <AlertDescription>
            ℹ️ These weights control how the formula calculates confidence from retrieval metrics.
            Total must equal 100%.
          </AlertDescription>
        </Alert>

        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium">
                Similarity Score: {(similarityWeight * 100).toFixed(0)}%
              </label>
              <span className="text-xs text-muted-foreground">
                How well documents match the query
              </span>
            </div>
            <Slider
              value={[similarityWeight]}
              onValueChange={([v]) =>
                handleWeightChange(setSimilarityWeight, v, setSourceQualityWeight, setResponseLengthWeight)
              }
              min={0.5}
              max={0.95}
              step={0.05}
              className="w-full"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium">
                Source Quality: {(sourceQualityWeight * 100).toFixed(0)}%
              </label>
              <span className="text-xs text-muted-foreground">
                Number of high-quality sources (similarity &gt; 0.75)
              </span>
            </div>
            <Slider
              value={[sourceQualityWeight]}
              onValueChange={([v]) =>
                handleWeightChange(setSourceQualityWeight, v, setSimilarityWeight, setResponseLengthWeight)
              }
              min={0}
              max={0.3}
              step={0.05}
              className="w-full"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium">
                Response Length: {(responseLengthWeight * 100).toFixed(0)}%
              </label>
              <span className="text-xs text-muted-foreground">
                Completeness of the generated response
              </span>
            </div>
            <Slider
              value={[responseLengthWeight]}
              onValueChange={([v]) =>
                handleWeightChange(setResponseLengthWeight, v, setSimilarityWeight, setSourceQualityWeight)
              }
              min={0}
              max={0.3}
              step={0.05}
              className="w-full"
            />
          </div>
        </div>

        <div className="p-4 bg-muted rounded-lg">
          <div className="text-sm font-medium mb-2">Total Weight Check</div>
          <div className="flex items-center space-x-2">
            <div className="flex-1 bg-background rounded-full h-2 overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${(similarityWeight + sourceQualityWeight + responseLengthWeight) * 100}%` }}
              />
            </div>
            <span className={`text-sm font-medium ${
              Math.abs((similarityWeight + sourceQualityWeight + responseLengthWeight) - 1.0) < 0.01
                ? 'text-green-600'
                : 'text-red-600'
            }`}>
              {((similarityWeight + sourceQualityWeight + responseLengthWeight) * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <Button
          variant="outline"
          onClick={() => {
            setSimilarityWeight(0.80);
            setSourceQualityWeight(0.10);
            setResponseLengthWeight(0.10);
          }}
          className="w-full"
        >
          Reset to Defaults (80/10/10)
        </Button>
      </CardContent>
    </Card>
  );
}
```

---

### Component 5: Prompt Editor

```tsx
function PromptEditor() {
  const [promptContent, setPromptContent] = useState('');
  const [promptVersions, setPromptVersions] = useState([]);
  const [activeVersion, setActiveVersion] = useState(null);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState('');

  // Load prompt versions on mount
  useEffect(() => {
    fetchPromptVersions();
  }, []);

  const fetchPromptVersions = async () => {
    const response = await fetch('/api/v1/admin/prompts/confidence_evaluation_prompt');
    const data = await response.json();
    setPromptVersions(data.versions);

    const active = data.versions.find(v => v.active);
    if (active) {
      setActiveVersion(active);
      setSelectedVersion(active.id);
      setPromptContent(active.content);
    }
  };

  const handleVersionChange = (versionId: string) => {
    setSelectedVersion(versionId);
    const version = promptVersions.find(v => v.id === versionId);
    if (version) {
      setPromptContent(version.content);
    }
  };

  const handleSaveVersion = async () => {
    setSaving(true);
    try {
      const response = await fetch('/api/v1/admin/prompts/confidence_evaluation_prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: promptContent,
          notes: notes,
          created_by: currentUser.email
        })
      });

      const data = await response.json();
      toast.success('New prompt version created successfully');
      fetchPromptVersions();
      setNotes('');
    } catch (error) {
      toast.error('Failed to save prompt version');
    } finally {
      setSaving(false);
    }
  };

  const handleActivateVersion = async (versionId: string) => {
    try {
      await fetch(`/api/v1/admin/prompts/confidence_evaluation_prompt/${versionId}/activate`, {
        method: 'PUT'
      });
      toast.success('Prompt version activated');
      fetchPromptVersions();
    } catch (error) {
      toast.error('Failed to activate version');
    }
  };

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const response = await fetch('/api/v1/admin/prompts/confidence_evaluation_prompt/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: promptContent,
          sample_data: {
            query: 'What is ACH payment?',
            context: 'ACH stands for Automated Clearing House. It is a network used for electronic payments and money transfers...',
            response: 'ACH payment is an electronic payment method that transfers funds directly between bank accounts...'
          }
        })
      });

      const data = await response.json();
      setPreviewResult(data.rendered_prompt);
    } catch (error) {
      toast.error('Preview failed');
    } finally {
      setPreviewing(false);
    }
  };

  // Only show if method is LLM or Hybrid
  if (method === 'formula') return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Confidence Evaluation Prompt</CardTitle>
        <CardDescription>
          Edit the prompt used by the LLM to evaluate confidence
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Alert>
          <AlertDescription>
            <strong>Template Variables:</strong> Use <code>{`{query}`}</code>, <code>{`{context}`}</code>,
            and <code>{`{response}`}</code> in your prompt. These will be replaced with actual values at runtime.
          </AlertDescription>
        </Alert>

        <Tabs defaultValue="editor">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="editor">Editor</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="versions">Version History</TabsTrigger>
          </TabsList>

          <TabsContent value="editor" className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Prompt Content</label>
              <Textarea
                value={promptContent}
                onChange={(e) => setPromptContent(e.target.value)}
                rows={16}
                className="font-mono text-sm"
                placeholder="Enter confidence evaluation prompt..."
              />
              <p className="text-xs text-muted-foreground">
                {promptContent.length} characters
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Version Notes</label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Describe what changed in this version..."
              />
            </div>

            <div className="flex space-x-2">
              <Button onClick={handlePreview} variant="outline" disabled={previewing}>
                {previewing ? 'Previewing...' : 'Preview with Sample Data'}
              </Button>
              <Button onClick={handleSaveVersion} disabled={saving || !promptContent.trim()}>
                {saving ? 'Saving...' : 'Save as New Version'}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="preview" className="space-y-4">
            {previewResult ? (
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-sm font-medium mb-2">Rendered Prompt:</div>
                <pre className="text-xs whitespace-pre-wrap font-mono">{previewResult}</pre>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Click "Preview with Sample Data" in the Editor tab to see the rendered prompt
              </div>
            )}
          </TabsContent>

          <TabsContent value="versions" className="space-y-4">
            <div className="space-y-2">
              {promptVersions.map((version) => (
                <div
                  key={version.id}
                  className={`border rounded-lg p-4 ${
                    version.active ? 'border-primary bg-primary/5' : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">Version {version.version}</span>
                      {version.active && <Badge>Active</Badge>}
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleVersionChange(version.id)}
                      >
                        View
                      </Button>
                      {!version.active && (
                        <Button
                          size="sm"
                          onClick={() => handleActivateVersion(version.id)}
                        >
                          Activate
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <div>Created: {new Date(version.created_at).toLocaleString()}</div>
                    <div>By: {version.created_by}</div>
                    {version.notes && <div className="mt-1 italic">"{version.notes}"</div>}
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
```

---

### Component 6: Cost Estimator

```tsx
function CostEstimator() {
  const [monthlyQueries, setMonthlyQueries] = useState(10000);

  const calculateCost = () => {
    if (method === 'formula') {
      return { total: 0, breakdown: 'No LLM costs' };
    }

    // Get selected model's cost
    const selectedModel = availableModels.find(m => m.id === model);
    if (!selectedModel) return { total: 0, breakdown: 'Select a model' };

    // Estimate tokens per query (prompt + response)
    const tokensPerQuery = 150; // ~100 prompt + ~50 response
    const totalTokens = (monthlyQueries * tokensPerQuery) / 1000; // in thousands
    const llmCost = totalTokens * selectedModel.cost_per_1k_tokens;

    if (method === 'llm') {
      return {
        total: llmCost,
        breakdown: `${monthlyQueries.toLocaleString()} queries × ${tokensPerQuery} tokens × $${selectedModel.cost_per_1k_tokens.toFixed(5)}/1K`
      };
    }

    if (method === 'hybrid') {
      // Hybrid costs same as LLM (always calculates both)
      return {
        total: llmCost,
        breakdown: `Same as LLM (always calculates both scores): ${monthlyQueries.toLocaleString()} queries × ${tokensPerQuery} tokens × $${selectedModel.cost_per_1k_tokens.toFixed(5)}/1K`
      };
    }
  };

  const cost = calculateCost();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cost Estimator</CardTitle>
        <CardDescription>
          Estimate monthly LLM costs for confidence evaluation
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-medium">
            Monthly Queries: {monthlyQueries.toLocaleString()}
          </label>
          <Slider
            value={[monthlyQueries]}
            onValueChange={([v]) => setMonthlyQueries(v)}
            min={1000}
            max={100000}
            step={1000}
            className="w-full"
          />
        </div>

        <div className="p-6 bg-gradient-to-r from-primary/10 to-primary/5 rounded-lg">
          <div className="text-center">
            <div className="text-sm text-muted-foreground mb-1">Estimated Monthly Cost</div>
            <div className="text-4xl font-bold text-primary">
              ${cost.total.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground mt-2">{cost.breakdown}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="p-3 bg-muted rounded-lg">
            <div className="text-muted-foreground">Cost per 1K queries</div>
            <div className="font-medium">${((cost.total / monthlyQueries) * 1000).toFixed(3)}</div>
          </div>
          <div className="p-3 bg-muted rounded-lg">
            <div className="text-muted-foreground">Cost per query</div>
            <div className="font-medium">${(cost.total / monthlyQueries).toFixed(5)}</div>
          </div>
        </div>

        <Alert>
          <AlertDescription>
            💡 <strong>Tip:</strong> For most use cases, GPT-4o-mini ($0.20/10K) or Claude Haiku ($0.15/10K)
            provide excellent accuracy at minimal cost.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
```

---

## State Management

### TypeScript Interfaces

```typescript
// types/confidence-config.ts

export type ConfidenceMethod = 'formula' | 'llm' | 'hybrid';
export type LLMProvider = 'openai' | 'anthropic' | 'azure';

export interface HybridSettings {
  formula_weight: number;
  llm_weight: number;
}

export interface LLMSettings {
  provider: LLMProvider;
  model: string;
  temperature: number;
  max_tokens: number;
  timeout_ms: number;
}

export interface FormulaWeights {
  similarity: number;
  source_quality: number;
  response_length: number;
}

export interface ConfidenceConfig {
  method: ConfidenceMethod;
  hybrid_settings: HybridSettings;
  llm_settings: LLMSettings;
  formula_weights: FormulaWeights;
}

export interface LLMModel {
  id: string;
  name: string;
  description: string;
  context_window: number;
  cost_per_1k_tokens: number;
}

export interface PromptVersion {
  id: string;
  version: number;
  content: string;
  active: boolean;
  created_at: string;
  created_by: string;
  notes?: string;
}
```

### React State Hook

```typescript
// hooks/useConfidenceConfig.ts

import { useState, useEffect } from 'react';
import { ConfidenceConfig, LLMModel, PromptVersion } from '@/types/confidence-config';

export function useConfidenceConfig() {
  const [config, setConfig] = useState<ConfidenceConfig | null>(null);
  const [availableModels, setAvailableModels] = useState<LLMModel[]>([]);
  const [promptVersions, setPromptVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Load configuration
  useEffect(() => {
    fetchConfig();
    fetchPromptVersions();
  }, []);

  // Fetch models when provider changes
  useEffect(() => {
    if (config?.llm_settings.provider) {
      fetchModels(config.llm_settings.provider);
    }
  }, [config?.llm_settings.provider]);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/admin/agent-config');
      const data = await response.json();
      setConfig(data.config.confidence_calculation);
    } catch (error) {
      console.error('Failed to fetch config:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchModels = async (provider: string) => {
    try {
      const response = await fetch(`/api/v1/admin/llm/models?provider=${provider}`);
      const data = await response.json();
      setAvailableModels(data.models);
    } catch (error) {
      console.error('Failed to fetch models:', error);
    }
  };

  const fetchPromptVersions = async () => {
    try {
      const response = await fetch('/api/v1/admin/prompts/confidence_evaluation_prompt');
      const data = await response.json();
      setPromptVersions(data.versions);
    } catch (error) {
      console.error('Failed to fetch prompt versions:', error);
    }
  };

  const saveConfig = async (updatedConfig: ConfidenceConfig) => {
    setSaving(true);
    try {
      const response = await fetch('/api/v1/admin/agent-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: {
            confidence_calculation: updatedConfig
          }
        })
      });

      if (response.ok) {
        setConfig(updatedConfig);
        return { success: true };
      } else {
        throw new Error('Failed to save configuration');
      }
    } catch (error) {
      console.error('Save failed:', error);
      return { success: false, error };
    } finally {
      setSaving(false);
    }
  };

  return {
    config,
    availableModels,
    promptVersions,
    loading,
    saving,
    saveConfig,
    fetchConfig,
    fetchPromptVersions
  };
}
```

---

## API Integration Examples

### Fetching Current Configuration

```typescript
const fetchConfig = async () => {
  const response = await fetch('/api/v1/admin/agent-config');
  const data = await response.json();

  // Extract confidence config
  const confidenceConfig = data.config.confidence_calculation;

  return confidenceConfig;
};
```

### Saving Configuration

```typescript
const saveConfig = async (config: ConfidenceConfig) => {
  const response = await fetch('/api/v1/admin/agent-config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      config: {
        confidence_calculation: config
      }
    })
  });

  if (!response.ok) {
    throw new Error('Failed to save configuration');
  }

  return response.json();
};
```

### Creating New Prompt Version

```typescript
const createPromptVersion = async (content: string, notes: string) => {
  const response = await fetch('/api/v1/admin/prompts/confidence_evaluation_prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      notes,
      created_by: currentUser.email
    })
  });

  return response.json();
};
```

### Activating Prompt Version

```typescript
const activatePromptVersion = async (versionId: string) => {
  const response = await fetch(
    `/api/v1/admin/prompts/confidence_evaluation_prompt/${versionId}/activate`,
    { method: 'PUT' }
  );

  return response.json();
};
```

---

## User Flows

### Flow 1: Switching to LLM Mode

1. Admin navigates to `/admin/agent-config/confidence`
2. Selects "LLM-Based" radio button
3. UI shows LLM Configuration section
4. Admin selects provider (e.g., "OpenAI")
5. System fetches available models
6. Admin selects model (e.g., "GPT-4o-mini")
7. (Optional) Admin adjusts temperature, max tokens, timeout
8. UI updates cost estimator
9. Admin clicks "Save Configuration"
10. System updates `agent_configs` in database
11. Success toast shown

### Flow 2: Editing Confidence Prompt

1. Admin is in LLM or Hybrid mode
2. Navigates to "Confidence Evaluation Prompt" section
3. Clicks "Editor" tab
4. Modifies prompt content with template variables
5. Adds version notes
6. Clicks "Preview with Sample Data"
7. Reviews rendered prompt in Preview tab
8. Clicks "Save as New Version"
9. System creates new prompt version
10. Admin clicks "Activate" on new version
11. New version becomes active

### Flow 3: Configuring Hybrid Mode

1. Admin selects "Hybrid" radio button
2. UI shows all sections: LLM Config + Hybrid Weights + Formula Weights + Prompt Editor
3. Admin adjusts formula weight slider (e.g., 65%)
4. System auto-adjusts LLM weight (35%)
5. Admin uses preset buttons (e.g., "Balanced 60/40")
6. Admin reviews cost estimator (same as LLM-only)
7. Clicks "Save Configuration"
8. System saves with hybrid method

---

## Validation Rules

### Client-Side Validation

```typescript
const validateConfig = (config: ConfidenceConfig): string[] => {
  const errors: string[] = [];

  // Hybrid weights must sum to 1.0
  if (config.method === 'hybrid') {
    const sum = config.hybrid_settings.formula_weight + config.hybrid_settings.llm_weight;
    if (Math.abs(sum - 1.0) > 0.01) {
      errors.push('Hybrid weights must sum to 100%');
    }
  }

  // Formula weights must sum to 1.0
  const formulaSum =
    config.formula_weights.similarity +
    config.formula_weights.source_quality +
    config.formula_weights.response_length;
  if (Math.abs(formulaSum - 1.0) > 0.01) {
    errors.push('Formula weights must sum to 100%');
  }

  // LLM settings required for LLM and Hybrid modes
  if (config.method !== 'formula') {
    if (!config.llm_settings.provider) {
      errors.push('LLM provider is required');
    }
    if (!config.llm_settings.model) {
      errors.push('LLM model is required');
    }
    if (config.llm_settings.temperature < 0 || config.llm_settings.temperature > 2) {
      errors.push('Temperature must be between 0 and 2');
    }
    if (config.llm_settings.max_tokens < 50 || config.llm_settings.max_tokens > 500) {
      errors.push('Max tokens must be between 50 and 500');
    }
  }

  return errors;
};
```

### Server-Side Validation

Backend should validate the same rules using Pydantic models:

```python
# app/models/config.py
from pydantic import BaseModel, Field, field_validator

class HybridConfidenceSettings(BaseModel):
    formula_weight: float = Field(ge=0.0, le=1.0)
    llm_weight: float = Field(ge=0.0, le=1.0)

    @field_validator('llm_weight')
    def weights_must_sum_to_one(cls, v, info):
        if abs((info.data.get('formula_weight', 0) + v) - 1.0) > 0.01:
            raise ValueError('Weights must sum to 1.0')
        return v
```

---

## Cost Estimation

### Default Cost Assumptions

| Model | Cost per 1K Tokens | Tokens per Query | Cost per 10K Queries |
|-------|-------------------|------------------|---------------------|
| GPT-4 | $0.03 | 150 | ~$45.00 |
| GPT-4o | $0.005 | 150 | ~$7.50 |
| GPT-4o-mini | $0.00015 | 150 | ~$0.23 |
| Claude 3.5 Sonnet | $0.003 | 150 | ~$4.50 |
| Claude 3 Haiku | $0.00025 | 150 | ~$0.38 |
| Azure GPT-4o | $0.005 | 150 | ~$7.50 |

**Tokens per Query Breakdown**:
- Prompt: ~100 tokens (query + context + response + system prompt)
- Response: ~50 tokens (confidence score + brief explanation)
- **Total**: ~150 tokens per query

**Formula**:
```
Monthly Cost = (Monthly Queries × Tokens per Query ÷ 1000) × Cost per 1K Tokens
```

**Example** (GPT-4o-mini, 10K queries/month):
```
Cost = (10,000 × 150 ÷ 1000) × $0.00015
     = 1,500 × $0.00015
     = $0.225 per month
```

---

## Testing Checklist

### Functional Tests

- [ ] **Method Selection**
  - [ ] Switching between Formula/LLM/Hybrid shows/hides correct sections
  - [ ] Default method (Formula) loads correctly
  - [ ] Save persists selected method

- [ ] **LLM Configuration**
  - [ ] Provider dropdown populates correctly
  - [ ] Model dropdown fetches models based on provider
  - [ ] Default model auto-selected when provider changes
  - [ ] Temperature, max tokens, timeout sliders work
  - [ ] Validation prevents invalid values

- [ ] **Hybrid Weights**
  - [ ] Sliders auto-adjust to maintain 100% total
  - [ ] Preset buttons (80/20, 60/40, 40/60) work
  - [ ] Final score formula displays correctly
  - [ ] Validation prevents weights ≠ 100%

- [ ] **Formula Weights**
  - [ ] Three weight sliders function correctly
  - [ ] Total weight indicator shows correct percentage
  - [ ] "Reset to Defaults" button restores 80/10/10
  - [ ] Validation prevents weights ≠ 100%

- [ ] **Prompt Editor**
  - [ ] Editor tab allows text editing
  - [ ] Template variables documented
  - [ ] Preview tab shows rendered prompt
  - [ ] Version History tab shows all versions
  - [ ] "Save as New Version" creates version
  - [ ] "Activate" button switches active version
  - [ ] Active version badge displays correctly

- [ ] **Cost Estimator**
  - [ ] Monthly queries slider updates calculation
  - [ ] Cost changes when model changes
  - [ ] Formula mode shows $0 cost
  - [ ] Hybrid mode shows same cost as LLM
  - [ ] Cost breakdown text is accurate

- [ ] **Save/Reset**
  - [ ] "Save Configuration" button saves to API
  - [ ] Success toast appears on save
  - [ ] Error toast appears on failure
  - [ ] "Reset to Defaults" restores initial values
  - [ ] Unsaved changes warning (optional)

### Integration Tests

- [ ] Configuration loads from `/api/v1/admin/agent-config`
- [ ] Models fetch from `/api/v1/admin/llm/models?provider={provider}`
- [ ] Prompt versions fetch from `/api/v1/admin/prompts/confidence_evaluation_prompt`
- [ ] Save updates database correctly
- [ ] New prompt version created successfully
- [ ] Prompt version activation works
- [ ] Changes reflected in agent behavior (backend integration test)

### Edge Cases

- [ ] No internet connection (error handling)
- [ ] API timeout (graceful degradation)
- [ ] Invalid JSON response (error handling)
- [ ] Very large prompt (character limit)
- [ ] Very high monthly queries (cost display)
- [ ] Switching providers mid-edit (state preservation)
- [ ] Multiple admins editing simultaneously (conflict resolution)

### Browser Compatibility

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)

### Accessibility

- [ ] Keyboard navigation works
- [ ] Screen reader compatibility
- [ ] ARIA labels present
- [ ] Focus indicators visible
- [ ] Color contrast meets WCAG AA

---

## Implementation Timeline

### Phase 1: Basic UI (Week 1)
- Method selector component
- LLM configuration component
- Basic save/load functionality

### Phase 2: Advanced Features (Week 2)
- Hybrid weights component
- Formula weights component
- Cost estimator
- Validation

### Phase 3: Prompt Editor (Week 2-3)
- Full prompt editor with tabs
- Version management
- Preview functionality
- Version history

### Phase 4: Polish & Testing (Week 3-4)
- Error handling
- Loading states
- Toast notifications
- Comprehensive testing
- Bug fixes

---

## Questions & Support

If you have questions during implementation:

1. **Backend API Issues**: Check backend logs, verify endpoint exists
2. **State Management**: Review `useConfidenceConfig` hook
3. **UI Component Issues**: Check component library documentation
4. **Validation Errors**: Review validation rules section
5. **Cost Calculation**: Review cost estimation formulas

**Backend Team Contact**: For API-related questions
**Design Team Contact**: For UI/UX clarifications
**QA Team Contact**: For testing support

---

## Appendix: Default Prompt Content

```markdown
You are a confidence evaluator for an AI-powered Q&A system.

Your task is to evaluate the confidence in the AI's response based on:
1. **Query Understanding**: How well does the response address the user's query?
2. **Context Relevance**: How relevant is the retrieved context to the query?
3. **Response Quality**: How accurate, complete, and well-structured is the response?
4. **Knowledge Gaps**: Are there any obvious gaps or uncertainties in the response?

**Query**: {query}

**Retrieved Context** (first 1000 chars):
{context}

**AI Response** (first 500 chars):
{response}

**Instructions**:
- Provide a confidence score between 0.0 and 1.0
- 1.0 = Extremely confident (complete, accurate, directly addresses query)
- 0.8-0.9 = High confidence (accurate but minor gaps)
- 0.6-0.7 = Moderate confidence (mostly accurate but some uncertainties)
- 0.4-0.5 = Low confidence (significant gaps or uncertainties)
- 0.0-0.3 = Very low confidence (inaccurate or doesn't address query)

Respond with ONLY a number between 0.0 and 1.0 (e.g., "0.85").
```

---

**End of Frontend Implementation Guide**
