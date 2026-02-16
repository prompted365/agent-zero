### meetgeek_manor:
Bridge to the MeetGeek audit system, meeting intelligence, and Fusion Core signal pipeline.
Connects to the webhook server REST API running on the host. Use this tool to manage the supervised learning audit loop, query MeetGeek meeting data, and control the Fusion Core processing pipeline.

**Actions:** list_pending, get_audit_prompt, submit_audit, audit_stats, meta_learning, approve_adjustments, meetings, meeting_details, transcript, summary, fusion_stats, process_queue, daily_digest

---

#### Audit Operations

**List pending audits:**
~~~json
{
    "thoughts": ["Checking the audit queue for signals that need review..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "list_pending",
        "limit": "10"
    }
}
~~~

**Get full audit prompt for a signal:**
~~~json
{
    "thoughts": ["Retrieving the complete audit context for this signal..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "get_audit_prompt",
        "signal_id": "sig_abc123"
    }
}
~~~

**Submit audit corrections and accuracy scores:**
~~~json
{
    "thoughts": ["Submitting corrections from the audit review..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "submit_audit",
        "signal_id": "sig_abc123",
        "corrections": "{\"content_vectors\":{\"contains_commitment\":true},\"mission_alignment\":{\"governance_distance\":2},\"actor_assessment\":{},\"routing\":{\"urgency\":\"medium\",\"action\":\"track\",\"reasoning\":\"Routine commitment\"},\"strategic_analysis\":\"Standard follow-up\",\"learning_feedback\":[\"Commitment detection was correct\"]}",
        "accuracy_scores": "{\"overall_accuracy\":0.85,\"content_vectors_accuracy\":0.9,\"mission_alignment_accuracy\":0.8,\"actor_assessment_accuracy\":0.85,\"pattern_prediction_accuracy\":0.8,\"routing_accuracy\":0.9}"
    }
}
~~~

**Get audit system statistics:**
~~~json
{
    "thoughts": ["Checking overall audit system performance metrics..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "audit_stats"
    }
}
~~~

**Generate meta-learning report (systematic error analysis):**
~~~json
{
    "thoughts": ["Analyzing systematic errors over the past 14 days..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "meta_learning",
        "days": "14"
    }
}
~~~

**Apply approved weight adjustments:**
~~~json
{
    "thoughts": ["Applying the approved pattern weight adjustments from meta-learning analysis..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "approve_adjustments",
        "adjustments": "[{\"type\":\"pattern_weight\",\"approved\":true,\"modified_value\":0.6},{\"type\":\"confidence_threshold\",\"approved\":false}]"
    }
}
~~~

---

#### Meeting Operations

**List recent meetings:**
~~~json
{
    "thoughts": ["Fetching recent meetings from MeetGeek..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "meetings",
        "limit": "10"
    }
}
~~~

**Get full meeting details:**
~~~json
{
    "thoughts": ["Retrieving full details for this meeting..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "meeting_details",
        "meeting_id": "mtg_xyz789"
    }
}
~~~

**Get meeting transcript:**
~~~json
{
    "thoughts": ["Pulling the transcript for deeper analysis..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "transcript",
        "meeting_id": "mtg_xyz789"
    }
}
~~~

**Get meeting summary:**
~~~json
{
    "thoughts": ["Fetching the AI-generated meeting summary..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "summary",
        "meeting_id": "mtg_xyz789"
    }
}
~~~

---

#### Fusion Core Operations

**Get signal processing statistics:**
~~~json
{
    "thoughts": ["Checking Fusion Core processing stats..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "fusion_stats"
    }
}
~~~

**Batch process signals through the pipeline:**
~~~json
{
    "thoughts": ["Processing a batch of meeting signals through the Fusion Core..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "process_queue",
        "signals": "[{\"source\":\"meetgeek\",\"sourceId\":\"mtg_001\",\"data\":{}}]",
        "limit": "5"
    }
}
~~~

**Generate daily intelligence digest:**
~~~json
{
    "thoughts": ["Generating today's intelligence digest from processed signals..."],
    "tool_name": "meetgeek_manor",
    "tool_args": {
        "action": "daily_digest"
    }
}
~~~
