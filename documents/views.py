import logging
import os

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from rag import vector_store
from rag.exceptions import RAGError

from . import services
from .forms import DocumentUploadForm
from .models import Document, DocumentChunk
from .permissions import document_manager_required

logger = logging.getLogger(__name__)


@document_manager_required
def document_list(request):
    documents = Document.objects.select_related("uploaded_by")
    ready_chunks = DocumentChunk.objects.filter(document__status=Document.Status.READY).count()
    index_error = None
    try:
        index_size = vector_store.size()
    except RAGError as exc:
        index_size, index_error = None, exc.user_message
    return render(request, "documents/list.html", {
        "documents": documents,
        "ready_chunks": ready_chunks,
        "index_size": index_size,
        "index_error": index_error,
        "out_of_sync": index_size is not None and index_size != ready_chunks,
    })


@document_manager_required
def document_upload(request):
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            name = os.path.basename(upload.name)[:255]
            document = Document(
                title=form.cleaned_data["title"].strip() or os.path.splitext(name)[0],
                original_filename=name,
                visibility=form.cleaned_data["visibility"],
                uploaded_by=request.user,
                file=upload,
            )
            document.save()
            services.process_document(document)   # can take a while for big PDFs
            if document.status == Document.Status.READY:
                messages.success(request, f"'{document.title}' was processed: "
                                          f"{document.page_count} page(s), {document.chunk_count} chunk(s).")
                if document.error_message:
                    messages.warning(request, document.error_message)
            else:
                messages.error(request, f"'{document.title}' could not be processed. {document.error_message}")
            return redirect("document_list")
    else:
        form = DocumentUploadForm()
    return render(request, "documents/upload.html", {"form": form})


@document_manager_required
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk)
    title = document.title
    try:
        services.delete_document(document)
        messages.success(request, f"'{title}' was deleted and the search index was updated.")
    except RAGError as exc:
        messages.warning(request, f"'{title}' was deleted, but the index needs attention: {exc.user_message}")
    return redirect("document_list")


@document_manager_required
@require_POST
def document_rebuild(request):
    try:
        count = services.rebuild_index()
        messages.success(request, f"The search index was rebuilt with {count} chunk(s).")
    except RAGError as exc:
        messages.error(request, exc.user_message)
    except Exception:
        logger.exception("Index rebuild failed")
        messages.error(request, "The index could not be rebuilt. See the server log.")
    return redirect("document_list")
