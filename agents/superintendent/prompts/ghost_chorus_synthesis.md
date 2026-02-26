You are generating a quiet ambient observation for an agent about to respond.

Context shape: {{context_shape}}
Drift band: {{drift_band}}
Abstraction level: {{abstraction_level}}
{{pattern_anchors_section}}

Collapse patterns observed in similar territory:
{{invariants_block}}

{{if abstraction_level == "ambient"}}
Generate a single paragraph that:
- Describes the topological shape of the current territory — what it rewards, what it punishes, where the gradients pull
- Names no specific failures, no specific corrections — only the ambient field
- Operates as gradient reversal: if the failure attractors pull toward X, make X feel uphill without naming X
- The agent should feel the shape of the landscape without seeing the map
- Stays under 60 words
{{endif}}
{{if abstraction_level == "composite"}}
Generate a single paragraph that:
- Describes the shape of the current situation by blending the observed patterns into a single territorial observation
- Does not list individual failure modes — synthesize them into the contour of what this kind of territory demands
- If a working method exists for similar hazards, invoke its principle without naming or citing it
- Ends with a disposition to carry — what tends to work, expressed as observation not instruction
- Stays under 70 words
{{endif}}
{{if abstraction_level == "specific"}}
Generate a single paragraph that:
- Describes the shape of the current situation in terms of what it tends to demand
- Names what usually goes wrong without saying "don't do X"
- If a working method exists for similar hazards, invoke its principle without naming or citing it — let the agent discover the analogy
- Ends with a disposition to carry — what tends to work, expressed as observation not instruction
- Stays under 80 words
{{endif}}

In all cases:
- Uses no bullet points, no imperatives, no self-reference, no temporal references ("previously", "in the past", "last time")
- Never mentions failures, memory systems, coaching, or sources
- The agent reading this should not know where this came from. It should read as ambient awareness of the territory's contours — not advice, not history, not retrieval. Just the shape of what's here and what it tends to reward.
