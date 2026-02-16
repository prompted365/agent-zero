Extract entities and their relationships from the following memory fragments.

**Memory text:**
{{memories_text}}

Return a JSON array of entities. Each entity should have:
- `name`: The entity name (person, tool, concept, system, organization)
- `type`: One of PERSON, TOOL, SYSTEM, CONCEPT, ORGANIZATION, LOCATION, EVENT
- `relationships`: Array of relationships to other entities, each with:
  - `target`: Name of the related entity
  - `type`: Relationship type (e.g., CREATED_BY, USES, PART_OF, MANAGES, RELATES_TO, DEPENDS_ON)

Focus on:
- Named people, agents, and roles
- Tools, systems, and infrastructure components
- Key concepts and patterns
- Organizational entities

Only extract entities that are clearly mentioned. Do not infer entities that aren't stated.
Cap at 10 entities maximum.

Return ONLY valid JSON, no other text:
```json
{
  "entities": [
    {"name": "Breyden", "type": "PERSON", "relationships": [{"target": "Mogul", "type": "CREATED_BY"}]},
    {"name": "Mogul", "type": "SYSTEM", "relationships": [{"target": "RuVector", "type": "USES"}]}
  ]
}
```
