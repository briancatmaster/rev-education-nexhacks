# Batch Summary Prompt

Analyze a batch of academic documents and extract the key concepts and knowledge the author demonstrates.

## Input
- `{DOCUMENTS}`: Array of document objects, each containing:
  - `id`: Material ID
  - `title`: Document title
  - `type`: paper_authored | paper_read | educational_course | educational_problems
  - `content`: Compressed text content

## Task
Synthesize the documents to identify:
1. What topics/concepts the author demonstrates understanding of
2. Evidence of their proficiency (quotes, complexity of work)
3. Domain expertise areas

## Output Format
Return a JSON object:

```json
{
  "summary": "2-3 paragraph synthesis of the author's demonstrated knowledge",
  "demonstrated_knowledge": [
    {
      "concept": "Concept Name (1-4 words)",
      "evidence": "Quote or description showing understanding",
      "confidence": 0.0-1.0,
      "source_material_ids": ["mat_id_1", "mat_id_2"]
    }
  ],
  "domain_expertise": ["domain1", "domain2"]
}
```

## Constraints
- Focus on what the author KNOWS, not what they are learning
- Extract 5-15 key concepts per batch depending on document richness
- Confidence reflects depth of demonstrated understanding:
  - 0.9-1.0: Explicitly demonstrated through authored work
  - 0.7-0.89: Clearly implied by complexity of work
  - 0.5-0.69: Referenced or used in context
- Include source_material_ids to trace which documents demonstrate each concept

## Example

Input:
```json
{
  "documents": [
    {
      "id": "mat_001",
      "title": "Neural Network Applications in Medical Imaging",
      "type": "paper_authored",
      "content": "We propose a novel CNN architecture for tumor detection..."
    },
    {
      "id": "mat_002",
      "title": "Deep Learning Notes",
      "type": "paper_read",
      "content": "Notes on backpropagation, gradient descent optimization..."
    }
  ]
}
```

Output:
```json
{
  "summary": "The author demonstrates strong expertise in deep learning applied to medical imaging. Their authored paper shows practical implementation of CNN architectures, while their notes indicate foundational understanding of neural network training. They appear to have working knowledge of optimization techniques and domain-specific applications in healthcare.",
  "demonstrated_knowledge": [
    {
      "concept": "CNN Architecture",
      "evidence": "Designed novel convolutional architecture for tumor detection",
      "confidence": 0.95,
      "source_material_ids": ["mat_001"]
    },
    {
      "concept": "Backpropagation",
      "evidence": "Detailed notes on gradient computation and chain rule",
      "confidence": 0.85,
      "source_material_ids": ["mat_002"]
    },
    {
      "concept": "Medical Imaging",
      "evidence": "Applied deep learning to healthcare domain",
      "confidence": 0.9,
      "source_material_ids": ["mat_001"]
    }
  ],
  "domain_expertise": ["Deep Learning", "Medical Imaging", "Computer Vision"]
}
```
