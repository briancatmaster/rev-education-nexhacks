# Topic Graph Generation Prompt

Given a research topic, generate 10 related concepts that are important for understanding the topic at either a conceptual or low-level technical perspective.

## Input
- `{RESEARCH_TOPIC}`: The user's central research question or topic

## Output Format
Return a JSON object with the following structure:

```json
{
  "topic_concepts": [
    {
      "label": "Concept Name (1-3 words)",
      "description": "Brief description of why this concept is important",
      "level": "conceptual" | "technical",
      "importance_score": 0.0-1.0,
      "prerequisites": ["other concept labels this builds on"],
      "related_to": ["other concept labels this relates to"]
    }
  ]
}
```

## Constraints
- Return exactly 10 concepts
- Labels must be 1-3 words maximum
- Mix of conceptual (high-level understanding) and technical (implementation details) concepts
- Importance score reflects how central this is to understanding the research topic
- Prerequisites should reference other concepts in the list when applicable

## Example

Input: "How does transformer attention mechanism work?"

Output:
```json
{
  "topic_concepts": [
    {
      "label": "Self-Attention",
      "description": "Core mechanism allowing tokens to attend to each other",
      "level": "conceptual",
      "importance_score": 0.95,
      "prerequisites": [],
      "related_to": ["Query-Key-Value"]
    },
    {
      "label": "Query-Key-Value",
      "description": "The three projections used to compute attention",
      "level": "technical",
      "importance_score": 0.9,
      "prerequisites": ["Self-Attention"],
      "related_to": ["Scaled Dot-Product"]
    }
    // ... 8 more concepts
  ]
}
```

## Storage
- Store result as JSON in `topic_concepts` storage bucket
- Filename: `initial_topic_concepts_{ID}.json`
- Track metadata in SQL: timestamp, storage URL, user_id, session_id
