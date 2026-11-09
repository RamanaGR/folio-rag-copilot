import base64
import re
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from . import config
from .memory_store import MemoryStore
from .models import (
    CoverLetterRequest,
    CoverLetterResponse,
    FieldAnswer,
    HealthResponse,
    LearnRequest,
    LearnResponse,
    ResolveFormRequest,
    ResolveFormResponse,
    ResolvedField,
)
from .ollama_engine import OllamaEngine, OllamaError
from .pdf_builder import build_cover_letter_pdf

app = FastAPI(title="Folio RAG Copilot", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
store = MemoryStore(config.MEMORY_DB_PATH)
engine = OllamaEngine()


def _profile_context(profile: dict[str, Any]) -> str:
    return str(profile)


def _project_context(profile: dict[str, Any]) -> str:
    projects = []
    for project in profile.get("project_case_studies", []):
        projects.append(
            "\n".join(
                [
                    f"PROJECT: {project.get('id')} | ROLE: {project.get('role')} | COMPANY: {project.get('company')} | PERIOD: {project.get('period')}",
                    f"DOMAIN: {project.get('domain')}",
                    f"HIGHLIGHTS: {' '.join(project.get('highlights', []))}",
                    f"TECH: {', '.join(project.get('tech_stack', []))}",
                ]
            )
        )
    return "\n\n".join(projects)


def _normalized(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    value = re.sub(r"\b(required|optional)\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _profile_answer(label: str, profile: dict[str, Any]) -> FieldAnswer | None:
    """Resolve only explicit, low-risk profile facts without asking the model to guess."""
    normalized = _normalized(label)
    aliases = {
        "first name": ("personal", "first_name"),
        "given name": ("personal", "first_name"),
        "last name": ("personal", "last_name"),
        "family name": ("personal", "last_name"),
        "surname": ("personal", "last_name"),
        "full name": ("personal", "full_name"),
        "email": ("personal", "email"),
        "email address": ("personal", "email"),
        "phone": ("personal", "phone"),
        "phone number": ("personal", "phone"),
        "mobile": ("personal", "phone"),
        "city": ("personal", "city"),
        "state": ("personal", "state"),
        "country": ("personal", "country"),
        "linkedin": ("links", "linkedin"),
        "linkedin url": ("links", "linkedin"),
        "github": ("links", "github"),
        "github url": ("links", "github"),
        "current location": ("work_authorization_and_logistics", "current_location"),
        "notice period": ("work_authorization_and_logistics", "notice_period"),
        "notice period weeks": ("work_authorization_and_logistics", "notice_period_weeks"),
        "willing to relocate": ("work_authorization_and_logistics", "willing_to_relocate"),
        "requires visa sponsorship": ("work_authorization_and_logistics", "requires_eu_visa_sponsorship"),
        "requires sponsorship": ("work_authorization_and_logistics", "requires_eu_visa_sponsorship"),
        "date of birth": ("personal", "date_of_birth"),
    }
    variants = {
        normalized,
        re.sub(r"^(what is your|what's your|please enter your|enter your|your)\s+", "", normalized),
        re.sub(r"^(are you|do you)\s+", "", normalized),
    }
    key = next((candidate for candidate in aliases if candidate in variants), None)
    if key is None:
        return None
    section, field = aliases[key]
    value = profile.get(section, {}).get(field)
    if value in (None, "", []):
        return None
    return FieldAnswer(value=str(value).lower() if isinstance(value, bool) else str(value), confidence=1.0, needs_human=False, reason="Verified profile")


def _narrative_fallback(label: str, profile: dict[str, Any]) -> FieldAnswer | None:
    normalized = _normalized(label)
    if any(term in normalized for term in ("impactful", "impact", "specific contribution", "contribution", "most impactful", "biggest achievement")):
        value = "The most impactful system I built was a grounded multi-agent RAG platform for contract understanding at Innovapath for Optum. My specific contribution was designing the 9-agent Google ADK workflow, ReAct retrieval, MCP interface, Pydantic validation, and the 16-node Neo4j knowledge graph. I also built FastAPI services and DeepEval evaluation workflows, reducing contract review effort by 40-50% with p95 latency below 5 seconds."
    elif any(term in normalized for term in ("complex project", "llm", "fine tuning", "scale of data", "ai project")):
        value = "My strongest LLM work spans two projects. At Innovapath for Optum, I built a 9-agent Google ADK pipeline with Document AI, Gemini, Neo4j, ReAct retrieval, MCP, and grounded citations, with p95 latency below 5 seconds. At Atlantis University, I built a LangGraph RAG platform using Bedrock, Milvus hybrid retrieval, reranking, Redis caching, and DeepEval for candidate evaluation."
    elif any(term in normalized for term in ("non expert", "client", "customer", "presentation", "explain a complex")):
        value = "Across my AI projects, I explain complex systems by connecting them to a simple workflow. For an AI governance platform at Synechron, I used a request-to-review example to explain Kafka telemetry, LLM-as-a-Judge checks, and human approval to non-specialists. I also used contract-extraction examples from the Optum project, adjusted the technical depth, and confirmed understanding through questions."
    elif any(term in normalized for term in ("what should we know", "about you", "tell us about yourself")):
        value = "I am a Senior AI and Software Engineer focused on agentic AI, RAG, evaluation, and backend systems. My recent work includes Google ADK, LangGraph, FastAPI, Kafka, Neo4j, AWS, and GCP across financial, healthcare, and talent platforms. I prefer grounded systems with clear evaluation, observable behavior, and a practical human review path."
    else:
        return None
    return FieldAnswer(value=value, confidence=0.88, needs_human=False, reason="Grounded profile fallback")


def _is_application_ready(value: str) -> bool:
    words = value.split()
    lower = value.lower()
    first_person = any(token in lower.split() for token in ("i", "i'm", "my", "me", "we"))
    third_person = re.search(
        r"\b(ramana(?:\s+gangarao)?|he|his|the candidate|the engineer)(?:['’]s)?\b",
        lower,
    )
    return 40 <= len(words) <= 100 and first_person and not third_person and not any(mark in value for mark in (";", "—"))


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", ollama_url=config.OLLAMA_BASE_URL, memory_count=store.count())


@app.post("/api/resolve-form", response_model=ResolveFormResponse)
async def resolve_form(request: ResolveFormRequest) -> ResolveFormResponse:
    profile = config.load_profile()
    answers: list[ResolvedField] = []
    grounding = _profile_context(profile)
    for field in request.fields:
        direct_answer = _profile_answer(field.label, profile)
        if direct_answer:
            answers.append(ResolvedField(label=field.label, answer=direct_answer))
            continue
        try:
            embedding = await engine.embed(field.label)
            learned = store.find_similar(embedding)
        except (OllamaError, Exception):
            learned = None
        narrative = field.field_type in {"textarea", "text", "search"} or len(field.label) > 90
        if learned:
            answer = FieldAnswer(value=learned["answer"], confidence=1.0, needs_human=False, reason="Learned answer")
            if narrative and not _is_application_ready(answer.value):
                answer = _narrative_fallback(field.label, profile) or FieldAnswer()
        else:
            if narrative:
                system = """You write a concise first-person answer that the applicant can paste into an application. Speak as Ramana, not about Ramana. Start with I, My, or a natural first-person sentence. Never refer to Ramana, the candidate, the engineer, he, or his. Use only facts in the supplied profile. Return JSON with keys value, confidence, needs_human, reason. Synthesize a direct answer from the relevant project facts rather than requiring an exact sentence in the profile. Use 2-4 sentences and 40-75 words unless the question asks for a different length. Never invent employers, metrics, dates, skills, clients, or responsibilities. If the profile has no relevant facts, return an empty value with confidence 0 and needs_human true. Never use em-dashes, semicolons, bullets, or these words: delve, testament, tapestry, passionate, thrilled, excited, dynamic, leverage, spearhead, synergy, cutting-edge, seamlessly, pivotal, honing, eager, align, foster, realm, embark, unwavering, moreover, furthermore."""
            else:
                system = "You answer form questions only from the supplied profile. Return JSON with keys value, confidence, needs_human, reason. If the exact fact is absent, value must be empty, confidence 0, needs_human true, reason Not in profile. Do not infer sensitive facts."
            prompt = f"Candidate profile: {grounding}\n\nComplete project dossier:\n{_project_context(profile)}\n\nQuestion: {field.label}\nField type: {field.field_type}\nAvailable options: {field.options}\nCompare every project in the dossier before answering. Select the most relevant project or combine multiple relevant projects. If the question asks for impact, explain the concrete system, the candidate's specific contribution, and the verified result. Do not default to the newest project merely because it appears first."
            try:
                result = await engine.structured(system, prompt)
                answer = FieldAnswer.model_validate(result)
                if narrative and (not answer.value.strip() or answer.needs_human or not _is_application_ready(answer.value)):
                    answer = _narrative_fallback(field.label, profile) or answer
            except (OllamaError, ValueError, Exception):
                answer = _narrative_fallback(field.label, profile) or FieldAnswer()
        answers.append(ResolvedField(label=field.label, answer=answer))
    return ResolveFormResponse(answers=answers)


@app.post("/api/learn", response_model=LearnResponse)
async def learn(request: LearnRequest) -> LearnResponse:
    if not request.user_value.strip():
        return LearnResponse(learned=False, message="Empty values are not learned", confidence=0.0)
    try:
        embedding = await engine.embed(request.question_label)
    except (OllamaError, Exception) as error:
        raise HTTPException(status_code=503, detail=f"Embedding service unavailable: {error}") from error
    store.add(request.question_label, request.user_value, request.field_type, request.options, request.domain, request.selector_hint, embedding)
    return LearnResponse(learned=True, message="Learned for future forms")


@app.post("/api/cover-letter", response_model=CoverLetterResponse)
async def cover_letter(request: CoverLetterRequest) -> CoverLetterResponse:
    profile = config.load_profile()
    prompt = f"Candidate profile: {_profile_context(profile)}\nRole title: {request.context.title}\nCompany: {request.context.company}\nJob description: {request.context.description[:8000]}"
    try:
        text = await engine.cover_letter(prompt)
    except (OllamaError, Exception) as error:
        raise HTTPException(status_code=503, detail=f"Cover letter service unavailable: {error}") from error
    text = re.sub(r"[\u2012\u2013\u2014;]", ",", text).strip()
    if request.output == "pdf":
        encoded = base64.b64encode(build_cover_letter_pdf(text)).decode("ascii")
        return CoverLetterResponse(text=text, content_base64=encoded)
    return CoverLetterResponse(text=text)


@app.get("/api/files/{kind}")
async def files(kind: str) -> Response:
    if kind == "resume":
        if not config.RESUME_PATH.is_file():
            raise HTTPException(status_code=404, detail="data/Ramana_Gangarao_CV.pdf is not available")
        return FileResponse(config.RESUME_PATH, media_type="application/pdf", filename="Ramana_Gangarao_CV.pdf")
    raise HTTPException(status_code=404, detail="Unknown file kind")
