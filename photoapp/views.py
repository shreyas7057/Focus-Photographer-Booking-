from django.shortcuts import render,redirect
from django.db.models import Q
from django.conf import settings
from django.core.mail import send_mail

from .models import Photographer,Category,Team,Gallery,Stat,Booking,Package,Service
# from .forms import BookingForm

# Create your views here.
# this view is created for searching the photographers, this is first page when website is opened.
def index(request):
    query = request.GET.get('q','')
    if query:
        queryset = (Q(location__icontains=query))
        results = Photographer.objects.filter(queryset).distinct()
    else:
       results = Photographer.objects.all()
    context = {
        'results':results,
        'query':query,
    }
    return render(request,'index.html',context)

