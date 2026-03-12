"""Core GraphMem wrapper around graphiti-core."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.cross_encoder import CrossEncoderClient
from graphiti_core.nodes import EpisodeType

from graphmem.config import DBBackend, Settings, load_settings
from graphmem.providers.embeddings import create_embedder
from graphmem.providers.llm import create_llm_client


class NoOpCrossEncoder(CrossEncoderClient):
    """Pass-through cross encoder that returns passages with equal scores.

    Used when the user doesn't have an OpenAI key (Graphiti defaults to OpenAI reranker).
    """

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(p, 1.0 / (i + 1)) for i, p in enumerate(passages)]


class GraphMem:
    """High-level wrapper around Graphiti for CLI usage."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self._graphiti: Graphiti | None = None

    def _default_group_id(self) -> str:
        """Get the default group_id for the current backend."""
        if self.settings.db_backend == DBBackend.kuzu:
            return ""
        return "neo4j"

    async def _get_graphiti(self) -> Graphiti:
        if self._graphiti is not None:
            return self._graphiti

        driver = self._create_driver()
        embedder = self._create_embedder()
        llm = self._create_llm()

        self._graphiti = Graphiti(
            graph_driver=driver,
            llm_client=llm,
            embedder=embedder,
            cross_encoder=NoOpCrossEncoder(),
            store_raw_episode_content=True,
        )

        await self._graphiti.build_indices_and_constraints()

        # Kuzu's build_indices_and_constraints is a no-op, so create FTS indexes manually
        if self.settings.db_backend == DBBackend.kuzu:
            import logging

            from graphiti_core.graph_queries import get_fulltext_indices
            from graphiti_core.driver.driver import GraphProvider

            kuzu_logger = logging.getLogger("graphiti_core.driver.kuzu_driver")
            prev_level = kuzu_logger.level
            kuzu_logger.setLevel(logging.CRITICAL)
            for query in get_fulltext_indices(GraphProvider.KUZU):
                try:
                    await driver.execute_query(query)
                except Exception:
                    pass  # Index may already exist
            kuzu_logger.setLevel(prev_level)

        return self._graphiti

    def _create_driver(self):
        s = self.settings
        if s.db_backend == DBBackend.kuzu:
            from graphiti_core.driver.kuzu_driver import KuzuDriver

            db_path = s.resolve_db_path()
            return KuzuDriver(db=db_path)
        elif s.db_backend == DBBackend.neo4j:
            # Neo4j uses the legacy uri/user/password constructor path
            # graphiti handles this internally
            return None  # Will use uri/user/password params
        else:
            raise ValueError(f"Unknown DB backend: {s.db_backend}")

    def _create_embedder(self):
        s = self.settings
        kwargs: dict[str, Any] = {}
        if s.embedder.value == "openai":
            kwargs["api_key"] = s.get_openai_key()
        elif s.embedder.value == "bedrock":
            kwargs["region"] = s.aws_region
            kwargs["model"] = s.bedrock_embed_model
        elif s.embedder.value == "local":
            kwargs["model"] = s.local_embed_model
        return create_embedder(s.embedder.value, **kwargs)

    def _create_llm(self):
        s = self.settings
        kwargs: dict[str, Any] = {}
        if s.llm.value == "openai":
            kwargs["api_key"] = s.get_openai_key()
        elif s.llm.value == "anthropic":
            kwargs["api_key"] = s.get_anthropic_key()
        elif s.llm.value == "bedrock":
            kwargs["region"] = s.aws_region
            kwargs["model"] = s.bedrock_llm_model
        elif s.llm.value == "ollama":
            kwargs["base_url"] = s.ollama_base_url
            kwargs["model"] = s.ollama_model
        return create_llm_client(s.llm.value, **kwargs)

    async def add(
        self,
        content: str,
        source: str = "cli",
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a memory episode. Graphiti extracts entities/facts automatically."""
        g = await self._get_graphiti()
        now = datetime.now(timezone.utc)

        result = await g.add_episode(
            name=f"memory_{now.strftime('%Y%m%d_%H%M%S')}",
            episode_body=content,
            source_description=source,
            reference_time=now,
            source=EpisodeType.message,
            group_id=group_id,
        )

        return {
            "episode_id": result.episode.uuid,
            "entities": [
                {"id": n.uuid, "name": n.name, "summary": n.summary}
                for n in result.nodes
            ],
            "facts": [
                {"id": e.uuid, "fact": e.fact, "source": e.name}
                for e in result.edges
            ],
        }

    async def query(
        self,
        query_text: str,
        num_results: int = 10,
        group_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search memories using hybrid search (semantic + keyword + graph)."""
        g = await self._get_graphiti()

        gids = group_ids or [self._default_group_id()]
        edges = await g.search(
            query=query_text,
            num_results=num_results,
            group_ids=gids,
        )

        return [
            {
                "id": edge.uuid,
                "fact": edge.fact,
                "name": edge.name,
                "created_at": str(edge.created_at) if edge.created_at else None,
                "valid_at": str(edge.valid_at) if edge.valid_at else None,
                "invalid_at": str(edge.invalid_at) if edge.invalid_at else None,
            }
            for edge in edges
        ]

    async def context(
        self,
        topic: str,
        depth: int = 2,
        group_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get expanded context around a topic using graph traversal."""
        from graphiti_core.search.search_config_recipes import (
            COMBINED_HYBRID_SEARCH_RRF,
        )

        g = await self._get_graphiti()

        gids = group_ids or [self._default_group_id()]
        results = await g.search_(
            query=topic,
            config=COMBINED_HYBRID_SEARCH_RRF,
            group_ids=gids,
        )

        return {
            "entities": [
                {
                    "id": n.uuid,
                    "name": n.name,
                    "summary": n.summary,
                }
                for n in results.nodes
            ],
            "facts": [
                {
                    "id": e.uuid,
                    "fact": e.fact,
                    "name": e.name,
                    "valid_at": str(e.valid_at) if e.valid_at else None,
                    "invalid_at": str(e.invalid_at) if e.invalid_at else None,
                }
                for e in results.edges
            ],
            "communities": [
                {
                    "id": c.uuid,
                    "name": c.name,
                    "summary": c.summary,
                }
                for c in results.communities
            ],
            "episodes": [
                {
                    "id": ep.uuid,
                    "name": ep.name,
                    "content": ep.content,
                    "created_at": str(ep.created_at) if ep.created_at else None,
                }
                for ep in results.episodes
            ],
        }

    async def remove(self, entity_id: str) -> bool:
        """Remove an entity node by ID."""
        g = await self._get_graphiti()
        try:
            await g.driver.execute_query(
                "MATCH (n:Entity {uuid: $uuid}) DETACH DELETE n",
                uuid=entity_id,
            )
            return True
        except Exception:
            return False

    async def remove_edge(self, edge_id: str) -> bool:
        """Remove a fact/edge by ID."""
        g = await self._get_graphiti()
        try:
            await g.driver.execute_query(
                "MATCH ()-[r {uuid: $uuid}]->() DELETE r",
                uuid=edge_id,
            )
            return True
        except Exception:
            return False

    async def list_episodes(
        self,
        limit: int = 20,
        group_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent episodes."""
        g = await self._get_graphiti()
        gid = group_id if group_id is not None else self._default_group_id()
        episodes = await g.driver.episode_node_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )
        # Sort by created_at descending, take limit
        episodes.sort(key=lambda e: e.created_at or "", reverse=True)
        episodes = episodes[:limit]

        return [
            {
                "id": ep.uuid,
                "name": ep.name,
                "content": (ep.content or "")[:200],
                "created_at": str(ep.created_at) if ep.created_at else None,
            }
            for ep in episodes
        ]

    async def list_entities(
        self,
        limit: int = 20,
        group_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List entities in the graph."""
        g = await self._get_graphiti()
        gid = group_id if group_id is not None else self._default_group_id()
        nodes = await g.driver.entity_node_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )
        nodes.sort(key=lambda n: n.created_at or "", reverse=True)
        nodes = nodes[:limit]

        return [
            {
                "id": n.uuid,
                "name": n.name,
                "summary": n.summary,
                "created_at": str(n.created_at) if n.created_at else None,
            }
            for n in nodes
        ]

    async def status(self) -> dict[str, Any]:
        """Get graph statistics."""
        g = await self._get_graphiti()
        gids = [self._default_group_id()]
        try:
            entities = await g.driver.entity_node_ops.get_by_group_ids(
                executor=g.driver, group_ids=gids,
            )
            episodes = await g.driver.episode_node_ops.get_by_group_ids(
                executor=g.driver, group_ids=gids,
            )
            return {
                "db_backend": self.settings.db_backend.value,
                "db_path": self.settings.db_path,
                "embedder": self.settings.embedder.value,
                "llm": self.settings.llm.value,
                "entity_count": len(entities),
                "episode_count": len(episodes),
                "connected": True,
            }
        except Exception as e:
            return {
                "db_backend": self.settings.db_backend.value,
                "connected": False,
                "error": str(e),
            }

    async def export_graph(
        self,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Export the full graph as JSON."""
        g = await self._get_graphiti()
        gid = group_id if group_id is not None else self._default_group_id()
        entities = await g.driver.entity_node_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )
        episodes = await g.driver.episode_node_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )
        edges = await g.driver.entity_edge_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )

        return {
            "entities": [
                {
                    "id": n.uuid,
                    "name": n.name,
                    "summary": n.summary,
                    "created_at": str(n.created_at) if n.created_at else None,
                }
                for n in entities
            ],
            "edges": [
                {
                    "id": e.uuid,
                    "source": e.source_node_uuid,
                    "target": e.target_node_uuid,
                    "name": e.name,
                    "fact": e.fact,
                    "created_at": str(e.created_at) if e.created_at else None,
                    "valid_at": str(e.valid_at) if e.valid_at else None,
                    "invalid_at": str(e.invalid_at) if e.invalid_at else None,
                }
                for e in edges
            ],
            "episodes": [
                {
                    "id": ep.uuid,
                    "name": ep.name,
                    "content": ep.content,
                    "created_at": str(ep.created_at) if ep.created_at else None,
                }
                for ep in episodes
            ],
        }

    async def viz_data(
        self,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Get graph data in D3.js-compatible format for visualization."""
        g = await self._get_graphiti()
        gid = group_id if group_id is not None else self._default_group_id()
        entities = await g.driver.entity_node_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )
        edges = await g.driver.entity_edge_ops.get_by_group_ids(
            executor=g.driver, group_ids=[gid],
        )

        entity_ids = {n.uuid for n in entities}

        return {
            "nodes": [
                {
                    "id": n.uuid,
                    "name": n.name,
                    "summary": n.summary or "",
                }
                for n in entities
            ],
            "links": [
                {
                    "source": e.source_node_uuid,
                    "target": e.target_node_uuid,
                    "name": e.name,
                    "fact": e.fact,
                }
                for e in edges
                if e.source_node_uuid in entity_ids
                and e.target_node_uuid in entity_ids
            ],
        }

    async def write_live_data(self, group_id: str | None = None) -> None:
        """Write ~/.graphmem/graph-data.js for the serverless live visualizer."""
        import json

        from graphmem.utils import get_graphmem_home

        data = await self.viz_data(group_id=group_id)
        js = f"window.GRAPH_DATA = {json.dumps(data)};\n"
        (get_graphmem_home() / "graph-data.js").write_text(js)

    async def ping(self) -> dict[str, bool]:
        """Test connectivity to all services."""
        results: dict[str, bool] = {}

        # Test DB
        try:
            g = await self._get_graphiti()
            await g.driver.entity_node_ops.get_by_group_ids(executor=g.driver, group_ids=[self._default_group_id()])
            results["database"] = True
        except Exception:
            results["database"] = False

        # Test embedder
        try:
            embedder = self._create_embedder()
            await embedder.create("test")
            results["embedder"] = True
        except Exception:
            results["embedder"] = False

        return results

    async def close(self):
        """Close connections."""
        if self._graphiti:
            await self._graphiti.close()
            self._graphiti = None


def run_async(coro):
    """Helper to run async functions from sync CLI context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)
