from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rag_operational_dashboard_exposes_live_visual_metrics():
    ui = (ROOT / "app/static/rag-jobs-ui.js").read_text(encoding="utf-8")

    assert "RAG em tempo real" in ui
    assert "Documentos indexados" in ui
    assert "Chunks vetorizados" in ui
    assert "Projetos indexados" in ui
    assert "Consultas retrieval" in ui
    assert "Última indexação" in ui
    assert "Última consulta" in ui
    assert "Na fila" in ui
    assert "INDEXANDO" in ui
    assert "CONCLUÍDO" in ui
    assert "FALHOU" in ui
    assert "/super-admin/rag/metrics" in ui
    assert "/super-admin/rag/projects/${encodeURIComponent(projectId)}/metrics" in ui
    assert "Promise.allSettled" in ui


def test_rag_operational_dashboard_shows_real_indexing_results():
    ui = (ROOT / "app/static/rag-jobs-ui.js").read_text(encoding="utf-8")

    assert "indexed_files" in ui
    assert "skipped_files" in ui
    assert "failed_files" in ui
    assert "chunks_indexed" in ui
    assert "Motivo:" in ui
    assert "indexados" in ui
    assert "ignorados" in ui
    assert "falhas" in ui
    assert "chunks" in ui


def test_rag_operational_dashboard_is_mobile_responsive():
    ui = (ROOT / "app/static/rag-jobs-ui.js").read_text(encoding="utf-8")

    assert "@media(max-width:900px)" in ui
    assert "@media(max-width:560px)" in ui
    assert "rag-ops-grid" in ui
    assert "grid-template-columns:1fr" in ui


def test_rag_metrics_serialize_operational_timestamps_and_counters():
    from app.rag.metrics import RagMetricsService

    stamp = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)
    result = RagMetricsService._serialize_row(
        {
            "documents": 7,
            "indexed_projects": 2,
            "chunks": 31,
            "indexed_tokens": 1200,
            "jobs_pending": 1,
            "jobs_processing": 0,
            "jobs_completed": 4,
            "jobs_failed": 0,
            "queries_total": 5,
            "cache_hits": 2,
            "avg_retrieval_ms": 12.5,
            "chunks_retrieved": 9,
            "last_indexed_at": stamp,
            "last_query_at": stamp,
            "last_job_at": stamp,
        }
    )

    assert result["documents"] == 7
    assert result["indexed_projects"] == 2
    assert result["jobs_completed"] == 4
    assert result["cache_hit_rate"] == 40.0
    assert result["avg_retrieval_ms"] == 12.5
    assert result["last_indexed_at"] == stamp.isoformat()
    assert result["last_query_at"] == stamp.isoformat()
    assert result["last_job_at"] == stamp.isoformat()
