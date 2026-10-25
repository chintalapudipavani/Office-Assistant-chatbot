from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from rag import chunker, text_cleaning, vector_store
from rag.testing import RagTestCase, make_pdf_bytes

from .models import Document, DocumentChunk

User = get_user_model()

LEAVE_TEXT = "Annual leave policy. Every employee gets 18 days of annual leave per calendar year."


class TextProcessingTests(RagTestCase):
    def test_clean_text_joins_hyphenated_words_and_collapses_space(self):
        self.assertEqual(text_cleaning.clean_text("re-\nimbursement   rules\n\n\n\nend"), "reimbursement rules\n\nend")

    def test_chunker_respects_size_and_overlap(self):
        text = " ".join(f"word{i}." for i in range(400))
        chunks = chunker.split_text(text, 300, 60)
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c) <= 300 for c in chunks))
        self.assertEqual(chunker.split_text("", 300, 60), [])
        self.assertEqual(chunker.split_text("short", 300, 60), ["short"])


class DocumentViewTests(RagTestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user("admin1", password="pass12345!", is_staff=True)
        self.employee = User.objects.create_user("emp1", password="pass12345!")

    def _upload(self, name, data, visibility="all", title=""):
        return self.client.post(reverse("document_upload"), {
            "title": title, "visibility": visibility,
            "file": SimpleUploadedFile(name, data, content_type="application/pdf"),
        }, follow=True)

    def test_anonymous_redirected_and_employee_forbidden(self):
        self.assertEqual(self.client.get(reverse("document_list")).status_code, 302)
        self.client.login(username="emp1", password="pass12345!")
        self.assertEqual(self.client.get(reverse("document_list")).status_code, 403)
        self.assertEqual(self.client.post(reverse("document_upload")).status_code, 403)

    def test_valid_pdf_is_processed_and_indexed(self):
        self.client.login(username="admin1", password="pass12345!")
        self._upload("leave.pdf", make_pdf_bytes([LEAVE_TEXT]), title="Leave Policy")
        doc = Document.objects.get()
        self.assertEqual(doc.status, Document.Status.READY)
        self.assertEqual(doc.page_count, 1)
        self.assertGreaterEqual(doc.chunk_count, 1)
        self.assertEqual(vector_store.size(), DocumentChunk.objects.count())

    def test_rejects_wrong_extension_and_fake_pdf(self):
        self.client.login(username="admin1", password="pass12345!")
        self._upload("notes.txt", b"hello")
        self.assertEqual(Document.objects.count(), 0)
        self._upload("fake.pdf", b"this is not a pdf at all")
        self.assertEqual(Document.objects.count(), 0)
        self._upload("empty.pdf", b"")
        self.assertEqual(Document.objects.count(), 0)

    def test_blank_pdf_marked_failed_with_message(self):
        self.client.login(username="admin1", password="pass12345!")
        self._upload("blank.pdf", make_pdf_bytes([""]))
        doc = Document.objects.get()
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertIn("No readable text", doc.error_message)
        self.assertEqual(vector_store.size(), 0)

    def test_delete_removes_chunks_file_and_vectors(self):
        self.client.login(username="admin1", password="pass12345!")
        self._upload("a.pdf", make_pdf_bytes([LEAVE_TEXT]), title="A")
        self._upload("b.pdf", make_pdf_bytes(["Meeting rooms can be booked for 2 hours at a time."]), title="B")
        a = Document.objects.get(title="A")
        file_path = Path(a.file.path)
        self.assertTrue(file_path.exists())
        before = vector_store.size()
        self.client.post(reverse("document_delete", args=[a.pk]))
        self.assertFalse(Document.objects.filter(pk=a.pk).exists())
        self.assertFalse(file_path.exists())
        self.assertLess(vector_store.size(), before)
        self.assertEqual(vector_store.size(), DocumentChunk.objects.count())

    def test_rebuild_restores_a_deleted_index_file(self):
        self.client.login(username="admin1", password="pass12345!")
        self._upload("a.pdf", make_pdf_bytes([LEAVE_TEXT]))
        from django.conf import settings
        settings.RAG_INDEX_PATH.unlink()
        vector_store.reset_cache()
        self.assertEqual(vector_store.size(), 0)
        self.client.post(reverse("document_rebuild"))
        self.assertEqual(vector_store.size(), DocumentChunk.objects.count())
