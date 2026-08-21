from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

from app.services.career_sync import copy_package, extract_resume_text, parse_resume, profile_diff

SAMPLE = """André Castilho
TECH LEAD | ARQUITETO DE SOFTWARE | DESENVOLVEDOR BACKEND SÊNIOR
São Paulo - SP | andre@example.com | linkedin.com/in/example
RESUMO PROFISSIONAL
Profissional de tecnologia com experiência em Python, FastAPI, PostgreSQL e IA aplicada.
COMPETÊNCIAS-CHAVE
Python; FastAPI; PostgreSQL; Docker; OpenAI; Codex CLI
EXPERIÊNCIA PROFISSIONAL
ACS Informática | Tech Lead / Desenvolvedor Web Sênior | Out/2024 - Atual
• Liderança técnica e arquitetura de APIs e microserviços.
TradeUp | Desenvolvedor de Software Sênior | Out/2023 - Set/2024
• Arquitetura Hexagonal, DDD e APIs.
PROJETOS RECENTES | ARQUITETURA & IA APLICADA
DevPilot — Plataforma agentic de engenharia com FastAPI, workers e Codex CLI.
RegulaAI — Inteligência regulatória com classificação determinística e impacto explicável.
FORMAÇÃO
Bacharelado em Sistemas de Informação - UNISA
IDIOMAS
Inglês: Intermediário
"""


def _docx_bytes(text: str) -> bytes:
    paragraphs = "".join(
        f'<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines()
        if line
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def test_extracts_docx_without_external_dependency():
    text = extract_resume_text("resume.docx", _docx_bytes(SAMPLE))
    assert "André Castilho" in text
    assert "DevPilot" in text


def test_parses_linkedin_ready_profile():
    profile = parse_resume(SAMPLE)
    assert profile["name"] == "André Castilho"
    assert profile["headline"].startswith("TECH LEAD")
    assert "FastAPI" in profile["skills"]
    assert profile["experience"][0]["company"] == "ACS Informática"
    assert profile["projects"][0]["name"] == "DevPilot"
    assert "PROJETOS RECENTES" not in profile["experience"][-1]["description"]


def test_diff_and_copy_package_are_deterministic():
    profile = parse_resume(SAMPLE)
    baseline = {"headline": "Senior Developer", "skills": ["Python"]}
    fields = {change["field"] for change in profile_diff(baseline, profile)}
    assert {"headline", "skills"} <= fields
    package = copy_package(profile)
    assert package["experience"][0]["header"].startswith("ACS Informática | Tech Lead")
