from django.core.management.base import BaseCommand, CommandError

from documents import services
from rag.exceptions import RAGError


class Command(BaseCommand):
    help = "Rebuild the FAISS search index from the chunks stored in the database."

    def handle(self, *args, **options):
        try:
            count = services.rebuild_index()
        except RAGError as exc:
            raise CommandError(exc.user_message)
        self.stdout.write(self.style.SUCCESS(f"Index rebuilt with {count} chunk(s)."))
