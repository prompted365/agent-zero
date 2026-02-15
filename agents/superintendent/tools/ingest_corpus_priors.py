"""
Corpus Priors Ingestion Tool — Loads civilization priors into RuVector.

Parses Aesop's Fables, The Prophet, sonar data, and world corpus into
the `civilization_priors` RuVector collection. Uses the same embedding
model (all-MiniLM-L6-v2) as bicameral memory for compatible drift tracking.

Actions:
  - ingest: Parse all corpus files and bulk-insert into RuVector
  - status: Check collection stats for civilization_priors
"""

import os
import re
import csv
import json
import urllib.request
import urllib.error
from python.helpers.tool import Tool, Response


RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
PRIORS_COLLECTION = os.environ.get("RUVECTOR_PRIORS_COLLECTION", "civilization_priors")
EMBEDDING_DIM = 384
BATCH_SIZE = 32

CORPUS_DIR = os.environ.get(
    "CORPUS_PRIORS_DIR",
    "/workspace/operationTorque/data/corpus-priors",
)


class IngestCorpusPriors(Tool):
    """Ingest civilization priors (Aesop, Prophet, world corpus) into RuVector."""

    async def execute(self, action="ingest", **kwargs):
        try:
            if action == "ingest":
                return await self._ingest(**kwargs)
            elif action == "status":
                return await self._status(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Use: ingest, status",
                    break_loop=False,
                )
        except urllib.error.URLError as e:
            return Response(
                message=f"RuVector connection failed at {RUVECTOR_URL}: {e}. Is the web-intelligence stack running?",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"Ingestion error: {e}", break_loop=False)

    async def _ingest(self, **kwargs):
        """Parse all corpus files and bulk-insert into RuVector."""
        from python.helpers.memory import Memory

        # Get embedding function from FAISS memory (same model)
        db = await Memory.get(self.agent)
        embed_fn = db.db.embedding_function

        documents = []

        # 1. Parse Aesop's Fables
        aesop_path = os.path.join(CORPUS_DIR, "aesops300fablesscraped.txt")
        if os.path.exists(aesop_path):
            fables = self._parse_aesop(aesop_path)
            documents.extend(fables)

        # 2. Parse The Prophet
        prophet_path = os.path.join(CORPUS_DIR, "theprophet_scrape.txt")
        if os.path.exists(prophet_path):
            chapters = self._parse_prophet(prophet_path)
            documents.extend(chapters)

        # 3. Parse sonar data
        sonar_path = os.path.join(CORPUS_DIR, "sonar_data.csv")
        if os.path.exists(sonar_path):
            sonar = self._parse_sonar(sonar_path)
            documents.extend(sonar)

        # 4. Parse world corpus
        world_path = os.path.join(CORPUS_DIR, "world_corpus.json")
        if os.path.exists(world_path):
            world = self._parse_world_corpus(world_path)
            documents.extend(world)

        if not documents:
            return Response(
                message=f"No corpus files found in {CORPUS_DIR}",
                break_loop=False,
            )

        # Ensure collection exists
        self._ensure_collection()

        # Generate embeddings and bulk insert in batches
        inserted = 0
        errors = []
        for i in range(0, len(documents), BATCH_SIZE):
            batch = documents[i : i + BATCH_SIZE]
            texts = [doc["text"] for doc in batch]

            try:
                embeddings = embed_fn.embed_documents(texts)
            except Exception as e:
                errors.append(f"Embedding batch {i // BATCH_SIZE}: {e}")
                continue

            payload_docs = []
            for doc, emb in zip(batch, embeddings):
                payload_docs.append(
                    {
                        "id": doc["id"],
                        "text": doc["text"][:2000],
                        "embedding": list(emb),
                        "metadata": doc.get("metadata", {}),
                    }
                )

            try:
                body = json.dumps(
                    {
                        "documents": payload_docs,
                        "collection": PRIORS_COLLECTION,
                    }
                ).encode()
                req = urllib.request.Request(
                    f"{RUVECTOR_URL}/documents/bulk",
                    data=body,
                    method="POST",
                )
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                inserted += result.get("inserted", len(payload_docs))
            except Exception as e:
                errors.append(f"Bulk insert batch {i // BATCH_SIZE}: {e}")

        # Count by source
        source_counts = {}
        for doc in documents:
            src = doc.get("metadata", {}).get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        report = (
            f"Corpus ingestion complete.\n"
            f"Total documents parsed: {len(documents)}\n"
            f"Successfully inserted: {inserted}\n"
            f"Breakdown: {json.dumps(source_counts)}\n"
        )
        if errors:
            report += f"Errors ({len(errors)}): {'; '.join(errors[:5])}\n"

        return Response(message=report, break_loop=False)

    async def _status(self, **kwargs):
        """Check collection stats for civilization_priors."""
        try:
            req = urllib.request.Request(
                f"{RUVECTOR_URL}/collections/{PRIORS_COLLECTION}/stats",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                stats = json.loads(resp.read().decode())
            return Response(
                message=f"Collection '{PRIORS_COLLECTION}' stats: {json.dumps(stats, indent=2)}",
                break_loop=False,
            )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return Response(
                    message=f"Collection '{PRIORS_COLLECTION}' does not exist. Run ingest first.",
                    break_loop=False,
                )
            raise

    def _ensure_collection(self):
        """Create the civilization_priors collection if it doesn't exist."""
        try:
            req = urllib.request.Request(
                f"{RUVECTOR_URL}/collections/{PRIORS_COLLECTION}/stats",
                method="GET",
            )
            urllib.request.urlopen(req, timeout=5)
            return  # Already exists
        except urllib.error.HTTPError:
            pass  # Doesn't exist, create it

        payload = {
            "name": PRIORS_COLLECTION,
            "dimension": EMBEDDING_DIM,
            "metric": "cosine",
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{RUVECTOR_URL}/collections",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)

    # ── Parsers ──────────────────────────────────────────────────────────

    def _parse_aesop(self, path: str) -> list[dict]:
        """Parse Aesop's Fables using page-break markers."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        page_break_header = "~~~~~~page_break_HEADER~~~"
        page_break_footer = "~~~~~~page_break_FOOTER~~~"

        pages = content.split(page_break_header)
        fables = []
        current_title = None
        current_text = []

        # Archetype mapping (same as TypeScript parser)
        archetype_map = {
            "Lion": "king", "Wolf": "predator", "Fox": "trickster",
            "Ass": "fool", "Mouse": "underdog", "Eagle": "power",
            "Crow": "vanity", "Dog": "loyalty", "Shepherd": "guardian",
            "Farmer": "worker", "Hare": "coward", "Tortoise": "persistent",
            "Ant": "industrious", "Grasshopper": "carefree",
        }

        for page in pages:
            clean_page = page.replace(page_break_footer, "").strip()
            if not clean_page:
                continue

            lines = [l.strip() for l in clean_page.split("\n") if l.strip()]

            for line in lines:
                # Skip header material
                if any(
                    skip in line
                    for skip in [
                        "PROJECT GUTENBERG", "CONTENTS", "PREFACE",
                        "George Fyler Townsend",
                    ]
                ):
                    continue

                # Check if this looks like a fable title
                if self._is_fable_title(line):
                    # Save previous fable
                    if current_title:
                        fables.append(
                            self._build_fable(current_title, current_text, archetype_map)
                        )
                    current_title = line
                    current_text = []
                elif current_title:
                    current_text.append(line)

        # Save last fable
        if current_title:
            fables.append(self._build_fable(current_title, current_text, archetype_map))

        return fables

    def _is_fable_title(self, line: str) -> bool:
        """Check if a line is a fable title (mirrors TypeScript logic)."""
        if len(line) > 80 or len(line) < 5:
            return False
        if not re.match(r"^[A-Z]", line):
            return False
        if "http" in line or "www" in line:
            return False
        if re.match(r"^\d+$", line):
            return False
        if line.startswith("The ") and (" and " in line or ", " in line):
            return True
        return False

    def _build_fable(self, title: str, text_lines: list, archetype_map: dict) -> dict:
        """Build a fable document with moral extraction."""
        text = " ".join(text_lines).strip()

        # Extract moral
        moral = None
        for indicator in ["moral:", "lesson:", "application:"]:
            idx = text.lower().find(indicator)
            if idx != -1:
                moral = text[idx:].strip()
                break

        # Infer archetypes from title
        archetypes = []
        for key, archetype in archetype_map.items():
            if key in title:
                archetypes.append(archetype)

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        full_text = f"{title}: {text}"
        if moral:
            full_text += f" Moral: {moral}"

        return {
            "id": f"aesop-{slug}",
            "text": full_text[:2000],
            "metadata": {
                "source": "aesop",
                "type": "fable",
                "title": title,
                "archetypes": archetypes,
            },
        }

    def _parse_prophet(self, path: str) -> list[dict]:
        """Parse The Prophet by chapter headers."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        page_break_header = "~~~~~~page_break_HEADER~~~"
        page_break_footer = "~~~~~~page_break_FOOTER~~~"

        themes = [
            "THE COMING OF THE SHIP",
            "ON LOVE", "ON MARRIAGE", "ON CHILDREN", "ON GIVING",
            "ON EATING AND DRINKING", "ON WORK", "ON JOY AND SORROW",
            "ON HOUSES", "ON CLOTHES", "ON BUYING AND SELLING",
            "ON CRIME AND PUNISHMENT", "ON LAWS", "ON FREEDOM",
            "ON REASON AND PASSION", "ON PAIN", "ON SELF-KNOWLEDGE",
            "ON TEACHING", "ON FRIENDSHIP", "ON TALKING", "ON TIME",
            "ON GOOD AND EVIL", "ON PRAYER", "ON PLEASURE", "ON BEAUTY",
            "ON RELIGION", "ON DEATH", "THE FAREWELL",
        ]

        pages = content.split(page_break_header)
        chapters = []
        current_theme = None
        current_text = []

        for page in pages:
            clean_page = page.replace(page_break_footer, "").strip()
            if not clean_page:
                continue

            lines = [l.strip() for l in clean_page.split("\n") if l.strip()]

            for line in lines:
                if "http" in line or "www" in line or "KAHLIL GIBRAN" in line:
                    continue
                if re.match(r"^\d+$", line):
                    continue

                matched = None
                for t in themes:
                    if t in line.upper():
                        matched = t
                        break

                if matched:
                    if current_theme:
                        chapters.append(
                            self._build_chapter(current_theme, current_text)
                        )
                    current_theme = matched
                    current_text = []
                elif current_theme and line:
                    current_text.append(line)

        if current_theme:
            chapters.append(self._build_chapter(current_theme, current_text))

        return chapters

    def _build_chapter(self, theme: str, text_lines: list) -> dict:
        """Build a Prophet chapter document."""
        text = " ".join(text_lines).strip()
        theme_clean = theme[3:].lower() if theme.startswith("ON ") else theme.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")[:60]

        return {
            "id": f"prophet-{slug}",
            "text": f"{theme}: {text}"[:2000],
            "metadata": {
                "source": "prophet",
                "type": "chapter",
                "title": theme,
                "theme": theme_clean,
            },
        }

    def _parse_sonar(self, path: str) -> list[dict]:
        """Parse sonar_data.csv into documents."""
        documents = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                # Build text from available fields
                parts = []
                for key in ["text", "content", "description", "title", "name"]:
                    if key in row and row[key]:
                        parts.append(row[key])

                if not parts:
                    # Fallback: concatenate all values
                    parts = [v for v in row.values() if v]

                text = " | ".join(parts)
                if not text.strip():
                    continue

                documents.append(
                    {
                        "id": f"sonar-{i:04d}",
                        "text": text[:2000],
                        "metadata": {
                            "source": "sonar",
                            "type": "sample",
                            "row_index": i,
                        },
                    }
                )
        return documents

    def _parse_world_corpus(self, path: str) -> list[dict]:
        """Parse world_corpus.json (477 pre-structured records)."""
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)

        documents = []
        for rec in records:
            rec_id = rec.get("id", "")
            title = rec.get("title", "Unknown")
            year = rec.get("year", "")
            era = rec.get("era", "")
            excerpt = rec.get("excerpt", "")
            keywords = rec.get("top_keywords", [])

            year_str = str(int(year)) if isinstance(year, (int, float)) and year else str(year)
            text = f"{title} ({year_str}, {era}): {excerpt}"

            documents.append(
                {
                    "id": f"world-{rec_id}",
                    "text": text[:2000],
                    "metadata": {
                        "source": "world_corpus",
                        "type": "historical_document",
                        "title": title,
                        "year": int(year) if isinstance(year, (int, float)) and year else None,
                        "era": era,
                        "keywords": keywords[:10],
                    },
                }
            )
        return documents
