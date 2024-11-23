import os
import threading
import google.generativeai as genai
from django.conf import settings
import logging
from .models import Cart, Product
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

discussed_product_list = []


class GeminiClient:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _chat = None
    cart = []
    user = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GeminiClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        api_key = "AIzaSyCLjKAxeYnPS_9SrbR7Cm8XNDNtgk3W4HQ"
        if not api_key:
            raise ValueError(
                "Gemini API key not found in settings or environment variables"
            )
        genai.configure(api_key=api_key)

        try:
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                tools=[
                    self.add_to_cart,
                    self.check_cart,
                    self.remove_from_cart,
                    self.add_id_to_list,
                ],
            )
            self._initialized = True
        except Exception as e:
            logger.error(f"Error initializing Gemini models: {str(e)}")
            raise

    @property
    def chat(self):
        if self._chat is None:
            self._chat = self.model.start_chat(enable_automatic_function_calling=True)
        return self._chat

    def add_to_cart(self, product_id: str) -> str:
        """Add item to cart using product_id"""
        int(product_id)
        cart_item, created = Cart.objects.get_or_create(
            user=self.user, product_id=product_id
        )
        print(cart_item)
        return "item has been added to the cart"

    def check_cart(self) -> list:
        """Check products present in the cart"""
        cart_items = Cart.objects.filter(user=self.user)
        cart_products = []
        for cart_item in cart_items:
            product = cart_item.product
            product_details = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
            }
            cart_products.append(product_details)
        return str(cart_products)

    def remove_from_cart(self, product_id: str) -> str:
        """Remove item from cart using product_id"""
        try:
            cart_item = Cart.objects.get(user=self.user, product_id=product_id)
            cart_item.delete()
            return "Item has been removed from the cart"
        except Cart.DoesNotExist:
            return "Item not found in cart"

    def add_id_to_list(self, product_id: str) -> str:
        """Add id to list....which will be used to fetch images"""
        global discussed_product_list
        discussed_product_list.append(int(product_id))
        return "id has been added to the list"

    def get_sales_chat_reply(self, query: str, relevant_passage: str) -> str:
        discussed_product_list.clear()
        cart_hot_words = ["cart", "wishlist", "bag"]
        image_hot_words = ["images", "image", "pictures", "pics"]
        cart_contents = str(self.check_cart())
        if any(word in query.lower() for word in cart_hot_words):
            prompt = (
                "You need to perform one of the operations on the cart......either adding......removing from the cart. "
                + "When you see that you have to add something to the cart make sure to call the add_to_cart function. "
                + "When you see that you have to remove something from the cart make sure to call the remove_from_cart function. "
                + "If the user asks about the items in the cart....reply with the the product names. The cart contents are mentioned below. "
                + "If the user adds or removes products from the cart....then reply with a confirmation and the names of the products. "
                + "Look at the query string and extract the relevant product ids from the provided passage...and execute the function using that data. "
                + "Confirm with the user if you aren't sure about which operation to carry out or you arent sure about the data to be added/removed. "
                + "Make sure the reply is human friendly. "
                + f"\n\nQUERY : '{query}' \n\n"
                + f"PASSAGE : '{relevant_passage}'\n\n"
                + f"CART CONTENTS : {cart_contents}\n\n"
                + "Above mentioned are the contents of the cart....answer any query regarding the cart contents using the above details. "
                + "At the end if the user wants to checkout his cart calculate the total price and confirm all the names of the products in the cart ."
                + "Ask for his name , phone number and shipping address. Once he provides you with these three details confirm him the details and tell him that all itsems will be shipped to him within 7 days and then thank him for shipping with us"
            )
        elif any(word in query.lower() for word in image_hot_words):
            prompt = (
                "The user is requesting to see an image. "
                + "Whichever product or products the user wants to see the image of....make sure to call the add_id_to_list function and pass the relevant product id. "
                + f"QUERY : {query}"
                + f"\n\nPASSAGE : {relevant_passage}\n\n"
            )

        else:
            prompt = (
                "You are a human salesman who needs to carry out the following task. "
                + "I will be providing you with a passage that contains the data of one or more products. "
                + "It has details about the product's id , name , description , price and distance. Ignore the distance completely and work only with the other 4 data fields. "
                + f"\n\nPASSAGE: '{relevant_passage}'\n\n"
                + "The above mentioned passage will almost always contain the data you need to answer the below mentioned query. "
                + f"\n\nQUERY : '{query}' \n\n"
                + "Using mostly the data in the passage suggest products mentioning the relevant details that can help the situation that comes up in the query. "
                + "Make sure to be friendly and provide whatever details are being asked for. "
                + "The data in the passage will almost always be relevant to the query, however if the passage is empty or the data is not relevant then just reply the way a human salesman would. "
                + "Reply in moderate to extensive detail, in about 50-75 words. "
                + "Use only the first 2 products from the passage for all purposes unless prompted for more details. "
            )
        response = self.chat.send_message(prompt)
        images = Product.objects.filter(id__in=discussed_product_list).values(
            "image1", "image2", "image3"
        )
        images_dict = {}
        for index, item in enumerate(images, 1):
            images_dict[f"item_{index}"] = {
                "image1": item["image1"],
                "image2": item["image2"],
                "image3": item["image3"],
            }
        reply = response._result.candidates[0].content.parts[0].text.strip()
        return [reply, images_dict]
