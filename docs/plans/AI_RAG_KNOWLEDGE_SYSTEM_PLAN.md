# AI-Powered RAG Knowledge System - Implementation Plan

> **Priority:** 6 (Transformative)  
> **Complexity:** Very High  
> **Estimated Effort:** 8-12 weeks  
> **Status:** Planned

## Executive Summary

Build an AI-powered knowledge system using RAG (Retrieval-Augmented Generation) that leverages the app's comprehensive case database, TNM staging data, and learning content to provide intelligent tutoring, case-based reasoning, differential diagnosis assistance, and personalized learning recommendations.

---

## CRITICAL: App Style and Branding Guidelines

**All AI interfaces MUST follow existing app design patterns:**

### Color Palette
- Primary Blue: `#5E899E` (headers, AI interface chrome)
- Success Green: `#28a745` (correct answers, positive feedback)
- Warning Orange: `#ffc107` (caution, learning gaps)
- Info Blue: `#17a2b8` (AI suggestions, hints)
- AI Purple: `#6f42c1` (AI-generated content - distinguishing color)

### AI-Specific Styling
- AI responses: Light purple background with purple left border
- Citations: Inline links styled as badges pointing to cases
- Disclaimers: Muted small text at bottom

---

## Core Features

### 1. AI Case Companion
Contextual AI assistant available on every case page.
- Answer questions about the current case
- Explain TNM staging with calculator integration
- Find and link to similar cases
- Generate practice questions

### 2. Similar Case Finder
Semantic search for related cases.
- Embedding-based similarity
- Learning value scoring
- Side-by-side comparison

### 3. Differential Diagnosis Assistant
AI-powered differentials grounded in app data.
- Only suggests diagnoses in database
- Citations to specific cases
- Distinguishing features

### 4. Personalized Study Planner
Learning recommendations based on user history.
- Track Q&A performance
- Identify knowledge gaps
- Suggest next cases to study

### 5. AI Tutor (Socratic)
Interactive learning through guided questions.
- Socratic dialogue flow
- References case materials
- Adapts to responses

---

## Technical Architecture

### Vector Database (Supabase pgvector)

```sql
CREATE TABLE case_embeddings (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id),
    content_type VARCHAR(50),  -- 'diagnosis', 'discussion', 'qa'
    content_text TEXT,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### RAG Pipeline

1. **Embed query** - Convert user query to vector
2. **Retrieve** - Semantic + keyword hybrid search
3. **Rerank** - Sort by relevance
4. **Augment** - Build context from retrieved content
5. **Generate** - Claude API with grounded response
6. **Validate** - Check citations, add disclaimers

---

## Safety Requirements

- All responses must cite specific cases
- Never generate facts not in database
- Always include clinical disclaimer
- Citation validation before display
- Prohibited claims filtering

---

## Implementation Phases

### Phase 1: Vector Database (2 weeks)
- Set up pgvector in Supabase
- Create embedding tables
- Build embedding pipeline for cases

### Phase 2: RAG Pipeline (2 weeks)
- Query embedding
- Hybrid search
- Reranking
- Context builder

### Phase 3: LLM Integration (1 week)
- Prompt templates
- Claude API integration
- Response validation

### Phase 4: AI Companion (2 weeks)
- Chat UI component
- Conversation management
- Case-context awareness

### Phase 5: Study Planner (1 week)
- User learning analytics
- Recommendation engine
- Dashboard UI

### Phase 6: AI Tutor (2 weeks)
- Socratic dialogue
- Conversation flow
- Progress tracking

---

## Cost Considerations

| Component | Estimated Cost |
|-----------|---------------|
| OpenAI Embeddings | ~$50/month |
| Claude API | ~$100-500/month |
| Supabase pgvector | Included |
| **Total** | ~$150-550/month |

---

## Todos

- [ ] Set up pgvector in Supabase
- [ ] Build embedding pipeline for cases
- [ ] Implement hybrid search with reranking
- [ ] Integrate Claude API with prompts
- [ ] Build AI Case Companion chat interface
- [ ] Implement Similar Case Finder
- [ ] Build personalized Study Planner
- [ ] Implement Socratic AI Tutor
- [ ] Add citation validation and safety filters
- [ ] User testing and prompt optimization
