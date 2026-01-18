# Compute Initial Knowledge Prompt

Given the generated topic concepts and user background (CV or description), identify which concepts the user most likely already has experience with.

## Input
- `{TOPIC_CONCEPTS}`: Array of 10 concepts from topic_graph generation
- `{USER_CV}` or `{USER_DESCRIPTION}`: User's background information

## Output Format
Return a JSON object with the following structure:

```json
{
  "known_concepts": [
    {
      "label": "Concept label from input concepts",
      "confidence": 0.0-1.0,
      "evidence": "Brief explanation of why user likely knows this",
      "highlight_priority": 1-4
    }
  ],
  "learning_path_suggestion": "Brief suggestion for where to start learning"
}
```

## Constraints
- Return exactly 4 concepts that the user most likely knows
- Confidence score reflects how certain we are they have experience
- Evidence should cite specific parts of their background
- Highlight priority (1=most prominent, 4=least) for frontend display ordering

## Frontend Display Notes
These 4 concepts should:
- Be "zoomed in on" / brought to foreground in the visualization
- Have subtly brightened background to highlight them
- Serve as starting points for the user's knowledge graph

## Example

Input concepts: [Self-Attention, Query-Key-Value, Positional Encoding, ...]
User description: "PhD student studying NLP, worked on BERT fine-tuning for 2 years"

Output:
```json
{
  "known_concepts": [
    {
      "label": "Self-Attention",
      "confidence": 0.95,
      "evidence": "Worked with BERT which uses self-attention extensively",
      "highlight_priority": 1
    },
    {
      "label": "Fine-Tuning",
      "confidence": 0.9,
      "evidence": "Explicitly mentioned 2 years of BERT fine-tuning experience",
      "highlight_priority": 2
    }
    // ... 2 more concepts
  ],
  "learning_path_suggestion": "Focus on multi-head attention mechanics and positional encoding variants"
}
```

## Storage
- Store result as JSON in `similarity` storage bucket
- Filename: `related_topic_concepts_{ID}.json`
- Track metadata in SQL: timestamp, storage URL, user_id, session_id, topic_concepts_id
