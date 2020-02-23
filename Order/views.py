from django.shortcuts import render, get_object_or_404, redirect, reverse, HttpResponse
# 160220 login_ required
from django.contrib.auth.decorators import login_required
from .forms import OrderForm, PaymentForm
from django.conf import settings
from django.contrib import messages
from Catalog.models import Book
from .models import OrderItem, Order
import stripe 

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def checkout(request):
    cart = list((request.session.get('shopping_cart', {})).values())

    # get the total amount of the orders
    total_amount = 0
    
    for elem in cart:
        total_amount = (total_amount + float(elem['total_price']))
        total_amount = total_amount
    
    # round up total amount to 2 decimal points
    total_amount = round(total_amount, 2)
    
    # check if delivery fees is needed
    if total_amount < 100.00:
        delivery_fee = 3.95
    else:
        delivery_fee = 0.00
        
    # total
    total_amount = round((total_amount + delivery_fee), 2)


    if request.method == "POST":
        
        order_form = OrderForm(request.POST)
        payment_form = PaymentForm(request.POST)

        if order_form.is_valid() and payment_form.is_valid():
            stripeToken = request.POST['stripe_id']
            
            try:
                customer = stripe.Charge.create(
                    amount=int(100*total_amount), # convert to cents
                    currency='sgd',
                    description=f"Charge for {request.user}: ${total_amount}",
                    source = stripeToken
                )
                
                if customer.paid:
                    messages.success(request, "Payment successfully made. We will begin to process your order!")
                    
                    # create order if the charge was successful
                    order = Order.objects.create(
                        customer=request.user,
                        stripe_token=stripeToken
                    )
                    
                    # create order item for each items in that particular order
                    for item in cart:
                        product = get_object_or_404(Book, pk=int(item['id']))
                        price = item['total_price']
                        quantity = item['quantity_ordered']
                        
                        OrderItem.objects.create(order=order, price=price, quantity=quantity, product=product) 
                        
                        # update stock for each product
                        product.quantity = product.quantity - quantity
                        product.save()
                        
                    # send order confirmation email to user 160220
                    email_subject = 'Your Pick A Book\'s Order Receipt'
                    sender_email = settings.DEFAULT_FROM_EMAIL
                    recipient_email = [sender_email, request.user.email]
                    
                    # get order ID
                    object_record = Order.objects.filter(stripe_token=stripeToken)
                    order_id = list(object_record.values())[0]['id']
                    
            
                    context = {
                        'user': request.user,
                        'order_total': total_amount,
                        'shopping_cart': cart,
                        'order_id': order_id,
                        
                        # 220220
                        'delivery_fee': delivery_fee,
                    }
                    
                    # create and send the email
                    html_notification_message = render_to_string('Order/order_confirmation.template.html', context)
                    plain_message = strip_tags(html_notification_message)
                    msg = EmailMultiAlternatives(email_subject, plain_message, sender_email, recipient_email)
                    msg.attach_alternative(html_notification_message, "text/html")
                    msg.send()

                    # empty the shopping cart 
                    request.session['shopping_cart'] = {}
                
                    return redirect(reverse('get_index'))
                else:
                    messages.error(request, "Unable to take payment.")
                    
            # errors adapted from https://github.com/justdjango/django-ecommerce/blob/master/core/views.py
            except stripe.error.CardError as e:
            	body = e.json_body
            	err = body.get('error', {})
            	messages.error(request, f"{err.get('message')}")
            	return redirect(reverse('get_index'))
            	
            except stripe.error.RateLimitError as e:
            	# Too many requests made to the API too quickly
            	messages.error(request, "Rate Limit Error")
            	return redirect("get_index")
            
            except stripe.error.InvalidRequestError as e:
            	# Invalid parameters were supplied to Stripe's API
            	messages.error(request, "Ïnvalid parameters")
            	return redirect("get_index")
            
            except stripe.error.AuthenticationError as e:
            	# Authentication with Stripe's API failed
            	# (maybe you changed API keys recently)
            	messages.error(request, "Not authenticated")
            	return redirect("get_index")
            
            except stripe.error.APIConnectionError as e:
            	# Network communication with Stripe failed
            	messages.error(request, "Connection error")
            	return redirect("get_index")
            
            except stripe.error.StripeError as e:
            	# Display a very generic error to the user, and maybe send
            	# yourself an email
            	messages.error(request, "Something went wrong. You were not charged. Please try again.")
            	return redirect("get_index")
            
            except Exception as e:
            	# Send email to ourselves 
            	print(e)
            	messages.error(request, "An error occured. We have been notified and are currently looking into it.")
            	return redirect("get_index")

        else:
            messages.error(request, "We were unable to take a payment with that card!")
        
            return render(request, 'Order/checkout.template.html', {
                'publishable': settings.STRIPE_PUBLISHABLE_KEY,
                'payment_form': payment_form,
                'order_form': order_form,
                'amount': total_amount   
            })
            
    else:
        order_form = OrderForm()
        payment_form = PaymentForm()
        
        return render(request, 'Order/checkout.template.html', {
            'publishable': settings.STRIPE_PUBLISHABLE_KEY,
            'payment_form': payment_form,
            'order_form': order_form,
            'amount': total_amount           
        })
    
def confirm_checkout(request):
    # retrieve shopping cart info
    cart = request.session.get('shopping_cart', {})
    
    shopping_cart_list = list(cart.values())
    
    # total amount payable 
    total_amount = 0
    
    for elem in shopping_cart_list:
        total_amount = total_amount + float(elem['total_price'])
        total_amount = total_amount
    
    # round up total amount to 2 decimal points
    total_amount = round(total_amount, 2)
    
    # check if delivery fees is needed
    if total_amount < 100.00:
        delivery_fee = 3.95
    else:
        delivery_fee = 0.00
        
    # subtotal
    subtotal = round((total_amount + delivery_fee), 2)
    
    return render(request, 'Order/confirm_checkout.template.html', {
        'shopping_cart':cart,
        'amount': total_amount,
        'delivery_fee': delivery_fee,
        'subtotal': subtotal,
    })