import os
import json
import urllib.request
import urllib.error
from python.helpers.tool import Tool, Response


WEBHOOK_URL = os.environ.get("MEETGEEK_WEBHOOK_URL", "http://host.docker.internal:3000")


class MeetgeekManor(Tool):
    """Bridge to the MeetGeek audit system, meeting data, and Fusion Core via REST API."""

    async def execute(self, action="audit_stats", **kwargs):
        try:
            # Audit actions
            if action == "list_pending":
                return await self._list_pending(**kwargs)
            elif action == "get_audit_prompt":
                return await self._get_audit_prompt(**kwargs)
            elif action == "submit_audit":
                return await self._submit_audit(**kwargs)
            elif action == "audit_stats":
                return await self._audit_stats(**kwargs)
            elif action == "meta_learning":
                return await self._meta_learning(**kwargs)
            elif action == "approve_adjustments":
                return await self._approve_adjustments(**kwargs)
            # Meeting actions
            elif action == "meetings":
                return await self._meetings(**kwargs)
            elif action == "meeting_details":
                return await self._meeting_details(**kwargs)
            elif action == "transcript":
                return await self._transcript(**kwargs)
            elif action == "summary":
                return await self._summary(**kwargs)
            # Fusion Core actions
            elif action == "fusion_stats":
                return await self._fusion_stats(**kwargs)
            elif action == "process_queue":
                return await self._process_queue(**kwargs)
            elif action == "daily_digest":
                return await self._daily_digest(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: list_pending, get_audit_prompt, submit_audit, audit_stats, meta_learning, approve_adjustments, meetings, meeting_details, transcript, summary, fusion_stats, process_queue, daily_digest",
                    break_loop=False,
                )
        except urllib.error.URLError as e:
            return Response(
                message=f"Webhook server connection failed at {WEBHOOK_URL}: {e}. Is the webhook server running on port 3000?",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"MeetGeek Manor error: {e}", break_loop=False)

    # ─── Audit actions ───────────────────────────────────────────

    async def _list_pending(self, limit=10, **kwargs):
        result = self._get(f"/api/audits/pending?limit={int(limit)}")
        if not result:
            return Response(message="No pending audits.", break_loop=False)
        text = f"Pending audits ({len(result)}):\n\n"
        for r in result:
            text += f"- **{r.get('signal_id', '?')}** | status={r.get('audit_status', '?')} | reason: {r.get('claude_wake_reason', 'none')}\n"
        return Response(message=text, break_loop=False)

    async def _get_audit_prompt(self, signal_id="", **kwargs):
        if not signal_id:
            return Response(message="Provide signal_id.", break_loop=False)
        result = self._get(f"/api/audits/{signal_id}/prompt")
        prompt = result.get("prompt", "No prompt content.")
        return Response(message=f"Audit prompt for {signal_id}:\n\n{prompt}", break_loop=False)

    async def _submit_audit(self, signal_id="", corrections=None, accuracy_scores=None, **kwargs):
        if not signal_id:
            return Response(message="Provide signal_id.", break_loop=False)
        if not corrections:
            return Response(message="Provide corrections dict.", break_loop=False)
        if not accuracy_scores:
            return Response(message="Provide accuracy_scores dict.", break_loop=False)

        if isinstance(corrections, str):
            corrections = json.loads(corrections)
        if isinstance(accuracy_scores, str):
            accuracy_scores = json.loads(accuracy_scores)

        payload = {
            "signalId": signal_id,
            "corrections": corrections,
            "accuracyScores": accuracy_scores,
        }
        result = self._post("/api/audits/submit", payload)
        return Response(
            message=f"Audit submitted for {signal_id}: {result.get('status', 'unknown')}",
            break_loop=False,
        )

    async def _audit_stats(self, **kwargs):
        result = self._get("/api/audits/stats")
        return Response(
            message=f"Audit system stats:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _meta_learning(self, days=7, **kwargs):
        result = self._get(f"/api/audits/meta-learning?days={int(days)}")
        return Response(
            message=f"Meta-learning report ({days} days):\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _approve_adjustments(self, adjustments=None, **kwargs):
        if not adjustments:
            return Response(message="Provide adjustments array.", break_loop=False)
        if isinstance(adjustments, str):
            adjustments = json.loads(adjustments)
        result = self._post("/api/audits/adjustments", {"adjustments": adjustments})
        return Response(
            message=f"Adjustments result:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    # ─── Meeting actions ─────────────────────────────────────────

    async def _meetings(self, limit=20, cursor="", **kwargs):
        url = f"/api/meetings?limit={int(limit)}"
        if cursor:
            url += f"&cursor={cursor}"
        result = self._get(url)
        if isinstance(result, list):
            meetings = result
        else:
            meetings = result.get("meetings", result.get("data", []))
        if not meetings:
            return Response(message="No meetings found.", break_loop=False)
        text = f"Meetings ({len(meetings)}):\n\n"
        for m in meetings[:int(limit)]:
            title = m.get("title", m.get("name", "Untitled"))
            mid = m.get("id", m.get("meeting_id", "?"))
            date = m.get("date", m.get("created_at", ""))
            text += f"- **{title}** (id={mid}) {date}\n"
        return Response(message=text, break_loop=False)

    async def _meeting_details(self, meeting_id="", **kwargs):
        if not meeting_id:
            return Response(message="Provide meeting_id.", break_loop=False)
        result = self._get(f"/api/meetings/{meeting_id}")
        return Response(
            message=f"Meeting details:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _transcript(self, meeting_id="", **kwargs):
        if not meeting_id:
            return Response(message="Provide meeting_id.", break_loop=False)
        result = self._get(f"/api/meetings/{meeting_id}/transcript")
        return Response(
            message=f"Transcript for {meeting_id}:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _summary(self, meeting_id="", **kwargs):
        if not meeting_id:
            return Response(message="Provide meeting_id.", break_loop=False)
        result = self._get(f"/api/meetings/{meeting_id}/summary")
        return Response(
            message=f"Summary for {meeting_id}:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    # ─── Fusion Core actions ─────────────────────────────────────

    async def _fusion_stats(self, **kwargs):
        result = self._get("/api/fusion/stats")
        return Response(
            message=f"Fusion Core stats:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _process_queue(self, signals=None, limit=10, **kwargs):
        if not signals:
            return Response(message="Provide signals array to process.", break_loop=False)
        if isinstance(signals, str):
            signals = json.loads(signals)
        result = self._post(f"/api/fusion/process?limit={int(limit)}", {"signals": signals})
        return Response(
            message=f"Batch process result:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _daily_digest(self, **kwargs):
        result = self._post("/api/fusion/digest/daily", {})
        return Response(
            message=f"Daily digest:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    # ─── HTTP helpers ────────────────────────────────────────────

    def _get(self, path):
        req = urllib.request.Request(f"{WEBHOOK_URL}{path}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _post(self, path, data):
        body = json.dumps(data).encode()
        req = urllib.request.Request(f"{WEBHOOK_URL}{path}", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
