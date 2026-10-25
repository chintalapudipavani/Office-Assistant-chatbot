import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from rag.pipeline import answer_question

from .models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

SAMPLE_QUESTIONS = [
    "How many days of annual leave do I get?",
    "How do I reset my password?",
    "What is the hotel limit for business travel in Mumbai?",
    "How long can I book a meeting room?",
]


def home(request):
    return render(request, "home.html", {"sample_questions": SAMPLE_QUESTIONS})


def _serialize(message):
    return {"role": message.role, "content": message.content, "sources": message.sources,
            "answer_found": message.answer_found, "is_error": message.is_error}


@login_required
def chat(request):
    session = None
    raw = request.GET.get("session")
    if raw:
        try:
            session = get_object_or_404(ChatSession, pk=int(raw), user=request.user)
        except ValueError:
            raise Http404
    messages_data = [_serialize(m) for m in session.messages.all()] if session else []
    return render(request, "chat/chat.html", {
        "session": session, "messages_data": messages_data,
        "sample_questions": SAMPLE_QUESTIONS, "max_chars": settings.MAX_QUESTION_CHARS,
    })


def _recent_history(session):
    limit = settings.CHAT_HISTORY_MESSAGES
    if limit <= 0:
        return []
    recent = list(session.messages.filter(is_error=False).order_by("-created_at", "-id")[:limit])
    recent.reverse()
    return [{"role": m.role, "content": m.content[:800]} for m in recent]


@require_POST
def chat_ask(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Your session has expired. Please log in again."}, status=401)
    try:
        payload = json.loads(request.body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request."}, status=400)

    question = str(payload.get("question", "")).strip()
    if not question:
        return JsonResponse({"error": "Please type a question."}, status=400)
    if len(question) > settings.MAX_QUESTION_CHARS:
        return JsonResponse({"error": f"Please keep your question under {settings.MAX_QUESTION_CHARS} characters."},
                            status=400)

    session_id = payload.get("session_id")
    if session_id:
        try:
            session = ChatSession.objects.filter(pk=int(session_id), user=request.user).first()
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid conversation."}, status=400)
        if session is None:
            return JsonResponse({"error": "Conversation not found."}, status=404)
    else:
        title = question[:60] + ("..." if len(question) > 60 else "")
        session = ChatSession.objects.create(user=request.user, title=title)

    history = _recent_history(session)
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=question)

    result = answer_question(question, request.user, history)

    ChatMessage.objects.create(
        session=session, role=ChatMessage.Role.ASSISTANT, content=result.answer,
        sources=result.sources, answer_found=result.answer_found, is_error=result.is_error,
    )
    session.save(update_fields=["updated_at"])
    return JsonResponse({
        "session_id": session.id, "answer": result.answer, "sources": result.sources,
        "answer_found": result.answer_found, "is_error": result.is_error,
    })


@login_required
def chat_history(request):
    sessions = ChatSession.objects.filter(user=request.user).annotate(message_count=Count("messages"))
    return render(request, "chat/history.html", {"sessions": sessions})


@login_required
def chat_new(request):
    return redirect("chat")


@login_required
@require_POST
def chat_delete(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    session.delete()
    messages.success(request, "The conversation was deleted.")
    return redirect("chat_history")
