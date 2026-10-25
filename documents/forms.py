from django import forms
from django.conf import settings

from .models import Document


class DocumentUploadForm(forms.Form):
    title = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Optional. If empty, the file name is used.",
    )
    visibility = forms.ChoiceField(
        choices=Document.Visibility.choices, initial=Document.Visibility.ALL,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="'Staff only' documents are never used to answer ordinary employees.",
    )
    file = forms.FileField(
        label="PDF file",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "application/pdf,.pdf"}),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Only PDF files (.pdf) are allowed.")
        if upload.size == 0:
            raise forms.ValidationError("The file is empty.")
        if upload.size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise forms.ValidationError(f"The file is too large. The limit is {settings.MAX_UPLOAD_SIZE_MB} MB.")
        header = upload.read(5)
        upload.seek(0)
        if header != b"%PDF-":
            raise forms.ValidationError("This file is not a real PDF (its content does not start like a PDF).")
        return upload
