# CrewAI Multi-Agent Chatbot Architecture

## Overview

This is a sophisticated **multi-agent RAG chatbot** using CrewAI framework with hierarchical manager orchestration. The system processes banking queries through 5 specialized agents coordinated by a Manager agent.

## System Architecture

### Pipeline Flow

```
User Query
    ↓
[Manager Agent]
    ↓
├─→ [Intent Classifier Agent]
│   └─→ Parse intent, extract banking type, tier, product type
│       ↓
├─→ [Product Retriever Agent]
│   └─→ Search vector DB with metadata filters
│       ↓
├─→ [Eligibility Analyzer Agent] (Conditional: if eligibility_check intent)
│   └─→ Check employment compatibility, calculate credit limits
│       ↓
├─→ [Feature Comparator Agent] (Conditional: if comparison intent)
│   └─→ Create side-by-side comparison tables
│       ↓
└─→ [Response Formatter Agent]
    └─→ Format markdown response with citations
        ↓
    Final Response + Agent Chain + Metadata
```

## 5 Specialized Agents

### 1. Intent Classifier Agent
**Role**: Understand user intent and extract parameters
- **Detects Intent Types**:
  - `product_info`: User wants information about a product
  - `comparison`: User wants to compare products
  - `eligibility_check`: User wants to check eligibility
  - `feature_query`: User asking about specific features

- **Extracts Parameters**:
  - `banking_type`: "islamic" or "conventional"
  - `tier`: "gold", "platinum", "silver"
  - `product_type`: "credit", "debit", "loan"
  - `use_cases`: shopping, travel, dining, business, rewards

- **Tools**: Query parsing, intent detection regex patterns

### 2. Product Retriever Agent
**Role**: Find relevant products using metadata filtering
- **Searches Vector DB** with filters:
  - `banking_type` filter (islamic/conventional)
  - `product_type` filter (credit/debit)
  - `tier` filter (gold/platinum)
  - `feature_category` filter

- **Returns**: Top-K relevant chunks (default: 5)

- **Tools**: Vector DB search, metadata filter building, query optimization

### 3. Eligibility Analyzer Agent (Conditional)
**Role**: Check if user qualifies for recommended products
- **Runs Only When**: Intent = "eligibility_check"

- **Analyzes**:
  - Employment compatibility (matches user_employment against product requirements)
  - Credit limit availability (extracts from product text)
  - Age/income requirements (text-based analysis)

- **Returns**: Eligibility assessment per product

- **Tools**: Employment matching, text parsing for credit limits

### 4. Feature Comparator Agent (Conditional)
**Role**: Create comparison tables between products
- **Runs Only When**: Intent = "comparison"

- **Extracts Features**:
  - Credit limits
  - Interest-free periods
  - Rewards programs
  - Lounge access
  - Insurance coverage
  - Annual fees

- **Returns**: Markdown comparison table

- **Tools**: Feature extraction from text, table formatting

### 5. Response Formatter Agent
**Role**: Create well-structured, cited responses
- **Formats**:
  - Product overviews (organized by section)
  - Comparison tables (if applicable)
  - Source citations with confidence levels

- **Returns**: Final markdown-formatted response

- **Tools**: Markdown generation, citation builder

## Manager Agent (Orchestrator)

**Role**: Coordinate the team using hierarchical model

**Decision Logic**:
1. Always run Intent Classifier → Extract context
2. Always run Product Retriever → Get candidates
3. **IF** eligibility_check intent → Run Eligibility Analyzer
4. **IF** comparison intent → Run Feature Comparator
5. Always run Response Formatter → Output

**Features**:
- Fallback mechanism: If no products found, generate clarification prompts
- Session context awareness: Remember user preferences
- Agent chain tracking: Record which agents were used

## Metadata Strategy

### Folder Hierarchy Extraction
```
knowledge_base/
├─ conventional/          # banking_type
│  └─ credit/            # product_type
│     └─ i_need_a_credit_card/  # feature_category
│        └─ visa_gold_credit_card.md
└─ islami/
   └─ credit/
      └─ i_need_a_credit_card/
         └─ visa_hasanah_gold_credit_card.md
```

**Extracted Metadata**:
- `banking_type`: From 1st folder level (conventional/islami)
- `product_type`: From 2nd folder level (credit/debit/loan)
- `feature_category`: From 3rd folder level (i_need_a_credit_card, etc.)

### YAML Frontmatter Extraction
```yaml
---
product_id: visa_gold_001
product_name: Visa Gold Credit Card
tier: gold
use_cases:
  - shopping
  - travel
employment_suitable:
  - salaried
  - business_owner
---
```

**Extracted Fields**:
- `product_id`, `product_name`, `tier`
- `use_cases`: List of applicable scenarios
- `employment_suitable`: List of compatible employment types

## Chunking Strategy

### Hybrid Approach
1. **Semantic Boundaries**: Split by markdown headers (##)
2. **Size Limits**: 500 tokens per chunk (≈350 words)
3. **Overlap**: 20% overlap between chunks for context preservation

### Chunk Structure
```python
Chunk(
    chunk_id="visa_gold_001_features_1",
    product_id="visa_gold_001",
    product_name="Visa Gold Credit Card",
    banking_type="conventional",
    product_type="credit",
    feature_category="i_need_a_credit_card",
    tier="gold",
    section="Features",
    subsection="Rewards Program",
    content="...",
    use_cases=["shopping", "travel"],
    employment_suitable=["salaried"],
)
```

## Multi-Turn Conversation Management

### Session Context
- **Session ID**: Unique identifier for conversation
- **Message Window**: Keep 5-10 recent messages for context
- **Session TTL**: 30 minutes (configurable)
- **Auto-Cleanup**: Old sessions removed automatically

### Preference Persistence
Across turns, remember:
- `user_employment`: Employment type (salaried/business/student)
- `banking_type_preference`: Last stated preference (islamic/conventional)
- `tier_preference`: Last searched tier (gold/platinum)
- `use_cases`: Extracted use cases from queries

### Example Multi-Turn Flow
```
Turn 1:
User: "I'm salaried and looking for Islamic credit cards"
→ Extracted: employment=salaried, banking_type=islami
→ Session remembers these

Turn 2:
User: "What's the difference between Gold and Platinum?"
→ Applies remembered: banking_type=islami, employment=salaried
→ Compares only Islamic cards, both tiers
→ Session updates tier_preference=both

Turn 3:
User: "Which one is better for travel?"
→ Applies remembered context + new filter: use_cases=travel
→ Recommends from Islamic cards, filtered for travel benefits
```

## Fallback & Error Handling

### No Results Scenario
If Product Retriever returns 0 products:
1. Generate clarification prompt
2. Suggest missing filters:
   - "Would you like Islamic or Conventional products?"
   - "What card tier interests you? Gold or Platinum?"
   - "Are you looking for Credit, Debit, or Loan?"

### Implementation
```python
clarification = """
I didn't find products matching your criteria.

Please let me know:
- Would you like **Islamic (Hasanah)** or **Conventional** products?
- What card tier interests you? **Gold** or **Platinum**?
- Are you looking for a **Credit**, **Debit**, or **Loan** product?
```

## Agent Execution Flow (Detailed)

### Example: "Compare Islamic platinum cards"

**Step 1: Intent Classifier**
```
Input: "Compare Islamic platinum cards"
Detected:
  - intent: "comparison"
  - banking_type: "islami"
  - tier: "platinum"
Output: QueryContext
```

**Step 2: Product Retriever**
```
Input: QueryContext + "Compare Islamic platinum cards"
Filter: {banking_type: "islami", tier: "platinum"}
Output: [
  {product: "Visa Hasanah Platinum", similarity: 0.87},
  {product: "Mastercard Platinum (islami)", similarity: 0.84}
]
```

**Step 3: Feature Comparator** (runs because intent="comparison")
```
Input: Product chunks
Extract:
  - Credit limits: Visa→BDT 500K, Mastercard→BDT 600K
  - Interest-free: Both→Yes
  - Rewards: Visa→Points, Mastercard→Cashback
Output: Comparison table in markdown
```

**Step 4: Response Formatter**
```
Input: Products + comparison table
Output:
  ## Visa Hasanah Platinum
  [Details]
  
  ## Mastercard Platinum (Islamic)
  [Details]
  
  ## Comparison
  [Table]
  
  ### Sources
  [Citations]
```

## API Endpoints

### POST /chat
**Multi-mode chatbot endpoint**
```json
Request:
{
  "query": "Tell me about Visa Gold",
  "session_id": "user_123_session",
  "user_employment": "salaried",
  "mode": "crew"
}

Response:
{
  "query": "Tell me about Visa Gold",
  "answer": "## Visa Gold Credit Card\n[Full response]",
  "agent_chain": ["IntentClassifier", "ProductRetriever", "ResponseFormatter"],
  "products_found": ["Visa Gold Credit Card"],
  "session_id": "user_123_session",
  "timestamp": "2024-01-15T10:30:45Z",
  "success": true
}
```

### GET /conversation/{session_id}
**Retrieve conversation history**
```json
Response:
{
  "session_id": "user_123_session",
  "messages": [
    {"role": "user", "content": "Tell me about Islamic cards"},
    {"role": "assistant", "content": "[Response]", "agent_chain": [...]},
    ...
  ]
}
```

### GET /session/{session_id}/stats
**Session statistics**
```json
Response:
{
  "session_id": "user_123_session",
  "created_at": 1705310000,
  "last_accessed": 1705310500,
  "message_count": 4,
  "preferences": {
    "employment": "salaried",
    "banking_type": "islami",
    "tier": "gold",
    "use_cases": ["travel", "shopping"]
  }
}
```

## Configuration

### agent_orchestration
```yaml
agent_orchestration:
  use_hierarchical_manager: true  # Use Manager orchestrator
  manager_timeout: 120  # Seconds
  enable_reasoning_chain: true  # Show agent chain in response
```

### chunking
```yaml
chunking:
  chunk_size: 350  # Target tokens
  overlap: 0.2  # 20% overlap
  min_chunk_size: 100
```

### multi_turn
```yaml
multi_turn:
  enabled: true
  session_ttl_minutes: 30
  message_window: 10  # Keep last 10 messages
```

## Performance Considerations

### Token Usage Per Query
- Intent Classifier: ~200 tokens (fast regex)
- Product Retriever: ~500 tokens (vector search)
- Other Agents: ~500-1000 tokens each
- **Total**: ~2000-3000 tokens (30-60 seconds on CPU)

### Memory Usage
- Qwen3-1.7B Q4: ~8-10 GB RAM
- Vector embeddings (8 products): ~50 MB
- Session storage (1000 sessions): ~100 MB
- **Total**: Fits comfortably in 16 GB

### Optimization Tips
1. Use `top_k=3` for retriever (instead of 5) for faster response
2. Cache embeddings for products (done automatically)
3. Expire sessions after 15 minutes (from 30) for lower memory
4. Disable verbose logging in production

## Comparison with Direct RAG

| Feature | Direct RAG | CrewAI Multi-Agent |
|---------|-----------|-------------------|
| **Intent Detection** | String matching only | Intelligent extraction |
| **Product Filtering** | Basic keyword match | Metadata-based filtering |
| **Eligibility** | Not available | Full analysis |
| **Comparisons** | Manual (user must ask explicitly) | Automatic comparison tables |
| **Conversation Memory** | Per-turn only | Multi-turn with preferences |
| **Transparency** | Single pipeline | Full agent chain visibility |
| **Response Quality** | Good | Better (specialized agents) |
| **Response Time** | 20-30s | 30-60s (more agents) |

## Future Enhancements

1. **Agent Performance Tracking**: Track which agents are most useful
2. **Dynamic Agent Selection**: Disable underperforming agents
3. **Feedback Loop**: Learn from user satisfaction ratings
4. **Hierarchical Context**: Use Manager's analysis to improve sub-agents
5. **Parallel Agent Execution**: Run independent agents in parallel
6. **Redis Session Storage**: Scale sessions across multiple servers
7. **Agent Analytics**: Dashboard showing agent usage patterns
