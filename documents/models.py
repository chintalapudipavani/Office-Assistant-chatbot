import uuid

import numpy as np
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


def document_upload_path(instance, filename):
    """Save uploads as media/documents/<random>.pdf so two files with the same name
    can never overwrite each other. The original name is kept in original_filename."""
    return f"documents/{uuid.uuid4().hex}.pdf"


class Document(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class Visibility(models.TextChoices):
        ALL = "all", "All employees"
        STAFF = "staff", "Staff only"

    title = models.CharField(max_length=200)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.ALL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROCESSING)
    # For FAILED documents: why. For READY documents: an optional warning.
    error_message = models.TextField(blank=True)
    page_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="uploaded_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    @property
    def is_ready(self):
        return self.status == self.Status.READY


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(default=1)
    text = models.TextField()
    # Raw float32 bytes of the embedding vector (384 numbers = 1536 bytes for MiniLM).
    embedding = models.BinaryField()
    embedding_model = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(fields=["document", "chunk_index"], name="unique_chunk_per_document")
        ]

    def __str__(self):
        return f"{self.document.title} - page {self.page_number} - chunk {self.chunk_index}"

    def set_embedding(self, vector):
        self.embedding = np.asarray(vector, dtype=np.float32).tobytes()

    def get_embedding(self):
        return np.frombuffer(bytes(self.embedding), dtype=np.float32).copy()


@receiver(post_delete, sender=Document)
def delete_pdf_file_with_document(sender, instance, **kwargs):
    """Remove the PDF file from disk whenever a Document row is deleted."""
    if instance.file:
        instance.file.delete(save=False)
