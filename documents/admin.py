from django.contrib import admin

from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "original_filename", "visibility", "status",
                    "page_count", "chunk_count", "uploaded_by", "uploaded_at")
    list_filter = ("status", "visibility")
    search_fields = ("title", "original_filename")
    readonly_fields = ("original_filename", "file", "status", "error_message",
                       "page_count", "chunk_count", "uploaded_by", "uploaded_at")

    def has_add_permission(self, request):
        # Uploads must use the Upload page so the PDF is processed and indexed.
        return False


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "page_number", "chunk_index", "short_text")
    list_filter = ("document",)
    search_fields = ("text",)

    @admin.display(description="Text preview")
    def short_text(self, obj):
        return obj.text[:80] + ("..." if len(obj.text) > 80 else "")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
