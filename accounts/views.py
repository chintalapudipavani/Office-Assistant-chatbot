from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegistrationForm


def register(request):
    """Show the registration form (GET) or create the account (POST).
    New users are regular employees, NOT staff."""
    if request.user.is_authenticated:
        return redirect("chat")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f"Welcome, {user.first_name or user.username}! Your account was created.",
            )
            return redirect("chat")
    else:
        form = RegistrationForm()

    return render(request, "registration/register.html", {"form": form})
