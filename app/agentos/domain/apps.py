from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnownAppProfile:
    key: str
    name: str
    slug: str
    repository_url: str
    default_branch: str
    description: str
    product_context: str
    stack: tuple[str, ...]
    guardrails: tuple[str, ...]
    recommended_agents: tuple[str, ...]
    profile_version: int = 1
    memory_version: int = 1

    def memory_document(self) -> str:
        stack = "\n".join(f"- {item}" for item in self.stack)
        guardrails = "\n".join(f"- {item}" for item in self.guardrails)
        agents = ", ".join(self.recommended_agents)
        return (
            f"Application: {self.name}\n"
            f"Repository: {self.repository_url}\n"
            f"Default branch: {self.default_branch}\n\n"
            f"Product context:\n{self.product_context}\n\n"
            f"Stack and architecture:\n{stack}\n\n"
            f"Project guardrails:\n{guardrails}\n\n"
            f"Recommended AgentOS agents: {agents}\n"
        )


KNOWN_APP_PROFILES: dict[str, KnownAppProfile] = {
    "regulaai": KnownAppProfile(
        key="regulaai",
        name="RegulaAI",
        slug="regulaai",
        repository_url="https://github.com/a-castilho/regulaai.git",
        default_branch="main",
        description="Plataforma de inteligência regulatória e análise de impacto empresarial.",
        product_context=(
            "Coleta, normaliza, classifica e analisa processos regulatórios oficiais brasileiros, "
            "cruzando eventos regulatórios com perfis de empresas para produzir impacto, motivos, "
            "áreas afetadas e ações recomendadas."
        ),
        stack=(
            "Python 3.12, FastAPI, SQLAlchemy e PostgreSQL 16 no backend.",
            "React 19 + Vite 6 no frontend.",
            "Coletores idempotentes para Brasil Participativo, ANPD e ANVISA.",
            "Docker/Compose, cron e scripts próprios de sync, health check e recovery.",
        ),
        guardrails=(
            "Priorizar precisão regulatória e nunca inventar deadlines ou eventos.",
            "Preservar idempotência, source_url e histórico de alterações regulatórias.",
            "Não remover volume PostgreSQL nem apagar dados automaticamente.",
            "Executar uma mudança por vez, com testes e health check antes de avançar.",
            "Não executar push, force-push, deploy ou ações destrutivas sem aprovação explícita.",
        ),
        recommended_agents=("researcher", "architect", "backend", "reviewer", "qa"),
    ),
    "maquinadeleads": KnownAppProfile(
        key="maquinadeleads",
        name="Máquina de Leads",
        slug="maquinadeleads",
        repository_url="https://github.com/a-castilho/maquinadeleads.git",
        default_branch="main",
        description="Plataforma autônoma de prospecção, campanhas, leads e mensagens.",
        product_context=(
            "O produto deve permitir criar, configurar, revisar, ativar, executar e acompanhar "
            "campanhas sem depender do n8n no fluxo principal. Campanha é o conceito central; "
            "descoberta, qualificação, mensagens, jobs, retries e funil devem migrar gradualmente "
            "para serviços nativos do backend."
        ),
        stack=(
            "Aplicação com backend Node.js/PostgreSQL como direção arquitetural do fluxo nativo.",
            "Workflows n8n existentes permanecem apenas como integração legada durante a migração.",
            "Deploy/configuração existente inclui Render, Vercel e Docker Compose para n8n.",
        ),
        guardrails=(
            "Não criar nova dependência central de n8n.",
            "Reaproveitar entidades, telas e serviços existentes antes de criar equivalentes.",
            "Preservar contratos e dados; mudanças estruturais devem usar migrations.",
            "Nunca expor tokens, credenciais ou secrets ao frontend ou logs.",
            "Implementar incrementalmente e cobrir criação de campanha, jobs, retries e estados com testes.",
        ),
        recommended_agents=("planner", "architect", "backend", "frontend", "reviewer", "qa"),
    ),
    "telaviva": KnownAppProfile(
        key="telaviva",
        name="TelaViva",
        slug="telaviva",
        repository_url="https://github.com/acastilho/telaviva.git",
        default_branch="main",
        description="Plataforma de transmissões ao vivo para aprender, interagir e apoiar criadores.",
        product_context=(
            "Criadores publicam perfis, agendam transmissões, vendem produtos/assinaturas e recebem "
            "gorjetas; espectadores acompanham agenda, entram em lives autorizadas, interagem, "
            "compram e retomam gravações e trilhas de aprendizagem."
        ),
        stack=(
            "FastAPI/Python 3.12 na API e React + TypeScript no web app.",
            "PostgreSQL 16 e Redis 7, com Docker Compose para ambiente local.",
            "WebSocket para interações ao vivo, storage S3/MinIO e adaptadores de pagamento/mídia.",
            "Testes API/frontend, Ruff, ESLint, mypy e TypeScript.",
        ),
        guardrails=(
            "Preservar autorização em HTTP e WebSocket; acesso comercial deve ser revalidado antes da entrega.",
            "Nunca persistir tokens em claro, chaves PIX ou dados bancários sensíveis.",
            "Manter webhooks e eventos de pagamento idempotentes e auditáveis.",
            "Não simular produção: adaptadores fake devem permanecer restritos ao desenvolvimento.",
            "Executar testes, lint e typecheck compatíveis com o escopo de cada alteração.",
        ),
        recommended_agents=("architect", "backend", "frontend", "reviewer", "qa"),
    ),
}
