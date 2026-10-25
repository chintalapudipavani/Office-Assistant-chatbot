from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from documents.services import process_document


def title_from_filename(path):
    stem = path.stem
    parts = stem.split("_")
    if parts and parts[0].isdigit():
        parts = parts[1:]
    words = [w.upper() if w.lower() in {"it", "hr"} else w.capitalize() for w in parts]
    return " ".join(words)


class Command(BaseCommand):
    help = ("Load every PDF in a folder (default: sample_documents) as a document. "
            "Files with 'confidential' in the name are saved as Staff only.")

    def add_arguments(self, parser):
        parser.add_argument("--folder", default="sample_documents")
        parser.add_argument("--username", default=None, help="Uploader. Default: first superuser.")

    def handle(self, *args, **options):
        folder = Path(options["folder"])
        if not folder.is_absolute():
            folder = settings.BASE_DIR / folder
        if not folder.is_dir():
            raise CommandError(f"Folder not found: {folder}")
        pdfs = sorted(folder.glob("*.pdf"))
        if not pdfs:
            raise CommandError(f"No PDF files in {folder}. Run: python tools\\make_sample_pdfs.py")

        User = get_user_model()
        if options["username"]:
            uploader = User.objects.filter(username=options["username"]).first()
            if not uploader:
                raise CommandError(f"User '{options['username']}' does not exist.")
        else:
            uploader = User.objects.filter(is_superuser=True).first()

        for pdf in pdfs:
            if Document.objects.filter(original_filename=pdf.name, status=Document.Status.READY).exists():
                self.stdout.write(f"Skipped (already loaded): {pdf.name}")
                continue
            visibility = Document.Visibility.STAFF if "confidential" in pdf.name.lower() else Document.Visibility.ALL
            document = Document(title=title_from_filename(pdf), original_filename=pdf.name,
                                visibility=visibility, uploaded_by=uploader)
            with open(pdf, "rb") as handle:
                document.file.save(pdf.name, File(handle), save=False)
            document.save()
            process_document(document)
            if document.status == Document.Status.READY:
                self.stdout.write(self.style.SUCCESS(
                    f"Loaded: {pdf.name} ({document.page_count} pages, {document.chunk_count} chunks, {visibility})"))
                if document.error_message:
                    self.stdout.write(self.style.WARNING("  " + document.error_message))
            else:
                self.stdout.write(self.style.ERROR(f"FAILED: {pdf.name} - {document.error_message}"))
