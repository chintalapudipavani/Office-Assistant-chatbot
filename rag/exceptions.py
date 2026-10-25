"""Custom errors. Each carries a friendly message that is safe to show to users."""


class RAGError(Exception):
    default_message = "Something went wrong while processing your request."

    def __init__(self, message=None):
        self.user_message = message or self.default_message
        super().__init__(self.user_message)


class InvalidPDFError(RAGError):
    default_message = "This file could not be read as a PDF. It may be damaged or password-protected."


class EmptyPDFError(RAGError):
    default_message = (
        "No readable text was found in this PDF. It may be a scanned image. "
        "Please upload a PDF that contains selectable text."
    )


class EmbeddingError(RAGError):
    default_message = (
        "The text-embedding model could not be loaded. Check your internet connection "
        "for the first download and the EMBEDDING_MODEL_NAME setting."
    )


class VectorStoreError(RAGError):
    default_message = "The search index has a problem. An administrator should click 'Rebuild index'."


class LLMConfigurationError(RAGError):
    default_message = (
        "The AI language model is not configured. Ask the administrator to set LLM_API_KEY "
        "in the .env file and restart the server."
    )


class LLMUnavailableError(RAGError):
    default_message = "The AI language model service is not reachable right now. Please try again in a few minutes."
