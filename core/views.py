from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from .forms import UserSignupForm, UserLoginForm
from django.http import JsonResponse
from .vector_db import vector_search
from .models import Cart, Product
from .ai_model import GeminiClient
import json

ai = GeminiClient()

confirmed_relevant_data = []


# Signup View
def signup_view(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")  # Redirect to a homepage or dashboard
    else:
        form = UserSignupForm()
    return render(request, "core/signup.html", {"form": form})


# Login View
class CustomLoginView(LoginView):
    form_class = UserLoginForm
    template_name = "core/login.html"


def home_view(request):
    global confirmed_relevant_data
    if request.method == "POST":
        try:
            cart_items = Cart.objects.filter(user=request.user).select_related(
                "product"
            )
            cart_dict = {
                str(item.id): {
                    "Name": item.product.name,
                    "Price": str(item.product.price),
                }
                for item in cart_items
            }
            ai.user = request.user
            data = json.loads(request.body)
            message = data.get("message")
            relevant_data = vector_search(message)
            if len(relevant_data):
                confirmed_relevant_data = relevant_data
            images_ids = []
            for dict in confirmed_relevant_data:
                images_ids.append(dict["ID"])
            images = Product.objects.filter(id__in=images_ids).values(
                "image1", "image2", "image3"
            )
            images_dict = {}
            for index, item in enumerate(images, 1):
                images_dict[f"item_{index}"] = {
                    "image1": item["image1"],
                    "image2": item["image2"],
                    "image3": item["image3"],
                }
            response = ai.get_sales_chat_reply(
                relevant_passage=str(confirmed_relevant_data), query=message
            )
            return JsonResponse(
                {"reply": str(response[0]), "images": response[1], "cart": cart_dict}
            )
        except Exception as e:
            print(e)
    return render(request, "core/home.html")
