import os
import threading
import google.generativeai as genai
from django.conf import settings
import logging
from .models import Cart
from django.shortcuts import get_object_or_404
import base64

# Cart,created = Cart.objects.get_or_create(user = req.user , other params)
# cart.products.add()

logger = logging.getLogger(__name__)


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
        api_key = "AIzaSyCadPuPUQvtH-NsETbzmgooO9OT2NkAt1s"
        if not api_key:
            raise ValueError(
                "Gemini API key not found in settings or environment variables"
            )
        genai.configure(api_key=api_key)

        try:
            self.model = genai.GenerativeModel(
                model_name="gemini-pro",
                tools=[self.add_to_cart, self.check_cart, self.remove_from_cart],
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

    def add_to_cart(self, product_id: int) -> str:
        """Add item to cart using product_id"""
        cart_item, created = Cart.objects.get_or_create(
            user=self.user, product_id=product_id
        )
        print(cart_item)
        return "item has been added to the cart"

    def check_cart(self) -> list:
        cart_items = Cart.objects.filter(user=self.user)
        cart_products = []
        for cart_item in cart_items:
            product = cart_item.product
            product_details = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
                "images": {
                    "image1": product.image1.path if product.image1 else None,
                    "image2": product.image2.path if product.image2 else None,
                    "image3": product.image3.path if product.image3 else None,
                },
            }
            cart_products.append(product_details)

        return str(cart_products)

    def remove_from_cart(self, product_id: int) -> str:
        """Remove item from cart using product_id"""
        try:
            # Find and delete the cart item for the specific user and product
            cart_item = Cart.objects.get(user=self.user, product_id=product_id)
            cart_item.delete()
            return "Item has been removed from the cart"
        except Cart.DoesNotExist:
            return "Item not found in cart"

    def identify_topic(self, query: str, user: object) -> str:
        if self.user is None:
            self.user = user
        try:
            prompt = (
                "From the query I am providing to you I want you to identify the type/category of products that I require. "
                + "If my prompt is like 'I want clothes for a sunny day' , I want you to return 'clothes for a sunny day'. "
                + "If my prompt is like 'I want to buy jeans' , I want you to return 'jeans' as the topic. "
                + "If my prompt is like 'I want to buy male t-shirts' , I want you to return 'male t-shirts' as the topic. "
                + "Follow the above mentioned pattern and keep your answers as short as possible without losing any detail. "
                + "Concise answers are preferred. "
                + "The reply you give must STRICTLY depend on the query given as input or the chat history. "
                + "If the query itself doesnt have any topic, then look at the chat history and return the latest topic, that is, the last output that the same prompt produced. "
                + "Do not give a response looking at the examples I have shown. Those were only to explain the method of topic detection. "
                f"QUERY - {query}"
            )

            response = self.chat.send_message(prompt)

            if hasattr(response, "text"):
                return response.text.strip()
            return response._result.candidates[0].content.parts[0].text.strip()

        except Exception as e:
            logger.error(f"Error identifying topic: {str(e)}")
            return None

    def get_sales_chat_reply(self, query: str, relevant_passage: str) -> str:
        cart_hot_words = ["cart", "wishlist", "bag"]
        print(query)
        if any(word in query.lower() for word in cart_hot_words):
            prompt = (
                "You need to perform one of the operations on the cart......either adding......removing.......or checking the products in the cart. "
                + "When you see that you have to add something to the cart make sure to call the add_to_cart function. "
                + "When you see that you have to get details from the cart make sure to call the check_cart function. "
                + "When you see that you have to remove something from the cart make sure to call the remove_from_cart function. "
                + "you have been provided with the necesary tools for each of the operations"
                "look at the query string and extract the relevant product ids from the provided passage...and execute the function using that data"
                "make sure the operations happens on valid data"
                "be very careful while extracting the data from the query"
                "confirm with the user if you aren't sure about which operation to carry out or you arent sure about the data to be added/removed"
                "look at the chat history giving more importance to the latest messages while making decisions as well"
                "it is essential that an operation on cart is carried out when this prompt is called. "
                "request confirmation but always perform an operation."
                "dont worry about quantity right now....just add the product id"
                f"\n\nQUERY : '{query}' \n\n"
                f"PASSAGE : '{relevant_passage}'\n\n"
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
                + "The data in the passage will almost always be relevant to the query, however if the passage is empty or the data is not relevant then just reply that it is not a relevant query. "
                + "Reply in moderate to extensive detail, in about 75-100 words. "
                + "Use only the first 2 products from the passage for all purposes unless prompted for more details. "
            )

        response = self.chat.send_message(prompt)
        reply = response._result.candidates[0].content.parts[0].text.strip()
        print(self.cart)
        print(reply)
        return reply
