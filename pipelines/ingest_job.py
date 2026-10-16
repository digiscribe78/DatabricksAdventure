"""Serverless job: parse lorebook PDFs, chunk them, write lore_chunks and sync the AI Search index.

Run by the `ingest_lore` bundle job. The pure helpers (chunks_for_rows, index_spec) are unit
tested. main() needs Spark and a workspace.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import PurePosixPath

logger = logging.getLogger("ingest_lore")
COLUMNS = ["chunk_id", "chunk_text", "doc_type", "location_id", "source", "page"]


def chunks_for_rows(rows, meta):
    from lore.chunking import chunk_document

    chunks, skipped = [], []
    for path, doc_json in rows:
        source = PurePosixPath(path).stem
        parsed = json.loads(doc_json)
        if parsed.get("error_status") or source not in meta:
            logger.warning("skipping %s (parse errors or not in manifest)", source)
            skipped.append(source)
            continue
        chunks.extend(chunk_document(parsed, source=source, **meta[source]))
    return chunks, skipped


def index_spec(source_table, embedding_endpoint):
    return {
        "source_table": source_table,
        "pipeline_type": "TRIGGERED",
        "embedding_source_columns": [
            {"name": "chunk_text", "embedding_model_endpoint_name": embedding_endpoint}
        ],
        "columns_to_sync": COLUMNS,
    }


def index_synced(index, expected_rows):
    """True once the index is ready AND has caught up with the rows just written.

    ``ready`` alone stays True from the first build, so after a re-sync it would pass instantly.
    """
    status = getattr(index, "status", None)
    return bool(status and status.ready and status.indexed_row_count == expected_rows)


def _wait(check, what, timeout_s=1800, every_s=20):
    deadline = time.time() + timeout_s
    while not check():
        if time.time() > deadline:
            raise TimeoutError(f"timed out waiting for {what}")
        logger.info("waiting for %s", what)
        time.sleep(every_s)


def main(argv=None):
    p = argparse.ArgumentParser()
    for name in ("--catalog", "--schema", "--endpoint", "--embedding-endpoint", "--src"):
        p.add_argument(name, required=True)
    a = p.parse_args(argv)
    sys.path.insert(0, a.src)
    logging.basicConfig(level=logging.INFO)

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.vectorsearch import (
        DeltaSyncVectorIndexSpecRequest,
        EmbeddingSourceColumn,
        EndpointStatusState,
        PipelineType,
        VectorIndexType,
    )
    from lore.manifest import doc_metadata, load_manifest
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    volume = f"/Volumes/{a.catalog}/{a.schema}/lore"
    table = f"{a.catalog}.{a.schema}.lore_chunks"
    index_name = f"{a.catalog}.{a.schema}.lore_index"

    meta = doc_metadata(load_manifest(f"{volume}/manifest.yaml"))
    rows = spark.sql(
        f"SELECT path, to_json(ai_parse_document(content, map('version', '2.0'))) AS doc_json "
        f"FROM read_files('{volume}/pdfs', format => 'binaryFile')"
    ).collect()
    chunks, skipped = chunks_for_rows([(r.path, r.doc_json) for r in rows], meta)
    if not chunks:
        raise RuntimeError(f"no chunks produced (skipped: {skipped})")
    logger.info("%d chunks from %d documents; skipped %s", len(chunks), len(rows) - len(skipped), skipped)

    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {table} (chunk_id STRING NOT NULL, chunk_text STRING, "
        f"doc_type STRING, location_id STRING, source STRING, page INT) "
        f"TBLPROPERTIES (delta.enableChangeDataFeed = true)"
    )
    df = spark.createDataFrame([[getattr(c, col) for col in COLUMNS] for c in chunks], spark.table(table).schema)
    df.write.mode("overwrite").option("overwriteSchema", "false").saveAsTable(table)

    w = WorkspaceClient()
    _wait(
        lambda: w.vector_search_endpoints.get_endpoint(a.endpoint).endpoint_status.state
        == EndpointStatusState.ONLINE,
        f"endpoint {a.endpoint}",
    )
    existing = {i.name for i in w.vector_search_indexes.list_indexes(a.endpoint)}
    if index_name in existing:
        w.vector_search_indexes.sync_index(index_name)
        logger.info("synced %s", index_name)
    else:
        spec = index_spec(table, a.embedding_endpoint)
        w.vector_search_indexes.create_index(
            name=index_name,
            endpoint_name=a.endpoint,
            primary_key="chunk_id",
            index_type=VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=spec["source_table"],
                pipeline_type=PipelineType.TRIGGERED,
                embedding_source_columns=[EmbeddingSourceColumn(**c) for c in spec["embedding_source_columns"]],
                columns_to_sync=spec["columns_to_sync"],
            ),
        )
        logger.info("created %s", index_name)
    _wait(lambda: index_synced(w.vector_search_indexes.get_index(index_name), len(chunks)), f"index {index_name}")
    logger.info("index %s ready", index_name)


if __name__ == "__main__":
    main()
