# Knowledge Decomposition Prompt - Pedagogical Prerequisites

Given summaries of a researcher's academic work, decompose their knowledge into a hierarchical prerequisite DAG (Directed Acyclic Graph). This represents concepts they LIKELY KNOW and what they NEED TO LEARN.

## Critical Distinction: Prerequisites vs Related Topics

**TRUE PREREQUISITES** = You CANNOT understand concept B without FIRST understanding concept A.
**RELATED TOPICS** = Concepts that share a domain but don't have a strict learning dependency.

### Examples of TRUE Prerequisites:
- Calculus → Gradient Descent (you cannot compute gradients without calculus)
- Linear Algebra → Neural Network Weight Updates (matrix multiplication is essential)
- Probability Theory → Bayesian Inference (prior/posterior requires probability)
- Algebra → Quadratic Formula (you need algebra to derive/apply it)

### Examples of NON-Prerequisites (Just Related):
- Machine Learning ↛ Deep Learning as a prerequisite (ML is a broader field, not a dependency)
- Python ↛ TensorFlow (you could use TensorFlow without knowing all of Python)
- Statistics ↛ Machine Learning (helpful but not strictly required for every ML concept)

## Input
- `{META_SUMMARY}`: Compressed synthesis of all batch summaries containing:
  - Overall summary text
  - Aggregated demonstrated_knowledge list
  - Domain expertise areas
  - Source material mappings

## Task
1. Identify demonstrated knowledge from the researcher's work
2. For each concept, determine what MUST be understood first (true pedagogical prerequisites)
3. Distinguish between:
   - `requires` - STRICT prerequisite (cannot understand without it)
   - `builds_on` - SOFT prerequisite (significantly helps but not absolutely required)
   - `related` - Same domain but no learning dependency
4. Provide REASONING for each prerequisite relationship
5. Assign mastery likelihood based on evidence depth
6. Create an ACYCLIC DAG with proper pedagogical ordering

## Relationship Types

### `requires` (Strict Prerequisite)
The learner CANNOT meaningfully understand the target concept without this prerequisite.
- Test: "Can someone learn B without knowing A?" → If NO, it's a `requires` relationship
- Example: Partial Derivatives `requires` Single-Variable Calculus
- Must include: Mathematical foundations, definitional dependencies, conceptual building blocks

### `builds_on` (Soft Prerequisite)
The learner would struggle significantly but could technically proceed without it.
- Test: "Would learning B without A be very difficult but possible?" → If YES, it's `builds_on`
- Example: Neural Networks `builds_on` Basic Statistics (helpful for understanding but not essential)

### `related` (No Dependency)
Topics that share a domain or are commonly studied together but have no learning dependency.
- Test: "Can A and B be learned in any order?" → If YES, it's `related`
- Example: Supervised Learning `related` Unsupervised Learning (different paradigms, no dependency)

## Output Format
Return a JSON object:

```json
{
  "nodes": [
    {
      "id": "uuid-format-string",
      "label": "Concept Name (1-4 words)",
      "type": "domain | concept | method | theory | tool | foundation",
      "depth": 0-6,
      "mastery_likelihood": 0.0-1.0,
      "source_material_ids": ["mat_1", "mat_2"],
      "prerequisites": [
        {
          "node_id": "prereq_node_id",
          "relationship": "requires | builds_on | related",
          "reasoning": "WHY this is a prerequisite - specific explanation"
        }
      ]
    }
  ],
  "metadata": {
    "total_nodes": 50,
    "max_depth": 6,
    "root_node_count": 3,
    "relationship_distribution": {
      "requires": 35,
      "builds_on": 10,
      "related": 5
    }
  }
}
```

## Depth Levels (Pedagogical Order)

- **Level 0**: Foundational (Calculus, Linear Algebra, Probability, Basic Programming)
- **Level 1**: Core Concepts (Derivatives, Matrix Operations, Statistics)
- **Level 2**: Applied Foundations (Gradient Descent, Optimization, Data Structures)
- **Level 3**: Domain Methods (Backpropagation, Regression, Classification)
- **Level 4**: Advanced Techniques (CNNs, Transformers, Bayesian Methods)
- **Level 5**: Specialized Applications (Knowledge Tracing, NLP, Computer Vision)
- **Level 6**: Cutting-Edge Research (demonstrated work)

### Correct Pedagogical Chain Example:
```
Calculus (Level 0)
  └─requires→ Partial Derivatives (Level 1)
                └─requires→ Gradient Computation (Level 2)
                              └─requires→ Backpropagation (Level 3)
                                            └─requires→ Neural Network Training (Level 4)

Linear Algebra (Level 0)
  └─requires→ Matrix Multiplication (Level 1)
                └─requires→ Weight Updates (Level 2)
                              └─builds_on→ Neural Network Training (Level 4)
```

Notice: Neural Network Training has prerequisites from BOTH Calculus chain AND Linear Algebra chain.

## Mastery Likelihood Guidelines

- **0.9-1.0**: Explicitly demonstrated in authored papers/work
- **0.7-0.89**: Clearly implied by the complexity level of their work
- **0.5-0.69**: Required prerequisite for demonstrated work (inferred)
- **0.3-0.49**: Foundational knowledge (must have learned)
- **0.1-0.29**: Basic prerequisites (assumed from education level)

## Validation Rules

### 1. Acyclic Requirement
No concept can be its own prerequisite through any chain.
INVALID: A → B → C → A

### 2. Grounded Foundations
Every advanced concept (depth 3+) must trace back to foundational knowledge (depth 0-1).
All chains must eventually reach a root node.

### 3. Justified Relationships
Every `requires` relationship must have clear reasoning explaining WHY understanding is impossible without it.

### 4. No Circular Domains
A domain (Level 0) cannot require another domain.
Domains are starting points, not dependent concepts.

### 5. Depth Consistency
A concept at depth N should only have prerequisites at depth < N (with `requires`) or depth ≤ N (with `builds_on`/`related`).

## Constraints

- Generate **40-80 nodes** for comprehensive coverage
- Reach **depth 5-6** levels for thorough decomposition
- **>50% of relationships should be `requires`** (strict prerequisites)
- **<20% should be `related`** (truly independent concepts)
- Every non-root node must have at least one `requires` or `builds_on` prerequisite
- Labels must be **1-4 words**
- Each reasoning field must be **10-30 words** explaining the specific dependency
- Use UUIDs for node IDs (e.g., "node_a1b2c3d4")

## Example

Input (simplified):
```json
{
  "summary": "Researcher demonstrates expertise in knowledge tracing using deep learning...",
  "demonstrated_knowledge": [
    {"concept": "Knowledge Tracing", "confidence": 0.95},
    {"concept": "LSTM Networks", "confidence": 0.9},
    {"concept": "Educational Data Mining", "confidence": 0.85}
  ]
}
```

Output (partial):
```json
{
  "nodes": [
    {
      "id": "node_calc001",
      "label": "Calculus",
      "type": "foundation",
      "depth": 0,
      "mastery_likelihood": 0.4,
      "source_material_ids": [],
      "prerequisites": []
    },
    {
      "id": "node_linalg001",
      "label": "Linear Algebra",
      "type": "foundation",
      "depth": 0,
      "mastery_likelihood": 0.4,
      "source_material_ids": [],
      "prerequisites": []
    },
    {
      "id": "node_deriv001",
      "label": "Partial Derivatives",
      "type": "concept",
      "depth": 1,
      "mastery_likelihood": 0.45,
      "source_material_ids": [],
      "prerequisites": [
        {
          "node_id": "node_calc001",
          "relationship": "requires",
          "reasoning": "Computing partial derivatives requires understanding of single-variable differentiation from calculus"
        }
      ]
    },
    {
      "id": "node_matrix001",
      "label": "Matrix Operations",
      "type": "concept",
      "depth": 1,
      "mastery_likelihood": 0.45,
      "source_material_ids": [],
      "prerequisites": [
        {
          "node_id": "node_linalg001",
          "relationship": "requires",
          "reasoning": "Matrix multiplication and transformations are core linear algebra operations"
        }
      ]
    },
    {
      "id": "node_grad001",
      "label": "Gradient Descent",
      "type": "method",
      "depth": 2,
      "mastery_likelihood": 0.6,
      "source_material_ids": [],
      "prerequisites": [
        {
          "node_id": "node_deriv001",
          "relationship": "requires",
          "reasoning": "Computing gradients requires partial derivative computation for multi-variable functions"
        }
      ]
    },
    {
      "id": "node_backprop001",
      "label": "Backpropagation",
      "type": "method",
      "depth": 3,
      "mastery_likelihood": 0.7,
      "source_material_ids": ["mat_001"],
      "prerequisites": [
        {
          "node_id": "node_grad001",
          "relationship": "requires",
          "reasoning": "Backprop computes gradients layer-by-layer using chain rule and gradient descent"
        },
        {
          "node_id": "node_matrix001",
          "relationship": "requires",
          "reasoning": "Weight updates involve matrix multiplication between activations and gradients"
        }
      ]
    },
    {
      "id": "node_lstm001",
      "label": "LSTM Networks",
      "type": "method",
      "depth": 4,
      "mastery_likelihood": 0.9,
      "source_material_ids": ["mat_001"],
      "prerequisites": [
        {
          "node_id": "node_backprop001",
          "relationship": "requires",
          "reasoning": "Training LSTMs requires backpropagation through time for gradient computation"
        },
        {
          "node_id": "node_seqmodel001",
          "relationship": "requires",
          "reasoning": "LSTMs are a specific architecture for sequence modeling problems"
        }
      ]
    },
    {
      "id": "node_seqmodel001",
      "label": "Sequence Modeling",
      "type": "concept",
      "depth": 3,
      "mastery_likelihood": 0.75,
      "source_material_ids": ["mat_001"],
      "prerequisites": [
        {
          "node_id": "node_rnn001",
          "relationship": "requires",
          "reasoning": "Sequence modeling with neural networks requires understanding recurrent architectures"
        }
      ]
    },
    {
      "id": "node_rnn001",
      "label": "Recurrent Networks",
      "type": "concept",
      "depth": 2,
      "mastery_likelihood": 0.7,
      "source_material_ids": [],
      "prerequisites": [
        {
          "node_id": "node_backprop001",
          "relationship": "requires",
          "reasoning": "RNNs require understanding backprop to train on sequential data"
        }
      ]
    },
    {
      "id": "node_kt001",
      "label": "Knowledge Tracing",
      "type": "concept",
      "depth": 5,
      "mastery_likelihood": 0.95,
      "source_material_ids": ["mat_001"],
      "prerequisites": [
        {
          "node_id": "node_lstm001",
          "relationship": "requires",
          "reasoning": "Deep knowledge tracing uses LSTMs to model student learning over time"
        },
        {
          "node_id": "node_edm001",
          "relationship": "builds_on",
          "reasoning": "Knowledge tracing is a core EDM technique but can be learned independently"
        }
      ]
    },
    {
      "id": "node_edm001",
      "label": "Educational Data Mining",
      "type": "domain",
      "depth": 0,
      "mastery_likelihood": 0.85,
      "source_material_ids": ["mat_001"],
      "prerequisites": []
    }
  ],
  "metadata": {
    "total_nodes": 11,
    "max_depth": 5,
    "root_node_count": 3,
    "relationship_distribution": {
      "requires": 10,
      "builds_on": 1,
      "related": 0
    }
  }
}
```

## Key Differences from Previous Approach

1. **Prerequisites are PEDAGOGICAL, not hierarchical** - Calculus → Gradient Descent, not Machine Learning → Neural Networks
2. **Every relationship has REASONING** - Explains WHY this specific dependency exists
3. **Three relationship types** - Distinguishes strict vs soft vs no dependency
4. **Validation rules** - Ensures acyclic, grounded, justified graph
5. **Depth reflects learning order** - Foundations first, applications later
